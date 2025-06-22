#!/usr/bin/env python3
"""
Bot Functionality Test Suite

Tests for core bot functionality including nanoleet detection, tamagotchi toggle,
YouTube URL detection, and other integrated features.
"""

import os
import sys
import tempfile
from unittest.mock import MagicMock, Mock, patch

# Add the parent directory to sys.path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_framework import TestCase, TestSuite
from dotenv import load_dotenv

# Load environment variables for testing
load_dotenv()


def test_nanoleet_detector_ultimate():
    """Test ultimate leet detection (perfect 13:37:13.371337133)."""
    try:
        from nanoleet_detector import create_nanoleet_detector
        
        detector = create_nanoleet_detector()
        
        # Test perfect ultimate leet timestamp
        ultimate_timestamp = "13:37:13.371337133"
        result = detector.detect_leet_patterns(ultimate_timestamp)
        level = detector.determine_achievement_level(result)
        
        if level != "ultimate":
            return False
            
        if not result["is_ultimate"]:
            return False
            
        if result["total_count"] < 1:
            return False
        
        # Test achievement message formatting
        message = detector.format_achievement_message("testuser", ultimate_timestamp, level)
        expected_parts = ["🏆👑", "Ultimate Leet!!", "[testuser]", ultimate_timestamp]
        
        for part in expected_parts:
            if part not in message:
                return False
        
        return True
        
    except Exception as e:
        print(f"Nanoleet detector ultimate test failed: {e}")
        return False


def test_nanoleet_detector_mega():
    """Test mega leet detection (3+ occurrences of 1337)."""
    try:
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
                if level != "ultimate":
                    return False
            elif result["total_count"] >= 3 and expected_level == "mega":
                if level != "mega":
                    return False
            elif result["total_count"] == 2 and expected_level == "super":
                if level != "super":
                    return False
        
        return True
        
    except Exception as e:
        print(f"Nanoleet detector mega test failed: {e}")
        return False


def test_nanoleet_detector_nano():
    """Test nano leet detection (1337 only in nanoseconds)."""
    try:
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
                if level != "nano":
                    return False
                    
                # Test message formatting
                message = detector.format_achievement_message("nanouser", timestamp, level)
                if "🔬⚡" not in message or "Nano Leet" not in message:
                    return False
        
        return True
        
    except Exception as e:
        print(f"Nanoleet detector nano test failed: {e}")
        return False


def test_tamagotchi_toggle_functionality():
    """Test tamagotchi toggle functionality with mock environment."""
    try:
        # Create temporary .env file for testing
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("BOT_NAME=TestBot\nTAMAGOTCHI_ENABLED=true\nUSE_NOTICES=false\n")
            env_file = f.name
        
        try:
            # Mock all dependencies
            with patch('bot_manager.DataManager') as mock_dm:
                with patch('bot_manager.get_api_key', return_value=None):
                    with patch('bot_manager.create_crypto_service', return_value=Mock()):
                        with patch('bot_manager.create_nanoleet_detector', return_value=Mock()):
                            with patch('bot_manager.create_fmi_warning_service', return_value=Mock()):
                                with patch('bot_manager.create_otiedote_service', return_value=Mock()):
                                    with patch('bot_manager.Lemmatizer', side_effect=Exception("Mock error")):
                                        from bot_manager import BotManager
                                        
                                        # Mock data manager methods
                                        mock_dm.return_value.load_tamagotchi_state.return_value = {"servers": {}}
                                        mock_dm.return_value.save_tamagotchi_state.return_value = None
                                        mock_dm.return_value.load_general_words_data.return_value = {"servers": {}}
                                        mock_dm.return_value.save_general_words_data.return_value = None
                                        mock_dm.return_value.load_drink_data.return_value = {"servers": {}}
                                        mock_dm.return_value.save_drink_data.return_value = None
                                        
                                        bot_manager = BotManager("TestBot")
                                        
                                        # Test initial state
                                        if not hasattr(bot_manager, 'tamagotchi_enabled'):
                                            return False
                                        
                                        # Test toggle functionality exists
                                        if not hasattr(bot_manager, 'toggle_tamagotchi'):
                                            return False
                                        
                                        # Mock server and response tracking
                                        mock_server = Mock()
                                        mock_server.config.name = "test_server"
                                        
                                        responses = []
                                        def mock_send_response(server, target, message):
                                            responses.append(message)
                                        
                                        bot_manager._send_response = mock_send_response
                                        
                                        # Test toggle command
                                        original_state = bot_manager.tamagotchi_enabled
                                        result = bot_manager.toggle_tamagotchi(mock_server, "#test", "testuser")
                                        
                                        # Should have changed state
                                        if bot_manager.tamagotchi_enabled == original_state:
                                            return False
                                        
                                        # Should have sent a response
                                        if not responses:
                                            return False
                                        
                                        if "Tamagotchi" not in responses[0]:
                                            return False
                                        
                                        return True
        finally:
            # Clean up temp file
            if os.path.exists(env_file):
                os.unlink(env_file)
        
    except Exception as e:
        print(f"Tamagotchi toggle test failed: {e}")
        return False


def test_youtube_url_detection():
    """Test YouTube URL detection functionality."""
    try:
        # Mock all dependencies
        with patch('bot_manager.DataManager'):
            with patch('bot_manager.get_api_key', return_value=None):
                with patch('bot_manager.create_crypto_service', return_value=Mock()):
                    with patch('bot_manager.create_nanoleet_detector', return_value=Mock()):
                        with patch('bot_manager.create_fmi_warning_service', return_value=Mock()):
                            with patch('bot_manager.create_otiedote_service', return_value=Mock()):
                                with patch('bot_manager.Lemmatizer', side_effect=Exception("Mock error")):
                                    from bot_manager import BotManager
                                    
                                    bot_manager = BotManager("TestBot")
                                    
                                    # Test various YouTube URL formats
                                    test_urls = [
                                        # Standard YouTube URLs
                                        ("https://www.youtube.com/watch?v=5nM6T3KCVfM", True),
                                        ("http://www.youtube.com/watch?v=5nM6T3KCVfM", True),
                                        ("https://youtube.com/watch?v=5nM6T3KCVfM", True),
                                        
                                        # Short YouTube URLs
                                        ("https://youtu.be/5nM6T3KCVfM", True),
                                        ("http://youtu.be/5nM6T3KCVfM", True),
                                        
                                        # YouTube Shorts URLs (new feature)
                                        ("https://www.youtube.com/shorts/5nM6T3KCVfM", True),
                                        
                                        # Mobile YouTube URLs
                                        ("https://m.youtube.com/watch?v=5nM6T3KCVfM", True),
                                        
                                        # YouTube Music URLs
                                        ("https://music.youtube.com/watch?v=5nM6T3KCVfM", True),
                                        
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
                                        if result != should_be_youtube:
                                            print(f"Failed for URL: {url}, expected {should_be_youtube}, got {result}")
                                            return False
                                    
                                    return True
        
    except Exception as e:
        print(f"YouTube URL detection test failed: {e}")
        return False


def test_url_blacklist_functionality():
    """Test URL blacklisting for title fetching."""
    try:
        # Mock all dependencies
        with patch('bot_manager.DataManager'):
            with patch('bot_manager.get_api_key', return_value=None):
                with patch('bot_manager.create_crypto_service', return_value=Mock()):
                    with patch('bot_manager.create_nanoleet_detector', return_value=Mock()):
                        with patch('bot_manager.create_fmi_warning_service', return_value=Mock()):
                            with patch('bot_manager.create_otiedote_service', return_value=Mock()):
                                with patch('bot_manager.Lemmatizer', side_effect=Exception("Mock error")):
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
                                        if not result:
                                            print(f"URL should be blacklisted but wasn't: {url}")
                                            return False
                                    
                                    # Test allowed URLs
                                    allowed_urls = [
                                        "https://example.com",
                                        "https://news.example.com/article",
                                        "https://github.com/user/repo",
                                    ]
                                    
                                    for url in allowed_urls:
                                        result = bot_manager._is_url_blacklisted(url)
                                        if result:
                                            print(f"URL should be allowed but was blacklisted: {url}")
                                            return False
                                    
                                    return True
        
    except Exception as e:
        print(f"URL blacklist test failed: {e}")
        return False


def test_nanoleet_message_for_leet():
    """Test nanoleet message processing for regular leet detection."""
    try:
        from nanoleet_detector import create_nanoleet_detector
        
        detector = create_nanoleet_detector()
        
        # Test check_message_for_leet function
        test_timestamp = "13:37:42.987654321"  # Regular leet (1337 in time)
        result = detector.check_message_for_leet("testuser", test_timestamp)
        
        if not result:
            return False
            
        message, level = result
        
        if level != "leet":
            return False
            
        if "testuser" not in message:
            return False
            
        if "13:37:42.987654321" not in message:
            return False
            
        if "🎊✨" not in message:
            return False
        
        return True
        
    except Exception as e:
        print(f"Nanoleet message for leet test failed: {e}")
        return False


def test_bot_manager_initialization_with_services():
    """Test that BotManager initializes properly with all services."""
    try:
        # Mock all dependencies but ensure they return proper values
        with patch('bot_manager.DataManager') as mock_dm:
            with patch('bot_manager.get_api_key') as mock_api:
                with patch('bot_manager.create_crypto_service') as mock_crypto:
                    with patch('bot_manager.create_nanoleet_detector') as mock_nano:
                        with patch('bot_manager.create_fmi_warning_service') as mock_fmi:
                            with patch('bot_manager.create_otiedote_service') as mock_otiedote:
                                with patch('bot_manager.Lemmatizer') as mock_lemma:
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
                                    mock_dm_instance.load_tamagotchi_state.return_value = {"servers": {}}
                                    mock_dm_instance.save_tamagotchi_state.return_value = None
                                    mock_dm_instance.load_general_words_data.return_value = {"servers": {}}
                                    mock_dm_instance.save_general_words_data.return_value = None
                                    mock_dm_instance.load_drink_data.return_value = {"servers": {}}
                                    mock_dm_instance.save_drink_data.return_value = None
                                    
                                    from bot_manager import BotManager
                                    
                                    bot_manager = BotManager("TestBot")
                                    
                                    # Check that essential attributes exist
                                    required_attrs = [
                                        'bot_name', 'servers', 'stop_event',
                                        'data_manager', 'drink_tracker', 'general_words',
                                        'tamagotchi', 'crypto_service', 'nanoleet_detector'
                                    ]
                                    
                                    for attr in required_attrs:
                                        if not hasattr(bot_manager, attr):
                                            print(f"Missing required attribute: {attr}")
                                            return False
                                    
                                    # Check that essential methods exist
                                    required_methods = [
                                        '_handle_message', '_track_words', '_process_commands',
                                        'start', 'stop', 'wait_for_shutdown',
                                        '_listen_for_console_commands', '_create_console_bot_functions'
                                    ]
                                    
                                    for method in required_methods:
                                        if not hasattr(bot_manager, method):
                                            print(f"Missing required method: {method}")
                                            return False
                                        if not callable(getattr(bot_manager, method)):
                                            print(f"Attribute {method} is not callable")
                                            return False
                                    
                                    return True
        
    except Exception as e:
        print(f"Bot manager initialization test failed: {e}")
        return False


def register_bot_functionality_tests(runner):
    """Register bot functionality tests with the test framework."""
    tests = [
        TestCase(
            name="nanoleet_detector_ultimate",
            description="Test ultimate leet detection (perfect 13:37:13.371337133)",
            test_func=test_nanoleet_detector_ultimate,
            category="bot_functionality",
        ),
        TestCase(
            name="nanoleet_detector_mega",
            description="Test mega leet detection (3+ occurrences of 1337)",
            test_func=test_nanoleet_detector_mega,
            category="bot_functionality",
        ),
        TestCase(
            name="nanoleet_detector_nano",
            description="Test nano leet detection (1337 only in nanoseconds)",
            test_func=test_nanoleet_detector_nano,
            category="bot_functionality",
        ),
        TestCase(
            name="tamagotchi_toggle_functionality",
            description="Test tamagotchi toggle functionality",
            test_func=test_tamagotchi_toggle_functionality,
            category="bot_functionality",
        ),
        TestCase(
            name="youtube_url_detection",
            description="Test YouTube URL detection functionality",
            test_func=test_youtube_url_detection,
            category="bot_functionality",
        ),
        TestCase(
            name="url_blacklist_functionality",
            description="Test URL blacklisting for title fetching",
            test_func=test_url_blacklist_functionality,
            category="bot_functionality",
        ),
        TestCase(
            name="nanoleet_message_for_leet",
            description="Test nanoleet message processing for regular leet detection",
            test_func=test_nanoleet_message_for_leet,
            category="bot_functionality",
        ),
        TestCase(
            name="bot_manager_initialization_with_services",
            description="Test BotManager initialization with all services",
            test_func=test_bot_manager_initialization_with_services,
            category="bot_functionality",
        ),
    ]
    
    suite = TestSuite(
        name="Bot_Functionality",
        description="Tests for core bot functionality (nanoleet, tamagotchi, URL handling, etc.)",
        tests=tests,
    )
    
    runner.add_suite(suite)


# For standalone testing
if __name__ == "__main__":
    from test_framework import TestRunner
    
    runner = TestRunner(verbose=True)
    register_bot_functionality_tests(runner)
    success = runner.run_all()
    
    print(f"\nBot functionality tests: {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1)
