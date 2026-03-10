#!/usr/bin/env python3
"""
Tests for the !junat (trains) command.
"""

import os
import sys
from unittest.mock import Mock, patch

import pytest

# Add src to path before importing project modules
_TEST_ROOT = os.path.dirname(os.path.abspath(__file__))
if _TEST_ROOT not in sys.path:
    sys.path.insert(0, os.path.join(_TEST_ROOT, "..", "src"))

from command_registry import CommandContext


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


class TestTrainsCommand:
    """Tests for the !junat (trains) command."""

    def test_trains_command_default(self, console_context, mock_bot_functions):
        """Test trains command with default station."""
        from cmd_modules.services import trains_command

        # Mock the trains service
        with patch("cmd_modules.services.get_trains_for_station") as mock_get_trains:
            mock_get_trains.return_value = "Next trains from Joensuu: Train 1, Train 2"

            result = trains_command(console_context, mock_bot_functions)

            assert "Next trains from Joensuu:" in result
            assert "Train 1" in result
            assert "Train 2" in result

    def test_trains_command_specific_station(self, console_context, mock_bot_functions):
        """Test trains command with specific station."""
        from cmd_modules.services import trains_command

        # Create context with arguments
        console_context.args_text = "Helsinki"
        console_context.args = ["Helsinki"]

        # Mock the trains service
        with patch("cmd_modules.services.get_trains_for_station") as mock_get_trains:
            mock_get_trains.return_value = "Next trains from Helsinki: Train A, Train B"

            result = trains_command(console_context, mock_bot_functions)

            assert "Next trains from Helsinki:" in result
            assert "Train A" in result
            assert "Train B" in result

    def test_trains_command_arrivals(self, console_context, mock_bot_functions):
        """Test trains command with arrivals subcommand."""
        from cmd_modules.services import trains_command

        # Create context with arguments
        console_context.args_text = "saapuvat Helsinki"
        console_context.args = ["saapuvat", "Helsinki"]

        # Mock the trains service
        with patch(
            "services.digitraffic_service.get_arrivals_for_station"
        ) as mock_get_arrivals:
            mock_get_arrivals.return_value = (
                "Arriving trains to Helsinki: Train X, Train Y"
            )

            result = trains_command(console_context, mock_bot_functions)

            assert "Arriving trains to Helsinki:" in result
            assert "Train X" in result
            assert "Train Y" in result
