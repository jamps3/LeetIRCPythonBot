#!/usr/bin/env python3
"""
Comprehensive test to detect console command issues.

This test identifies missing service functions and integration problems
with console commands, particularly focusing on YouTube and other services.
"""

import os
import sys
import tempfile
from unittest.mock import MagicMock, Mock, patch

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_console_command_service_functions():
    """Test that console commands have all required service functions."""
    print("🧪 Testing console command service functions...")

    try:
        # Import required modules
        from console_manager import ConsoleManager
        from message_handler import MessageHandler
        from service_manager import ServiceManager
        from word_tracking import DataManager

        # Create test instances
        service_manager = ServiceManager()
        data_manager = DataManager()
        message_handler = MessageHandler(service_manager, data_manager)

        # Create console manager
        console_manager = ConsoleManager(service_manager, message_handler, None, None)

        # Set up mock server for testing
        class MockServer:
            def __init__(self):
                self.config = type("obj", (object,), {"name": "test_server"})
                self.bot_name = "test_bot"
                self.connected = True

            def send_message(self, target, message):
                print(
                    f"   📤 Would send to {target}: {message[:50]}{'...' if len(message) > 50 else ''}"
                )
                return True

        mock_server = MockServer()
        console_manager.active_server = "test_server"

        # Create a proper mock server manager with correct method signature
        class MockServerManager:
            def get_server(self, server_name):
                return mock_server if server_name == "test_server" else None

        console_manager.server_manager = MockServerManager()

        # Get console bot functions
        bot_functions = console_manager._create_console_bot_functions()

        # Required service functions that should be available
        required_functions = [
            "send_weather",
            "send_electricity_price",
            "get_crypto_price",
            "send_scheduled_message",
            "get_eurojackpot_numbers",
            "search_youtube",
            "handle_ipfs_command",
            "load_leet_winners",
            "save_leet_winners",
            "chat_with_gpt",
            "server",  # Critical: server parameter
        ]

        missing_functions = []
        for func_name in required_functions:
            if func_name not in bot_functions:
                missing_functions.append(func_name)

        if missing_functions:
            print(f"❌ Missing console service functions: {missing_functions}")
            return False
        else:
            print("✅ All required service functions present in console bot functions")

        # Test that server parameter is properly set
        server = bot_functions.get("server")
        if not server:
            print("❌ Server parameter missing from console bot functions")
            return False
        else:
            print(f"✅ Server parameter present: {type(server)}")

        # Test that search_youtube function exists and is callable
        search_youtube = bot_functions.get("search_youtube")
        if not search_youtube or not callable(search_youtube):
            print("❌ search_youtube function missing or not callable")
            return False
        else:
            print("✅ search_youtube function available")

        return True

    except Exception as e:
        print(f"❌ Error testing console service functions: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_youtube_command_console_routing():
    """Test YouTube command routing from console."""
    print("\n🧪 Testing YouTube command console routing...")

    try:
        from command_loader import process_console_command
        from console_manager import ConsoleManager
        from message_handler import MessageHandler
        from service_manager import ServiceManager
        from word_tracking import DataManager

        # Create test instances
        service_manager = ServiceManager()
        data_manager = DataManager()
        message_handler = MessageHandler(service_manager, data_manager)

        console_manager = ConsoleManager(service_manager, message_handler, None, None)

        # Set up mock server
        class MockServer:
            def __init__(self):
                self.config = type("obj", (object,), {"name": "test_server"})
                self.bot_name = "test_bot"
                self.connected = True

            def send_message(self, target, message):
                print(
                    f"   📤 YouTube result: {message[:100]}{'...' if len(message) > 100 else ''}"
                )
                return True

        mock_server = MockServer()
        console_manager.active_server = "test_server"
        console_manager.server_manager = type(
            "obj",
            (object,),
            {"get_server": lambda name: mock_server if name == "test_server" else None},
        )()

        # Create bot functions
        bot_functions = console_manager._create_console_bot_functions()

        # Test YouTube command processing
        responses = []

        def mock_notice(msg, irc=None, target=None):
            responses.append(msg)
            print(f"   📝 Console response: {msg}")

        bot_functions["notice_message"] = mock_notice
        bot_functions["log"] = lambda msg, level="INFO": None

        # Test YouTube command
        responses.clear()
        process_console_command("!youtube python tutorial", bot_functions)

        # Check if command was processed
        if responses:
            print("✅ YouTube command processed successfully")
            return True
        else:
            print("❌ YouTube command not processed - no responses generated")
            return False

    except Exception as e:
        print(f"❌ Error testing YouTube console routing: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_kaiku_command_console():
    """Test kaiku (echo) command from console."""
    print("\n🧪 Testing kaiku command from console...")

    try:
        from command_loader import process_console_command

        responses = []

        def mock_notice(msg, irc=None, target=None):
            responses.append(msg)
            print(f"   📝 Console response: {msg}")

        bot_functions = {
            "notice_message": mock_notice,
            "log": lambda msg, level="INFO": None,
        }

        # Test kaiku command
        responses.clear()
        process_console_command("!kaiku Hello World", bot_functions)

        if responses:
            print("✅ kaiku command processed successfully")
            return True
        else:
            print("❌ kaiku command not processed")
            return False

    except Exception as e:
        print(f"❌ Error testing kaiku command: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_weather_command_console():
    """Test weather command from console."""
    print("\n🧪 Testing weather command from console...")

    try:
        from command_loader import process_console_command

        responses = []

        def mock_notice(msg, irc=None, target=None):
            responses.append(msg)
            print(f"   📝 Console response: {msg}")

        # Mock weather service function
        def mock_send_weather(irc, target, location):
            mock_notice(f"Weather for {location}: Sunny, 20°C")

        bot_functions = {
            "notice_message": mock_notice,
            "log": lambda msg, level="INFO": None,
            "send_weather": mock_send_weather,
        }

        # Test weather command
        responses.clear()
        process_console_command("!s Helsinki", bot_functions)

        if responses:
            print("✅ Weather command processed successfully")
            return True
        else:
            print("❌ Weather command not processed")
            return False

    except Exception as e:
        print(f"❌ Error testing weather command: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_service_availability_console():
    """Test that services are available from console context."""
    print("\n🧪 Testing service availability from console...")

    try:
        from service_manager import ServiceManager

        service_manager = ServiceManager()

        # Check which services are available
        available_services = []
        for service_name in ["weather", "gpt", "electricity", "youtube", "crypto"]:
            service = service_manager.get_service(service_name)
            if service:
                available_services.append(service_name)

        print(f"   📊 Available services: {available_services}")

        # Check if YouTube service has API key
        youtube_service = service_manager.get_service("youtube")
        if youtube_service and youtube_service.api_key:
            print("✅ YouTube service available with API key")
        elif youtube_service:
            print("⚠️  YouTube service available but no API key")
        else:
            print("❌ YouTube service not available")

        return len(available_services) > 0

    except Exception as e:
        print(f"❌ Error testing service availability: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_console_command_error_handling():
    """Test console command error handling."""
    print("\n🧪 Testing console command error handling...")

    try:
        from command_loader import process_console_command

        responses = []
        errors_logged = []

        def mock_notice(msg, irc=None, target=None):
            responses.append(msg)
            print(f"   📝 Console response: {msg}")

        def mock_log(msg, level="INFO"):
            if level == "ERROR":
                errors_logged.append(msg)
                print(f"   ❌ Error logged: {msg}")

        # Test with broken service function
        def broken_service(*args):
            raise Exception("Service is broken")

        bot_functions = {
            "notice_message": mock_notice,
            "log": mock_log,
            "send_weather": broken_service,
        }

        # Test command that should fail gracefully
        responses.clear()
        errors_logged.clear()
        process_console_command("!s Helsinki", bot_functions)

        # Should handle error gracefully
        if errors_logged or responses:
            print("✅ Error handling works (errors logged or responses generated)")
            return True
        else:
            print("❌ No error handling - command failed silently")
            return False

    except Exception as e:
        print(f"❌ Error testing error handling: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_console_command_integration():
    """Test complete console command integration."""
    print("\n🧪 Testing complete console command integration...")

    try:
        from console_manager import ConsoleManager
        from message_handler import MessageHandler
        from service_manager import ServiceManager
        from word_tracking import DataManager

        # Create complete test setup
        service_manager = ServiceManager()
        data_manager = DataManager()
        message_handler = MessageHandler(service_manager, data_manager)

        console_manager = ConsoleManager(service_manager, message_handler, None, None)

        # Set up mock server
        class MockServer:
            def __init__(self):
                self.config = type("obj", (object,), {"name": "test_server"})
                self.bot_name = "test_bot"
                self.connected = True

            def send_message(self, target, message):
                print(
                    f"   📤 Message sent to {target}: {message[:50]}{'...' if len(message) > 50 else ''}"
                )
                return True

        mock_server = MockServer()
        console_manager.active_server = "test_server"
        console_manager.server_manager = type(
            "obj",
            (object,),
            {"get_server": lambda name: mock_server if name == "test_server" else None},
        )()

        # Create complete bot functions
        bot_functions = console_manager._create_console_bot_functions()

        # Add console-specific functions
        responses = []

        def mock_notice(msg, irc=None, target=None):
            responses.append(msg)
            print(f"   📝 Console response: {msg}")

        bot_functions["notice_message"] = mock_notice
        bot_functions["log"] = lambda msg, level="INFO": None

        # Test multiple commands
        test_commands = [
            "!version",
            "!ping",
            "!aika",
            "!kaiku Test message",
            "!help",
        ]

        success_count = 0
        for cmd in test_commands:
            responses.clear()
            try:
                from command_loader import process_console_command

                process_console_command(cmd, bot_functions)

                if responses:
                    print(f"   ✅ {cmd}: Success")
                    success_count += 1
                else:
                    print(f"   ❌ {cmd}: No response")
            except Exception as e:
                print(f"   ❌ {cmd}: Error - {e}")

        success_rate = success_count / len(test_commands)
        print(
            f"   📊 Success rate: {success_rate:.1%} ({success_count}/{len(test_commands)})"
        )

        return success_rate >= 0.8  # 80% success rate required

    except Exception as e:
        print(f"❌ Error testing console integration: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all console command issue detection tests."""
    print("🔍 Console Command Issue Detection Tests")
    print("=" * 50)

    tests = [
        ("Service Functions", test_console_command_service_functions),
        ("YouTube Command Routing", test_youtube_command_console_routing),
        ("Kaiku Command", test_kaiku_command_console),
        ("Weather Command", test_weather_command_console),
        ("Service Availability", test_service_availability_console),
        ("Error Handling", test_console_command_error_handling),
        ("Complete Integration", test_console_command_integration),
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\n📋 Running: {test_name}")
        print("-" * 30)
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test {test_name} failed with exception: {e}")
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)

    passed = 0
    failed = 0

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
        else:
            failed += 1

    total = len(results)
    print(f"\n📈 Results: {passed}/{total} tests passed ({passed/total:.1%})")

    if failed > 0:
        print(f"\n🚨 {failed} test(s) failed! Console commands need fixing.")
        print("\n🔧 Key issues identified:")
        for test_name, result in results:
            if not result:
                print(f"   - {test_name}")
    else:
        print("\n🎉 All tests passed! Console commands are working correctly.")

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)


def test_youtube_service_direct():
    """Test YouTube service directly via ServiceManager."""
    print("\n🧪 Testing YouTube service directly...")

    try:
        from config import load_env_file
        from service_manager import ServiceManager

        # Load environment
        load_env_file()

        # Create service manager
        service_manager = ServiceManager()

        # Check if YouTube service is available
        youtube_service = service_manager.get_service("youtube")
        print(f"   YouTube service available: {youtube_service is not None}")

        if youtube_service:
            print(f"   YouTube service type: {type(youtube_service)}")
            print(
                f'   YouTube service has api_key: {hasattr(youtube_service, "api_key")}'
            )
            if hasattr(youtube_service, "api_key") and youtube_service.api_key:
                print(f"   YouTube API key: {youtube_service.api_key[:10]}...")

                # Test the search function directly
                try:
                    result = youtube_service.search_videos(
                        "python tutorial", max_results=1
                    )
                    print(
                        f"   Search result: {result[:100]}..."
                        if result
                        else "   No results"
                    )
                    return True
                except Exception as e:
                    print(f"   Search error: {e}")
                    return False
            else:
                print("   No API key configured")
                return False
        else:
            return False

    except Exception as e:
        print(f"❌ Error testing YouTube service: {e}")
        import traceback

        traceback.print_exc()
        return False
