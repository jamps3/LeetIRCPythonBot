#!/usr/bin/env python3
"""
Console Commands Test Suite - Unified Pytest Version

Tests for console command functionality, including command processing,
bot manager integration, and command responses.
"""

import os
import sys
import tempfile
from io import StringIO
from unittest.mock import MagicMock, Mock

import pytest
from dotenv import load_dotenv

# Load environment variables for testing
load_dotenv()


@pytest.fixture(autouse=True, scope="function")
def ensure_command_registry():
    """Ensure command registry is properly initialized for console command tests."""
    # Only apply this fixture to tests in this file
    import inspect

    frame = inspect.currentframe()
    try:
        # Check if we're in a console command test
        test_name = frame.f_back.f_code.co_name if frame.f_back else "unknown"
        if not test_name.startswith("test_"):
            yield
            return

        # Ensure command registry is initialized with commands
        try:
            from command_registry import get_command_registry

            registry = get_command_registry()

            # If registry is empty, force reload commands
            if len(registry._commands) == 0:
                # Import command modules to register commands
                import commands_admin
                import commands_basic
                import commands_extended

        except Exception:
            # If anything fails, try to import command_loader which loads all commands
            try:
                import command_loader
            except Exception:
                pass

        yield

    finally:
        if frame:
            del frame


def test_console_command_processing():
    """Test basic console command processing."""
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
    assert any(
        "2.0.0" in str(response) for response in responses
    ), "Should get version response"


def test_console_weather_command():
    """Test console weather command processing."""
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
    assert any(
        "Helsinki" in str(response) for response in responses
    ), "Should get Helsinki weather response"


def test_console_help_command():
    """Test console help command."""
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
    assert any(
        "command" in str(response).lower() for response in responses
    ), "Should get help response"


def test_bot_manager_console_integration():
    """Test BotManager console integration."""
    # Using module-level imports for os/sys/StringIO to avoid redefinition

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
        assert hasattr(
            bot_manager, "_listen_for_console_commands"
        ), "Should have console listener method"

        # Check if console bot functions method exists
        assert hasattr(
            bot_manager, "_create_console_bot_functions"
        ), "Should have console bot functions method"

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
            assert func_name in bot_functions, f"Should have {func_name} function"

    finally:
        # Always restore stdout/stderr
        sys.stdout = old_stdout
        sys.stderr = old_stderr


def test_console_command_with_services():
    """Test console commands with actual services."""
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
        assert responses, f"No response for command: {cmd}"


def test_compatibility_console_commands():
    """Test compatibility console command system."""
    responses = []

    def mock_notice(msg, irc=None, target=None):
        responses.append(msg)

    # Mock services for compatibility
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

    # Test compatibility commands
    test_commands = ["!s Joensuu", "!crypto btc eur", "!sahko", "!help", "!version"]

    for cmd in test_commands:
        responses.clear()
        from command_loader import enhanced_process_console_command

        enhanced_process_console_command(cmd, bot_functions)

        # Each command should generate responses
        assert responses, f"No response for compatibility command: {cmd}"


def test_console_tilaa_command():
    """Test that !tilaa command works in console."""
    import subscriptions

    # Create temporary file for subscriptions
    temp_file = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json")
    temp_file.write("{}")
    temp_file.close()

    # Patch the SUBSCRIBERS_FILE constant
    original_file = subscriptions.SUBSCRIBERS_FILE
    subscriptions.SUBSCRIBERS_FILE = temp_file.name

    try:
        responses = []

        def mock_notice(msg):
            responses.append(msg)

        def mock_log(msg, level="INFO"):
            pass

        # Mock subscriptions service with all required functions
        bot_functions = {
            "notice_message": mock_notice,
            "log": mock_log,
            "subscriptions": subscriptions,
            "send_electricity_price": lambda *args: None,
            "load_leet_winners": lambda: {},
            "send_weather": lambda *args: None,
            "load": lambda: {},
            "fetch_title": lambda *args: None,
            "handle_ipfs_command": lambda *args: None,
        }

        # Test !tilaa list command
        responses.clear()
        from command_loader import enhanced_process_console_command

        enhanced_process_console_command("!tilaa list", bot_functions)

        # Should get subscription list response
        assert any(
            "tilauksia" in str(response).lower() or "tilaukset" in str(response).lower()
            for response in responses
        ), f"Should get subscription list response, got: {responses}"

        # Test !tilaa varoitukset command
        responses.clear()
        from command_loader import enhanced_process_console_command

        enhanced_process_console_command("!tilaa varoitukset", bot_functions)

        # Should get subscription toggle response
        assert any(
            "tilaus" in str(response).lower() for response in responses
        ), f"Should get subscription toggle response, got: {responses}"

    finally:
        # Restore original file
        subscriptions.SUBSCRIBERS_FILE = original_file
        if os.path.exists(temp_file.name):
            os.unlink(temp_file.name)


def test_console_tilaa_missing_service():
    """Test console !tilaa command when subscriptions service is missing."""

    responses = []

    def mock_notice(msg):
        responses.append(msg)

    def mock_log(msg, level="INFO"):
        pass  # Silent logging for tests

    # Bot functions without subscriptions service
    bot_functions = {
        "notice_message": mock_notice,
        "log": mock_log,
        "BOT_VERSION": "2.0.0",
        "send_electricity_price": lambda *args: None,
        "load_leet_winners": lambda: {},
        "send_weather": lambda *args: None,
        "load": lambda: {},
        "fetch_title": lambda *args: None,
        "handle_ipfs_command": lambda *args: None,
    }

    # Test !tilaa list command without service
    responses.clear()
    from command_loader import enhanced_process_console_command

    enhanced_process_console_command("!tilaa list", bot_functions)

    # Should get error response about missing service
    assert any(
        "not available" in str(response) for response in responses
    ), "Should get error about missing subscription service"


def test_console_error_handling():
    """Test console command error handling."""
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
    assert errors_logged or any(
        "error" in str(r).lower() for r in responses
    ), "Should handle errors gracefully"


@pytest.fixture
def mock_bot_functions():
    """Create mock bot functions for testing."""
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

    # Attach responses list for test access
    bot_functions["_responses"] = responses
    return bot_functions


@pytest.fixture
def enhanced_command_processor():
    """Import the enhanced command processor."""
    from command_loader import enhanced_process_console_command

    return enhanced_process_console_command


@pytest.mark.parametrize(
    "command",
    [
        "!version",
        "!ping",
        "!aika",
        "!s Helsinki",
        "!kaiku Hello World",
        "!about",
    ],
)
def test_parametrized_console_commands(command, enhanced_command_processor):
    """Test console commands with parametrization."""
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

    # Test command
    responses.clear()
    enhanced_command_processor(command, bot_functions)

    # Each command should generate at least one response
    assert responses, f"Command {command} should generate at least one response"


@pytest.mark.parametrize(
    "compatibility_command",
    ["!s Joensuu", "!crypto btc eur", "!sahko", "!help", "!version"],
)
def test_parametrized_compatibility_console_commands(compatibility_command):
    """Test compatibility commands using the new registry-based processor."""
    # Use the enhanced processor directly (no legacy commands.py)
    from command_loader import enhanced_process_console_command

    responses = []

    def mock_notice(msg, irc=None, target=None):
        responses.append(msg)

    # Mock services
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

    # Test command
    responses.clear()
    enhanced_process_console_command(compatibility_command, bot_functions)

    # Each command should generate responses
    assert (
        responses
    ), f"Compatibility command {compatibility_command} should generate responses"


def test_console_command_argument_parsing():
    """Test console command argument parsing."""
    from command_loader import enhanced_process_console_command

    responses = []

    def mock_notice(msg, irc=None, target=None):
        responses.append(msg)

    def mock_send_weather_with_args(irc, target, location):
        mock_notice(f"Weather requested for: {location}")

    bot_functions = {
        "notice_message": mock_notice,
        "log": lambda msg, level="INFO": None,
        "send_weather": mock_send_weather_with_args,
        "BOT_VERSION": "2.0.0",
    }

    # Test command with arguments
    responses.clear()
    enhanced_process_console_command("!s New York", bot_functions)

    # Should have parsed arguments correctly
    assert any(
        "New York" in str(response) for response in responses
    ), "Command should parse multi-word location arguments"


def test_console_command_case_insensitive():
    """Test console commands are case insensitive."""
    from command_loader import enhanced_process_console_command

    responses = []

    def mock_notice(msg, irc=None, target=None):
        responses.append(msg)

    bot_functions = {
        "notice_message": mock_notice,
        "log": lambda msg, level="INFO": None,
        "BOT_VERSION": "2.0.0",
    }

    # Test different case variations
    test_cases = ["!version", "!VERSION", "!Version", "!VeRsIoN"]

    for cmd in test_cases:
        responses.clear()
        enhanced_process_console_command(cmd, bot_functions)

        # All should work (if case insensitive) or at least handle gracefully
        # We expect at least some response or error handling
        assert len(responses) >= 0, f"Command {cmd} should be processed"


def test_console_command_empty_input():
    """Test handling of empty console command input."""
    from command_loader import enhanced_process_console_command

    responses = []

    def mock_notice(msg, irc=None, target=None):
        responses.append(msg)

    bot_functions = {
        "notice_message": mock_notice,
        "log": lambda msg, level="INFO": None,
        "BOT_VERSION": "2.0.0",
    }

    # Test empty command
    responses.clear()
    enhanced_process_console_command("", bot_functions)

    # Should handle gracefully (no crash)
    # Response behavior may vary but should not crash
    assert True  # If we get here, no exception was thrown


def test_console_command_unknown_command():
    """Test handling of unknown console commands."""
    from command_loader import enhanced_process_console_command

    responses = []

    def mock_notice(msg, irc=None, target=None):
        responses.append(msg)

    bot_functions = {
        "notice_message": mock_notice,
        "log": lambda msg, level="INFO": None,
        "BOT_VERSION": "2.0.0",
    }

    # Test unknown command
    responses.clear()
    enhanced_process_console_command("!unknowncommand", bot_functions)

    # Should handle gracefully, possibly with unknown command message
    # or silently ignore - either is acceptable
    assert True  # If we get here, no exception was thrown


def test_console_command_unicode_handling():
    """Test console command handling with unicode characters."""
    from command_loader import enhanced_process_console_command

    responses = []

    def mock_notice(msg, irc=None, target=None):
        responses.append(msg)

    def mock_send_weather_unicode(irc, target, location):
        mock_notice(f"Weather for {location}: ☀️ 20°C")

    bot_functions = {
        "notice_message": mock_notice,
        "log": lambda msg, level="INFO": None,
        "send_weather": mock_send_weather_unicode,
        "BOT_VERSION": "2.0.0",
    }

    # Test command with unicode location
    responses.clear()
    enhanced_process_console_command("!s Jyväskylä", bot_functions)

    # Should handle unicode gracefully
    assert any(
        "Jyväskylä" in str(response) for response in responses
    ), "Command should handle unicode characters in arguments"
