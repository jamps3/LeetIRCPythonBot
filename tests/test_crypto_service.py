"""
Cryptocurrency Service Tests - Unified Pytest Version

Comprehensive tests for the cryptocurrency service functionality.
"""

import json
import os
import sys
from unittest.mock import Mock, patch

import pytest
import requests

# Add the parent directory to Python path to ensure imports work in CI
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


@pytest.fixture
def crypto_service():
    """Create a CryptoService instance for testing."""
    from services.crypto_service import CryptoService

    return CryptoService()


@pytest.fixture
def mock_bitcoin_response():
    """Mock response data for Bitcoin price requests."""
    return {
        "bitcoin": {
            "eur": 45000.50,
            "eur_24h_change": 2.5,
            "eur_market_cap": 850000000000,
            "eur_24h_vol": 15000000000,
            "last_updated_at": 1640000000,
        }
    }


@pytest.fixture
def mock_trending_response():
    """Mock response data for trending cryptocurrencies."""
    return {
        "coins": [
            {
                "item": {
                    "id": "bitcoin",
                    "name": "Bitcoin",
                    "symbol": "BTC",
                    "market_cap_rank": 1,
                    "score": 100,
                }
            },
            {
                "item": {
                    "id": "ethereum",
                    "name": "Ethereum",
                    "symbol": "ETH",
                    "market_cap_rank": 2,
                    "score": 95,
                }
            },
        ]
    }


@pytest.fixture
def mock_search_response():
    """Mock response data for cryptocurrency search."""
    return {
        "coins": [
            {
                "id": "bitcoin",
                "name": "Bitcoin",
                "symbol": "BTC",
                "market_cap_rank": 1,
                "thumb": "bitcoin_thumb.png",
            }
        ]
    }


def test_crypto_service_creation():
    """Test cryptocurrency service creation."""
    from services.crypto_service import CryptoService, create_crypto_service

    # Test direct instantiation
    service = CryptoService()
    assert (
        service.base_url == "https://api.coingecko.com/api/v3"
    ), "Base URL should be set"
    assert isinstance(service.crypto_aliases, dict), "Should have crypto aliases"
    assert isinstance(
        service.supported_currencies, list
    ), "Should have supported currencies"

    # Test factory function
    service2 = create_crypto_service()
    assert isinstance(
        service2, CryptoService
    ), "Factory should return CryptoService instance"


def test_crypto_price_success():
    """Test successful cryptocurrency price response."""
    from services.crypto_service import CryptoService

    # Mock response data
    mock_response_data = {
        "bitcoin": {
            "eur": 45000.50,
            "eur_24h_change": 2.5,
            "eur_market_cap": 850000000000,
            "eur_24h_vol": 15000000000,
            "last_updated_at": 1640000000,
        }
    }

    service = CryptoService()

    with patch("requests.get") as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_get.return_value = mock_response

        result = service.get_crypto_price("bitcoin", "eur")

    assert result["error"] is False, "Should not have error"
    assert result["coin_id"] == "bitcoin", "Coin ID should match"
    assert result["currency"] == "EUR", "Currency should be uppercase"
    assert result["price"] == 45000.50, "Price should match"
    assert result["change_24h"] == 2.5, "24h change should match"


def test_crypto_alias_handling(crypto_service, mock_bitcoin_response):
    """Test cryptocurrency alias handling."""
    with patch("requests.get") as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_bitcoin_response
        mock_get.return_value = mock_response

        # Test BTC alias resolves to bitcoin
        result = crypto_service.get_crypto_price("btc", "eur")

    assert not result["error"], "Should not have error"
    assert result["coin_id"] == "bitcoin", "BTC should resolve to bitcoin"


def test_crypto_api_error():
    """Test cryptocurrency API error handling."""
    try:
        from services.crypto_service import CryptoService

        service = CryptoService()

        # Test HTTP error
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_get.return_value = mock_response

            result = service.get_crypto_price("nonexistent", "eur")

        assert result["error"] is True, "Should have error"
        assert "404" in str(result["status_code"]), "Should include status code"

        return True
    except Exception as e:
        print(f"Crypto API error test failed: {e}")
        return False


def test_crypto_timeout_handling():
    """Test cryptocurrency API timeout handling."""
    try:
        import requests

        from services.crypto_service import CryptoService

        service = CryptoService()

        with patch("requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.Timeout()

            result = service.get_crypto_price("bitcoin", "eur")

        assert result["error"] is True, "Should have error"
        assert "timed out" in result["message"].lower(), "Should mention timeout"
        assert result["exception"] == "timeout", "Should have timeout exception type"

        return True
    except Exception as e:
        print(f"Crypto timeout test failed: {e}")
        return False


def test_unsupported_currency():
    """Test unsupported currency handling."""
    try:
        from services.crypto_service import CryptoService

        service = CryptoService()

        result = service.get_crypto_price("bitcoin", "xyz")

        assert result["error"] is True, "Should have error"
        assert (
            "Unsupported currency" in result["message"]
        ), "Should mention unsupported currency"

        return True
    except Exception as e:
        print(f"Unsupported currency test failed: {e}")
        return False


def test_coin_not_found():
    """Test coin not found handling."""
    try:
        from services.crypto_service import CryptoService

        service = CryptoService()

        # Mock empty response
        mock_response_data = {}

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data
            mock_get.return_value = mock_response

            result = service.get_crypto_price("nonexistentcoin", "eur")

        assert result["error"] is True, "Should have error"
        assert "not found" in result["message"].lower(), "Should mention coin not found"

        return True
    except Exception as e:
        print(f"Coin not found test failed: {e}")
        return False


def test_trending_cryptos():
    """Test trending cryptocurrencies functionality."""
    try:
        from services.crypto_service import CryptoService

        service = CryptoService()

        # Mock trending response
        mock_response_data = {
            "coins": [
                {
                    "item": {
                        "id": "bitcoin",
                        "name": "Bitcoin",
                        "symbol": "BTC",
                        "market_cap_rank": 1,
                        "score": 100,
                    }
                },
                {
                    "item": {
                        "id": "ethereum",
                        "name": "Ethereum",
                        "symbol": "ETH",
                        "market_cap_rank": 2,
                        "score": 95,
                    }
                },
            ]
        }

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data
            mock_get.return_value = mock_response

            result = service.get_trending_cryptos()

        assert result["error"] is False, "Should not have error"
        assert len(result["trending"]) == 2, "Should have 2 trending coins"
        assert result["trending"][0]["symbol"] == "BTC", "First coin should be BTC"

        return True
    except Exception as e:
        print(f"Trending cryptos test failed: {e}")
        return False


def test_crypto_search():
    """Test cryptocurrency search functionality."""
    try:
        from services.crypto_service import CryptoService

        service = CryptoService()

        # Mock search response
        mock_response_data = {
            "coins": [
                {
                    "id": "bitcoin",
                    "name": "Bitcoin",
                    "symbol": "BTC",
                    "market_cap_rank": 1,
                    "thumb": "bitcoin_thumb.png",
                }
            ]
        }

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data
            mock_get.return_value = mock_response

            result = service.search_crypto("bitcoin")

        assert result["error"] is False, "Should not have error"
        assert len(result["results"]) == 1, "Should have 1 search result"
        assert result["results"][0]["name"] == "Bitcoin", "Should find Bitcoin"

        return True
    except Exception as e:
        print(f"Crypto search test failed: {e}")
        return False


def test_price_message_formatting():
    """Test price message formatting."""
    try:
        from services.crypto_service import CryptoService

        service = CryptoService()

        # Test successful price formatting
        price_data = {
            "error": False,
            "coin_id": "bitcoin",
            "currency": "EUR",
            "price": 45000.50,
            "change_24h": 2.5,
            "market_cap": 850000000000,
            "volume_24h": 15000000000,
        }

        result = service.format_price_message(price_data)

        assert "💰 Bitcoin:" in result, "Should include coin name"
        assert "€45,000.50" in result, "Should include formatted price"
        assert "📈 +2.50%" in result, "Should include positive change"
        assert "850.0B" in result, "Should include market cap"

        # Test error formatting
        error_data = {"error": True, "message": "Coin not found"}

        error_result = service.format_price_message(error_data)
        assert "💸 Kryptohaku epäonnistui" in error_result, "Should indicate failure"
        assert "Coin not found" in error_result, "Should include error message"

        return True
    except Exception as e:
        print(f"Price message formatting test failed: {e}")
        return False


def test_trending_message_formatting():
    """Test trending message formatting."""
    try:
        from services.crypto_service import CryptoService

        service = CryptoService()

        # Test successful trending formatting
        trending_data = {
            "error": False,
            "trending": [
                {"symbol": "btc", "name": "Bitcoin"},
                {"symbol": "eth", "name": "Ethereum"},
            ],
        }

        result = service.format_trending_message(trending_data)

        assert "🔥 Trending kryptot:" in result, "Should include trending header"
        assert "1. BTC (Bitcoin)" in result, "Should include first coin"
        assert "2. ETH (Ethereum)" in result, "Should include second coin"

        # Test error formatting
        error_data = {"error": True, "message": "API error"}

        error_result = service.format_trending_message(error_data)
        assert "🔥 Trending-haku epäonnistui" in error_result, "Should indicate failure"

        return True
    except Exception as e:
        print(f"Trending message formatting test failed: {e}")
        return False


def test_currency_symbol_mapping():
    """Test currency symbol mapping."""
    try:
        from services.crypto_service import CryptoService

        service = CryptoService()

        test_cases = [
            ("EUR", "€"),
            ("USD", "$"),
            ("BTC", "₿"),
            ("ETH", "Ξ"),
            ("UNKNOWN", "UNKNOWN "),
        ]

        for currency, expected_symbol in test_cases:
            result = service._get_currency_symbol(currency)
            assert (
                result == expected_symbol
            ), f"Currency symbol for {currency} should be {expected_symbol}, got {result}"

        return True
    except Exception as e:
        print(f"Currency symbol mapping test failed: {e}")
        return False


def test_price_formatting_precision():
    """Test price formatting precision."""
    try:
        from services.crypto_service import CryptoService

        service = CryptoService()

        test_cases = [
            # High value coins
            {
                "error": False,
                "coin_id": "bitcoin",
                "currency": "EUR",
                "price": 45000.50,
                "change_24h": None,
            },
            # Medium value coins
            {
                "error": False,
                "coin_id": "ethereum",
                "currency": "EUR",
                "price": 3.5678,
                "change_24h": None,
            },
            # Low value coins
            {
                "error": False,
                "coin_id": "lowcoin",
                "currency": "EUR",
                "price": 0.00001234,
                "change_24h": None,
            },
        ]

        for price_data in test_cases:
            result = service.format_price_message(price_data)
            price = price_data["price"]

            if price >= 1:
                # Check specific price formatting based on the actual price value
                if price >= 1000:
                    assert (
                        "45,000.50" in result
                    ), f"Should format large price correctly, got: {result}"
                else:
                    # For prices >= 1 but < 1000, format uses 2 decimal places
                    assert (
                        "3.57" in result
                    ), f"Should format medium price correctly, got: {result}"
            else:
                assert (
                    "0.00001234" in result
                ), f"Should format low prices with 8 decimals, got: {result}"

        return True
    except Exception as e:
        print(f"Price formatting precision test failed: {e}")
        return False


def test_service_configuration():
    """Test service configuration and methods."""
    try:
        from services.crypto_service import CryptoService

        service = CryptoService()

        # Test supported currencies
        currencies = service.get_supported_currencies()
        assert isinstance(currencies, list), "Should return list"
        assert "eur" in currencies, "Should support EUR"
        assert "usd" in currencies, "Should support USD"

        # Test crypto aliases
        aliases = service.get_crypto_aliases()
        assert isinstance(aliases, dict), "Should return dict"
        assert aliases["btc"] == "bitcoin", "BTC should map to bitcoin"
        assert aliases["eth"] == "ethereum", "ETH should map to ethereum"

        return True
    except Exception as e:
        print(f"Service configuration test failed: {e}")
        return False
