#!/usr/bin/env python3
"""
GPT Service Test Suite - Pure Pytest Version

Tests for GPT service functionality including date correction.
"""

import os
import re
import sys
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

# Add the parent directory to sys.path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Mock only the external dependencies needed for GPT service
sys.modules["openai"] = Mock()


def test_date_correction_tanaanaon_pattern():
    """Test date correction for 'Tänään on [date]' pattern."""
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
        "tammikuuta", "helmikuuta", "maaliskuuta", "huhtikuuta",
        "toukokuuta", "kesäkuuta", "heinäkuuta", "elokuuta",
        "syyskuuta", "lokakuuta", "marraskuuta", "joulukuuta",
    ]
    expected_date = f"{current_date.day}. {finnish_months[current_date.month - 1]} {current_date.year}"

    for test_case in test_cases:
        corrected = service._correct_outdated_dates(test_case)

        # Should contain the corrected date
        assert expected_date in corrected, f"Expected '{expected_date}' in '{corrected}'"
        
        # Should still contain "Tänään on"
        assert "Tänään on" in corrected, f"'Tänään on' missing from '{corrected}'"
        
        # Should have changed from original
        assert corrected != test_case, f"No change applied to '{test_case}'"


def test_date_correction_other_patterns():
    """Test date correction for other Finnish date patterns."""
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
        assert corrected != test_case, f"No change applied to '{test_case}'"
        
        # Should contain current year
        current_year = str(datetime.now().year)
        assert current_year in corrected, f"Current year '{current_year}' not in '{corrected}'"


def test_date_correction_no_change_cases():
    """Test that date correction doesn't change inappropriate cases."""
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
        assert corrected == test_case, f"Unexpected change from '{test_case}' to '{corrected}'"


def test_date_correction_pattern_matching():
    """Test that date correction pattern matching works correctly."""
    # Import directly to avoid services package __init__.py
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))
    from gpt_service import GPTService

    service = GPTService("fake_api_key")

    # Test specific patterns
    current_date = datetime.now()
    finnish_months = [
        "tammikuuta", "helmikuuta", "maaliskuuta", "huhtikuuta",
        "toukokuuta", "kesäkuuta", "heinäkuuta", "elokuuta",
        "syyskuuta", "lokakuuta", "marraskuuta", "joulukuuta",
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
        assert expected_date in corrected, f"Expected '{expected_date}' in '{corrected}' for case-insensitive test"
        
        # Should have changed from original
        assert corrected != test_case, f"No change applied to '{test_case}' in case-insensitive test"


def test_date_correction_edge_cases():
    """Test edge cases for date correction."""
    # Import directly to avoid services package __init__.py
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))
    from gpt_service import GPTService

    service = GPTService("fake_api_key")

    # Edge cases
    test_cases = [
        # Should be corrected
        ("Tänään on 1. tammikuuta 2000.", True),
        ("päivämäärä on 15. maaliskuuta 1999.", True),
        # Should NOT be corrected (historical references)
        ("Syntymäni 15. maaliskuuta 1990.", False),
        ("Muistan 1. tammikuuta 2000.", False),
    ]

    for test_case, should_change in test_cases:
        corrected = service._correct_outdated_dates(test_case)

        if should_change:
            assert corrected != test_case, f"Should have changed: '{test_case}'"
        else:
            assert corrected == test_case, f"Should NOT have changed: '{test_case}'"


def test_gpt_service_initialization():
    """Test GPT service initialization."""
    # Import directly to avoid services package __init__.py
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))
    from gpt_service import GPTService

    api_key = "test_api_key"
    service = GPTService(api_key)

    assert service.api_key == api_key, "API key should be set correctly"
    assert hasattr(service, "_correct_outdated_dates"), "Service should have date correction method"
    assert hasattr(service, "conversation_history"), "Service should have conversation history"
    assert hasattr(service, "client"), "Service should have OpenAI client"


def test_date_correction_month_names():
    """Test date correction with all Finnish month names."""
    # Import directly to avoid services package __init__.py
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))
    from gpt_service import GPTService

    service = GPTService("fake_api_key")

    # Test all Finnish months
    finnish_months = [
        "tammikuuta", "helmikuuta", "maaliskuuta", "huhtikuuta",
        "toukokuuta", "kesäkuuta", "heinäkuuta", "elokuuta",
        "syyskuuta", "lokakuuta", "marraskuuta", "joulukuuta",
    ]

    current_date = datetime.now()
    current_year = current_date.year

    for month in finnish_months:
        test_text = f"Tänään on 15. {month} 2020."
        corrected = service._correct_outdated_dates(test_text)

        # Should be corrected to current year
        assert str(current_year) in corrected, f"Should correct year for month {month}: '{corrected}'"
        assert corrected != test_text, f"Should change for month {month}"
