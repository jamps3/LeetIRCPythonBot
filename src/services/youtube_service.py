"""
YouTube Service Module

Provides YouTube video information and search functionality using YouTube Data API v3.
"""

import random
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import isodate
import requests


class YouTubeService:
    """Service for fetching YouTube video information and search."""

    def __init__(self, api_key: str):
        """
        Initialize YouTube service.

        Args:
            api_key: YouTube Data API v3 key
        """
        self.api_key = api_key
        self.base_url = "https://www.googleapis.com/youtube/v3"

        # YouTube URL patterns
        self.youtube_patterns = [
            r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
            r"(?:https?://)?(?:www\.)?youtu\.be/([a-zA-Z0-9_-]{11})",
            r"(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})",
            r"(?:https?://)?(?:www\.)?youtube\.com/v/([a-zA-Z0-9_-]{11})",
        ]

    def extract_video_id(self, text: str) -> Optional[str]:
        """
        Extract YouTube video ID from text containing YouTube URLs.

        Args:
            text: Text that may contain YouTube URLs

        Returns:
            Video ID if found, None otherwise
        """
        for pattern in self.youtube_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return None

    def get_video_info(self, video_id: str) -> Dict[str, Any]:
        """
        Get video information by video ID.

        Args:
            video_id: YouTube video ID

        Returns:
            Dictionary containing video information or error details
        """
        try:
            url = f"{self.base_url}/videos"
            params = {
                "part": "snippet,statistics,contentDetails",
                "id": video_id,
                "key": self.api_key,
            }

            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                return self._parse_video_data(data, video_id)
            else:
                return {
                    "error": True,
                    "message": f"YouTube API returned status code {response.status_code}",
                    "status_code": response.status_code,
                }

        except requests.exceptions.Timeout:
            return {
                "error": True,
                "message": "YouTube API request timed out",
                "exception": "timeout",
            }
        except requests.exceptions.RequestException as e:
            return {
                "error": True,
                "message": f"YouTube API request failed: {str(e)}",
                "exception": str(e),
            }
        except Exception as e:
            return {
                "error": True,
                "message": f"Unexpected error: {str(e)}",
                "exception": str(e),
            }

    def _parse_video_data(self, data: Dict[str, Any], video_id: str) -> Dict[str, Any]:
        """
        Parse video data from API response.

        Args:
            data: Raw video data from API
            video_id: YouTube video ID

        Returns:
            Parsed video information
        """
        try:
            if not data.get("items"):
                return {
                    "error": True,
                    "message": f"Video not found or private: {video_id}",
                }

            video = data["items"][0]
            snippet = video.get("snippet", {})
            statistics = video.get("statistics", {})
            content_details = video.get("contentDetails", {})

            # Parse duration using a robust helper that doesn't rely solely on isodate
            duration_iso = content_details.get("duration", "PT0S")
            duration_seconds = self._parse_iso8601_duration_seconds(duration_iso)
            if duration_seconds is not None:
                duration_str = self._format_duration(
                    timedelta(seconds=duration_seconds)
                )
            else:
                duration_str = "Unknown"

            # Parse upload date
            published_at = snippet.get("publishedAt")
            upload_date = None
            if published_at:
                try:
                    upload_date = datetime.fromisoformat(
                        published_at.replace("Z", "+00:00")
                    )
                except Exception:
                    upload_date = None

            return {
                "error": False,
                "video_id": video_id,
                "title": snippet.get("title", "No title"),
                "channel": snippet.get("channelTitle", "Unknown channel"),
                "duration": duration_str,
                "view_count": int(statistics.get("viewCount", 0)),
                "like_count": int(statistics.get("likeCount", 0)),
                "comment_count": int(statistics.get("commentCount", 0)),
                "upload_date": upload_date,
                "description": snippet.get("description", ""),
                "tags": snippet.get("tags", []),
                "url": f"https://www.youtube.com/watch?v={video_id}",
            }

        except Exception as e:
            return {
                "error": True,
                "message": f"Error parsing video data: {str(e)}",
                "exception": str(e),
            }

    def search_videos(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """
        Search for YouTube videos.

        Args:
            query: Search query
            max_results: Maximum number of results to return (default: 5)

        Returns:
            Dictionary containing search results or error details
        """
        try:
            url = f"{self.base_url}/search"
            params = {
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": min(max_results, 10),  # Limit to 10 max
                "order": "relevance",
                "key": self.api_key,
            }

            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                return self._parse_search_results(data, query)
            else:
                return {
                    "error": True,
                    "message": f"YouTube search API returned status code {response.status_code}",
                    "status_code": response.status_code,
                }

        except requests.exceptions.Timeout:
            return {
                "error": True,
                "message": "YouTube search API request timed out",
                "exception": "timeout",
            }
        except requests.exceptions.RequestException as e:
            return {
                "error": True,
                "message": f"YouTube search API request failed: {str(e)}",
                "exception": str(e),
            }
        except Exception as e:
            return {
                "error": True,
                "message": f"Error searching YouTube: {str(e)}",
                "exception": str(e),
            }

    def _parse_search_results(self, data: Dict[str, Any], query: str) -> Dict[str, Any]:
        """
        Parse search results from API response.

        Args:
            data: Raw search data from API
            query: Original search query

        Returns:
            Parsed search results
        """
        try:
            items = data.get("items", [])

            results = []
            for item in items:
                snippet = item.get("snippet", {})
                video_id = item.get("id", {}).get("videoId")

                if video_id:
                    # Parse upload date
                    published_at = snippet.get("publishedAt")
                    upload_date = None
                    if published_at:
                        try:
                            upload_date = datetime.fromisoformat(
                                published_at.replace("Z", "+00:00")
                            )
                        except Exception:
                            upload_date = None

                    results.append(
                        {
                            "video_id": video_id,
                            "title": snippet.get("title", "No title"),
                            "channel": snippet.get("channelTitle", "Unknown channel"),
                            "description": snippet.get("description", ""),
                            "upload_date": upload_date,
                            "url": f"https://www.youtube.com/watch?v={video_id}",
                        }
                    )

            return {
                "error": False,
                "query": query,
                "results": results,
                "total_results": len(results),
            }

        except Exception as e:
            return {
                "error": True,
                "message": f"Error parsing search results: {str(e)}",
                "exception": str(e),
            }

    def _format_duration(self, duration: timedelta) -> str:
        """
        Format duration (timedelta or isodate Duration) to readable string.

        Args:
            duration: Duration as timedelta or isodate.duration.Duration

        Returns:
            Formatted duration string (e.g., "3:45", "1:23:45")
        """
        # Try the straightforward path first (datetime.timedelta)
        total_seconds_val: Optional[int] = None
        try:
            # duration may be datetime.timedelta
            total_seconds_val = int(duration.total_seconds())  # type: ignore[attr-defined]
        except Exception:
            # Fall back for isodate.duration.Duration which may not have total_seconds
            try:
                days = int(getattr(duration, "days", 0) or 0)  # type: ignore[assignment]
                hours = int(getattr(duration, "hours", 0) or 0)
                minutes = int(getattr(duration, "minutes", 0) or 0)
                seconds_val = getattr(duration, "seconds", 0) or 0
                try:
                    seconds_int = int(seconds_val)
                except Exception:
                    # In case seconds is Decimal/float-like
                    seconds_int = int(float(seconds_val))
                total_seconds_val = (
                    days * 86400 + hours * 3600 + minutes * 60 + seconds_int
                )
            except Exception:
                # If everything fails, return Unknown
                return "Unknown"

        hours = total_seconds_val // 3600
        minutes = (total_seconds_val % 3600) // 60
        seconds = total_seconds_val % 60

        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}"

    def _parse_iso8601_duration_seconds(self, duration_iso: str) -> Optional[int]:
        """
        Parse an ISO 8601 duration string (as returned by YouTube API) to total seconds.
        Tries a lightweight regex first; falls back to isodate if needed.
        Returns None if parsing fails.
        """
        try:
            if not isinstance(duration_iso, str):
                return None

            # Quick path: handle common YouTube patterns: PnW nD T nH nM nS
            m = re.fullmatch(
                r"^P(?:(?P<w>\d+)W)?(?:(?P<d>\d+)D)?(?:T(?:(?P<h>\d+)H)?(?:(?P<m>\d+)M)?(?:(?P<s>\d+)S)?)?$",
                duration_iso,
            )
            if m:
                weeks = int(m.group("w") or 0)
                days = int(m.group("d") or 0)
                hours = int(m.group("h") or 0)
                minutes = int(m.group("m") or 0)
                seconds = int(m.group("s") or 0)
                return (
                    weeks * 7 * 86400
                    + days * 86400
                    + hours * 3600
                    + minutes * 60
                    + seconds
                )

            # Fallback: use isodate to parse, then convert to seconds
            try:
                dur = isodate.parse_duration(duration_iso)
            except Exception:
                return None

            # Try timedelta path first
            try:
                return int(dur.total_seconds())  # type: ignore[attr-defined]
            except Exception:
                pass

            # Fallback for isodate.duration.Duration
            try:
                days = int(getattr(dur, "days", 0) or 0)
                hours = int(getattr(dur, "hours", 0) or 0)
                minutes = int(getattr(dur, "minutes", 0) or 0)
                seconds_val = getattr(dur, "seconds", 0) or 0
                try:
                    seconds_int = int(seconds_val)
                except Exception:
                    seconds_int = int(float(seconds_val))
                return days * 86400 + hours * 3600 + minutes * 60 + seconds_int
            except Exception:
                return None
        except Exception:
            return None

    def format_video_info_message(self, video_data: Dict[str, Any]) -> str:
        """
        Format video information into IRC message with colored ▶ symbol.

        Args:
            video_data: Video data dictionary

        Returns:
            Formatted video info message string
        """
        if video_data.get("error"):
            return f"🎥 YouTube error: {video_data.get('message', 'Unknown error')}"

        title = video_data["title"]
        duration = video_data["duration"]
        views = video_data["view_count"]
        likes = video_data["like_count"]
        upload_date = video_data["upload_date"]
        url = video_data["url"]

        # Format view count
        if views >= 1000000:
            view_str = f"{views/1000000:.1f}M"
        elif views >= 1000:
            view_str = f"{views/1000:.1f}k"
        else:
            view_str = str(views)

        # Format like count
        if likes >= 1000000:
            like_str = f"{likes/1000000:.1f}M"
        elif likes >= 1000:
            like_str = f"{likes/1000:.1f}k"
        else:
            like_str = str(likes)

        # Format upload date
        if upload_date:
            date_str = upload_date.strftime("%d.%m.%Y")
        else:
            date_str = "Unknown"

        # IRC-formatted YouTube logo
        yt_logo = random.choice(
            [
                # "\x02\x0314,15You\x0315,04Tube\x03\x02",  # YouTube
                "\x0300,04 ▶ \x03",  # _▶_
            ]
        )
        # Use IRC color codes: \x0304 = red, \x03 = reset
        # Format: ▶ 'Title' [duration] / Views: xx | xx 👍 / Added: date / url
        message = f"{yt_logo} '{title}' [{duration}] / {view_str}|{like_str}👍 / Added: {date_str} / {url}"

        return message

    def format_search_results_message(self, search_data: Dict[str, Any]) -> str:
        """
        Format search results into IRC message.

        Args:
            search_data: Search results dictionary

        Returns:
            Formatted search results message string
        """
        if search_data.get("error"):
            return f"🎥 YouTube search error: {search_data.get('message', 'Unknown error')}"

        results = search_data.get("results", [])
        if not results:
            return f"🎥 No YouTube videos found for '{search_data.get('query', 'unknown query')}'"

        query = search_data.get("query", "unknown")

        # Format top results
        result_lines = []
        for i, result in enumerate(results[:3], 1):  # Show top 3 results
            title = result["title"][:50] + ("..." if len(result["title"]) > 50 else "")
            channel = result["channel"]
            url = result["url"]
            result_lines.append(f"{i}. '{title}' by {channel} - {url}")

        if len(results) > 3:
            result_lines.append(f"... and {len(results) - 3} more results")

        header = f"🎥 YouTube search results for '{query}':"
        return header + "\n" + "\n".join(result_lines)


def create_youtube_service(api_key: str) -> YouTubeService:
    """
    Factory function to create a YouTube service instance.

    Args:
        api_key: YouTube Data API v3 key

    Returns:
        YouTubeService instance
    """
    return YouTubeService(api_key)
