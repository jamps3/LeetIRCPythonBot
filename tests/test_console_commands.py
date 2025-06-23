#!/usr/bin/env python3
"""
Console Commands Test Suite

Tests for console command functionality, including command processing,
bot manager integration, and command responses.
"""

import os
import sys
from unittest.mock import MagicMock, Mock

# Add the parent directory to sys.path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

from test_framework import TestCase, TestSuite

# Load environment variables for testing
load_dotenv()


def test_console_command_processing():
    """Test basic console command processing."""
    try:
        from command_loader import enhanced_process_console_command

        # Create minimal bot_functions for testing
        responses = []

        def mock_notice(msg, irc=None, target=None):
            responses.append(msg)

        def mock_log(msg, level="INFO"):
            pass  # Silent logging for tests

        bot_functions = {
            "notice_message": mock_notice,
            "log": mock_log,
            "send_weather": lambda *args: mock_notice("Weather service called"),
            "send_electricity_price": lambda *args: mock_notice(
                "Electricity service called"
            ),
            "load_leet_winners": lambda: {},
            "send_scheduled_message": lambda *args: None,
            "load": lambda: {},
            "fetch_title": lambda *args: None,
            "handle_ipfs_command": lambda *args: None,
            "chat_with_gpt": lambda msg: f"AI: {msg}",
            "wrap_irc_message_utf8_bytes": lambda msg, **kwargs: [msg],
            "get_crypto_price": lambda coin, currency="eur": "1000",
            "BOT_VERSION": "2.0.0",
        }

        # Test version command
        responses.clear()
        enhanced_process_console_command("!version", bot_functions)

        # Should have gotten a version response
        if not any("2.0.0" in str(response) for response in responses):
            return False

        return True

    except Exception as e:
        print(f"Console command processing test failed: {e}")
        return False


def test_console_weather_command():
    """Test console weather command processing."""
    try:
        from command_loader import enhanced_process_console_command

        responses = []

        def mock_notice(msg, irc=None, target=None):
            responses.append(msg)

        bot_functions = {
            "notice_message": mock_notice,
            "log": lambda msg, level="INFO": None,
            "send_weather": lambda irc, target, location: mock_notice(
                f"Weather for {location}: Sunny, 20°C"
            ),
            "BOT_VERSION": "2.0.0",
        }

        # Test weather command
        responses.clear()
        enhanced_process_console_command("!s Helsinki", bot_functions)

        # Should have gotten weather response
        if not any("Helsinki" in str(response) for response in responses):
            return False

        return True

    except Exception as e:
        print(f"Console weather command test failed: {e}")
        return False


def test_console_help_command():
    """Test console help command."""
    try:
        from command_loader import enhanced_process_console_command

        responses = []

        def mock_notice(msg, irc=None, target=None):
            responses.append(msg)

        bot_functions = {
            "notice_message": mock_notice,
            "log": lambda msg, level="INFO": None,
            "BOT_VERSION": "2.0.0",
        }

        # Test help command
        responses.clear()
        enhanced_process_console_command("!help", bot_functions)

        # Should have gotten help response
        if not any("command" in str(response).lower() for response in responses):
            return False

        return True

    except Exception as e:
        print(f"Console help command test failed: {e}")
        return False


def test_bot_manager_console_integration():
    """Test BotManager console integration."""
    try:
        import os
        import sys
        from io import StringIO

        # Capture stdout/stderr to avoid encoding issues during testing
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = StringIO()
        sys.stderr = StringIO()

        try:
            from bot_manager import BotManager

            # Create bot manager
            bot_manager = BotManager("TestBot")

            # Check if console listener method exists
            if not hasattr(bot_manager, "_listen_for_console_commands"):
                return False

            # Check if console bot functions method exists
            if not hasattr(bot_manager, "_create_console_bot_functions"):
                return False

            # Test console bot functions creation
            bot_functions = bot_manager._create_console_bot_functions()

            required_functions = [
                "notice_message",
                "log",
                "send_weather",
                "send_electricity_price",
                "get_crypto_price",
            ]

            for func_name in required_functions:
                if func_name not in bot_functions:
                    return False

            return True

        finally:
            # Always restore stdout/stderr
            sys.stdout = old_stdout
            sys.stderr = old_stderr

    except Exception as e:
        print(f"BotManager console integration test failed: {e}")
        return False


def test_console_command_with_services():
    """Test console commands with actual services."""
    try:
        # Create working bot_functions with services
        responses = []

        def mock_notice(msg, irc=None, target=None):
            responses.append(msg)

        def mock_log(msg, level="INFO"):
            if level != "DEBUG":  # Reduce noise
                pass

        # Mock service functions
        def mock_send_weather(irc, target, location):
            mock_notice(f"Weather for {location}: Sunny, 20°C")

        def mock_send_electricity(irc, target, args):
            mock_notice("Current electricity price: 5.2 snt/kWh")

        bot_functions = {
            "notice_message": mock_notice,
            "log": mock_log,
            "send_weather": mock_send_weather,
            "send_electricity_price": mock_send_electricity,
            "get_crypto_price": lambda coin, currency="eur": "50000",
            "load": lambda: {},
            "BOT_VERSION": "2.0.0",
        }

        from command_loader import enhanced_process_console_command

        # Test multiple commands
        test_commands = [
            "!version",
            "!ping",
            "!aika",
            "!s Helsinki",
            "!kaiku Hello World",
            "!about",
        ]

        for cmd in test_commands:
            responses.clear()
            enhanced_process_console_command(cmd, bot_functions)

            # Each command should generate at least one response
            if not responses:
                print(f"No response for command: {cmd}")
                return False

        return True

    except Exception as e:
        print(f"Console commands with services test failed: {e}")
        return False


def test_legacy_console_commands():
    """Test legacy console command system."""
    try:
        import commands

        responses = []

        def mock_notice(msg, irc=None, target=None):
            responses.append(msg)

        # Mock services for legacy system
        def mock_send_weather(irc, channel, location):
            responses.append(f"Weather for {location}: Test data")

        def mock_send_crypto_price(irc, channel, parts):
            if isinstance(parts, list) and len(parts) > 1:
                coin = parts[1]
                responses.append(f"The current price of {coin.capitalize()} is 1000 €.")

        def mock_send_electricity_price(irc, channel, parts):
            responses.append("Electricity price: 5.2 snt/kWh")

        bot_functions = {
            "notice_message": mock_notice,
            "send_weather": mock_send_weather,
            "send_crypto_price": mock_send_crypto_price,
            "send_electricity_price": mock_send_electricity_price,
            "get_crypto_price": lambda coin, currency="eur": "1000",
            "load_leet_winners": lambda: {},
            "send_scheduled_message": lambda *args: None,
            "load": lambda: {},
            "log": lambda msg, level="INFO": None,
            "fetch_title": lambda *args: None,
            "handle_ipfs_command": lambda *args: None,
            "chat_with_gpt": lambda msg: f"Mock AI response to: {msg}",
            "wrap_irc_message_utf8_bytes": lambda msg, **kwargs: [msg],
        }

        # Test legacy commands
        test_commands = ["!s Joensuu", "!crypto btc eur", "!sahko", "!help", "!version"]

        for cmd in test_commands:
            responses.clear()
            commands.process_console_command(cmd, bot_functions)

            # Each command should generate responses
            if not responses:
                print(f"No response for legacy command: {cmd}")
                return False

        return True

    except Exception as e:
        print(f"Legacy console commands test failed: {e}")
        return False


def test_console_error_handling():
    """Test console command error handling."""
    try:
        from command_loader import enhanced_process_console_command

        errors_logged = []

        def mock_log(msg, level="INFO"):
            if level == "ERROR":
                errors_logged.append(msg)

        responses = []

        def mock_notice(msg, irc=None, target=None):
            responses.append(msg)

        # Create bot_functions with some broken services
        def broken_weather(*args):
            raise Exception("Weather service broken")

        bot_functions = {
            "notice_message": mock_notice,
            "log": mock_log,
            "send_weather": broken_weather,
            "BOT_VERSION": "2.0.0",
        }

        # Test command that should fail gracefully
        responses.clear()
        errors_logged.clear()
        enhanced_process_console_command("!s Helsinki", bot_functions)

        # Should have handled the error gracefully
        # Either by logging error or providing error response
        if not errors_logged and not any("error" in str(r).lower() for r in responses):
            # No error handling detected
            return False

        return True

    except Exception as e:
        print(f"Console error handling test failed: {e}")
        return False


def register_console_command_tests(runner):
    """Register console command tests with the test framework."""
    tests = [
        TestCase(
            name="console_command_processing",
            description="Test basic console command processing",
            test_func=test_console_command_processing,
            category="console",
        ),
        TestCase(
            name="console_weather_command",
            description="Test console weather command",
            test_func=test_console_weather_command,
            category="console",
        ),
        TestCase(
            name="console_help_command",
            description="Test console help command",
            test_func=test_console_help_command,
            category="console",
        ),
        TestCase(
            name="bot_manager_console_integration",
            description="Test BotManager console integration",
            test_func=test_bot_manager_console_integration,
            category="console",
        ),
        TestCase(
            name="console_commands_with_services",
            description="Test console commands with services",
            test_func=test_console_command_with_services,
            category="console",
        ),
        TestCase(
            name="legacy_console_commands",
            description="Test legacy console command system",
            test_func=test_legacy_console_commands,
            category="console",
        ),
        TestCase(
            name="console_error_handling",
            description="Test console command error handling",
            test_func=test_console_error_handling,
            category="console",
        ),
    ]

    suite = TestSuite(
        name="Console_Commands",
        description="Tests for console command functionality and integration",
        tests=tests,
    )

    runner.add_suite(suite)


# For standalone testing
if __name__ == "__main__":
    from test_framework import TestRunner

    runner = TestRunner(verbose=True)
    register_console_command_tests(runner)
    success = runner.run_all()

    print(f"\nConsole commands tests: {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1)
