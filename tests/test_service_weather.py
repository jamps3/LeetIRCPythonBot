#!/usr/bin/env python3
"""
Pytest Weather Service tests

Comprehensive tests for the weather service functionality.
"""

import json
import os
import sys
from unittest.mock import Mock, patch

import pytest

# Add the parent directory to Python path to ensure imports work in CI
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


@pytest.fixture
def weather_service():
    """Create a weather service instance for testing."""
    from services.weather_service import WeatherService

    return WeatherService("test_api_key")


@pytest.fixture
def mock_weather_response():
    """Mock successful weather API response data."""
    return {
        "weather": [{"description": "clear sky", "main": "Clear"}],
        "main": {
            "temp": 22.5,
            "feels_like": 23.1,
            "humidity": 60,
            "pressure": 1013,
        },
        "wind": {"speed": 3.2, "deg": 180},
        "clouds": {"all": 20},
        "visibility": 10000,
        "rain": {},
        "snow": {},
        "sys": {"country": "FI", "sunrise": 1640000000, "sunset": 1640030000},
        "coord": {"lat": 62.6, "lon": 29.76},
    }


def test_weather_service_creation():
    """Test weather service creation."""
    from services.weather_service import WeatherService, create_weather_service

    # Test direct instantiation
    service = WeatherService("test_api_key")
    assert service.api_key == "test_api_key", "API key should be set"
    assert (
        service.base_url == "http://api.openweathermap.org/data/2.5"
    ), "Base URL should be set"

    # Test factory function
    service2 = create_weather_service("another_key")
    assert service2.api_key == "another_key", "Factory should set API key"
    assert isinstance(
        service2, WeatherService
    ), "Factory should return WeatherService instance"


def test_weather_api_success(weather_service, mock_weather_response):
    """Test successful weather API response."""
    with patch("requests.get") as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_weather_response
        mock_get.return_value = mock_response

        # Also mock UV response
        with patch.object(weather_service, "_get_uv_index", return_value=5.2):
            result = weather_service.get_weather("Helsinki")

    assert result["error"] is False, "Should not have error"
    assert result["location"] == "Helsinki", "Location should match"
    assert result["country"] == "FI", "Country should match"
    assert result["temperature"] == 22.5, "Temperature should match"
    assert result["description"] == "Clear sky", "Description should be capitalized"
    assert result["weather_emoji"] == "☀️", "Should have clear weather emoji"


def test_weather_api_error(weather_service):
    """Test weather API error handling."""
    # Test HTTP error
    with patch("requests.get") as mock_get:
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = weather_service.get_weather("NonExistentCity")

    assert result["error"] is True, "Should have error"
    assert "404" in str(result["status_code"]), "Should include status code"


def test_weather_timeout_handling(weather_service):
    """Test weather API timeout handling."""
    import requests

    with patch("requests.get") as mock_get:
        mock_get.side_effect = requests.exceptions.Timeout()

        result = weather_service.get_weather("TestCity")

    assert result["error"] is True, "Should have error"
    assert "timed out" in result["message"].lower(), "Should mention timeout"
    assert result["exception"] == "timeout", "Should have timeout exception type"


def test_weather_data_parsing(weather_service):
    """Test weather data parsing functionality."""
    # Test complete weather data
    test_data = {
        "weather": [{"description": "light rain", "main": "Rain"}],
        "main": {
            "temp": 15.3,
            "feels_like": 14.8,
            "humidity": 85,
            "pressure": 1008,
        },
        "wind": {"speed": 5.5, "deg": 270},
        "clouds": {"all": 90},
        "visibility": 8000,
        "rain": {"1h": 2.5},
        "snow": {},
        "sys": {"country": "SE", "sunrise": 1640000000, "sunset": 1640030000},
        "coord": {"lat": 59.33, "lon": 18.07},
    }

    result = weather_service._parse_weather_data(test_data, "Stockholm")

    assert result["error"] is False, "Should not have error"
    assert result["location"] == "Stockholm", "Location should match"
    assert result["country"] == "SE", "Country should match"
    assert result["rain"] == 2.5, "Rain amount should match"
    assert result["visibility"] == 8.0, "Visibility should be converted to km"
    assert result["weather_emoji"] == "🌧️", "Should have rain emoji"


@pytest.mark.parametrize(
    "degrees,expected_emoji",
    [
        (0, "⬆️"),  # North
        (45, "↗️"),  # Northeast
        (90, "➡️"),  # East
        (135, "↘️"),  # Southeast
        (180, "⬇️"),  # South
        (225, "↙️"),  # Southwest
        (270, "⬅️"),  # West
        (315, "↖️"),  # Northwest
        (360, "⬆️"),  # Full circle back to North
    ],
)
def test_wind_direction_calculation(weather_service, degrees, expected_emoji):
    """Test wind direction emoji calculation."""
    result = weather_service._get_wind_direction(degrees)
    assert (
        result == expected_emoji
    ), f"Wind direction for {degrees}° should be {expected_emoji}, got {result}"


@pytest.mark.parametrize(
    "condition,expected_emoji",
    [
        ("Clear", "☀️"),
        ("Clouds", "☁️"),
        ("Rain", "🌧️"),
        ("Snow", "❄️"),
        ("Thunderstorm", "⛈️"),
        ("Fog", "🌁"),
        ("UnknownCondition", "🌈"),  # Default
    ],
)
def test_weather_emoji_mapping(weather_service, condition, expected_emoji):
    """Test weather condition to emoji mapping."""
    result = weather_service._get_weather_emoji(condition)
    assert (
        result == expected_emoji
    ), f"Weather emoji for {condition} should be {expected_emoji}, got {result}"


@pytest.mark.parametrize(
    "pressure,expected_visual",
    [
        (1013.25, "〇"),  # Normal pressure
        (1020, "🟢"),  # Slightly high
        (1025, "🟡"),  # Moderately high
        (1040, "🟠"),  # High
        (1060, "☠"),  # Very high
        (1005, "🟢"),  # Slightly low
        (995, "🟡"),  # Moderately low
        (985, "🟠"),  # Low
        (980, "🔴"),  # Lower
        (950, "☠"),  # Very low
    ],
)
def test_pressure_analysis(weather_service, pressure, expected_visual):
    """Test atmospheric pressure analysis."""
    result = weather_service._analyze_pressure(pressure)
    assert (
        result["visual"] == expected_visual
    ), f"Pressure visual for {pressure} hPa should be {expected_visual}, got {result['visual']}"
    assert isinstance(result["diff"], float), "Should have pressure difference"
    assert isinstance(result["percent"], float), "Should have pressure percentage"


def test_uv_index_fetching(weather_service):
    """Test UV index fetching."""
    # Test successful UV response
    with patch("requests.get") as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"value": 7.3}
        mock_get.return_value = mock_response

        result = weather_service._get_uv_index(60.17, 24.95)  # Helsinki coordinates

    assert result == 7.3, "Should return UV index value"

    # Test failed UV response
    with patch("requests.get") as mock_get:
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = weather_service._get_uv_index(60.17, 24.95)

    assert result is None, "Should return None on error"


def test_weather_message_formatting(weather_service):
    """Test weather message formatting."""
    # Test successful weather data formatting
    weather_data = {
        "error": False,
        "location": "Joensuu",
        "country": "FI",
        "description": "Clear sky",
        "temperature": 20.5,
        "feels_like": 21.0,
        "humidity": 65,
        "wind_speed": 3.0,
        "wind_direction": "➡️",
        "visibility": 10.0,
        "pressure": 1015,
        "pressure_analysis": {"visual": "🟢"},
        "clouds": 25,
        "sunrise": "06:30",
        "sunset": "20:45",
        "weather_emoji": "☀️",
        "uv_index": 6.5,
        "rain": 0,
        "snow": 0,
    }

    result = weather_service.format_weather_message(weather_data)

    assert "Joensuu,FI" in result, "Should include location and country"
    assert "☀️" in result, "Should include weather emoji"
    assert "20.5°C" in result, "Should include temperature"
    assert "🔆6.5" in result, "Should include UV index"
    assert result.endswith("."), "Should end with period"

    # Test error weather data formatting
    error_data = {"error": True, "message": "API key invalid"}

    error_result = weather_service.format_weather_message(error_data)
    assert "epäonnistui" in error_result, "Should indicate failure"
    assert "API key invalid" in error_result, "Should include error message"


def test_precipitation_handling(weather_service):
    """Test precipitation (rain/snow) handling."""
    # Test with rain
    rain_data = {
        "error": False,
        "location": "Test",
        "country": "XX",
        "description": "Rain",
        "temperature": 10,
        "feels_like": 9,
        "humidity": 90,
        "wind_speed": 2,
        "wind_direction": "⬆️",
        "visibility": 5.0,
        "pressure": 1000,
        "pressure_analysis": {"visual": "🟢"},
        "clouds": 100,
        "sunrise": "07:00",
        "sunset": "19:00",
        "weather_emoji": "🌧️",
        "uv_index": None,
        "rain": 5.2,
        "snow": 0,
    }

    rain_result = weather_service.format_weather_message(rain_data)
    assert "Sade: 5.2 mm/tunti." in rain_result, "Should include rain amount"

    # Test with snow
    snow_data = rain_data.copy()
    snow_data["rain"] = 0
    snow_data["snow"] = 3.1

    snow_result = weather_service.format_weather_message(snow_data)
    assert "Lumi: 3.1 mm/tunti." in snow_result, "Should include snow amount"


def test_weather_service_edge_cases(weather_service):
    """Test weather service edge cases."""
    # Test with missing wind data
    incomplete_data = {
        "weather": [{"description": "clear sky", "main": "Clear"}],
        "main": {"temp": 20.0, "feels_like": 20.0, "humidity": 50, "pressure": 1013},
        "clouds": {"all": 0},
        "visibility": 10000,
        "rain": {},
        "snow": {},
        "sys": {"country": "FI", "sunrise": 1640000000, "sunset": 1640030000},
        "coord": {"lat": 60.0, "lon": 24.0},
    }

    result = weather_service._parse_weather_data(incomplete_data, "Test")
    assert result["error"] is False, "Should handle missing wind data"
    assert result["wind_speed"] == 0, "Should default wind speed to 0"
    assert result["wind_direction"] == "⬆️", "Should have default wind direction"


def test_weather_service_network_errors(weather_service):
    """Test weather service network error handling."""
    import requests

    # Test connection error
    with patch("requests.get") as mock_get:
        mock_get.side_effect = requests.exceptions.ConnectionError()
        result = weather_service.get_weather("TestCity")

    assert result["error"] is True, "Should have error for connection issues"
    assert "connection" in result["message"].lower(), "Should mention connection error"

    # Test general request exception
    with patch("requests.get") as mock_get:
        mock_get.side_effect = requests.exceptions.RequestException("General error")
        result = weather_service.get_weather("TestCity")

    assert result["error"] is True, "Should have error for general request issues"


def test_weather_service_api_key_validation(weather_service):
    """Test API key validation."""
    # Test with empty API key
    empty_key_service = weather_service.__class__("")
    assert empty_key_service.api_key == "", "Should accept empty API key"

    # Test with None API key
    none_key_service = weather_service.__class__(None)
    assert none_key_service.api_key is None, "Should accept None API key"


def test_weather_coordinates_handling(weather_service):
    """Test coordinate handling in weather data."""
    test_data = {
        "weather": [{"description": "clear sky", "main": "Clear"}],
        "main": {"temp": 20, "feels_like": 20, "humidity": 50, "pressure": 1013},
        "wind": {"speed": 2, "deg": 90},
        "clouds": {"all": 0},
        "visibility": 10000,
        "rain": {},
        "snow": {},
        "sys": {"country": "FI", "sunrise": 1640000000, "sunset": 1640030000},
        "coord": {"lat": 60.1699, "lon": 24.9384},  # Helsinki
    }

    result = weather_service._parse_weather_data(test_data, "Helsinki")
    assert "lat" in result, "Should include latitude"
    assert "lon" in result, "Should include longitude"
    assert result["lat"] == 60.1699, "Should preserve latitude precision"
    assert result["lon"] == 24.9384, "Should preserve longitude precision"


def test_weather_generic_exception_handling(weather_service):
    """Test generic exception handling in get_weather."""
    with patch("requests.get") as mock_get:
        mock_get.side_effect = ValueError("boom")
        result = weather_service.get_weather("TestCity")

    assert result["error"] is True, "Should have error for unexpected exceptions"
    assert "Unexpected error" in result["message"], "Should indicate unexpected error"


def test_parse_weather_data_missing_field_returns_error(weather_service):
    """Test that missing required fields result in a proper error."""
    data = {
        "weather": [{"description": "clear sky", "main": "Clear"}],
        # 'main' is intentionally missing to trigger KeyError
        "clouds": {"all": 0},
        "visibility": 10000,
        "sys": {"country": "FI", "sunrise": 1640000000, "sunset": 1640030000},
        "coord": {"lat": 60.0, "lon": 24.0},
    }

    result = weather_service._parse_weather_data(data, "Test")

    assert result["error"] is True, "Should have error when required field is missing"
    assert "Missing required field" in result["message"], "Should mention missing field"
    assert "main" in result["message"].lower(), "Should include the missing key name"


def test_parse_weather_data_general_exception_returns_error(weather_service):
    """Test that non-KeyError exceptions are handled gracefully."""
    data = {
        "weather": None,  # Will cause TypeError when indexing
        "main": {"temp": 20, "feels_like": 20, "humidity": 50, "pressure": 1013},
        "clouds": {"all": 0},
        "visibility": 10000,
        "sys": {"country": "FI", "sunrise": 1640000000, "sunset": 1640030000},
        "coord": {"lat": 60.0, "lon": 24.0},
    }

    result = weather_service._parse_weather_data(data, "Test")

    assert result["error"] is True, "Should have error when parsing fails"
    assert (
        "Error parsing weather data" in result["message"]
    ), "Should indicate parsing error"


def test_uv_index_exception_returns_none(weather_service):
    """Test that exceptions in UV index fetching return None."""
    with patch("requests.get") as mock_get:
        mock_get.side_effect = Exception("network down")
        result = weather_service._get_uv_index(1.0, 2.0)

    assert result is None, "Should return None on exception"
