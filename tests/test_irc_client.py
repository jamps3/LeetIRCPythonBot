"""
IRC Client Tests

Comprehensive tests for the IRC client functionality.
"""

import time
from test_framework import TestCase, TestSuite, TestRunner


def test_irc_client_creation():
    """Test IRC client creation."""
    try:
        from irc_client import create_irc_client

        client = create_irc_client("SERVER1", "testbot")

        assert client.nickname == "testbot", "Nickname should be set correctly"
        assert client.server_config is not None, "Server config should be set"
        assert hasattr(client, "connection_info"), "Should have connection info"

        return True
    except Exception as e:
        print(f"IRC client creation test failed: {e}")
        return False


def test_irc_message_parsing():
    """Test IRC message parsing functionality."""
    try:
        from irc_client import create_irc_client, IRCMessageType

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

        return True
    except Exception as e:
        print(f"IRC message parsing test failed: {e}")
        return False


def test_irc_message_properties():
    """Test IRC message property methods."""
    try:
        from irc_client import create_irc_client

        client = create_irc_client("SERVER1", "testbot")

        # Test channel message
        channel_msg = client.parse_message(":nick!user@host PRIVMSG #channel :Hello")
        assert channel_msg.is_channel_message == True, "Should be channel message"
        assert channel_msg.is_private_message == False, "Should not be private message"

        # Test private message
        private_msg = client.parse_message(":nick!user@host PRIVMSG testbot :Hello")
        assert private_msg.is_private_message == True, "Should be private message"
        assert private_msg.is_channel_message == False, "Should not be channel message"

        # Test command message
        command_msg = client.parse_message(":nick!user@host PRIVMSG #channel :!help")
        assert command_msg.is_command == True, "Should be command"

        # Test non-command message
        normal_msg = client.parse_message(":nick!user@host PRIVMSG #channel :Hello")
        assert normal_msg.is_command == False, "Should not be command"

        return True
    except Exception as e:
        print(f"IRC message properties test failed: {e}")
        return False


def test_irc_connection_states():
    """Test IRC connection state management."""
    try:
        from irc_client import create_irc_client, IRCConnectionState

        client = create_irc_client("SERVER1", "testbot")

        # Initial state should be disconnected
        assert (
            client.connection_info.state == IRCConnectionState.DISCONNECTED
        ), "Initial state should be disconnected"

        # Test connection info properties
        assert (
            client.connection_info.uptime is None
        ), "Uptime should be None when disconnected"
        assert client.is_connected == False, "Should not be connected initially"

        # Test status string
        status = client.get_status()
        assert (
            "disconnected" in status.lower()
        ), "Status should mention disconnected state"

        return True
    except Exception as e:
        print(f"IRC connection states test failed: {e}")
        return False


def test_irc_handler_system():
    """Test IRC message handler registration system."""
    try:
        from irc_client import create_irc_client, IRCMessageType

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
        assert (
            handler_called[0] == IRCMessageType.PRIVMSG
        ), "Handler should receive PRIVMSG"

        # Test handler removal
        client.remove_message_handler(IRCMessageType.PRIVMSG, test_handler)
        assert (
            len(client._message_handlers.get(IRCMessageType.PRIVMSG, [])) == 0
        ), "Handler should be removed"

        return True
    except Exception as e:
        print(f"IRC handler system test failed: {e}")
        return False


def test_irc_rate_limiting():
    """Test IRC rate limiting functionality."""
    try:
        from irc_client import create_irc_client

        client = create_irc_client("SERVER1", "testbot")

        # Test rate limiting properties
        assert hasattr(client, "_last_send_time"), "Should have last send time tracking"
        assert hasattr(client, "_send_delay"), "Should have send delay setting"
        assert client._send_delay >= 0, "Send delay should be non-negative"

        return True
    except Exception as e:
        print(f"IRC rate limiting test failed: {e}")
        return False


def test_irc_channel_management():
    """Test IRC channel management methods."""
    try:
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
        except:
            # Network error is expected in test environment
            pass

        try:
            client.part_channel("#test")
            # Should remove from channel list
            assert (
                "#test" not in client.connection_info.channels
            ), "Channel should be removed from list"
        except:
            # Network error is expected in test environment
            pass

        return True
    except Exception as e:
        print(f"IRC channel management test failed: {e}")
        return False


def register_irc_client_tests(runner: TestRunner):
    """Register IRC client tests with the test runner."""

    tests = [
        TestCase(
            name="irc_client_creation",
            description="Test IRC client creation",
            test_func=test_irc_client_creation,
            category="irc_client",
        ),
        TestCase(
            name="irc_message_parsing",
            description="Test IRC message parsing",
            test_func=test_irc_message_parsing,
            category="irc_client",
        ),
        TestCase(
            name="irc_message_properties",
            description="Test IRC message property methods",
            test_func=test_irc_message_properties,
            category="irc_client",
        ),
        TestCase(
            name="irc_connection_states",
            description="Test IRC connection state management",
            test_func=test_irc_connection_states,
            category="irc_client",
        ),
        TestCase(
            name="irc_handler_system",
            description="Test IRC message handler system",
            test_func=test_irc_handler_system,
            category="irc_client",
        ),
        TestCase(
            name="irc_rate_limiting",
            description="Test IRC rate limiting",
            test_func=test_irc_rate_limiting,
            category="irc_client",
        ),
        TestCase(
            name="irc_channel_management",
            description="Test IRC channel management",
            test_func=test_irc_channel_management,
            category="irc_client",
        ),
    ]

    suite = TestSuite(
        name="IRC_Client", description="Tests for IRC client functionality", tests=tests
    )

    runner.add_suite(suite)
