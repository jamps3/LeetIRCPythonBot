import asyncio
import json
import os
from typing import Callable, Optional

import requests
from bs4 import BeautifulSoup

import logger

BASE_URL = "https://otiedote.fi/"
RELEASE_URL_TEMPLATE = "https://otiedote.fi/release_view/{}"

# Where full releases get stored
JSON_FILE = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "otiedote.json")
)

# Where latest processed ID is stored
STATE_FILE = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "state.json")
)

DEFAULT_START_ID = 2830  # fallback

CHECK_INTERVAL = 5 * 60  # 5 min


# ----------------------------------------------------
# Helpers
# ----------------------------------------------------
def load_existing_ids():
    """Load previously saved releases from JSON_FILE."""
    if not os.path.exists(JSON_FILE):
        return {}, set()

    try:
        with open(JSON_FILE, "r", encoding="utf8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}, set()

    id_map = {item["id"]: item for item in data}
    return id_map, set(id_map.keys())


def fetch_release(id: int) -> Optional[dict]:
    """Fetch a release page and parse it into a dict."""
    url = RELEASE_URL_TEMPLATE.format(id)

    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return None

        soup = BeautifulSoup(r.text, "html.parser")

        # Title
        h1 = soup.find("h1")
        if not h1:
            return None

        title = h1.get_text(strip=True)
        if "Tiedotetta ei löytynyt" in title or "Sinulla ei ole oikeuksia" in title:
            return None

        # Published date
        date = ""
        published_span = soup.find("span", string=lambda s: s and "Julkaistu" in s)
        if published_span:
            date = published_span.get_text(strip=True).replace("Julkaistu: ", "")

        # Location
        location = ""
        location_label = soup.find("b", string=lambda s: s and "Tapahtumapaikka" in s)
        if location_label:
            parent = location_label.parent
            location = (
                parent.get_text(strip=True).replace("Tapahtumapaikka:", "").strip()
            )

        # Description
        content = ""
        description_block = soup.find(
            "b", string=lambda s: s and "Tapahtuman kuvaus" in s
        )
        if description_block:
            row = description_block.find_parent(class_="row")
            if row:
                paragraphs = row.find_all("p")
                content = "\n".join(
                    p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)
                )

        # Units
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
        logger.warning(f"Failed to fetch release {id}: {e}")
        return None


# ----------------------------------------------------
# Service Class
# ----------------------------------------------------
class OtiedoteService:
    """Async monitoring service for otiedote.fi releases."""

    DEFAULT_CHECK_INTERVAL = 5 * 60

    def __init__(
        self,
        callback: Callable[[str, str, Optional[str]], None],
        check_interval: int = DEFAULT_CHECK_INTERVAL,
        state_file: str = STATE_FILE,
        json_file: str = JSON_FILE,
    ):
        self.callback = callback
        self.check_interval = check_interval
        self.state_file = state_file
        self.json_file = json_file

        self.running = False
        self._monitor_task = None

        self.latest_release = self._load_latest_release()

    # ---------------- State handling ----------------
    def _load_latest_release(self) -> int:
        """Load last processed ID from state.json."""
        if not os.path.exists(self.state_file):
            return DEFAULT_START_ID - 1

        try:
            with open(self.state_file, "r", encoding="utf8") as f:
                data = json.load(f)

            return data.get("otiedote", {}).get("latest_release", DEFAULT_START_ID - 1)

        except Exception:
            return DEFAULT_START_ID - 1

    def _save_latest_release(self, id_val: int) -> None:
        """Update state.json cleanly."""
        data = {}

        # Load existing state if present
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf8") as f:
                    data = json.load(f)
            except Exception:
                data = {}

        data.setdefault("otiedote", {})
        data["otiedote"]["latest_release"] = id_val

        try:
            with open(self.state_file, "w", encoding="utf8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save state: {e}")

    # ---------------- Public API ----------------
    async def start(self):
        if self.running:
            return
        self.running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("🟢 Otiedote monitor started")

    async def stop(self):
        self.running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        logger.info("🔴 Otiedote monitor stopped")

    # ---------------- Main loop ----------------
    async def _monitor_loop(self):
        id_map, existing_ids = load_existing_ids()
        releases = list(id_map.values())
        next_id = max(self.latest_release + 1, DEFAULT_START_ID)

        while self.running:
            try:
                release = fetch_release(next_id)
                if release and release["id"] not in existing_ids:

                    # Add to memory
                    releases.append(release)
                    existing_ids.add(release["id"])

                    # Compose description for callback
                    parts = []
                    if release.get("location"):
                        parts.append(f"Sijainti: {release['location']}")
                    if release.get("content"):
                        parts.append(release["content"])
                    if release.get("units"):
                        parts.append(
                            "Osallistuneet yksiköt: " + ", ".join(release["units"])
                        )
                    description = "\n".join(parts).strip()

                    # Notify bot
                    self.callback(release["title"], release["url"], description)

                    # Save entire JSON list
                    try:
                        with open(self.json_file, "w", encoding="utf8") as f:
                            json.dump(releases, f, ensure_ascii=False, indent=2)
                    except Exception as e:
                        logger.warning(f"Failed to save releases JSON: {e}")

                    # Save state
                    self.latest_release = release["id"]
                    self._save_latest_release(self.latest_release)

                    logger.info(f"New Otiedote #{release['id']}: {release['title']}")

                next_id += 1

            except Exception as e:
                logger.error(f"Error in Otiedote loop: {e}")

            # Sleep in chunks so stop() is responsive
            sleep_chunk = min(1.0, self.check_interval / 10)
            slept = 0
            while slept < self.check_interval and self.running:
                try:
                    await asyncio.sleep(sleep_chunk)
                except asyncio.CancelledError:
                    return
                slept += sleep_chunk

    # ---------------- Utility ----------------
    def get_latest_release_info(self):
        return {
            "latest_release": self.latest_release,
            "running": self.running,
            "state_file": self.state_file,
            "json_file": self.json_file,
        }


# Factory
def create_otiedote_service(callback, check_interval=CHECK_INTERVAL):
    return OtiedoteService(callback, check_interval)
