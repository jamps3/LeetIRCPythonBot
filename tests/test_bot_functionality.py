#!/usr/bin/env python3
"""
Bot Functionality Test Suite - Pure Pytest Version

Tests for core bot functionality including nanoleet detection, tamagotchi toggle,
YouTube URL detection, and other integrated features.
"""

import os
import sys
import tempfile
from unittest.mock import MagicMock, Mock, patch

# Add the parent directory to sys.path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

# Mock external dependencies selectively to avoid test interference
external_deps = [
    "bs4",
    "selenium",
    "youtube_dl",
    "yt_dlp",
    "psutil",
    "matplotlib",
    "openai",
    "websocket",
    "idna",
    "lxml",
    "html5lib",
    "pytz",
    "dateutil",
    "cryptography",
    "jwt",
    "aiohttp",
    "websockets",
    "discord",
    "tweepy",
    "praw",
    "pandas",
    "numpy",
    "PIL",
    "cv2",
    "googleapiclient",
    "isodate",
]

# Mock main modules
for dep in external_deps:
    sys.modules[dep] = Mock()

# Mock common submodules
submodules = {
    "selenium.webdriver": Mock(),
    "selenium.webdriver.common": Mock(),
    "selenium.webdriver.chrome": Mock(),
    "selenium.webdriver.firefox": Mock(),
    "selenium.webdriver.chrome.options": Mock(),
    "selenium.webdriver.chrome.service": Mock(),
    "selenium.webdriver.common.by": Mock(),
    "selenium.webdriver.support": Mock(),
    "selenium.webdriver.support.ui": Mock(),
    "selenium.webdriver.support.expected_conditions": Mock(),
    "bs4": Mock(),
    "matplotlib.pyplot": Mock(),
    "PIL.Image": Mock(),
    "cryptography.fernet": Mock(),
    "jwt.exceptions": Mock(),
    "googleapiclient.discovery": Mock(),
    "googleapiclient.errors": Mock(),
}

for module_name, mock_obj in submodules.items():
    sys.modules[module_name] = mock_obj

# Load environment variables for testing
load_dotenv()


def test_youtube_url_detection():
    """Test YouTube URL detection functionality."""
    # Mock all dependencies
    with patch("bot_manager.DataManager"):
        with patch("bot_manager.get_api_key", return_value=None):
            with patch("bot_manager.create_crypto_service", return_value=Mock()):
                with patch("bot_manager.create_nanoleet_detector", return_value=Mock()):
                    with patch(
                        "bot_manager.create_fmi_warning_service", return_value=Mock()
                    ):
                        with patch(
                            "bot_manager.create_otiedote_service", return_value=Mock()
                        ):
                            with patch(
                                "bot_manager.Lemmatizer",
                                side_effect=Exception("Mock error"),
                            ):
                                from bot_manager import BotManager

                                bot_manager = BotManager("TestBot")

                                # Test various YouTube URL formats
                                test_urls = [
                                    # Standard YouTube URLs
                                    (
                                        "https://www.youtube.com/watch?v=5nM6T3KCVfM",
                                        True,
                                    ),
                                    (
                                        "http://www.youtube.com/watch?v=5nM6T3KCVfM",
                                        True,
                                    ),
                                    ("https://youtube.com/watch?v=5nM6T3KCVfM", True),
                                    # Short YouTube URLs
                                    ("https://youtu.be/5nM6T3KCVfM", True),
                                    ("http://youtu.be/5nM6T3KCVfM", True),
                                    # YouTube Shorts URLs
                                    (
                                        "https://www.youtube.com/shorts/5nM6T3KCVfM",
                                        True,
                                    ),
                                    # Mobile YouTube URLs
                                    ("https://m.youtube.com/watch?v=5nM6T3KCVfM", True),
                                    # YouTube Music URLs
                                    (
                                        "https://music.youtube.com/watch?v=5nM6T3KCVfM",
                                        True,
                                    ),
                                    # Embed URLs
                                    ("https://www.youtube.com/embed/5nM6T3KCVfM", True),
                                    ("https://www.youtube.com/v/5nM6T3KCVfM", True),
                                    # Non-YouTube URLs (should return False)
                                    ("https://www.google.com", False),
                                    ("https://example.com/watch?v=notYouTube", False),
                                    ("https://vimeo.com/123456", False),
                                    ("https://twitch.tv/streamername", False),
                                    ("", False),
                                    ("not a url at all", False),
                                ]

                                for url, should_be_youtube in test_urls:
                                    result = bot_manager._is_youtube_url(url)
                                    assert (
                                        result == should_be_youtube
                                    ), f"Failed for URL: {url}, expected {should_be_youtube}, got {result}"


def test_url_blacklist_functionality():
    """Test URL blacklisting for title fetching."""
    # Mock all dependencies
    with patch("bot_manager.DataManager"):
        with patch("bot_manager.get_api_key", return_value=None):
            with patch("bot_manager.create_crypto_service", return_value=Mock()):
                with patch("bot_manager.create_nanoleet_detector", return_value=Mock()):
                    with patch(
                        "bot_manager.create_fmi_warning_service", return_value=Mock()
                    ):
                        with patch(
                            "bot_manager.create_otiedote_service", return_value=Mock()
                        ):
                            with patch(
                                "bot_manager.Lemmatizer",
                                side_effect=Exception("Mock error"),
                            ):
                                from bot_manager import BotManager

                                bot_manager = BotManager("TestBot")

                                # Test blacklisted URLs
                                blacklisted_urls = [
                                    "https://www.youtube.com/watch?v=5nM6T3KCVfM",
                                    "https://facebook.com/somepost",
                                    "https://x.com/sometweet",
                                    "https://example.com/photo.jpg",
                                    "https://example.com/document.pdf",
                                ]

                                for url in blacklisted_urls:
                                    result = bot_manager._is_url_blacklisted(url)
                                    assert (
                                        result
                                    ), f"URL should be blacklisted but wasn't: {url}"

                                # Test allowed URLs
                                allowed_urls = [
                                    "https://example.com",
                                    "https://news.example.com/article",
                                    "https://github.com/user/repo",
                                ]

                                for url in allowed_urls:
                                    result = bot_manager._is_url_blacklisted(url)
                                    assert (
                                        not result
                                    ), f"URL should be allowed but was blacklisted: {url}"


def test_bot_manager_initialization_with_services():
    """Test that BotManager initializes properly with all services."""
    # Mock all dependencies but ensure they return proper values
    with patch("bot_manager.DataManager") as mock_dm:
        with patch("bot_manager.get_api_key") as mock_api:
            with patch("bot_manager.create_crypto_service") as mock_crypto:
                with patch("bot_manager.create_nanoleet_detector") as mock_nano:
                    with patch("bot_manager.create_fmi_warning_service") as mock_fmi:
                        with patch(
                            "bot_manager.create_otiedote_service"
                        ) as mock_otiedote:
                            with patch("bot_manager.Lemmatizer") as mock_lemma:
                                # Set up proper mock returns
                                mock_api.return_value = "fake_key"
                                mock_crypto.return_value = Mock()
                                mock_nano.return_value = Mock()
                                mock_fmi.return_value = Mock()
                                mock_otiedote.return_value = Mock()
                                mock_lemma.return_value = Mock()

                                # Mock data manager
                                mock_dm_instance = Mock()
                                mock_dm.return_value = mock_dm_instance
                                mock_dm_instance.load_tamagotchi_state.return_value = {
                                    "servers": {}
                                }
                                mock_dm_instance.save_tamagotchi_state.return_value = (
                                    None
                                )
                                mock_dm_instance.load_general_words_data.return_value = {
                                    "servers": {}
                                }
                                mock_dm_instance.save_general_words_data.return_value = (
                                    None
                                )
                                mock_dm_instance.load_drink_data.return_value = {
                                    "servers": {}
                                }
                                mock_dm_instance.save_drink_data.return_value = None

                                from bot_manager import BotManager

                                bot_manager = BotManager("TestBot")

                                # Check that essential attributes exist
                                required_attrs = [
                                    "bot_name",
                                    "servers",
                                    "stop_event",
                                    "data_manager",
                                    "drink_tracker",
                                    "general_words",
                                    "tamagotchi",
                                    "crypto_service",
                                    "nanoleet_detector",
                                ]

                                for attr in required_attrs:
                                    assert hasattr(
                                        bot_manager, attr
                                    ), f"Missing required attribute: {attr}"

                                # Check that essential methods exist
                                required_methods = [
                                    "_handle_message",
                                    "_track_words",
                                    "_process_commands",
                                    "start",
                                    "stop",
                                    "wait_for_shutdown",
                                    "_listen_for_console_commands",
                                    "_create_console_bot_functions",
                                ]

                                for method in required_methods:
                                    assert hasattr(
                                        bot_manager, method
                                    ), f"Missing required method: {method}"
                                    assert callable(
                                        getattr(bot_manager, method)
                                    ), f"Attribute {method} is not callable"
