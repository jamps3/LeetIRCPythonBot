import asyncio
import json
import os
import signal
from typing import Callable, Optional

import requests
from bs4 import BeautifulSoup

from logger import log

RELEASE_URL_TEMPLATE = "https://otiedote.fi/release_view/{}"
JSON_FILE = "otiedote.json"
CHECK_INTERVAL = 5 * 60  # 5 minuuttia


class OtiedoteService:
    def __init__(self, callback: Callable[[dict], None]):
        self._task = None  # initialize the task holder
        self.callback = callback
        self._running = False
        self.stop_requested = False

        self.results = []
        self.id_map = {}
        self.existing_ids = set()
        self.next_id = 1

        self._load_existing()
        log(f"Starting OTIEDOTE service from ID {self.next_id}", "INFO", "OTIEDOTE")

        # Ctrl+C signaali
        signal.signal(signal.SIGINT, self._handle_stop_signal)

    # --------------------------------------------------
    def _load_existing(self):
        if not os.path.exists(JSON_FILE):
            self.results = []
            self.id_map = {}
            self.existing_ids = set()
            self.next_id = 1
            return

        try:
            with open(JSON_FILE, "r", encoding="utf8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            log(
                "otiedote.json parse error, starting with empty dataset",
                "ERROR",
                "OTIEDOTE",
            )
            data = []

        self.results = sorted(data, key=lambda i: i["id"])
        self.id_map = {item["id"]: item for item in self.results}
        self.existing_ids = set(self.id_map.keys())
        self.next_id = max(self.existing_ids) + 1 if self.existing_ids else 1

    # --------------------------------------------------
    def _save_json(self):
        self.results = sorted(self.results, key=lambda x: x["id"])
        with open(JSON_FILE, "w", encoding="utf8") as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)

    # --------------------------------------------------
    def _handle_stop_signal(self, sig, frame):
        self.stop_requested = True
        log("Stop signal received, shutting down service...", "INFO", "OTIEDOTE")

    # --------------------------------------------------
    def fetch_release(self, id: int) -> Optional[dict]:
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

            # Organisaatio
            org_block = soup.find(
                "b", string=lambda s: s and "Julkaiseva organisaatio" in s
            )
            organization = ""
            if org_block:
                parent = org_block.find_parent("div")
                if parent:
                    div = parent.find_next("div", class_="mb-3")
                    if div:
                        organization = div.get_text(strip=True)

            # Päivämäärä
            published_span = soup.find("span", string=lambda s: s and "Julkaistu" in s)
            date = ""
            if published_span:
                date = published_span.get_text(strip=True).replace("Julkaistu: ", "")

            # Tapahtumapaikka
            location = ""
            loc_b = soup.find("b", string=lambda s: s and "Tapahtumapaikka" in s)
            if loc_b:
                parent = loc_b.parent
                location = (
                    parent.get_text(strip=True).replace("Tapahtumapaikka:", "").strip()
                )

            content = ""
            description_block = soup.find(
                "b", string=lambda s: s and "Tapahtuman kuvaus" in s
            )
            if description_block:
                row = description_block.find_parent(class_="row")
                if row:
                    # Hae kaikki <p>-tagit rivin sisällä
                    paragraphs = row.find_all("p")
                    content = "\n".join(
                        p.get_text(strip=True)
                        for p in paragraphs
                        if p.get_text(strip=True)
                    )

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
                "organization": organization,
                "url": url,
            }
        except Exception as e:
            log(f"Failed to fetch release {id}: {e}", "ERROR", "OTIEDOTE")
            return None

    # --------------------------------------------------
    async def start(self, missing_streak_limit: int = 10):
        self._running = True
        log("OTIEDOTE service started.", "INFO", "OTIEDOTE")

        missing_streak = 0
        while not self.stop_requested:
            # Run the blocking fetch in a separate thread
            release = await asyncio.to_thread(self.fetch_release, self.next_id)

            if release:
                missing_streak = 0
                if release["id"] not in self.existing_ids:
                    # Save all releases
                    self.results.append(release)
                    self.existing_ids.add(release["id"])
                    await asyncio.to_thread(self._save_json)

                    # Send only Pohjois-Karjalan pelastuslaitos
                    if release["organization"] == "Pohjois-Karjalan pelastuslaitos":
                        self.callback(release)

                    log(
                        f"Saved release {release['id']} - {release['title']}",
                        "INFO",
                        "OTIEDOTE",
                    )
            else:
                missing_streak += 1
                if missing_streak >= missing_streak_limit:
                    log(
                        f"Reached {missing_streak_limit} consecutive missing IDs, pausing.",
                        "WARNING",
                        "OTIEDOTE",
                    )
                    missing_streak = 0
                    # Instead of one long sleep, break into smaller chunks
                    pause_time = CHECK_INTERVAL
                    step = 5  # seconds
                    for _ in range(pause_time // step):
                        if self.stop_requested:
                            break
                        await asyncio.sleep(step)

                    # retry same next_id after pause
                    continue

            self.next_id += 1
            await asyncio.sleep(2)  # short sleep to avoid hammering server

        log("OTIEDOTE service stopped.", "INFO", "OTIEDOTE")

    async def stop(self):
        # perform async cleanup, e.g. cancelling tasks
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


# --------------------------------------------------
# Factory-funktio bottia varten
# --------------------------------------------------
def create_otiedote_service(callback: Callable[[dict], None]) -> OtiedoteService:
    return OtiedoteService(callback)
