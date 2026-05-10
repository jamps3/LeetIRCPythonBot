import asyncio
import json
import os
import threading
from typing import Callable, Optional

import requests
from bs4 import BeautifulSoup

import logger
from config import OTIEDOTE_FILE, STATE_FILE
from state_utils import load_json_file, save_json_atomic, update_json_file

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

CHECK_INTERVAL = 15 * 60  # 15 min


# ----------------------------------------------------
# Helpers
# ----------------------------------------------------
def load_existing_ids(json_file: str = None):
    """Load previously saved releases from a release JSON file."""
    json_file = json_file or JSON_FILE
    if not os.path.exists(json_file):
        return {}, set()

    try:
        with open(json_file, "r", encoding="utf8") as f:
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
        self.thread: Optional[threading.Thread] = None

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
        try:
            update_json_file(
                self.state_file,
                lambda data: self._with_otiedote_value(
                    data, "subscribers", subscribers
                ),
                default=dict,
            )
        except Exception as e:
            logger.warning(f"Failed to save subscribers: {e}")

    # ---------------- State handling ----------------
    def _load_latest_release(self) -> int:
        """Load last processed ID from state.json."""
        data = load_json_file(self.state_file, default=dict)
        if not isinstance(data, dict):
            return DEFAULT_START_ID - 1
        return data.get("otiedote", {}).get("latest_release", DEFAULT_START_ID - 1)

    def _load_state(self) -> dict:
        """Load full state including filters from state.json."""
        data = load_json_file(self.state_file, default=self._get_default_state)
        return data if isinstance(data, dict) else self._get_default_state()

    def _save_state(self, state: dict) -> None:
        """Save full state including filters to state.json."""
        try:
            save_json_atomic(self.state_file, state)
        except Exception as e:
            logger.warning(f"Failed to save state: {e}")

    def _save_latest_release(self, id_val: int) -> None:
        """Update state.json cleanly with atomic writes."""
        try:
            update_json_file(
                self.state_file,
                lambda data: self._with_otiedote_value(data, "latest_release", id_val),
                default=dict,
            )

        except Exception as e:
            logger.warning(f"Failed to save state: {e}")

    @staticmethod
    def _with_otiedote_value(data: dict, key: str, value):
        """Return state data with one otiedote field updated."""
        if not isinstance(data, dict):
            data = {}
        data.setdefault("otiedote", {})
        data["otiedote"][key] = value
        return data

    # ---------------- Public API ----------------
    async def start(self):
        if self.running:
            return
        self.running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("🟢 Otiedote monitor started")

    async def run_until_stopped(self):
        """Run the monitor in the current event loop until stopped."""
        if self.running:
            return

        self.running = True
        logger.info("🟢 Otiedote monitor started")
        try:
            await self._monitor_loop()
        finally:
            self.running = False
            logger.info("🔴 Otiedote monitor stopped")

    def start_background(self):
        """Start monitoring in a dedicated daemon thread."""
        if self.thread and self.thread.is_alive():
            return

        self.thread = threading.Thread(
            target=self._run_background_loop,
            name="OtiedoteMonitor",
            daemon=True,
        )
        self.thread.start()

    def _run_background_loop(self):
        try:
            asyncio.run(self.run_until_stopped())
        except Exception as e:
            logger.error(f"Otiedote background monitor stopped unexpectedly: {e}")

    def stop_background(self, timeout: float = 30.0):
        """Stop a background-thread monitor."""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=timeout)
            if self.thread.is_alive():
                logger.warning("Otiedote monitor thread did not stop cleanly")

    async def stop(self):
        self.running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        self.stop_background(timeout=30.0)

        logger.info("🔴 Otiedote monitor stopped")

    # ---------------- Main loop ----------------
    async def _monitor_loop(self):
        while self.running:
            try:
                new_releases = self.check_new_releases()
                for release in new_releases:
                    logger.info(f"New Otiedote #{release['id']}: {release['title']}")
                    try:
                        self.callback(release)
                    except Exception as e:
                        logger.error(
                            f"Error in Otiedote callback for #{release['id']}: {e}"
                        )

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
        id_map, _ = load_existing_ids(self.json_file)
        return list(id_map.values())

    def _save_releases(self, releases: list) -> None:
        releases.sort(key=lambda x: x["id"])
        save_json_atomic(self.json_file, releases, update_timestamp=False)

    def check_new_releases(
        self, max_attempts: int = 10, max_releases: int = 20
    ) -> list:
        """Check for newly published releases without skipping unpublished IDs."""
        self.latest_release = self._load_latest_release()
        starting_latest = self.latest_release
        id_map, existing_ids = load_existing_ids(self.json_file)
        releases = list(id_map.values())
        new_releases = []

        next_id = max(self.latest_release + 1, DEFAULT_START_ID)
        misses = 0

        while misses < max_attempts and len(new_releases) < max_releases:
            logger.info(f"Checking Otiedote release #{next_id}")
            release = fetch_release(next_id)

            if release:
                if release["id"] not in existing_ids:
                    releases.append(release)
                    existing_ids.add(release["id"])
                    new_releases.append(release)

                self.latest_release = max(self.latest_release, release["id"])
                misses = 0
            else:
                misses += 1

            next_id += 1

        if new_releases:
            try:
                self._save_releases(releases)
            except Exception as e:
                logger.warning(f"Failed to save releases JSON: {e}")

        if new_releases or self.latest_release != starting_latest:
            self._save_latest_release(self.latest_release)

        return new_releases

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
                id_map, existing_ids = load_existing_ids(self.json_file)
                releases = list(id_map.values())
                if release["id"] not in existing_ids:
                    releases.append(release)

                try:
                    self._save_releases(releases)
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

        id_map, existing_ids = load_existing_ids(self.json_file)
        releases = list(id_map.values())
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
                    if release["id"] not in existing_ids:
                        releases.append(release)
                        existing_ids.add(release["id"])
                        fetched_count += 1
                    consecutive_failures = 0

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

        if fetched_count:
            # Sort by ID
            releases.sort(key=lambda x: x["id"])

            # Save to JSON file
            try:
                self._save_releases(releases)

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
                "count": fetched_count,
                "latest_id": latest_id,
                "start_id": start_id,
                "total_count": len(releases),
            }

        if releases:
            latest_id = max(r["id"] for r in releases)
            return {
                "success": True,
                "count": 0,
                "latest_id": latest_id,
                "start_id": start_id,
                "total_count": len(releases),
            }

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
