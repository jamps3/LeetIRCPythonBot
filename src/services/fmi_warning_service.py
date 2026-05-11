"""
FMI Warning Service Module

Monitors Finnish Meteorological Institute (FMI) weather warnings
via RSS feed and provides notifications for filtered locations.
"""

import hashlib
import json
import os
import re
import threading
import time
from typing import Callable, List, Optional, Set

import feedparser

from config import get_config
from logger import log


class FMIWarningService:
    """Service for monitoring FMI weather warnings."""

    FEED_URL = "https://alerts.fmi.fi/cap/feed/rss_fi-FI.rss"
    DEFAULT_CHECK_INTERVAL = 300  # 5 minutes

    # Locations to exclude from notifications
    EXCLUDED_LOCATIONS = [
        "ahvenanmaa",
        "etelä-pohjanmaa",
        "itämeren",
        "kainuu",
        "keski-",
        "keskiosa",
        "keski-lappi",
        "länsi-lappi",
        "maan länsiosa",
        "maan eteläosa",
        "maan pohjoisosa",
        "pohjois-pohjanmaa",
        "pohjanmaa",
        "merelle",
        "suomenlahden",
    ]

    # Locations to include (if empty, all locations except excluded are allowed)
    ALLOWED_LOCATIONS = [
        "joensuu",
        "itä-suomi",
        "pohjois-karjala",
        "itä-",
        "koko maa",
    ]

    def __init__(
        self,
        callback: Callable[[List[str]], None],
        state_file: str = None,
        check_interval: int = DEFAULT_CHECK_INTERVAL,
    ):
        """
        Initialize FMI warning service.

        Args:
            callback: Function to call with list of warning messages
            state_file: File to store seen warning hashes
            check_interval: Check interval in seconds
        """
        self.callback = callback
        self.state_file = state_file
        self.check_interval = check_interval
        self.running = False
        self.thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start monitoring FMI warnings in background thread."""
        if self.thread and self.thread.is_alive():
            return

        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        log(
            "✅ FMI warning service started.",
            level="INFO",
            context="FMI_WS",
            fallback_text="FMI warning service started.",
        )

    def stop(self) -> None:
        """Stop monitoring FMI warnings."""
        self.running = False
        if self.thread:
            # Join with timeout to allow graceful shutdown (30 seconds)
            self.thread.join(timeout=30.0)
            if self.thread.is_alive():
                log(
                    "FMI warning service thread did not stop cleanly within 30 second timeout",
                    level="WARNING",
                    context="FMI_WS",
                )
        log(
            "🛑 FMI warning service stopped.",
            level="INFO",
            context="FMI_WS",
            fallback_text="FMI warning service stopped.",
        )

    def _monitor_loop(self) -> None:
        """Main monitoring loop running in background thread."""
        while self.running:
            try:
                new_warnings = self.check_new_warnings()
                if new_warnings:
                    self.callback(new_warnings)
            except Exception as e:
                log(
                    f"Error checking FMI warnings: {e}", level="ERROR", context="FMI_WS"
                )

            # Sleep in smaller chunks to respond faster to shutdown requests
            remaining_sleep = self.check_interval
            while remaining_sleep > 0 and self.running:
                chunk_sleep = min(remaining_sleep, 5.0)  # Check every 5 seconds
                time.sleep(chunk_sleep)
                remaining_sleep -= chunk_sleep

    def check_new_warnings(self) -> List[str]:
        """
        Check for new FMI warnings.

        Returns:
            List of formatted warning messages
        """
        try:
            feed = feedparser.parse(self.FEED_URL)
            seen_hashes = self._load_seen_hashes()
            seen_data = self._load_seen_data()

            new_entries = []
            for entry in feed.entries:
                entry_hash = self._get_entry_hash(entry)
                if entry_hash not in seen_hashes:
                    new_entries.append((entry_hash, entry))

            if not new_entries:
                return []

            messages = []
            for entry_hash, entry in reversed(new_entries):
                message = self._format_warning_message(entry)
                if message:  # Only add if not filtered out
                    # Check for duplicate titles in the last 5 warnings
                    title = entry.get("title", "")
                    if not self._is_duplicate_title(title, seen_data):
                        messages.append(message)
                        seen_hashes.add(entry_hash)
                        # Add to seen data for duplicate checking
                        seen_data.append(
                            {
                                "title": self._normalize_title(title),
                                "timestamp": entry.get("published", ""),
                                "hash": entry_hash,
                            }
                        )

            # Keep only the 50 most recent hashes to prevent unlimited growth
            seen_hashes = set(list(seen_hashes)[-50:])
            self._save_seen_hashes(seen_hashes)

            # Keep only the last 10 warnings for duplicate checking
            seen_data = seen_data[-10:]
            self._save_seen_data(seen_data)

            return messages

        except Exception as e:
            log(f"Error fetching FMI warnings: {e}", level="ERROR", context="FMI_WS")
            return []

    def _get_entry_hash(self, entry: dict) -> str:
        """Generate hash for warning entry to detect duplicates."""
        title = entry.get("title", "")
        summary = entry.get("summary", "")

        normalized = self._normalize_title(title) + summary
        cleaned = " ".join(normalized.split())
        return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()

    def _load_seen_hashes(self) -> Set[str]:
        """Load previously seen warning hashes from state file."""
        data = self._load_state_data("seen hashes")
        if not isinstance(data, dict):
            return set()
        if "fmi_warnings" in data:
            return set(data["fmi_warnings"].get("seen_hashes", []))
        return set(data.get("seen_hashes", []))

    def _save_seen_hashes(self, hashes: Set[str]) -> None:
        """Save seen warning hashes to state file."""
        try:
            data = self._load_state_data("seen hashes", log_corrupt=False)
            self._save_state_data(
                self._with_fmi_value(data, "seen_hashes", list(hashes))
            )
        except Exception as e:
            print(f"Error saving seen hashes: {e}")
            log(f"Error saving seen hashes: {e}", level="ERROR", context="FMI_WS")

    def _load_seen_data(self) -> List[dict]:
        """Load previously seen warning data for duplicate checking."""
        data = self._load_state_data("seen data")
        if not isinstance(data, dict):
            return []
        if "fmi_warnings" in data:
            return data["fmi_warnings"].get("seen_data", [])
        return data.get("seen_data", [])

    def _save_seen_data(self, seen_data: List[dict]) -> None:
        """Save seen warning data to state file."""
        try:
            data = self._load_state_data("seen data", log_corrupt=False)
            self._save_state_data(self._with_fmi_value(data, "seen_data", seen_data))
        except Exception as e:
            print(f"Error saving seen data: {e}")
            log(f"Error saving seen data: {e}", level="ERROR", context="FMI_WS")

    def _load_state_data(self, reset_target: str, log_corrupt: bool = True) -> dict:
        """Load state data, reporting corrupt JSON for FMI warning state."""
        if not self.state_file or not os.path.exists(self.state_file):
            return {}

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            if log_corrupt:
                message = f"State file corrupted, resetting {reset_target}"
                print(message)
                log(message, level="WARNING", context="FMI_WS")
            return {}
        except OSError:
            return {}

        return data if isinstance(data, dict) else {}

    def _save_state_data(self, data: dict) -> None:
        """Save FMI warning state."""
        target_dir = os.path.dirname(self.state_file)
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)

        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def _with_fmi_value(data: dict, key: str, value):
        """Return state data with one FMI warning field updated."""
        if not isinstance(data, dict):
            data = {}
        data.setdefault("fmi_warnings", {})
        data["fmi_warnings"][key] = value
        return data

    def _normalize_title(self, title: str) -> str:
        """
        Extract only the END time from the warning title.
        Removes weekday, start time, dash, and surrounding spaces.
        """
        if not title:
            return ""

        t = title.lower()

        # Examples:
        # "ma 14.32 - 23.00", "ma 17.49 – 23.00", "ti 06.00-09.00"
        t = re.sub(
            r"\b(ma|ti|ke|to|pe|la|su)\s+\d{1,2}\.\d{2}\s*[–-]\s*\d{1,2}\.\d{2}", "", t
        )

        # Also match "klo 17.49–23.00"
        t = re.sub(r"klo\s*\d{1,2}\.\d{2}\s*[–-]\s*\d{1,2}\.\d{2}", "", t)

        # Clean multiple spaces
        t = re.sub(r"\s+", " ", t).strip()

        return t

    def _is_duplicate_title(self, title: str, seen_data: List[dict]) -> bool:
        """Check if a title is a duplicate of recently seen warnings."""
        if not title:
            return False

        # Clean and normalize title for comparison
        clean_title = self._normalize_title(title)

        for item in seen_data:
            seen_title = self._normalize_title(item.get("title", ""))
            if clean_title == seen_title:
                return True

        return False

    def _format_warning_message(self, entry: dict) -> Optional[str]:
        """
        Format warning entry into a message string.

        Args:
            entry: RSS feed entry

        Returns:
            Formatted message string or None if filtered out
        """
        title = "⚠ " + entry.get("title", "")
        summary = entry.get("summary", "")

        lower_title = title.lower()
        lower_summary = summary.lower()

        # Apply exclusion filter
        if any(excluded in lower_title for excluded in self.EXCLUDED_LOCATIONS):
            return None

        # Apply inclusion filter (if configured)
        if self.ALLOWED_LOCATIONS and not any(
            allowed in lower_title for allowed in self.ALLOWED_LOCATIONS
        ):
            return None

        # Apply color symbols
        title = self._apply_color_symbols(title)

        # Apply warning type symbols
        title = self._apply_warning_symbols(title, lower_title, lower_summary)

        # Clean up formatting
        title = title.replace(" maa-alueille:", "")
        title = title.replace("  ", " ")
        title = title.replace(": Paikoin", "Paikoin")

        return f"{title} | {summary} ⚠"

    def _apply_color_symbols(self, title: str) -> str:
        """Apply color symbols to warning title."""
        color_replacements = {
            "Punainen ": "🟥",
            "Oranssi ": "🟠",
            "Keltainen ": "🟡",
            "Vihreä ": "🟢",
        }

        for text, symbol in color_replacements.items():
            title = title.replace(text, symbol)

        return title

    def _apply_warning_symbols(
        self, title: str, lower_title: str, lower_summary: str
    ) -> str:
        """Apply warning type symbols to title."""
        if "sadevaroitus" in lower_title or "sadevaroitus" in lower_summary:
            title = title.replace("sadevaroitus", "🌧️ ")
        elif "raju ukonilma" in lower_title or "raju ukonilma" in lower_summary:
            title = title.replace("raju ukonilma", "🌩️ ")
        elif "tuulivaroitus" in lower_title or "tuulivaroitus" in lower_summary:
            title = title.replace("tuulivaroitus", "🌪️ ")
        elif (
            "maastopalovaroitus" in lower_title or "maastopalovaroitus" in lower_summary
        ):
            title = title.replace("maastopalovaroitus", "♨ ")
        elif "liikennesää" in lower_title or "liikennesää" in lower_summary:
            title = title.replace("liikennesää", "🚗 ")
        elif "aallokkovaroitus" in lower_title or "aallokkovaroitus" in lower_summary:
            title = title.replace("aallokkovaroitus", "🌊 ")

        return title


def create_fmi_warning_service(
    callback: Callable[[List[str]], None],
    state_file: str = None,
    check_interval: int = FMIWarningService.DEFAULT_CHECK_INTERVAL,
) -> FMIWarningService:
    """
    Factory function to create an FMI warning service instance.

    Args:
        callback: Function to call with warning messages
        state_file: File to store seen warning hashes (defaults to config value)
        check_interval: Check interval in seconds

    Returns:
        FMIWarningService instance
    """
    if state_file is None:
        config = get_config()
        state_file = config.state_file
    return FMIWarningService(callback, state_file, check_interval)
