#!/usr/bin/env python3
"""
Test script for the new command system.
"""

import asyncio
from command_registry import get_command_registry, CommandContext, process_command_message
import command_loader  # This loads all commands


async def test_commands():
    """Test various commands in the new system."""
    registry = get_command_registry()
    
    print("=== Command Registry Test ===")
    print(f"Total commands registered: {len(registry._commands)}")
    
    # List all commands
    print("\nRegistered commands:")
    for name, handler in registry._commands.items():
        info = handler.info
        print(f"  • {name} - {info.description}")
        if info.aliases:
            print(f"    Aliases: {', '.join(info.aliases)}")
    
    print("\n=== Command Execution Tests ===")
    
    # Test basic commands
    test_cases = [
        ("!help", "Console help command"),
        ("!version", "Version command"),  
        ("!aika", "Time command"),
        ("!ping", "Ping command"),
        ("!kaiku Hello World", "Echo command"),
        ("!about", "About command"),
        ("!nosuchcommand", "Non-existent command")
    ]
    
    # Mock bot functions for testing
    bot_functions = {
        'log': lambda msg, level="INFO": print(f"[{level}] {msg}"),
        'notice_message': lambda msg: print(f"OUTPUT: {msg}"),
    }
    
    for command_text, description in test_cases:
        print(f"\nTesting: {command_text} ({description})")
        
        # Create console context
        context = CommandContext(
            command="",
            args=[],
            raw_message=command_text,
            sender=None,
            target=None,
            is_console=True,
            server_name="test"
        )
        
        try:
            response = await process_command_message(command_text, context, bot_functions)
            if response:
                if response.should_respond and response.message:
                    print(f"  Response: {response.message}")
                else:
                    print("  (No response message)")
            else:
                print("  (No command found)")
        except Exception as e:
            print(f"  ERROR: {e}")
    
    print("\n=== Admin Command Tests ===")
    
    # Test admin commands (should fail without password)
    admin_test_cases = [
        ("!join", "Join without password"),
        ("!join wrongpass #test", "Join with wrong password"),
        ("!nick wrongpass newbot", "Nick with wrong password"),
    ]
    
    for command_text, description in admin_test_cases:
        print(f"\nTesting: {command_text} ({description})")
        
        context = CommandContext(
            command="",
            args=[],
            raw_message=command_text,
            sender="testuser",
            target="#test",
            is_console=False,
            server_name="test"
        )
        
        try:
            response = await process_command_message(command_text, context, bot_functions)
            if response:
                if response.should_respond and response.message:
                    print(f"  Response: {response.message}")
                else:
                    print("  (No response message)")
            else:
                print("  (No command found)")
        except Exception as e:
            print(f"  ERROR: {e}")


if __name__ == "__main__":
    asyncio.run(test_commands())

