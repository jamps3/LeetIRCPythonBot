#!/usr/bin/env python3
"""
Comprehensive tests for service commands in cmd_modules/services.py

These tests actually test the command functionality, not just existence.
"""

import os
import sys
import unittest.mock as mock
from datetime import datetime, timedelta
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


class TestWeatherCommand:
    """Tests for the !s (weather) command."""

    def test_weather_command_console(self, console_context, mock_bot_functions):
        """Test weather command from console."""
        from cmd_modules.services import weather_command

        # Mock the send_weather function
        mock_bot_functions["send_weather"].return_value = None

        result = weather_command(console_context, mock_bot_functions)

        # Should return no_response since service handles output
        assert isinstance(result, CommandResponse)
        assert result.message is None
        mock_bot_functions["send_weather"].assert_called_once()

    def test_weather_command_irc(self, irc_context, mock_bot_functions):
        """Test weather command from IRC."""
        from cmd_modules.services import weather_command

        # Mock the send_weather function
        mock_bot_functions["send_weather"].return_value = None

        result = weather_command(irc_context, mock_bot_functions)

        # Should return no_response since service handles output
        assert isinstance(result, CommandResponse)
        assert result.message is None
        mock_bot_functions["send_weather"].assert_called_once()

    def test_weather_command_no_service(self, console_context, mock_bot_functions):
        """Test weather command when service is not available."""
        from cmd_modules.services import weather_command

        # Remove send_weather from bot functions
        del mock_bot_functions["send_weather"]

        result = weather_command(console_context, mock_bot_functions)

        assert result == "Weather service not available"


class TestElectricityCommand:
    """Tests for the !sahko (electricity) command."""

    def test_electricity_command_console_no_args(
        self, console_context, mock_bot_functions
    ):
        """Test electricity command from console with no arguments."""
        from cmd_modules.services import electricity_command

        # Mock the electricity service
        with patch(
            "services.electricity_service.create_electricity_service"
        ) as mock_service_class, patch("config.get_api_key") as mock_get_api_key:

            mock_get_api_key.return_value = "test_api_key"
            mock_service = Mock()
            mock_service_class.return_value = mock_service

            # Mock parse_command_args to return default values
            mock_service.parse_command_args.return_value = {
                "error": None,
                "show_stats": False,
                "show_all_hours": False,
                "date": datetime.now(),
                "is_tomorrow": False,
                "hour": None,
                "quarter": None,
            }

            # Mock get_electricity_price to return a test result
            mock_service.get_electricity_price.return_value = {
                "error": False,
                "message": "Test price message",
            }
            mock_service.format_price_message.return_value = "Test price message"

            result = electricity_command(console_context, mock_bot_functions)

            assert result == "Test price message"
            mock_service.get_electricity_price.assert_called_once()

    def test_electricity_command_console_with_args(
        self, console_context, mock_bot_functions
    ):
        """Test electricity command from console with arguments."""
        from cmd_modules.services import electricity_command

        # Create context with arguments
        console_context.args_text = "huomenna 15"
        console_context.args = ["huomenna", "15"]

        with patch(
            "services.electricity_service.create_electricity_service"
        ) as mock_service_class, patch("config.get_api_key") as mock_get_api_key:

            mock_get_api_key.return_value = "test_api_key"
            mock_service = Mock()
            mock_service_class.return_value = mock_service

            # Mock parse_command_args to return stats values
            mock_service.parse_command_args.return_value = {
                "error": None,
                "show_stats": True,
                "show_all_hours": False,
                "date": datetime.now(),
                "is_tomorrow": True,
                "hour": 15,
                "quarter": None,
            }

            # Mock get_price_statistics to return test data
            mock_service.get_price_statistics.return_value = {
                "min_price": 10.0,
                "max_price": 50.0,
                "avg_price": 30.0,
                "current_price": 25.0,
                "prices": [10.0, 20.0, 30.0, 40.0, 50.0],
            }
            mock_service.format_statistics_message.return_value = "Test stats message"

            result = electricity_command(console_context, mock_bot_functions)

            assert result == "Test stats message"
            mock_service.get_price_statistics.assert_called_once()

    def test_electricity_command_irc(self, irc_context, mock_bot_functions):
        """Test electricity command from IRC."""
        from cmd_modules.services import electricity_command

        # Mock the send_electricity_price function
        mock_bot_functions["send_electricity_price"].return_value = None

        result = electricity_command(irc_context, mock_bot_functions)

        # Should return no_response since service handles output
        assert isinstance(result, CommandResponse)
        assert result.message is None
        mock_bot_functions["send_electricity_price"].assert_called_once()

    def test_electricity_command_no_api_key(self, console_context, mock_bot_functions):
        """Test electricity command when API key is not configured."""
        from cmd_modules.services import electricity_command

        with patch("cmd_modules.services.get_api_key") as mock_get_api_key:
            mock_get_api_key.return_value = None

            result = electricity_command(console_context, mock_bot_functions)

            assert "Electricity service not available" in result
            assert "ELECTRICITY_API_KEY" in result


class TestCryptoCommand:
    """Tests for the !crypto command."""

    def test_crypto_command_default(self, console_context, mock_bot_functions):
        """Test crypto command with default top coins."""
        from cmd_modules.services import crypto_command

        # Mock get_crypto_price for multiple coins
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

        assert "bitcoin" in result
        assert "ethereum" in result
        assert "tether" in result
        assert "50000.00 EUR" in result

    def test_crypto_command_specific_coin(self, console_context, mock_bot_functions):
        """Test crypto command with specific coin."""
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

        assert "💸 BTC: 45000.00 EUR" == result

    def test_crypto_command_no_service(self, console_context, mock_bot_functions):
        """Test crypto command when service is not available."""
        from cmd_modules.services import crypto_command

        # Remove get_crypto_price from bot functions
        del mock_bot_functions["get_crypto_price"]

        result = crypto_command(console_context, mock_bot_functions)

        assert result == "Crypto price service not available"


class TestYouTubeCommand:
    """Tests for the !youtube command."""

    def test_youtube_command_with_query(self, console_context, mock_bot_functions):
        """Test YouTube command with search query."""
        from cmd_modules.services import youtube_command

        # Create context with arguments
        console_context.args_text = "python tutorial"
        console_context.args = ["python", "tutorial"]

        # Mock the send_youtube_info function
        mock_bot_functions["send_youtube_info"].return_value = None

        result = youtube_command(console_context, mock_bot_functions)

        # Should return no_response since service handles output
        assert isinstance(result, CommandResponse)
        assert result.message is None
        mock_bot_functions["send_youtube_info"].assert_called_once_with(
            mock_bot_functions["server"],
            None,  # target is None for console
            "python tutorial",
            5,  # default max_results
        )

    def test_youtube_command_with_number(self, console_context, mock_bot_functions):
        """Test YouTube command with number parameter."""
        from cmd_modules.services import youtube_command

        # Create context with arguments including number
        console_context.args_text = "5 python tutorial"
        console_context.args = ["5", "python", "tutorial"]

        # Mock the send_youtube_info function
        mock_bot_functions["send_youtube_info"].return_value = None

        result = youtube_command(console_context, mock_bot_functions)

        # Should return no_response since service handles output
        assert isinstance(result, CommandResponse)
        assert result.message is None
        mock_bot_functions["send_youtube_info"].assert_called_once_with(
            mock_bot_functions["server"],
            None,  # target is None for console
            "python tutorial",
            5,  # parsed max_results
        )

    def test_youtube_command_no_service(self, console_context, mock_bot_functions):
        """Test YouTube command when service is not available."""
        from cmd_modules.services import youtube_command

        # Remove send_youtube_info from bot functions
        del mock_bot_functions["send_youtube_info"]

        result = youtube_command(console_context, mock_bot_functions)

        assert "YouTube service not available" in result


class TestAlkoCommand:
    """Tests for the !alko command."""

    def test_alko_command_with_product(self, console_context, mock_bot_functions):
        """Test Alko command with product name."""
        from cmd_modules.services import alko_command

        # Create context with arguments
        console_context.args_text = "karhu"
        console_context.args = ["karhu"]

        # Mock the get_alko_product function
        mock_bot_functions["get_alko_product"].return_value = "🍺 Karhu: 4.7% 0.5L"

        result = alko_command(console_context, mock_bot_functions)

        assert result == "🍺 Karhu: 4.7% 0.5L"
        mock_bot_functions["get_alko_product"].assert_called_once_with("karhu")

    def test_alko_command_no_service(self, console_context, mock_bot_functions):
        """Test Alko command when service is not available."""
        from cmd_modules.services import alko_command

        # Remove get_alko_product from bot functions
        del mock_bot_functions["get_alko_product"]

        result = alko_command(console_context, mock_bot_functions)

        assert "Alko service not available" in result


class TestDrugsCommand:
    """Tests for the !drugs command."""

    def test_drugs_command_with_drugs(self, console_context, mock_bot_functions):
        """Test drugs command with drug names."""
        from cmd_modules.services import drugs_command

        # Create context with arguments
        console_context.args_text = "cannabis alcohol"
        console_context.args = ["cannabis", "alcohol"]

        # Mock the check_drug_interactions function
        mock_bot_functions["check_drug_interactions"].return_value = (
            "💊 No interactions found"
        )

        result = drugs_command(console_context, mock_bot_functions)

        assert result == "💊 No interactions found"
        mock_bot_functions["check_drug_interactions"].assert_called_once_with(
            "cannabis alcohol"
        )

    def test_drugs_command_no_service(self, console_context, mock_bot_functions):
        """Test drugs command when service is not available."""
        from cmd_modules.services import drugs_command

        # Remove check_drug_interactions from bot functions
        del mock_bot_functions["check_drug_interactions"]

        result = drugs_command(console_context, mock_bot_functions)

        assert "Drug service not available" in result


class TestTeachCommand:
    """Tests for the !teach command."""

    def test_teach_command_add_teaching(self, irc_context, mock_bot_functions):
        """Test teach command to add a new teaching."""
        from cmd_modules.services import teach_command

        # Mock the data manager
        with patch("cmd_modules.services.get_data_manager") as mock_get_data_manager:
            mock_data_manager = Mock()
            mock_get_data_manager.return_value = mock_data_manager
            mock_data_manager.add_teaching.return_value = 1

            # Create context with arguments
            irc_context.args_text = "The capital of Finland is Helsinki"
            irc_context.args = ["The", "capital", "of", "Finland", "is", "Helsinki"]

            result = teach_command(irc_context, mock_bot_functions)

            assert "Added teaching #1" in result
            mock_data_manager.add_teaching.assert_called_once_with(
                "The capital of Finland is Helsinki", "TestUser"
            )

    def test_teach_command_list_teachings(self, irc_context, mock_bot_functions):
        """Test teach command to list teachings."""
        from cmd_modules.services import teach_command

        # Mock the data manager
        with patch("cmd_modules.services.get_data_manager") as mock_get_data_manager:
            mock_data_manager = Mock()
            mock_get_data_manager.return_value = mock_data_manager
            mock_data_manager.get_teachings.return_value = [
                {"id": 1, "content": "Test teaching 1", "added_by": "User1"},
                {"id": 2, "content": "Test teaching 2", "added_by": "User2"},
            ]

            # Create context without arguments (list mode)
            irc_context.args_text = ""
            irc_context.args = []

            result = teach_command(irc_context, mock_bot_functions)

            assert "📚 Teachings:" in result
            assert "Test teaching 1" in result
            assert "Test teaching 2" in result
            mock_data_manager.get_teachings.assert_called_once()

    def test_teach_command_no_teachings(self, irc_context, mock_bot_functions):
        """Test teach command when no teachings exist."""
        from cmd_modules.services import teach_command

        # Mock the data manager
        with patch("cmd_modules.services.get_data_manager") as mock_get_data_manager:
            mock_data_manager = Mock()
            mock_get_data_manager.return_value = mock_data_manager
            mock_data_manager.get_teachings.return_value = []

            # Create context without arguments (list mode)
            irc_context.args_text = ""
            irc_context.args = []

            result = teach_command(irc_context, mock_bot_functions)

            assert "No teachings stored yet" in result


class TestUnlearnCommand:
    """Tests for the !unlearn command."""

    def test_unlearn_command_remove_teaching(self, irc_context, mock_bot_functions):
        """Test unlearn command to remove a teaching."""
        from cmd_modules.services import unlearn_command

        # Mock the data manager
        with patch("cmd_modules.services.get_data_manager") as mock_get_data_manager:
            mock_data_manager = Mock()
            mock_get_data_manager.return_value = mock_data_manager
            mock_data_manager.get_teaching_by_id.return_value = {
                "id": 1,
                "content": "Test teaching to remove",
                "added_by": "User1",
            }
            mock_data_manager.remove_teaching.return_value = True

            # Create context with teaching ID
            irc_context.args_text = "1"
            irc_context.args = ["1"]

            result = unlearn_command(irc_context, mock_bot_functions)

            assert "Removed teaching #1" in result
            assert "Test teaching to remove" in result
            mock_data_manager.get_teaching_by_id.assert_called_once_with(1)
            mock_data_manager.remove_teaching.assert_called_once_with(1)

    def test_unlearn_command_invalid_id(self, irc_context, mock_bot_functions):
        """Test unlearn command with invalid ID."""
        from cmd_modules.services import unlearn_command

        # Create context with invalid ID
        irc_context.args_text = "abc"
        irc_context.args = ["abc"]

        result = unlearn_command(irc_context, mock_bot_functions)

        assert "Invalid teaching ID" in result

    def test_unlearn_command_teaching_not_found(self, irc_context, mock_bot_functions):
        """Test unlearn command when teaching is not found."""
        from cmd_modules.services import unlearn_command

        # Mock the data manager
        with patch("cmd_modules.services.get_data_manager") as mock_get_data_manager:
            mock_data_manager = Mock()
            mock_get_data_manager.return_value = mock_data_manager
            mock_data_manager.get_teaching_by_id.return_value = None

            # Create context with teaching ID
            irc_context.args_text = "999"
            irc_context.args = ["999"]

            result = unlearn_command(irc_context, mock_bot_functions)

            assert "not found" in result
            mock_data_manager.get_teaching_by_id.assert_called_once_with(999)


class TestOtiedoteCommand:
    """Tests for the !otiedote command."""

    def test_otiedote_command_latest(self, console_context, mock_bot_functions):
        """Test otiedote command to show latest release."""
        from cmd_modules.services import otiedote_command

        # Mock the otiedote service
        with patch(
            "cmd_modules.services.create_otiedote_service"
        ) as mock_service_class, patch(
            "cmd_modules.services.get_config"
        ) as mock_get_config:

            mock_config = Mock()
            mock_get_config.return_value = mock_config

            mock_service = Mock()
            mock_service_class.return_value = mock_service

            # Mock load_otiedote_data to return test data
            mock_service.load_otiedote_data.return_value = [
                {
                    "id": 1,
                    "title": "Test Otiedote",
                    "content": "This is a test otiedote content",
                    "url": "https://example.com/otiedote/1",
                }
            ]

            result = otiedote_command(console_context, mock_bot_functions)

            assert "Test Otiedote" in result
            assert "This is a test otiedote content" in result
            assert "https://example.com/otiedote/1" in result

    def test_otiedote_command_specific_number(
        self, console_context, mock_bot_functions
    ):
        """Test otiedote command with specific release number."""
        from cmd_modules.services import otiedote_command

        # Create context with arguments
        console_context.args_text = "#5"
        console_context.args = ["#5"]

        # Mock the otiedote service
        with patch(
            "cmd_modules.services.create_otiedote_service"
        ) as mock_service_class, patch(
            "cmd_modules.services.get_config"
        ) as mock_get_config:

            mock_config = Mock()
            mock_get_config.return_value = mock_config

            mock_service = Mock()
            mock_service_class.return_value = mock_service

            # Mock load_otiedote_data to return test data
            mock_service.load_otiedote_data.return_value = [
                {
                    "id": 5,
                    "title": "Test Otiedote #5",
                    "content": "This is test otiedote content for release 5",
                    "url": "https://example.com/otiedote/5",
                }
            ]

            result = otiedote_command(console_context, mock_bot_functions)

            assert "Test Otiedote #5" in result
            assert "This is test otiedote content for release 5" in result
            assert "https://example.com/otiedote/5" in result

    def test_otiedote_command_no_data(self, console_context, mock_bot_functions):
        """Test otiedote command when no data is available."""
        from cmd_modules.services import otiedote_command

        # Mock the otiedote service
        with patch(
            "cmd_modules.services.create_otiedote_service"
        ) as mock_service_class, patch(
            "cmd_modules.services.get_config"
        ) as mock_get_config:

            mock_config = Mock()
            mock_get_config.return_value = mock_config

            mock_service = Mock()
            mock_service_class.return_value = mock_service

            # Mock load_otiedote_data to return empty list
            mock_service.load_otiedote_data.return_value = []

            result = otiedote_command(console_context, mock_bot_functions)

            assert "No otiedote data available" in result


class TestEurojackpotCommand:
    """Tests for the !eurojackpot command."""

    def test_eurojackpot_command_default(self, console_context, mock_bot_functions):
        """Test eurojackpot command with default behavior."""
        from cmd_modules.services import command_eurojackpot

        # Mock the eurojackpot service
        with patch(
            "cmd_modules.services.get_eurojackpot_service"
        ) as mock_service_class:
            mock_service = Mock()
            mock_service_class.return_value = mock_service

            # Mock get_eurojackpot_numbers to return test data
            mock_service.get_eurojackpot_numbers.return_value = (
                "Next draw: 1, 2, 3, 4, 5 + 1, 2"
            )

            result = command_eurojackpot(console_context, mock_bot_functions)

            assert "Next draw:" in result
            assert "1, 2, 3, 4, 5" in result

    def test_eurojackpot_command_results(self, console_context, mock_bot_functions):
        """Test eurojackpot command with results subcommand."""
        from cmd_modules.services import command_eurojackpot

        # Create context with arguments
        console_context.args_text = "tulokset"
        console_context.args = ["tulokset"]

        # Mock the eurojackpot service
        with patch(
            "cmd_modules.services.get_eurojackpot_service"
        ) as mock_service_class:
            mock_service = Mock()
            mock_service_class.return_value = mock_service

            # Mock get_eurojackpot_results to return test data
            mock_service.get_eurojackpot_results.return_value = (
                "Last draw: 1, 2, 3, 4, 5 + 1, 2"
            )

            result = command_eurojackpot(console_context, mock_bot_functions)

            assert "Last draw:" in result
            assert "1, 2, 3, 4, 5" in result

    def test_eurojackpot_command_error(self, console_context, mock_bot_functions):
        """Test eurojackpot command with error handling."""
        from cmd_modules.services import command_eurojackpot

        # Mock the eurojackpot service to raise an exception
        with patch(
            "cmd_modules.services.get_eurojackpot_service"
        ) as mock_service_class:
            mock_service_class.side_effect = Exception("Service error")

            result = command_eurojackpot(console_context, mock_bot_functions)

            assert "Eurojackpot error" in result
            assert "Service error" in result


class TestTrainsCommand:
    """Tests for the !junat (trains) command."""

    def test_trains_command_default(self, console_context, mock_bot_functions):
        """Test trains command with default station."""
        from cmd_modules.services import trains_command

        # Mock the trains service
        with patch("cmd_modules.services.get_trains_for_station") as mock_get_trains:
            mock_get_trains.return_value = "Next trains from Joensuu: Train 1, Train 2"

            result = trains_command(console_context, mock_bot_functions)

            assert "Next trains from Joensuu:" in result
            assert "Train 1" in result
            assert "Train 2" in result

    def test_trains_command_specific_station(self, console_context, mock_bot_functions):
        """Test trains command with specific station."""
        from cmd_modules.services import trains_command

        # Create context with arguments
        console_context.args_text = "Helsinki"
        console_context.args = ["Helsinki"]

        # Mock the trains service
        with patch("cmd_modules.services.get_trains_for_station") as mock_get_trains:
            mock_get_trains.return_value = "Next trains from Helsinki: Train A, Train B"

            result = trains_command(console_context, mock_bot_functions)

            assert "Next trains from Helsinki:" in result
            assert "Train A" in result
            assert "Train B" in result

    def test_trains_command_arrivals(self, console_context, mock_bot_functions):
        """Test trains command with arrivals subcommand."""
        from cmd_modules.services import trains_command

        # Create context with arguments
        console_context.args_text = "saapuvat Helsinki"
        console_context.args = ["saapuvat", "Helsinki"]

        # Mock the trains service
        with patch(
            "services.digitraffic_service.get_arrivals_for_station"
        ) as mock_get_arrivals:
            mock_get_arrivals.return_value = (
                "Arriving trains to Helsinki: Train X, Train Y"
            )

            result = trains_command(console_context, mock_bot_functions)

            assert "Arriving trains to Helsinki:" in result
            assert "Train X" in result
            assert "Train Y" in result


class TestImdbCommand:
    """Tests for the !imdb command."""

    def test_imdb_command_with_title(self, console_context, mock_bot_functions):
        """Test IMDb command with movie title."""
        from cmd_modules.services import imdb_command

        # Create context with arguments
        console_context.args_text = "The Matrix"
        console_context.args = ["The", "Matrix"]

        # Mock the send_imdb_info function
        mock_bot_functions["send_imdb_info"].return_value = None

        result = imdb_command(console_context, mock_bot_functions)

        # Should return no_response since service handles output
        assert isinstance(result, CommandResponse)
        assert result.message is None
        mock_bot_functions["send_imdb_info"].assert_called_once_with(
            mock_bot_functions["server"],
            None,  # target is None for console
            "The Matrix",
        )

    def test_imdb_command_no_service(self, console_context, mock_bot_functions):
        """Test IMDb command when service is not available."""
        from cmd_modules.services import imdb_command

        # Remove send_imdb_info from bot functions
        del mock_bot_functions["send_imdb_info"]

        result = imdb_command(console_context, mock_bot_functions)

        assert result == "IMDb service not available"


class TestLeetwinnersCommand:
    """Tests for the !leetwinners command."""

    def test_leetwinners_command_default(self, console_context, mock_bot_functions):
        """Test leetwinners command with default behavior."""
        from cmd_modules.services import leetwinners_command

        # Mock the load_leet_winners function
        mock_bot_functions["load_leet_winners"].return_value = {
            "User1": {"first": 5, "last": 3, "multileet": 2},
            "User2": {"first": 2, "last": 4, "multileet": 1},
        }

        result = leetwinners_command(console_context, mock_bot_functions)

        assert "User1" in result
        assert "User2" in result
        assert "5" in result  # User1's first count
        assert "4" in result  # User2's last count

    def test_leetwinners_command_last(self, console_context, mock_bot_functions):
        """Test leetwinners command with 'last' parameter."""
        from cmd_modules.services import leetwinners_command

        # Create context with arguments
        console_context.args_text = "last"
        console_context.args = ["last"]

        # Mock the load_leet_winners function
        mock_bot_functions["load_leet_winners"].return_value = {
            "Beiki": {"first": 1, "last": 2, "multileet": 1},
            "Beici": {"first": 0, "last": 1, "multileet": 0},
            "Beibi": {"first": 2, "last": 0, "multileet": 1},
        }

        result = leetwinners_command(console_context, mock_bot_functions)

        assert "Beiki" in result
        assert "Beici" in result
        assert "Beibi" in result
        assert "ensimmäinen" in result
        assert "viimeinen" in result
        assert "multileet" in result

    def test_leetwinners_command_no_data(self, console_context, mock_bot_functions):
        """Test leetwinners command when no data is available."""
        from cmd_modules.services import leetwinners_command

        # Mock the load_leet_winners function to return empty data
        mock_bot_functions["load_leet_winners"].return_value = {}

        result = leetwinners_command(console_context, mock_bot_functions)

        assert "No leet winners recorded yet" in result


class TestEuriborCommand:
    """Tests for the !euribor command."""

    def test_euribor_command_success(self, console_context, mock_bot_functions):
        """Test euribor command with successful API response."""
        from cmd_modules.services import euribor_command

        # Mock requests.get to return a successful response
        with patch("cmd_modules.services.requests.get") as mock_get:
            # Create a mock XML response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.content = b"""
            <ns:period value="2023-03-01">
                <ns:rate name="12 month (act/360)">
                    <ns:intr value="3.5"/>
                </ns:rate>
            </ns:period>
            """
            mock_get.return_value = mock_response

            result = euribor_command(console_context, mock_bot_functions)

            assert "12kk Euribor:" in result
            assert "3.5%" in result

    def test_euribor_command_api_error(self, console_context, mock_bot_functions):
        """Test euribor command with API error."""
        from cmd_modules.services import euribor_command

        # Mock requests.get to return an error response
        with patch("cmd_modules.services.requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_get.return_value = mock_response

            result = euribor_command(console_context, mock_bot_functions)

            assert "Failed to retrieve XML data" in result
            assert "500" in result


class TestUrlCommand:
    """Tests for the !url command."""

    def test_url_command_stats(self, console_context, mock_bot_functions):
        """Test url command with stats subcommand."""
        from cmd_modules.services import url_command

        # Mock the url tracker service
        with patch(
            "cmd_modules.services.create_url_tracker_service"
        ) as mock_service_class:
            mock_service = Mock()
            mock_service_class.return_value = mock_service

            # Mock get_stats to return test data
            mock_service.get_stats.return_value = {
                "total_urls": 100,
                "total_posts": 500,
                "most_popular_url": "https://example.com",
                "most_popular_count": 10,
                "oldest_url": "https://old.example.com",
                "oldest_timestamp": "2023-01-01T00:00:00Z",
            }

            # Create context with arguments
            console_context.args_text = "stats"
            console_context.args = ["stats"]

            result = url_command(console_context, mock_bot_functions)

            assert "URL tracking:" in result
            assert "100 URLs" in result
            assert "500 posts" in result
            assert "https://example.com" in result

    def test_url_command_search(self, console_context, mock_bot_functions):
        """Test url command with search subcommand."""
        from cmd_modules.services import url_command

        # Mock the url tracker service
        with patch(
            "cmd_modules.services.create_url_tracker_service"
        ) as mock_service_class:
            mock_service = Mock()
            mock_service_class.return_value = mock_service

            # Mock find_closest_match to return test data
            mock_service.find_closest_match.return_value = (
                "https://example.com/test",
                {
                    "posters": [
                        {"timestamp": "2023-01-01T00:00:00", "user": "TestUser"}
                    ],
                    "channels": {},
                },
            )

            # Create context with arguments
            console_context.args_text = "search example.com"
            console_context.args = ["search", "example.com"]

            result = url_command(console_context, mock_bot_functions)

            assert "https://example.com/test" in result

    def test_url_command_no_service(self, console_context, mock_bot_functions):
        """Test url command when service is not available."""
        from cmd_modules.services import url_command

        # Mock the url tracker service to raise an exception
        with patch(
            "cmd_modules.services.create_url_tracker_service"
        ) as mock_service_class:
            mock_service_class.side_effect = Exception("Service error")

            result = url_command(console_context, mock_bot_functions)

            assert "Error:" in result
            assert "Service error" in result


class TestWrapCommand:
    """Tests for the !wrap command."""

    def test_wrap_command_console(self, console_context, mock_bot_functions):
        """Test wrap command from console."""
        from cmd_modules.services import wrap_command

        # Mock the TUI instance
        with patch("cmd_modules.services._current_tui") as mock_tui:
            mock_tui_instance = Mock()
            mock_tui.return_value = mock_tui_instance

            result = wrap_command(console_context, mock_bot_functions)

            # Should return empty string since toggle_wrap handles the logging
            assert result == ""
            mock_tui_instance.toggle_wrap.assert_called_once()

    def test_wrap_command_no_tui(self, console_context, mock_bot_functions):
        """Test wrap command when TUI is not available."""
        from cmd_modules.services import wrap_command

        # Mock the TUI instance to be None
        with patch("cmd_modules.services._current_tui", None):
            result = wrap_command(console_context, mock_bot_functions)

            assert result == "TUI not available"


class TestTilaaCommand:
    """Tests for the !tilaa (subscribe) command."""

    def test_tilaa_command_list(self, console_context, mock_bot_functions):
        """Test tilaa command with list subcommand."""
        from cmd_modules.services import command_tilaa

        # Mock the subscriptions service
        mock_subscriptions = Mock()
        mock_subscriptions.format_all_subscriptions.return_value = (
            "Current subscriptions: varoitukset, onnettomuustiedotteet"
        )
        mock_bot_functions["subscriptions"] = mock_subscriptions

        # Create context with arguments
        console_context.args_text = "list"
        console_context.args = ["list"]

        result = command_tilaa(console_context, mock_bot_functions)

        assert "Current subscriptions:" in result
        assert "varoitukset" in result
        assert "onnettomuustiedotteet" in result

    def test_tilaa_command_toggle_subscription(
        self, console_context, mock_bot_functions
    ):
        """Test tilaa command to toggle subscription."""
        from cmd_modules.services import command_tilaa

        # Mock the subscriptions service
        mock_subscriptions = Mock()
        mock_subscriptions.toggle_subscription.return_value = (
            "Subscribed to varoitukset on #test"
        )
        mock_bot_functions["subscriptions"] = mock_subscriptions

        # Create context with arguments
        console_context.args_text = "varoitukset"
        console_context.args = ["varoitukset"]

        result = command_tilaa(console_context, mock_bot_functions)

        assert "Subscribed to varoitukset" in result
        mock_subscriptions.toggle_subscription.assert_called_once_with(
            "#test", "TestServer", "varoitukset"
        )

    def test_tilaa_command_no_service(self, console_context, mock_bot_functions):
        """Test tilaa command when service is not available."""
        from cmd_modules.services import command_tilaa

        result = command_tilaa(console_context, mock_bot_functions)

        assert "Subscription service is not available" in result


class TestSolarwindCommand:
    """Tests for the !solarwind command."""

    def test_solarwind_command_success(self, console_context, mock_bot_functions):
        """Test solarwind command with successful API response."""
        from cmd_modules.services import solarwind_command

        # Mock the solarwind service
        with patch("cmd_modules.services.get_solar_wind_info") as mock_get_info:
            mock_get_info.return_value = "Solar wind speed: 400 km/s, Density: 5 p/cm³"

            result = solarwind_command(console_context, mock_bot_functions)

            assert "Solar wind speed:" in result
            assert "400 km/s" in result
            assert "Density:" in result

    def test_solarwind_command_error(self, console_context, mock_bot_functions):
        """Test solarwind command with error handling."""
        from cmd_modules.services import solarwind_command

        # Mock the solarwind service to raise an exception
        with patch("cmd_modules.services.get_solar_wind_info") as mock_get_info:
            mock_get_info.side_effect = Exception("API error")

            result = solarwind_command(console_context, mock_bot_functions)

            assert "Solar wind error:" in result
            assert "API error" in result


class TestShortForecastCommand:
    """Tests for the !se (short forecast) command."""

    def test_short_forecast_command_default(self, console_context, mock_bot_functions):
        """Test short forecast command with default parameters."""
        from cmd_modules.services import short_forecast_command

        # Mock the weather forecast service
        with patch("cmd_modules.services.format_single_line") as mock_format:
            mock_format.return_value = "Joensuu: 15°C, cloudy, wind 5 m/s"

            result = short_forecast_command(console_context, mock_bot_functions)

            assert "Joensuu:" in result
            assert "15°C" in result
            assert "cloudy" in result
            mock_format.assert_called_once_with(None, None)

    def test_short_forecast_command_with_params(
        self, console_context, mock_bot_functions
    ):
        """Test short forecast command with city and hours parameters."""
        from cmd_modules.services import short_forecast_command

        # Create context with arguments
        console_context.args_text = "Helsinki 12"
        console_context.args = ["Helsinki", "12"]

        # Mock the weather forecast service
        with patch("cmd_modules.services.format_single_line") as mock_format:
            mock_format.return_value = "Helsinki: 12°C, sunny, wind 3 m/s"

            result = short_forecast_command(console_context, mock_bot_functions)

            assert "Helsinki:" in result
            assert "12°C" in result
            assert "sunny" in result
            mock_format.assert_called_once_with("Helsinki", 12)


class TestShortForecastListCommand:
    """Tests for the !sel (short forecast list) command."""

    def test_short_forecast_list_command_default(
        self, console_context, mock_bot_functions
    ):
        """Test short forecast list command with default parameters."""
        from cmd_modules.services import short_forecast_list_command

        # Mock the weather forecast service
        with patch("cmd_modules.services.format_multi_line") as mock_format:
            mock_format.return_value = [
                "Joensuu: 15°C, cloudy",
                "Joensuu: 16°C, partly cloudy",
                "Joensuu: 14°C, rain",
            ]

            result = short_forecast_list_command(console_context, mock_bot_functions)

            assert "Joensuu:" in result
            assert "15°C" in result
            assert "16°C" in result
            assert "14°C" in result
            mock_format.assert_called_once_with(None, None)

    def test_short_forecast_list_command_with_params(
        self, console_context, mock_bot_functions
    ):
        """Test short forecast list command with city and hours parameters."""
        from cmd_modules.services import short_forecast_list_command

        # Create context with arguments
        console_context.args_text = "Helsinki 6"
        console_context.args = ["Helsinki", "6"]

        # Mock the weather forecast service
        with patch("cmd_modules.services.format_multi_line") as mock_format:
            mock_format.return_value = [
                "Helsinki: 12°C, sunny",
                "Helsinki: 13°C, partly sunny",
            ]

            result = short_forecast_list_command(console_context, mock_bot_functions)

            assert "Helsinki:" in result
            assert "12°C" in result
            assert "13°C" in result
            mock_format.assert_called_once_with("Helsinki", 6)
