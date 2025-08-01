#!/usr/bin/env python3
"""
Console Commands Test Suite - Pure Pytest Version

Tests for console command functionality, including command processing,
bot manager integration, and command responses.
"""

import os
import sys
from unittest.mock import MagicMock, Mock

# Add the parent directory to Python path to ensure imports work in CI
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from dotenv import load_dotenv

# Load environment variables for testing
load_dotenv()


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


def test_legacy_console_commands():
    """Test legacy console command system."""
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
        assert responses, f"No response for legacy command: {cmd}"


def test_console_tilaa_command():
    """Test that !tilaa command works in console."""
    import tempfile

    import commands
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
        commands.process_console_command("!tilaa list", bot_functions)

        # Should get subscription list response
        assert any(
            "tilauksia" in str(response).lower() or "tilaukset" in str(response).lower()
            for response in responses
        ), f"Should get subscription list response, got: {responses}"

        # Test !tilaa varoitukset command
        responses.clear()
        commands.process_console_command("!tilaa varoitukset", bot_functions)

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
    import commands

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
    commands.process_console_command("!tilaa list", bot_functions)

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
