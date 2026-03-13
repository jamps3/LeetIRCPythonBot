#!/usr/bin/env python3
"""
Tests for the !drugs command.
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


class TestDrugsCommand:
    """Tests for the !drugs command."""

    def test_drugs_command_with_drugs(self, console_context, mock_bot_functions):
        """Test drugs command with drug names."""
        from cmd_modules.services import drugs_command

        # Create context with arguments
        console_context.args_text = "cannabis alcohol"
        console_context.args = ["cannabis", "alcohol"]

        # Mock the check_drug_interactions function
        mock_bot_functions["check_drug_interactions"].return_value = (
            "💊 No interactions found"
        )

        result = drugs_command(console_context, mock_bot_functions)

        assert result == "💊 No interactions found"
        mock_bot_functions["check_drug_interactions"].assert_called_once_with(
            "cannabis alcohol"
        )

    def test_drugs_command_no_service(self, console_context, mock_bot_functions):
        """Test drugs command when service is not available."""
        from cmd_modules.services import drugs_command

        # Remove check_drug_interactions from bot functions
        del mock_bot_functions["check_drug_interactions"]

        # Set args so we get past the usage check
        console_context.args_text = "cannabis alcohol"
        console_context.args = ["cannabis", "alcohol"]

        # Also mock create_drug_service to return None (service not available)
        with patch("cmd_modules.services.create_drug_service") as mock_create_service:
            mock_create_service.return_value = None

            result = drugs_command(console_context, mock_bot_functions)

            assert "Drug service not available" in result
