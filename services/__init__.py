"""
Services Package

This package contains all external service integrations for the IRC bot.
"""

from .weather_service import WeatherService, create_weather_service
from .crypto_service import CryptoService, create_crypto_service

__all__ = [
    "WeatherService",
    "create_weather_service",
    "CryptoService",
    "create_crypto_service",
]
