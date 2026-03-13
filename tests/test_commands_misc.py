#!/usr/bin/env python3
"""
Tests for miscellaneous service commands: leetwinners, euribor, url, wrap, tilaa, solarwind, forecasts.
"""

import os
import sys
from unittest.mock import Mock, patch

import pytest

# Add src to path before importing project modules
_TEST_ROOT = os.path.dirname(os.path.abspath(__file__))
if _TEST_ROOT not in sys.path:
    sys.path.insert(0, os.path.join(_TEST_ROOT, "..", "src"))

from command_registry import CommandContext


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

        # Check for leet-style text or plain text
        assert "No" in result and "recorded yet" in result


class TestEuriborCommand:
    """Tests for the !euribor command."""

    def test_euribor_command_success(self, console_context, mock_bot_functions):
        """Test euribor command with successful API response."""
        from cmd_modules.services import euribor_command

        # Mock requests.get to return a successful response
        with patch("cmd_modules.services.requests.get") as mock_get:
            # Create a mock XML response matching the expected namespace
            mock_response = Mock()
            mock_response.status_code = 200
            # Use the correct namespace that the code expects
            mock_response.content = b'<?xml version="1.0" encoding="UTF-8"?><Envelope xmlns="euribor_korot_today_xml_en"><period value="2023-03-01"><rate name="12 month (act/360)"><intr value="3.5"/></rate></period></Envelope>'
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

        # Mock the url tracker service by providing it in bot_functions
        mock_service = Mock()
        mock_service.get_stats.return_value = {
            "total_urls": 100,
            "total_posts": 500,
            "most_popular_url": "https://example.com",
            "most_popular_count": 10,
            "oldest_url": "https://old.example.com",
            "oldest_timestamp": "2023-01-01T00:00:00Z",
        }
        mock_bot_functions["url_tracker"] = mock_service

        # Create context with arguments
        console_context.args_text = "stats"
        console_context.args = ["stats"]

        result = url_command(console_context, mock_bot_functions)

        assert "URL Stats:" in result
        assert "100 URLs" in result
        assert "500 posts" in result
        assert "https://example.com" in result

    def test_url_command_search(self, console_context, mock_bot_functions):
        """Test url command with search subcommand."""
        from cmd_modules.services import url_command

        # Mock the url tracker service
        with patch(
            "services.url_tracker_service.create_url_tracker_service"
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
            "services.url_tracker_service.create_url_tracker_service"
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

        # Mock the TUI instance - need to use new_callable to make it a callable Mock
        with patch("cmd_modules.services._current_tui", new_callable=Mock) as mock_tui:
            result = wrap_command(console_context, mock_bot_functions)

            # Should return empty string since toggle_wrap handles the logging
            assert result == ""
            mock_tui.toggle_wrap.assert_called_once()

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
        # For console with no target/sender, it uses "console" as subscriber and server_name
        mock_subscriptions.toggle_subscription.assert_called_once_with(
            "console", "console", "varoitukset"
        )

    def test_tilaa_command_no_service(self, console_context, mock_bot_functions):
        """Test tilaa command when service is not available."""
        from cmd_modules.services import command_tilaa

        # Add args so we get past the usage check
        console_context.args_text = "varoitukset"
        console_context.args = ["varoitukset"]

        # Don't add subscriptions to mock_bot_functions
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
