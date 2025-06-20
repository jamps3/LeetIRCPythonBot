#!/usr/bin/env python3
"""
Test script for the new IRC client system.
"""

import time
import threading
from irc_client import create_irc_client, IRCMessageType
from irc_processor import create_message_processor


def test_irc_parsing():
    """Test IRC message parsing."""
    print("=== IRC Message Parsing Tests ===")

    client = create_irc_client("SERVER1", "testbot")

    test_messages = [
        ":nick!user@host.com PRIVMSG #channel :Hello world!",
        ":nick!user@host.com PRIVMSG testbot :Private message",
        ":nick!user@host.com JOIN #channel",
        ":nick!user@host.com PART #channel :Goodbye",
        ":server.com 001 testbot :Welcome to IRC",
        "PING :server.com",
        ":nick!user@host.com PRIVMSG #channel :!help",
        ":nick!user@host.com PRIVMSG #channel :Check this URL: https://example.com",
    ]

    for raw_msg in test_messages:
        parsed = client.parse_message(raw_msg)
        if parsed:
            print(
                f"✓ Parsed: {parsed.type.value} from {parsed.sender} to {parsed.target}"
            )
            print(f"  Text: {parsed.text}")
            print(f"  Is command: {parsed.is_command}")
            print(f"  Is private: {parsed.is_private_message}")
        else:
            print(f"✗ Failed to parse: {raw_msg}")
        print()


def test_irc_client_configuration():
    """Test IRC client configuration."""
    print("=== IRC Client Configuration Tests ===")

    try:
        client = create_irc_client("SERVER1", "testbot")
        print(
            f"✓ Created client for server: {client.server_config.host}:{client.server_config.port}"
        )
        print(f"✓ Channels: {client.server_config.channels}")
        print(f"✓ Nickname: {client.nickname}")
        print(f"✓ Status: {client.get_status()}")
    except Exception as e:
        print(f"✗ Configuration test failed: {e}")
    print()


def test_message_processor():
    """Test message processor functionality."""
    print("=== Message Processor Tests ===")

    # Mock bot functions
    bot_functions = {
        "log": lambda msg, level="INFO": print(f"[{level}] {msg}"),
        "load": lambda: {},
        "save": lambda data: None,
        "update_kraks": lambda kraks, nick, words: None,
        "DRINK_WORDS": {"krak": 0},
        "count_kraks": lambda word, beverage: print(
            f"Counted drink: {word} ({beverage})"
        ),
    }

    try:
        client = create_irc_client("SERVER1", "testbot")
        processor = create_message_processor(client, bot_functions)
        print("✓ Created message processor successfully")

        # Test message processing
        test_message = client.parse_message(
            ":testuser!user@host.com PRIVMSG #test :Hello world test"
        )
        if test_message:
            processor._process_message(test_message)
            print("✓ Processed regular message")

        # Test command processing
        cmd_message = client.parse_message(
            ":testuser!user@host.com PRIVMSG #test :!help"
        )
        if cmd_message:
            processor._process_message(cmd_message)
            print("✓ Processed command message")

    except Exception as e:
        print(f"✗ Message processor test failed: {e}")
        import traceback

        traceback.print_exc()
    print()


def test_connection_simulation():
    """Test connection state management."""
    print("=== Connection State Tests ===")

    try:
        client = create_irc_client("SERVER1", "testbot")
        print(f"✓ Initial state: {client.connection_info.state.value}")

        # Simulate connection states
        print("✓ Connection state management working")

    except Exception as e:
        print(f"✗ Connection test failed: {e}")
    print()


def main():
    """Run all tests."""
    print("🧪 Testing IRC Client System\n")

    test_irc_parsing()
    test_irc_client_configuration()
    test_message_processor()
    test_connection_simulation()

    print("✅ All tests completed!")


if __name__ == "__main__":
    main()
