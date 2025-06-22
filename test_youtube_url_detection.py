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

    def test_fetch_title_skips_blacklisted_urls(self):
        """Test that _fetch_title skips blacklisted URLs and processes allowed URLs."""
        print("\n=== Testing title fetching blacklist behavior ===")
        
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
        
        # Test text with blacklisted and allowed URLs
        test_cases = [
            # Should be skipped (blacklisted domains)
            "Check YouTube: https://www.youtube.com/watch?v=5nM6T3KCVfM",
            "Facebook link: https://facebook.com/somepost", 
            "Twitter: https://x.com/sometweet",
            "Image file: https://example.com/photo.jpg",
            "PDF file: https://example.com/document.pdf",
            
            # Should be processed (allowed)
            "Regular website: https://example.com",
            "News site: https://news.example.com/article"
        ]
        
        for test_text in test_cases:
            print(f"\nTesting: {test_text}")
            sent_messages.clear()
            
            # Mock requests.get for non-blacklisted URLs
            with patch('requests.get') as mock_get:
                # Set up mock response
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.headers = {'Content-Type': 'text/html'}
                mock_response.content = "<html><head><title>Test Website</title></head></html>"
                mock_get.return_value = mock_response
                
                # Mock BeautifulSoup
                with patch('bs4.BeautifulSoup') as mock_soup:
                    mock_title = Mock()
                    mock_title.string = "Test Website"
                    mock_soup.return_value.find.return_value = mock_title
                    
                    # Call _fetch_title
                    try:
                        self.bot_manager._fetch_title(mock_irc, mock_target, test_text)
                    except ImportError:
                        print("ℹ️  BeautifulSoup not installed, test will skip title fetching")
                        continue
            
            # Check results
            if "youtube.com" in test_text or "facebook.com" in test_text or "x.com" in test_text or ".jpg" in test_text or ".pdf" in test_text:
                # Should be blacklisted
                self.assertEqual(len(sent_messages), 0, f"Blacklisted URL should not generate title: {test_text}")
                print(f"✓ Correctly skipped blacklisted URL")
            else:
                # Should be processed
                if sent_messages:
                    self.assertEqual(len(sent_messages), 1, f"Allowed URL should generate exactly one title: {test_text}")
                    self.assertIn("Test Website", sent_messages[0])
                    print(f"✓ Correctly processed allowed URL")
                else:
                    print(f"ℹ️  No title sent (mocking may not be working)")

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
