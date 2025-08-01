"""
Weather Service Tests

Comprehensive tests for the weather service functionality.
"""

import json
import os
import sys
from unittest.mock import Mock, patch

# Add the parent directory to Python path to ensure imports work in CI
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


def test_weather_service_creation():
    """Test weather service creation."""
    # Direct import to avoid services/__init__.py issues with mocked modules
    sys.path.insert(0, os.path.join(parent_dir, 'services'))
    from weather_service import WeatherService, create_weather_service

    # Test direct instantiation
    service = WeatherService("test_api_key")
    assert service.api_key == "test_api_key"
    assert service.base_url == "http://api.openweathermap.org/data/2.5"

    # Test factory function
    service2 = create_weather_service("another_key")
    assert service2.api_key == "another_key"
    assert isinstance(service2, WeatherService)


def test_weather_api_success():
    """Test successful weather API response."""
    # Direct import to avoid services/__init__.py issues with mocked modules
    sys.path.insert(0, os.path.join(parent_dir, 'services'))
    from weather_service import WeatherService

    # Mock response data
    mock_response_data = {
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

    service = WeatherService("test_key")

    with patch("requests.get") as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_get.return_value = mock_response

        # Also mock UV response
        with patch.object(service, "_get_uv_index", return_value=5.2):
            result = service.get_weather("Helsinki")

    assert result["error"] is False
    assert result["location"] == "Helsinki"
    assert result["country"] == "FI"
    assert result["temperature"] == 22.5
    assert result["description"] == "Clear sky"
    assert result["weather_emoji"] == "☀️"


def test_weather_api_error():
    """Test weather API error handling."""
    # Direct import to avoid services/__init__.py issues with mocked modules
    sys.path.insert(0, os.path.join(parent_dir, 'services'))
    from weather_service import WeatherService

    service = WeatherService("test_key")

    # Test HTTP error
    with patch("requests.get") as mock_get:
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = service.get_weather("NonExistentCity")

    assert result["error"] is True
    assert "404" in str(result["status_code"])


def test_weather_timeout_handling():
    """Test weather API timeout handling."""
    import requests
    # Direct import to avoid services/__init__.py issues with mocked modules
    sys.path.insert(0, os.path.join(parent_dir, 'services'))
    from weather_service import WeatherService

    service = WeatherService("test_key")

    with patch("requests.get") as mock_get:
        mock_get.side_effect = requests.exceptions.Timeout()

        result = service.get_weather("TestCity")

    assert result["error"] is True
    assert "timed out" in result["message"].lower()
    assert result["exception"] == "timeout"


def test_weather_data_parsing():
    """Test weather data parsing functionality."""
    # Direct import to avoid services/__init__.py issues with mocked modules
    sys.path.insert(0, os.path.join(parent_dir, 'services'))
    from weather_service import WeatherService

    service = WeatherService("test_key")

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

    result = service._parse_weather_data(test_data, "Stockholm")

    assert result["error"] is False
    assert result["location"] == "Stockholm"
    assert result["country"] == "SE"
    assert result["rain"] == 2.5
    assert result["visibility"] == 8.0  # Converted to km
    assert result["weather_emoji"] == "🌧️"


def test_wind_direction_calculation():
    """Test wind direction emoji calculation."""
    from services.weather_service import WeatherService

    service = WeatherService("test_key")

    test_cases = [
        (0, "⬆️"),  # North
        (45, "↗️"),  # Northeast
        (90, "➡️"),  # East
        (135, "↘️"),  # Southeast
        (180, "⬇️"),  # South
        (225, "↙️"),  # Southwest
        (270, "⬅️"),  # West
        (315, "↖️"),  # Northwest
        (360, "⬆️"),  # Full circle back to North
    ]

    for degrees, expected_emoji in test_cases:
        result = service._get_wind_direction(degrees)
        assert (
            result == expected_emoji
        ), f"Wind direction for {degrees}° should be {expected_emoji}, got {result}"


def test_weather_emoji_mapping():
    """Test weather condition to emoji mapping."""
    from services.weather_service import WeatherService

    service = WeatherService("test_key")

    test_cases = [
        ("Clear", "☀️"),
        ("Clouds", "☁️"),
        ("Rain", "🌧️"),
        ("Snow", "❄️"),
        ("Thunderstorm", "⛈️"),
        ("Fog", "🌁"),
        ("UnknownCondition", "🌈"),  # Default
    ]

    for condition, expected_emoji in test_cases:
        result = service._get_weather_emoji(condition)
        assert (
            result == expected_emoji
        ), f"Weather emoji for {condition} should be {expected_emoji}, got {result}"


def test_pressure_analysis():
    """Test atmospheric pressure analysis."""
    from services.weather_service import WeatherService

    service = WeatherService("test_key")

    test_cases = [
        (1013.25, "〇"),  # Normal pressure
        (1020, "🟢"),  # Slightly high (abs(percent) = 0.675 <= 1)
        (1025, "🟡"),  # Moderately high (abs(percent) = 1.175 <= 2)
        (1040, "🟠"),  # High (abs(percent) = 2.675 <= 3)
        (1060, "☠"),  # Very high (abs(percent) = 4.675 > 4)
        (1005, "🟢"),  # Slightly low (abs(percent) = 0.825 <= 1)
        (995, "🟡"),  # Moderately low (abs(percent) = 1.825 <= 2)
        (985, "🟠"),  # Low (abs(percent) = 2.825 <= 3)
        (980, "🔴"),  # Lower (abs(percent) = 3.325 <= 4)
        (950, "☠"),  # Very low (abs(percent) = 6.325 > 4)
    ]

    for pressure, expected_visual in test_cases:
        result = service._analyze_pressure(pressure)
        assert (
            result["visual"] == expected_visual
        ), f"Pressure visual for {pressure} hPa should be {expected_visual}, got {result['visual']}"
        assert isinstance(result["diff"], float)
        assert isinstance(result["percent"], float)


def test_uv_index_fetching():
    """Test UV index fetching."""
    from services.weather_service import WeatherService

    service = WeatherService("test_key")

    # Test successful UV response
    with patch("requests.get") as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"value": 7.3}
        mock_get.return_value = mock_response

        result = service._get_uv_index(60.17, 24.95)  # Helsinki coordinates

    assert result == 7.3

    # Test failed UV response
    with patch("requests.get") as mock_get:
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = service._get_uv_index(60.17, 24.95)

    assert result is None


def test_weather_message_formatting():
    """Test weather message formatting."""
    from services.weather_service import WeatherService

    service = WeatherService("test_key")

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

    result = service.format_weather_message(weather_data)

    assert "Joensuu,FI" in result
    assert "☀️" in result
    assert "20.5°C" in result
    assert "🔆6.5" in result
    assert result.endswith(".")

    # Test error weather data formatting
    error_data = {"error": True, "message": "API key invalid"}

    error_result = service.format_weather_message(error_data)
    assert "epäonnistui" in error_result
    assert "API key invalid" in error_result


def test_precipitation_handling():
    """Test precipitation (rain/snow) handling."""
    from services.weather_service import WeatherService

    service = WeatherService("test_key")

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

    rain_result = service.format_weather_message(rain_data)
    assert "Sade: 5.2 mm/tunti." in rain_result

    # Test with snow
    snow_data = rain_data.copy()
    snow_data["rain"] = 0
    snow_data["snow"] = 3.1

    snow_result = service.format_weather_message(snow_data)
    assert "Lumi: 3.1 mm/tunti." in snow_result

    # Test with no precipitation
    no_precip_data = rain_data.copy()
    no_precip_data["rain"] = 0
    no_precip_data["snow"] = 0

    no_precip_result = service.format_weather_message(no_precip_data)
    assert no_precip_result.endswith(".")
    assert "Sade:" not in no_precip_result
    assert "Lumi:" not in no_precip_result


def test_weather_service_edge_cases():
    """Test weather service edge cases."""
    from services.weather_service import WeatherService

    service = WeatherService("test_key")

    # Test empty string location
    with patch("requests.get") as mock_get:
        mock_response = Mock()
        mock_response.status_code = 400
        mock_get.return_value = mock_response

        result = service.get_weather("")

    assert result["error"] is True


def test_weather_service_network_errors():
    """Test weather service network error handling."""
    import requests

    from services.weather_service import WeatherService

    service = WeatherService("test_key")

    # Test connection error
    with patch("requests.get") as mock_get:
        mock_get.side_effect = requests.exceptions.ConnectionError("Test connection error")

        result = service.get_weather("TestCity")

    assert result["error"] is True
    assert "exception" in result
    assert result["exception"]  # Should not be empty
    assert "Test connection error" in result["exception"]


def test_weather_service_api_key_validation():
    """Test API key validation and handling."""
    from services.weather_service import WeatherService

    service = WeatherService("invalid_key")

    with patch("requests.get") as mock_get:
        mock_response = Mock()
        mock_response.status_code = 401  # Unauthorized
        mock_get.return_value = mock_response

        result = service.get_weather("Helsinki")

    assert result["error"] is True
    assert result["status_code"] == 401


def test_weather_coordinates_handling():
    """Test weather coordinates handling."""
    from services.weather_service import WeatherService

    service = WeatherService("test_key")

    # Mock successful response with coordinates
    mock_data = {
        "weather": [{"description": "clear sky", "main": "Clear"}],
        "main": {"temp": 20.0, "feels_like": 19.0, "humidity": 50, "pressure": 1013},
        "wind": {"speed": 2.0, "deg": 0},
        "clouds": {"all": 0},
        "visibility": 10000,
        "rain": {},
        "snow": {},
        "sys": {"country": "FI", "sunrise": 1640000000, "sunset": 1640030000},
        "coord": {"lat": 60.17, "lon": 24.95},  # Helsinki coordinates
    }

    result = service._parse_weather_data(mock_data, "Helsinki")

    assert result["coordinates"]["lat"] == 60.17
    assert result["coordinates"]["lon"] == 24.95
