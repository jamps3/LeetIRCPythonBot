"""
Leet Detection System

Detects "1337" patterns in high-precision timestamps and awards different
levels of leet achievements based on the position and frequency of occurrence.
Saves all detected leets to a JSON file for historical tracking.
"""

import json
import os
import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from logger import get_logger


class LeetDetector:
    """
    Detects leet (1337) patterns in nanosecond-precision timestamps.

    Achievement levels based on where "1337" appears in the timestamp:
    - Ultimate Leet: Perfect "13:37:13.371337133" format
    - Mega Leet: "1337" appears 3+ times in the timestamp
    - Super Leet: "1337" appears 2 times in the timestamp
    - Leet: "1337" appears once in timestamp (but not only from hours and minutes when time is 13:37)
    - Nano Leet: "1337" appears only in nanosecond digits
    """

    def __init__(self, leet_history_file: str = "data/leet_detections.json"):
        """Initialize the leet detector."""
        self.logger = get_logger("LeetDetector")
        self.leet_history_file = leet_history_file

        # Achievement levels and their criteria
        self.achievement_levels = {
            "ultimate": {
                "name": "Ultimate Leet!!",
                "emoji": "🏆👑",
                "criteria": "Perfect 13:37:13.371337133 format",
                "min_count": 1,
            },
            "heroic": {
                "name": "Heroic Leet!!",
                "emoji": "🥇🚀",
                "criteria": "Almost perfect 13:37:13.371337 format",
                "min_count": 1,
            },
            "mega": {
                "name": "Mega Leet!",
                "emoji": "🎯🔥",
                "criteria": "1337 appears 3+ times",
                "min_count": 3,
            },
            "super": {
                "name": "Super Leet!",
                "emoji": "⭐💫",
                "criteria": "1337 appears 2 times",
                "min_count": 2,
            },
            "leet": {
                "name": "Leet!",
                "emoji": "🎊✨",
                "criteria": "1337 appears in time part",
                "min_count": 1,
            },
            "nano": {
                "name": "Nano Leet",
                "emoji": "🔬⚡",
                "criteria": "1337 appears only in nanoseconds",
                "min_count": 1,
            },
        }

    def get_timestamp_with_nanoseconds(self) -> str:
        """
        Get current timestamp with nanosecond precision.

        Returns:
            Formatted timestamp string like "13:37:13.371337133"
        """
        now = datetime.now()
        nanoseconds = time.time_ns() % 1_000_000_000

        # Format: HH:MM:SS.nnnnnnnnn
        return f"{now.strftime('%H:%M:%S')}.{nanoseconds:09d}"

    def detect_leet_patterns(self, timestamp: str) -> Dict[str, any]:
        """
        Detect leet patterns in a timestamp string.

        Args:
            timestamp: Timestamp string like "13:37:13.371337133"

        Returns:
            Dictionary with detection results
        """
        # Remove colons and dots to get pure number string for counting
        pure_numbers = re.sub(r"[:.]+", "", timestamp)

        # Split timestamp into components
        if "." in timestamp:
            time_part, nano_part = timestamp.split(".", 1)
        else:
            time_part = timestamp
            nano_part = ""

        # Count total occurrences of "1337"
        total_count = len(re.findall(r"1337", pure_numbers))

        # Count occurrences in different parts
        time_count = len(re.findall(r"1337", time_part.replace(":", "")))
        nano_count = len(re.findall(r"1337", nano_part))

        # Check for ultimate leet pattern (perfect 13:37:13.371337133)
        is_ultimate = self._check_ultimate_pattern(timestamp)

        # Check for heroic leet pattern (13:37:13.371337)
        is_heroic = self._check_heroic_pattern(timestamp)

        # Find all positions where 1337 occurs
        positions = []
        for match in re.finditer(r"1337", pure_numbers):
            positions.append(match.start())

        return {
            "timestamp": timestamp,
            "pure_numbers": pure_numbers,
            "total_count": total_count,
            "time_count": time_count,
            "nano_count": nano_count,
            "is_ultimate": is_ultimate,
            "is_heroic": is_heroic,
            "positions": positions,
            "time_part": time_part,
            "nano_part": nano_part,
        }

    def _check_ultimate_pattern(self, timestamp: str) -> bool:
        """
        Check if timestamp matches the ultimate leet pattern.

        Args:
            timestamp: Timestamp string

        Returns:
            True if it matches 13:37:13.371337133 pattern
        """
        # The ultimate pattern: 13:37:13.371337133
        # Hours=13, Minutes=37, Seconds=13, Nanoseconds=371337133
        pattern = r"^13:37:13\.371337133$"
        return bool(re.match(pattern, timestamp))

    def _check_heroic_pattern(self, timestamp: str) -> bool:
        """
        Check if timestamp matches the ultimate leet pattern.

        Args:
            timestamp: Timestamp string

        Returns:
            True if it matches 13:37:13.371337 pattern
        """
        # The ultimate pattern: 13:37:13.371337
        # Hours=13, Minutes=37, Seconds=13, Nanoseconds=371337
        return timestamp.startswith("13:37:13.371337")

    def determine_achievement_level(
        self, detection_result: Dict[str, any]
    ) -> Optional[str]:
        """
        Determine the achievement level based on detection results.

        Args:
            detection_result: Result from detect_leet_patterns()

        Returns:
            Achievement level string or None if no achievement
        """
        # Check for ultimate leet first
        if detection_result["is_ultimate"]:
            return "ultimate"

        # Check for heroic leet second
        if detection_result["is_heroic"]:
            return "heroic"

        total_count = detection_result["total_count"]
        time_count = detection_result["time_count"]
        nano_count = detection_result["nano_count"]

        # No 1337 found
        if total_count == 0:
            return None

        # Mega leet: 3+ occurrences
        if total_count >= 3:
            return "mega"

        # Super leet: exactly 2 occurrences
        if total_count == 2:
            return "super"

        # Ignore trivial 13:37 where the only occurrence comes from hours+minutes
        try:
            hh_mm = detection_result["time_part"].split(":", 2)[:2]
            if (
                len(hh_mm) == 2
                and hh_mm[0] == "13"
                and hh_mm[1] == "37"
                and total_count == 1
                and nano_count == 0
            ):
                return None
        except Exception:
            # If parsing fails, fall through to regular checks
            pass

        # Regular leet: 1 occurrence in time part (excluding trivial 13:37-only case)
        if time_count > 0:
            return "leet"

        # Nano leet: 1 occurrence only in nanoseconds
        if nano_count > 0:
            return "nano"

        return None

    def format_achievement_message(
        self,
        nick: str,
        timestamp: str,
        achievement_level: str,
        user_message: str = None,
    ) -> str:
        """
        Format the achievement message for IRC.

        Args:
            nick: Nickname who achieved the leet
            timestamp: The timestamp that triggered the achievement
            achievement_level: Level of achievement
            user_message: The message text the user sent (optional)

        Returns:
            Formatted message string
        """
        achievement = self.achievement_levels[achievement_level]

        base_message = (
            f"{achievement['emoji']} {achievement['name']} [{nick}] {timestamp}"
        )

        # Add user message in quotes if provided
        if user_message:
            base_message += f' "{user_message}"'

        return base_message

    def _load_leet_history(self) -> List[Dict]:
        """
        Load leet detection history from JSON file.

        Returns:
            List of leet detection records
        """
        if not os.path.exists(self.leet_history_file):
            return []

        try:
            with open(self.leet_history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            self.logger.error(f"Failed to load leet history: {e}")
            return []

    def _save_leet_detection(
        self,
        nick: str,
        timestamp: str,
        achievement_level: str,
        user_message: Optional[str] = None,
    ) -> None:
        """
        Save a leet detection to the history file.

        Args:
            nick: Nickname who achieved the leet
            timestamp: The timestamp that triggered the achievement
            achievement_level: Level of achievement
            user_message: The message text the user sent (optional)
        """
        detection_record = {
            "datetime": datetime.now().isoformat(),
            "nick": nick,
            "timestamp": timestamp,
            "achievement_level": achievement_level,
            "user_message": user_message,
            "achievement_name": self.achievement_levels[achievement_level]["name"],
            "emoji": self.achievement_levels[achievement_level]["emoji"],
        }

        try:
            history = self._load_leet_history()
            history.append(detection_record)

            with open(self.leet_history_file, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2, ensure_ascii=False)

            self.logger.debug(f"Saved leet detection to {self.leet_history_file}")
        except IOError as e:
            self.logger.error(f"Failed to save leet detection: {e}")

    def get_leet_history(self, limit: Optional[int] = None) -> List[Dict]:
        """
        Get leet detection history.

        Args:
            limit: Maximum number of records to return (most recent first)

        Returns:
            List of leet detection records
        """
        history = self._load_leet_history()
        # Sort by datetime descending (most recent first)
        history.sort(key=lambda x: x.get("datetime", ""), reverse=True)

        if limit:
            return history[:limit]
        return history

    def check_message_for_leet(
        self,
        nick: str,
        message_time: Optional[str] = None,
        user_message: Optional[str] = None,
    ) -> Optional[Tuple[str, str]]:
        """
        Check if a message timestamp contains leet patterns.

        Args:
            nick: Nickname of the message sender
            message_time: Optional timestamp, uses current time if None
            user_message: Optional user message text to include in achievement

        Returns:
            Tuple of (achievement_message, achievement_level) or None
        """
        if message_time is None:
            message_time = self.get_timestamp_with_nanoseconds()

        detection_result = self.detect_leet_patterns(message_time)
        achievement_level = self.determine_achievement_level(detection_result)

        if achievement_level:
            message = self.format_achievement_message(
                nick, message_time, achievement_level, user_message
            )

            # Save the detection to history
            self._save_leet_detection(
                nick, message_time, achievement_level, user_message
            )

            self.logger.info(
                f"Leet detected: {achievement_level} for {nick} at {message_time} - message: {user_message or 'N/A'}"
            )
            return (message, achievement_level)

        return None

    def get_achievement_stats(self) -> Dict[str, Dict[str, any]]:
        """
        Get statistics about all achievement levels.

        Returns:
            Dictionary with achievement level information
        """
        return self.achievement_levels.copy()


def create_leet_detector() -> LeetDetector:
    """
    Factory function to create a LeetDetector instance.

    Returns:
        LeetDetector instance
    """
    return LeetDetector()
