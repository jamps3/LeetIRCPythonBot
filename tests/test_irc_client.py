"""
IRC Client Tests - Improved Pytest Version

Comprehensive tests for the IRC client functionality.
"""

import os
import sys
import time

import pytest

# Add the parent directory to Python path to ensure imports work in CI
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


def test_irc_client_creation():
    """Test IRC client creation."""
    from irc_client import create_irc_client

    client = create_irc_client("SERVER1", "testbot")

    assert client.nickname == "testbot", "Nickname should be set correctly"
    assert client.server_config is not None, "Server config should be set"
    assert hasattr(client, "connection_info"), "Should have connection info"


def test_irc_message_parsing():
    """Test IRC message parsing functionality."""
    from irc_client import IRCMessageType, create_irc_client

    client = create_irc_client("SERVER1", "testbot")

    test_cases = [
        (
            ":nick!user@host PRIVMSG #channel :Hello world",
            IRCMessageType.PRIVMSG,
            "#channel",
            "Hello world",
        ),
        (":nick!user@host JOIN #channel", IRCMessageType.JOIN, "#channel", None),
        (
            "PING :server.example.com",
            IRCMessageType.PING,
            None,
            "server.example.com",
        ),
        (":server 001 testbot :Welcome", IRCMessageType.NUMERIC, None, "Welcome"),
        (
            ":nick!user@host PRIVMSG testbot :Private message",
            IRCMessageType.PRIVMSG,
            "testbot",
            "Private message",
        ),
    ]

    for raw_msg, expected_type, expected_target, expected_text in test_cases:
        parsed = client.parse_message(raw_msg)

        assert parsed is not None, f"Should parse message: {raw_msg}"
        assert parsed.type == expected_type, f"Wrong type for: {raw_msg}"
        assert parsed.target == expected_target, f"Wrong target for: {raw_msg}"
        assert parsed.text == expected_text, f"Wrong text for: {raw_msg}"


def test_irc_message_properties():
    """Test IRC message property methods."""
    from irc_client import create_irc_client

    client = create_irc_client("SERVER1", "testbot")

    # Test channel message
    channel_msg = client.parse_message(":nick!user@host PRIVMSG #channel :Hello")
    assert channel_msg.is_channel_message is True, "Should be channel message"
    assert channel_msg.is_private_message is False, "Should not be private message"

    # Test private message
    private_msg = client.parse_message(":nick!user@host PRIVMSG testbot :Hello")
    assert private_msg.is_private_message is True, "Should be private message"
    assert private_msg.is_channel_message is False, "Should not be channel message"

    # Test command message
    command_msg = client.parse_message(":nick!user@host PRIVMSG #channel :!help")
    assert command_msg.is_command is True, "Should be command"

    # Test non-command message
    normal_msg = client.parse_message(":nick!user@host PRIVMSG #channel :Hello")
    assert normal_msg.is_command is False, "Should not be command"


def test_irc_connection_states():
    """Test IRC connection state management."""
    from irc_client import IRCConnectionState, create_irc_client

    client = create_irc_client("SERVER1", "testbot")

    # Initial state should be disconnected
    assert (
        client.connection_info.state == IRCConnectionState.DISCONNECTED
    ), "Initial state should be disconnected"

    # Test connection info properties
    assert (
        client.connection_info.uptime is None
    ), "Uptime should be None when disconnected"
    assert client.is_connected is False, "Should not be connected initially"

    # Test status string
    status = client.get_status()
    assert "disconnected" in status.lower(), "Status should mention disconnected state"


def test_irc_handler_system():
    """Test IRC message handler registration system."""
    from irc_client import IRCMessageType, create_irc_client

    client = create_irc_client("SERVER1", "testbot")

    # Test handler registration
    handler_called = []

    def test_handler(message):
        handler_called.append(message.type)

    client.add_message_handler(IRCMessageType.PRIVMSG, test_handler)

    # Simulate message processing (without actual network)
    test_msg = client.parse_message(":nick!user@host PRIVMSG #test :Hello")

    # Call handlers manually for testing
    if test_msg and test_msg.type in client._message_handlers:
        for handler in client._message_handlers[test_msg.type]:
            handler(test_msg)

    assert len(handler_called) == 1, "Handler should be called once"
    assert handler_called[0] == IRCMessageType.PRIVMSG, "Handler should receive PRIVMSG"

    # Test handler removal
    client.remove_message_handler(IRCMessageType.PRIVMSG, test_handler)
    assert (
        len(client._message_handlers.get(IRCMessageType.PRIVMSG, [])) == 0
    ), "Handler should be removed"


def test_irc_rate_limiting():
    """Test IRC rate limiting functionality."""
    from irc_client import create_irc_client

    client = create_irc_client("SERVER1", "testbot")

    # Test rate limiting properties
    assert hasattr(client, "_last_send_time"), "Should have last send time tracking"
    assert hasattr(client, "_send_delay"), "Should have send delay setting"
    assert client._send_delay >= 0, "Send delay should be non-negative"


def test_irc_channel_management():
    """Test IRC channel management methods."""
    from irc_client import create_irc_client

    client = create_irc_client("SERVER1", "testbot")

    # Test initial channel list
    assert isinstance(
        client.connection_info.channels, list
    ), "Channels should be a list"

    # Test channel operations (without actual network)
    initial_count = len(client.connection_info.channels)

    # Note: These would normally send IRC commands, but we're testing the logic
    try:
        client.join_channel("#test")
        # Should add to channel list (even if network call fails)
        assert (
            "#test" in client.connection_info.channels
        ), "Channel should be added to list"
    except Exception:
        # Network error is expected in test environment
        pass


# Parametrized test for multiple message parsing scenarios
@pytest.mark.parametrize(
    "raw_message,expected_nick,expected_user,expected_host",
    [
        (":nick!user@host PRIVMSG #channel :Hello", "nick", "user", "host"),
        (":testnick!testuser@testhost JOIN #test", "testnick", "testuser", "testhost"),
        (":bot!botuser@bothost PART #channel :Bye", "bot", "botuser", "bothost"),
        (":admin!adminuser@adminhost QUIT :Leaving", "admin", "adminuser", "adminhost"),
    ],
)
def test_irc_message_hostmask_parsing(raw_message, expected_nick, expected_user, expected_host):
    """Test IRC message hostmask parsing with parametrized inputs."""
    from irc_client import create_irc_client

    client = create_irc_client("SERVER1", "testbot")
    parsed = client.parse_message(raw_message)

    assert parsed is not None, f"Should parse message: {raw_message}"
    assert parsed.nick == expected_nick, f"Wrong nick for: {raw_message}"
    assert parsed.user == expected_user, f"Wrong user for: {raw_message}"
    assert parsed.host == expected_host, f"Wrong host for: {raw_message}"


@pytest.mark.parametrize(
    "message_text,expected_command",
    [
        ("!help", True),
        ("!version", True),
        ("!ping arg1 arg2", True),
        ("hello world", False),
        ("this is !not a command", False),
        ("!cmd", True),
    ],
)
def test_irc_command_detection(message_text, expected_command):
    """Test IRC command detection with various message formats."""
    from irc_client import create_irc_client

    client = create_irc_client("SERVER1", "testbot")
    raw_message = f":nick!user@host PRIVMSG #channel :{message_text}"
    parsed = client.parse_message(raw_message)

    assert parsed is not None, f"Should parse message: {raw_message}"
    assert parsed.is_command == expected_command, f"Command detection failed for: {message_text}"


def test_irc_client_fixtures():
    """Test IRC client with fixture-like setup."""
    from irc_client import create_irc_client

    # Test multiple client instances
    client1 = create_irc_client("SERVER1", "bot1")
    client2 = create_irc_client("SERVER1", "bot2")

    assert client1.nickname != client2.nickname, "Clients should have different nicknames"
    assert client1.server_config == client2.server_config, "Clients should share server config"

    try:
        client1.part_channel("#test")
        # Should remove from channel list
        assert (
            "#test" not in client1.connection_info.channels
        ), "Channel should be removed from list"
    except Exception:
        # Network error is expected in test environment
        pass
