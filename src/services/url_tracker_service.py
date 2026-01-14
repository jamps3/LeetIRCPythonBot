"""
URL Tracker Service Module

Tracks URLs posted in channels and detects duplicates with "Wanha!" messages.
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from logger import get_logger

logger = get_logger("URLTrackerService")


class URLTrackerService:
    """Service for tracking URLs posted in IRC channels."""

    def __init__(self, data_dir: str = "data"):
        """
        Initialize URL tracker service.

        Args:
            data_dir: Directory where data files are stored
        """
        self.data_dir = Path(data_dir)
        self.urls_file = self.data_dir / "urls.json"
        self.urls_data: Dict[str, Dict] = {}

        # Ensure data directory exists
        self.data_dir.mkdir(exist_ok=True)

        # Load existing URL data
        self._load_urls()

    def _load_urls(self):
        """Load URL tracking data from file."""
        try:
            if self.urls_file.exists():
                with open(self.urls_file, "r", encoding="utf-8") as f:
                    self.urls_data = json.load(f)
                logger.info(f"Loaded URL tracking data for {len(self.urls_data)} URLs")
            else:
                self.urls_data = {}
                logger.info("No existing URL tracking data found, starting fresh")
        except Exception as e:
            logger.error(f"Error loading URL data: {e}")
            self.urls_data = {}

    def _save_urls(self):
        """Save URL tracking data to file."""
        try:
            with open(self.urls_file, "w", encoding="utf-8") as f:
                json.dump(self.urls_data, f, ensure_ascii=False, indent=2)
            logger.debug(f"Saved URL tracking data for {len(self.urls_data)} URLs")
        except Exception as e:
            logger.error(f"Error saving URL data: {e}")

    def track_url(
        self, url: str, nick: str, server_name: str, timestamp: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Track a URL and return whether it was seen before (case insensitive, trailing slash ignored).

        Args:
            url: The URL to track
            nick: Nickname of the user who posted it
            server_name: Server name
            timestamp: ISO timestamp string, uses current time if None

        Returns:
            Tuple of (is_duplicate, first_seen_timestamp)
            is_duplicate: True if URL was seen before (case insensitive, trailing slash ignored)
            first_seen_timestamp: ISO timestamp of first sighting, None if new
        """
        if not timestamp:
            timestamp = datetime.now().isoformat()

        # Normalize URL: strip whitespace, trailing slashes, and convert to lowercase for comparison
        normalized_url = re.sub(r"/$", "", url.strip()).lower()

        if normalized_url in self.urls_data:
            # URL already exists (normalized match), add this poster to the list if not already there
            url_entry = self.urls_data[normalized_url]

            # Check if this nick already posted this URL
            existing_posters = [p["nick"] for p in url_entry["posters"]]
            if nick not in existing_posters:
                # Add new poster
                url_entry["posters"].append(
                    {"nick": nick, "timestamp": timestamp, "server": server_name}
                )
                url_entry["count"] += 1

                # Keep posters sorted by timestamp
                url_entry["posters"].sort(key=lambda x: x["timestamp"])

                self._save_urls()

            # Return that it's a duplicate with first seen time
            first_poster = url_entry["posters"][0]
            return True, first_poster["timestamp"]
        else:
            # New URL, create entry with normalized URL as key
            self.urls_data[normalized_url] = {
                "count": 1,
                "posters": [
                    {"nick": nick, "timestamp": timestamp, "server": server_name}
                ],
            }
            self._save_urls()
            return False, None

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for consistent tracking."""
        # Remove trailing slashes
        url = re.sub(r"/$", "", url.strip())

        # Convert to lowercase for case-insensitive matching
        # But preserve the original case for display
        return url

    def get_url_info(self, url: str) -> Optional[Dict]:
        """Get information about a tracked URL (case insensitive, trailing slash ignored)."""
        normalized_url = re.sub(r"/$", "", url.strip()).lower()
        return self.urls_data.get(normalized_url)

    def search_urls(self, query: str, limit: int = 5) -> List[Tuple[str, Dict]]:
        """
        Search for URLs containing the query string.

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            List of (url, info) tuples for matching URLs
        """
        query_lower = query.lower()
        matches = []

        for url, info in self.urls_data.items():
            if query_lower in url.lower():
                matches.append((url, info))

        # Sort by most recent first seen time
        matches.sort(key=lambda x: x[1]["posters"][-1]["timestamp"], reverse=True)

        return matches[:limit]

    def find_closest_match(self, partial_url: str) -> Optional[Tuple[str, Dict]]:
        """
        Find the closest matching URL for a partial URL (case insensitive, trailing slash ignored).

        Args:
            partial_url: Partial URL to search for

        Returns:
            Tuple of (full_url, info) or None if no match found
        """
        # Normalize the search URL (ignore trailing slash, case insensitive)
        normalized_search = re.sub(r"/$", "", partial_url.strip()).lower()

        # First try exact normalized match
        if normalized_search in self.urls_data:
            return (normalized_search, self.urls_data[normalized_search])

        # Since all keys are already lowercase, just check for substring match
        best_match = None
        best_score = 0

        for url, info in self.urls_data.items():
            # Substring match (all URLs are stored in lowercase)
            if normalized_search in url:
                score = len(normalized_search) / len(
                    url
                )  # Ratio of match length to URL length
                if score > best_score:
                    best_score = score
                    best_match = (url, info)

        return best_match

    def get_stats(self) -> Dict:
        """Get statistics about URL tracking."""
        total_urls = len(self.urls_data)
        total_posts = sum(info["count"] for info in self.urls_data.values())

        if self.urls_data:
            # Find most popular URL
            most_popular = max(self.urls_data.items(), key=lambda x: x[1]["count"])

            # Find oldest URL
            oldest = min(
                self.urls_data.items(), key=lambda x: x[1]["posters"][0]["timestamp"]
            )

            return {
                "total_urls": total_urls,
                "total_posts": total_posts,
                "most_popular_url": most_popular[0],
                "most_popular_count": most_popular[1]["count"],
                "oldest_url": oldest[0],
                "oldest_timestamp": oldest[1]["posters"][0]["timestamp"],
            }
        else:
            return {
                "total_urls": 0,
                "total_posts": 0,
                "most_popular_url": None,
                "most_popular_count": 0,
                "oldest_url": None,
                "oldest_timestamp": None,
            }

    def format_duplicate_message(
        self, url: str, first_timestamp: str, first_nick: str
    ) -> str:
        """Format the 'Wanha!' message for duplicate URLs."""
        try:
            # Parse ISO timestamp
            dt = datetime.fromisoformat(first_timestamp.replace("Z", "+00:00"))

            # Format as dd.mm.yy hour:min:sec
            formatted_time = dt.strftime("%d.%m.%y %H:%M:%S")

            return f"Wanha! [{url}] @ {formatted_time} -{first_nick}"
        except Exception as e:
            logger.error(f"Error formatting duplicate message: {e}")
            return f"Wanha! [{url}] -{first_nick}"

    def format_url_info(self, url: str, info: Dict) -> str:
        """Format detailed information about a URL."""
        first_poster = info["posters"][0]
        last_poster = info["posters"][-1]

        first_time = datetime.fromisoformat(
            first_poster["timestamp"].replace("Z", "+00:00")
        )
        last_time = datetime.fromisoformat(
            last_poster["timestamp"].replace("Z", "+00:00")
        )

        formatted_first = first_time.strftime("%d.%m.%y %H:%M:%S")
        formatted_last = last_time.strftime("%d.%m.%y %H:%M:%S")

        posters_list = ", ".join(
            [
                f"{p['nick']}({datetime.fromisoformat(p['timestamp'].replace('Z', '+00:00')).strftime('%d.%m.%y')})"
                for p in info["posters"][:5]
            ]
        )  # Show first 5 posters

        if len(info["posters"]) > 5:
            posters_list += f" ... and {len(info['posters']) - 5} more"

        return f"🔗 {url} | First: {formatted_first} by {first_poster['nick']} | Last: {formatted_last} by {last_poster['nick']} | Total: {info['count']} posts | Posters: {posters_list}"

    def format_search_result(self, url: str, info: Dict) -> str:
        """Format search result showing URL and first seen time."""
        first_poster = info["posters"][0]
        first_time = datetime.fromisoformat(
            first_poster["timestamp"].replace("Z", "+00:00")
        )
        formatted_time = first_time.strftime("%d.%m.%y %H:%M:%S")

        return f"🔗 {url} (first seen: {formatted_time} by {first_poster['nick']})"


def create_url_tracker_service(data_dir: str = "data") -> URLTrackerService:
    """
    Factory function to create a URL tracker service instance.

    Args:
        data_dir: Directory where data files are stored

    Returns:
        URLTrackerService instance
    """
    return URLTrackerService(data_dir)
