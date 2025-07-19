"""
Tests for Admin Commands - Pure Pytest Version

This module contains comprehensive tests for all admin commands including:
- quit command (console and IRC)
- join command
- part command
- nick command
- raw command
"""

import os
import sys
from unittest.mock import MagicMock, Mock, call, patch
import pytest

# Add parent directory to sys.path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from command_registry import CommandContext, CommandResponse
from commands_admin import (
    join_command,
    nick_command,
    part_command,
    quit_command,
    raw_command,
    verify_admin_password,
)


@pytest.fixture
def mock_config():
    """Create a mock configuration."""
    config = Mock()
    config.admin_password = "testpass123"
    return config


@pytest.fixture
def mock_irc():
    """Create a mock IRC connection."""
    irc = Mock()
    irc.send_raw = Mock()
    return irc


@pytest.fixture
def mock_stop_event():
    """Create a mock stop event."""
    return Mock()


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    return Mock()


@pytest.fixture
def bot_functions(mock_irc, mock_stop_event, mock_logger):
    """Create bot functions dictionary."""
    return {
        "irc": mock_irc,
        "stop_event": mock_stop_event,
        "log": mock_logger,
    }


def test_verify_admin_password_valid(mock_config):
    """Test admin password verification with valid password."""
    with patch("commands_admin.get_config", return_value=mock_config):
        assert verify_admin_password(["testpass123"]) is True


def test_verify_admin_password_invalid(mock_config):
    """Test admin password verification with invalid password."""
    with patch("commands_admin.get_config", return_value=mock_config):
        assert verify_admin_password(["wrongpass"]) is False


def test_verify_admin_password_no_args(mock_config):
    """Test admin password verification with no arguments."""
    with patch("commands_admin.get_config", return_value=mock_config):
        assert verify_admin_password([]) is False


def test_quit_command_console_triggers_shutdown(mock_config, bot_functions):
    """Test that quit command in console actually triggers shutdown."""
    context = CommandContext(
        command="quit",
        args=["testpass123", "goodbye"],
        raw_message="!quit testpass123 goodbye",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )

    with patch("commands_admin.get_config", return_value=mock_config):
        response = quit_command(context, bot_functions)

    # Verify shutdown was triggered
    bot_functions["stop_event"].set.assert_called_once()
    assert "🛑 Shutting down bot" in response
    assert "goodbye" in response


def test_quit_command_console_no_message(mock_config, bot_functions):
    """Test quit command in console without message."""
    context = CommandContext(
        command="quit",
        args=["testpass123"],
        raw_message="!quit testpass123",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )

    with patch("commands_admin.get_config", return_value=mock_config):
        response = quit_command(context, bot_functions)

    bot_functions["stop_event"].set.assert_called_once()
    assert "🛑 Shutting down bot" in response
    assert "Admin quit" in response


def test_quit_command_console_invalid_password(mock_config, bot_functions):
    """Test quit command with invalid password."""
    context = CommandContext(
        command="quit",
        args=["wrongpass"],
        raw_message="!quit wrongpass",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )

    with patch("commands_admin.get_config", return_value=mock_config):
        response = quit_command(context, bot_functions)

    # Verify shutdown was NOT triggered
    bot_functions["stop_event"].set.assert_not_called()
    assert response == "❌ Invalid admin password"


def test_quit_command_console_no_stop_event(mock_config, mock_irc, mock_logger):
    """Test quit command when stop_event is not available."""
    bot_functions_no_stop = {
        "irc": mock_irc,
        "log": mock_logger,
    }

    context = CommandContext(
        command="quit",
        args=["testpass123"],
        raw_message="!quit testpass123",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )

    with patch("commands_admin.get_config", return_value=mock_config):
        response = quit_command(context, bot_functions_no_stop)

    assert response == "❌ Cannot access shutdown mechanism"


def test_quit_command_irc_sends_quit_and_triggers_shutdown(mock_config, bot_functions):
    """Test quit command over IRC sends QUIT and triggers shutdown."""
    context = CommandContext(
        command="quit",
        args=["testpass123", "bye", "everyone"],
        raw_message="!quit testpass123 bye everyone",
        sender="admin",
        target="#test",
        is_private=False,
        is_console=False,
        server_name="testserver",
    )

    with patch("commands_admin.get_config", return_value=mock_config):
        response = quit_command(context, bot_functions)

    # Verify IRC QUIT was sent
    bot_functions["irc"].send_raw.assert_called_once_with("QUIT :bye everyone")

    # Verify shutdown was triggered
    bot_functions["stop_event"].set.assert_called_once()

    # Verify logging
    bot_functions["log"].assert_called_once_with(
        "Admin quit with message: bye everyone", "INFO"
    )

    # Should return no response for IRC quit
    assert response == ""


def test_quit_command_irc_no_connection(mock_config, mock_stop_event, mock_logger):
    """Test quit command when IRC connection is not available."""
    bot_functions_no_irc = {
        "stop_event": mock_stop_event,
        "log": mock_logger,
    }

    context = CommandContext(
        command="quit",
        args=["testpass123"],
        raw_message="!quit testpass123",
        sender="admin",
        target="#test",
        is_private=False,
        is_console=False,
        server_name="testserver",
    )

    with patch("commands_admin.get_config", return_value=mock_config):
        response = quit_command(context, bot_functions_no_irc)

    assert response == "❌ IRC connection not available"


def test_join_command_console(mock_config, bot_functions):
    """Test join command in console."""
    context = CommandContext(
        command="join",
        args=["testpass123", "#newchannel"],
        raw_message="!join testpass123 #newchannel",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )

    with patch("commands_admin.get_config", return_value=mock_config):
        response = join_command(context, bot_functions)

    assert response == "Admin command: JOIN #newchannel (no key)"


def test_join_command_console_with_key(mock_config, bot_functions):
    """Test join command in console with channel key."""
    context = CommandContext(
        command="join",
        args=["testpass123", "#private", "secretkey"],
        raw_message="!join testpass123 #private secretkey",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )

    with patch("commands_admin.get_config", return_value=mock_config):
        response = join_command(context, bot_functions)

    assert response == "Admin command: JOIN #private secretkey"


def test_join_command_irc(mock_config, bot_functions):
    """Test join command over IRC."""
    context = CommandContext(
        command="join",
        args=["testpass123", "#newchannel"],
        raw_message="!join testpass123 #newchannel",
        sender="admin",
        target="#test",
        is_private=False,
        is_console=False,
        server_name="testserver",
    )

    with patch("commands_admin.get_config", return_value=mock_config):
        response = join_command(context, bot_functions)

    bot_functions["irc"].send_raw.assert_called_once_with("JOIN #newchannel")
    bot_functions["log"].assert_called_once_with(
        "Admin joined channel #newchannel", "INFO"
    )
    assert response == "Joined #newchannel"


def test_join_command_irc_with_key(mock_config, bot_functions):
    """Test join command over IRC with channel key."""
    context = CommandContext(
        command="join",
        args=["testpass123", "#private", "secretkey"],
        raw_message="!join testpass123 #private secretkey",
        sender="admin",
        target="#test",
        is_private=False,
        is_console=False,
        server_name="testserver",
    )

    with patch("commands_admin.get_config", return_value=mock_config):
        response = join_command(context, bot_functions)

    bot_functions["irc"].send_raw.assert_called_once_with("JOIN #private secretkey")
    bot_functions["log"].assert_called_once_with(
        "Admin joined channel #private", "INFO"
    )
    assert response == "Joined #private"


def test_part_command_console(mock_config, bot_functions):
    """Test part command in console."""
    context = CommandContext(
        command="part",
        args=["testpass123", "#channel"],
        raw_message="!part testpass123 #channel",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )

    with patch("commands_admin.get_config", return_value=mock_config):
        response = part_command(context, bot_functions)

    assert response == "Admin command: PART #channel"


def test_part_command_irc(mock_config, bot_functions):
    """Test part command over IRC."""
    context = CommandContext(
        command="part",
        args=["testpass123", "#channel"],
        raw_message="!part testpass123 #channel",
        sender="admin",
        target="#test",
        is_private=False,
        is_console=False,
        server_name="testserver",
    )

    with patch("commands_admin.get_config", return_value=mock_config):
        response = part_command(context, bot_functions)

    bot_functions["irc"].send_raw.assert_called_once_with("PART #channel")
    bot_functions["log"].assert_called_once_with("Admin left channel #channel", "INFO")
    assert response == "Left #channel"


def test_nick_command_console(mock_config, bot_functions):
    """Test nick command in console."""
    context = CommandContext(
        command="nick",
        args=["testpass123", "newbot"],
        raw_message="!nick testpass123 newbot",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )

    with patch("commands_admin.get_config", return_value=mock_config):
        response = nick_command(context, bot_functions)

    assert response == "Admin command: NICK newbot"


def test_nick_command_irc(mock_config, bot_functions):
    """Test nick command over IRC."""
    context = CommandContext(
        command="nick",
        args=["testpass123", "newbot"],
        raw_message="!nick testpass123 newbot",
        sender="admin",
        target="#test",
        is_private=False,
        is_console=False,
        server_name="testserver",
    )

    with patch("commands_admin.get_config", return_value=mock_config):
        response = nick_command(context, bot_functions)

    bot_functions["irc"].send_raw.assert_called_once_with("NICK newbot")
    bot_functions["log"].assert_called_once_with("Admin changed nick to newbot", "INFO")
    assert response == "Changed nick to newbot"


def test_raw_command_irc(mock_config, bot_functions):
    """Test raw command over IRC."""
    context = CommandContext(
        command="raw",
        args=["testpass123", "MODE", "#channel", "+o", "user"],
        raw_message="!raw testpass123 MODE #channel +o user",
        sender="admin",
        target="#test",
        is_private=False,
        is_console=False,
        server_name="testserver",
    )

    with patch("commands_admin.get_config", return_value=mock_config):
        response = raw_command(context, bot_functions)

    bot_functions["irc"].send_raw.assert_called_once_with("MODE #channel +o user")
    bot_functions["log"].assert_called_once_with(
        "Admin sent raw command: MODE #channel +o user", "INFO"
    )
    assert response == "Sent: MODE #channel +o user"


@pytest.mark.parametrize(
    "command_name,args,command_func",
    [
        ("join", ["testpass123"], join_command),
        ("part", ["testpass123"], part_command),
        ("nick", ["testpass123"], nick_command),
        ("raw", ["testpass123"], raw_command),
    ],
)
def test_commands_require_args(command_name, args, command_func, mock_config, bot_functions):
    """Test that commands properly validate required arguments."""
    context = CommandContext(
        command=command_name,
        args=args,
        raw_message=f"!{command_name} {' '.join(args)}",
        sender="admin",
        target="#test",
        is_private=False,
        is_console=False,
        server_name="testserver",
    )

    with patch("commands_admin.get_config", return_value=mock_config):
        response = command_func(context, bot_functions)

    # All these commands should return error when missing required args
    assert "❌" in response or "Usage:" in response


def test_admin_commands_invalid_password(mock_config, bot_functions):
    """Test that all admin commands reject invalid passwords."""
    commands_and_funcs = [
        ("join", join_command),
        ("part", part_command),
        ("nick", nick_command),
        ("raw", raw_command),
        ("quit", quit_command),
    ]

    for command_name, command_func in commands_and_funcs:
        context = CommandContext(
            command=command_name,
            args=["wrongpass", "somearg"],
            raw_message=f"!{command_name} wrongpass somearg",
            sender="user",
            target="#test",
            is_private=False,
            is_console=False,
            server_name="testserver",
        )

        with patch("commands_admin.get_config", return_value=mock_config):
            response = command_func(context, bot_functions)

        assert response == "❌ Invalid admin password", f"Command {command_name} should reject invalid password"
