"""
Service Manager Module

Manages initialization and lifecycle of all external services used by the bot.
This includes weather, GPT, electricity, YouTube, crypto, Alko, Otiedote, and FMI services.
"""

import os
from typing import Any, Dict, Optional

import logger
from config import get_api_key

logger = logger.get_logger("ServiceManager")


class ServiceManager:
    """
    Manages all external services used by the bot.

    This class handles:
    - Service initialization with proper error handling
    - API key validation
    - Service availability checking
    - Graceful fallback when services are unavailable
    """

    def __init__(self):
        """Initialize the service manager."""
        self.services: Dict[str, Any] = {}

        # Initialize all services
        self._initialize_weather_service()
        self._initialize_gpt_service()
        self._initialize_electricity_service()
        self._initialize_youtube_service()
        self._initialize_crypto_service()
        self._initialize_alko_service()
        self._initialize_drug_service()
        self._initialize_leet_detector()
        self._initialize_fmi_warning_service()
        self._initialize_otiedote_service()

        logger.info("Service manager initialization complete")

    def _initialize_weather_service(self):
        """Initialize weather service if API key is available."""
        try:
            from services.weather_service import WeatherService

            weather_api_key = get_api_key("WEATHER_API_KEY")
            if weather_api_key:
                self.services["weather"] = WeatherService(weather_api_key)
                logger.info("🌤️ Weather service initialized")
            else:
                logger.warning(
                    "⚠️  No weather API key found. Weather commands will not work."
                )
                self.services["weather"] = None
        except ImportError as e:
            logger.warning(f"Warning: Weather service not available: {e}")
            self.services["weather"] = None

    def _initialize_gpt_service(self):
        """Initialize GPT service if API key is available."""
        try:
            from services.gpt_service import GPTService

            openai_api_key = get_api_key("OPENAI_API_KEY")
            history_file = os.getenv("HISTORY_FILE", "data/conversation_history.json")
            history_limit = int(os.getenv("GPT_HISTORY_LIMIT", "100"))

            if openai_api_key:
                self.services["gpt"] = GPTService(
                    openai_api_key, history_file, history_limit
                )
                logger.info(
                    f"🤖 GPT chat service initialized (history limit: {history_limit} messages)."
                )
                # Log the OpenAI model in use at startup
                logger.info(f"🧠 OpenAI model: {self.services['gpt'].model}")
            else:
                logger.warning("⚠️  No OpenAI API key found. AI chat will not work.")
                self.services["gpt"] = None
        except ImportError as e:
            logger.warning(f"GPT service not available: {e}")
            self.services["gpt"] = None

    def _initialize_electricity_service(self):
        """Initialize electricity service if available."""
        try:
            from services.electricity_service import create_electricity_service

            electricity_api_key = get_api_key("ELECTRICITY_API_KEY")
            if electricity_api_key:
                self.services["electricity"] = create_electricity_service(
                    electricity_api_key
                )
                logger.info("⚡ Electricity price service initialized.")
            else:
                logger.warning(
                    "⚠️  No electricity API key found. Electricity price commands will not work."
                )
                self.services["electricity"] = None
        except ImportError as e:
            logger.warning(f"Electricity service not available: {e}")
            self.services["electricity"] = None

    def _initialize_youtube_service(self):
        """Initialize YouTube service if API key is available."""
        try:
            from services.youtube_service import create_youtube_service

            youtube_api_key = get_api_key("YOUTUBE_API_KEY")
            if youtube_api_key:
                self.services["youtube"] = create_youtube_service(youtube_api_key)
                logger.info("▶️ YouTube service initialized.")
            else:
                logger.warning(
                    "⚠️  No YouTube API key found. YouTube commands will not work."
                )
                self.services["youtube"] = None
        except ImportError as e:
            logger.warning(f"YouTube service not available: {e}")
            self.services["youtube"] = None

    def _initialize_crypto_service(self):
        """Initialize crypto service."""
        try:
            from services.crypto_service import create_crypto_service

            self.services["crypto"] = create_crypto_service()
            logger.info("🪙 Crypto service initialized (using CoinGecko API).")
        except ImportError as e:
            logger.warning(f"Crypto service not available: {e}")
            self.services["crypto"] = None

    def _initialize_alko_service(self):
        """Initialize Alko service."""
        try:
            from services.alko_service import create_alko_service

            self.services["alko"] = create_alko_service()
            logger.info("🍺 Alko service initialized.")
        except ImportError as e:
            logger.warning(f"Alko service not available: {e}")
            self.services["alko"] = None

    def _initialize_drug_service(self):
        """Initialize drug service."""
        try:
            from services.drug_service import create_drug_service

            self.services["drug"] = create_drug_service()
            logger.info("💊 Drug service initialized.")
        except Exception as e:
            logger.warning(f"Drug service initialization failed: {e}")
            self.services["drug"] = None

    def _initialize_leet_detector(self):
        """Initialize leet detector."""
        try:
            from leet_detector import create_leet_detector

            self.services["leet_detector"] = create_leet_detector()
            logger.info("🎯 Leet detector initialized.")
        except ImportError as e:
            logger.warning(f"Leet detector not available: {e}")
            self.services["leet_detector"] = None

    def _initialize_fmi_warning_service(self):
        """Initialize FMI warning service."""
        try:
            from config import get_config
            from services.fmi_warning_service import create_fmi_warning_service

            config = get_config()
            self.services["fmi_warning"] = create_fmi_warning_service(
                callback=lambda warnings: None,  # Will be set by message handler
                state_file=config.state_file,
            )
            logger.info("⚠️ FMI warning service initialized.")
        except ImportError as e:
            logger.warning(f"FMI warning service not available: {e}")
            self.services["fmi_warning"] = None

    def _initialize_otiedote_service(self):
        """Initialize Otiedote service."""
        try:
            from config import get_config
            from services.otiedote_json_service import create_otiedote_service

            config = get_config()
            self.services["otiedote"] = create_otiedote_service(
                callback=lambda title, url, description: None,  # Will be set by message handler
                state_file=config.state_file,
            )
            logger.info("📢 Otiedote monitoring service initialized.")
        except ImportError as e:
            logger.warning(f"Otiedote service not available: {e}")
            self.services["otiedote"] = None

    def get_service(self, service_name: str) -> Optional[Any]:
        """
        Get a service instance by name.

        Args:
            service_name: Name of the service to retrieve

        Returns:
            Service instance or None if not available
        """
        return self.services.get(service_name)

    def is_service_available(self, service_name: str) -> bool:
        """
        Check if a service is available.

        Args:
            service_name: Name of the service to check

        Returns:
            True if service is available, False otherwise
        """
        return self.services.get(service_name) is not None

    def get_available_services(self) -> Dict[str, Any]:
        """
        Get all available services.

        Returns:
            Dictionary of service name -> service instance for available services
        """
        return {
            name: service
            for name, service in self.services.items()
            if service is not None
        }

    def get_unavailable_services(self) -> list[str]:
        """
        Get list of unavailable services.

        Returns:
            List of service names that are not available
        """
        return [name for name, service in self.services.items() if service is None]


def create_service_manager() -> ServiceManager:
    """
    Factory function to create a service manager instance.

    Returns:
        ServiceManager instance
    """
    return ServiceManager()
