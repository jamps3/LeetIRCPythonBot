#!/usr/bin/env python3
"""
Tests for media commands: !youtube and !imdb.
"""

import os
import sys
from unittest.mock import Mock

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


class TestYouTubeCommand:
    """Tests for the !youtube command."""

    def test_youtube_command_with_query(self, console_context, mock_bot_functions):
        """Test YouTube command with search query."""
        from cmd_modules.services import youtube_command

        # Create context with arguments
        console_context.args_text = "python tutorial"
        console_context.args = ["python", "tutorial"]

        # Mock the send_youtube_info function
        mock_bot_functions["send_youtube_info"].return_value = None

        result = youtube_command(console_context, mock_bot_functions)

        # Should return no_response since service handles output
        assert isinstance(result, CommandResponse)
        assert result.should_respond is False
        # Just verify it was called
        mock_bot_functions["send_youtube_info"].assert_called_once()

    def test_youtube_command_with_number(self, console_context, mock_bot_functions):
        """Test YouTube command with number parameter."""
        from cmd_modules.services import youtube_command

        # Create context with arguments including number
        console_context.args_text = "5 python tutorial"
        console_context.args = ["5", "python", "tutorial"]

        # Mock the send_youtube_info function
        mock_bot_functions["send_youtube_info"].return_value = None

        result = youtube_command(console_context, mock_bot_functions)

        # Should return no_response since service handles output
        assert isinstance(result, CommandResponse)
        assert result.should_respond is False
        # Just verify it was called
        mock_bot_functions["send_youtube_info"].assert_called_once()

    def test_youtube_command_no_service(self, console_context, mock_bot_functions):
        """Test YouTube command when service is not available."""
        from cmd_modules.services import youtube_command

        # Remove send_youtube_info from bot functions
        del mock_bot_functions["send_youtube_info"]

        result = youtube_command(console_context, mock_bot_functions)

        assert "YouTube service not available" in result


class TestImdbCommand:
    """Tests for the !imdb command."""

    def test_imdb_command_with_title(self, console_context, mock_bot_functions):
        """Test IMDb command with movie title."""
        from cmd_modules.services import imdb_command

        # Create context with arguments
        console_context.args_text = "The Matrix"
        console_context.args = ["The", "Matrix"]

        # Mock the send_imdb_info function
        mock_bot_functions["send_imdb_info"].return_value = None

        result = imdb_command(console_context, mock_bot_functions)

        # Should return no_response since service handles output
        assert isinstance(result, CommandResponse)
        assert result.should_respond is False
        mock_bot_functions["send_imdb_info"].assert_called_once_with(
            mock_bot_functions["server"],
            None,  # target is None for console
            "The Matrix",
        )

    def test_imdb_command_no_service(self, console_context, mock_bot_functions):
        """Test IMDb command when service is not available."""
        from cmd_modules.services import imdb_command

        # Remove send_imdb_info from bot functions
        del mock_bot_functions["send_imdb_info"]

        result = imdb_command(console_context, mock_bot_functions)

        assert result == "IMDb service not available."
