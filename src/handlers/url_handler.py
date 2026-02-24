"""
URL Handler Mixin

Provides URL fetching, title extraction, and URL blacklist functionality.
"""

import re
from typing import Any, Dict, Optional


class UrlHandlerMixin:
    """
    Mixin for URL handling functionality.

    Extracts URL titles, handles YouTube/X URLs, and manages URL blacklists.
    """

    # Abstract properties to be defined by the including class
    service_manager = None
    _x_cache = None
    _x_cache_settings = None

    # Blacklisted file extensions and domains (can be overridden)
    BLACKLISTED_EXTENSIONS = frozenset(
        {
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".bmp",
            ".ico",
            ".webp",
            ".mp3",
            ".mp4",
            ".avi",
            ".mkv",
            ".mov",
            ".wav",
            ".flac",
            ".zip",
            ".rar",
            ".7z",
            ".tar",
            ".gz",
            ".pdf",
            ".doc",
            ".docx",
            ".xls",
            ".xlsx",
            ".ppt",
            ".pptx",
            ".exe",
            ".dll",
            ".msi",
            ".deb",
            ".rpm",
            ".appimage",
        }
    )

    BLACKLISTED_DOMAINS = frozenset(
        {
            "localhost",
            "127.0.0.1",
            "0.0.0.0",
        }
    )

    @staticmethod
    def _is_youtube_url(url: str) -> bool:
        """Check if a URL is a YouTube URL."""
        return bool(re.search(r"(?:youtube\.com|youtu\.be|youtube-nocookie\.com)", url))

    @staticmethod
    def _is_x_url(url: str) -> bool:
        """Check if a URL is an X/Twitter URL."""
        return bool(re.search(r"(?:x\.com|twitter\.com)/[\w]+/status", url))

    def _is_url_blacklisted(self, url: str) -> bool:
        """Check if a URL should be blacklisted from title fetching."""
        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            # Check domain blacklist
            if domain in self.BLACKLISTED_DOMAINS:
                return True

            # Check extension blacklist
            path = parsed.path.lower()
            for ext in self.BLACKLISTED_EXTENSIONS:
                if path.endswith(ext):
                    return True

            return False
        except Exception:
            return True  # Blacklist on any parsing error

    def _is_title_banned(self, title: str) -> bool:
        """Check if a title should be banned from being displayed."""
        if not title:
            return True

        title_lower = title.lower()

        # Check for common spam/phishing patterns
        banned_patterns = [
            "bit.ly",
            "tinyurl",
            "click here",
            "buy now",
            "act now",
            "limited time",
            "click below",
        ]

        return any(pattern in title_lower for pattern in banned_patterns)

    def _fetch_title(self, irc, target, text):
        """
        Fetch and display URL titles or X/Twitter post content.

        Excludes blacklisted URLs and file types.
        """
        # This is a proxy to the actual implementation
        # The including class should implement this or delegate to service_manager
        pass

    def _get_cached_x_response(self, url: str) -> Optional[str]:
        """Get cached X response for URL if available."""
        if self._x_cache is None:
            return None
        return self._x_cache.get(url)

    def _cache_x_response(self, url: str, response: str):
        """Cache X response for URL."""
        if self._x_cache is not None:
            self._x_cache[url] = {
                "response": response,
                "timestamp": __import__("time").time(),
            }
            self._manage_x_cache_size(self._x_cache)

    def _manage_x_cache_size(self, x_cache: Dict[str, Dict]):
        """Manage X cache size to prevent it from growing too large."""
        if not x_cache:
            return

        max_cache_size = getattr(self, "_x_cache_settings", {}).get("max_size", 100)

        if len(x_cache) > max_cache_size:
            # Remove oldest entries
            sorted_items = sorted(
                x_cache.items(), key=lambda x: x[1].get("timestamp", 0)
            )
            items_to_remove = len(x_cache) - max_cache_size + 10
            for key, _ in sorted_items[:items_to_remove]:
                del x_cache[key]
