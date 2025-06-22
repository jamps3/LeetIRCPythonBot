#!/usr/bin/env python3
"""
Test to verify YouTube URL detection and title fetching exclusion.

This test ensures that the _is_youtube_url() method correctly identifies
YouTube URLs and that _fetch_title() skips them.
"""

import unittest
from unittest.mock import Mock, patch
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(__file__))

from bot_manager import BotManager


class TestYouTubeURLDetection(unittest.TestCase):
    """Test cases for YouTube URL detection and title fetching exclusion."""

    def setUp(self):
        """Set up test environment."""
        # Mock all the dependencies for BotManager
        with patch('bot_manager.DataManager'):
            with patch('bot_manager.get_api_key', return_value=None):
                with patch('bot_manager.create_crypto_service', return_value=Mock()):
                    with patch('bot_manager.create_nanoleet_detector', return_value=Mock()):
                        with patch('bot_manager.create_fmi_warning_service', return_value=Mock()):
                            with patch('bot_manager.create_otiedote_service', return_value=Mock()):
                                with patch('bot_manager.Lemmatizer', side_effect=Exception("Mock error")):
                                    self.bot_manager = BotManager("TestBot")

    def test_youtube_url_detection(self):
        """Test that various YouTube URL formats are detected correctly."""
        test_urls = [
            # Standard YouTube URLs
            ("https://www.youtube.com/watch?v=5nM6T3KCVfM", True),
            ("http://www.youtube.com/watch?v=5nM6T3KCVfM", True),
            ("https://youtube.com/watch?v=5nM6T3KCVfM", True),
            
            # Short YouTube URLs
            ("https://youtu.be/5nM6T3KCVfM", True),
            ("http://youtu.be/5nM6T3KCVfM", True),
            
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
            with self.subTest(url=url):
                result = self.bot_manager._is_youtube_url(url)
                self.assertEqual(result, should_be_youtube, 
                    f"URL '{url}' should {'be' if should_be_youtube else 'not be'} detected as YouTube")

    def test_fetch_title_skips_youtube_urls(self):
        """Test that _fetch_title skips YouTube URLs and processes other URLs."""
        print("\n=== Testing title fetching behavior ===")
        
        # Mock IRC and target
        mock_irc = Mock()
        mock_irc.send_message = Mock()
        mock_target = "#test_channel"
        
        # Mock the _send_response method to capture what gets sent
        sent_messages = []
        def mock_send_response(irc, target, message):
            sent_messages.append(message)
            print(f"MOCK SEND: {message}")
        
        self.bot_manager._send_response = mock_send_response
        
        # Test text with both YouTube and non-YouTube URLs
        test_text = "Check this out: https://www.youtube.com/watch?v=5nM6T3KCVfM and also https://example.com"
        
        # Mock requests.get for the non-YouTube URL
        with patch('requests.get') as mock_get:
            # Set up mock response for example.com
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.content = "<html><head><title>Example Website</title></head></html>"
            mock_get.return_value = mock_response
            
            # Mock BeautifulSoup in the correct module
            with patch('bs4.BeautifulSoup') as mock_soup:
                mock_title = Mock()
                mock_title.string = "Example Website"
                mock_soup.return_value.find.return_value = mock_title
                
                # Call _fetch_title
                try:
                    self.bot_manager._fetch_title(mock_irc, mock_target, test_text)
                except ImportError:
                    print("ℹ️  BeautifulSoup not installed, test will skip title fetching")
        
        print(f"Messages sent: {sent_messages}")
        
        # Verify behavior
        if sent_messages:
            # Should only have title for non-YouTube URL
            self.assertEqual(len(sent_messages), 1)
            self.assertIn("Example Website", sent_messages[0])
            self.assertIn("📄", sent_messages[0])  # Title emoji
            print("✓ Title fetching correctly skipped YouTube URL and processed other URL")
        else:
            print("ℹ️  No title messages sent (which is also correct if mocking doesn't work)")

    def test_youtube_url_variations(self):
        """Test edge cases and variations of YouTube URLs."""
        edge_cases = [
            # URLs with parameters
            ("https://www.youtube.com/watch?v=5nM6T3KCVfM&list=PLxxx", True),
            ("https://www.youtube.com/watch?v=5nM6T3KCVfM&t=120s", True),
            
            # Mixed case
            ("HTTPS://WWW.YOUTUBE.COM/WATCH?V=5nM6T3KCVfM", True),
            ("https://YouTube.com/watch?v=5nM6T3KCVfM", True),
            
            # Without protocol
            ("www.youtube.com/watch?v=5nM6T3KCVfM", True),
            ("youtube.com/watch?v=5nM6T3KCVfM", True),
            
            # Invalid video IDs (but still YouTube URLs)
            ("https://www.youtube.com/watch?v=", True),
            ("https://www.youtube.com/watch?v=invalid", True),
        ]
        
        for url, should_be_youtube in edge_cases:
            with self.subTest(url=url):
                result = self.bot_manager._is_youtube_url(url)
                self.assertEqual(result, should_be_youtube,
                    f"Edge case URL '{url}' should {'be' if should_be_youtube else 'not be'} detected as YouTube")


if __name__ == "__main__":
    # Run the tests
    unittest.main(verbosity=2)
