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

# Mock external dependencies at import time to avoid import errors
external_deps = [
    "requests",
    "feedparser",
    "bs4",
    "selenium",
    "youtube_dl",
    "yt_dlp",
    "psutil",
    "matplotlib",
    "openai",
    "websocket",
    "urllib3",
    "certifi",
    "charset_normalizer",
    "idna",
    "lxml",
    "html5lib",
    "pytz",
    "dateutil",
    "cryptography",
    "jwt",
    "aiohttp",
    "asyncio",
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
    "requests.adapters": Mock(),
    "requests.exceptions": Mock(),
    "urllib3.exceptions": Mock(),
    "cryptography.fernet": Mock(),
    "jwt.exceptions": Mock(),
    "googleapiclient.discovery": Mock(),
    "googleapiclient.errors": Mock(),
}

for module_name, mock_obj in submodules.items():
    sys.modules[module_name] = mock_obj

# Load environment variables for testing
load_dotenv()


def test_nanoleet_detector_ultimate():
    """Test ultimate leet detection (perfect 13:37:13.371337133)."""
    from nanoleet_detector import create_nanoleet_detector

    detector = create_nanoleet_detector()

    # Test perfect ultimate leet timestamp
    ultimate_timestamp = "13:37:13.371337133"
    result = detector.detect_leet_patterns(ultimate_timestamp)
    level = detector.determine_achievement_level(result)

    assert level == "ultimate", f"Expected 'ultimate' level, got '{level}'"
    assert result["is_ultimate"], "Result should be marked as ultimate"
    assert result["total_count"] >= 1, "Total count should be at least 1"

    # Test achievement message formatting
    message = detector.format_achievement_message("testuser", ultimate_timestamp, level)
    expected_parts = ["🏆👑", "Ultimate Leet!!", "[testuser]", ultimate_timestamp]

    for part in expected_parts:
        assert part in message, f"Expected '{part}' in message: {message}"


def test_nanoleet_detector_mega():
    """Test mega leet detection (3+ occurrences of 1337)."""
    from nanoleet_detector import create_nanoleet_detector

    detector = create_nanoleet_detector()

    # Test timestamps with 3+ occurrences of 1337
    test_cases = [
        ("13:37:21.133713371", "mega"),  # 3 occurrences
        ("12:34:56.133713371", "super"),  # 2 occurrences, should be super
    ]

    for timestamp, expected_level in test_cases:
        result = detector.detect_leet_patterns(timestamp)
        level = detector.determine_achievement_level(result)

        if timestamp == "13:37:13.371337133":
            # This should be ultimate, not mega
            assert (
                level == "ultimate"
            ), f"Ultimate timestamp should be 'ultimate', got '{level}'"
        elif result["total_count"] >= 3 and expected_level == "mega":
            assert (
                level == "mega"
            ), f"Expected 'mega' level for {timestamp}, got '{level}'"
        elif result["total_count"] == 2 and expected_level == "super":
            assert (
                level == "super"
            ), f"Expected 'super' level for {timestamp}, got '{level}'"


def test_nanoleet_detector_nano():
    """Test nano leet detection (1337 only in nanoseconds)."""
    from nanoleet_detector import create_nanoleet_detector

    detector = create_nanoleet_detector()

    # Test timestamps with 1337 only in nanosecond part
    test_cases = [
        "02:38:12.123451337",  # nano leet at the end
        "14:25:48.133700000",  # 1337 at start of nanoseconds
        "09:15:33.000133700",  # 1337 in middle of nanoseconds
    ]

    for timestamp in test_cases:
        result = detector.detect_leet_patterns(timestamp)
        level = detector.determine_achievement_level(result)

        if result["nano_count"] > 0 and result["time_count"] == 0:
            assert (
                level == "nano"
            ), f"Expected 'nano' level for {timestamp}, got '{level}'"

            # Test message formatting
            message = detector.format_achievement_message("nanouser", timestamp, level)
            assert "🔬⚡" in message, f"Expected nano emoji in message: {message}"
            assert "Nano Leet" in message, f"Expected 'Nano Leet' in message: {message}"


def test_tamagotchi_toggle_functionality():
    """Test tamagotchi toggle functionality with mock environment."""
    # Create temporary .env file for testing
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write("BOT_NAME=TestBot\nTAMAGOTCHI_ENABLED=true\nUSE_NOTICES=false\n")
        env_file = f.name

    try:
        # Mock all dependencies
        with patch("bot_manager.DataManager") as mock_dm:
            with patch("bot_manager.get_api_key", return_value=None):
                with patch("bot_manager.create_crypto_service", return_value=Mock()):
                    with patch(
                        "bot_manager.create_nanoleet_detector", return_value=Mock()
                    ):
                        with patch(
                            "bot_manager.create_fmi_warning_service",
                            return_value=Mock(),
                        ):
                            with patch(
                                "bot_manager.create_otiedote_service",
                                return_value=Mock(),
                            ):
                                with patch(
                                    "bot_manager.Lemmatizer",
                                    side_effect=Exception("Mock error"),
                                ):
                                    from bot_manager import BotManager

                                    # Mock data manager methods
                                    mock_dm.return_value.load_tamagotchi_state.return_value = {
                                        "servers": {}
                                    }
                                    mock_dm.return_value.save_tamagotchi_state.return_value = (
                                        None
                                    )
                                    mock_dm.return_value.load_general_words_data.return_value = {
                                        "servers": {}
                                    }
                                    mock_dm.return_value.save_general_words_data.return_value = (
                                        None
                                    )
                                    mock_dm.return_value.load_drink_data.return_value = {
                                        "servers": {}
                                    }
                                    mock_dm.return_value.save_drink_data.return_value = (
                                        None
                                    )

                                    bot_manager = BotManager("TestBot")

                                    # Test initial state
                                    assert hasattr(
                                        bot_manager, "tamagotchi_enabled"
                                    ), "Bot should have tamagotchi_enabled attribute"
                                    assert hasattr(
                                        bot_manager, "toggle_tamagotchi"
                                    ), "Bot should have toggle_tamagotchi method"

                                    # Mock server and response tracking
                                    mock_server = Mock()
                                    mock_server.config.name = "test_server"

                                    responses = []

                                    def mock_send_response(server, target, message):
                                        responses.append(message)

                                    bot_manager._send_response = mock_send_response

                                    # Test toggle command
                                    original_state = bot_manager.tamagotchi_enabled
                                    bot_manager.toggle_tamagotchi(
                                        mock_server, "#test", "testuser"
                                    )

                                    # Should have changed state
                                    assert (
                                        bot_manager.tamagotchi_enabled != original_state
                                    ), "Tamagotchi state should have changed"
                                    assert (
                                        len(responses) > 0
                                    ), "Should have sent a response"
                                    assert (
                                        "Tamagotchi" in responses[0]
                                    ), "Response should mention Tamagotchi"
    finally:
        # Clean up temp file
        if os.path.exists(env_file):
            os.unlink(env_file)


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


def test_nanoleet_message_for_leet():
    """Test nanoleet message processing for regular leet detection."""
    from nanoleet_detector import create_nanoleet_detector

    detector = create_nanoleet_detector()

    # Test check_message_for_leet function
    test_timestamp = "13:37:42.987654321"  # Regular leet (1337 in time)
    result = detector.check_message_for_leet("testuser", test_timestamp)

    assert result is not None, "Should detect leet in timestamp"

    message, level = result

    assert level == "leet", f"Expected 'leet' level, got '{level}'"
    assert "testuser" in message, "Message should contain username"
    assert "13:37:42.987654321" in message, "Message should contain timestamp"
    assert "🎊✨" in message, "Message should contain leet emoji"


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
