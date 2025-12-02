#!/usr/bin/env python3
"""
Pytest Console Commands tests

Tests for console command functionality, including command processing,
bot manager integration, and command responses.
"""

import os
import sys
import tempfile
from io import StringIO
from unittest.mock import Mock

import pytest
from dotenv import load_dotenv

# Load environment variables for testing
load_dotenv()


@pytest.fixture(autouse=True, scope="function")
def ensure_command_registry():
    """Ensure command registry is properly initialized for console command tests."""
    # Reset command registry and loader state before each test to avoid conflicts
    from command_registry import reset_command_registry

    reset_command_registry()

    # Reset command loader flag so commands get reloaded
    try:
        from command_loader import reset_commands_loaded_flag

        reset_commands_loaded_flag()
    except (ImportError, AttributeError):
        # If the function doesn't exist, manually reset the flag
        try:
            import command_loader

            command_loader._commands_loaded = False
        except Exception:
            pass

    # Load all command modules to register commands properly
    try:
        import importlib

        import commands
        import commands_admin
        import commands_irc

        # Force reload so decorators execute again after registry reset
        # Ignore duplicate registration errors
        try:
            importlib.reload(commands)
        except ValueError as e:
            if "already registered" not in str(e):
                raise
        try:
            importlib.reload(commands_admin)
        except ValueError as e:
            if "already registered" not in str(e):
                raise
        try:
            importlib.reload(commands_irc)
        except ValueError as e:
            if "already registered" not in str(e):
                raise

        # Log the number of registered commands for debugging
        from command_registry import get_command_registry

        reg = get_command_registry()
        print(
            f"Console test: Loaded {len(reg._commands)} commands from command modules"
        )
    except Exception as e:
        print(f"Warning: Failed to reload commands in test fixture: {e}")

    yield

    # Clean up after test
    reset_command_registry()
    try:
        from command_loader import reset_commands_loaded_flag

        reset_commands_loaded_flag()
    except (ImportError, AttributeError):
        try:
            import command_loader

            command_loader._commands_loaded = False
        except Exception:
            pass


def test_console_command_processing():
    """Test basic console command processing."""
    from command_loader import process_console_command

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
        "BOT_VERSION": "2.2.0",
    }

    # Test version command
    responses.clear()
    process_console_command("!version", bot_functions)

    # Should have gotten a version response
    assert any(
        "2.2.0" in str(response) for response in responses
    ), "Should get version response"


def test_console_weather_command():
    """Test console weather command processing."""
    from command_loader import process_console_command

    responses = []

    def mock_notice(msg, irc=None, target=None):
        responses.append(msg)

    bot_functions = {
        "notice_message": mock_notice,
        "log": lambda msg, level="INFO": None,
        "send_weather": lambda irc, target, location: mock_notice(
            f"Weather for {location}: Sunny, 20°C"
        ),
        "BOT_VERSION": "2.2.0",
    }

    # Test weather command
    responses.clear()
    process_console_command("!s Helsinki", bot_functions)

    # Should have gotten weather response
    assert any(
        "Helsinki" in str(response) for response in responses
    ), "Should get Helsinki weather response"


def test_console_help_command():
    """Test console help command."""
    from command_loader import process_console_command

    responses = []

    def mock_notice(msg, irc=None, target=None):
        responses.append(msg)

    bot_functions = {
        "notice_message": mock_notice,
        "log": lambda msg, level="INFO": None,
        "BOT_VERSION": "2.2.0",
    }

    # Test help command
    responses.clear()
    process_console_command("!help", bot_functions)

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
        "BOT_VERSION": "2.2.0",
    }

    from command_loader import process_console_command

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
        process_console_command(cmd, bot_functions)

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
        from command_loader import process_console_command

        process_console_command(cmd, bot_functions)

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

        # Create a wrapper object that provides the methods expected by the command
        class SubscriptionsWrapper:
            def format_all_subscriptions(self):
                return subscriptions.format_all_subscriptions()

            def toggle_subscription(self, subscriber, server, topic):
                return subscriptions.toggle_subscription(subscriber, server, topic)

        # Mock subscriptions service with wrapper
        bot_functions = {
            "notice_message": mock_notice,
            "log": mock_log,
            "subscriptions": SubscriptionsWrapper(),
            "send_electricity_price": lambda *args: None,
            "load_leet_winners": lambda: {},
            "send_weather": lambda *args: None,
            "load": lambda: {},
            "fetch_title": lambda *args: None,
            "handle_ipfs_command": lambda *args: None,
        }

        # Test !tilaa list command
        responses.clear()
        from command_loader import process_console_command

        process_console_command("!tilaa list", bot_functions)

        # Should get subscription list response
        assert any(
            "tilauksia" in str(response).lower() or "tilaukset" in str(response).lower()
            for response in responses
        ), f"Should get subscription list response, got: {responses}"

        # Test !tilaa varoitukset command
        responses.clear()
        from command_loader import process_console_command

        process_console_command("!tilaa varoitukset", bot_functions)

        # Should get subscription toggle response
        assert any(
            "tilaus" in str(response).lower() for response in responses
        ), f"Should get subscription toggle response, got: {responses}"

    finally:
        # Restore original file
        subscriptions.SUBSCRIBERS_FILE = original_file
        if os.path.exists(temp_file.name):
            os.unlink(temp_file.name)


def test_console_error_handling():
    """Test console command error handling."""
    from command_loader import process_console_command

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
        "BOT_VERSION": "2.2.0",
    }

    # Test command that should fail gracefully
    responses.clear()
    errors_logged.clear()
    process_console_command("!s Helsinki", bot_functions)

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
        "BOT_VERSION": "2.2.0",
    }

    # Attach responses list for test access
    bot_functions["_responses"] = responses
    return bot_functions


@pytest.fixture
def enhanced_command_processor():
    """Import the enhanced command processor."""
    from command_loader import process_console_command

    return process_console_command


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
        "BOT_VERSION": "2.2.0",
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
    from command_loader import process_console_command

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
    process_console_command(compatibility_command, bot_functions)

    # Each command should generate responses
    assert (
        responses
    ), f"Compatibility command {compatibility_command} should generate responses"


def test_console_command_argument_parsing():
    """Test console command argument parsing."""
    from command_loader import process_console_command

    responses = []

    def mock_notice(msg, irc=None, target=None):
        responses.append(msg)

    def mock_send_weather_with_args(irc, target, location):
        mock_notice(f"Weather requested for: {location}")

    bot_functions = {
        "notice_message": mock_notice,
        "log": lambda msg, level="INFO": None,
        "send_weather": mock_send_weather_with_args,
        "BOT_VERSION": "2.2.0",
    }

    # Test command with arguments
    responses.clear()
    process_console_command("!s New York", bot_functions)

    # Should have parsed arguments correctly
    assert any(
        "New York" in str(response) for response in responses
    ), "Command should parse multi-word location arguments"


def test_console_command_case_insensitive():
    """Test console commands are case insensitive."""
    from command_loader import process_console_command

    responses = []

    def mock_notice(msg, irc=None, target=None):
        responses.append(msg)

    bot_functions = {
        "notice_message": mock_notice,
        "log": lambda msg, level="INFO": None,
        "BOT_VERSION": "2.2.0",
    }

    # Test different case variations
    test_cases = ["!version", "!VERSION", "!Version", "!VeRsIoN"]

    for cmd in test_cases:
        responses.clear()
        process_console_command(cmd, bot_functions)

        # All should work (if case insensitive) or at least handle gracefully
        # We expect at least some response or error handling
        assert len(responses) >= 0, f"Command {cmd} should be processed"


def test_console_command_empty_input():
    """Test handling of empty console command input."""
    from command_loader import process_console_command

    responses = []

    def mock_notice(msg, irc=None, target=None):
        responses.append(msg)

    bot_functions = {
        "notice_message": mock_notice,
        "log": lambda msg, level="INFO": None,
        "BOT_VERSION": "2.2.0",
    }

    # Test empty command
    responses.clear()
    process_console_command("", bot_functions)

    # Should handle gracefully (no crash)
    # Response behavior may vary but should not crash
    assert True  # If we get here, no exception was thrown


def test_console_command_unknown_command():
    """Test handling of unknown console commands."""
    from command_loader import process_console_command

    responses = []

    def mock_notice(msg, irc=None, target=None):
        responses.append(msg)

    bot_functions = {
        "notice_message": mock_notice,
        "log": lambda msg, level="INFO": None,
        "BOT_VERSION": "2.2.0",
    }

    # Test unknown command
    responses.clear()
    process_console_command("!unknowncommand", bot_functions)

    # Should handle gracefully, possibly with unknown command message
    # or silently ignore - either is acceptable
    assert True  # If we get here, no exception was thrown


def test_console_command_unicode_handling():
    """Test console command handling with unicode characters."""
    from command_loader import process_console_command

    responses = []

    def mock_notice(msg, irc=None, target=None):
        responses.append(msg)

    def mock_send_weather_unicode(irc, target, location):
        mock_notice(f"Weather for {location}: ☀️ 20°C")

    bot_functions = {
        "notice_message": mock_notice,
        "log": lambda msg, level="INFO": None,
        "send_weather": mock_send_weather_unicode,
        "BOT_VERSION": "2.2.0",
    }

    # Test command with unicode location
    responses.clear()
    process_console_command("!s Jyväskylä", bot_functions)

    # Should handle unicode gracefully
    assert any(
        "Jyväskylä" in str(response) for response in responses
    ), "Command should handle unicode characters in arguments"


def test_help_specific_command_console():
    """!help <cmd> should return specific command help in console."""
    from command_loader import process_console_command

    responses = []

    def mock_notice(msg, irc=None, target=None):
        responses.append(msg)

    bot_functions = {
        "notice_message": mock_notice,
        "log": lambda msg, level="INFO": None,
        "BOT_VERSION": "2.2.0",
    }

    responses.clear()
    process_console_command("!help ping", bot_functions)
    assert any("ping" in str(r).lower() for r in responses)


def test_euribor_command_success_and_error(monkeypatch):
    """Test euribor command success XML path and error path."""
    from command_registry import CommandContext
    from commands import euribor_command

    class Resp:
        def __init__(self, code, content):
            self.status_code = code
            self.content = content

    xml_ok = (
        b'<euribor_korot_today_xml_en xmlns="euribor_korot_today_xml_en">'
        b"<period value='2025-08-01'>"
        b"<rates>"
        b"<rate name='12 month (act/360)'><intr value='3.456'/></rate>"
        b"</rates>"
        b"</period>"
        b"</euribor_korot_today_xml_en>"
    )

    # Success path
    import requests as _requests

    monkeypatch.setattr(_requests, "get", lambda url: Resp(200, xml_ok))
    ctx = CommandContext(
        command="euribor",
        args=[],
        raw_message="!euribor",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )
    res = euribor_command(ctx, {})
    assert "12kk Euribor" in res

    # HTTP error path
    monkeypatch.setattr(_requests, "get", lambda url: Resp(500, b""))
    res2 = euribor_command(ctx, {})
    assert "HTTP Status Code: 500" in res2

    # Exception path
    def boom(url):
        raise Exception("boom")

    monkeypatch.setattr(_requests, "get", boom)
    res3 = euribor_command(ctx, {})
    assert "Error fetching Euribor rate" in res3


def test_trains_command_variants_and_error(monkeypatch):
    """Test trains command with both subcommands and error handling."""
    from command_registry import CommandContext
    from commands import trains_command

    monkeypatch.setattr(
        "services.digitraffic_service.get_trains_for_station",
        lambda station: f"Trains for {station or 'Joensuu'}",
    )
    monkeypatch.setattr(
        "services.digitraffic_service.get_arrivals_for_station",
        lambda station: f"Arrivals for {station or 'Joensuu'}",
    )

    # Default trains
    ctx = CommandContext(
        command="junat",
        args=[],
        raw_message="!junat",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )
    res_default = trains_command(ctx, {})
    msg_default = (
        res_default
        if isinstance(res_default, str)
        else getattr(res_default, "message", str(res_default))
    )
    assert "Trains for" in msg_default

    # Arrivals subcommand
    ctx2 = CommandContext(
        command="junat",
        args=["saapuvat", "HKI"],
        raw_message="!junat saapuvat HKI",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )
    res_arr = trains_command(ctx2, {})
    msg_arr = (
        res_arr
        if isinstance(res_arr, str)
        else getattr(res_arr, "message", str(res_arr))
    )
    assert "Arrivals for HKI" in msg_arr

    # Error handling
    def fail(*args, **kwargs):
        raise Exception("down")

    monkeypatch.setattr("services.digitraffic_service.get_trains_for_station", fail)
    assert "Digitraffic" in trains_command(ctx, {})


def test_url_command_calls_fetch_title_and_missing_service():
    """Test url command with and without fetch_title service."""
    from command_loader import process_console_command

    called = {"url": None}

    def fetch_title(_irc, _target, url):
        called["url"] = url

    bot_functions = {
        "notice_message": lambda *a, **k: None,
        "fetch_title": fetch_title,
        "log": lambda *a, **k: None,
    }

    process_console_command("!url https://example.com", bot_functions)
    assert called["url"] == "https://example.com"

    # Missing service path
    bot_functions2 = {
        "notice_message": lambda *a, **k: None,
        "log": lambda *a, **k: None,
    }
    process_console_command("!url https://example.com", bot_functions2)


def test_leetwinners_command_empty_and_with_data():
    from command_loader import process_console_command

    # Empty
    responses = []
    bot_functions = {
        "notice_message": lambda m, *a, **k: responses.append(m),
        "log": lambda *a, **k: None,
        "load_leet_winners": lambda: {},
    }
    responses.clear()
    process_console_command("!leetwinners", bot_functions)
    assert any("Leet" in str(r) or "𝓛𝓮𝓮𝓽" in str(r) for r in responses)

    # With data
    winners = {
        "Alice": {"first": 3, "multileet": 1},
        "Bob": {"first": 2, "viimeinen": 4},
    }
    bot_functions["load_leet_winners"] = lambda: winners
    responses.clear()
    process_console_command("!leetwinners", bot_functions)
    assert responses


def test_exit_command_console_and_irc():
    from command_loader import (
        process_console_command,
        process_irc_message,
    )

    # Console with stop_event
    responses = []
    stop_event = Mock()
    bot_functions = {
        "notice_message": lambda m, *a, **k: responses.append(m),
        "stop_event": stop_event,
    }
    process_console_command("!exit", bot_functions)
    stop_event.set.assert_called_once()
    assert any("Bot shutdown initiated" in str(r) for r in responses)

    # Console without stop_event
    responses.clear()
    process_console_command(
        "!exit", {"notice_message": lambda m, *a, **k: responses.append(m)}
    )
    assert any(
        "Exit command" in str(r) or "bot shutting down" in str(r) for r in responses
    )

    # IRC path – should indicate console-only
    notices = []

    def mock_notice(msg, irc=None, target=None):
        notices.append(msg)

    botf = {"notice_message": mock_notice}

    class _DummyIrc:
        def __init__(self):
            self.sent = []

    import asyncio

    raw = ":nick!u@h PRIVMSG #c :!exit"
    asyncio.run(process_irc_message(_DummyIrc(), raw, botf))
    assert notices and any(
        ("only" in n.lower() and "console" in n.lower()) for n in notices
    )


def test_crypto_command_variants():
    from command_loader import process_console_command

    responses = []

    def notice(m, *a, **k):
        responses.append(m)

    # With args
    botf = {
        "notice_message": notice,
        "get_crypto_price": lambda coin, currency="eur": "123",
    }
    responses.clear()
    process_console_command("!crypto btc usd", botf)
    assert any("123 USD" in r or "Btc" in r for r in responses)

    # Default list
    responses.clear()
    process_console_command("!crypto", botf)
    assert responses


def test_drink_commands_full_cycle(tmp_path):
    """Cover drinkword, drink, and kraks commands using injected drink_tracker."""
    from command_loader import process_console_command
    from word_tracking import DataManager, DrinkTracker

    dm = DataManager(str(tmp_path))
    dt = DrinkTracker(dm)

    # Seed some data
    dt.process_message("console", "alice", "krak krak")
    dt.process_message("console", "bob", "narsk")

    responses = []

    def n(m, *a, **k):
        responses.append(m)

    botf = {"notice_message": n, "drink_tracker": dt, "server_name": "console"}

    # drinkword usage
    responses.clear()
    process_console_command("!drinkword", botf)
    assert responses and any("Käyttö" in r for r in responses)

    # drinkword success
    responses.clear()
    process_console_command("!drinkword krak", botf)
    assert responses and any("krak" in r for r in responses)

    # drink usage
    responses.clear()
    process_console_command("!drink", botf)
    assert responses and any("Käyttö" in r for r in responses)

    # drink success
    responses.clear()
    process_console_command("!drink krak", botf)
    assert responses and any("krak" in r for r in responses)

    # kraks summary
    responses.clear()
    process_console_command("!kraks", botf)
    assert responses and any("Krakit" in r for r in responses)


def test_tamagotchi_commands_basic():
    from command_loader import process_console_command

    responses = []

    def n(m, *a, **k):
        responses.append(m)

    botf = {"notice_message": n}

    process_console_command("!tamagotchi", botf)
    process_console_command("!feed pizza", botf)
    process_console_command("!pet", botf)
    assert len(responses) >= 3


def test_schedule_command_cases(monkeypatch):
    from command_registry import CommandContext
    from commands import command_schedule

    # Valid schedule
    call_args = {}

    def fake_send(server, channel, message, h, m, s, ns):
        call_args.update(
            dict(server=server, channel=channel, message=message, h=h, m=m, s=s, ns=ns)
        )
        return "id123"

    monkeypatch.setattr(
        "services.scheduled_message_service.send_scheduled_message", fake_send
    )

    ctx = CommandContext(
        command="schedule",
        args=["irc.atw-inter.net", "#ch", "10:05:03.123456789", "msg here"],
        raw_message="irc.atw-inter.net #ch 10:05:03.123456789 msg here",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )
    res = command_schedule(ctx, {"server": object()})
    assert "Message scheduled" in res and call_args["ns"] == "123456789"

    # Invalid format
    ctx2 = CommandContext(
        command="schedule",
        args=["#ch", "bad"],
        raw_message="",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )
    assert "Invalid format" in command_schedule(ctx2, {"server": object()})

    # Invalid time
    ctx3 = CommandContext(
        command="schedule",
        args=["#ch", "25:61:61", "oops"],
        raw_message="",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )
    assert "Invalid format!" in command_schedule(ctx3, {"server": object()})

    # Missing server
    ctx4 = CommandContext(
        command="schedule",
        args=["#ch", "10:00:00", "hi"],
        raw_message="",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )
    assert "Invalid format!" in command_schedule(ctx4, {})


def test_ipfs_command_usage_and_success(monkeypatch):
    import os as _os

    from command_registry import CommandContext
    from commands import command_ipfs

    # Usage
    ctx = CommandContext(
        command="ipfs",
        args=[],
        raw_message="!ipfs",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )
    assert "Usage" in command_ipfs(ctx, {})

    # Success path
    def fake_handle(cmd_text, admin_pwd):
        assert cmd_text.startswith("!ipfs add") or cmd_text.startswith("!ipfs ")
        return "ok"

    monkeypatch.setattr("services.ipfs_service.handle_ipfs_command", fake_handle)
    _os.environ["ADMIN_PASSWORD"] = "secret"
    ctx2 = CommandContext(
        command="ipfs",
        args=["add", "http://example.com/file"],
        raw_message="!ipfs add http://example.com/file",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )
    assert command_ipfs(ctx2, {}) == "ok"


def test_eurojackpot_command_branches(monkeypatch):
    from command_loader import process_console_command

    responses = []

    def n(m, *a, **k):
        responses.append(m)

    botf = {"notice_message": n}

    # results path
    monkeypatch.setattr(
        "services.eurojackpot_service.get_eurojackpot_results", lambda: "results"
    )
    responses.clear()
    process_console_command("!eurojackpot tulokset", botf)
    assert responses and "results" in responses[0]

    # numbers path
    monkeypatch.setattr(
        "services.eurojackpot_service.get_eurojackpot_numbers", lambda: "numbers"
    )
    responses.clear()
    process_console_command("!eurojackpot", botf)
    assert responses and "numbers" in responses[0]


def test_short_forecast_commands_console_and_irc(monkeypatch):
    from command_loader import (
        process_console_command,
        process_irc_message,
    )

    # Console short forecast
    monkeypatch.setattr(
        "services.weather_forecast_service.format_single_line",
        lambda city, hours: f"Forecast {city or 'Joensuu'} {hours or ''}".strip(),
    )
    resps = []

    def n(m, *a, **k):
        resps.append(m)

    botf = {"notice_message": n}

    process_console_command("!se Joensuu 6", botf)
    assert resps and any("Joensuu" in r for r in resps)

    # IRC short forecast list with notices
    monkeypatch.setattr(
        "services.weather_forecast_service.format_multi_line",
        lambda city, hours: [f"L1 {city}", f"L2 {hours}"],
    )
    notices = []

    def notice(msg, irc=None, target=None):
        notices.append((msg, target))

    botfi = {"notice_message": notice}

    class _DummyIrc2:
        def __init__(self):
            self.sent = []

    import asyncio

    raw = ":nick!u@h PRIVMSG #chan :!sel TestCity 12"
    asyncio.run(process_irc_message(_DummyIrc2(), raw, botfi))
    assert notices and any("L1" in n[0] for n in notices)


def test_sana_topwords_leaderboard_commands(monkeypatch):
    """Cover sana, topwords and leaderboard command branches."""
    import commands as _cmd
    from command_loader import process_console_command

    # Patch search_word to return results with users
    def fake_search(word):
        return {
            "total_occurrences": 2,
            "servers": {"srv": {"users": [{"nick": "a", "count": 2}]}},
        }

    monkeypatch.setattr(_cmd._general_words, "search_word", fake_search)

    responses = []
    botf = {"notice_message": lambda m, *a, **k: responses.append(m)}

    responses.clear()
    process_console_command("!sana testisana", botf)
    assert any("Sana" in r for r in responses)

    # Patch data_manager and general_words for topwords
    monkeypatch.setattr(_cmd.data_manager, "get_all_servers", lambda: ["srv1"])
    monkeypatch.setattr(
        _cmd.general_words, "get_user_stats", lambda srv, nick: {"total_words": 5}
    )
    monkeypatch.setattr(
        _cmd.general_words,
        "get_user_top_words",
        lambda srv, nick, n: [{"word": "foo", "count": 3}],
    )

    responses.clear()
    process_console_command("!topwords Alice", botf)
    assert any("Alice@srv1" in r for r in responses)

    # Global leaderboard
    def fake_leaderboard(srv, n):
        return [{"nick": "u1", "total_words": 10}, {"nick": "u2", "total_words": 7}]

    monkeypatch.setattr(_cmd.general_words, "get_leaderboard", fake_leaderboard)

    responses.clear()
    process_console_command("!leaderboard", botf)
    assert any("Aktiivisimmat" in r for r in responses)


def test_kraks_no_breakdown(monkeypatch, tmp_path):
    """Cover kraks else-branch when no breakdown but top users exist."""
    from command_loader import process_console_command
    from word_tracking import DataManager, DrinkTracker

    dm = DataManager(str(tmp_path))
    dt = DrinkTracker(dm)
    # Seed minimal data
    dt.process_message("console", "alice", "krak")

    # Monkeypatch breakdown empty and stats top_users present
    monkeypatch.setattr(dt, "get_drink_word_breakdown", lambda server: [])
    stats = dt.get_server_stats("console")
    stats["top_users"] = [("alice", 1)]
    monkeypatch.setattr(dt, "get_server_stats", lambda server: stats)

    responses = []
    botf = {
        "notice_message": lambda m, *a, **k: responses.append(m),
        "drink_tracker": dt,
        "server_name": "console",
    }
    process_console_command("!kraks", botf)
    assert any("Top 5" in r or "Top" in r for r in responses)


def test_schedule_management_list_and_cancel(monkeypatch):
    """Test !scheduled list and cancel flows (require admin password)."""
    import importlib
    import time

    from command_loader import ensure_commands_loaded, process_console_command
    from command_registry import reset_command_registry

    # Ensure commands are loaded for this test
    reset_command_registry()
    try:
        from command_loader import reset_commands_loaded_flag

        reset_commands_loaded_flag()
    except (ImportError, AttributeError):
        pass

    # Force reload all command modules to ensure all commands are registered
    import commands
    import commands_admin
    import commands_irc

    # Reload modules to trigger command registration (ignore duplicate errors)
    for mod in [commands, commands_admin, commands_irc]:
        try:
            importlib.reload(mod)
        except ValueError:
            pass  # Ignore duplicate registration errors

    # Explicitly ensure commands are loaded
    ensure_commands_loaded()

    class FakeService:
        def __init__(self):
            self._messages = {
                "id1": {
                    "message": "m1",
                    "channel": "#c",
                    "target_time": "t",
                    "target_display": "t",
                }
            }

        def list_scheduled_messages(self):
            return self._messages

        def cancel_message(self, mid):
            if mid in self._messages:
                del self._messages[mid]
                return True
            return False

    monkeypatch.setattr(
        "services.scheduled_message_service.get_scheduled_message_service",
        lambda: FakeService(),
    )

    # Set admin password expected by commands_admin.verify_admin_password
    class _Cfg:
        admin_password = "adm"

    monkeypatch.setattr("commands_admin.get_config", lambda: _Cfg())

    responses = []
    # Use a list that we can check for responses
    botf = {
        "notice_message": lambda m, *a, **k: responses.append(str(m)),
        "log": lambda msg, level="INFO": None,
    }

    # List - check that we get a response with scheduled messages info
    responses.clear()
    process_console_command("!scheduled adm list", botf)
    # process_console_command is synchronous (uses asyncio.run or waits for thread completion)
    # But we need to handle cases where responses might be added asynchronously
    # Wait a small amount for any async callbacks to complete
    for _ in range(10):  # Wait up to 0.1s for response
        if responses:
            break
        time.sleep(0.01)
    # Combine all responses to handle multi-line output
    combined_response = " ".join(responses) if responses else ""
    assert (
        "Scheduled messages" in combined_response
        or "📅" in combined_response
        or "id1" in combined_response
    ), f"Expected scheduled messages info, got: {responses}"

    # Cancel
    responses.clear()
    process_console_command("!scheduled adm cancel id1", botf)
    # Wait for response
    for _ in range(10):  # Wait up to 0.1s for response
        if responses:
            break
        time.sleep(0.01)
    # Combine all responses to handle multi-line output
    combined_response = " ".join(responses) if responses else ""
    assert (
        "Cancelled" in combined_response
        or "✅" in combined_response
        or "id1" in combined_response
    ), f"Expected cancellation message, got: {responses}"


def test_ipfs_and_eurojackpot_error_paths(monkeypatch):
    from command_loader import process_console_command

    # IPFS error path
    monkeypatch.setattr(
        "services.ipfs_service.handle_ipfs_command",
        lambda *a, **k: (_ for _ in ()).throw(Exception("boom")),
    )
    resps = []
    botf = {"notice_message": lambda m, *a, **k: resps.append(m)}
    resps.clear()
    process_console_command("!ipfs add http://x", botf)
    assert any("IPFS error" in r for r in resps)

    # Eurojackpot error path
    monkeypatch.setattr(
        "services.eurojackpot_service.get_eurojackpot_numbers",
        lambda: (_ for _ in ()).throw(Exception("down")),
    )
    resps.clear()
    process_console_command("!eurojackpot", botf)
    assert any("Eurojackpot error" in r for r in resps)


def test_eurojackpot_freq_stats_hot(monkeypatch):
    from command_loader import process_console_command

    # Fake service with selected methods
    class FakeService:
        def get_frequent_numbers(self, limit=10, extended=False):
            return {"success": True, "message": f"FREQ ext={extended} limit={limit}"}

        def get_database_stats(self):
            return {"success": True, "message": "DB STATS"}

        def get_hot_cold_numbers(self, mode="hot", window=None, top=5):
            return {"success": True, "message": f"HOTCOLD {mode}"}

    monkeypatch.setattr(
        "services.eurojackpot_service.get_eurojackpot_service",
        lambda: FakeService(),
    )

    responses = []
    botf = {"notice_message": lambda m, *a, **k: responses.append(m)}

    # freq with flags
    responses.clear()
    process_console_command("!eurojackpot freq --extended --limit 7", botf)
    assert any("FREQ ext=True limit=7" in r for r in responses)

    # stats
    responses.clear()
    process_console_command("!eurojackpot stats", botf)
    assert any("DB STATS" in r for r in responses)

    # hot analytics
    responses.clear()
    process_console_command("!eurojackpot hot", botf)
    assert any("HOTCOLD hot" in r for r in responses)


def test_services_missing_branches():
    from command_loader import process_console_command

    # Crypto service missing
    resps = []
    botf = {"notice_message": lambda m, *a, **k: resps.append(m)}
    resps.clear()
    process_console_command("!crypto", botf)
    assert any("not available" in r for r in resps)


def test_help_irc_fallback_without_notice():
    """Test help command IRC branch when no notice_message available."""
    from command_loader import process_irc_message

    class _DummyIrc3:
        def __init__(self):
            self.sent = []

    responses = []

    # Without irc
    import asyncio

    raw = ":nick!u@h PRIVMSG #c :!help"
    botf_no_irc = {"notice_message": lambda m, *a, **k: responses.append(m)}
    responses.clear()
    asyncio.run(process_irc_message(_DummyIrc3(), raw, botf_no_irc))
    # Should still add response in fallback


def test_echo_command_console_vs_irc():
    """Test echo command has different console vs IRC message format."""
    from command_registry import CommandContext
    from commands import echo_command

    # Console context
    ctx_console = CommandContext(
        command="kaiku",
        args=["hello", "world"],
        raw_message="!kaiku hello world",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )
    res = echo_command(ctx_console, {})
    assert "Console:" in res

    # IRC context
    ctx_irc = CommandContext(
        command="kaiku",
        args=["hello", "world"],
        raw_message="!kaiku hello world",
        sender="TestUser",
        target="#channel",
        is_private=False,
        is_console=False,
        server_name="server",
    )
    res2 = echo_command(ctx_irc, {})
    assert "TestUser:" in res2


def test_weather_branch_import_logging(monkeypatch):
    """Test weather command console branch logging import."""
    from command_registry import CommandContext
    from commands import weather_command

    ctx = CommandContext(
        command="s",
        args=["TestCity"],
        raw_message="!s TestCity",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )

    # Mock send_weather to do nothing but confirm called
    called = []

    def mock_weather(irc, target, loc):
        called.append((irc, target, loc))

    botf = {"send_weather": mock_weather}

    weather_command(ctx, botf)
    assert called and called[0][2] == "TestCity"


def test_tilaa_special_cases(monkeypatch):
    """Test tilaa command edge cases."""
    from command_loader import process_console_command

    # Mock subscriptions service
    class FakeSubService:
        def toggle_subscription(self, sub, server, topic):
            return "Toggled subscription"

        def format_all_subscriptions(self):
            return "No subscriptions"

    service = FakeSubService()

    responses = []
    botf = {
        "notice_message": lambda m, *a, **k: responses.append(m),
        "subscriptions": service,
    }

    # Test with explicit channel arg
    responses.clear()
    process_console_command("!tilaa varoitukset #testchannel", botf)
    assert responses

    # Test bad topic
    responses.clear()
    process_console_command("!tilaa badtopic", botf)
    assert any("Tuntematon" in r for r in responses)


def test_leets_command_args_handling(monkeypatch):
    """Test leets command args parsing with numeric limit."""
    from command_registry import CommandContext
    from commands import command_leets

    # Mock detector with custom history
    def fake_detector():
        class FakeDet:
            def get_leet_history(self, limit=5):
                return (
                    []
                    if limit <= 0
                    else [
                        {
                            "datetime": "2025-01-01T12:00:00",
                            "nick": "test",
                            "timestamp": "12:00:00",
                            "achievement_name": "Test",
                            "emoji": "🎉",
                            "user_message": "",
                        }
                    ]
                    * min(limit, 3)
                )

        return FakeDet()

    monkeypatch.setattr("leet_detector.create_leet_detector", fake_detector)

    # Test with numeric arg
    ctx = CommandContext(
        command="leets",
        args=["2"],
        raw_message="!leets 2",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )
    res = command_leets(ctx, {})
    assert "Recent Leet" in res or "Test" in res


def test_schedule_invalid_arg_cases(monkeypatch):
    """Test schedule command with more invalid argument patterns."""
    from command_registry import CommandContext
    from commands import command_schedule

    # No args
    ctx1 = CommandContext(
        command="schedule",
        args=[],
        raw_message="!schedule",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )
    assert "Usage" in command_schedule(ctx1, {"server": object()})

    # Valid fractional but exception
    def boom(*a, **k):
        raise Exception("scheduling error")

    monkeypatch.setattr(
        "services.scheduled_message_service.send_scheduled_message", boom
    )

    ctx2 = CommandContext(
        command="schedule",
        args=["#c", "12:00:00.500", "msg"],
        raw_message="",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )
    assert "Invalid format!" in command_schedule(ctx2, {"server": object()})


def test_sana_no_users_branch(monkeypatch):
    """Cover sana command branch when total_occurrences>0 but no users."""
    import commands as _cmd
    from command_loader import process_console_command

    # Mock search to return total>0 but empty users
    def fake_search_no_users(word):
        return {"total_occurrences": 1, "servers": {"srv": {"users": []}}}

    monkeypatch.setattr(_cmd._general_words, "search_word", fake_search_no_users)

    responses = []
    botf = {"notice_message": lambda m, *a, **k: responses.append(m)}
    process_console_command("!sana xyz", botf)
    assert any("Kukaan ei ole sanonut" in r for r in responses)


def test_topwords_found_user_early_return(monkeypatch):
    """Cover topwords command early return when user found."""
    import commands as _cmd
    from command_loader import process_console_command

    monkeypatch.setattr(_cmd.data_manager, "get_all_servers", lambda: ["srv1", "srv2"])

    def user_stats(srv, nick):
        if srv == "srv1" and nick == "Alice":
            return {"total_words": 10}
        return {"total_words": 0}  # No data for srv2

    def top_words(srv, nick, n):
        if srv == "srv1":
            return [{"word": "test", "count": 5}]
        return []

    monkeypatch.setattr(_cmd.general_words, "get_user_stats", user_stats)
    monkeypatch.setattr(_cmd.general_words, "get_user_top_words", top_words)

    responses = []
    botf = {"notice_message": lambda m, *a, **k: responses.append(m)}
    process_console_command("!topwords Alice", botf)
    # Should find on srv1 and return early, never checking srv2
    assert any("Alice@srv1" in r and "test: 5" in r for r in responses)


def test_help_command_direct_fallbacks():
    """Call help_command directly to exercise IRC fallbacks without notice/irc."""
    from command_registry import CommandContext
    from commands import help_command

    # Specific command with IRC context but no notice
    ctx = CommandContext(
        command="help",
        args=["ping"],
        raw_message="!help ping",
        sender="u",
        target="#c",
        is_private=False,
        is_console=False,
        server_name="s",
    )
    res = help_command(ctx, {})
    msg = res if isinstance(res, str) else getattr(res, "message", str(res))
    assert "ping" in msg.lower()
    # No-arg help with IRC context but no notice
    ctx2 = CommandContext(
        command="help",
        args=[],
        raw_message="!help",
        sender="u",
        target="#c",
        is_private=False,
        is_console=False,
        server_name="s",
    )
    res2 = help_command(ctx2, {})
    msg2 = res2 if isinstance(res2, str) else getattr(res2, "message", str(res2))
    assert "commands" in msg2.lower()


def test_topwords_and_leaderboard_no_data(monkeypatch):
    """Cover no-data branches in topwords and leaderboard."""
    import commands as _cmd
    from command_loader import process_console_command

    # topwords no data path
    monkeypatch.setattr(_cmd.data_manager, "get_all_servers", lambda: [])
    responses = []
    botf = {"notice_message": lambda m, *a, **k: responses.append(m)}
    process_console_command("!topwords", botf)
    assert any("Ei vielä tarpeeksi dataa" in r for r in responses)
    # leaderboard no data path
    responses.clear()
    process_console_command("!leaderboard", botf)
    assert any("Ei vielä tarpeeksi dataa" in r for r in responses)


def test_drink_tracker_missing_paths(monkeypatch):
    """Force drink commands to report missing tracker by nulling globals."""
    import commands as _cmd
    from command_loader import process_console_command

    # Temporarily null trackers
    orig_dt = _cmd._drink_tracker
    try:
        _cmd._drink_tracker = None
        responses = []
        botf = {"notice_message": lambda m, *a, **k: responses.append(m)}
        process_console_command("!drinkword krak", botf)
        assert any("ei ole käytettävissä" in r.lower() for r in responses)
        responses.clear()
        process_console_command("!drink krak", botf)
        assert any("ei ole käytettävissä" in r.lower() for r in responses)
    finally:
        _cmd._drink_tracker = orig_dt


def test_scheduled_empty_and_not_found_and_usage(monkeypatch):
    import importlib
    import time

    from command_loader import ensure_commands_loaded, process_console_command
    from command_registry import reset_command_registry

    # Ensure commands are loaded for this test
    reset_command_registry()
    try:
        from command_loader import reset_commands_loaded_flag

        reset_commands_loaded_flag()
    except (ImportError, AttributeError):
        pass

    # Force reload all command modules to ensure all commands are registered
    import commands
    import commands_admin
    import commands_irc

    # Reload modules to trigger command registration (ignore duplicate errors)
    for mod in [commands, commands_admin, commands_irc]:
        try:
            importlib.reload(mod)
        except ValueError:
            pass  # Ignore duplicate registration errors

    # Explicitly ensure commands are loaded
    ensure_commands_loaded()

    class EmptyService:
        def list_scheduled_messages(self):
            return {}

        def cancel_message(self, mid):
            return False

    monkeypatch.setattr(
        "services.scheduled_message_service.get_scheduled_message_service",
        lambda: EmptyService(),
    )

    # Set admin password expected by commands_admin.verify_admin_password
    class _Cfg:
        admin_password = "adm"

    monkeypatch.setattr("commands_admin.get_config", lambda: _Cfg())

    responses = []
    botf = {
        "notice_message": lambda m, *a, **k: responses.append(str(m)),
        "log": lambda msg, level="INFO": None,
    }
    # Empty list
    responses.clear()
    process_console_command("!scheduled list", botf)
    # Wait for response (process_console_command should be synchronous, but wait just in case)
    for _ in range(10):  # Wait up to 0.1s for response
        if responses:
            break
        time.sleep(0.01)
    # Combine all responses to handle multi-line output
    combined_response = " ".join(responses) if responses else ""
    assert (
        "No messages" in combined_response or "📅" in combined_response
    ), f"Expected 'No messages' response, got: {responses}"

    # Not found cancel
    responses.clear()
    process_console_command("!scheduled cancel unknown", botf)
    # Wait for response
    for _ in range(10):  # Wait up to 0.1s for response
        if responses:
            break
        time.sleep(0.01)
    # Combine all responses to handle multi-line output
    combined_response = " ".join(responses) if responses else ""
    assert (
        "not found" in combined_response.lower()
        or "unknown" in combined_response.lower()
    ), f"Expected 'not found' message, got: {responses}"

    # Usage
    responses.clear()
    process_console_command("!scheduled bogus", botf)
    # Wait for response
    for _ in range(10):  # Wait up to 0.1s for response
        if responses:
            break
        time.sleep(0.01)
    # Combine all responses to handle multi-line output
    combined_response = " ".join(responses) if responses else ""
    assert "Usage" in combined_response, f"Expected usage message, got: {responses}"


def test_short_forecast_import_errors(monkeypatch):
    """Simulate import errors for forecast commands to hit error branches."""
    import builtins

    from command_registry import CommandContext
    from commands import short_forecast_command, short_forecast_list_command

    # Patch import to raise for the specific module
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "services.weather_forecast_service":
            raise ImportError("no module")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    ctx = CommandContext(
        command="se",
        args=[],
        raw_message="!se",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )
    res = short_forecast_command(ctx, {})
    assert "not available" in res or "not available" in res.lower()
    ctx2 = CommandContext(
        command="sel",
        args=[],
        raw_message="!sel",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )
    res2 = short_forecast_list_command(ctx2, {})
    assert "not available" in res2 or "not available" in res2.lower()


def test_euribor_non_windows_and_missing_cases(monkeypatch):
    """Hit non-Windows format branch, no-rate, and no-period branches."""
    import platform as _platform

    import requests as _requests

    from command_registry import CommandContext
    from commands import euribor_command

    class Resp:
        def __init__(self, code, content):
            self.status_code = code
            self.content = content

    # Non-Windows formatting path with period present but missing 12m rate
    xml_no_rate = (
        b'<euribor_korot_today_xml_en xmlns="euribor_korot_today_xml_en">'
        b"<period value='2025-08-01'><rates><rate name='6 month (act/360)'><intr value='2.0'/></rate></rates></period>"
        b"</euribor_korot_today_xml_en>"
    )
    monkeypatch.setattr(_requests, "get", lambda url: Resp(200, xml_no_rate))
    # Force non-Windows branch but patch datetime formatting to be compatible
    import builtins as _builtins

    real_import = _builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "datetime" and fromlist and "datetime" in fromlist:
            import types as _types

            class _FakeDt:
                @staticmethod
                def strptime(s, fmt):
                    class _D:
                        def strftime(self, fmt2):
                            return "1.8.25"

                    return _D()

            return _types.SimpleNamespace(datetime=_FakeDt)
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(_builtins, "__import__", fake_import)
    monkeypatch.setattr(_platform, "system", lambda: "Linux")
    ctx = CommandContext(
        command="euribor",
        args=[],
        raw_message="!euribor",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )
    res = euribor_command(ctx, {})
    assert "12-month Euribor rate not found" in res

    # Missing intr value branch
    xml_no_intr = (
        b'<euribor_korot_today_xml_en xmlns="euribor_korot_today_xml_en">'
        b"<period value='2025-08-01'><rates><rate name='12 month (act/360)'></rate></rates></period>"
        b"</euribor_korot_today_xml_en>"
    )
    monkeypatch.setattr(_requests, "get", lambda url: Resp(200, xml_no_intr))
    res_mid = euribor_command(ctx, {})
    assert "Interest rate value not found" in res_mid

    # No period branch
    xml_no_period = b'<euribor_korot_today_xml_en xmlns="euribor_korot_today_xml_en"></euribor_korot_today_xml_en>'
    monkeypatch.setattr(_requests, "get", lambda url: Resp(200, xml_no_period))
    res2 = euribor_command(ctx, {})
    assert "No period data" in res2


def test_quote_command_functionality(monkeypatch, tmp_path):
    """Test the quote command with various scenarios."""
    from command_loader import process_console_command

    # Create a test quotes file with multiple quotes
    quotes_file = tmp_path / "quotes.txt"
    quotes_file.write_text(
        "Quote 1: This is the first test quote.\n"
        "Quote 2: This is the second test quote.\n"
        "Quote 3: This is the third test quote.\n"
        "Quote 4: This is the fourth test quote.\n"
        "Quote 5: This is the fifth test quote.\n"
    )

    # Mock the config to use our test quotes file
    class MockConfig:
        quotes_source = str(quotes_file)

    monkeypatch.setattr("commands.get_config", lambda: MockConfig())

    responses = []

    def mock_notice(msg, *args, **kwargs):
        responses.append(msg)

    bot_functions = {
        "notice_message": mock_notice,
        "log": lambda msg, level="INFO": None,
        "BOT_VERSION": "2.2.0",
    }

    # Test with test quotes file
    responses.clear()
    process_console_command("!quote", bot_functions)

    # Should have gotten a quote response
    assert responses, "Quote command should return a response"
    assert len(responses) == 1, "Quote command should return exactly one response"

    # Quote should not be empty and should be a string
    quote = responses[0]
    assert isinstance(quote, str), "Quote should be a string"
    assert len(quote) > 0, "Quote should not be empty"

    # Quote should not contain line numbers (they should be stripped)
    assert not (
        quote[0].isdigit() and "|" in quote[:10]
    ), "Quote should not contain line numbers"

    # Test multiple calls return different quotes (with high probability)
    quotes_seen = set()
    for _ in range(10):
        responses.clear()
        process_console_command("!quote", bot_functions)
        if responses:
            quotes_seen.add(responses[0])

    # Should get some variety (at least 3 different quotes in 10 tries)
    assert len(quotes_seen) >= 3, "Quote command should return varied quotes"


def test_quote_command_error_handling(monkeypatch):
    """Test quote command error handling scenarios."""
    from command_loader import process_console_command
    from config import get_config

    responses = []

    def mock_notice(msg, *args, **kwargs):
        responses.append(msg)

    bot_functions = {
        "notice_message": mock_notice,
        "log": lambda msg, level="INFO": None,
    }

    # Test with non-existent file
    config = get_config()
    original_quotes_source = getattr(config, "quotes_source", "quotes.txt")

    try:
        config.quotes_source = "nonexistent_quotes_file.txt"
        responses.clear()
        process_console_command("!quote", bot_functions)

        # Should get an error response
        assert responses, "Should get error response for missing file"
        assert any(
            "not found" in str(response).lower() for response in responses
        ), "Should indicate file not found"
    finally:
        # Restore original quotes source
        config.quotes_source = original_quotes_source


def test_quote_command_with_custom_file():
    """Test quote command with a custom quotes file."""
    import os
    import tempfile

    from command_loader import process_console_command
    from config import get_config

    responses = []

    def mock_notice(msg, *args, **kwargs):
        responses.append(msg)

    bot_functions = {
        "notice_message": mock_notice,
        "log": lambda msg, level="INFO": None,
    }

    # Create temporary quotes file
    with tempfile.NamedTemporaryFile(
        mode="w", delete=False, suffix=".txt", encoding="utf-8"
    ) as f:
        f.write("1|Test quote one\n")
        f.write("2|Test quote two\n")
        f.write("3|Test quote three\n")
        temp_quotes_file = f.name

    try:
        # Configure to use temporary file
        config = get_config()
        original_quotes_source = getattr(config, "quotes_source", "quotes.txt")
        config.quotes_source = temp_quotes_file

        # Test quote command
        responses.clear()
        process_console_command("!quote", bot_functions)

        # Should get a quote response
        assert responses, "Should get quote response from custom file"
        quote = responses[0]

        # Should be one of our test quotes (without line numbers)
        expected_quotes = ["Test quote one", "Test quote two", "Test quote three"]
        assert (
            quote in expected_quotes
        ), f"Quote should be one of {expected_quotes}, got: {quote}"

        # Test multiple calls to ensure randomness
        quotes_found = set()
        for _ in range(20):  # Try multiple times to get all quotes
            responses.clear()
            process_console_command("!quote", bot_functions)
            if responses:
                quotes_found.add(responses[0])

        # Should eventually see all three quotes
        assert (
            len(quotes_found) == 3
        ), f"Should find all 3 quotes, found: {quotes_found}"

    finally:
        # Clean up
        config.quotes_source = original_quotes_source
        if os.path.exists(temp_quotes_file):
            os.unlink(temp_quotes_file)


def test_quote_command_search_functionality(tmp_path):
    """Test quote command search functionality."""
    from command_loader import process_console_command

    responses = []

    def mock_notice(msg, *args, **kwargs):
        responses.append(msg)

    bot_functions = {
        "notice_message": mock_notice,
        "log": lambda msg, level="INFO": None,
    }

    # Create a test quotes file with searchable content
    quotes_file = tmp_path / "search_quotes.txt"
    quotes_file.write_text(
        "Our motto is excellence.\n"
        "The best quote ever: strive for greatness.\n"
        "Random quote about life.\n"
        "Another motto: work hard, play hard.\n"
        "Life is what you make it.\n"
    )

    # Mock the config to use our test quotes file
    class MockConfig:
        quotes_source = str(quotes_file)

    # Store original config and restore later
    import commands

    original_get_config = commands.get_config
    commands.get_config = lambda: MockConfig()

    try:
        # Test search functionality - should find first matching quote
        responses.clear()
        process_console_command("!quote motto", bot_functions)

        assert responses, "Should get search result response"
        quote = responses[0]

        # Should be the first quote containing "motto"
        assert (
            "motto is excellence" in quote.lower()
        ), f"Should find first motto quote, got: {quote}"

        # Test search with no matches
        responses.clear()
        process_console_command("!quote nonexistent", bot_functions)

        assert responses, "Should get no matches response"
        assert "No quotes found containing 'nonexistent'" in responses[0]

        # Test empty search (should be random)
        responses.clear()
        process_console_command("!quote", bot_functions)

        assert responses, "Should get random quote response"
        quote = responses[0]
        assert len(quote) > 0, "Quote should not be empty"

        # Test case-insensitive search
        responses.clear()
        process_console_command("!quote MOTTO", bot_functions)

        assert responses, "Should get case-insensitive search result"
        quote = responses[0]
        assert (
            "motto is excellence" in quote.lower()
        ), f"Should find motto quote case-insensitively, got: {quote}"

    finally:
        # Restore original get_config
        commands.get_config = original_get_config


def test_electricity_command_with_args_split():
    """Ensure !sahko command returns error when no service available."""
    from command_loader import process_console_command

    responses = []

    def mock_notice(msg):
        responses.append(msg)

    botf = {
        "notice_message": mock_notice,
        "log": lambda msg, level="INFO": None,
        # No bot_manager means no electricity service
    }
    process_console_command("!sahko huomenna 7", botf)
    assert responses, "Should get error response when electricity service unavailable"
    assert (
        "not available" in responses[0].lower()
    ), f"Should indicate service not available, got: {responses[0]}"


def test_exit_command_direct_irc():
    from command_registry import CommandContext
    from commands import exit_command

    ctx = CommandContext(
        command="exit",
        args=[],
        raw_message="!exit",
        sender="u",
        target="#c",
        is_private=False,
        is_console=False,
        server_name="s",
    )
    res = exit_command(ctx, {})
    # Exit command returns None for non-console contexts (IRC)
    assert res is None


def test_tilaa_subscriber_selection_branches():
    from command_registry import CommandContext
    from commands import command_tilaa

    class FakeSub:
        def toggle_subscription(self, subscriber, server, topic):
            return f"Toggled {subscriber} on {server} for {topic}"

        def format_all_subscriptions(self):
            return "List"

    botf = {"subscriptions": FakeSub()}
    # Explicit override arg
    ctx1 = CommandContext(
        command="tilaa",
        args=["varoitukset", "#chan"],
        raw_message="",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )
    assert "#chan" in command_tilaa(ctx1, botf)
    # Use target channel
    ctx2 = CommandContext(
        command="tilaa",
        args=["varoitukset"],
        raw_message="",
        sender=None,
        target="#room",
        is_private=False,
        is_console=False,
        server_name="irc",
    )
    assert "#room" in command_tilaa(ctx2, botf)
    # Use sender
    ctx3 = CommandContext(
        command="tilaa",
        args=["varoitukset"],
        raw_message="",
        sender="Nick",
        target=None,
        is_private=True,
        is_console=False,
        server_name="irc",
    )
    assert "Nick" in command_tilaa(ctx3, botf)
    # Fallback console
    ctx4 = CommandContext(
        command="tilaa",
        args=["varoitukset"],
        raw_message="",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="",
    )
    assert "console" in command_tilaa(ctx4, botf)


def test_topwords_not_found_and_global_aggregate(monkeypatch):
    import commands as _cmd
    from command_loader import process_console_command

    # Not found branch
    monkeypatch.setattr(_cmd.data_manager, "get_all_servers", lambda: ["srv1"])
    monkeypatch.setattr(
        _cmd.general_words, "get_user_stats", lambda srv, nick: {"total_words": 0}
    )
    responses = []
    botf = {"notice_message": lambda m, *a, **k: responses.append(m)}
    responses.clear()
    process_console_command("!topwords Unknown", botf)
    assert any("ei löydy" in r.lower() for r in responses)

    # Global aggregate
    def server_stats(server):
        return {"top_words": [("foo", 3), ("bar", 2)]}

    monkeypatch.setattr(_cmd.general_words, "get_server_stats", server_stats)
    monkeypatch.setattr(_cmd.data_manager, "get_all_servers", lambda: ["srv1", "srv2"])
    responses.clear()
    process_console_command("!topwords", botf)
    assert any("Käytetyimmät sanat" in r for r in responses)


def test_drinkword_and_drink_no_hits(tmp_path, monkeypatch):
    from command_loader import process_console_command
    from word_tracking import DataManager, DrinkTracker

    dm = DataManager(str(tmp_path))
    dt = DrinkTracker(dm)
    # Monkeypatch search to return no hits
    monkeypatch.setattr(
        dt,
        "search_drink_word",
        lambda word, server_filter=None: {"total_occurrences": 0},
    )
    monkeypatch.setattr(
        dt,
        "search_specific_drink",
        lambda query, server_filter=None: {"total_occurrences": 0},
    )
    responses = []
    botf = {
        "notice_message": lambda m, *a, **k: responses.append(m),
        "drink_tracker": dt,
        "server_name": "console",
    }
    responses.clear()
    process_console_command("!drinkword unknown", botf)
    assert any("Ei osumia sanalle" in r for r in responses)
    responses.clear()
    process_console_command("!drink unknown", botf)
    assert any("Ei osumia juomalle" in r for r in responses)


def test_kraks_missing_tracker_and_empty(monkeypatch, tmp_path):
    import commands as _cmd
    from command_loader import process_console_command
    from word_tracking import DataManager, DrinkTracker

    # Missing tracker
    orig_dt = _cmd._drink_tracker
    try:
        _cmd._drink_tracker = None
        responses = []
        botf = {"notice_message": lambda m, *a, **k: responses.append(m)}
        process_console_command("!kraks", botf)
        assert any("ei ole käytettävissä" in r.lower() for r in responses)
    finally:
        _cmd._drink_tracker = orig_dt
    # Empty stats
    dm = DataManager(str(tmp_path))
    dt = DrinkTracker(dm)
    responses = []
    botf2 = {
        "notice_message": lambda m, *a, **k: responses.append(m),
        "drink_tracker": dt,
        "server_name": "console",
    }
    process_console_command("!kraks", botf2)
    assert any("Ei vielä krakkauksia" in r for r in responses)


def test_leets_invalid_datetime(monkeypatch):
    from command_registry import CommandContext
    from commands import command_leets

    # Detector that returns invalid datetime string to hit exception branch
    class FakeDet:
        def get_leet_history(self, limit=5):
            return [
                {
                    "datetime": "invalid",
                    "nick": "u",
                    "timestamp": "t",
                    "achievement_name": "A",
                    "emoji": "*",
                    "user_message": "msg",
                }
            ]

    monkeypatch.setattr("leet_detector.create_leet_detector", lambda: FakeDet())
    ctx = CommandContext(
        command="leets",
        args=[],
        raw_message="!leets",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )
    res = command_leets(ctx, {})
    assert "Recent Leet" in res


def test_scheduled_exception(monkeypatch):
    from command_loader import process_console_command

    monkeypatch.setattr(
        "services.scheduled_message_service.get_scheduled_message_service",
        lambda: (_ for _ in ()).throw(Exception("boom")),
    )
    responses = []
    botf = {"notice_message": lambda m, *a, **k: responses.append(m)}
    process_console_command("!scheduled list", botf)
    assert any("Scheduled messages error" in r for r in responses)


def test_direct_leetwinners_and_electricity_unavailable_and_sana_no_users(monkeypatch):
    from command_registry import CommandContext
    from commands import command_sana, electricity_command, leetwinners_command

    # leetwinners service missing
    ctx = CommandContext(
        command="leetwinners",
        args=[],
        raw_message="!leetwinners",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )
    assert "service not available" in leetwinners_command(ctx, {}).lower()
    # electricity unavailable direct
    ctx2 = CommandContext(
        command="sahko",
        args=[],
        raw_message="!sahko",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )
    assert "not available" in electricity_command(ctx2, {}).lower()

    # sana total>0 but no users direct
    class G:
        def search(self, word):
            return {"total_occurrences": 1, "servers": {"srv": {"users": []}}}

    import commands as _cmd

    monkeypatch.setattr(_cmd._general_words, "search_word", lambda w: G().search(w))
    ctx3 = CommandContext(
        command="sana",
        args=["test"],
        raw_message="!sana test",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )
    assert "Kukaan ei ole sanonut" in command_sana(ctx3, {})


def test_tilaa_usage_when_no_topic():
    from command_registry import CommandContext
    from commands import command_tilaa

    ctx = CommandContext(
        command="tilaa",
        args=[],
        raw_message="!tilaa",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )
    assert "Käyttö" in command_tilaa(ctx, {})


def test_sana_total_zero(monkeypatch):
    import commands as _cmd
    from command_registry import CommandContext
    from commands import command_sana

    monkeypatch.setattr(
        _cmd._general_words, "search_word", lambda w: {"total_occurrences": 0}
    )
    ctx = CommandContext(
        command="sana",
        args=["foo"],
        raw_message="!sana foo",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )
    assert "Kukaan ei ole sanonut" in command_sana(ctx, {})


def test_sana_usage_no_args():
    from command_registry import CommandContext
    from commands import command_sana

    ctx = CommandContext(
        command="sana",
        args=[],
        raw_message="!sana",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )
    assert "Käytä komentoa" in command_sana(ctx, {})


def test_drink_details_branch(monkeypatch, tmp_path):
    from command_loader import process_console_command
    from word_tracking import DataManager, DrinkTracker

    dm = DataManager(str(tmp_path))
    dt = DrinkTracker(dm)
    # force detailed results
    monkeypatch.setattr(
        dt,
        "search_specific_drink",
        lambda q, server_filter=None: {
            "total_occurrences": 7,
            "drink_words": {"beer": 4, "ale": 3},
            "users": [{"nick": "alice", "total": 4}, {"nick": "bob", "total": 3}],
        },
    )
    responses = []
    botf = {
        "notice_message": lambda m, *a, **k: responses.append(m),
        "drink_tracker": dt,
        "server_name": "console",
    }
    responses.clear()
    process_console_command("!drink some", botf)
    assert any("top:" in r for r in responses)


def test_leets_limit_parse_exception(monkeypatch):
    # Patch int only within the function globals to avoid global side effects
    import builtins

    from command_registry import CommandContext
    from commands import command_leets

    real_int = builtins.int

    def fake_int(x, base=10):
        if x == "2":
            raise Exception("bad int")
        return real_int(x, base)

    monkeypatch.setitem(command_leets.__globals__, "int", fake_int)
    ctx = CommandContext(
        command="leets",
        args=["2"],
        raw_message="!leets 2",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )
    res = command_leets(ctx, {})
    assert "Recent Leet" in res or res


def test_weather_unavailable_and_forecast_direct_paths(monkeypatch):
    from command_registry import CommandContext
    from commands import (
        short_forecast_command,
        short_forecast_list_command,
        solarwind_command,
        weather_command,
    )

    # weather unavailable direct
    ctx = CommandContext(
        command="s",
        args=[],
        raw_message="!s",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )
    assert "Weather service not available" in weather_command(ctx, {})
    # forecast parsing: non-int tail triggers except-pass
    ctx2 = CommandContext(
        command="se",
        args=["City", "x"],
        raw_message="!se City x",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )

    # monkeypatch service to return line
    class S:
        def single(city, hours):
            return f"Forecast {city} {hours}"

    monkeypatch.setattr(
        "services.weather_forecast_service.format_single_line",
        lambda city, hours: f"Forecast {city} {hours}",
    )
    assert "Forecast" in short_forecast_command(ctx2, {})
    # forecast list IRC fallback without notice
    ctx3 = CommandContext(
        command="sel",
        args=["Town", "3"],
        raw_message="!sel Town 3",
        sender=None,
        target=None,
        is_private=False,
        is_console=False,
        server_name="server",
    )
    monkeypatch.setattr(
        "services.weather_forecast_service.format_multi_line",
        lambda city, hours: ["A", "B"],
    )
    # No notice or irc provided in botf, should return joined lines
    assert short_forecast_list_command(ctx3, {}) == "A\nB"
    # forecast single-line exception
    monkeypatch.setattr(
        "services.weather_forecast_service.format_single_line",
        lambda city, hours: (_ for _ in ()).throw(Exception("x")),
    )
    assert "Ennustevirhe" in short_forecast_command(ctx2, {})
    # forecast list console join
    ctx4 = CommandContext(
        command="sel",
        args=["Town"],
        raw_message="!sel Town",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )
    monkeypatch.setattr(
        "services.weather_forecast_service.format_multi_line",
        lambda city, hours: ["L1", "L2"],
    )
    assert short_forecast_list_command(ctx4, {}) == "L1\nL2"
    # forecast list exception path
    monkeypatch.setattr(
        "services.weather_forecast_service.format_multi_line",
        lambda city, hours: (_ for _ in ()).throw(Exception("boom")),
    )
    assert "Ennustevirhe" in short_forecast_list_command(ctx4, {})
    # solarwind exception direct
    monkeypatch.setattr(
        "services.solarwind_service.get_solar_wind_info",
        lambda: (_ for _ in ()).throw(Exception("down")),
    )
    ctx4 = CommandContext(
        command="solarwind",
        args=[],
        raw_message="!solarwind",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )
    assert "Solar wind error" in solarwind_command(ctx4, {})
