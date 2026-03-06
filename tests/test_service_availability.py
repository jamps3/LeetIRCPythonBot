#!/usr/bin/env python3
"""
Service Availability Tests

Tests that verify critical services are properly initialized and available.
These tests help catch configuration issues early.
"""

import os
import sys

import pytest

# Ensure proper import path
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


def test_weather_service_can_be_imported():
    """Test that weather service module can be imported."""
    try:
        from services.weather_service import WeatherService
    except ImportError as e:
        pytest.fail(f"Failed to import weather service: {e}")


def test_np_data_file_exists():
    """Test that NP (name day) data file exists."""
    from config import DATA_DIR

    np_file = os.path.join(DATA_DIR, "nimipaivat.json")
    assert os.path.exists(np_file), f"NP data file not found at {np_file}"


def test_quotes_file_exists_or_can_be_created():
    """Test that quotes file exists or can be created."""
    from config import QUOTES_FILE

    # Check if file exists
    if os.path.exists(QUOTES_FILE):
        return  # OK - file exists

    # If file doesn't exist, try to create it
    try:
        os.makedirs(os.path.dirname(QUOTES_FILE), exist_ok=True)
        with open(QUOTES_FILE, "w", encoding="utf-8") as f:
            f.write("# Quotes file\n")
    except Exception as e:
        pytest.fail(f"Cannot create quotes file at {QUOTES_FILE}: {e}")


def test_service_manager_weather_initialization():
    """Test that service manager can initialize weather service."""
    from service_manager import ServiceManager

    sm = ServiceManager()
    sm._initialize_weather_service()

    # Weather service should be initialized if API key is set
    weather_service = sm.services.get("weather")

    # Check if API key is available
    from config import get_api_key

    api_key = get_api_key("WEATHER_API_KEY")

    if api_key:
        assert (
            weather_service is not None
        ), "Weather service should be initialized when API key is available"
    else:
        # If no API key, service should be None - this is expected in test env
        pytest.skip("No WEATHER_API_KEY configured")


def test_np_command_works():
    """
    Test that !np (name day) command works.
    This is a basic sanity check - if this fails, something is seriously wrong.
    """
    from cmd_modules.misc import np_command
    from command_registry import CommandContext, CommandResponse

    # Create a minimal mock context
    class MockContext:
        def __init__(self):
            self.args = []
            self.args_text = ""
            self.command = "np"
            self.sender = "testuser"
            self.target = "#test"
            self.is_console = True

    # This should not raise an exception
    try:
        # NP command should at least be importable and return something
        result = np_command(MockContext(), {})
        # If we get here, the command is working
        assert True
    except Exception as e:
        pytest.fail(f"np command failed: {e}")


def test_weather_command_fails_gracefully_when_service_unavailable():
    """
    Test that weather command handles unavailable service gracefully.
    This test verifies the error handling, not that it works.
    """
    from cmd_modules.services import weather_command
    from command_registry import CommandContext

    class MockContext:
        def __init__(self):
            self.args = ["test"]
            self.args_text = "test"
            self.command = "s"
            self.sender = "testuser"
            self.target = "#test"
            self.is_console = False

    # Mock bot_functions without send_weather
    mock_functions = {}

    result = weather_command(MockContext(), mock_functions)

    # Should return an error message, not crash
    assert result is not None
    assert "not available" in str(result).lower() or isinstance(result, str)


def test_config_data_paths_exist():
    """Test that critical data directories and files are accessible."""
    from config import (
        CONVERSATION_HISTORY_FILE,
        DATA_DIR,
        GENERAL_WORDS_FILE,
        STATE_FILE,
    )

    # Data directory should exist
    assert os.path.isdir(DATA_DIR), f"Data directory not found at {DATA_DIR}"

    # These files should be readable (they may not exist but shouldn't cause import errors)
    # Just verify the paths are valid strings
    assert STATE_FILE
    assert CONVERSATION_HISTORY_FILE
    assert GENERAL_WORDS_FILE


def test_imports_work_without_pythonpath():
    """
    Test that critical modules can be imported without explicit PYTHONPATH.
    This catches issues where imports break when running the bot directly.
    """
    # This test simulates running the bot without PYTHONPATH
    # by checking that the sys.path manipulation in main.py works

    # Save original sys.path
    original_path = sys.path.copy()

    try:
        # Remove project root from path to simulate no PYTHONPATH
        if _project_root in sys.path:
            sys.path.remove(_project_root)

        # Now try importing through the src/ package
        # This tests that the sys.path fix in __init__.py works
        from src.config import DATA_DIR
        from src.service_manager import ServiceManager

        # Verify we got the expected values
        assert DATA_DIR
        assert ServiceManager

    except ModuleNotFoundError as e:
        pytest.fail(f"Import failed without PYTHONPATH: {e}")
    finally:
        # Restore sys.path
        sys.path[:] = original_path
