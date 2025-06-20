"""
Services Package

This package contains all external service integrations for the IRC bot.
"""

from .crypto_service import CryptoService, create_crypto_service
from .fmi_warning_service import FMIWarningService, create_fmi_warning_service
from .otiedote_service import OtiedoteService, create_otiedote_service
from .weather_service import WeatherService, create_weather_service

__all__ = [
    "WeatherService",
    "create_weather_service",
    "CryptoService",
    "create_crypto_service",
    "FMIWarningService",
    "create_fmi_warning_service",
    "OtiedoteService",
    "create_otiedote_service",
]
