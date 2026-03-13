#!/usr/bin/env python3
"""
Tests for the !sahko (electricity) command.
"""

import os
import sys
from datetime import datetime
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


class TestElectricityCommand:
    """Tests for the !sahko (electricity) command."""

    def test_electricity_command_console_no_args(
        self, console_context, mock_bot_functions
    ):
        """Test electricity command from console with no arguments."""
        from cmd_modules.services import electricity_command

        # Mock the electricity service - patch the module-level import
        with patch(
            "cmd_modules.services.create_electricity_service"
        ) as mock_service_class, patch(
            "cmd_modules.services.get_api_key"
        ) as mock_get_api_key:

            mock_get_api_key.return_value = "test_api_key"
            mock_service = Mock()
            mock_service_class.return_value = mock_service

            # Mock parse_command_args to return default values
            mock_service.parse_command_args.return_value = {
                "error": None,
                "show_stats": False,
                "show_all_hours": False,
                "date": datetime.now(),
                "is_tomorrow": False,
                "hour": None,
                "quarter": None,
            }

            # Mock get_electricity_price to return a test result
            mock_service.get_electricity_price.return_value = {
                "error": False,
                "message": "Test price message",
            }
            mock_service.format_price_message.return_value = "Test price message"

            result = electricity_command(console_context, mock_bot_functions)

            assert result == "Test price message"
            mock_service.get_electricity_price.assert_called_once()

    def test_electricity_command_console_with_args(
        self, console_context, mock_bot_functions
    ):
        """Test electricity command from console with arguments."""
        from cmd_modules.services import electricity_command

        # Create context with arguments
        console_context.args_text = "huomenna 15"
        console_context.args = ["huomenna", "15"]

        with patch(
            "cmd_modules.services.create_electricity_service"
        ) as mock_service_class, patch(
            "cmd_modules.services.get_api_key"
        ) as mock_get_api_key:

            mock_get_api_key.return_value = "test_api_key"
            mock_service = Mock()
            mock_service_class.return_value = mock_service

            # Mock parse_command_args to return stats values
            mock_service.parse_command_args.return_value = {
                "error": None,
                "show_stats": True,
                "show_all_hours": False,
                "date": datetime.now(),
                "is_tomorrow": True,
                "hour": 15,
                "quarter": None,
            }

            # Mock get_price_statistics to return test data
            mock_service.get_price_statistics.return_value = {
                "min_price": 10.0,
                "max_price": 50.0,
                "avg_price": 30.0,
                "current_price": 25.0,
                "prices": [10.0, 20.0, 30.0, 40.0, 50.0],
            }
            mock_service.format_statistics_message.return_value = "Test stats message"

            result = electricity_command(console_context, mock_bot_functions)

            assert result == "Test stats message"
            mock_service.get_price_statistics.assert_called_once()

    def test_electricity_command_irc(self, irc_context, mock_bot_functions):
        """Test electricity command from IRC."""
        from cmd_modules.services import electricity_command

        # Mock the send_electricity_price function
        mock_bot_functions["send_electricity_price"].return_value = None

        result = electricity_command(irc_context, mock_bot_functions)

        # Should return no_response since service handles output
        assert isinstance(result, CommandResponse)
        assert result.should_respond is False
        mock_bot_functions["send_electricity_price"].assert_called_once()

    def test_electricity_command_no_api_key(self, console_context, mock_bot_functions):
        """Test electricity command when API key is not configured."""
        from cmd_modules.services import electricity_command

        with patch("cmd_modules.services.get_api_key") as mock_get_api_key:
            mock_get_api_key.return_value = None

            result = electricity_command(console_context, mock_bot_functions)

            assert "Electricity service not available" in result
            assert "ELECTRICITY_API_KEY" in result
