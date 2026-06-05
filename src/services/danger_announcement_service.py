"""
Danger Announcement Service.

Monitors Finnish danger announcements from 112.fi and emits only the Finnish
announcement text.
"""

import hashlib
import os
import threading
import time
from typing import Callable, List, Optional

import requests
from bs4 import BeautifulSoup

from config import get_config
from logger import get_logger
from state_utils import load_json_file, update_json_file

logger = get_logger("DangerAnnouncementService")


class DangerAnnouncementService:
    """Service for monitoring Finnish danger announcements from 112.fi."""

    URL = "https://112.fi/etusivu"
    DEFAULT_CHECK_INTERVAL = 5 * 60

    def __init__(
        self,
        callback: Callable[[List[str]], None],
        state_file: Optional[str] = None,
        check_interval: int = DEFAULT_CHECK_INTERVAL,
        url: str = URL,
    ):
        self.callback = callback
        self.state_file = state_file
        self.check_interval = check_interval
        self.url = url
        self.running = False
        self.thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start monitoring danger announcements in a background thread."""
        if self.thread and self.thread.is_alive():
            return

        self.running = True
        self.thread = threading.Thread(
            target=self._monitor_loop,
            name="DangerAnnouncementMonitor",
            daemon=True,
        )
        self.thread.start()
        logger.info("Danger announcement service started.")

    def stop(self) -> None:
        """Stop monitoring danger announcements."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=30.0)
            if self.thread.is_alive():
                logger.warning("Danger announcement monitor did not stop cleanly")
        logger.info("Danger announcement service stopped.")

    def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self.running:
            try:
                announcements = self.check_new_announcements()
                if announcements:
                    self.callback(announcements)
            except Exception as e:
                logger.error(f"Error checking danger announcements: {e}")

            remaining_sleep = self.check_interval
            while remaining_sleep > 0 and self.running:
                chunk_sleep = min(remaining_sleep, 5.0)
                time.sleep(chunk_sleep)
                remaining_sleep -= chunk_sleep

    def check_new_announcements(self) -> List[str]:
        """Fetch, parse, deduplicate, and return new formatted announcements."""
        announcements = fetch_danger_announcements(self.url)
        seen_hashes = self._load_seen_hashes()
        new_messages = []

        for announcement in reversed(announcements):
            announcement_hash = self._get_announcement_hash(announcement)
            if announcement_hash in seen_hashes:
                continue

            seen_hashes.add(announcement_hash)
            new_messages.append(format_danger_announcement(announcement))

        if new_messages:
            self._save_seen_hashes(set(list(seen_hashes)[-50:]))

        return new_messages

    def _load_seen_hashes(self) -> set[str]:
        """Load previously seen danger-announcement hashes."""
        data = load_json_file(self.state_file, default=dict)
        if not isinstance(data, dict):
            return set()
        return set(data.get("danger_announcements", {}).get("seen_hashes", []))

    def _save_seen_hashes(self, seen_hashes: set[str]) -> None:
        """Save seen hashes while preserving the rest of state.json."""
        try:
            update_json_file(
                self.state_file,
                lambda data: self._with_danger_value(
                    data, "seen_hashes", list(seen_hashes)
                ),
                default=dict,
                strict=True,
            )
        except Exception as e:
            logger.warning(f"Failed to save danger announcement state: {e}")

    @staticmethod
    def _with_danger_value(data: dict, key: str, value):
        """Return state with one danger-announcement field updated."""
        if not isinstance(data, dict):
            data = {}
        data.setdefault("danger_announcements", {})
        data["danger_announcements"][key] = value
        return data

    @staticmethod
    def _get_announcement_hash(announcement: dict) -> str:
        """Generate a stable hash for an announcement."""
        text = "\n".join(
            [
                announcement.get("title", ""),
                announcement.get("date", ""),
                announcement.get("text", ""),
            ]
        )
        normalized = " ".join(text.split())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def fetch_danger_announcements(url: str = DangerAnnouncementService.URL) -> List[dict]:
    """Fetch 112.fi front page and parse Finnish danger announcements."""
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    return parse_danger_announcements_html(str(soup))


def parse_danger_announcements_html(html: str) -> List[dict]:
    """Parse Finnish danger announcements from a 112.fi HTML document."""
    soup = BeautifulSoup(html, "html.parser")
    announcements = []

    for heading in soup.find_all(["h1", "h2", "h3"]):
        title = heading.get_text(" ", strip=True)
        if title.lower() != "vaaratiedote":
            continue

        container = heading.find_parent("div") or heading.parent
        date_node = container.find(class_="date") if container else None
        paragraphs = container.find_all("p") if container else []
        finnish_text = next(
            (p.get_text(" ", strip=True) for p in paragraphs if p.get_text(strip=True)),
            "",
        )

        if not finnish_text:
            continue

        announcements.append(
            {
                "title": title,
                "date": date_node.get_text(" ", strip=True) if date_node else "",
                "text": finnish_text,
            }
        )

    return announcements


def format_danger_announcement(announcement: dict) -> str:
    """Format a danger announcement for IRC."""
    title = announcement.get("title", "Vaaratiedote")
    date = announcement.get("date", "")
    text = announcement.get("text", "")
    if date:
        return f"⚠ {title} {date}: {text}"
    return f"⚠ {title}: {text}"


def create_danger_announcement_service(
    callback: Callable[[List[str]], None],
    state_file: Optional[str] = None,
    check_interval: int = DangerAnnouncementService.DEFAULT_CHECK_INTERVAL,
) -> DangerAnnouncementService:
    """Create a danger-announcement monitoring service."""
    if state_file is None:
        state_file = get_config().state_file
    state_file = os.path.normpath(state_file)
    return DangerAnnouncementService(callback, state_file, check_interval)
