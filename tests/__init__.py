"""
Test Suite Registration Module

This module registers all test suites for the LeetIRC Bot testing framework.
"""

import os
import sys
from unittest.mock import Mock

# Add the parent directory to sys.path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Mock external dependencies at import time to avoid import errors
external_deps = [
    "requests",
    "feedparser",
    "bs4",
    "selenium",
    "youtube_dl",
    "yt_dlp",
    "psutil",
    "matplotlib",
    "openai",
    "websocket",
    "urllib3",
    "certifi",
    "charset_normalizer",
    "idna",
    "lxml",
    "html5lib",
    "pytz",
    "dateutil",
    "cryptography",
    "jwt",
    "aiohttp",
    "asyncio",
    "websockets",
    "discord",
    "tweepy",
    "praw",
    "pandas",
    "numpy",
    "PIL",
    "cv2",
    "googleapiclient",
    "isodate",
]

# Mock main modules
for dep in external_deps:
    sys.modules[dep] = Mock()

# Mock common submodules
submodules = {
    "selenium.webdriver": Mock(),
    "selenium.webdriver.common": Mock(),
    "selenium.webdriver.chrome": Mock(),
    "selenium.webdriver.firefox": Mock(),
    "selenium.webdriver.chrome.options": Mock(),
    "selenium.webdriver.chrome.service": Mock(),
    "selenium.webdriver.common.by": Mock(),
    "selenium.webdriver.support": Mock(),
    "selenium.webdriver.support.ui": Mock(),
    "selenium.webdriver.support.expected_conditions": Mock(),
    "bs4": Mock(),
    "matplotlib.pyplot": Mock(),
    "PIL.Image": Mock(),
    "requests.adapters": Mock(),
    "requests.exceptions": Mock(),
    "urllib3.exceptions": Mock(),
    "cryptography.fernet": Mock(),
    "jwt.exceptions": Mock(),
    "googleapiclient.discovery": Mock(),
    "googleapiclient.errors": Mock(),
}

for module_name, mock_obj in submodules.items():
    sys.modules[module_name] = mock_obj

from test_framework import TestRunner

# Import working test suites
from .test_bot_functionality import register_bot_functionality_tests
from .test_gpt_service import register_gpt_service_tests

# TODO: Add these when they are created
# from .test_command_registry import register_command_registry_tests
# from .test_config import register_config_tests
# from .test_console_commands import register_console_command_tests
# from .test_crypto_service import register_crypto_service_tests
# from .test_eurojackpot_service import register_eurojackpot_service_tests
# from .test_irc_client import register_irc_client_tests
# from .test_new_features import register_new_features_tests
# from .test_weather_service import register_weather_service_tests
# from .test_commands import register_command_tests
# from .test_services import register_service_tests
# from .test_integration import register_integration_tests


def register_all_test_suites(runner: TestRunner, quick_mode: bool = False):
    """
    Register all test suites with the test runner.

    Args:
        runner: The test runner instance
        quick_mode: If True, only register fast tests
    """

    # Register working test suites
    try:
        register_bot_functionality_tests(runner)
        print("[INFO] Registered bot functionality tests")
    except Exception as e:
        print(f"[WARNING] Could not register bot functionality tests: {e}")

    try:
        register_gpt_service_tests(runner)
        print("[INFO] Registered GPT service tests")
    except Exception as e:
        print(f"[WARNING] Could not register GPT service tests: {e}")

    # TODO: Add these when they are created
    # Core component tests (always run)
    # register_config_tests(runner)
    # register_irc_client_tests(runner)
    # register_command_registry_tests(runner)
    # register_console_command_tests(runner)

    # Service tests (may be slower)
    # if not quick_mode:
    #     register_weather_service_tests(runner)
    #     register_crypto_service_tests(runner)
    #     register_eurojackpot_service_tests(runner)
    #     register_new_features_tests(runner)
    #     # TODO: Add other service tests when created

    # Integration tests (typically the slowest)
    # TODO: Add integration tests when created
