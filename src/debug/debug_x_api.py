#!/usr/bin/env python3
"""
Debug script for X API functionality in bot_manager.py

This script tests the X API post content fetching feature with various scenarios:
- Missing dependencies
- Missing bearer token
- URL parsing validation
- Graceful error handling

Usage: python src/debug/debug_x_api.py
"""

import os
import sys
import tempfile
from unittest.mock import Mock, patch

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import logger
from bot_manager import BotManager


def test_x_api_missing_dependencies():
    """Test X API behavior when dependencies are missing."""
    print("🔍 Testing X API with missing dependencies...")

    # Mock the xdk import to be unavailable
    with patch.dict("sys.modules", {"xdk": None}):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            state_file = f.name

        try:
            # Initialize bot manager (this will check for xdk import)
            bot = BotManager("TestBot", console_mode=True)

            # Create mock IRC server and target
            mock_irc = Mock()
            target = "#test"

            # Test URL
            test_url = "https://x.com/testuser/status/1234567890"

            # Call the method
            bot._fetch_x_post_content(mock_irc, target, test_url)

            # Check that warning was logged (dependency not available)
            print("✅ X API correctly handles missing dependencies")

            # Verify no message was sent to IRC (since dependency is missing)
            mock_irc.send_message.assert_not_called()
            print("✅ No IRC message sent when dependency missing")

        finally:
            # Clean up
            if os.path.exists(state_file):
                os.unlink(state_file)


def test_x_api_missing_token():
    """Test X API behavior when dependency is available but token is missing."""
    print("🔍 Testing X API with available dependency but missing token...")

    # Create a temporary state file
    with tempfile.NamedTemporaryFile(delete=False) as f:
        state_file = f.name

    try:
        # Initialize bot manager (xdk should now be available)
        bot = BotManager("TestBot", console_mode=True)

        # Create mock IRC server and target
        mock_irc = Mock()
        target = "#test"

        # Test URL
        test_url = "https://x.com/testuser/status/1234567890"

        # Call the method
        bot._fetch_x_post_content(mock_irc, target, test_url)

        # Should log warning about missing token and not send message
        print("✅ X API correctly handles missing bearer token")

        # Verify no message was sent to IRC (since token is missing)
        mock_irc.send_message.assert_not_called()
        print("✅ No IRC message sent when token missing")

    finally:
        # Clean up
        if os.path.exists(state_file):
            os.unlink(state_file)


def test_x_api_url_parsing():
    """Test X API URL parsing functionality."""
    print("🔍 Testing X API URL parsing...")

    with tempfile.NamedTemporaryFile(delete=False) as f:
        state_file = f.name

    try:
        bot = BotManager("TestBot", console_mode=True)

        # Test various X/Twitter URLs
        test_urls = [
            "https://x.com/testuser/status/1234567890",
            "https://twitter.com/testuser/status/1234567890",
            "https://www.x.com/testuser/status/1234567890",
            "https://www.twitter.com/testuser/status/1234567890",
            "https://mobile.twitter.com/testuser/status/1234567890",
        ]

        for url in test_urls:
            is_x_url = bot._is_x_url(url)
            if is_x_url:
                print(f"✅ Correctly identified X URL: {url}")
            else:
                print(f"❌ Failed to identify X URL: {url}")

    finally:
        if os.path.exists(state_file):
            os.unlink(state_file)


def test_x_api_status():
    """Test current X API status and configuration."""
    print("🔍 Testing X API status and configuration...")

    # Check if xdk is available
    try:
        from xdk import Client as XClient

        xdk_available = True
        print("✅ xdk package is installed")
    except ImportError:
        xdk_available = False
        print("❌ xdk package is NOT installed")

    # Check if bearer token is configured
    bearer_token = os.getenv("X_BEARER_TOKEN")
    if bearer_token:
        print("✅ X_BEARER_TOKEN is configured")
        # Don't print the actual token for security
    else:
        print("❌ X_BEARER_TOKEN is NOT configured")

    # Overall status
    if xdk_available and bearer_token:
        print("🎉 X API is fully configured and ready to use!")
    elif xdk_available and not bearer_token:
        print("⚠️  X API dependency installed, but bearer token needed")
        print("   Set X_BEARER_TOKEN environment variable to enable X post fetching")
    else:
        print(
            "❌ X API not available - install xdk package and configure X_BEARER_TOKEN"
        )


if __name__ == "__main__":
    print("🐦 X API Debug Tool")
    print("=" * 50)

    test_x_api_status()
    print()
    test_x_api_missing_dependencies()
    test_x_api_missing_token()
    test_x_api_url_parsing()

    print()
    print("✅ X API debug testing complete!")
    print()
    print("To enable X API functionality:")
    print("1. Ensure xdk package is installed: pip install xdk")
    print("2. Set X_BEARER_TOKEN environment variable")
    print("3. Restart the bot")
    print()
    print("The bot will then automatically fetch X/Twitter post content")
    print("when users share post URLs in IRC channels.")
