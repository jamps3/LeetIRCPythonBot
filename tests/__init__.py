"""
Test Suite Registration Module

This module registers all test suites for the LeetIRC Bot testing framework.
"""

from test_framework import TestRunner

from .test_command_registry import register_command_registry_tests
from .test_config import register_config_tests
from .test_crypto_service import register_crypto_service_tests
from .test_irc_client import register_irc_client_tests
from .test_weather_service import register_weather_service_tests

# TODO: Add these when they are created
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

    # Core component tests (always run)
    register_config_tests(runner)
    register_irc_client_tests(runner)
    register_command_registry_tests(runner)

    # Service tests (may be slower)
    if not quick_mode:
        register_weather_service_tests(runner)
        register_crypto_service_tests(runner)
        # TODO: Add other service tests when created

    # Integration tests (typically the slowest)
    # TODO: Add integration tests when created
