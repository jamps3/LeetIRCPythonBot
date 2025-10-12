#!/usr/bin/env python3
"""
Pytest tests for Admin Commands

This module contains comprehensive tests for all admin commands including:
- quit command (console and IRC)
- join command
- part command
- nick command
- raw command
"""

import os
import sys
import threading
import time
from unittest.mock import MagicMock, Mock, call, patch

import pytest

from command_registry import CommandContext, CommandResponse
from commands_admin import (
    join_command,
    nick_command,
    openai_command,
    part_command,
    quit_command,
    raw_command,
    verify_admin_password,
)

# Mock dotenv to avoid dependency issues in environments where it's absent
sys.modules["dotenv"] = Mock()


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


@pytest.mark.parametrize(
    "command_func,args",
    [
        (join_command, ["testpass123", "#test"]),
        (part_command, ["testpass123", "#test"]),
        (nick_command, ["testpass123", "testnick"]),
        (raw_command, ["testpass123", "MODE", "#test", "+o", "user"]),
    ],
)
def test_other_commands_irc_no_connection(
    command_func, args, mock_config, mock_logger, mock_stop_event
):
    """Other admin commands should error when IRC connection is not available."""
    bot_functions_no_irc = {
        "stop_event": mock_stop_event,
        "log": mock_logger,
    }

    # Derive command name for context
    command_name = command_func.__name__.replace("_command", "")

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
        response = command_func(context, bot_functions_no_irc)

    assert "❌ IRC connection not available" in response


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
def test_commands_require_args(
    command_name, args, command_func, mock_config, bot_functions
):
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
        ("openai", openai_command),
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

        assert (
            response == "❌ Invalid admin password"
        ), f"Command {command_name} should reject invalid password"


# === COMPREHENSIVE CUSTOM QUIT MESSAGE TESTS ===


def test_bot_manager_quit_message_attribute():
    """Test that BotManager has quit_message attribute and set_quit_message method."""
    with patch("bot_manager.DataManager"), patch(
        "bot_manager.get_api_key", return_value=None
    ), patch("bot_manager.create_crypto_service", return_value=Mock()), patch(
        "bot_manager.create_nanoleet_detector", return_value=Mock()
    ), patch(
        "bot_manager.create_fmi_warning_service", return_value=Mock()
    ), patch(
        "bot_manager.create_otiedote_service", return_value=Mock()
    ), patch(
        "bot_manager.Lemmatizer", side_effect=Exception("Mock error")
    ):

        from bot_manager import BotManager

        bot_manager = BotManager("TestBot")

        # Test that quit_message attribute exists and has a value (either default or from env)
        assert hasattr(
            bot_manager, "quit_message"
        ), "BotManager should have quit_message attribute"
        # Quit message can be either the default or from QUIT_MESSAGE env var
        assert (
            bot_manager.quit_message is not None and len(bot_manager.quit_message) > 0
        ), f"quit_message should have a non-empty value, got '{bot_manager.quit_message}'"

        # Test that set_quit_message method exists and works
        assert hasattr(
            bot_manager, "set_quit_message"
        ), "BotManager should have set_quit_message method"
        assert callable(
            bot_manager.set_quit_message
        ), "set_quit_message should be callable"

        # Test setting custom quit message
        custom_message = "Custom farewell message"
        bot_manager.set_quit_message(custom_message)
        assert (
            bot_manager.quit_message == custom_message
        ), f"Expected quit_message to be '{custom_message}', got '{bot_manager.quit_message}'"


def test_server_quit_message_functionality():
    """Test that Server class accepts quit_message parameter and uses it."""
    with patch("server.get_logger", return_value=Mock()):
        from config import ServerConfig
        from server import Server

        # Mock server config
        config = Mock(spec=ServerConfig)
        config.name = "TestServer"
        config.host = "irc.example.com"
        config.port = 6667
        config.channels = ["#test"]
        config.keys = []
        config.tls = False

        # Create server instance
        stop_event = threading.Event()
        server = Server(config, "TestBot", stop_event)

        # Test that server has quit_message attribute
        assert hasattr(
            server, "quit_message"
        ), "Server should have quit_message attribute"
        assert (
            server.quit_message == "Disconnecting"
        ), f"Expected default quit_message 'Disconnecting', got '{server.quit_message}'"

        # Test that stop method accepts quit_message parameter
        custom_message = "Server shutdown with custom message"

        # Mock the socket and connection state
        server.connected = True
        mock_socket = Mock()
        server.socket = mock_socket

        # Call stop with custom quit message
        server.stop(quit_message=custom_message)

        # Verify that quit_message was set
        assert (
            server.quit_message == custom_message
        ), f"Expected quit_message to be '{custom_message}', got '{server.quit_message}'"

        # Verify that QUIT command was sent with custom message
        mock_socket.sendall.assert_called()
        call_args = mock_socket.sendall.call_args[0][0].decode("utf-8")
        assert (
            f"QUIT :{custom_message}" in call_args
        ), f"Expected 'QUIT :{custom_message}' in socket call, got '{call_args}'"


def test_console_bot_functions_has_set_quit_message():
    """Test that console bot functions includes set_quit_message function."""
    with patch("bot_manager.DataManager"), patch(
        "bot_manager.get_api_key", return_value=None
    ), patch("bot_manager.create_crypto_service", return_value=Mock()), patch(
        "bot_manager.create_nanoleet_detector", return_value=Mock()
    ), patch(
        "bot_manager.create_fmi_warning_service", return_value=Mock()
    ), patch(
        "bot_manager.create_otiedote_service", return_value=Mock()
    ), patch(
        "bot_manager.Lemmatizer", side_effect=Exception("Mock error")
    ):

        from bot_manager import BotManager

        bot_manager = BotManager("TestBot")

        # Get console bot functions
        bot_functions = bot_manager._create_console_bot_functions()

        # Test that set_quit_message is included
        assert (
            "set_quit_message" in bot_functions
        ), "Console bot functions should include set_quit_message"
        assert callable(
            bot_functions["set_quit_message"]
        ), "set_quit_message should be callable"

        # Test that it actually calls the BotManager's set_quit_message method
        test_message = "Test quit message from console"
        bot_functions["set_quit_message"](test_message)
        assert (
            bot_manager.quit_message == test_message
        ), f"Expected quit_message to be '{test_message}', got '{bot_manager.quit_message}'"


def test_legacy_quit_commands_use_set_quit_message():
    """Test that legacy quit commands in commands.py use set_quit_message."""
    # Mock bot functions with set_quit_message and stop_event
    quit_message_calls = []

    def mock_set_quit_message(message):
        quit_message_calls.append(message)

    stop_event_calls = []

    def mock_stop_event_set():
        stop_event_calls.append("set")

    stop_event = Mock()
    stop_event.set = mock_stop_event_set

    bot_functions = {
        "set_quit_message": mock_set_quit_message,
        "stop_event": stop_event,
        "notice_message": Mock(),
        "log": Mock(),
        "send_electricity_price": Mock(),
        "load_leet_winners": Mock(return_value={}),
        "send_weather": Mock(),
        "load": Mock(return_value={}),
        "fetch_title": Mock(),
        "handle_ipfs_command": Mock(),
    }

    # Test console quit command
    from command_loader import process_console_command

    with patch("commands_admin.verify_admin_password", return_value=True):
        process_console_command(
            "!quit testpass123 Goodbye from console!", bot_functions
        )

    # Verify that set_quit_message was called with correct message
    assert (
        len(quit_message_calls) == 1
    ), f"Expected 1 call to set_quit_message, got {len(quit_message_calls)}"
    assert (
        quit_message_calls[0] == "Goodbye from console!"
    ), f"Expected 'Goodbye from console!', got '{quit_message_calls[0]}'"

    # Verify that stop_event.set() was called
    assert (
        len(stop_event_calls) == 1
    ), f"Expected 1 call to stop_event.set(), got {len(stop_event_calls)}"


def test_irc_quit_command_integration():
    """Test IRC quit command sets custom message and triggers shutdown."""
    quit_message_calls = []

    def mock_set_quit_message(message):
        quit_message_calls.append(message)

    stop_event_calls = []

    def mock_stop_event_set():
        stop_event_calls.append("set")

    stop_event = Mock()
    stop_event.set = mock_stop_event_set

    # Mock IRC connection with modern send_raw
    irc_raw_calls = []

    def mock_send_raw(cmd):
        irc_raw_calls.append(cmd)

    irc = Mock()
    irc.send_raw = mock_send_raw
    irc.set_quit_message = mock_set_quit_message

    bot_functions = {
        "set_quit_message": mock_set_quit_message,
        "stop_event": stop_event,
        "notice_message": Mock(),
        "log": Mock(),
        "send_message": Mock(),
        "send_electricity_price": Mock(),
        "measure_latency": Mock(),
        "get_crypto_price": Mock(return_value="50000"),
        "load_leet_winners": Mock(return_value={}),
        "save_leet_winners": Mock(),
        "send_weather": Mock(),
        "send_scheduled_message": Mock(),
        "search_youtube": Mock(),
        "handle_ipfs_command": Mock(),
        "lookup": Mock(return_value="testserver"),
        "format_counts": Mock(),
        "chat_with_gpt": Mock(return_value="AI response"),
        "wrap_irc_message_utf8_bytes": Mock(return_value=["response"]),
        "fetch_title": Mock(),
        "lemmat": Mock(),
        "subscriptions": Mock(),
        "EKAVIKA_FILE": "test_ekavika.json",
        "bot_name": "TestBot",
        "latency_start": Mock(return_value=0),
        "set_latency_start": Mock(),
    }

    # Test IRC quit command processing using command registry
    from command_loader import process_irc_message

    # Create a mock IRC message for admin quit
    admin_quit_message = (
        ":admin!admin@host.com PRIVMSG #test :!quit testpass123 Farewell from IRC"
    )

    with patch("commands_admin.verify_admin_password", return_value=True):
        process_irc_message(irc, admin_quit_message, bot_functions)

    # Verify that set_quit_message was called
    assert (
        len(quit_message_calls) == 1
    ), f"Expected 1 call to set_quit_message, got {len(quit_message_calls)}"
    assert (
        quit_message_calls[0] == "Farewell from IRC"
    ), f"Expected 'Farewell from IRC', got '{quit_message_calls[0]}'"

    # Verify that IRC QUIT was sent via send_raw
    assert len(irc_raw_calls) == 1, f"Expected 1 IRC command, got {len(irc_raw_calls)}"
    assert (
        "QUIT :Farewell from IRC" in irc_raw_calls[0]
    ), f"Expected 'QUIT :Farewell from IRC' in '{irc_raw_calls[0]}'"

    # Verify that stop_event.set() was called for global shutdown
    assert (
        len(stop_event_calls) == 1
    ), f"Expected 1 call to stop_event.set(), got {len(stop_event_calls)}"


def test_quit_command_actually_stops_thread():
    """Integration test: verify quit command actually stops a running thread."""
    # Create a real threading.Event
    stop_event = threading.Event()

    # Create a worker thread that runs until stop_event is set
    def worker():
        while not stop_event.is_set():
            time.sleep(0.1)

    # Start the worker thread
    thread = threading.Thread(target=worker)
    thread.start()

    # Verify thread is running
    assert thread.is_alive()

    # Set up quit command with mock config and functions
    mock_config = Mock()
    mock_config.admin_password = "testpass123"

    bot_functions = {
        "stop_event": stop_event,
        "log": Mock(),
    }

    context = CommandContext(
        command="quit",
        args=["testpass123", "test shutdown"],
        raw_message="!quit testpass123 test shutdown",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )

    # Execute quit command
    with patch("commands_admin.get_config", return_value=mock_config):
        response = quit_command(context, bot_functions)

    # Verify response
    assert "🛑 Shutting down bot" in response
    assert "test shutdown" in response

    # Wait for thread to stop
    thread.join(timeout=2.0)

    # Verify thread has stopped
    assert not thread.is_alive()
    assert stop_event.is_set()


def test_quit_command_irc_without_send_raw_uses_notice(mock_config):
    """If irc lacks send_raw, quit_command should call notice_message and still shutdown."""

    # IRC object without send_raw
    class NoRawIRC:
        pass

    notice_calls = []

    def notice_collector(msg, *args, **kwargs):
        notice_calls.append(msg)

    bot_functions = {
        "irc": NoRawIRC(),
        "stop_event": Mock(),
        "log": Mock(),
        "notice_message": notice_collector,
    }

    context = CommandContext(
        command="quit",
        args=["testpass123", "fallback", "path"],
        raw_message="!quit testpass123 fallback path",
        sender="admin",
        target="#test",
        is_private=False,
        is_console=False,
        server_name="testserver",
    )

    with patch("commands_admin.get_config", return_value=mock_config):
        response = quit_command(context, bot_functions)

    # Notice should be called with the fallback message
    assert notice_calls and "Sending QUIT: fallback path" in notice_calls[0]
    # Shutdown should be triggered
    bot_functions["stop_event"].set.assert_called_once()
    # Function returns empty string for IRC path
    assert response == ""


def test_openai_command_no_setter(mock_config):
    """openai command returns error when setter not available."""
    context = CommandContext(
        command="openai",
        args=["testpass123", "gpt-5"],
        raw_message="!openai testpass123 gpt-5",
        sender="admin",
        target="#test",
        is_private=False,
        is_console=True,
        server_name="console",
    )

    bot_functions = {"log": Mock()}

    with patch("commands_admin.get_config", return_value=mock_config):
        result = openai_command(context, bot_functions)

    assert result == "❌ Cannot change model: setter not available"


def test_openai_command_console_returns_result(mock_config):
    """Console path should return the setter's result string."""
    context = CommandContext(
        command="openai",
        args=["testpass123", "gpt-5"],
        raw_message="!openai testpass123 gpt-5",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )

    bot_functions = {"set_openai_model": Mock(return_value="Model set to gpt-5")}

    with patch("commands_admin.get_config", return_value=mock_config):
        result = openai_command(context, bot_functions)

    assert result == "Model set to gpt-5"


def test_openai_command_irc_with_notice_returns_empty(mock_config):
    """IRC path with notice and irc present sends a notice and returns empty string."""
    context = CommandContext(
        command="openai",
        args=["testpass123", "gpt-5-mini"],
        raw_message="!openai testpass123 gpt-5-mini",
        sender="admin",
        target="#test",
        is_private=False,
        is_console=False,
        server_name="testserver",
    )

    irc = Mock()
    notice = Mock()
    bot_functions = {
        "set_openai_model": Mock(return_value="Model set to gpt-5-mini"),
        "notice_message": notice,
        "irc": irc,
    }

    with patch("commands_admin.get_config", return_value=mock_config):
        result = openai_command(context, bot_functions)

    notice.assert_called_once()
    # First arg is the message
    assert "Model set to gpt-5-mini" in notice.call_args[0][0]
    assert result == ""


def test_openai_command_irc_without_notice_returns_result(mock_config):
    """If notice not available, IRC path should return the result string."""
    context = CommandContext(
        command="openai",
        args=["testpass123", "gpt-5-large"],
        raw_message="!openai testpass123 gpt-5-large",
        sender="admin",
        target="#test",
        is_private=False,
        is_console=False,
        server_name="testserver",
    )

    bot_functions = {
        "set_openai_model": Mock(return_value="Model set to gpt-5-large"),
        "irc": Mock(),
    }

    with patch("commands_admin.get_config", return_value=mock_config):
        result = openai_command(context, bot_functions)

    assert result == "Model set to gpt-5-large"


def test_openai_command_missing_args_usage_error(mock_config):
    """openai command should validate required args."""
    context = CommandContext(
        command="openai",
        args=["testpass123"],
        raw_message="!openai testpass123",
        sender="admin",
        target="#test",
        is_private=False,
        is_console=False,
        server_name="testserver",
    )

    bot_functions = {"set_openai_model": Mock(return_value="OK")}

    with patch("commands_admin.get_config", return_value=mock_config):
        result = openai_command(context, bot_functions)

    assert "Usage" in result or result.startswith("❌")
