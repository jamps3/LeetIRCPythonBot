"""
Tests for games commands in cmd_modules/games.py
"""

import os
import sys
from unittest.mock import Mock, patch

import pytest

# Add src to path before importing project modules
_TEST_ROOT = os.path.dirname(os.path.abspath(__file__))
if _TEST_ROOT not in sys.path:
    sys.path.insert(0, os.path.join(_TEST_ROOT, "..", "src"))

from command_registry import CommandContext  # noqa: E402


@pytest.fixture
def mock_bot_functions():
    """Create mock bot functions for testing commands."""
    return {
        "log": Mock(),
        "notice_message": Mock(),
    }


@pytest.fixture
def console_context():
    """Create a mock CommandContext for console commands."""
    return CommandContext(
        command="",
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
        command="",
        args=[],
        raw_message="!test",
        sender="TestUser",
        target="#test",
        is_private=False,
        is_console=False,
        server_name="TestServer",
    )


class TestKolikkoCommand:
    """Tests for the !kolikko (coin) command."""

    def test_kolikko_command_exists(self):
        """Test kolikko command is registered."""
        from cmd_modules.games import kolikko_command

        assert callable(kolikko_command)


class TestNoppaCommand:
    """Tests for the !noppa (dice) command."""

    def test_noppa_command_exists(self):
        """Test noppa command is registered."""
        from cmd_modules.games import noppa_command

        assert callable(noppa_command)

    def test_noppa_console(self, console_context, mock_bot_functions):
        """Test noppa command from console."""
        from cmd_modules.games import noppa_command

        console_context.command = "noppa"
        result = noppa_command(console_context, mock_bot_functions)
        assert result is not None
        # Should contain a number between 1-6
        assert any(str(i) in result for i in range(1, 7))


class TestKspCommand:
    """Tests for the !ksp (rock paper scissors) command."""

    def test_ksp_command_exists(self):
        """Test ksp command is registered."""
        from cmd_modules.games import ksp_command

        assert callable(ksp_command)


class TestBlackjackCommand:
    """Tests for the !blackjack command."""

    def test_blackjack_command_exists(self):
        """Test blackjack command is registered."""
        from cmd_modules.games import blackjack_command

        assert callable(blackjack_command)


class TestSanaketjuCommand:
    """Tests for the !sanaketju (word chain) command."""

    def test_sanaketju_command_exists(self):
        """Test sanaketju command is registered."""
        from cmd_modules.games import sanaketju_command

        assert callable(sanaketju_command)
