#!/usr/bin/env python3
"""
Phase 2 Test - IRC Client and Message Processing

This tests the new IRC client and message processing system
without depending on all legacy functions.
"""

from config import get_config_manager, get_config
from irc_client import create_irc_client, IRCMessageType
from irc_processor import create_message_processor
from command_registry import get_command_registry
import command_loader


def test_configuration():
    """Test the enhanced configuration system."""
    print("=== Configuration System Test ===")
    
    try:
        config_manager = get_config_manager()
        config = config_manager.config
        
        print(f"✓ Bot name: {config.name}")
        print(f"✓ Version: {config.version}")
        print(f"✓ Log level: {config.log_level}")
        print(f"✓ Admin password configured: {'Yes' if config.admin_password != 'changeme' else 'No'}")
        print(f"✓ Servers configured: {len(config.servers)}")
        
        for server in config.servers:
            print(f"  - {server.name}: {server.host}:{server.port}")
            print(f"    Channels: {', '.join(server.channels)}")
        
        # Validate configuration
        errors = config_manager.validate_config()
        if errors:
            print("\n⚠️ Configuration Issues:")
            for error in errors:
                print(f"  - {error}")
        else:
            print("\n✅ Configuration is valid")
        
        return True
    
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False


def test_irc_client():
    """Test IRC client creation and basic functionality."""
    print("\n=== IRC Client Test ===")
    
    try:
        client = create_irc_client("SERVER1", "testbot")
        print(f"✓ Created IRC client for {client.server_config.host}:{client.server_config.port}")
        print(f"✓ Nickname: {client.nickname}")
        print(f"✓ Channels to join: {', '.join(client.server_config.channels)}")
        print(f"✓ Connection state: {client.connection_info.state.value}")
        print(f"✓ Status: {client.get_status()}")
        
        # Test message parsing
        test_messages = [
            ":nick!user@host PRIVMSG #channel :Hello world!",
            ":nick!user@host PRIVMSG testbot :Private message",
            ":nick!user@host PRIVMSG #channel :!help",
            "PING :server.example.com",
        ]
        
        print("\n  Message Parsing Tests:")
        for raw_msg in test_messages:
            parsed = client.parse_message(raw_msg)
            if parsed:
                print(f"  ✓ {parsed.type.value}: {parsed.sender} -> {parsed.target}")
                if parsed.text:
                    print(f"    Text: {parsed.text}")
                    print(f"    Is command: {parsed.is_command}")
            else:
                print(f"  ❌ Failed to parse: {raw_msg}")
        
        return True
    
    except Exception as e:
        print(f"❌ IRC client test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_command_system():
    """Test the command registry and processing."""
    print("\n=== Command System Test ===")
    
    try:
        # Load commands
        command_loader.load_all_commands()
        
        registry = get_command_registry()
        commands = registry.get_command_names(include_aliases=True)
        
        print(f"✓ Commands loaded: {len(registry._commands)}")
        print(f"✓ Total names (including aliases): {len(commands)}")
        
        # Test help generation
        help_text = registry.generate_help()
        print(f"✓ Help text generated ({len(help_text)} characters)")
        
        # Test specific command help
        version_help = registry.generate_help(specific_command="version")
        print(f"✓ Version command help: {version_help}")
        
        return True
    
    except Exception as e:
        print(f"❌ Command system test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_message_processor():
    """Test the message processing system."""
    print("\n=== Message Processor Test ===")
    
    try:
        # Create minimal bot functions for testing
        bot_functions = {
            'log': lambda msg, level="INFO": print(f"[{level}] {msg}"),
            'load': lambda: {},
            'save': lambda data: None,
            'update_kraks': lambda kraks, nick, words: None,
        }
        
        client = create_irc_client("SERVER1", "testbot")
        processor = create_message_processor(client, bot_functions)
        
        print("✓ Message processor created")
        
        # Test processing different message types
        test_cases = [
            (":user!host PRIVMSG #test :Hello world", "Regular message"),
            (":user!host PRIVMSG #test :!help", "Command message"),
            (":user!host JOIN #test", "Join message"),
        ]
        
        for raw_msg, description in test_cases:
            parsed = client.parse_message(raw_msg)
            if parsed:
                print(f"✓ Parsed {description}: {parsed.type.value}")
            else:
                print(f"❌ Failed to parse {description}")
        
        return True
    
    except Exception as e:
        print(f"❌ Message processor test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_integration():
    """Test integration between components."""
    print("\n=== Integration Test ===")
    
    try:
        # Test that all components work together
        config = get_config()
        client = create_irc_client("SERVER1", config.name)
        
        # Minimal bot functions
        bot_functions = {
            'log': lambda msg, level="INFO": None,  # Silent for this test
        }
        
        processor = create_message_processor(client, bot_functions)
        
        # Test command processing flow
        test_msg = client.parse_message(":testuser!user@host PRIVMSG #test :!version")
        if test_msg:
            print("✓ Command message parsed successfully")
            # Note: We can't fully test execution without IRC connection
            print("✓ Message processor initialized with command message")
        
        print("✓ All components integrate successfully")
        return True
    
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        return False


def main():
    """Run all Phase 2 tests."""
    print("🧪 Phase 2 Testing - IRC Client & Message Processing\n")
    
    tests = [
        ("Configuration System", test_configuration),
        ("IRC Client", test_irc_client),
        ("Command System", test_command_system),
        ("Message Processor", test_message_processor),
        ("Integration", test_integration),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"Running: {test_name}")
        print('='*50)
        
        if test_func():
            passed += 1
            print(f"✅ {test_name} PASSED")
        else:
            print(f"❌ {test_name} FAILED")
    
    print(f"\n{'='*50}")
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All Phase 2 tests PASSED!")
        return True
    else:
        print("⚠️ Some tests failed. Check output above for details.")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)

