"""
Utility functions for the IRC bot.

This module contains shared utility functions that are used across multiple command modules.
"""

import html
import os
import re

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from googleapiclient.discovery import build

from logger import get_logger

# Load environment variables
load_dotenv()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# Initialize YouTube API client
youtube = (
    build("youtube", "v3", developerKey=YOUTUBE_API_KEY) if YOUTUBE_API_KEY else None
)

# Initialize logger
_logger = get_logger("Utils")


def verify_admin_password(command_text):
    """Check if command contains correct admin password."""
    parts = command_text.split()
    if len(parts) >= 2 and parts[1] == ADMIN_PASSWORD:
        return True
    return False


def send_raw_irc_command(irc, command, log_func):
    """Send a raw IRC command to the server."""
    try:
        irc.sendall(f"{command}\r\n".encode("utf-8"))
        log_func(f"Sent raw IRC command: {command}", "INFO")
        return True
    except Exception as e:
        log_func(f"Error sending raw IRC command: {e}", "ERROR")
        return False


def fetch_title_improved(
    irc, channel, url, last_title_ref, send_message_func, log_func
):
    """
    Improved version of fetch_title from message_handlers.py with better YouTube handling
    and encoding detection.
    """
    # Skip URLs that are unlikely to have meaningful titles
    if any(
        skip_url in url.lower()
        for skip_url in [".jpg", ".jpeg", ".png", ".gif", ".mp4", ".webm"]
    ):
        log_func(f"Skipping image/video URL: {url}", "DEBUG")
        return

    try:
        log_func(f"Fetching title for URL: {url}", "DEBUG")

        # Special handling for YouTube URLs to get more information
        youtube_pattern = re.compile(
            r"(?:https?:\/\/)?(?:www\.)?(?:youtube\.com|youtu\.be)\/(?:watch\?v=|shorts\/|embed\/)?([a-zA-Z0-9_-]{11})"
        )
        youtube_match = youtube_pattern.search(url)

        if youtube_match and youtube:
            video_id = youtube_match.group(1)
            _logger.debug(f"YouTube video detected, ID: {video_id}")

            try:
                # Use YouTube API to get detailed information
                video_response = (
                    youtube.videos()
                    .list(part="snippet,contentDetails,statistics", id=video_id)
                    .execute()
                )

                if video_response.get("items"):
                    video = video_response["items"][0]
                    snippet = video["snippet"]
                    statistics = video["statistics"]

                    title = snippet["title"]
                    channel_name = snippet["channelTitle"]
                    view_count = int(statistics.get("viewCount", 0))
                    like_count = int(statistics.get("likeCount", 0))

                    # Format view count with commas
                    view_count_str = f"{view_count:,}".replace(",", " ")
                    like_count_str = f"{like_count:,}".replace(",", " ")

                    # Create formatted message
                    youtube_info = f'YouTube: "{title}" by {channel_name} | Views: {view_count_str} | Likes: {like_count_str}'

                    if youtube_info != last_title_ref[0]:
                        send_message_func(irc, channel, youtube_info)
                        last_title_ref[0] = youtube_info
                    return
            except Exception as e:
                _logger.warning(f"Error fetching YouTube video info: {str(e)}")
                # Fall back to regular title extraction if YouTube API fails

        # Regular title extraction for all other URLs
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
        }

        # Use a timeout to prevent hanging
        response = requests.get(url, headers=headers, timeout=10, stream=True)

        # Check content type before downloading everything
        content_type = response.headers.get("Content-Type", "").lower()
        log_func(f"Content type: {content_type}", "DEBUG")

        # Skip binary files and large content
        if (
            "text/html" not in content_type
            and "application/xhtml+xml" not in content_type
        ):
            log_func(f"Skipping non-HTML content: {content_type}", "DEBUG")
            return

        # Limit content size to prevent memory issues (100 KB should be enough for most titles)
        content_bytes = b""
        for chunk in response.iter_content(chunk_size=4096):
            content_bytes += chunk
            if len(content_bytes) > 102400:  # 100 KB
                break

        # Try to determine the encoding
        encoding = response.encoding

        # If the encoding is None or ISO-8859-1 (often default), try to detect it
        if not encoding or encoding.lower() == "iso-8859-1":
            # Check for charset in meta tags
            charset_match = re.search(
                rb'<meta[^>]*charset=["\'']?([\\w-]+)', content_bytes, re.IGNORECASE
            )
            if charset_match:
                encoding = charset_match.group(1).decode("ascii", errors="ignore")
                log_func(f"Found encoding in meta tag: {encoding}", "DEBUG")

        # Default to UTF-8 if detection failed
        if not encoding or encoding.lower() == "iso-8859-1":
            encoding = "utf-8"

        # Decode content with the detected encoding
        try:
            content = content_bytes.decode(encoding, errors="replace")
        except (UnicodeDecodeError, LookupError):
            log_func(
                f"Decoding failed with {encoding}, falling back to utf-8", "WARNING"
            )
            content = content_bytes.decode("utf-8", errors="replace")

        # Use BeautifulSoup to extract the title
        soup = BeautifulSoup(content, "html.parser")
        title_tag = soup.find("title")

        if title_tag and title_tag.string:
            title = title_tag.string.strip()

            # Clean the title by removing excessive whitespace
            title = re.sub(r"\s+", " ", title)

            # HTML unescape to handle entities like &amp;
            title = html.unescape(title)

            # Prepend "Title:" to distinguish from regular messages
            formatted_title = f"Title: {title}"

            # Only send if the title is different from the last one to avoid spam
            if formatted_title != last_title_ref[0]:
                send_message_func(irc, channel, formatted_title)
                last_title_ref[0] = formatted_title
                _logger.debug(f"Sent title: {title}")
        else:
            _logger.debug(f"No title found for URL: {url}")

    except requests.exceptions.Timeout:
        _logger.warning(f"Timeout while fetching URL: {url}")
    except requests.exceptions.TooManyRedirects:
        _logger.warning(f"Too many redirects for URL: {url}")
    except requests.exceptions.RequestException as e:
        _logger.warning(f"Request error for URL {url}: {str(e)}")
    except Exception as e:
        _logger.error(f"Error fetching title for {url}: {str(e)}")
        # More detailed error logging for debugging
        import traceback

        _logger.error(traceback.format_exc())


def split_message_intelligently(message, limit):
    """
    Splits a message into parts without cutting words, ensuring correct byte-size limits.

    Args:
        message (str): The full message to split.
        limit (int): Max length per message.

    Returns:
        list: List of message parts that fit within the limit.
    """
    words = message.split(" ")
    parts = []
    current_part = ""

    for word in words:
        # Calculate encoded byte size
        encoded_size = (
            len((current_part + " " + word).encode("utf-8"))
            if current_part
            else len(word.encode("utf-8"))
        )

        if encoded_size > limit:
            if current_part:  # Store the current part before starting a new one
                parts.append(current_part)
            current_part = word  # Start new part with the long word
        else:
            current_part += (" " + word) if current_part else word

    if current_part:
        parts.append(current_part)

    return parts
