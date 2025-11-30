import json
import os
import time

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://otiedote.fi/release_view/{}"
JSON_FILE = "data/otiedote.json"


# ----------------------------------------------------------------------
# Lataa aiemmat ID:t JSONista, jos tiedosto on jo olemassa
# ----------------------------------------------------------------------
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


# ----------------------------------------------------------------------
# Parsitaan yksittäinen tiedote
# ----------------------------------------------------------------------
def fetch_release(id):
    url = BASE_URL.format(id)
    r = requests.get(url, timeout=10)
    if r.status_code != 200:
        return None

    soup = BeautifulSoup(r.text, "html.parser")

    # Otsikko
    h1 = soup.find("h1")
    if not h1:
        return None
    title = h1.get_text(strip=True)
    # if "Tiedotetta ei löytynyt" in title or "Sinulla ei ole oikeuksia nähdä tätä sivua!" in title:
    if "Tiedotetta ei löytynyt" in title:
        print(f"ID {id} not found.")
        return None

    # Päivämäärä
    published_span = soup.find("span", string=lambda s: s and "Julkaistu" in s)
    date = (
        published_span.get_text(strip=True).replace("Julkaistu: ", "")
        if published_span
        else ""
    )

    # Tapahtumapaikka
    location = ""
    location_label = soup.find("b", string=lambda s: s and "Tapahtumapaikka" in s)
    if location_label:
        row = location_label.find_parent(class_="row")
        if row:
            div_content = row.find("div", class_="mb-3")
            if div_content:
                location = div_content.get_text(strip=True)

    # Julkaiseva organisaatio
    organization = ""
    org_label = soup.find("b", string=lambda s: s and "Julkaiseva organisaatio" in s)
    if org_label:
        col_parent = org_label.find_parent("div", class_="col-lg-2")
        if col_parent:
            col_auto = col_parent.find_next_sibling("div", class_="col-auto")
            if col_auto:
                mb3_div = col_auto.find("div", class_="mb-3")
                if mb3_div:
                    organization = mb3_div.get_text(strip=True)

    # Tapahtuman kuvaus
    content = ""
    description_block = soup.find("b", string=lambda s: s and "Tapahtuman kuvaus" in s)
    if description_block:
        row = description_block.find_parent(class_="row")
        if row:
            # Hae kaikki <p>-tagit rivin sisällä
            paragraphs = row.find_all("p")
            content = "\n".join(
                p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)
            )

    # Osallistuneet yksiköt
    units = []
    units_header = soup.find("b", string=lambda s: s and "Osallistuneet yksiköt" in s)
    if units_header:
        row = units_header.find_parent(class_="row")
        if row:
            list_root = row.find("ul")
            if list_root:
                units = [li.get_text(strip=True) for li in list_root.find_all("li")]

    return {
        "id": id,
        "title": title,
        "date": date,
        "location": location,
        "organization": organization,
        "content": content,
        "units": units,
        "url": url,
    }


# ----------------------------------------------------------------------
# Hakuun sisältyvä logiikka
# ----------------------------------------------------------------------
def fetch_until_limit(start_id=50, found_limit=10, missing_streak_limit=10):
    id_map, existing_ids = load_existing_ids()
    results = list(id_map.values())

    found_count = 0
    missing_streak = 0
    current_id = start_id
    updated = False  # Merkitsee, että JSONiin on tehty muutoksia

    print(f"Loaded {len(existing_ids)} existing IDs from JSON.")
    print(f"Starting from ID {start_id}...\n")

    while found_count < found_limit or missing_streak < missing_streak_limit:
        # OHITA JOS JO JSONISSA
        if current_id in existing_ids:
            existing_item = id_map[current_id]
            # Päivitä organisaatio, jos puuttuu
            if not existing_item.get("organization"):
                data = fetch_release(current_id)
                if data and data.get("organization"):
                    existing_item["organization"] = data["organization"]
                    print(
                        f"ID {current_id} existed but organization updated → {data['organization']}"
                    )
                    updated = True

            # Päivitä content, jos siellä lukee vain "Tapahtuman kuvaus:" tai se on tyhjä
            if existing_item.get(
                "content", ""
            ).strip() == "Tapahtuman kuvaus:" or not existing_item.get("content"):
                data = fetch_release(current_id)
                if data and data.get("content"):
                    existing_item["content"] = data["content"]
                    print(
                        f"ID {current_id} content updated → {data['content'][:60]}..."
                    )
                    updated = True

            current_id += 1
            continue

        print(f"Checking ID {current_id}...", end=" ")

        data = fetch_release(current_id)
        if data:
            print(f"FOUND → {data['title']}")
            results.append(data)
            id_map[current_id] = data
            existing_ids.add(current_id)

            found_count += 1
            missing_streak = 0
            updated = True  # Uusi ID lisätty
        else:
            print("missing")
            missing_streak += 1

        current_id += 1
        # time.sleep(0.1)  # Hyödytön, palvelin vastaa hitaasti joka tapauksessa

    # Tallennus JSONiin vain, jos jotain on päivittynyt
    if updated:
        # Tallennus JSONiin numerojärjestyksessä
        results_sorted = sorted(results, key=lambda x: x["id"])
        with open(JSON_FILE, "w", encoding="utf8") as f:
            json.dump(results_sorted, f, ensure_ascii=False, indent=2)

    print("\nSearch finished.")
    print(f"Found new IDs: {found_count}")
    print(f"Total IDs now in JSON: {len(results)}")


# ----------------------------------------------------------------------
if __name__ == "__main__":
    fetch_until_limit(start_id=2835, found_limit=10, missing_streak_limit=10)
