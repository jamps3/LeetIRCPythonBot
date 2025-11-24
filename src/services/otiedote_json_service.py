import asyncio
import json
import logging
import os
import time
from typing import Callable, Optional

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://otiedote.fi/pohjois-karjalan-pelastuslaitos"
RELEASE_URL_TEMPLATE = "https://otiedote.fi/release_view/{}"
JSON_FILE = "../../otiedote.json"
CHECK_INTERVAL = 5 * 60  # 5 minutes
START_ID = 50  # aloitus-ID


# -------------------------
# Lataa jo haetut tiedotteet
# -------------------------
def load_existing_ids():
    if not os.path.exists(JSON_FILE):
        return {}, set()
    with open(JSON_FILE, "r", encoding="utf8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return {}, set()
    id_map = {item["id"]: item for item in data}
    return id_map, set(id_map.keys())


# -------------------------
# Hae yksittäinen tiedote
# -------------------------
def fetch_release(id: int) -> Optional[dict]:
    url = RELEASE_URL_TEMPLATE.format(id)
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        h1 = soup.find("h1")
        if not h1:
            return None
        title = h1.get_text(strip=True)
        if (
            "Tiedotetta ei löytynyt" in title
            or "Sinulla ei ole oikeuksia nähdä tätä sivua!" in title
        ):
            return None

        # Päivämäärä
        published_span = soup.find("span", string=lambda s: s and "Julkaistu" in s)
        date = (
            published_span.get_text(strip=True).replace("Julkaistu: ", "")
            if published_span
            else ""
        )

        # Sijainti
        location_label = soup.find("b", string=lambda s: s and "Tapahtumapaikka" in s)
        location = ""
        if location_label:
            parent = location_label.parent
            location = (
                parent.get_text(strip=True).replace("Tapahtumapaikka:", "").strip()
            )

        # Kuvaus
        description_block = soup.find(
            "b", string=lambda s: s and "Tapahtuman kuvaus" in s
        )
        content = ""
        if description_block:
            for sibling in description_block.parent.find_next_siblings():
                content = sibling.get_text("\n", strip=True)
                break

        # Osallistuneet yksiköt
        units = []
        units_header = soup.find(
            "b", string=lambda s: s and "Osallistuneet yksiköt" in s
        )
        if units_header:
            list_root = units_header.find_parent("div").find_next("ul")
            if list_root:
                units = [li.get_text(strip=True) for li in list_root.find_all("li")]

        return {
            "id": id,
            "title": title,
            "date": date,
            "location": location,
            "content": content,
            "units": units,
            "url": url,
        }
    except Exception as e:
        logging.warning(f"Failed to fetch release {id}: {e}")
        return None


# -------------------------
# Service loop
# -------------------------
async def otiedote_service(callback: Callable[[dict], None]):
    id_map, existing_ids = load_existing_ids()
    results = list(id_map.values())
    next_id = START_ID

    while True:
        try:
            release = fetch_release(next_id)
            if release and release["id"] not in existing_ids:
                results.append(release)
                existing_ids.add(release["id"])
                callback(release)
                # Tallenna JSONiin
                with open(JSON_FILE, "w", encoding="utf8") as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)
                logging.info(f"Saved release {release['id']}: {release['title']}")
            next_id += 1
        except Exception as e:
            logging.error(f"Error in service loop: {e}")

        await asyncio.sleep(CHECK_INTERVAL)


# -------------------------
# Esimerkkikäyttö
# -------------------------
def my_callback(release: dict):
    print(
        f"New release: {release['title']} ({release['date']}) at {release['location']}"
    )
    print(f"Units: {', '.join(release['units']) if release['units'] else 'N/A'}")
    print(f"URL: {release['url']}\n")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(otiedote_service(my_callback))
