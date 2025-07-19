"""
Cryptocurrency Service Tests

Comprehensive tests for the cryptocurrency service functionality.
Pure pytest implementation with fixtures, parametrization, and assertions.
"""

import json
import pytest
import requests
from unittest.mock import Mock, patch


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
    assert service.base_url == "https://api.coingecko.com/api/v3", "Base URL should be set"
    assert isinstance(service.crypto_aliases, dict), "Should have crypto aliases"
    assert isinstance(service.supported_currencies, list), "Should have supported currencies"

    # Test factory function
    service2 = create_crypto_service()
    assert isinstance(service2, CryptoService), "Factory should return CryptoService instance"


def test_crypto_price_success(crypto_service, mock_bitcoin_response):
    """Test successful cryptocurrency price response."""
    with patch("requests.get") as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_bitcoin_response
        mock_get.return_value = mock_response

        result = crypto_service.get_crypto_price("bitcoin", "eur")

    assert result["error"] == False, "Should not have error"
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

    assert result["error"] == False, "Should not have error"
    assert result["coin_id"] == "bitcoin", "BTC should resolve to bitcoin"


def test_crypto_api_error(crypto_service):
    """Test cryptocurrency API error handling."""
    # Test HTTP error
    with patch("requests.get") as mock_get:
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = crypto_service.get_crypto_price("nonexistent", "eur")

    assert result["error"] == True, "Should have error"
    assert "404" in str(result["status_code"]), "Should include status code"


def test_crypto_timeout_handling(crypto_service):
    """Test cryptocurrency API timeout handling."""
    with patch("requests.get") as mock_get:
        mock_get.side_effect = requests.exceptions.Timeout()

        result = crypto_service.get_crypto_price("bitcoin", "eur")

    assert result["error"] == True, "Should have error"
    assert "timed out" in result["message"].lower(), "Should mention timeout"
    assert result["exception"] == "timeout", "Should have timeout exception type"


def test_unsupported_currency(crypto_service):
    """Test unsupported currency handling."""
    result = crypto_service.get_crypto_price("bitcoin", "xyz")

    assert result["error"] == True, "Should have error"
    assert "Unsupported currency" in result["message"], "Should mention unsupported currency"


def test_coin_not_found(crypto_service):
    """Test coin not found handling."""
    # Mock empty response
    mock_response_data = {}

    with patch("requests.get") as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_get.return_value = mock_response

        result = crypto_service.get_crypto_price("nonexistentcoin", "eur")

    assert result["error"] == True, "Should have error"
    assert "not found" in result["message"].lower(), "Should mention coin not found"


def test_trending_cryptos(crypto_service, mock_trending_response):
    """Test trending cryptocurrencies functionality."""
    with patch("requests.get") as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_trending_response
        mock_get.return_value = mock_response

        result = crypto_service.get_trending_cryptos()

    assert result["error"] == False, "Should not have error"
    assert len(result["trending"]) == 2, "Should have 2 trending coins"
    assert result["trending"][0]["symbol"] == "BTC", "First coin should be BTC"


def test_crypto_search(crypto_service, mock_search_response):
    """Test cryptocurrency search functionality."""
    with patch("requests.get") as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_search_response
        mock_get.return_value = mock_response

        result = crypto_service.search_crypto("bitcoin")

    assert result["error"] == False, "Should not have error"
    assert len(result["results"]) == 1, "Should have 1 search result"
    assert result["results"][0]["name"] == "Bitcoin", "Should find Bitcoin"


def test_price_message_formatting(crypto_service):
    """Test price message formatting."""
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

    result = crypto_service.format_price_message(price_data)

    assert "💰 Bitcoin:" in result, "Should include coin name"
    assert "€45,000.50" in result, "Should include formatted price"
    assert "📈 +2.50%" in result, "Should include positive change"
    assert "850.0B" in result, "Should include market cap"

    # Test error formatting
    error_data = {"error": True, "message": "Coin not found"}

    error_result = crypto_service.format_price_message(error_data)
    assert "💸 Kryptohaku epäonnistui" in error_result, "Should indicate failure"
    assert "Coin not found" in error_result, "Should include error message"


def test_trending_message_formatting(crypto_service):
    """Test trending message formatting."""
    # Test successful trending formatting
    trending_data = {
        "error": False,
        "trending": [
            {"symbol": "btc", "name": "Bitcoin"},
            {"symbol": "eth", "name": "Ethereum"},
        ],
    }

    result = crypto_service.format_trending_message(trending_data)

    assert "🔥 Trending kryptot:" in result, "Should include trending header"
    assert "1. BTC (Bitcoin)" in result, "Should include first coin"
    assert "2. ETH (Ethereum)" in result, "Should include second coin"

    # Test error formatting
    error_data = {"error": True, "message": "API error"}

    error_result = crypto_service.format_trending_message(error_data)
    assert "🔥 Trending-haku epäonnistui" in error_result, "Should indicate failure"


@pytest.mark.parametrize("currency,expected_symbol", [
    ("EUR", "€"),
    ("USD", "$"),
    ("BTC", "₿"),
    ("ETH", "Ξ"),
    ("UNKNOWN", "UNKNOWN "),
])
def test_currency_symbol_mapping(crypto_service, currency, expected_symbol):
    """Test currency symbol mapping."""
    result = crypto_service._get_currency_symbol(currency)
    assert result == expected_symbol, f"Currency symbol for {currency} should be {expected_symbol}, got {result}"


@pytest.mark.parametrize("price_data,expected_content", [
    # High value coins
    ({
        "error": False,
        "coin_id": "bitcoin",
        "currency": "EUR",
        "price": 45000.50,
        "change_24h": None,
    }, "45,000.50"),
    # Medium value coins
    ({
        "error": False,
        "coin_id": "ethereum",
        "currency": "EUR",
        "price": 3.5678,
        "change_24h": None,
    }, "3.57"),
    # Low value coins
    ({
        "error": False,
        "coin_id": "lowcoin",
        "currency": "EUR",
        "price": 0.00001234,
        "change_24h": None,
    }, "0.00001234"),
])
def test_price_formatting_precision(crypto_service, price_data, expected_content):
    """Test price formatting precision."""
    result = crypto_service.format_price_message(price_data)
    assert expected_content in result, f"Should format price correctly, got: {result}"


def test_service_configuration(crypto_service):
    """Test service configuration and methods."""
    # Test supported currencies
    currencies = crypto_service.get_supported_currencies()
    assert isinstance(currencies, list), "Should return list"
    assert "eur" in currencies, "Should support EUR"
    assert "usd" in currencies, "Should support USD"

    # Test crypto aliases
    aliases = crypto_service.get_crypto_aliases()
    assert isinstance(aliases, dict), "Should return dict"
    assert aliases["btc"] == "bitcoin", "BTC should map to bitcoin"
    assert aliases["eth"] == "ethereum", "ETH should map to ethereum"


def test_network_error_handling(crypto_service):
    """Test network error handling."""
    with patch("requests.get") as mock_get:
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")

        result = crypto_service.get_crypto_price("bitcoin", "eur")

    assert result["error"] == True, "Should have error"
    assert "connection" in result["message"].lower(), "Should mention connection error"


def test_json_decode_error(crypto_service):
    """Test JSON decode error handling."""
    with patch("requests.get") as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_get.return_value = mock_response

        result = crypto_service.get_crypto_price("bitcoin", "eur")

    assert result["error"] == True, "Should have error"
    assert "json" in result["message"].lower() or "decode" in result["message"].lower(), "Should mention JSON error"


def test_negative_price_change_formatting(crypto_service):
    """Test formatting of negative price changes."""
    price_data = {
        "error": False,
        "coin_id": "bitcoin",
        "currency": "EUR",
        "price": 40000.00,
        "change_24h": -5.25,
        "market_cap": 800000000000,
        "volume_24h": 12000000000,
    }

    result = crypto_service.format_price_message(price_data)

    assert "💰 Bitcoin:" in result, "Should include coin name"
    assert "€40,000.00" in result, "Should include formatted price"
    assert "📉 -5.25%" in result, "Should include negative change with down arrow"


def test_zero_price_change_formatting(crypto_service):
    """Test formatting when price change is zero."""
    price_data = {
        "error": False,
        "coin_id": "bitcoin",
        "currency": "EUR",
        "price": 40000.00,
        "change_24h": 0.0,
        "market_cap": 800000000000,
        "volume_24h": 12000000000,
    }

    result = crypto_service.format_price_message(price_data)

    assert "💰 Bitcoin:" in result, "Should include coin name"
    assert "€40,000.00" in result, "Should include formatted price"
    assert "📈 +0.00%" in result, "Should show zero change formatted as positive"
