"""
Weather Service Module

Provides weather information using OpenWeatherMap API.
"""

import requests
import urllib.parse
import random
from datetime import datetime
from typing import Optional, Dict, Any


class WeatherService:
    """Service for fetching weather information."""
    
    def __init__(self, api_key: str):
        """
        Initialize weather service.
        
        Args:
            api_key: OpenWeatherMap API key
        """
        self.api_key = api_key
        self.base_url = "http://api.openweathermap.org/data/2.5"
        
    def get_weather(self, location: str = "Joensuu") -> Dict[str, Any]:
        """
        Get weather information for a location.
        
        Args:
            location: Location name (default: Joensuu)
            
        Returns:
            Dictionary containing weather information or error details
        """
        try:
            location = location.strip().title()
            encoded_location = urllib.parse.quote(location)
            weather_url = f"{self.base_url}/weather?q={encoded_location}&appid={self.api_key}&units=metric&lang=fi"
            
            response = requests.get(weather_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return self._parse_weather_data(data, location)
            else:
                return {
                    'error': True,
                    'message': f"Weather API returned status code {response.status_code}",
                    'status_code': response.status_code
                }
                
        except requests.exceptions.Timeout:
            return {
                'error': True,
                'message': "Weather API request timed out",
                'exception': 'timeout'
            }
        except requests.exceptions.RequestException as e:
            return {
                'error': True,
                'message': f"Weather API request failed: {str(e)}",
                'exception': str(e)
            }
        except Exception as e:
            return {
                'error': True,
                'message': f"Unexpected error: {str(e)}",
                'exception': str(e)
            }
    
    def _parse_weather_data(self, data: Dict[str, Any], location: str) -> Dict[str, Any]:
        """
        Parse weather data from API response.
        
        Args:
            data: Raw weather data from API
            location: Location name
            
        Returns:
            Parsed weather information
        """
        try:
            # Basic weather info
            description = data["weather"][0]["description"].capitalize()
            temp = data["main"]["temp"]
            feels_like = data["main"]["feels_like"]
            humidity = data["main"]["humidity"]
            wind_speed = data["wind"]["speed"]
            pressure = data["main"]["pressure"]
            clouds = data["clouds"]["all"]
            country = data["sys"].get("country", "?")
            
            # Visibility (convert from meters to kilometers)
            visibility = data.get("visibility", 0) / 1000
            
            # Precipitation
            rain = data.get("rain", {}).get("1h", 0)
            snow = data.get("snow", {}).get("1h", 0)
            
            # Sun times
            sunrise = datetime.fromtimestamp(data["sys"]["sunrise"]).strftime("%H:%M")
            sunset = datetime.fromtimestamp(data["sys"]["sunset"]).strftime("%H:%M")
            
            # Wind direction
            wind_deg = data["wind"].get("deg", 0)
            wind_direction = self._get_wind_direction(wind_deg)
            
            # Weather emoji
            main_weather = data["weather"][0]["main"]
            weather_emoji = self._get_weather_emoji(main_weather)
            
            # Pressure analysis
            pressure_analysis = self._analyze_pressure(pressure)
            
            # Coordinates for UV index
            lat = data["coord"]["lat"]
            lon = data["coord"]["lon"]
            uv_index = self._get_uv_index(lat, lon)
            
            return {
                'error': False,
                'location': location,
                'country': country,
                'description': description,
                'temperature': temp,
                'feels_like': feels_like,
                'humidity': humidity,
                'wind_speed': wind_speed,
                'wind_direction': wind_direction,
                'wind_deg': wind_deg,
                'visibility': visibility,
                'pressure': pressure,
                'pressure_analysis': pressure_analysis,
                'clouds': clouds,
                'rain': rain,
                'snow': snow,
                'sunrise': sunrise,
                'sunset': sunset,
                'weather_emoji': weather_emoji,
                'uv_index': uv_index,
                'coordinates': {'lat': lat, 'lon': lon}
            }
            
        except KeyError as e:
            return {
                'error': True,
                'message': f"Missing required field in weather data: {e}",
                'exception': str(e)
            }
        except Exception as e:
            return {
                'error': True,
                'message': f"Error parsing weather data: {str(e)}",
                'exception': str(e)
            }
    
    def _get_wind_direction(self, degrees: float) -> str:
        """Get wind direction emoji from degrees."""
        directions = ["⬆️", "↗️", "➡️", "↘️", "⬇️", "↙️", "⬅️", "↖️"]
        idx = round(degrees % 360 / 45) % 8
        return directions[idx]
    
    def _get_weather_emoji(self, main_weather: str) -> str:
        """Get weather emoji from main weather condition."""
        weather_icons = {
            "Clear": "☀️",
            "Clouds": "☁️",
            "Rain": "🌧️",
            "Drizzle": "🌦️",
            "Thunderstorm": "⛈️",
            "Snow": "❄️",
            "Mist": "🌫️",
            "Smoke": "🌫️",
            "Haze": "🌫️",
            "Dust": "🌪️",
            "Fog": "🌁",
            "Sand": "🌪️",
            "Ash": "🌋",
            "Squall": "💨",
            "Tornado": "🌪️",
        }
        return weather_icons.get(main_weather, "🌈")
    
    def _analyze_pressure(self, pressure: float) -> Dict[str, Any]:
        """Analyze pressure and return visual representation."""
        normal_pressure = 1013.25
        pressure_diff = pressure - normal_pressure
        pressure_percent = (pressure_diff / 1000) * 100
        
        if pressure_diff == 0:
            visual = "〇"  # No change
        elif abs(pressure_percent) > 4:
            visual = "☠"  # Large change
        else:
            if abs(pressure_percent) <= 1:
                visual = "🟢"
            elif abs(pressure_percent) <= 2:
                visual = "🟡"
            elif abs(pressure_percent) <= 3:
                visual = "🟠"
            else:
                visual = "🔴"
        
        return {
            'visual': visual,
            'diff': pressure_diff,
            'percent': pressure_percent
        }
    
    def _get_uv_index(self, lat: float, lon: float) -> Optional[float]:
        """Get UV index for coordinates."""
        try:
            uv_url = f"{self.base_url}/uvi?lat={lat}&lon={lon}&appid={self.api_key}"
            response = requests.get(uv_url, timeout=5)
            
            if response.status_code == 200:
                uv_data = response.json()
                return uv_data.get("value", None)
            else:
                return None
                
        except Exception:
            return None
    
    def format_weather_message(self, weather_data: Dict[str, Any]) -> str:
        """
        Format weather data into a readable message.
        
        Args:
            weather_data: Weather data dictionary
            
        Returns:
            Formatted weather message string
        """
        if weather_data.get('error'):
            return f"Sään haku epäonnistui: {weather_data.get('message', 'Tuntematon virhe')}"
        
        # Random symbol at the beginning
        random_symbol = random.choice(["🌈", "🔮", "🍺", "☀️", "❄️", "🌊", "🔥", "🚴"])
        
        # Build weather message
        weather_info = (
            f"{random_symbol}{weather_data['location']},{weather_data['country']}:"
            f"{weather_data['weather_emoji']} {weather_data['description']}, "
            f"{weather_data['temperature']}°C ({weather_data['feels_like']}🌡️°C), "
            f"💦{weather_data['humidity']}%, "
            f"🍃{weather_data['wind_speed']}{weather_data['wind_direction']}m/s, "
            f"👁 {weather_data['visibility']:.1f} km, "
            f"⚖️{weather_data['pressure']} hPa{weather_data['pressure_analysis']['visual']}, "
            f"☁️{weather_data['clouds']}%, "
            f"🌄{weather_data['sunrise']}-{weather_data['sunset']}🌅"
        )
        
        # Add UV index if available
        if weather_data['uv_index'] is not None:
            weather_info += f", 🔆{weather_data['uv_index']:.1f}"
        
        # Add precipitation info
        if weather_data['rain'] > 0:
            weather_info += f", Sade: {weather_data['rain']} mm/tunti."
        elif weather_data['snow'] > 0:
            weather_info += f", Lumi: {weather_data['snow']} mm/tunti."
        else:
            weather_info += "."
        
        return weather_info


def create_weather_service(api_key: str) -> WeatherService:
    """
    Factory function to create a weather service instance.
    
    Args:
        api_key: OpenWeatherMap API key
        
    Returns:
        WeatherService instance
    """
    return WeatherService(api_key)

