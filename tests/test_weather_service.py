"""
Weather Service Tests

Comprehensive tests for the weather service functionality.
"""

import json
from unittest.mock import Mock, patch
from test_framework import TestCase, TestSuite, TestRunner


def test_weather_service_creation():
    """Test weather service creation."""
    try:
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

        return True
    except Exception as e:
        print(f"Weather service creation test failed: {e}")
        return False


def test_weather_api_success():
    """Test successful weather API response."""
    try:
        from services.weather_service import WeatherService

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

        assert result["error"] == False, "Should not have error"
        assert result["location"] == "Helsinki", "Location should match"
        assert result["country"] == "FI", "Country should match"
        assert result["temperature"] == 22.5, "Temperature should match"
        assert result["description"] == "Clear sky", "Description should be capitalized"
        assert result["weather_emoji"] == "☀️", "Should have clear weather emoji"

        return True
    except Exception as e:
        print(f"Weather API success test failed: {e}")
        return False


def test_weather_api_error():
    """Test weather API error handling."""
    try:
        from services.weather_service import WeatherService

        service = WeatherService("test_key")

        # Test HTTP error
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_get.return_value = mock_response

            result = service.get_weather("NonExistentCity")

        assert result["error"] == True, "Should have error"
        assert "404" in str(result["status_code"]), "Should include status code"

        return True
    except Exception as e:
        print(f"Weather API error test failed: {e}")
        return False


def test_weather_timeout_handling():
    """Test weather API timeout handling."""
    try:
        from services.weather_service import WeatherService
        import requests

        service = WeatherService("test_key")

        with patch("requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.Timeout()

            result = service.get_weather("TestCity")

        assert result["error"] == True, "Should have error"
        assert "timed out" in result["message"].lower(), "Should mention timeout"
        assert result["exception"] == "timeout", "Should have timeout exception type"

        return True
    except Exception as e:
        print(f"Weather timeout test failed: {e}")
        return False


def test_weather_data_parsing():
    """Test weather data parsing functionality."""
    try:
        from services.weather_service import WeatherService

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

        assert result["error"] == False, "Should not have error"
        assert result["location"] == "Stockholm", "Location should match"
        assert result["country"] == "SE", "Country should match"
        assert result["rain"] == 2.5, "Rain amount should match"
        assert result["visibility"] == 8.0, "Visibility should be converted to km"
        assert result["weather_emoji"] == "🌧️", "Should have rain emoji"

        return True
    except Exception as e:
        print(f"Weather data parsing test failed: {e}")
        return False


def test_wind_direction_calculation():
    """Test wind direction emoji calculation."""
    try:
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

        return True
    except Exception as e:
        print(f"Wind direction test failed: {e}")
        return False


def test_weather_emoji_mapping():
    """Test weather condition to emoji mapping."""
    try:
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

        return True
    except Exception as e:
        print(f"Weather emoji test failed: {e}")
        return False


def test_pressure_analysis():
    """Test atmospheric pressure analysis."""
    try:
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
            assert isinstance(result["diff"], float), "Should have pressure difference"
            assert isinstance(
                result["percent"], float
            ), "Should have pressure percentage"

        return True
    except Exception as e:
        print(f"Pressure analysis test failed: {e}")
        return False


def test_uv_index_fetching():
    """Test UV index fetching."""
    try:
        from services.weather_service import WeatherService

        service = WeatherService("test_key")

        # Test successful UV response
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"value": 7.3}
            mock_get.return_value = mock_response

            result = service._get_uv_index(60.17, 24.95)  # Helsinki coordinates

        assert result == 7.3, "Should return UV index value"

        # Test failed UV response
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_get.return_value = mock_response

            result = service._get_uv_index(60.17, 24.95)

        assert result is None, "Should return None on error"

        return True
    except Exception as e:
        print(f"UV index test failed: {e}")
        return False


def test_weather_message_formatting():
    """Test weather message formatting."""
    try:
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

        assert "Joensuu,FI" in result, "Should include location and country"
        assert "☀️" in result, "Should include weather emoji"
        assert "20.5°C" in result, "Should include temperature"
        assert "🔆6.5" in result, "Should include UV index"
        assert result.endswith("."), "Should end with period"

        # Test error weather data formatting
        error_data = {"error": True, "message": "API key invalid"}

        error_result = service.format_weather_message(error_data)
        assert "epäonnistui" in error_result, "Should indicate failure"
        assert "API key invalid" in error_result, "Should include error message"

        return True
    except Exception as e:
        print(f"Weather message formatting test failed: {e}")
        return False


def test_precipitation_handling():
    """Test precipitation (rain/snow) handling."""
    try:
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
        assert "Sade: 5.2 mm/tunti." in rain_result, "Should include rain amount"

        # Test with snow
        snow_data = rain_data.copy()
        snow_data["rain"] = 0
        snow_data["snow"] = 3.1

        snow_result = service.format_weather_message(snow_data)
        assert "Lumi: 3.1 mm/tunti." in snow_result, "Should include snow amount"

        # Test with no precipitation
        no_precip_data = rain_data.copy()
        no_precip_data["rain"] = 0
        no_precip_data["snow"] = 0

        no_precip_result = service.format_weather_message(no_precip_data)
        assert no_precip_result.endswith(
            "."
        ), "Should end with period when no precipitation"
        assert "Sade:" not in no_precip_result, "Should not mention rain"
        assert "Lumi:" not in no_precip_result, "Should not mention snow"

        return True
    except Exception as e:
        print(f"Precipitation handling test failed: {e}")
        return False


def test_malformed_api_response():
    """Test handling of malformed API responses."""
    try:
        from services.weather_service import WeatherService

        service = WeatherService("test_key")

        # Test missing required fields
        incomplete_data = {
            "weather": [{"description": "test"}],
            # Missing main, wind, etc.
        }

        result = service._parse_weather_data(incomplete_data, "Test")
        assert result["error"] == True, "Should have error for incomplete data"
        assert (
            "Missing required field" in result["message"]
        ), "Should mention missing field"

        return True
    except Exception as e:
        print(f"Malformed API response test failed: {e}")
        return False


def register_weather_service_tests(runner: TestRunner):
    """Register weather service tests with the test runner."""

    tests = [
        TestCase(
            name="weather_service_creation",
            description="Test weather service creation",
            test_func=test_weather_service_creation,
            category="weather_service",
        ),
        TestCase(
            name="weather_api_success",
            description="Test successful weather API response",
            test_func=test_weather_api_success,
            category="weather_service",
        ),
        TestCase(
            name="weather_api_error",
            description="Test weather API error handling",
            test_func=test_weather_api_error,
            category="weather_service",
        ),
        TestCase(
            name="weather_timeout_handling",
            description="Test weather API timeout handling",
            test_func=test_weather_timeout_handling,
            category="weather_service",
        ),
        TestCase(
            name="weather_data_parsing",
            description="Test weather data parsing",
            test_func=test_weather_data_parsing,
            category="weather_service",
        ),
        TestCase(
            name="wind_direction_calculation",
            description="Test wind direction calculation",
            test_func=test_wind_direction_calculation,
            category="weather_service",
        ),
        TestCase(
            name="weather_emoji_mapping",
            description="Test weather emoji mapping",
            test_func=test_weather_emoji_mapping,
            category="weather_service",
        ),
        TestCase(
            name="pressure_analysis",
            description="Test pressure analysis",
            test_func=test_pressure_analysis,
            category="weather_service",
        ),
        TestCase(
            name="uv_index_fetching",
            description="Test UV index fetching",
            test_func=test_uv_index_fetching,
            category="weather_service",
        ),
        TestCase(
            name="weather_message_formatting",
            description="Test weather message formatting",
            test_func=test_weather_message_formatting,
            category="weather_service",
        ),
        TestCase(
            name="precipitation_handling",
            description="Test precipitation handling",
            test_func=test_precipitation_handling,
            category="weather_service",
        ),
        TestCase(
            name="malformed_api_response",
            description="Test malformed API response handling",
            test_func=test_malformed_api_response,
            category="weather_service",
        ),
    ]

    suite = TestSuite(
        name="Weather_Service",
        description="Tests for weather service functionality",
        tests=tests,
    )

    runner.add_suite(suite)
