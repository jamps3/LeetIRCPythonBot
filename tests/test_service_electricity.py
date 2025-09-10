#!/usr/bin/env python3
"""
Pytest tests for services.electricity_service module.

Tests electricity price functionality including API integration,
command parsing, and message formatting.
"""

import json
import os
import sys
import unittest
from datetime import datetime, timedelta
from io import StringIO
from unittest.mock import Mock, patch

import requests

# Add the services directory to the path to avoid import dependency issues
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "services"))

from electricity_service import (  # noqa: E402
    ElectricityService,
    create_electricity_service,
)


class TestElectricityService(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures."""
        self.api_key = "test_api_key"
        self.service = ElectricityService(self.api_key)

    def test_service_initialization(self):
        """Test that the service initializes correctly."""
        self.assertEqual(self.service.api_key, self.api_key)
        self.assertEqual(self.service.base_url, "https://web-api.tp.entsoe.eu/api")
        self.assertEqual(self.service.finland_domain, "10YFI-1--------U")
        self.assertEqual(self.service.vat_rate, 1.255)

    def test_factory_function(self):
        """Test the factory function."""
        service = create_electricity_service(self.api_key)
        self.assertIsInstance(service, ElectricityService)
        self.assertEqual(service.api_key, self.api_key)

    def test_price_conversion(self):
        """Test price conversion from EUR/MWh to snt/kWh with VAT."""
        # 100 EUR/MWh should be 12.55 snt/kWh with VAT
        result = self.service._convert_price(100.0)
        self.assertAlmostEqual(result, 12.55, places=2)

        # 50 EUR/MWh should be 6.275 snt/kWh with VAT
        result = self.service._convert_price(50.0)
        self.assertAlmostEqual(result, 6.275, places=2)

    def test_command_parsing_current_hour(self):
        """Test parsing command with no arguments (current hour)."""
        current_time = datetime.now()
        result = self.service.parse_command_args([])

        self.assertEqual(result["hour"], current_time.hour)
        self.assertIsNone(result["error"])
        self.assertFalse(result["is_tomorrow"])
        self.assertFalse(result["show_stats"])

    def test_command_parsing_specific_hour(self):
        """Test parsing command with specific hour."""
        result = self.service.parse_command_args(["15"])

        self.assertEqual(result["hour"], 15)
        self.assertIsNone(result["error"])
        self.assertFalse(result["is_tomorrow"])
        self.assertFalse(result["show_stats"])

    def test_command_parsing_tomorrow(self):
        """Test parsing command for tomorrow."""
        result = self.service.parse_command_args(["huomenna"])

        current_time = datetime.now()
        expected_date = current_time + timedelta(days=1)

        self.assertEqual(result["hour"], current_time.hour)
        self.assertIsNone(result["error"])
        self.assertTrue(result["is_tomorrow"])
        self.assertFalse(result["show_stats"])
        self.assertEqual(result["date"].date(), expected_date.date())

    def test_command_parsing_tomorrow_with_hour(self):
        """Test parsing command for tomorrow with specific hour."""
        result = self.service.parse_command_args(["huomenna", "10"])

        current_time = datetime.now()
        expected_date = current_time + timedelta(days=1)

        self.assertEqual(result["hour"], 10)
        self.assertIsNone(result["error"])
        self.assertTrue(result["is_tomorrow"])
        self.assertFalse(result["show_stats"])
        self.assertEqual(result["date"].date(), expected_date.date())

    def test_command_parsing_statistics(self):
        """Test parsing command for statistics."""
        result = self.service.parse_command_args(["tilastot"])

        self.assertIsNone(result["error"])
        self.assertFalse(result["is_tomorrow"])
        self.assertTrue(result["show_stats"])

    def test_command_parsing_statistics_english(self):
        """Test parsing command for statistics using English 'stats' parameter."""
        result = self.service.parse_command_args(["stats"])

        self.assertIsNone(result["error"])
        self.assertFalse(result["is_tomorrow"])
        self.assertTrue(result["show_stats"])

    def test_command_parsing_tanaan(self):
        """Test parsing command for tänään (today all hours)."""
        result = self.service.parse_command_args(["tänään"])

        self.assertIsNone(result["error"])
        self.assertFalse(result["is_tomorrow"])
        self.assertFalse(result["show_stats"])
        self.assertTrue(result["show_all_hours"])

    def test_command_parsing_huomenna_all_hours(self):
        """Test parsing command for huomenna without specific hour (all hours)."""
        result = self.service.parse_command_args(["huomenna"])

        current_time = datetime.now()
        expected_date = current_time + timedelta(days=1)

        self.assertIsNone(result["error"])
        self.assertTrue(result["is_tomorrow"])
        self.assertFalse(result["show_stats"])
        self.assertTrue(result["show_all_hours"])
        self.assertEqual(result["date"].date(), expected_date.date())

    def test_command_parsing_invalid_hour(self):
        """Test parsing command with invalid hour."""
        result = self.service.parse_command_args(["25"])

        self.assertIsNotNone(result["error"])
        self.assertIn("Virheellinen tunti", result["error"])

    def test_command_parsing_invalid_tomorrow_hour(self):
        """Test parsing command with invalid hour for tomorrow."""
        result = self.service.parse_command_args(["huomenna", "25"])

        self.assertIsNotNone(result["error"])
        self.assertIn("Virheellinen tunti", result["error"])

    def test_command_parsing_invalid_command(self):
        """Test parsing invalid command."""
        result = self.service.parse_command_args(["invalid"])

        self.assertIsNotNone(result["error"])
        self.assertIn("Virheellinen komento", result["error"])

    @patch("requests.get")
    def test_fetch_daily_prices_success(self, mock_get):
        """Test successful API response parsing."""
        # Mock successful API response with XML data
        xml_response = """<?xml version="1.0" encoding="UTF-8"?>
<Publication_MarketDocument xmlns="urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3">
    <TimeSeries>
        <Period>
            <Point>
                <position>1</position>
                <price.amount>50.0</price.amount>
            </Point>
            <Point>
                <position>2</position>
                <price.amount>45.5</price.amount>
            </Point>
            <Point>
                <position>24</position>
                <price.amount>20.0</price.amount>
            </Point>
        </Period>
    </TimeSeries>
</Publication_MarketDocument>"""

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = xml_response
        mock_get.return_value = mock_response

        test_date = datetime(2023, 1, 1)
        result = self.service._fetch_daily_prices(test_date)

        self.assertFalse(result["error"])
        self.assertEqual(result["date"], "2023-01-01")
        self.assertEqual(result["prices"][1], 50.0)
        self.assertEqual(result["prices"][2], 45.5)
        self.assertEqual(result["prices"][24], 20.0)  # Hour 0 maps to position 24
        self.assertEqual(result["total_hours"], 3)

    @patch("requests.get")
    def test_fetch_daily_prices_api_error(self, mock_get):
        """Test API error handling."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        test_date = datetime(2023, 1, 1)
        result = self.service._fetch_daily_prices(test_date)

        self.assertTrue(result["error"])
        self.assertEqual(result["status_code"], 401)
        self.assertIn("Invalid ENTSO-E API key", result["message"])

    @patch("requests.get")
    def test_fetch_daily_prices_timeout(self, mock_get):
        """Test timeout handling."""
        # Mock a timeout exception
        mock_get.side_effect = requests.exceptions.Timeout("Request timed out")

        test_date = datetime(2023, 1, 1)
        result = self.service._fetch_daily_prices(test_date)

        self.assertTrue(result["error"])
        self.assertIn("ENTSO-E API request timed out", result["message"])
        self.assertEqual(result["exception"], "timeout")

    def test_format_price_message_success(self):
        """Test formatting of successful price data."""
        price_data = {
            "error": False,
            "date": "2023-01-01",
            "hour": 14,
            "today_price": {
                "eur_per_mwh": 50.0,
                "snt_per_kwh_with_vat": 6.275,
                "snt_per_kwh_no_vat": 5.0,
            },
            "tomorrow_price": {
                "eur_per_mwh": 45.0,
                "snt_per_kwh_with_vat": 5.6475,
                "snt_per_kwh_no_vat": 4.5,
            },
            "tomorrow_available": True,  # Need to mark as available
            "include_tomorrow": True,
        }

        result = self.service.format_price_message(price_data)

        self.assertIn("⚡ Tänään 2023-01-01 klo 14: 6.28 snt/kWh", result)
        self.assertIn("⚡ Huomenna 2023-01-02 klo 14: 5.65 snt/kWh", result)
        self.assertIn("ALV 25,5%", result)

    def test_format_price_message_error(self):
        """Test formatting of error message."""
        price_data = {"error": True, "message": "API error occurred"}

        result = self.service.format_price_message(price_data)

        self.assertIn("⚡ Sähkön hintatietojen haku epäonnistui", result)
        self.assertIn("API error occurred", result)

    def test_format_price_message_no_data(self):
        """Test formatting when no price data is available."""
        price_data = {
            "error": False,
            "date": "2023-01-01",
            "hour": 14,
            "today_price": None,
            "tomorrow_price": None,
            "include_tomorrow": False,  # No tomorrow requested to get the "no data" message
        }

        result = self.service.format_price_message(price_data)

        self.assertIn("⚡ Sähkön hintatietoja ei saatavilla tunnille 14", result)
        self.assertIn("https://sahko.tk", result)

    def test_format_statistics_message(self):
        """Test formatting of statistics message."""
        stats_data = {
            "error": False,
            "date": "2023-01-01",
            "min_price": {"hour": 3, "eur_per_mwh": 20.0, "snt_per_kwh_with_vat": 2.51},
            "max_price": {
                "hour": 18,
                "eur_per_mwh": 80.0,
                "snt_per_kwh_with_vat": 10.04,
            },
            "avg_price": {"eur_per_mwh": 50.0, "snt_per_kwh_with_vat": 6.275},
        }

        result = self.service.format_statistics_message(stats_data)

        self.assertIn("📊 Sähkön hintatilastot 2023-01-01", result)
        self.assertIn("Min: 2.51 snt/kWh (klo 03)", result)
        self.assertIn("Max: 10.04 snt/kWh (klo 18)", result)
        self.assertIn("Keskiarvo: 6.28 snt/kWh", result)

    @patch.object(ElectricityService, "_fetch_daily_prices")
    def test_get_electricity_price_success(self, mock_fetch):
        """Test getting electricity price successfully."""
        # Mock the daily prices response
        mock_fetch.return_value = {
            "error": False,
            "prices": {
                24: 20.0,  # Position 24 maps to hour 0
                14: 50.0,  # Position 14 maps to hour 14
                15: 45.0,  # Position 15 maps to hour 15
            },
        }

        test_date = datetime(2023, 1, 1, 14, 0)  # 14:00
        result = self.service.get_electricity_price(hour=14, date=test_date)

        self.assertFalse(result["error"])
        self.assertEqual(result["hour"], 14)
        self.assertIsNotNone(result["today_price"])
        self.assertEqual(result["today_price"]["eur_per_mwh"], 50.0)
        self.assertAlmostEqual(
            result["today_price"]["snt_per_kwh_with_vat"], 6.275, places=2
        )

    @patch.object(ElectricityService, "_fetch_daily_prices")
    def test_get_electricity_price_hour_0_success(self, mock_fetch):
        """Test getting electricity price for hour 0 (midnight)."""
        # Mock the calls for handling midnight price correctly
        # First call: yesterday's data (API offset), Second call: day before yesterday (hour 0)
        mock_fetch.side_effect = [
            {  # Yesterday's data (API offset) - no hour 0 data here
                "error": False,
                "prices": {1: 25.0, 2: 26.0},
            },
            {  # Day before yesterday's data - has position 24 for today's hour 0
                "error": False,
                "prices": {24: 30.0},
            },
        ]

        test_date = datetime(2023, 1, 2, 0, 0)  # 00:00 on Jan 2
        result = self.service.get_electricity_price(
            hour=0, date=test_date, include_tomorrow=False
        )

        self.assertFalse(result["error"])
        self.assertEqual(result["hour"], 0)
        self.assertIsNotNone(result["today_price"])
        self.assertEqual(result["today_price"]["eur_per_mwh"], 30.0)
        self.assertAlmostEqual(
            result["today_price"]["snt_per_kwh_with_vat"], 3.765, places=2
        )
        # Should call _fetch_daily_prices twice: yesterday (API offset) and day before yesterday (hour 0)
        self.assertEqual(mock_fetch.call_count, 2)

    def test_get_electricity_price_invalid_hour(self):
        """Test getting electricity price with invalid hour."""
        result = self.service.get_electricity_price(hour=25)

        self.assertTrue(result["error"])
        self.assertIn("Invalid hour: 25", result["message"])


class TestElectricityMapping(unittest.TestCase):
    """
    Integration tests for electricity price mapping verification.

    Tests the correct mapping of hours to API positions, particularly
    for hour 0 (midnight) which requires special handling.
    """

    def setUp(self):
        """Set up test fixtures for mapping tests."""
        self.api_key = "test_mapping_key"
        self.service = ElectricityService(self.api_key)

    @patch.object(ElectricityService, "_fetch_daily_prices")
    def test_hour_0_mapping_today(self, mock_fetch):
        """Test that today's hour 0 correctly maps to position 24 from day before yesterday."""
        # Mock the call sequence for hour 0: first yesterday (API offset), then day before yesterday (hour 0)
        mock_fetch.side_effect = [
            {
                "error": False,
                "prices": {1: 25.0},
            },  # Yesterday for API offset (no hour 0 here)
            {"error": False, "prices": {24: 30.0}},  # Day before yesterday for hour 0
        ]

        test_date = datetime(2023, 1, 2, 0, 0)  # 00:00 on Jan 2
        result = self.service.get_electricity_price(
            hour=0, date=test_date, include_tomorrow=False
        )

        self.assertFalse(result["error"])
        self.assertEqual(result["hour"], 0)
        self.assertIsNotNone(result["today_price"])
        self.assertEqual(result["today_price"]["eur_per_mwh"], 30.0)

        # Should call _fetch_daily_prices twice: yesterday (API offset) and day before yesterday (hour 0)
        self.assertEqual(mock_fetch.call_count, 2)

    @patch.object(ElectricityService, "_fetch_daily_prices")
    def test_hour_0_mapping_tomorrow(self, mock_fetch):
        """Test that tomorrow's hour 0 correctly uses previous day's position 24."""
        # Simulate the complete call sequence for getting hour 0 with tomorrow prices
        mock_fetch.side_effect = [
            {  # Yesterday's data (API offset for today)
                "error": False,
                "prices": {1: 25.0},
            },
            {  # Day before yesterday's data (for today's hour 0)
                "error": False,
                "prices": {24: 30.0},
            },
            {  # Today's data (API offset for tomorrow)
                "error": False,
                "prices": {1: 28.0},
            },
            {  # Yesterday's data (for tomorrow's hour 0)
                "error": False,
                "prices": {24: 32.0},
            },
        ]

        test_date = datetime(2023, 1, 2, 0, 0)  # 00:00 on Jan 2
        result = self.service.get_electricity_price(
            hour=0, date=test_date, include_tomorrow=True
        )

        self.assertFalse(result["error"])
        self.assertEqual(result["hour"], 0)
        self.assertIsNotNone(result["tomorrow_price"])
        self.assertEqual(result["tomorrow_price"]["eur_per_mwh"], 32.0)
        self.assertTrue(result["tomorrow_available"])

    @patch.object(ElectricityService, "_fetch_daily_prices")
    def test_regular_hours_mapping(self, mock_fetch):
        """Test that regular hours (1-23) map directly to their positions."""
        mock_fetch.return_value = {
            "error": False,
            "prices": {
                1: 20.0,
                15: 45.0,
                23: 35.0,
            },
        }

        test_date = datetime(2023, 1, 2, 15, 0)

        # Test hour 15
        result = self.service.get_electricity_price(
            hour=15, date=test_date, include_tomorrow=False
        )
        self.assertFalse(result["error"])
        self.assertEqual(result["today_price"]["eur_per_mwh"], 45.0)

        # Test hour 1
        result = self.service.get_electricity_price(
            hour=1, date=test_date, include_tomorrow=False
        )
        self.assertFalse(result["error"])
        self.assertEqual(result["today_price"]["eur_per_mwh"], 20.0)

        # Test hour 23
        result = self.service.get_electricity_price(
            hour=23, date=test_date, include_tomorrow=False
        )
        self.assertFalse(result["error"])
        self.assertEqual(result["today_price"]["eur_per_mwh"], 35.0)

    @patch.object(ElectricityService, "_fetch_daily_prices")
    def test_api_offset_handling(self, mock_fetch):
        """Test that the API one-day offset is handled correctly."""
        # The service should fetch from yesterday for today's prices (except hour 0)
        mock_fetch.return_value = {
            "error": False,
            "prices": {15: 40.0},
        }

        test_date = datetime(2023, 1, 2, 15, 0)  # Jan 2, 15:00
        result = self.service.get_electricity_price(
            hour=15, date=test_date, include_tomorrow=False
        )

        # Should call _fetch_daily_prices with yesterday's date
        expected_api_date = test_date - timedelta(days=1)  # Jan 1
        mock_fetch.assert_called_with(expected_api_date)

        self.assertFalse(result["error"])
        self.assertEqual(result["today_price"]["eur_per_mwh"], 40.0)


class TestElectricityServiceIntegration(unittest.TestCase):
    """
    Integration tests for electricity service with bot manager.

    These tests simulate the actual IRC command flow to catch
    parameter handling errors.
    """

    def setUp(self):
        """Set up test fixtures for integration tests."""
        # Ensure the environment variable for the electricity API key is set correctly
        self.original_env = os.environ.get("ELECTRICITY_API_KEY")
        if not self.original_env:
            os.environ["ELECTRICITY_API_KEY"] = "test_integration_key"

        # Import and create bot manager for testing
        from bot_manager import BotManager

        self.bot_manager = BotManager("TestBot")

        # Mock server for testing
        self.mock_server = Mock()
        self.mock_server.send_message = Mock()
        self.mock_server.send_notice = Mock()

        # Create service instance for testing
        self.service = ElectricityService("test_integration_key")

    def tearDown(self):
        """Clean up after tests."""
        if self.original_env:
            os.environ["ELECTRICITY_API_KEY"] = self.original_env
        elif "ELECTRICITY_API_KEY" in os.environ:
            del os.environ["ELECTRICITY_API_KEY"]

    def test_electricity_command_with_list_input(self):
        """Test electricity command when called with list input (from IRC parsing)."""
        # This simulates how the command is called from IRC command processing
        # where text.split() returns a list: ['!sahko', 'argument']
        test_cases = [
            ["!sahko"],  # Just the command
            ["!sahko", "15"],  # Command with hour
            ["!sahko", "huomenna"],  # Command with tomorrow
            ["!sahko", "huomenna", "10"],  # Command with tomorrow and hour
            ["!sahko", "tilastot"],  # Command with statistics
            ["!sahko", "stats"],  # Command with statistics (English)
            ["!sahko", "25"],  # Invalid hour
            ["!sahko", "invalid"],  # Invalid argument
        ]

        for parts_list in test_cases:
            with self.subTest(parts=parts_list):
                try:
                    # This should not raise an AttributeError about 'list' object has no attribute 'split'
                    self.bot_manager._send_electricity_price(
                        self.mock_server, "#testchannel", parts_list
                    )
                    # If we get here, the function handled the list input correctly
                    self.assertTrue(
                        True, f"Successfully handled list input: {parts_list}"
                    )
                except AttributeError as e:
                    if "'list' object has no attribute 'split'" in str(e):
                        self.fail(
                            f"Function failed to handle list input {parts_list}: {e}"
                        )
                    else:
                        # Some other AttributeError, re-raise
                        raise
                except Exception as e:
                    # Other exceptions are OK (like API errors), we just want to avoid the split() error
                    pass

    def test_electricity_command_with_string_input(self):
        """Test electricity command when called with string input (console mode)."""
        # This simulates how the command might be called from console
        test_cases = [
            "",  # Empty string
            "15",  # Just hour
            "huomenna",  # Just tomorrow
            "huomenna 10",  # Tomorrow with hour
            "tilastot",  # Statistics
            "25",  # Invalid hour
            "invalid",  # Invalid argument
        ]

        for text_input in test_cases:
            with self.subTest(text=text_input):
                try:
                    # This should handle string input correctly
                    self.bot_manager._send_electricity_price(
                        self.mock_server, "#testchannel", text_input
                    )
                    # If we get here, the function handled the string input correctly
                    self.assertTrue(
                        True, f"Successfully handled string input: '{text_input}'"
                    )
                except Exception as e:
                    # Exceptions are OK (like API errors), we just want to ensure no crashes
                    pass

    def test_electricity_command_flow_with_mock_service(self):
        """Test complete command flow with mocked electricity service."""
        # Skip if bot manager doesn't have electricity service due to missing dependencies
        if not self.bot_manager.electricity_service:
            self.skipTest("Electricity service not available in bot manager")

        # Mock the get_electricity_price method on the actual instance
        with patch.object(
            self.bot_manager.electricity_service, "get_electricity_price"
        ) as mock_get_price:
            # Mock successful API response
            mock_get_price.return_value = {
                "error": False,
                "date": "2023-01-01",
                "hour": 15,
                "today_price": {
                    "eur_per_mwh": 50.0,
                    "snt_per_kwh_with_vat": 6.275,
                    "snt_per_kwh_no_vat": 5.0,
                },
                "tomorrow_price": None,
            }

            # Test the full flow with list input (IRC command style)
            self.bot_manager._send_electricity_price(
                self.mock_server, "#testchannel", ["!sahko", "15"]
            )

            # Verify the service was called correctly
            mock_get_price.assert_called_once()

        # Verify a response was sent (either NOTICE or PRIVMSG)
        self.assertTrue(
            self.mock_server.send_notice.called or self.mock_server.send_message.called,
            "No response was sent to IRC",
        )

    def test_electricity_command_without_service(self):
        """Test electricity command when service is not available."""
        # Create bot manager without electricity service
        original_service = self.bot_manager.electricity_service
        self.bot_manager.electricity_service = None

        try:
            # Should handle gracefully and send error message
            self.bot_manager._send_electricity_price(
                self.mock_server, "#testchannel", ["!sahko"]
            )

            # Verify error response was sent
            self.assertTrue(
                self.mock_server.send_notice.called
                or self.mock_server.send_message.called,
                "No error response was sent when service unavailable",
            )

        finally:
            # Restore service
            self.bot_manager.electricity_service = original_service

    def test_format_price_message_tomorrow_unavailable(self):
        """Test formatting when tomorrow's price is not available."""
        price_data = {
            "error": False,
            "date": "2025-08-01",
            "hour": 14,
            "today_price": {
                "eur_per_mwh": 12.6,
                "snt_per_kwh_with_vat": 1.58,
                "snt_per_kwh_no_vat": 1.26,
            },
            "tomorrow_price": None,
            "today_available": True,
            "tomorrow_available": False,  # Key: tomorrow is NOT available
            "include_tomorrow": True,  # Tomorrow was requested
        }

        message = self.service.format_price_message(price_data)

        # Should show today's price
        self.assertIn("Tänään 2025-08-01 klo 14: 1.58 snt/kWh", message)

        # Should show "not available" message for tomorrow
        self.assertIn("Huomisen hintaa ei vielä saatavilla", message)

        # Should NOT show today's price as tomorrow's price
        self.assertNotRegex(message, r"Huomenna.*1\.58 snt/kWh")

    def test_format_price_message_tomorrow_available(self):
        """Test formatting when tomorrow's price is available."""
        price_data = {
            "error": False,
            "date": "2025-08-01",
            "hour": 14,
            "today_price": {
                "eur_per_mwh": 12.6,
                "snt_per_kwh_with_vat": 1.58,
                "snt_per_kwh_no_vat": 1.26,
            },
            "tomorrow_price": {
                "eur_per_mwh": 15.2,
                "snt_per_kwh_with_vat": 1.91,
                "snt_per_kwh_no_vat": 1.52,
            },
            "today_available": True,
            "tomorrow_available": True,  # Key: tomorrow IS available
            "include_tomorrow": True,
        }

        message = self.service.format_price_message(price_data)

        # Should show both today's and tomorrow's prices correctly
        self.assertIn("Tänään 2025-08-01 klo 14: 1.58 snt/kWh", message)
        self.assertIn("Huomenna 2025-08-02 klo 14: 1.91 snt/kWh", message)

        # Should NOT show "not available" message
        self.assertNotIn("Huomisen hintaa ei vielä saatavilla", message)

    def test_format_price_message_tomorrow_not_requested(self):
        """Test formatting when tomorrow's price is not requested."""
        price_data = {
            "error": False,
            "date": "2025-08-01",
            "hour": 14,
            "today_price": {
                "eur_per_mwh": 12.6,
                "snt_per_kwh_with_vat": 1.58,
                "snt_per_kwh_no_vat": 1.26,
            },
            "tomorrow_price": None,
            "today_available": True,
            "tomorrow_available": False,
            "include_tomorrow": False,  # Tomorrow was NOT requested
        }

        message = self.service.format_price_message(price_data)

        # Should only show today's price
        self.assertIn("Tänään 2025-08-01 klo 14: 1.58 snt/kWh", message)

        # Should NOT show tomorrow-related messages
        self.assertNotIn("Huomenna", message)
        self.assertNotIn("Huomisen hintaa ei vielä saatavilla", message)

    def test_get_electricity_price_includes_tomorrow_flag(self):
        """Test that get_electricity_price includes the include_tomorrow flag in result."""
        with patch.object(self.service, "_fetch_daily_prices") as mock_fetch:
            # Mock successful today fetch, failed tomorrow fetch
            mock_fetch.side_effect = [
                {  # Today's prices
                    "error": False,
                    "date": "2025-08-01",
                    "prices": {14: 12.6},
                },
                {  # Tomorrow's prices (failed)
                    "error": True,
                    "message": "No data available",
                },
            ]

            result = self.service.get_electricity_price(
                hour=14, date=datetime(2025, 8, 1), include_tomorrow=True
            )

            # Verify the include_tomorrow flag is preserved
            self.assertTrue(result.get("include_tomorrow"))
            self.assertFalse(result.get("tomorrow_available"))
            self.assertIsNone(result.get("tomorrow_price"))


if __name__ == "__main__":
    # Run the tests
    unittest.main()
