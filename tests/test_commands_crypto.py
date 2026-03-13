#!/usr/bin/env python3
"""
Tests for the !crypto command.
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

        assert "bitcoin" in result.lower()
        assert "ethereum" in result.lower()
        assert "tether" in result.lower()
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

        assert "💸 BTC: 45000.00 EUR" == result or "💸 Btc: 45000.00 EUR" == result

    def test_crypto_command_no_service(self, console_context, mock_bot_functions):
        """Test crypto command when service is not available."""
        from cmd_modules.services import crypto_command

        # Remove get_crypto_price from bot functions
        del mock_bot_functions["get_crypto_price"]

        result = crypto_command(console_context, mock_bot_functions)

        assert result == "Crypto price service not available"
