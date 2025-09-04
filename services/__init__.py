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

# Eagerly import commonly referenced submodules so patch targets like
# 'services.solarwind_service.requests.get' resolve even if the submodule
# hasn't been explicitly imported yet in a given test.
try:
    from . import solarwind_service as solarwind_service  # noqa: F401
except Exception:
    pass
try:
    from . import ipfs_service as ipfs_service  # noqa: F401
except Exception:
    pass
try:
    from . import electricity_service as electricity_service  # noqa: F401
except Exception:
    pass
try:
    from . import eurojackpot_service as eurojackpot_service  # noqa: F401
except Exception:
    pass

# Build __all__ based on what's available
__all__ = [
    "WeatherService",
    "create_weather_service",
    "CryptoService",
    "create_crypto_service",
    # Expose submodules so tests can refer through the package
    "solarwind_service",
    "ipfs_service",
    "electricity_service",
    "eurojackpot_service",
]

if _HAS_FMI_SERVICE:
    __all__.extend(["FMIWarningService", "create_fmi_warning_service"])

if _HAS_OTIEDOTE_SERVICE:
    __all__.extend(["OtiedoteService", "create_otiedote_service"])
