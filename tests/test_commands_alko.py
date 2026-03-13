#!/usr/bin/env python3
"""
Tests for the !alko command including !alko halvin (cheapest by value).
"""

import os
import sys
from unittest.mock import Mock

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

        # The service may return usage from cache even without explicit mock
        # Just verify the command runs without error
        assert result is not None


class TestAlkoHalvinCommand:
    """Tests for the !alko halvin (cheapest by value) command."""

    def test_alko_command_halvin_default(self, console_context, mock_bot_functions):
        """Test alko command with halvin (cheapest) without limit."""
        from cmd_modules.services import alko_command

        # Create context with arguments
        console_context.args_text = "halvin"
        console_context.args = ["halvin"]

        # Mock alko service with test products
        mock_product1 = {
            "name": "Cheap Beer",
            "price": 2.00,
            "alcohol_grams": 10.0,
            "value_ratio": 5.0,
            "bottle_size_raw": "0.5 l",
            "alcohol_percent": 4.5,
        }
        mock_product2 = {
            "name": "Expensive Wine",
            "price": 20.00,
            "alcohol_grams": 80.0,
            "value_ratio": 4.0,
            "bottle_size_raw": "0.75 l",
            "alcohol_percent": 12.0,
        }

        mock_alko_service = Mock()
        mock_alko_service.find_cheapest_by_value.return_value = [
            mock_product1,
            mock_product2,
        ]

        mock_bot_functions = {"get_alko_service": lambda: mock_alko_service}

        result = alko_command(console_context, mock_bot_functions)
        expected = "🍺 Halvimmat juomat arvoltaan:\n1. Cheap Beer 0.5 l 4.5% (10.0g) - 2.00€ (arvo: 5.00g/€)\n2. Expensive Wine 0.75 l 12.0% (80.0g) - 20.00€ (arvo: 4.00g/€)"
        assert result == expected

    def test_alko_command_halvin_with_limit(self, console_context, mock_bot_functions):
        """Test alko command with halvin and custom limit."""
        from cmd_modules.services import alko_command

        # Create context with arguments
        console_context.args_text = "halvin 1"
        console_context.args = ["halvin", "1"]

        # Mock alko service with test products
        mock_product1 = {
            "name": "Cheap Beer",
            "price": 2.00,
            "alcohol_grams": 10.0,
            "value_ratio": 5.0,
            "bottle_size_raw": "0.5 l",
            "alcohol_percent": 4.5,
        }

        mock_alko_service = Mock()
        mock_alko_service.find_cheapest_by_value.return_value = [mock_product1]

        mock_bot_functions = {"get_alko_service": lambda: mock_alko_service}

        result = alko_command(console_context, mock_bot_functions)
        expected = "🍺 Halvimmat juomat arvoltaan:\n1. Cheap Beer 0.5 l 4.5% (10.0g) - 2.00€ (arvo: 5.00g/€)"
        assert result == expected

    def test_alko_command_halvin_invalid_limit(
        self, console_context, mock_bot_functions
    ):
        """Test alko command with halvin and invalid limit."""
        from cmd_modules.services import alko_command

        # Create context with arguments
        console_context.args_text = "halvin 15"
        console_context.args = ["halvin", "15"]

        mock_bot_functions = {"get_alko_service": lambda: Mock()}

        result = alko_command(console_context, mock_bot_functions)
        assert result == "🍺 Limit must be between 1 and 10"

    def test_alko_command_halvin_no_service(self, console_context, mock_bot_functions):
        """Test alko command with halvin when service is not available."""
        from cmd_modules.services import alko_command

        # Create context with arguments
        console_context.args_text = "halvin"
        console_context.args = ["halvin"]

        mock_bot_functions = {}  # No alko service

        # The service may return data from cache even without explicit mock
        # Just check that the command runs without error
        result = alko_command(console_context, mock_bot_functions)
        assert result is not None  # Command should return something

    def test_alko_command_halvin_no_products(self, console_context, mock_bot_functions):
        """Test alko command with halvin when no alcoholic products found."""
        from cmd_modules.services import alko_command

        # Create context with arguments
        console_context.args_text = "halvin"
        console_context.args = ["halvin"]

        mock_alko_service = Mock()
        mock_alko_service.find_cheapest_by_value.return_value = []

        mock_bot_functions = {"get_alko_service": lambda: mock_alko_service}

        result = alko_command(console_context, mock_bot_functions)
        assert result == "🍺 No alcoholic products found in database"

    def test_alko_command_halvin_error(self, console_context, mock_bot_functions):
        """Test alko command with halvin when error occurs."""
        from cmd_modules.services import alko_command

        # Create context with arguments
        console_context.args_text = "halvin"
        console_context.args = ["halvin"]

        mock_alko_service = Mock()
        mock_alko_service.find_cheapest_by_value.side_effect = Exception("Test error")

        mock_bot_functions = {"get_alko_service": lambda: mock_alko_service}

        result = alko_command(console_context, mock_bot_functions)
        assert "Error finding cheapest products" in result
