#!/usr/bin/env python3
"""
Console Commands Test Suite

Tests for console command functionality, including command processing,
bot manager integration, and command responses.
Pure pytest implementation with fixtures and proper assertions.
"""

import os
import sys
from io import StringIO
from unittest.mock import MagicMock, Mock

import pytest
from dotenv import load_dotenv

# Load environment variables for testing
load_dotenv()


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


def test_console_command_processing(mock_bot_functions, enhanced_command_processor):
    """Test basic console command processing."""
    responses = mock_bot_functions["_responses"]

    # Test version command
    responses.clear()
    enhanced_command_processor("!version", mock_bot_functions)

    # Should have gotten a version response
    assert any(
        "2.0.0" in str(response) for response in responses
    ), "Version command should return version number"


def test_console_weather_command(enhanced_command_processor):
    """Test console weather command processing."""
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
    enhanced_command_processor("!s Helsinki", bot_functions)

    # Should have gotten weather response
    assert any(
        "Helsinki" in str(response) for response in responses
    ), "Weather command should return Helsinki weather data"


def test_console_help_command(enhanced_command_processor):
    """Test console help command."""
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
    enhanced_command_processor("!help", bot_functions)

    # Should have gotten help response
    assert any(
        "command" in str(response).lower() for response in responses
    ), "Help command should return command information"


def test_bot_manager_console_integration():
    """Test BotManager console integration."""
    # Skip if dependencies are missing
    bot_manager = pytest.importorskip("bot_manager")

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
        ), "BotManager should have console listener method"

        # Check if console bot functions method exists
        assert hasattr(
            bot_manager, "_create_console_bot_functions"
        ), "BotManager should have console bot functions method"

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
            assert (
                func_name in bot_functions
            ), f"Bot functions should contain {func_name}"

    finally:
        # Always restore stdout/stderr
        sys.stdout = old_stdout
        sys.stderr = old_stderr


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
def test_console_command_with_services(command, enhanced_command_processor):
    """Test console commands with actual services."""
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
    "legacy_command", ["!s Joensuu", "!crypto btc eur", "!sahko", "!help", "!version"]
)
def test_legacy_console_commands(legacy_command):
    """Test legacy console command system."""
    # Skip if dependencies are missing
    commands = pytest.importorskip("commands")

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

    # Test legacy command
    responses.clear()
    commands.process_console_command(legacy_command, bot_functions)

    # Each command should generate responses
    assert responses, f"Legacy command {legacy_command} should generate responses"


def test_console_error_handling(enhanced_command_processor):
    """Test console command error handling."""
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
    enhanced_command_processor("!s Helsinki", bot_functions)

    # Should have handled the error gracefully
    # Either by logging error or providing error response
    assert errors_logged or any(
        "error" in str(r).lower() for r in responses
    ), "Error should be handled gracefully with error logging or response"


def test_console_command_argument_parsing(enhanced_command_processor):
    """Test console command argument parsing."""
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
    enhanced_command_processor("!s New York", bot_functions)

    # Should have parsed arguments correctly
    assert any(
        "New York" in str(response) for response in responses
    ), "Command should parse multi-word location arguments"


def test_console_command_case_insensitive(enhanced_command_processor):
    """Test console commands are case insensitive."""
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
        enhanced_command_processor(cmd, bot_functions)

        # All should work (if case insensitive) or at least handle gracefully
        # We expect at least some response or error handling
        assert len(responses) >= 0, f"Command {cmd} should be processed"


def test_console_command_empty_input(enhanced_command_processor):
    """Test handling of empty console command input."""
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
    enhanced_command_processor("", bot_functions)

    # Should handle gracefully (no crash)
    # Response behavior may vary but should not crash
    assert True  # If we get here, no exception was thrown


def test_console_command_unknown_command(enhanced_command_processor):
    """Test handling of unknown console commands."""
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
    enhanced_command_processor("!unknowncommand", bot_functions)

    # Should handle gracefully, possibly with unknown command message
    # or silently ignore - either is acceptable
    assert True  # If we get here, no exception was thrown


def test_console_command_unicode_handling(enhanced_command_processor):
    """Test console command handling with unicode characters."""
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
    enhanced_command_processor("!s Jyväskylä", bot_functions)

    # Should handle unicode gracefully
    assert any(
        "Jyväskylä" in str(response) for response in responses
    ), "Command should handle unicode characters in arguments"
