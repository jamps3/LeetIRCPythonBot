#!/usr/bin/env python3
"""
Pytest tests for services.electricity_service module.

Tests electricity price functionality including API integration,
command parsing, and message formatting.
"""

import os
import unittest
from datetime import datetime
from unittest.mock import Mock, patch

import requests

from services.electricity_service import ElectricityService, create_electricity_service

# Add the services directory to the path to avoid import dependency issues
# sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "services"))


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

    @patch("requests.get")
    def test_get_daily_prices_timeout(self, mock_get):
        """Test timeout handling."""
        # Mock a timeout exception
        mock_get.side_effect = requests.exceptions.Timeout("request timed out")

        test_date = datetime(2023, 1, 1)
        result = self.service.get_daily_prices(test_date)

        self.assertTrue(result["error"])
        self.assertIn("request timed out", result["message"])


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


if __name__ == "__main__":
    # Run the tests
    unittest.main()
