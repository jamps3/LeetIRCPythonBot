#!/usr/bin/env python3
"""
Tests for the !s (weather) command.
"""

import os
import sys
from unittest.mock import Mock, patch

import pytest

# Add src to path before importing project modules
_TEST_ROOT = os.path.dirname(os.path.abspath(__file__))
if _TEST_ROOT not in sys.path:
    sys.path.insert(0, os.path.join(_TEST_ROOT, "..", "src"))

from command_registry import CommandContext, CommandResponse


@pytest.fixture
def mock_bot_functions():
    """Create mock bot functions for testing commands."""
    return {
        "log": Mock(),
        "notice_message": Mock(),
        "send_weather": Mock(),
        "send_electricity_price": Mock(),
        "send_youtube_info": Mock(),
        "send_imdb_info": Mock(),
        "get_crypto_price": Mock(),
        "load_leet_winners": Mock(),
        "get_alko_product": Mock(),
        "check_drug_interactions": Mock(),
        "server": Mock(),
        "bot_manager": Mock(),
    }


@pytest.fixture
def console_context():
    """Create a mock CommandContext for console commands."""
    return CommandContext(
        command="test",
        args=[],
        raw_message="!test",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )


@pytest.fixture
def irc_context():
    """Create a mock CommandContext for IRC commands."""
    return CommandContext(
        command="test",
        args=[],
        raw_message="!test",
        sender="TestUser",
        target="#test",
        is_private=False,
        is_console=False,
        server_name="TestServer",
    )


class TestWeatherCommand:
    """Tests for the !s (weather) command."""

    def test_weather_command_console(self, console_context, mock_bot_functions):
        """Test weather command from console."""
        from cmd_modules.services import weather_command

        # Mock the send_weather function
        mock_bot_functions["send_weather"].return_value = None

        result = weather_command(console_context, mock_bot_functions)

        # Should return no_response since service handles output
        assert isinstance(result, CommandResponse)
        assert result.should_respond is False
        mock_bot_functions["send_weather"].assert_called_once()

    def test_weather_command_irc(self, irc_context, mock_bot_functions):
        """Test weather command from IRC."""
        from cmd_modules.services import weather_command

        # Mock the send_weather function
        mock_bot_functions["send_weather"].return_value = None

        result = weather_command(irc_context, mock_bot_functions)

        # Should return no_response since service handles output
        assert isinstance(result, CommandResponse)
        assert result.should_respond is False
        mock_bot_functions["send_weather"].assert_called_once()

    def test_weather_command_no_service(self, console_context, mock_bot_functions):
        """Test weather command when service is not available."""
        from cmd_modules.services import weather_command

        # Remove send_weather from bot functions
        del mock_bot_functions["send_weather"]

        result = weather_command(console_context, mock_bot_functions)

        assert result == "Weather service not available"
