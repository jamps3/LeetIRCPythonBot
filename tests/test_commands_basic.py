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


class TestHelpCommandNoticeRouting:
    """Regression tests for IRC-specific command help delivery."""

    def test_specific_help_sends_message_server_and_target(
        self, irc_context, monkeypatch
    ):
        """!help <command> must pass a server object, not a nick string."""
        from cmd_modules.basic import help_command
        from cmd_modules.services import command_tilaa  # noqa: F401

        irc_context.command = "help"
        irc_context.args = ["tilaa"]
        irc_context.raw_message = "!help tilaa"

        server = Mock(connected=True)
        irc_context.server = server
        sent = []

        def strict_notice(message, irc, target):
            assert hasattr(irc, "connected")
            sent.append((message, irc, target))

        result = help_command(
            irc_context,
            {
                "irc": server,
                "notice_message": strict_notice,
            },
        )

        assert result is None
        assert sent
        assert sent[0][1] is server
        assert sent[0][2] == "TestUser"
        assert "tilaa" in sent[0][0]

    @pytest.mark.parametrize("command_name", ["ping", "tilaa"])
    def test_specific_help_does_not_treat_target_as_server(
        self, irc_context, command_name
    ):
        """Catch str.connected regressions for any specific help command."""
        from cmd_modules.basic import help_command
        from cmd_modules.services import command_tilaa  # noqa: F401

        irc_context.command = "help"
        irc_context.args = [command_name]
        irc_context.raw_message = f"!help {command_name}"

        server = Mock(connected=True)
        messages = []

        def notice_requires_server(message, irc, target):
            if not getattr(irc, "connected", False):
                raise AssertionError("notice helper received a non-server object")
            messages.append((message, target))

        help_command(
            irc_context,
            {
                "irc": server,
                "notice_message": notice_requires_server,
            },
        )

        assert messages
        assert all(target == "TestUser" for _, target in messages)

    def test_general_irc_help_is_split_into_two_notices(self, irc_context):
        """Bare !help should be split into two IRC notices."""
        import cmd_modules  # noqa: F401
        from cmd_modules.basic import help_command
        from command_registry import CommandResponse

        irc_context.command = "help"
        irc_context.args = []
        irc_context.raw_message = "!help"

        server = Mock(connected=True)
        sent = []

        result = help_command(
            irc_context,
            {
                "irc": server,
                "notice_message": lambda message, irc, target: sent.append(
                    (message, irc, target)
                ),
            },
        )

        assert result == CommandResponse.no_response()
        assert len(sent) == 2
        assert sent[0][0].startswith("Available commands: ")
        assert sent[1][0].startswith("Available commands continued: ")
        assert all(irc is server for _, irc, _ in sent)
        assert all(target == "TestUser" for _, _, target in sent)


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
