"""
Services Package

This package contains all external service integrations for the IRC bot.
"""

from .crypto_service import CryptoService, create_crypto_service
from .weather_service import WeatherService, create_weather_service

__all__ = [
    "WeatherService",
    "create_weather_service",
    "CryptoService",
    "create_crypto_service",
]
