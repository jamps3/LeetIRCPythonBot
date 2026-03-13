#!/usr/bin/env python3
"""
Tests for the !eurojackpot command.
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


class TestEurojackpotCommand:
    """Tests for the !eurojackpot command."""

    def test_eurojackpot_command_default(self, console_context, mock_bot_functions):
        """Test eurojackpot command with default behavior."""
        from cmd_modules.services import command_eurojackpot

        # Mock the eurojackpot functions at the source module
        with patch(
            "services.eurojackpot_service.get_eurojackpot_numbers"
        ) as mock_numbers:
            mock_numbers.return_value = "Next draw: 1, 2, 3, 4, 5 + 1, 2"

            result = command_eurojackpot(console_context, mock_bot_functions)

            assert "Next draw:" in result
            assert "1, 2, 3, 4, 5" in result

    def test_eurojackpot_command_results(self, console_context, mock_bot_functions):
        """Test eurojackpot command with results subcommand."""
        from cmd_modules.services import command_eurojackpot

        # Create context with arguments
        console_context.args_text = "tulokset"
        console_context.args = ["tulokset"]

        # Mock the eurojackpot functions at the source module
        with patch(
            "services.eurojackpot_service.get_eurojackpot_results"
        ) as mock_results:
            mock_results.return_value = "Last draw: 1, 2, 3, 4, 5 + 1, 2"

            result = command_eurojackpot(console_context, mock_bot_functions)

            assert "Last draw:" in result
            assert "1, 2, 3, 4, 5" in result

    def test_eurojackpot_command_error(self, console_context, mock_bot_functions):
        """Test eurojackpot command with error handling."""
        from cmd_modules.services import command_eurojackpot

        # Mock the eurojackpot function to raise an exception at the source module
        with patch(
            "services.eurojackpot_service.get_eurojackpot_numbers"
        ) as mock_numbers:
            mock_numbers.side_effect = Exception("Service error")

            result = command_eurojackpot(console_context, mock_bot_functions)

            assert "Eurojackpot error" in result
            assert "Service error" in result
