#!/usr/bin/env python3
"""
Tests for data commands: !teach and !unlearn.
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


class TestTeachCommand:
    """Tests for the !teach command."""

    def test_teach_command_add_teaching(self, irc_context, mock_bot_functions):
        """Test teach command to add a new teaching."""
        from cmd_modules.services import teach_command

        # Mock the data manager
        with patch("cmd_modules.services.get_data_manager") as mock_get_data_manager:
            mock_data_manager = Mock()
            mock_get_data_manager.return_value = mock_data_manager
            mock_data_manager.add_teaching.return_value = 1

            # Create context with arguments
            irc_context.args_text = "The capital of Finland is Helsinki"
            irc_context.args = ["The", "capital", "of", "Finland", "is", "Helsinki"]

            result = teach_command(irc_context, mock_bot_functions)

            assert "Added teaching #1" in result
            mock_data_manager.add_teaching.assert_called_once_with(
                "The capital of Finland is Helsinki", "TestUser", "TestServer", "#test"
            )

    def test_teach_command_list_teachings(self, irc_context, mock_bot_functions):
        """Test teach command to list teachings."""
        from cmd_modules.services import teach_command

        # Mock the data manager
        with patch("cmd_modules.services.get_data_manager") as mock_get_data_manager:
            mock_data_manager = Mock()
            mock_get_data_manager.return_value = mock_data_manager
            mock_data_manager.get_teachings.return_value = [
                {"id": 1, "content": "Test teaching 1", "added_by": "User1"},
                {"id": 2, "content": "Test teaching 2", "added_by": "User2"},
            ]

            # Create context without arguments (list mode)
            irc_context.args_text = ""
            irc_context.args = []

            result = teach_command(irc_context, mock_bot_functions)

            assert "📚 Teachings:" in result
            assert "Test teaching 1" in result
            assert "Test teaching 2" in result
            mock_data_manager.get_teachings.assert_called_once()

    def test_teach_command_no_teachings(self, irc_context, mock_bot_functions):
        """Test teach command when no teachings exist."""
        from cmd_modules.services import teach_command

        # Mock the data manager
        with patch("cmd_modules.services.get_data_manager") as mock_get_data_manager:
            mock_data_manager = Mock()
            mock_get_data_manager.return_value = mock_data_manager
            mock_data_manager.get_teachings.return_value = []

            # Create context without arguments (list mode)
            irc_context.args_text = ""
            irc_context.args = []

            result = teach_command(irc_context, mock_bot_functions)

            assert "No teachings stored yet" in result


class TestUnlearnCommand:
    """Tests for the !unlearn command."""

    def test_unlearn_command_remove_teaching(self, irc_context, mock_bot_functions):
        """Test unlearn command to remove a teaching."""
        from cmd_modules.services import unlearn_command

        # Mock the data manager
        with patch("cmd_modules.services.get_data_manager") as mock_get_data_manager:
            mock_data_manager = Mock()
            mock_get_data_manager.return_value = mock_data_manager
            mock_data_manager.get_teaching_by_id.return_value = {
                "id": 1,
                "content": "Test teaching to remove",
                "added_by": "User1",
            }
            mock_data_manager.remove_teaching.return_value = True

            # Create context with teaching ID
            irc_context.args_text = "1"
            irc_context.args = ["1"]

            result = unlearn_command(irc_context, mock_bot_functions)

            assert "Removed teaching #1" in result
            assert "Test teaching to remove" in result
            mock_data_manager.get_teaching_by_id.assert_called_once_with(1)
            mock_data_manager.remove_teaching.assert_called_once_with(1)

    def test_unlearn_command_invalid_id(self, irc_context, mock_bot_functions):
        """Test unlearn command with invalid ID."""
        from cmd_modules.services import unlearn_command

        # Mock the data manager
        with patch("cmd_modules.services.get_data_manager") as mock_get_data_manager:
            mock_data_manager = Mock()
            mock_get_data_manager.return_value = mock_data_manager

            # Create context with invalid ID
            irc_context.args_text = "abc"
            irc_context.args = ["abc"]

            result = unlearn_command(irc_context, mock_bot_functions)

            assert "Invalid teaching ID" in result

    def test_unlearn_command_teaching_not_found(self, irc_context, mock_bot_functions):
        """Test unlearn command when teaching is not found."""
        from cmd_modules.services import unlearn_command

        # Mock the data manager
        with patch("cmd_modules.services.get_data_manager") as mock_get_data_manager:
            mock_data_manager = Mock()
            mock_get_data_manager.return_value = mock_data_manager
            mock_data_manager.get_teaching_by_id.return_value = None

            # Create context with teaching ID
            irc_context.args_text = "999"
            irc_context.args = ["999"]

            result = unlearn_command(irc_context, mock_bot_functions)

            assert "not found" in result
            mock_data_manager.get_teaching_by_id.assert_called_once_with(999)
