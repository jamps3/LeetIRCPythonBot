import asyncio
import json
import os
from typing import Callable, Optional

import requests
from bs4 import BeautifulSoup

import logger
from config import OTIEDOTE_FILE, STATE_FILE

BASE_URL = "https://otiedote.fi/"
RELEASE_URL_TEMPLATE = "https://otiedote.fi/release_view/{}"

# Where full releases get stored
JSON_FILE = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        OTIEDOTE_FILE,
    )
)

# Where latest processed ID is stored
CONFIG_STATE_FILE = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        STATE_FILE,
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
        state_file: str = CONFIG_STATE_FILE,
        json_file: str = JSON_FILE,
    ):
        self.callback = callback
        self.check_interval = check_interval
        self.state_file = state_file
        self.json_file = json_file

        self.running = False
        self._monitor_task = None

        self.latest_release = self._load_latest_release()

    # ---------------- Subscription management ----------------

    def _get_default_state(self) -> dict:
        """Return default state structure."""
        return {
            "otiedote": {
                "latest_release": 0,
                "filters": {},
                "subscribers": [],
            }
        }

    def _load_subscribers(self) -> list:
        """Load subscribers list from state.json."""
        state = self._load_state()
        return state.get("otiedote", {}).get("subscribers", [])

    def subscribe(self, nick: str) -> bool:
        """
        Add a subscriber to otiedote notifications.

        Args:
            nick: IRC nick to subscribe

        Returns:
            True if newly subscribed, False if already subscribed
        """
        nick = nick.lower().strip()
        subscribers = self._load_subscribers()

        if nick in subscribers:
            return False

        subscribers.append(nick)
        self._save_subscribers(subscribers)
        return True

    def unsubscribe(self, nick: str) -> bool:
        """
        Remove a subscriber from otiedote notifications.

        Args:
            nick: IRC nick to unsubscribe

        Returns:
            True if unsubscribed, False if not subscribed
        """
        nick = nick.lower().strip()
        subscribers = self._load_subscribers()

        if nick not in subscribers:
            return False

        subscribers.remove(nick)
        self._save_subscribers(subscribers)
        return True

    def get_subscribers(self) -> list:
        """Get list of current subscribers."""
        return self._load_subscribers().copy()

    def _save_subscribers(self, subscribers: list) -> None:
        """Save subscribers list to state.json."""
        data = {}

        # Load existing state if present
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf8") as f:
                    data = json.load(f)
            except Exception:
                data = {}

        data.setdefault("otiedote", {})
        data["otiedote"]["subscribers"] = subscribers

        # Atomic write with temporary file
        import tempfile
        from datetime import datetime

        temp_path = None
        try:
            target_dir = os.path.dirname(self.state_file) or "."
            os.makedirs(target_dir, exist_ok=True)

            data["last_updated"] = datetime.now().isoformat()

            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf8", dir=target_dir, delete=False, suffix=".json"
            ) as temp_file:
                json.dump(data, temp_file, ensure_ascii=False, indent=2)
                temp_path = temp_file.name

            os.replace(temp_path, self.state_file)
        except Exception:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass

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

    def _load_state(self) -> dict:
        """Load full state including filters from state.json."""
        if not os.path.exists(self.state_file):
            return {"otiedote": {"latest_release": 0, "filters": {}}}

        try:
            with open(self.state_file, "r", encoding="utf8") as f:
                data = json.load(f)
            return data
        except Exception:
            return {"otiedote": {"latest_release": 0, "filters": {}}}

    def _save_state(self, state: dict) -> None:
        """Save full state including filters to state.json."""
        import tempfile
        from datetime import datetime

        temp_path = None
        try:
            # Ensure target directory exists
            target_dir = os.path.dirname(self.state_file) or "."
            os.makedirs(target_dir, exist_ok=True)

            # Update timestamp
            state["last_updated"] = datetime.now().isoformat()

            # Save to a unique temporary file in the same directory, then rename atomically
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf8", dir=target_dir, delete=False, suffix=".json"
            ) as temp_file:
                json.dump(state, temp_file, ensure_ascii=False, indent=2)
                temp_path = temp_file.name

            # Atomic rename
            os.replace(temp_path, self.state_file)
        except Exception:
            # Clean up temp file on error
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass

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

    def load_otiedote_data(self):
        """Load otiedote data from JSON file.

        Returns:
            List of otiedote entries, or empty list if no data available.
        """
        id_map, _ = load_existing_ids()
        return list(id_map.values())

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

    def fetch_all_releases(
        self, start_id: int = DEFAULT_START_ID, max_releases: int = 500
    ) -> dict:
        """Fetch all releases starting from start_id and save to JSON file.

        Args:
            start_id: The release ID to start fetching from (default: DEFAULT_START_ID)
            max_releases: Maximum number of releases to fetch (default: 500)

        Returns:
            Dict with 'success', 'count', 'latest_id', and optional 'error' keys.
        """
        import time

        releases = []
        existing_ids = set()
        next_id = start_id
        fetched_count = 0
        consecutive_failures = 0
        max_consecutive_failures = 10  # Stop after 10 consecutive failures

        logger.info(f"Starting to fetch otiedote releases from #{start_id}...")

        while (
            fetched_count < max_releases
            and consecutive_failures < max_consecutive_failures
        ):
            try:
                release = fetch_release(next_id)

                if release:
                    releases.append(release)
                    existing_ids.add(release["id"])
                    consecutive_failures = 0
                    fetched_count += 1

                    if fetched_count % 50 == 0:
                        logger.info(
                            f"Fetched {fetched_count} releases so far (current: #{next_id})"
                        )
                else:
                    consecutive_failures += 1

                next_id += 1

                # Small delay to be nice to the server
                time.sleep(0.2)

            except Exception as e:
                logger.warning(f"Error fetching release #{next_id}: {e}")
                consecutive_failures += 1
                next_id += 1

        if releases:
            # Sort by ID
            releases.sort(key=lambda x: x["id"])

            # Save to JSON file
            try:
                # Ensure data directory exists
                os.makedirs(os.path.dirname(self.json_file), exist_ok=True)

                with open(self.json_file, "w", encoding="utf8") as f:
                    json.dump(releases, f, ensure_ascii=False, indent=2)

                logger.info(f"Saved {len(releases)} releases to {self.json_file}")
            except Exception as e:
                return {
                    "success": False,
                    "count": fetched_count,
                    "error": f"Failed to save JSON: {e}",
                }

            # Update state
            latest_id = max(r["id"] for r in releases)
            self.latest_release = latest_id
            self._save_latest_release(latest_id)

            logger.info(
                f"Completed! Fetched {len(releases)} releases, latest ID: #{latest_id}"
            )

            return {
                "success": True,
                "count": len(releases),
                "latest_id": latest_id,
                "start_id": start_id,
            }
        else:
            return {
                "success": False,
                "count": 0,
                "error": "No releases found. The website may be unavailable or the start_id is too high.",
            }


# Factory
def create_otiedote_service(
    callback, check_interval=CHECK_INTERVAL, state_file=CONFIG_STATE_FILE
):
    return OtiedoteService(callback, check_interval, state_file)
