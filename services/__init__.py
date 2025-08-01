"""
Services Package

This package contains all external service integrations for the IRC bot.
"""

from .crypto_service import CryptoService, create_crypto_service
from .weather_service import WeatherService, create_weather_service

# Conditional imports for services that depend on feedparser
try:
    from .fmi_warning_service import FMIWarningService, create_fmi_warning_service
    _HAS_FMI_SERVICE = True
except ImportError:
    FMIWarningService = None
    create_fmi_warning_service = None
    _HAS_FMI_SERVICE = False

try:
    from .otiedote_service import OtiedoteService, create_otiedote_service
    _HAS_OTIEDOTE_SERVICE = True
except ImportError:
    OtiedoteService = None
    create_otiedote_service = None
    _HAS_OTIEDOTE_SERVICE = False

# Build __all__ based on what's available
__all__ = [
    "WeatherService",
    "create_weather_service",
    "CryptoService",
    "create_crypto_service",
]

if _HAS_FMI_SERVICE:
    __all__.extend(["FMIWarningService", "create_fmi_warning_service"])

if _HAS_OTIEDOTE_SERVICE:
    __all__.extend(["OtiedoteService", "create_otiedote_service"])
