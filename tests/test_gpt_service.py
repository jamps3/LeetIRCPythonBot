#!/usr/bin/env python3
"""
GPT Service Test Suite

Tests for GPT service functionality including date correction.
"""

import os
import re
import sys
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

# Add the parent directory to sys.path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_framework import TestCase, TestSuite

# Mock only the external dependencies needed for GPT service
sys.modules["openai"] = Mock()


def test_date_correction_tanaanaon_pattern():
    """Test date correction for 'Tänään on [date]' pattern."""
    try:
        # Import directly to avoid services package __init__.py
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))
        from gpt_service import GPTService

        service = GPTService("fake_api_key")

        # Test cases with 'Tänään on' pattern
        test_cases = [
            "Tänään on 22. lokakuuta 2023.",
            "Tänään on 15. maaliskuuta 2022.",
            "Hyvää huomenta! Tänään on 1. tammikuuta 2023 ja sää on kaunis.",
        ]

        current_date = datetime.now()
        finnish_months = [
            "tammikuuta",
            "helmikuuta",
            "maaliskuuta",
            "huhtikuuta",
            "toukokuuta",
            "kesäkuuta",
            "heinäkuuta",
            "elokuuta",
            "syyskuuta",
            "lokakuuta",
            "marraskuuta",
            "joulukuuta",
        ]
        expected_date = f"{current_date.day}. {finnish_months[current_date.month - 1]} {current_date.year}"

        for test_case in test_cases:
            corrected = service._correct_outdated_dates(test_case)

            # Should contain the corrected date
            if expected_date not in corrected:
                print(f"Failed: Expected '{expected_date}' in '{corrected}'")
                return False

            # Should still contain "Tänään on"
            if "Tänään on" not in corrected:
                print(f"Failed: 'Tänään on' missing from '{corrected}'")
                return False

            # Should have changed from original
            if corrected == test_case:
                print(f"Failed: No change applied to '{test_case}'")
                return False

        return True

    except Exception as e:
        print(f"Date correction 'Tänään on' test failed: {e}")
        return False


def test_date_correction_other_patterns():
    """Test date correction for other Finnish date patterns."""
    try:
        # Import directly to avoid services package __init__.py
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))
        from gpt_service import GPTService

        service = GPTService("fake_api_key")

        # Test cases with various patterns
        test_cases = [
            "Nykyinen päivämäärä on 1. tammikuuta 2023.",
            "Päivämäärä on 25. joulukuuta 2021.",
            "Olemme nyt 10. kesäkuuta 2023.",
        ]

        for test_case in test_cases:
            corrected = service._correct_outdated_dates(test_case)

            # Should have been corrected (changed from original)
            if corrected == test_case:
                print(f"Failed: No change applied to '{test_case}'")
                return False

            # Should contain current year
            current_year = str(datetime.now().year)
            if current_year not in corrected:
                print(f"Failed: Current year '{current_year}' not in '{corrected}'")
                return False

        return True

    except Exception as e:
        print(f"Date correction other patterns test failed: {e}")
        return False


def test_date_correction_no_change_cases():
    """Test that date correction doesn't change inappropriate cases."""
    try:
        # Import directly to avoid services package __init__.py
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))
        from gpt_service import GPTService

        service = GPTService("fake_api_key")

        # Test cases that should NOT be changed
        test_cases = [
            "Tämä on normaali lause ilman päivämäärää.",
            "Syntymäpäiväni on 15. kesäkuuta 1990.",
            "Muistan hyvin 11. syyskuuta 2001.",
            "Joulua vietetään 25. joulukuuta joka vuosi.",
            "Hyvää uutta vuotta!",
            "",
            "Pelkkä teksti ilman mitään päivämäärää.",
        ]

        for test_case in test_cases:
            corrected = service._correct_outdated_dates(test_case)

            # Should NOT have been changed
            if corrected != test_case:
                print(f"Failed: Unexpected change from '{test_case}' to '{corrected}'")
                return False

        return True

    except Exception as e:
        print(f"Date correction no-change test failed: {e}")
        return False


def test_date_correction_pattern_matching():
    """Test that date correction pattern matching works correctly."""
    try:
        # Import directly to avoid services package __init__.py
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))
        from gpt_service import GPTService

        service = GPTService("fake_api_key")

        # Test specific patterns
        current_date = datetime.now()
        finnish_months = [
            "tammikuuta",
            "helmikuuta",
            "maaliskuuta",
            "huhtikuuta",
            "toukokuuta",
            "kesäkuuta",
            "heinäkuuta",
            "elokuuta",
            "syyskuuta",
            "lokakuuta",
            "marraskuuta",
            "joulukuuta",
        ]
        expected_date = f"{current_date.day}. {finnish_months[current_date.month - 1]} {current_date.year}"

        # Test case-insensitive matching
        test_cases = [
            "tänään on 22. lokakuuta 2023.",  # lowercase
            "TÄNÄÄN ON 22. LOKAKUUTA 2023.",  # uppercase
            "Tänään On 22. Lokakuuta 2023.",  # mixed case
        ]

        for test_case in test_cases:
            corrected = service._correct_outdated_dates(test_case)

            # Should contain the corrected date
            if expected_date not in corrected:
                print(
                    f"Failed case-insensitive: Expected '{expected_date}' in '{corrected}'"
                )
                return False

            # Should have changed from original
            if corrected == test_case:
                print(f"Failed case-insensitive: No change applied to '{test_case}'")
                return False

        return True

    except Exception as e:
        print(f"Date correction pattern matching test failed: {e}")
        return False


def test_date_correction_edge_cases():
    """Test date correction edge cases."""
    try:
        # Import directly to avoid services package __init__.py
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))
        from gpt_service import GPTService

        service = GPTService("fake_api_key")

        # Edge cases
        test_cases = [
            # Multiple date references in one message
            "Tänään on 22. lokakuuta 2023. Eilen oli 21. lokakuuta 2023.",
            # Date with extra text
            "Tänään on 22. lokakuuta 2023 ja aurinko paistaa!",
            # Different formats that should be caught
            "Nykyinen päivämäärä on 5. toukokuuta 2020.",
        ]

        for test_case in test_cases:
            corrected = service._correct_outdated_dates(test_case)

            # Should contain current year
            current_year = str(datetime.now().year)
            if current_year not in corrected:
                print(
                    f"Failed edge case: Current year '{current_year}' not in '{corrected}'"
                )
                return False

            # Should have changed from original
            if corrected == test_case:
                print(f"Failed edge case: No change applied to '{test_case}'")
                return False

        return True

    except Exception as e:
        print(f"Date correction edge cases test failed: {e}")
        return False


def test_gpt_service_initialization():
    """Test GPT service initialization without API key."""
    try:
        # Import directly to avoid services package __init__.py
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))
        from gpt_service import GPTService

        service = GPTService("fake_api_key")

        # Check that essential attributes exist
        required_attrs = [
            "api_key",
            "history_file",
            "history_limit",
            "conversation_history",
            "default_history",
        ]

        for attr in required_attrs:
            if not hasattr(service, attr):
                print(f"Missing required attribute: {attr}")
                return False

        # Check that essential methods exist
        required_methods = [
            "_correct_outdated_dates",
            "_load_conversation_history",
            "_save_conversation_history",
            "reset_conversation",
            "get_conversation_stats",
            "set_system_prompt",
        ]

        for method in required_methods:
            if not hasattr(service, method):
                print(f"Missing required method: {method}")
                return False
            if not callable(getattr(service, method)):
                print(f"Attribute {method} is not callable")
                return False

        return True

    except Exception as e:
        print(f"GPT service initialization test failed: {e}")
        return False


def test_date_correction_month_names():
    """Test that date correction uses correct Finnish month names."""
    try:
        # Import directly to avoid services package __init__.py
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))
        from gpt_service import GPTService

        service = GPTService("fake_api_key")

        # Test correction with different months
        test_cases = [
            "Tänään on 1. tammikuuta 2023.",  # January
            "Tänään on 15. kesäkuuta 2023.",  # June
            "Tänään on 25. joulukuuta 2023.",  # December
        ]

        finnish_months = [
            "tammikuuta",
            "helmikuuta",
            "maaliskuuta",
            "huhtikuuta",
            "toukokuuta",
            "kesäkuuta",
            "heinäkuuta",
            "elokuuta",
            "syyskuuta",
            "lokakuuta",
            "marraskuuta",
            "joulukuuta",
        ]

        current_date = datetime.now()
        expected_month = finnish_months[current_date.month - 1]

        for test_case in test_cases:
            corrected = service._correct_outdated_dates(test_case)

            # Should contain the current month name
            if expected_month not in corrected:
                print(f"Failed: Expected month '{expected_month}' not in '{corrected}'")
                return False

            # Should have changed from original
            if corrected == test_case:
                print(f"Failed: No change applied to '{test_case}'")
                return False

        return True

    except Exception as e:
        print(f"Date correction month names test failed: {e}")
        return False


def register_gpt_service_tests(runner):
    """Register GPT service tests with the test framework."""
    tests = [
        TestCase(
            name="date_correction_tanaanaon_pattern",
            description="Test date correction for 'Tänään on [date]' pattern",
            test_func=test_date_correction_tanaanaon_pattern,
            category="gpt_service",
        ),
        TestCase(
            name="date_correction_other_patterns",
            description="Test date correction for other Finnish date patterns",
            test_func=test_date_correction_other_patterns,
            category="gpt_service",
        ),
        TestCase(
            name="date_correction_no_change_cases",
            description="Test that date correction doesn't change inappropriate cases",
            test_func=test_date_correction_no_change_cases,
            category="gpt_service",
        ),
        TestCase(
            name="date_correction_pattern_matching",
            description="Test that date correction pattern matching works correctly",
            test_func=test_date_correction_pattern_matching,
            category="gpt_service",
        ),
        TestCase(
            name="date_correction_edge_cases",
            description="Test date correction edge cases",
            test_func=test_date_correction_edge_cases,
            category="gpt_service",
        ),
        TestCase(
            name="gpt_service_initialization",
            description="Test GPT service initialization",
            test_func=test_gpt_service_initialization,
            category="gpt_service",
        ),
        TestCase(
            name="date_correction_month_names",
            description="Test that date correction uses correct Finnish month names",
            test_func=test_date_correction_month_names,
            category="gpt_service",
        ),
    ]

    suite = TestSuite(
        name="GPT_Service",
        description="Tests for GPT service functionality including date correction",
        tests=tests,
    )

    runner.add_suite(suite)


# For standalone testing
if __name__ == "__main__":
    from test_framework import TestRunner

    runner = TestRunner(verbose=True)
    register_gpt_service_tests(runner)
    success = runner.run_all()

    print(f"\nGPT service tests: {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1)
