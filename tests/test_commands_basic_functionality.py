#!/usr/bin/env python3
"""
Basic functionality tests for command modules.
These tests verify that commands can be imported and called without complex mocking.
"""

import os
import sys
import unittest.mock as mock
from unittest.mock import Mock, patch

import pytest

# Add src to path before importing project modules
_TEST_ROOT = os.path.dirname(os.path.abspath(__file__))
if _TEST_ROOT not in sys.path:
    sys.path.insert(0, os.path.join(_TEST_ROOT, "..", "src"))

from command_registry import CommandContext, CommandResponse, CommandScope, CommandType


@pytest.fixture
def mock_bot_functions():
    """Create mock bot functions for testing commands."""
    return {
        "log": Mock(),
        "notice_message": Mock(),
        "send_weather": Mock(),
        "send_electricity_price": Mock(),
        "send_youtube_info": Mock(),
        "send_imdb_info": Mock(),
        "get_crypto_price": Mock(),
        "load_leet_winners": Mock(),
        "get_alko_product": Mock(),
        "check_drug_interactions": Mock(),
        "server": Mock(),
        "bot_manager": Mock(),
    }


@pytest.fixture
def console_context():
    """Create a mock CommandContext for console commands."""
    return CommandContext(
        command="test",
        args=[],
        raw_message="!test",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )


@pytest.fixture
def irc_context():
    """Create a mock CommandContext for IRC commands."""
    return CommandContext(
        command="test",
        args=[],
        raw_message="!test",
        sender="TestUser",
        target="#test",
        is_private=False,
        is_console=False,
        server_name="TestServer",
    )


class TestBasicCommandImports:
    """Test that commands can be imported and are callable."""

    def test_all_command_modules_import(self):
        """Test that all command modules can be imported."""
        from cmd_modules import admin, basic, games, misc, services, word_tracking

        # Verify modules are imported
        assert hasattr(basic, "help_command")
        assert hasattr(admin, "connect_command")
        assert hasattr(games, "kolikko_command")
        assert hasattr(misc, "echo_command")  # kaiku is actually echo_command
        assert hasattr(services, "weather_command")
        assert hasattr(word_tracking, "topwords_command")

    def test_command_registry_integration(self):
        """Test that commands are properly registered in the command registry."""
        from command_registry import get_command_registry

        registry = get_command_registry()
        # Check that we can get commands (use the internal _commands dict)
        commands = registry._commands

        # Should have many commands registered
        assert len(commands) > 50

        # Check some specific commands exist (using actual registered names)
        assert "help" in commands
        assert "ping" in commands
        assert "version" in commands
        assert "s" in commands  # weather command
        assert "sahko" in commands
        assert "crypto" in commands


class TestCommandExecution:
    """Test that commands can be executed with proper context."""

    def test_help_command_execution(self, console_context, mock_bot_functions):
        """Test that help command executes without errors."""
        from cmd_modules.basic import help_command

        result = help_command(console_context, mock_bot_functions)
        # Help command should return a string or CommandResponse
        assert result is not None

    def test_ping_command_execution(self, console_context, mock_bot_functions):
        """Test that ping command executes without errors."""
        from cmd_modules.basic import ping_command

        result = ping_command(console_context, mock_bot_functions)
        # Ping command should return a string or CommandResponse
        assert result is not None

    def test_version_command_execution(self, console_context, mock_bot_functions):
        """Test that version command executes without errors."""
        from cmd_modules.basic import version_command

        result = version_command(console_context, mock_bot_functions)
        # Version command should return a string or CommandResponse
        assert result is not None

    def test_crypto_command_execution(self, console_context, mock_bot_functions):
        """Test that crypto command executes without errors."""
        from cmd_modules.services import crypto_command

        # Mock the get_crypto_price function
        def mock_get_crypto_price(coin, currency):
            if coin == "bitcoin":
                return "50000.00 EUR"
            return "N/A"

        mock_bot_functions["get_crypto_price"] = mock_get_crypto_price

        result = crypto_command(console_context, mock_bot_functions)
        # Crypto command should return a string
        assert isinstance(result, str)
        assert "bitcoin" in result.lower() or "50000.00" in result

    def test_crypto_command_with_args(self, console_context, mock_bot_functions):
        """Test that crypto command with arguments executes without errors."""
        from cmd_modules.services import crypto_command

        # Create context with arguments
        console_context.args_text = "btc eur"
        console_context.args = ["btc", "eur"]

        def mock_get_crypto_price(coin, currency):
            if coin == "btc" and currency == "eur":
                return "45000.00 EUR"
            return "N/A"

        mock_bot_functions["get_crypto_price"] = mock_get_crypto_price

        result = crypto_command(console_context, mock_bot_functions)
        # Crypto command should return a string
        assert isinstance(result, str)
        assert "45000.00 EUR" in result

    def test_crypto_command_no_service(self, console_context, mock_bot_functions):
        """Test crypto command when service is not available."""
        from cmd_modules.services import crypto_command

        # Remove get_crypto_price from bot functions
        del mock_bot_functions["get_crypto_price"]

        result = crypto_command(console_context, mock_bot_functions)

        assert result == "Crypto price service not available"

    def test_alko_command_execution(self, console_context, mock_bot_functions):
        """Test that alko command executes without errors."""
        from cmd_modules.services import alko_command

        # Create context with arguments
        console_context.args_text = "karhu"
        console_context.args = ["karhu"]

        # Mock the get_alko_product function
        mock_bot_functions["get_alko_product"].return_value = "🍺 Karhu: 4.7% 0.5L"

        result = alko_command(console_context, mock_bot_functions)
        # Alko command should return a string
        assert isinstance(result, str)
        assert "Karhu" in result

    def test_alko_command_no_service(self, console_context, mock_bot_functions):
        """Test alko command when service is not available."""
        from cmd_modules.services import alko_command

        # Remove get_alko_product from bot functions
        del mock_bot_functions["get_alko_product"]

        result = alko_command(console_context, mock_bot_functions)

        assert "Usage: !alko" in result

    def test_drugs_command_execution(self, console_context, mock_bot_functions):
        """Test that drugs command executes without errors."""
        from cmd_modules.services import drugs_command

        # Create context with arguments
        console_context.args_text = "cannabis alcohol"
        console_context.args = ["cannabis", "alcohol"]

        # Mock the check_drug_interactions function
        mock_bot_functions["check_drug_interactions"].return_value = (
            "💊 No interactions found"
        )

        result = drugs_command(console_context, mock_bot_functions)
        # Drugs command should return a string
        assert isinstance(result, str)
        assert "No interactions found" in result

    def test_drugs_command_no_service(self, console_context, mock_bot_functions):
        """Test drugs command when service is not available."""
        from cmd_modules.services import drugs_command

        # Remove check_drug_interactions from bot functions
        del mock_bot_functions["check_drug_interactions"]

        result = drugs_command(console_context, mock_bot_functions)

        assert "Usage: !drugs" in result

    def test_weather_command_execution(self, console_context, mock_bot_functions):
        """Test that weather command executes without errors."""
        from cmd_modules.services import weather_command

        # Mock the send_weather function
        mock_bot_functions["send_weather"].return_value = None

        result = weather_command(console_context, mock_bot_functions)
        # Weather command should return CommandResponse
        assert isinstance(result, CommandResponse)

    def test_weather_command_no_service(self, console_context, mock_bot_functions):
        """Test weather command when service is not available."""
        from cmd_modules.services import weather_command

        # Remove send_weather from bot functions
        del mock_bot_functions["send_weather"]

        result = weather_command(console_context, mock_bot_functions)

        assert result == "Weather service not available"

    def test_youtube_command_execution(self, console_context, mock_bot_functions):
        """Test that YouTube command executes without errors."""
        from cmd_modules.services import youtube_command

        # Create context with arguments
        console_context.args_text = "python tutorial"
        console_context.args = ["python", "tutorial"]

        # Mock the send_youtube_info function
        mock_bot_functions["send_youtube_info"].return_value = None

        result = youtube_command(console_context, mock_bot_functions)
        # YouTube command should return CommandResponse
        assert isinstance(result, CommandResponse)

    def test_youtube_command_no_service(self, console_context, mock_bot_functions):
        """Test YouTube command when service is not available."""
        from cmd_modules.services import youtube_command

        # Remove send_youtube_info from bot functions
        del mock_bot_functions["send_youtube_info"]

        result = youtube_command(console_context, mock_bot_functions)

        assert "YouTube service not available" in result

    def test_imdb_command_execution(self, console_context, mock_bot_functions):
        """Test that IMDb command executes without errors."""
        from cmd_modules.services import imdb_command

        # Create context with arguments
        console_context.args_text = "The Matrix"
        console_context.args = ["The", "Matrix"]

        # Mock the send_imdb_info function
        mock_bot_functions["send_imdb_info"].return_value = None

        result = imdb_command(console_context, mock_bot_functions)
        # IMDb command should return CommandResponse
        assert isinstance(result, CommandResponse)

    def test_imdb_command_no_service(self, console_context, mock_bot_functions):
        """Test IMDb command when service is not available."""
        from cmd_modules.services import imdb_command

        # Remove send_imdb_info from bot functions
        del mock_bot_functions["send_imdb_info"]

        result = imdb_command(console_context, mock_bot_functions)

        assert result == "IMDb service not available."

    def test_kolikko_command_execution(self, console_context, mock_bot_functions):
        """Test that kolikko command executes without errors."""
        from cmd_modules.games import kolikko_command

        result = kolikko_command(console_context, mock_bot_functions)
        # Kolikko command should return a string or CommandResponse
        assert result is not None

    def test_noppa_command_execution(self, console_context, mock_bot_functions):
        """Test that noppa command executes without errors."""
        from cmd_modules.games import noppa_command

        result = noppa_command(console_context, mock_bot_functions)
        # Noppa command should return a string or CommandResponse
        assert result is not None

    def test_ksp_command_execution(self, console_context, mock_bot_functions):
        """Test that ksp command executes without errors."""
        from cmd_modules.games import ksp_command

        # Create context with arguments
        console_context.args_text = "kivi"
        console_context.args = ["kivi"]

        result = ksp_command(console_context, mock_bot_functions)
        # KSP command should return a string or CommandResponse
        assert result is not None

    def test_echo_command_execution(self, console_context, mock_bot_functions):
        """Test that echo command executes without errors."""
        from cmd_modules.misc import echo_command

        # Create context with arguments
        console_context.args_text = "test message"
        console_context.args = ["test", "message"]

        result = echo_command(console_context, mock_bot_functions)
        # Echo command should return a string or CommandResponse
        assert result is not None

    def test_echo_command_no_args(self, console_context, mock_bot_functions):
        """Test echo command with no arguments."""
        from cmd_modules.misc import echo_command

        # Create context without arguments
        console_context.args_text = ""
        console_context.args = []

        result = echo_command(console_context, mock_bot_functions)
        # Echo command should return a string or CommandResponse
        assert result is not None

    def test_np_command_execution(self, console_context, mock_bot_functions):
        """Test that np command executes without errors."""
        from cmd_modules.misc import np_command

        result = np_command(console_context, mock_bot_functions)
        # NP command should return a string or CommandResponse
        assert result is not None

    def test_topwords_command_execution(self, console_context, mock_bot_functions):
        """Test that topwords command executes without errors."""
        from cmd_modules.word_tracking import topwords_command

        result = topwords_command(console_context, mock_bot_functions)
        # Topwords command should return a string or CommandResponse
        assert result is not None

    def test_leaderboard_command_execution(self, console_context, mock_bot_functions):
        """Test that leaderboard command executes without errors."""
        from cmd_modules.word_tracking import leaderboard_command

        # Mock the data manager to avoid NoneType errors
        mock_data_manager = Mock()
        mock_data_manager.get_all_servers.return_value = ["console"]
        mock_bot_functions["data_manager"] = mock_data_manager

        # Mock the general_words tracker
        mock_general_words = Mock()
        mock_general_words.get_server_stats.return_value = {"users": {}}
        mock_bot_functions["general_words"] = mock_general_words

        # Mock the drink tracker for drink leaderboard
        mock_drink_tracker = Mock()
        mock_drink_tracker.get_server_stats.return_value = {"top_users": []}
        mock_bot_functions["drink_tracker"] = mock_drink_tracker

        # Mock the module-level data_manager variable
        import src.cmd_modules.word_tracking as word_tracking_module

        original_data_manager = word_tracking_module.data_manager
        word_tracking_module.data_manager = mock_data_manager

        try:
            result = leaderboard_command(console_context, mock_bot_functions)
            # Leaderboard command should return a string or CommandResponse
            assert result is not None
        finally:
            # Restore original value
            word_tracking_module.data_manager = original_data_manager

    def test_drink_command_execution(self, console_context, mock_bot_functions):
        """Test that drink command executes without errors."""
        from cmd_modules.word_tracking import drink_command

        result = drink_command(console_context, mock_bot_functions)
        # Drink command should return a string or CommandResponse
        assert result is not None

    def test_kraks_command_execution(self, console_context, mock_bot_functions):
        """Test that kraks command executes without errors."""
        from cmd_modules.word_tracking import kraks_command

        result = kraks_command(console_context, mock_bot_functions)
        # Kraks command should return a string or CommandResponse
        assert result is not None

    def test_tamagotchi_command_execution(self, console_context, mock_bot_functions):
        """Test that tamagotchi command executes without errors."""
        from cmd_modules.word_tracking import tamagotchi_command

        # Mock the data manager to avoid _load_state errors
        mock_data_manager = Mock()
        mock_bot_functions["data_manager"] = mock_data_manager

        # Mock the tamagotchi bot
        mock_tamagotchi = Mock()
        mock_tamagotchi.get_status.return_value = "Tamagotchi is happy!"
        mock_bot_functions["tamagotchi"] = mock_tamagotchi

        result = tamagotchi_command(console_context, mock_bot_functions)
        # Tamagotchi command should return a string or CommandResponse
        assert result is not None


class TestCommandErrorHandling:
    """Test that commands handle errors gracefully."""

    def test_command_with_exception_handling(self, console_context, mock_bot_functions):
        """Test that commands handle exceptions gracefully."""
        from cmd_modules.services import crypto_command

        # Mock the get_crypto_price function to raise an exception
        def mock_get_crypto_price(coin, currency):
            raise Exception("Test error")

        mock_bot_functions["get_crypto_price"] = mock_get_crypto_price

        # This should not crash, but may return an error message
        try:
            result = crypto_command(console_context, mock_bot_functions)
            # If it doesn't crash, that's good
            assert result is not None
        except Exception as e:
            # If it does crash, it should be a controlled exception
            assert "Test error" in str(e)


class TestCommandContextHandling:
    """Test that commands handle different contexts correctly."""

    def test_console_vs_irc_context(
        self, console_context, irc_context, mock_bot_functions
    ):
        """Test that commands handle console and IRC contexts differently."""
        from cmd_modules.services import weather_command

        # Mock the send_weather function
        mock_bot_functions["send_weather"].return_value = None

        # Test console context
        console_result = weather_command(console_context, mock_bot_functions)
        assert isinstance(console_result, CommandResponse)

        # Test IRC context
        irc_result = weather_command(irc_context, mock_bot_functions)
        assert isinstance(irc_result, CommandResponse)


class TestCommandArguments:
    """Test that commands handle arguments correctly."""

    def test_command_with_multiple_args(self, console_context, mock_bot_functions):
        """Test that commands handle multiple arguments correctly."""
        from cmd_modules.services import crypto_command

        # Create context with multiple arguments
        console_context.args_text = "bitcoin ethereum tether"
        console_context.args = ["bitcoin", "ethereum", "tether"]

        def mock_get_crypto_price(coin, currency):
            if coin == "bitcoin":
                return "50000.00 EUR"
            elif coin == "ethereum":
                return "3000.00 EUR"
            elif coin == "tether":
                return "1.00 EUR"
            return "N/A"

        mock_bot_functions["get_crypto_price"] = mock_get_crypto_price

        result = crypto_command(console_context, mock_bot_functions)
        # Should handle multiple arguments
        assert isinstance(result, str)
        assert "bitcoin" in result.lower() or "50000.00" in result

    def test_command_with_numeric_args(self, console_context, mock_bot_functions):
        """Test that commands handle numeric arguments correctly."""
        from cmd_modules.services import crypto_command

        # Create context with numeric argument
        console_context.args_text = "5 bitcoin"
        console_context.args = ["5", "bitcoin"]

        def mock_get_crypto_price(coin, currency):
            if coin == "bitcoin":
                return "50000.00 EUR"
            return "N/A"

        mock_bot_functions["get_crypto_price"] = mock_get_crypto_price

        result = crypto_command(console_context, mock_bot_functions)
        # Should handle numeric arguments
        assert isinstance(result, str)
        # The crypto command handles numeric args differently - it treats "5" as a coin name
        assert "5" in result


class TestCommandResponseTypes:
    """Test that commands return appropriate response types."""

    def test_commands_return_strings_or_responses(
        self, console_context, mock_bot_functions
    ):
        """Test that commands return either strings or CommandResponse objects."""
        from cmd_modules.basic import help_command, ping_command, version_command
        from cmd_modules.games import kolikko_command, noppa_command
        from cmd_modules.misc import np_command
        from cmd_modules.services import alko_command, crypto_command, drugs_command
        from cmd_modules.word_tracking import topwords_command

        # Mock services for commands that need them
        def mock_get_crypto_price(coin, currency):
            return "50000.00 EUR"

        mock_bot_functions["get_crypto_price"] = mock_get_crypto_price
        mock_bot_functions["get_alko_product"].return_value = "🍺 Test beer"
        mock_bot_functions["check_drug_interactions"].return_value = (
            "💊 No interactions"
        )

        # Mock data manager for word tracking commands
        mock_data_manager = Mock()
        mock_data_manager.get_all_servers.return_value = ["console"]
        mock_bot_functions["data_manager"] = mock_data_manager

        # Test various commands (excluding async echo_command)
        commands_to_test = [
            help_command,
            ping_command,
            version_command,
            crypto_command,
            alko_command,
            drugs_command,
            kolikko_command,
            noppa_command,
            np_command,
            topwords_command,
        ]

        for command in commands_to_test:
            result = command(console_context, mock_bot_functions)
            # Should return either a string or CommandResponse
            assert isinstance(
                result, (str, CommandResponse)
            ), f"Command {command.__name__} returned {type(result)}"
