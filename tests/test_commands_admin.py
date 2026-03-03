"""
Tests for admin commands in cmd_modules/admin.py
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


class TestConnectCommand:
    """Tests for the !connect command."""

    def test_connect_command_exists(self):
        """Test connect command is registered."""
        from cmd_modules.admin import connect_command

        assert callable(connect_command)


class TestDisconnectCommand:
    """Tests for the !disconnect command."""

    def test_disconnect_command_exists(self):
        """Test disconnect command is registered."""
        from cmd_modules.admin import disconnect_command

        assert callable(disconnect_command)


class TestExitCommand:
    """Tests for the !exit command."""

    def test_exit_command_exists(self):
        """Test exit command is registered."""
        from cmd_modules.admin import exit_command

        assert callable(exit_command)


class TestCountdownCommand:
    """Tests for the !k (countdown) command."""

    def test_k_command_exists(self):
        """Test k (countdown) command is registered."""
        from cmd_modules.admin import countdown_command

        assert callable(countdown_command)
