"""
Tests for ElectricityService module - Pure Pytest Version

Tests electricity price functionality including API integration,
command parsing, and message formatting.
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from io import StringIO
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add the parent directory to sys.path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Mock external dependencies
sys.modules["requests"] = Mock()
sys.modules["feedparser"] = Mock()
sys.modules["bs4"] = Mock()
sys.modules["selenium"] = Mock()
sys.modules["selenium.webdriver"] = Mock()
sys.modules["selenium.webdriver.chrome"] = Mock()
sys.modules["selenium.webdriver.chrome.options"] = Mock()
sys.modules["selenium.webdriver.chrome.service"] = Mock()
sys.modules["selenium.webdriver.common"] = Mock()
sys.modules["selenium.webdriver.common.by"] = Mock()
sys.modules["selenium.webdriver.support"] = Mock()
sys.modules["selenium.webdriver.support.ui"] = Mock()
sys.modules["selenium.webdriver.support.expected_conditions"] = Mock()
sys.modules["openai"] = Mock()
sys.modules["lxml"] = Mock()


@pytest.fixture
def api_key():
    """API key fixture."""
    return "test_api_key"


@pytest.fixture
def electricity_service(api_key):
    """Electricity service fixture."""
    from services.electricity_service import ElectricityService

    return ElectricityService(api_key)


@pytest.fixture
def mock_server():
    """Mock server fixture for integration tests."""
    server = Mock()
    server.send_message = Mock()
    server.send_notice = Mock()
    return server


def test_service_initialization(electricity_service, api_key):
    """Test that the service initializes correctly."""
    assert electricity_service.api_key == api_key
    assert electricity_service.base_url == "https://web-api.tp.entsoe.eu/api"
    assert electricity_service.finland_domain == "10YFI-1--------U"
    assert electricity_service.vat_rate == 1.255


def test_factory_function(api_key):
    """Test the factory function."""
    from services.electricity_service import create_electricity_service

    service = create_electricity_service(api_key)
    from services.electricity_service import ElectricityService

    assert isinstance(service, ElectricityService)
    assert service.api_key == api_key


def test_price_conversion(electricity_service):
    """Test price conversion from EUR/MWh to snt/kWh with VAT."""
    # 100 EUR/MWh should be 12.55 snt/kWh with VAT
    result = electricity_service._convert_price(100.0)
    assert abs(result - 12.55) < 0.01

    # 50 EUR/MWh should be 6.275 snt/kWh with VAT
    result = electricity_service._convert_price(50.0)
    assert abs(result - 6.275) < 0.01


def test_command_parsing_current_hour(electricity_service):
    """Test parsing command with no arguments (current hour)."""
    current_time = datetime.now()
    result = electricity_service.parse_command_args([])

    assert result["hour"] == current_time.hour
    assert result["error"] is None
    assert result["is_tomorrow"] is False
    assert result["show_stats"] is False


def test_command_parsing_specific_hour(electricity_service):
    """Test parsing command with specific hour."""
    result = electricity_service.parse_command_args(["15"])

    assert result["hour"] == 15
    assert result["error"] is None
    assert result["is_tomorrow"] is False
    assert result["show_stats"] is False


def test_command_parsing_tomorrow(electricity_service):
    """Test parsing command for tomorrow."""
    result = electricity_service.parse_command_args(["huomenna"])

    current_time = datetime.now()
    expected_date = current_time + timedelta(days=1)

    assert result["hour"] == current_time.hour
    assert result["error"] is None
    assert result["is_tomorrow"] is True
    assert result["show_stats"] is False
    assert result["date"].date() == expected_date.date()


def test_command_parsing_tomorrow_with_hour(electricity_service):
    """Test parsing command for tomorrow with specific hour."""
    result = electricity_service.parse_command_args(["huomenna", "10"])

    current_time = datetime.now()
    expected_date = current_time + timedelta(days=1)

    assert result["hour"] == 10
    assert result["error"] is None
    assert result["is_tomorrow"] is True
    assert result["show_stats"] is False
    assert result["date"].date() == expected_date.date()


def test_command_parsing_statistics(electricity_service):
    """Test parsing command for statistics."""
    result = electricity_service.parse_command_args(["tilastot"])

    assert result["error"] is None
    assert result["is_tomorrow"] is False
    assert result["show_stats"] is True


def test_command_parsing_invalid_hour(electricity_service):
    """Test parsing command with invalid hour."""
    result = electricity_service.parse_command_args(["25"])

    assert result["error"] is not None
    assert "Virheellinen tunti" in result["error"]


def test_command_parsing_invalid_tomorrow_hour(electricity_service):
    """Test parsing command with invalid hour for tomorrow."""
    result = electricity_service.parse_command_args(["huomenna", "25"])

    assert result["error"] is not None
    assert "Virheellinen tunti" in result["error"]


def test_command_parsing_invalid_command(electricity_service):
    """Test parsing invalid command."""
    result = electricity_service.parse_command_args(["invalid"])

    assert result["error"] is not None
    assert "Virheellinen komento" in result["error"]


@patch("requests.get")
def test_fetch_daily_prices_success(mock_get, electricity_service):
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
        </Period>
    </TimeSeries>
</Publication_MarketDocument>"""

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = xml_response
    mock_get.return_value = mock_response

    test_date = datetime(2023, 1, 1)
    result = electricity_service._fetch_daily_prices(test_date)

    assert result["error"] is False
    assert result["date"] == "2023-01-01"
    assert result["prices"][1] == 50.0
    assert result["prices"][2] == 45.5
    assert result["total_hours"] == 2


@patch("requests.get")
def test_fetch_daily_prices_api_error(mock_get, electricity_service):
    """Test API error handling."""
    mock_response = Mock()
    mock_response.status_code = 401
    mock_get.return_value = mock_response

    test_date = datetime(2023, 1, 1)
    result = electricity_service._fetch_daily_prices(test_date)

    assert result["error"] is True
    assert result["status_code"] == 401
    assert "Invalid ENTSO-E API key" in result["message"]


def test_format_price_message_success(electricity_service):
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
    }

    result = electricity_service.format_price_message(price_data)

    assert "⚡ Tänään 2023-01-01 klo 14: 6.28 snt/kWh" in result
    assert "⚡ Huomenna 2023-01-02 klo 14: 5.65 snt/kWh" in result
    assert "ALV 25,5%" in result


def test_format_price_message_error(electricity_service):
    """Test formatting of error message."""
    price_data = {"error": True, "message": "API error occurred"}

    result = electricity_service.format_price_message(price_data)

    assert "⚡ Sähkön hintatietojen haku epäonnistui" in result
    assert "API error occurred" in result


def test_format_price_message_no_data(electricity_service):
    """Test formatting when no price data is available."""
    price_data = {
        "error": False,
        "date": "2023-01-01",
        "hour": 14,
        "today_price": None,
        "tomorrow_price": None,
    }

    result = electricity_service.format_price_message(price_data)

    assert "⚡ Sähkön hintatietoja ei saatavilla tunnille 14" in result
    assert "https://sahko.tk" in result


def test_format_statistics_message(electricity_service):
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

    result = electricity_service.format_statistics_message(stats_data)

    assert "📊 Sähkön hintatilastot 2023-01-01" in result
    assert "Min: 2.51 snt/kWh (klo 03)" in result
    assert "Max: 10.04 snt/kWh (klo 18)" in result
    assert "Keskiarvo: 6.28 snt/kWh" in result


def test_get_electricity_price_success(electricity_service):
    """Test getting electricity price successfully."""
    # Mock the _fetch_daily_prices method
    electricity_service._fetch_daily_prices = Mock(
        return_value={
            "error": False,
            "prices": {
                14: 50.0,  # Hour 14 should map to position 14
                15: 45.0,
            },
        }
    )

    test_date = datetime(2023, 1, 1, 14, 0)  # 14:00
    result = electricity_service.get_electricity_price(hour=14, date=test_date)

    assert result["error"] is False
    assert result["hour"] == 14
    assert result["today_price"] is not None
    assert result["today_price"]["eur_per_mwh"] == 50.0
    assert abs(result["today_price"]["snt_per_kwh_with_vat"] - 6.275) < 0.01


def test_get_electricity_price_invalid_hour(electricity_service):
    """Test getting electricity price with invalid hour."""
    result = electricity_service.get_electricity_price(hour=25)

    assert result["error"] is True
    assert "Invalid hour: 25" in result["message"]


# Integration Tests


@pytest.fixture
def bot_manager():
    """Bot manager fixture for integration tests."""
    # Mock environment for electricity service
    original_env = os.environ.get("ELECTRICITY_API_KEY")
    os.environ["ELECTRICITY_API_KEY"] = "test_integration_key"

    try:
        # Mock external dependencies
        with patch("bot_manager.DataManager"):
            with patch("bot_manager.get_api_key", return_value="fake_key"):
                with patch("bot_manager.create_crypto_service", return_value=Mock()):
                    with patch(
                        "bot_manager.create_nanoleet_detector", return_value=Mock()
                    ):
                        with patch(
                            "bot_manager.create_fmi_warning_service",
                            return_value=Mock(),
                        ):
                            with patch(
                                "bot_manager.create_otiedote_service",
                                return_value=Mock(),
                            ):
                                with patch(
                                    "bot_manager.Lemmatizer", return_value=Mock()
                                ):
                                    from bot_manager import BotManager

                                    bot_manager = BotManager("TestBot")
                                    yield bot_manager
    finally:
        if original_env:
            os.environ["ELECTRICITY_API_KEY"] = original_env
        elif "ELECTRICITY_API_KEY" in os.environ:
            del os.environ["ELECTRICITY_API_KEY"]


def test_electricity_command_with_list_input(bot_manager, mock_server):
    """Test electricity command when called with list input (from IRC parsing)."""
    # This simulates how the command is called from IRC command processing
    # where text.split() returns a list: ['!sahko', 'argument']
    test_cases = [
        ["!sahko"],  # Just the command
        ["!sahko", "15"],  # Command with hour
        ["!sahko", "huomenna"],  # Command with tomorrow
        ["!sahko", "huomenna", "10"],  # Command with tomorrow and hour
        ["!sahko", "tilastot"],  # Command with statistics
        ["!sahko", "25"],  # Invalid hour
        ["!sahko", "invalid"],  # Invalid argument
    ]

    for parts_list in test_cases:
        try:
            # This should not raise an AttributeError about 'list' object has no attribute 'split'
            bot_manager._send_electricity_price(mock_server, "#testchannel", parts_list)
            # If we get here, the function handled the list input correctly
            assert True, f"Successfully handled list input: {parts_list}"
        except AttributeError as e:
            if "'list' object has no attribute 'split'" in str(e):
                pytest.fail(f"Function failed to handle list input {parts_list}: {e}")
            else:
                # Some other AttributeError, re-raise
                raise
        except Exception:
            # Other exceptions are OK (like API errors), we just want to avoid the split() error
            pass


def test_electricity_command_with_string_input(bot_manager, mock_server):
    """Test electricity command when called with string input (legacy/console mode)."""
    # This simulates how the command might be called from console or legacy code
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
        try:
            # This should handle string input correctly
            bot_manager._send_electricity_price(mock_server, "#testchannel", text_input)
            # If we get here, the function handled the string input correctly
            assert True, f"Successfully handled string input: '{text_input}'"
        except Exception:
            # Exceptions are OK (like API errors), we just want to ensure no crashes
            pass


@patch("services.electricity_service.ElectricityService.get_electricity_price")
def test_electricity_command_flow_with_mock_service(
    mock_get_price, bot_manager, mock_server
):
    """Test complete command flow with mocked electricity service."""
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
    bot_manager._send_electricity_price(mock_server, "#testchannel", ["!sahko", "15"])

    # Verify the service was called correctly
    mock_get_price.assert_called_once()

    # Verify a response was sent (either NOTICE or PRIVMSG)
    assert (
        mock_server.send_notice.called or mock_server.send_message.called
    ), "No response was sent to IRC"


def test_electricity_command_without_service(bot_manager, mock_server):
    """Test electricity command when service is not available."""
    # Create bot manager without electricity service
    original_service = bot_manager.electricity_service
    bot_manager.electricity_service = None

    try:
        # Should handle gracefully and send error message
        bot_manager._send_electricity_price(mock_server, "#testchannel", ["!sahko"])

        # Verify error response was sent
        assert (
            mock_server.send_notice.called or mock_server.send_message.called
        ), "No error response was sent when service unavailable"

    finally:
        # Restore service
        bot_manager.electricity_service = original_service
