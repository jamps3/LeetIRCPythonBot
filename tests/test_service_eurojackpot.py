"""
Pytest test suite for Eurojackpot Service.
"""

import json
import os

# Add the parent directory to sys.path to import our modules
import sys
from datetime import datetime
from unittest.mock import MagicMock, Mock

import pytest
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# External modules that the service may import but are optional in tests
modules_to_mock = [
    "feedparser",
    "bs4",
    "selenium",
    "googleapiclient",
    "isodate",
    "selenium.webdriver",
    "selenium.webdriver.chrome",
    "selenium.webdriver.chrome.options",
    "selenium.webdriver.common",
    "selenium.webdriver.common.by",
    "selenium.webdriver.support",
    "selenium.webdriver.support.ui",
    "selenium.webdriver.support.expected_conditions",
    "googleapiclient.discovery",
    "googleapiclient.errors",
    "selenium.webdriver.chrome.service",
]


@pytest.fixture(autouse=True)
def mock_optional_external_modules(monkeypatch):
    """Mock optional heavy external modules so imports in the service won't fail."""
    for module in modules_to_mock:
        monkeypatch.setitem(sys.modules, module, MagicMock())


@pytest.fixture
def service(tmp_path):
    """Provide a EurojackpotService instance with an isolated temp DB and quiet logger."""
    from services.eurojackpot_service import EurojackpotService

    s = EurojackpotService()
    s.db_file = str(tmp_path / "eurojackpot_test_db.json")
    if hasattr(s, "logger"):
        s.logger = MagicMock()
    return s


def _get_mock_responses():
    """Get mock API responses for testing."""
    mock_next_draw_response = {"error": 0, "next_draw": "2025-06-27"}

    mock_jackpot_response = {
        "error": 0,
        "jackpot": "15000000",
        "currency": "EUR",
    }

    mock_last_results_response = {
        "error": 0,
        "draw": "2025-06-20",
        "results": "06,12,18,37,46,07,09",
        "jackpot": "10000000",
        "currency": "EUR",
    }

    mock_draw_by_date_response = {
        "error": 0,
        "draw": "2025-06-13",
        "results": "01,15,23,34,45,02,11",
        "jackpot": "8000000",
        "currency": "EUR",
    }

    mock_no_draw_response = {"error": 1, "message": "No draw found"}


def test_get_week_number(service):
    week_num = service.get_week_number("2025-06-20")
    assert isinstance(week_num, int)
    assert 1 <= week_num <= 53


def test_make_request_success(service, monkeypatch):
    mock_response = Mock()
    mock_response.json.return_value = {"success": True}
    mock_response.raise_for_status.return_value = None
    mock_response.status_code = 200

    class DummySession:
        headers = {}

        def get(self, url, params=None, timeout=None, headers=None):
            return mock_response

    monkeypatch.setattr(
        "services.eurojackpot_service.requests.Session", lambda: DummySession()
    )

    result = service._make_request("http://test.com", {"param": "value"})
    assert result == {"success": True}


def test_make_request_failure(service, monkeypatch):
    class FailingSession:
        def get(self, *args, **kwargs):
            raise requests.RequestException("boom")

    monkeypatch.setattr(
        "services.eurojackpot_service.requests.Session", lambda: FailingSession()
    )

    result = service._make_request("http://test.com", {"param": "value"})
    assert isinstance(result, dict)
    assert "error" in result


def test_get_next_draw_info_no_api_key(service, monkeypatch):
    monkeypatch.delenv("EUROJACKPOT_API_KEY", raising=False)
    service.api_key = None

    result = service.get_next_draw_info()
    assert result["success"] is True
    assert "demo-data" in result["message"]
    assert result.get("is_demo", False) is True


def test_get_next_draw_info_success(service, monkeypatch):
    service.api_key = "test_key"

    mock_next_draw_response = {"error": 0, "next_draw": "2025-06-27"}
    mock_jackpot_response = {"error": 0, "jackpot": "15000000", "currency": "EUR"}

    responses = [
        Mock(json=lambda: mock_next_draw_response, raise_for_status=lambda: None),
        Mock(json=lambda: mock_jackpot_response, raise_for_status=lambda: None),
    ]

    def fake_get(*args, **kwargs):
        return responses.pop(0)

    monkeypatch.setattr("services.eurojackpot_service.requests.get", fake_get)

    result = service.get_next_draw_info()
    assert result["success"] is True
    assert "Seuraava Eurojackpot-arvonta" in result["message"]
    assert result["jackpot"] == "15000000"
    assert result["currency"] == "EUR"


def test_get_last_results_fallback(service):
    service.api_key = None
    result = service.get_last_results()
    assert result["success"] is False
    assert "Ei API-avainta" in result["message"]


def test_get_draw_by_date_success(service):
    draw = {
        "date_iso": "2025-06-13",
        "date": "13.06.2025",
        "week_number": 24,
        "numbers": ["01", "15", "23", "34", "45", "02", "11"],
        "main_numbers": "01 15 23 34 45",
        "euro_numbers": "02 11",
        "jackpot": "8000000",
        "currency": "EUR",
        "type": "test",
        "saved_at": datetime.now().isoformat(),
    }
    service._save_draw_to_database(draw)

    service.api_key = None
    result = service.get_draw_by_date("13.06.25")
    assert result["success"] is True
    assert "13.06.2025" in result["message"]


def test_get_draw_by_date_invalid_format(service):
    service.api_key = "test_key"
    result = service.get_draw_by_date("invalid-date")
    assert result["success"] is False
    assert "Virheellinen päivämäärä" in result["message"]


def test_get_draw_by_date_not_found_fallback(service, monkeypatch):
    service.api_key = "test_key"

    mock_no_draw_response = {"error": 1, "message": "No draw found"}
    mock_next_draw_response = {"error": 0, "next_draw": "2025-06-27"}
    mock_jackpot_response = {"error": 0, "jackpot": "15000000", "currency": "EUR"}

    responses = [
        Mock(json=lambda: mock_no_draw_response, raise_for_status=lambda: None),
        Mock(json=lambda: mock_next_draw_response, raise_for_status=lambda: None),
        Mock(json=lambda: mock_jackpot_response, raise_for_status=lambda: None),
    ]

    def fake_get(*args, **kwargs):
        return responses.pop(0)

    monkeypatch.setattr("services.eurojackpot_service.requests.get", fake_get)

    result = service.get_draw_by_date("21.06.25")
    assert result["success"] is True
    assert "Arvontaa ei löytynyt" in result["message"]
    assert "Seuraava Eurojackpot-arvonta" in result["message"]
    assert "Yleisimmät numerot" in result["message"]


def test_get_frequent_numbers(service):
    result = service.get_frequent_numbers()
    assert result["success"] is True
    assert "📊 Yleisimmät numerot" in result["message"]
    assert len(result["primary_numbers"]) == 5
    assert len(result["secondary_numbers"]) == 2

    for num in result["primary_numbers"]:
        assert 1 <= num <= 50
    for num in result["secondary_numbers"]:
        assert 1 <= num <= 12


# (Removed placeholder date format test; covered by integration-style tests below)


def test_get_combined_info(service):
    service.api_key = None
    result = service.get_combined_info()
    assert "Seuraava Eurojackpot-arvonta" in result
    assert "demo-data" in result


def test_eurojackpot_command_no_arg(monkeypatch):
    from services.eurojackpot_service import eurojackpot_command

    mock_service = Mock()
    mock_service.get_combined_info.return_value = "Combined info"

    monkeypatch.setattr(
        "services.eurojackpot_service._eurojackpot_service", mock_service, raising=False
    )

    result = eurojackpot_command()
    assert result == "Combined info"


def test_eurojackpot_command_with_date(monkeypatch):
    from services.eurojackpot_service import eurojackpot_command

    mock_service = Mock()
    mock_service.get_draw_by_date.return_value = {"message": "Draw result"}

    monkeypatch.setattr(
        "services.eurojackpot_service._eurojackpot_service", mock_service, raising=False
    )

    result = eurojackpot_command("20.06.25")
    assert result == "Draw result"


# Enhanced database/scrape style tests now use the 'service' fixture


def test_database_initialization(service):
    db = service._load_database()
    assert isinstance(db, dict)
    assert "draws" in db
    assert "last_updated" in db
    assert len(db["draws"]) == 0
    assert db["last_updated"] is None


def test_save_and_load_draw_to_database(service):
    test_draw = {
        "date_iso": "2023-12-15",
        "date": "15.12.2023",
        "week_number": 50,
        "numbers": ["01", "12", "23", "34", "45", "06", "07"],
        "main_numbers": "01 12 23 34 45",
        "euro_numbers": "06 07",
        "jackpot": "15000000",
        "currency": "EUR",
        "type": "test",
        "saved_at": datetime.now().isoformat(),
    }

    service._save_draw_to_database(test_draw)

    loaded_draw = service._get_draw_by_date_from_database("2023-12-15")
    assert loaded_draw is not None
    assert loaded_draw["date"] == "15.12.2023"
    assert loaded_draw["main_numbers"] == "01 12 23 34 45"
    assert loaded_draw["euro_numbers"] == "06 07"


def test_get_latest_draw_from_database(service):
    draws = [
        {
            "date_iso": "2023-12-08",
            "date": "08.12.2023",
            "week_number": 49,
            "numbers": ["01", "02", "03", "04", "05", "01", "02"],
            "main_numbers": "01 02 03 04 05",
            "euro_numbers": "01 02",
            "jackpot": "10000000",
            "currency": "EUR",
            "type": "test",
            "saved_at": datetime.now().isoformat(),
        },
        {
            "date_iso": "2023-12-15",
            "date": "15.12.2023",
            "week_number": 50,
            "numbers": ["06", "07", "08", "09", "10", "03", "04"],
            "main_numbers": "06 07 08 09 10",
            "euro_numbers": "03 04",
            "jackpot": "20000000",
            "currency": "EUR",
            "type": "test",
            "saved_at": datetime.now().isoformat(),
        },
    ]

    for draw in draws:
        service._save_draw_to_database(draw)

    latest = service._get_latest_draw_from_database()
    assert latest is not None
    assert latest["date"] == "15.12.2023"


def test_scrape_all_draws_success(service, monkeypatch):
    service.api_key = "test_api_key"

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "error": 0,
        "draw": "2023-12-15",
        "results": "01,12,23,34,45,06,07",
        "jackpot": "15000000",
        "currency": "EUR",
    }

    monkeypatch.setattr(
        "services.eurojackpot_service.requests.get",
        lambda *args, **kwargs: mock_response,
    )

    result = service.scrape_all_draws(start_year=2023, max_api_calls=3)
    assert result["success"] is True
    assert result["new_draws"] >= 0
    assert "total_draws" in result
    assert "Scrape valmis!" in result["message"]


def test_scrape_all_draws_no_api_key(service):
    service.api_key = None
    result = service.scrape_all_draws()
    assert result["success"] is False
    assert "API-avaimen" in result["message"]


def test_scrape_all_draws_api_error(service, monkeypatch):
    service.api_key = "test_api_key"

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"error": 1, "message": "API error"}

    monkeypatch.setattr(
        "services.eurojackpot_service.requests.get",
        lambda *args, **kwargs: mock_response,
    )

    result = service.scrape_all_draws(max_api_calls=1)
    assert result["success"] is True
    assert result["new_draws"] == 0
    assert result.get(
        ["failed_calls"][0]
        if isinstance(result.get("failed_calls"), list)
        else "failed_calls"
    )
    assert "Scrape valmis!" in result["message"]


def test_get_database_stats_empty(service):
    result = service.get_database_stats()
    assert result["success"] is True
    assert result["total_draws"] == 0
    assert "tyhjä" in result["message"]


def test_get_database_stats_with_data(service):
    test_draws = [
        {
            "date_iso": "2023-12-08",
            "date": "08.12.2023",
            "week_number": 49,
            "numbers": ["01", "02", "03", "04", "05", "01", "02"],
            "main_numbers": "01 02 03 04 05",
            "euro_numbers": "01 02",
            "jackpot": "10000000",
            "currency": "EUR",
            "type": "test",
            "saved_at": datetime.now().isoformat(),
        },
        {
            "date_iso": "2023-12-15",
            "date": "15.12.2023",
            "week_number": 50,
            "numbers": ["06", "07", "08", "09", "10", "03", "04"],
            "main_numbers": "06 07 08 09 10",
            "euro_numbers": "03 04",
            "jackpot": "20000000",
            "currency": "EUR",
            "type": "test",
            "saved_at": datetime.now().isoformat(),
        },
    ]

    for draw in test_draws:
        service._save_draw_to_database(draw)

    result = service.get_database_stats()
    assert result["success"] is True
    assert result["total_draws"] == 2
    assert "08.12.2023 - 15.12.2023" in result["message"]


def test_get_draw_by_date_database_fallback(service):
    test_draw = {
        "date_iso": "2023-12-15",
        "date": "15.12.2023",
        "week_number": 50,
        "numbers": ["01", "12", "23", "34", "45", "06", "07"],
        "main_numbers": "01 12 23 34 45",
        "euro_numbers": "06 07",
        "jackpot": "15000000",
        "currency": "EUR",
        "type": "test",
        "saved_at": datetime.now().isoformat(),
    }
    service._save_draw_to_database(test_draw)

    service.api_key = None
    result = service.get_draw_by_date("15.12.23")

    assert result["success"] is True
    assert result["date"] == "15.12.2023"
    assert "tallennettu data" in result["message"]


def test_date_format_variations(service):
    test_draw = {
        "date_iso": "2023-12-15",
        "date": "15.12.2023",
        "week_number": 50,
        "numbers": ["01", "12", "23", "34", "45", "06", "07"],
        "main_numbers": "01 12 23 34 45",
        "euro_numbers": "06 07",
        "jackpot": "15000000",
        "currency": "EUR",
        "type": "test",
        "saved_at": datetime.now().isoformat(),
    }
    service._save_draw_to_database(test_draw)

    service.api_key = None
    for fmt in ("15.12.23", "15.12.2023", "2023-12-15"):
        result = service.get_draw_by_date(fmt)
        assert result["success"] is True
        assert result["date"] == "15.12.2023"


# Integration-style tests continue using the same 'service' fixture


def test_scrape_command_integration(service, monkeypatch):
    service.api_key = "test_api_key"

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "error": 0,
        "draw": "2023-12-15",
        "results": "01,12,23,34,45,06,07",
        "jackpot": "15000000",
        "currency": "EUR",
    }
    monkeypatch.setattr(
        "services.eurojackpot_service.requests.get",
        lambda *args, **kwargs: mock_response,
    )

    result = service.scrape_all_draws(start_year=2023, max_api_calls=1)

    assert result["success"] is True
    assert result["new_draws"] >= 0
    assert ("Scrape valmis!" in result["message"]) or (
        "tallennettu" in result["message"]
    )


def test_stats_command_integration(service):
    test_draw = {
        "date_iso": "2023-12-15",
        "date": "15.12.2023",
        "week_number": 50,
        "numbers": ["01", "12", "23", "34", "45", "06", "07"],
        "main_numbers": "01 12 23 34 45",
        "euro_numbers": "06 07",
        "jackpot": "15000000",
        "currency": "EUR",
        "type": "test",
        "saved_at": datetime.now().isoformat(),
    }
    service._save_draw_to_database(test_draw)

    result = service.get_database_stats()
    assert result["success"] is True
    assert result["total_draws"] == 1
    assert "15.12.2023" in result["message"]


def test_date_specific_command_integration(service):
    test_draw = {
        "date_iso": "2023-12-15",
        "date": "15.12.2023",
        "week_number": 50,
        "numbers": ["01", "12", "23", "34", "45", "06", "07"],
        "main_numbers": "01 12 23 34 45",
        "euro_numbers": "06 07",
        "jackpot": "15000000",
        "currency": "EUR",
        "type": "test",
        "saved_at": datetime.now().isoformat(),
    }
    service._save_draw_to_database(test_draw)

    service.api_key = None
    result = service.get_draw_by_date("15.12.23")

    assert result["success"] is True
    assert result["date"] == "15.12.2023"
    assert "01 12 23 34 45" in result["message"]


def test_next_draw_fallback_integration(service):
    service.api_key = None
    result = service.get_draw_by_date("20.12.23")

    assert result["success"] is True
    assert "Arvontaa ei löytynyt" in result["message"]
    assert "Seuraava" in result["message"]


def test_corrupted_database_handling(service, tmp_path):
    # Write invalid JSON to the DB file path
    bad_path = tmp_path / "bad.json"
    bad_path.write_text("invalid json content", encoding="utf-8")
    service.db_file = str(bad_path)

    db = service._load_database()
    assert isinstance(db, dict)
    assert "draws" in db
    assert len(db["draws"]) == 0


def test_service_initialization_basic():
    from services.eurojackpot_service import EurojackpotService

    s = EurojackpotService()
    assert s is not None
    assert hasattr(s, "logger")


def test_command_function_exists_basic():
    from services.eurojackpot_service import eurojackpot_command

    assert callable(eurojackpot_command)


def test_demo_data_without_api_key_basic(monkeypatch):
    from services.eurojackpot_service import EurojackpotService

    monkeypatch.delenv("EUROJACKPOT_API_KEY", raising=False)
    s = EurojackpotService()
    result = s.get_next_draw_info()
    assert result["success"] is True
    assert "demo-data" in result["message"]
    assert result.get("is_demo", False) is True


def test_eurojackpot_service_creation_basic():
    from services.eurojackpot_service import EurojackpotService

    s = EurojackpotService()
    week_num = s.get_week_number("2023-12-15")
    assert isinstance(week_num, int)
    assert 1 <= week_num <= 53

    result = s.get_frequent_numbers()
    assert result["success"] is True
    assert len(result["primary_numbers"]) == 5
    assert len(result["secondary_numbers"]) == 2


def test_eurojackpot_manual_add(service):
    result = service.add_draw_manually("22.12.2023", "1,5,12,25,35,3,8", "15000000")
    assert result["success"] is True
    assert result["action"] in ("lisätty", "päivitetty")

    result = service.add_draw_manually("21.12.2023", "1,5,12,25,35,3,8", "15000000")
    assert result["success"] is False
    assert "tiistaisin ja perjantaisin" in result["message"]

    result = service.add_draw_manually("22.12.2023", "1,5,12", "15000000")
    assert result["success"] is False
    assert "7 numeroa" in result["message"]


def test_eurojackpot_database_operations(service):
    db = service._load_database()
    assert isinstance(db, dict)
    assert "draws" in db
    assert "last_updated" in db
    assert len(db["draws"]) == 0
    assert db["last_updated"] is None

    test_draw = {
        "date_iso": "2023-12-15",
        "date": "15.12.2023",
        "week_number": 50,
        "numbers": ["01", "12", "23", "34", "45", "06", "07"],
        "main_numbers": "01 12 23 34 45",
        "euro_numbers": "06 07",
        "jackpot": "15000000",
        "currency": "EUR",
        "type": "test",
        "saved_at": datetime.now().isoformat(),
    }

    service._save_draw_to_database(test_draw)

    loaded_draw = service._get_draw_by_date_from_database("2023-12-15")
    assert loaded_draw is not None
    assert loaded_draw["date"] == "15.12.2023"
    assert loaded_draw["main_numbers"] == "01 12 23 34 45"
    assert loaded_draw["euro_numbers"] == "06 07"


def test_eurojackpot_tuesday_friday_validation(service):
    result = service.add_draw_manually("19.12.2023", "1,5,12,25,35,3,8", "15000000")
    assert result["success"] is True

    result = service.add_draw_manually("22.12.2023", "2,6,13,26,36,4,9", "20000000")
    assert result["success"] is True

    result = service.add_draw_manually("20.12.2023", "3,7,14,27,37,5,10", "25000000")
    assert result["success"] is False
    assert "tiistaisin ja perjantaisin" in result["message"]
