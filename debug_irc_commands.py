#!/usr/bin/env python3
"""
Demo script showing the new IRC command system with / prefix support
"""

from command_loader import load_all_commands
from command_registry import CommandContext, get_command_registry


def demo_irc_commands():
    """Demonstrate the IRC command system."""
    print("🚀 Loading IRC command system...")

    # Load all commands
    load_all_commands()
    registry = get_command_registry()

    print(f"✅ Loaded {len(registry._commands)} total commands")

    # Get IRC commands
    irc_commands = [
        name
        for name in registry._commands.keys()
        if name
        in [
            "join",
            "part",
            "quit",
            "nick",
            "msg",
            "notice",
            "away",
            "whois",
            "list",
            "invite",
            "kick",
            "topic",
            "mode",
            "names",
            "ircping",
            "irctime",
            "ircversion",
            "ircadmin",
            "motd",
            "raw",
        ]
    ]

    print(f"\n📋 Available IRC commands ({len(irc_commands)}):")
    for cmd in sorted(irc_commands):
        cmd_info = registry._commands[cmd].info
        print(f"  /{cmd:<12} - {cmd_info.description}")

    print("\n🧪 Testing IRC command execution...")

    # Mock bot functions (minimal for testing)
    bot_functions = {
        "bot_manager": None,  # In real use, this would be the actual BotManager
        "log": lambda msg, level="INFO": print(f"  LOG [{level}]: {msg}"),
    }

    # Test commands that don't require IRC connection for basic functionality
    test_cases = [
        ("/join #test", "join", ["#test"]),
        ("/part #test goodbye", "part", ["#test", "goodbye"]),
        ("/nick BotNick", "nick", ["BotNick"]),
        ("/msg Alice Hello there!", "msg", ["Alice", "Hello", "there!"]),
        ("/quit Goodbye all!", "quit", ["Goodbye", "all!"]),
    ]

    for raw_message, command, args in test_cases:
        print(f"\n  Testing: {raw_message}")

        context = CommandContext(
            command=command,
            args=args,
            raw_message=raw_message,
            sender=None,
            target=None,
            is_private=False,
            is_console=True,
            server_name="console",
        )

        handler = registry.get_handler(command)
        if handler:
            try:
                response = handler.func(context, bot_functions)
                print(f"    Response: {response}")
            except Exception as e:
                print(f"    Expected error (no IRC connection): {e}")
        else:
            print(f"    ❌ Command not found: {command}")

    print("\n🎯 Command prefix parsing test:")
    from command_registry import parse_command_message

    test_messages = [
        "!help",
        "/join #test",
        "!version",
        "/quit goodbye",
        "/msg Alice hi",
        "regular message (not a command)",
    ]

    for msg in test_messages:
        result = parse_command_message(msg)
        if result[0]:
            print(f"  '{msg}' -> Command: {result[0]}, Args: {result[1]}")
        else:
            print(f"  '{msg}' -> Not a command")

    print("\n✅ IRC command system demo complete!")
    print(f"   • {len(irc_commands)} IRC commands available with / prefix")
    print("   • Both ! and / prefixes supported")
    print("   • Commands work in console, TUI, and IRC contexts")
    print("   • Error handling for missing IRC connections")


if __name__ == "__main__":
    demo_irc_commands()
