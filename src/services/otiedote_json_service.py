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
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "data",
        os.getenv("OTIEDOTE_FILE", "otiedote.json"),
    )
)

# Where latest processed ID is stored
STATE_FILE = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "data",
        os.getenv("STATE_FILE", "state.json"),
    )
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

        # Organization (Julkaiseva organisaatio)
        organization = ""
        org_label = soup.find(
            "b", string=lambda s: s and "Julkaiseva organisaatio" in s
        )
        if org_label:
            # Get the row/div containing the organization info
            row = org_label.find_parent(class_="row") or org_label.find_parent("div")
            if row:
                row_text = row.get_text(strip=True)
                # Extract organization from the row text
                if "Julkaiseva organisaatio:" in row_text:
                    organization = row_text.split("Julkaiseva organisaatio:", 1)[
                        1
                    ].strip()
                    # Clean up any extra whitespace or newlines
                    organization = " ".join(organization.split())

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
            "organization": organization,
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
        callback: Callable[[dict], None],
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
        """Update state.json cleanly with atomic writes."""
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

        # Atomic write with temporary file
        import tempfile
        from datetime import datetime

        temp_path = None
        try:
            # Ensure target directory exists
            target_dir = os.path.dirname(self.state_file) or "."
            os.makedirs(target_dir, exist_ok=True)

            # Update timestamp
            data["last_updated"] = datetime.now().isoformat()

            # Save to a unique temporary file in the same directory, then rename atomically
            with tempfile.NamedTemporaryFile(
                "w", delete=False, dir=target_dir, suffix=".tmp", encoding="utf8"
            ) as tmp:
                temp_path = tmp.name
                json.dump(data, tmp, ensure_ascii=False, indent=2)
                tmp.flush()
                os.fsync(tmp.fileno())

            # Atomic replace
            os.replace(temp_path, self.state_file)
            temp_path = None  # consumed

        except Exception as e:
            logger.warning(f"Failed to save state: {e}")
            # Clean up temporary file if it exists
            try:
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception:
                pass

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

                    # Notify bot with full release data
                    self.callback(release)

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

    def fetch_next_release(self) -> Optional[dict]:
        """Manually fetch the next release after the current latest one."""
        # Reload latest_release from state.json to ensure we have the most current value
        # (in case the monitoring thread has updated it)
        self.latest_release = self._load_latest_release()

        # Try up to 3 releases ahead in case there are gaps (some releases may be inaccessible)
        max_attempts = 3
        for attempt in range(max_attempts):
            next_id = self.latest_release + 1 + attempt
            logger.info(
                f"fetch_next_release: attempting to fetch release #{next_id} (attempt {attempt + 1}/{max_attempts})"
            )
            release = fetch_release(next_id)
            if release:
                # Update state
                self.latest_release = release["id"]
                self._save_latest_release(self.latest_release)

                # Add to JSON file
                id_map, existing_ids = load_existing_ids()
                releases = list(id_map.values())
                releases.append(release)

                try:
                    with open(self.json_file, "w", encoding="utf8") as f:
                        json.dump(releases, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    logger.warning(f"Failed to save releases JSON: {e}")

                logger.info(
                    f"Manually fetched Otiedote #{release['id']}: {release['title']}"
                )
                return release

        logger.info(
            f"fetch_next_release: no accessible releases found in next {max_attempts} attempts after #{self.latest_release}"
        )
        return None


# Factory
def create_otiedote_service(
    callback, check_interval=CHECK_INTERVAL, state_file=STATE_FILE
):
    return OtiedoteService(callback, check_interval, state_file)
