#!/usr/bin/env python3
"""
Pytest tests for commands_irc module.

Tests IRC-specific commands that use / prefix instead of !.
"""

from unittest.mock import Mock

import pytest

from command_registry import reset_command_registry
from commands_irc import (
    get_irc_connection,
    irc_admin_command,
    irc_away_command,
    irc_invite_command,
    irc_join_command,
    irc_kick_command,
    irc_list_command,
    irc_mode_command,
    irc_motd_command,
    irc_msg_command,
    irc_names_command,
    irc_nick_command,
    irc_notice_command,
    irc_part_command,
    irc_ping_command,
    irc_quit_command,
    irc_raw_command,
    irc_time_command,
    irc_topic_command,
    irc_version_command,
    irc_whois_command,
    irc_whowas_command,
)


@pytest.fixture(autouse=True, scope="function")
def reset_registry():
    """Reset command registry before each test."""
    reset_command_registry()
    yield
    reset_command_registry()


@pytest.fixture
def mock_context():
    """Create a mock command context."""
    from command_registry import CommandContext

    return CommandContext(
        command="test",
        args=["arg1", "arg2"],
        raw_message="!test arg1 arg2",
        sender="TestUser",
        target="#testchannel",
        is_private=False,
        is_console=False,
        server_name="TestServer",
    )


@pytest.fixture
def mock_console_context():
    """Create a mock console command context."""
    from command_registry import CommandContext

    return CommandContext(
        command="test",
        args=["arg1", "arg2"],
        raw_message="!test arg1 arg2",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )


@pytest.fixture
def mock_irc():
    """Create a mock IRC connection."""
    irc = Mock()
    irc.send_raw = Mock()
    irc.send_message = Mock()
    irc.send_notice = Mock()
    irc.send = Mock()
    return irc


@pytest.fixture
def mock_bot_functions(mock_irc):
    """Create mock bot functions."""
    return {
        "irc": mock_irc,
        "log": Mock(),
        "stop_event": Mock(),
    }


@pytest.fixture
def mock_bot_manager(mock_irc):
    """Create a mock bot manager."""
    bm = Mock()
    bm.servers = {"TestServer": mock_irc}
    bm.joined_channels = {"TestServer": ["#testchannel"]}
    return bm


class TestIRCCommands:
    """Test IRC-specific commands."""

    def test_get_irc_connection_console_mode(
        self, mock_console_context, mock_bot_manager
    ):
        """Test getting IRC connection in console mode."""
        mock_console_context.is_console = True

        # Should work with bot_functions passed directly
        bot_functions = {"bot_manager": mock_bot_manager}
        result = get_irc_connection(mock_console_context, bot_functions)
        assert result is not None

    def test_get_irc_connection_irc_mode(self, mock_context, mock_irc):
        """Test getting IRC connection in IRC mode."""
        bot_functions = {"irc": mock_irc}
        result = get_irc_connection(mock_context, bot_functions)
        assert result == mock_irc

    def test_get_irc_connection_no_connection(self, mock_console_context):
        """Test getting IRC connection when none available."""
        result = get_irc_connection(mock_console_context, {})
        assert result is None

    def test_irc_join_command_success(self, mock_context, mock_irc, mock_bot_functions):
        """Test successful IRC join command."""
        mock_context.args = ["#newchannel"]
        mock_bot_functions["irc"] = mock_irc

        result = irc_join_command(mock_context, mock_bot_functions)

        assert "✅ Joining #newchannel" in result
        mock_irc.send_raw.assert_called_with("JOIN #newchannel")

    def test_irc_join_command_with_key(
        self, mock_context, mock_irc, mock_bot_functions
    ):
        """Test IRC join command with channel key."""
        mock_context.args = ["#private", "secret"]
        mock_bot_functions["irc"] = mock_irc

        result = irc_join_command(mock_context, mock_bot_functions)

        assert "✅ Joining #private" in result
        mock_irc.send_raw.assert_called_with("JOIN #private secret")

    def test_irc_join_command_add_hash(
        self, mock_context, mock_irc, mock_bot_functions
    ):
        """Test IRC join command adds # prefix if missing."""
        mock_context.args = ["newchannel"]
        mock_bot_functions["irc"] = mock_irc

        result = irc_join_command(mock_context, mock_bot_functions)

        assert "✅ Joining #newchannel" in result
        mock_irc.send_raw.assert_called_with("JOIN #newchannel")

    def test_irc_join_command_no_args(self, mock_context, mock_bot_functions):
        """Test IRC join command with no arguments."""
        mock_context.args = []

        result = irc_join_command(mock_context, mock_bot_functions)

        assert "Usage: /join <#channel> [key]" in result

    def test_irc_join_command_no_connection(self, mock_context):
        """Test IRC join command with no IRC connection."""
        mock_context.args = ["#test"]

        result = irc_join_command(mock_context, {})

        assert "❌ No IRC connection available" in result

    def test_irc_part_command_success(self, mock_context, mock_irc, mock_bot_functions):
        """Test successful IRC part command."""
        mock_context.args = ["#oldchannel"]
        mock_bot_functions["irc"] = mock_irc

        result = irc_part_command(mock_context, mock_bot_functions)

        assert "✅ Left #oldchannel" in result
        mock_irc.send_raw.assert_called_with("PART #oldchannel")

    def test_irc_part_command_with_message(
        self, mock_context, mock_irc, mock_bot_functions
    ):
        """Test IRC part command with leave message."""
        mock_context.args = ["#oldchannel", "Goodbye", "everyone"]
        mock_bot_functions["irc"] = mock_irc

        result = irc_part_command(mock_context, mock_bot_functions)

        assert "✅ Left #oldchannel" in result
        mock_irc.send_raw.assert_called_with("PART #oldchannel :Goodbye everyone")

    def test_irc_part_command_no_args(self, mock_context, mock_bot_functions):
        """Test IRC part command with no arguments."""
        mock_context.args = []

        result = irc_part_command(mock_context, mock_bot_functions)

        assert "Usage: /part <#channel> [message]" in result

    def test_irc_quit_command_success(self, mock_context, mock_irc, mock_bot_functions):
        """Test successful IRC quit command."""
        mock_context.args = ["Goodbye", "world"]
        mock_bot_functions["irc"] = mock_irc
        mock_bot_functions["stop_event"] = Mock()

        result = irc_quit_command(mock_context, mock_bot_functions)

        assert "✅ Disconnecting: Goodbye world" in result
        mock_irc.send_raw.assert_called_with("QUIT :Goodbye world")

    def test_irc_quit_command_no_args(self, mock_context, mock_irc, mock_bot_functions):
        """Test IRC quit command with no arguments."""
        mock_context.args = []
        mock_bot_functions["irc"] = mock_irc

        result = irc_quit_command(mock_context, mock_bot_functions)

        assert "✅ Disconnecting: Quit" in result
        mock_irc.send_raw.assert_called_with("QUIT :Quit")

    def test_irc_nick_command_success(self, mock_context, mock_irc, mock_bot_functions):
        """Test successful IRC nick command."""
        mock_context.args = ["NewNick"]
        mock_bot_functions["irc"] = mock_irc

        result = irc_nick_command(mock_context, mock_bot_functions)

        assert "✅ Changing nick to NewNick" in result
        mock_irc.send_raw.assert_called_with("NICK NewNick")

    def test_irc_nick_command_no_args(self, mock_context, mock_bot_functions):
        """Test IRC nick command with no arguments."""
        mock_context.args = []

        result = irc_nick_command(mock_context, mock_bot_functions)

        assert "Usage: /nick <new_nickname>" in result

    def test_irc_msg_command_success(self, mock_context, mock_irc, mock_bot_functions):
        """Test successful IRC msg command."""
        mock_context.args = ["TargetUser", "Hello", "there"]
        mock_bot_functions["irc"] = mock_irc

        result = irc_msg_command(mock_context, mock_bot_functions)

        assert "✅ Message sent to TargetUser" in result
        mock_irc.send_raw.assert_called_with("PRIVMSG TargetUser :Hello there")

    def test_irc_msg_command_fallback(self, mock_context, mock_irc, mock_bot_functions):
        """Test IRC msg command fallback when send_raw not available."""
        mock_context.args = ["TargetUser", "Hello"]
        mock_bot_functions["irc"] = mock_irc
        del mock_irc.send_raw  # Remove send_raw to test fallback

        result = irc_msg_command(mock_context, mock_bot_functions)

        assert "✅ Message sent to TargetUser" in result
        mock_irc.send_message.assert_called_with("TargetUser", "Hello")

    def test_irc_msg_command_no_args(self, mock_context, mock_bot_functions):
        """Test IRC msg command with insufficient arguments."""
        mock_context.args = ["TargetUser"]

        result = irc_msg_command(mock_context, mock_bot_functions)

        assert "Usage: /msg <nick> <message>" in result

    def test_irc_notice_command_success(
        self, mock_context, mock_irc, mock_bot_functions
    ):
        """Test successful IRC notice command."""
        mock_context.args = ["TargetUser", "Important", "message"]
        mock_bot_functions["irc"] = mock_irc

        result = irc_notice_command(mock_context, mock_bot_functions)

        assert "✅ Notice sent to TargetUser" in result
        mock_irc.send_raw.assert_called_with("NOTICE TargetUser :Important message")

    def test_irc_notice_command_fallback(
        self, mock_context, mock_irc, mock_bot_functions
    ):
        """Test IRC notice command fallback when send_raw not available."""
        mock_context.args = ["TargetUser", "Notice"]
        mock_bot_functions["irc"] = mock_irc
        del mock_irc.send_raw  # Remove send_raw to test fallback

        result = irc_notice_command(mock_context, mock_bot_functions)

        assert "✅ Notice sent to TargetUser" in result
        mock_irc.send_notice.assert_called_with("TargetUser", "Notice")

    def test_irc_away_command_with_message(
        self, mock_context, mock_irc, mock_bot_functions
    ):
        """Test IRC away command with message."""
        mock_context.args = ["Gone", "to", "lunch"]
        mock_bot_functions["irc"] = mock_irc

        result = irc_away_command(mock_context, mock_bot_functions)

        assert "✅ Set away: Gone to lunch" in result
        mock_irc.send_raw.assert_called_with("AWAY :Gone to lunch")

    def test_irc_away_command_no_message(
        self, mock_context, mock_irc, mock_bot_functions
    ):
        """Test IRC away command without message."""
        mock_context.args = []
        mock_bot_functions["irc"] = mock_irc

        result = irc_away_command(mock_context, mock_bot_functions)

        assert "✅ Removed away status" in result
        mock_irc.send_raw.assert_called_with("AWAY")

    def test_irc_whois_command_success(
        self, mock_context, mock_irc, mock_bot_functions
    ):
        """Test successful IRC whois command."""
        mock_context.args = ["SomeUser"]
        mock_bot_functions["irc"] = mock_irc

        result = irc_whois_command(mock_context, mock_bot_functions)

        assert "✅ WHOIS request sent for SomeUser" in result
        mock_irc.send_raw.assert_called_with("WHOIS SomeUser")

    def test_irc_whowas_command_success(
        self, mock_context, mock_irc, mock_bot_functions
    ):
        """Test successful IRC whowas command."""
        mock_context.args = ["OldUser"]
        mock_bot_functions["irc"] = mock_irc

        result = irc_whowas_command(mock_context, mock_bot_functions)

        assert "✅ WHOWAS request sent for OldUser" in result
        mock_irc.send_raw.assert_called_with("WHOWAS OldUser")

    def test_irc_list_command_with_channel(
        self, mock_context, mock_irc, mock_bot_functions
    ):
        """Test IRC list command with specific channel."""
        mock_context.args = ["#specific"]
        mock_bot_functions["irc"] = mock_irc

        result = irc_list_command(mock_context, mock_bot_functions)

        assert "✅ Listing channel info for #specific" in result
        mock_irc.send_raw.assert_called_with("LIST #specific")

    def test_irc_list_command_all_channels(
        self, mock_context, mock_irc, mock_bot_functions
    ):
        """Test IRC list command for all channels."""
        mock_context.args = []
        mock_bot_functions["irc"] = mock_irc

        result = irc_list_command(mock_context, mock_bot_functions)

        assert "✅ Listing all channels" in result
        mock_irc.send_raw.assert_called_with("LIST")

    def test_irc_invite_command_success(
        self, mock_context, mock_irc, mock_bot_functions
    ):
        """Test successful IRC invite command."""
        mock_context.args = ["NewUser", "#private"]
        mock_bot_functions["irc"] = mock_irc

        result = irc_invite_command(mock_context, mock_bot_functions)

        assert "✅ Invited NewUser to #private" in result
        mock_irc.send_raw.assert_called_with("INVITE NewUser #private")

    def test_irc_invite_command_add_hash(
        self, mock_context, mock_irc, mock_bot_functions
    ):
        """Test IRC invite command adds # prefix."""
        mock_context.args = ["NewUser", "private"]
        mock_bot_functions["irc"] = mock_irc

        result = irc_invite_command(mock_context, mock_bot_functions)

        assert "✅ Invited NewUser to #private" in result
        mock_irc.send_raw.assert_called_with("INVITE NewUser #private")

    def test_irc_invite_command_no_args(self, mock_context, mock_bot_functions):
        """Test IRC invite command with insufficient arguments."""
        mock_context.args = ["NewUser"]

        result = irc_invite_command(mock_context, mock_bot_functions)

        assert "Usage: /invite <nick> <#channel>" in result

    def test_irc_kick_command_success(self, mock_context, mock_irc, mock_bot_functions):
        """Test successful IRC kick command."""
        mock_context.args = ["BadUser", "Spam"]
        mock_context.target = "#channel"
        mock_bot_functions["irc"] = mock_irc

        result = irc_kick_command(mock_context, mock_bot_functions)

        assert "✅ Kicked BadUser from #channel" in result
        mock_irc.send_raw.assert_called_with("KICK #channel BadUser :Spam")

    def test_irc_kick_command_no_reason(
        self, mock_context, mock_irc, mock_bot_functions
    ):
        """Test IRC kick command without reason."""
        mock_context.args = ["BadUser"]
        mock_context.target = "#channel"
        mock_bot_functions["irc"] = mock_irc

        result = irc_kick_command(mock_context, mock_bot_functions)

        assert "✅ Kicked BadUser from #channel" in result
        mock_irc.send_raw.assert_called_with("KICK #channel BadUser")

    def test_irc_kick_command_no_channel(self, mock_context, mock_bot_functions):
        """Test IRC kick command without target channel."""
        mock_context.args = ["BadUser"]
        mock_context.target = None

        result = irc_kick_command(mock_context, mock_bot_functions)

        assert "❌ This command must be used in a channel" in result

    def test_irc_topic_command_success(
        self, mock_context, mock_irc, mock_bot_functions
    ):
        """Test successful IRC topic command."""
        mock_context.args = ["#channel", "New", "topic", "here"]
        mock_bot_functions["irc"] = mock_irc

        result = irc_topic_command(mock_context, mock_bot_functions)

        assert "✅ Set topic for #channel: New topic here" in result
        mock_irc.send_raw.assert_called_with("TOPIC #channel :New topic here")

    def test_irc_topic_command_add_hash(
        self, mock_context, mock_irc, mock_bot_functions
    ):
        """Test IRC topic command adds # prefix."""
        mock_context.args = ["channel", "New topic"]
        mock_bot_functions["irc"] = mock_irc

        result = irc_topic_command(mock_context, mock_bot_functions)

        assert "✅ Set topic for #channel: New topic" in result
        mock_irc.send_raw.assert_called_with("TOPIC #channel :New topic")

    def test_irc_mode_command_success(self, mock_context, mock_irc, mock_bot_functions):
        """Test successful IRC mode command."""
        mock_context.args = ["#channel", "+t", "-l"]
        mock_bot_functions["irc"] = mock_irc

        result = irc_mode_command(mock_context, mock_bot_functions)

        assert "✅ Set mode +t -l on #channel" in result
        mock_irc.send_raw.assert_called_with("MODE #channel +t -l")

    def test_irc_names_command_success(
        self, mock_context, mock_irc, mock_bot_functions
    ):
        """Test successful IRC names command."""
        mock_context.args = ["#channel"]
        mock_bot_functions["irc"] = mock_irc

        result = irc_names_command(mock_context, mock_bot_functions)

        assert "✅ Requesting user list for #channel" in result
        mock_irc.send_raw.assert_called_with("NAMES #channel")

    def test_irc_names_command_add_hash(
        self, mock_context, mock_irc, mock_bot_functions
    ):
        """Test IRC names command adds # prefix."""
        mock_context.args = ["channel"]
        mock_bot_functions["irc"] = mock_irc

        result = irc_names_command(mock_context, mock_bot_functions)

        assert "✅ Requesting user list for #channel" in result
        mock_irc.send_raw.assert_called_with("NAMES #channel")

    def test_irc_ping_command_success(self, mock_context, mock_irc, mock_bot_functions):
        """Test successful IRC ping command."""
        mock_context.args = ["irc.example.com"]
        mock_bot_functions["irc"] = mock_irc

        result = irc_ping_command(mock_context, mock_bot_functions)

        assert "✅ Ping sent to irc.example.com" in result
        mock_irc.send_raw.assert_called_with("PING irc.example.com")

    def test_irc_time_command_success(self, mock_context, mock_irc, mock_bot_functions):
        """Test successful IRC time command."""
        mock_context.args = []
        mock_bot_functions["irc"] = mock_irc

        result = irc_time_command(mock_context, mock_bot_functions)

        assert "✅ Time request sent to server" in result
        mock_irc.send_raw.assert_called_with("TIME")

    def test_irc_version_command_success(
        self, mock_context, mock_irc, mock_bot_functions
    ):
        """Test successful IRC version command."""
        mock_context.args = []
        mock_bot_functions["irc"] = mock_irc

        result = irc_version_command(mock_context, mock_bot_functions)

        assert "✅ Version request sent to server" in result
        mock_irc.send_raw.assert_called_with("VERSION")

    def test_irc_admin_command_success(
        self, mock_context, mock_irc, mock_bot_functions
    ):
        """Test successful IRC admin command."""
        mock_context.args = []
        mock_bot_functions["irc"] = mock_irc

        result = irc_admin_command(mock_context, mock_bot_functions)

        assert "✅ Admin info request sent" in result
        mock_irc.send_raw.assert_called_with("ADMIN")

    def test_irc_admin_command_with_server(
        self, mock_context, mock_irc, mock_bot_functions
    ):
        """Test IRC admin command with server argument."""
        mock_context.args = ["irc.example.com"]
        mock_bot_functions["irc"] = mock_irc

        result = irc_admin_command(mock_context, mock_bot_functions)

        assert "✅ Admin info request sent" in result
        mock_irc.send_raw.assert_called_with("ADMIN irc.example.com")

    def test_irc_motd_command_success(self, mock_context, mock_irc, mock_bot_functions):
        """Test successful IRC motd command."""
        mock_context.args = []
        mock_bot_functions["irc"] = mock_irc

        result = irc_motd_command(mock_context, mock_bot_functions)

        assert "✅ MOTD request sent" in result
        mock_irc.send_raw.assert_called_with("MOTD")

    def test_irc_raw_command_success(
        self, mock_context, mock_irc, mock_bot_functions, monkeypatch
    ):
        """Test successful IRC raw command."""
        # Mock admin password verification to accept "password"
        from unittest.mock import patch

        def mock_verify_admin_password(args):
            return args and args[0] == "password"

        monkeypatch.setattr(
            "commands_irc.verify_admin_password", mock_verify_admin_password
        )

        mock_context.args = ["password", "MODE", "#channel", "+t"]
        mock_bot_functions["irc"] = mock_irc

        result = irc_raw_command(mock_context, mock_bot_functions)

        assert "✅ Raw command sent: MODE #channel +t" in result
        mock_irc.send_raw.assert_called_with("MODE #channel +t")

    def test_irc_raw_command_fallback(
        self, mock_context, mock_irc, mock_bot_functions, monkeypatch
    ):
        """Test IRC raw command fallback when send_raw not available."""

        # Mock admin password verification to accept "password"
        def mock_verify_admin_password(args):
            return args and args[0] == "password"

        monkeypatch.setattr(
            "commands_irc.verify_admin_password", mock_verify_admin_password
        )

        mock_context.args = ["password", "PING", "server"]
        mock_bot_functions["irc"] = mock_irc
        del mock_irc.send_raw  # Remove send_raw to test fallback

        result = irc_raw_command(mock_context, mock_bot_functions)

        assert "✅ Raw command sent: PING server" in result
        mock_irc.send.assert_called_with("PING server")

    # Test error cases for commands that require IRC connection
    @pytest.mark.parametrize(
        "command_func,command_name",
        [
            (irc_join_command, "join"),
            (irc_part_command, "part"),
            (irc_quit_command, "quit"),
            (irc_nick_command, "nick"),
            (irc_msg_command, "msg"),
            (irc_notice_command, "notice"),
            (irc_away_command, "away"),
            (irc_whois_command, "whois"),
            (irc_whowas_command, "whowas"),
            (irc_list_command, "list"),
            (irc_invite_command, "invite"),
            (irc_kick_command, "kick"),
            (irc_topic_command, "topic"),
            (irc_mode_command, "mode"),
            (irc_names_command, "names"),
            (irc_ping_command, "ping"),
            (irc_time_command, "time"),
            (irc_version_command, "version"),
            (irc_admin_command, "admin"),
            (irc_motd_command, "motd"),
            (irc_raw_command, "raw"),
        ],
    )
    def test_irc_commands_no_connection(
        self, mock_context, mock_irc, command_func, command_name
    ):
        """Test that IRC commands handle no connection gracefully."""
        result = command_func(mock_context, {})
        assert "❌ No IRC connection available" in result
