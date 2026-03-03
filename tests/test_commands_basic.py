"""
Tests for basic commands in cmd_modules/basic.py
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


class TestPingCommand:
    """Tests for the !ping command."""

    def test_ping_command_exists(self):
        """Test ping command is registered."""
        from cmd_modules.basic import ping_command

        assert callable(ping_command)

    def test_ping_console(self, console_context, mock_bot_functions):
        """Test ping command from console."""
        from cmd_modules.basic import ping_command

        console_context.command = "ping"
        result = ping_command(console_context, mock_bot_functions)
        assert result is not None
        assert "pong" in result.lower()

    def test_ping_irc(self, irc_context, mock_bot_functions):
        """Test ping command from IRC."""
        from cmd_modules.basic import ping_command

        irc_context.command = "ping"
        result = ping_command(irc_context, mock_bot_functions)
        assert result is not None
        assert "pong" in result.lower()


class TestVersionCommand:
    """Tests for the !version command."""

    def test_version_command_exists(self):
        """Test version command is registered."""
        from cmd_modules.basic import version_command

        assert callable(version_command)

    def test_version_returns_version(self, console_context, mock_bot_functions):
        """Test version command returns version info."""
        from cmd_modules.basic import version_command

        console_context.command = "version"
        result = version_command(console_context, mock_bot_functions)
        assert result is not None
        # Should contain version info


class TestHelpCommand:
    """Tests for the !help command."""

    def test_help_command_exists(self):
        """Test help command is registered."""
        from cmd_modules.basic import help_command

        assert callable(help_command)


class TestServersCommand:
    """Tests for the !servers command."""

    def test_servers_command_exists(self):
        """Test servers command is registered."""
        from cmd_modules.basic import servers_command

        assert callable(servers_command)


class TestStatusCommand:
    """Tests for the !status command."""

    def test_status_command_exists(self):
        """Test status command is registered."""
        from cmd_modules.basic import status_command

        assert callable(status_command)


class TestChannelsCommand:
    """Tests for the !channels command."""

    def test_channels_command_exists(self):
        """Test channels command is registered."""
        from cmd_modules.basic import channels_command

        assert callable(channels_command)


class TestAboutCommand:
    """Tests for the !about command."""

    def test_about_command_exists(self):
        """Test about command is registered."""
        from cmd_modules.basic import about_command

        assert callable(about_command)

    def test_about_returns_info(self, console_context, mock_bot_functions):
        """Test about command returns bot info."""
        from cmd_modules.basic import about_command

        console_context.command = "about"
        result = about_command(console_context, mock_bot_functions)
        assert result is not None
        assert "bot" in result.lower() or "leet" in result.lower()
