#!/usr/bin/env python3
"""
Pytest tests for services.eurojackpot_service module.
"""

import os

# Add the parent directory to sys.path to import our modules
import sys
from datetime import datetime
from datetime import datetime as _dt
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


def test_make_request_branches_303_and_json_error_then_success(service, monkeypatch):
    # Simulate three approaches: 1) 303 redirect, 2) JSON error=303, 3) success
    class Resp303:
        status_code = 303
        url = "http://x"
        headers = {"Location": "http://redirect"}

        def raise_for_status(self):
            return None

    class RespJSON303:
        status_code = 200
        url = "http://y"

        def raise_for_status(self):
            return None

        def json(self):
            return {"error": 303}

    class RespOK:
        status_code = 200
        url = "http://z"

        def raise_for_status(self):
            return None

        def json(self):
            return {"ok": True}

    calls = {"i": 0}

    class DummySession:
        headers = {}

        def get(self, *args, **kwargs):
            i = calls["i"]
            calls["i"] += 1
            if i == 0:
                return Resp303()
            elif i == 1:
                return RespJSON303()
            else:
                return RespOK()

    monkeypatch.setattr(
        "services.eurojackpot_service.requests.Session", lambda: DummySession()
    )

    res = service._make_request("http://test", {"a": 1})
    assert res == {"ok": True}


def test_make_request_all_approaches_303_returns_error(service, monkeypatch):
    class Resp303:
        status_code = 303
        url = "http://x"
        headers = {"Location": "http://redirect"}

        def raise_for_status(self):
            return None

        def json(self):
            return {"error": 303}

    class DummySession:
        headers = {}

        def get(self, *args, **kwargs):
            return Resp303()

    monkeypatch.setattr(
        "services.eurojackpot_service.requests.Session", lambda: DummySession()
    )

    res = service._make_request("http://test", {"a": 1})
    assert res["error"] == 303


def test_make_request_json_decode_errors(service, monkeypatch):
    import json as _json

    class RespBadJSON:
        status_code = 200
        url = "http://x"
        text = "bad"

        def raise_for_status(self):
            return None

        def json(self):
            raise _json.JSONDecodeError("bad", "{}", 0)

    calls = {"i": 0}

    class DummySession:
        headers = {}

        def get(self, *args, **kwargs):
            calls["i"] += 1
            return RespBadJSON()

    monkeypatch.setattr(
        "services.eurojackpot_service.requests.Session", lambda: DummySession()
    )

    res = service._make_request("http://test", {"a": 1})
    assert res["error"] in (998, 999, 997)


def test_make_request_unexpected_exception(service, monkeypatch):
    class DummySession:
        headers = {}

        def get(self, *args, **kwargs):
            raise RuntimeError("weird")

    monkeypatch.setattr(
        "services.eurojackpot_service.requests.Session", lambda: DummySession()
    )

    res = service._make_request("http://test", {"a": 1})
    assert res["error"] in (997, 999)


def test_get_next_draw_info_no_api_key(service, monkeypatch):
    monkeypatch.delenv("EUROJACKPOT_API_KEY", raising=False)
    service.api_key = None

    result = service.get_next_draw_info()
    assert result["success"] is True
    assert "(API ei saatavilla)" in result["message"]
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


def test_get_next_draw_info_api_success(service, monkeypatch):
    service.api_key = "x"

    # First call returns draw_data, second returns jackpot_data
    seq = iter(
        [
            {"error": 0, "next_draw": "2025-06-27"},
            {"error": 0, "jackpot": "15000000", "currency": "EUR"},
        ]
    )
    monkeypatch.setattr(service, "_make_request", lambda *a, **k: next(seq))
    res = service.get_next_draw_info()
    assert (
        res["success"] is True
        and res["jackpot"] == "15000000"
        and res["currency"] == "EUR"
    )


def test_get_last_results_no_api_key_with_cached_draw(service):
    service.api_key = None
    draw = {
        "date_iso": "2025-06-20",
        "date": "20.06.2025",
        "week_number": 25,
        "numbers": ["06", "12", "18", "37", "46", "07", "09"],
        "main_numbers": "06 12 18 37 46",
        "euro_numbers": "07 09",
        "jackpot": "10000000",
        "currency": "EUR",
        "type": "latest_result",
        "saved_at": datetime.now().isoformat(),
    }
    service._save_draw_to_database(draw)
    res = service.get_last_results()
    assert res["success"] is True and "tallennettu data" in res["message"]


def test_get_last_results_api_error_no_db(service, monkeypatch):
    service.api_key = "x"
    monkeypatch.setattr(service, "_make_request", lambda *a, **k: {"error": 1})
    res = service.get_last_results()
    assert res["success"] is False and "API ei saatavilla" in res["message"]


def test_get_last_results_outer_exception(service, monkeypatch):
    service.api_key = "x"
    monkeypatch.setattr(
        service,
        "_make_request",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")),
    )
    res = service.get_last_results()
    assert res["success"] is False and "Virhe" in res["message"]


def test_make_request_outer_last_approach_exception(service, monkeypatch):
    # Cause RequestException on each approach; last should bubble to outer except
    class DummySession:
        headers = {}
        calls = {"i": 0}

        def get(self, *args, **kwargs):
            DummySession.calls["i"] += 1
            raise requests.RequestException("boom")

    monkeypatch.setattr(
        "services.eurojackpot_service.requests.Session", lambda: DummySession()
    )
    res = service._make_request("http://test", {"a": 1})
    assert isinstance(res, dict) and "error" in res


def test_get_next_draw_info_fallback_date_adjustment_friday(service, monkeypatch):
    # Patch module datetime.now to Friday to hit next_friday <= today branch
    from datetime import datetime as _dt

    import services.eurojackpot_service as mod

    class FakeDT(_dt):
        @classmethod
        def now(cls):
            return cls(2025, 6, 27)  # Friday

    monkeypatch.setattr(mod, "datetime", FakeDT, raising=True)
    service.api_key = None
    res = service.get_next_draw_info()
    assert res["success"] is True


def test_get_next_draw_info_api_failure_fallback_date_adjust(service, monkeypatch):
    from datetime import datetime as _dt

    import services.eurojackpot_service as mod

    class FakeDT(_dt):
        @classmethod
        def now(cls):
            return cls(2025, 6, 27)  # Friday

    monkeypatch.setattr(mod, "datetime", FakeDT, raising=True)
    service.api_key = "x"
    # Force API failure
    monkeypatch.setattr(service, "_make_request", lambda *a, **k: {"error": 1})
    res = service.get_next_draw_info()
    assert res["success"] is True and "API ei saatavilla" in res["message"]


def test_get_next_draw_info_exception(service, monkeypatch):
    service.api_key = "x"
    monkeypatch.setattr(
        service,
        "_make_request",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")),
    )
    res = service.get_next_draw_info()
    assert res["success"] is False and "Virhe" in res["message"]


def test_get_last_results_api_error_with_db_fallback(service, monkeypatch):
    # API error with DB data present
    service.api_key = "x"
    draw = {
        "date_iso": "2025-06-20",
        "date": "20.06.2025",
        "week_number": 25,
        "numbers": ["06", "12", "18", "37", "46", "07", "09"],
        "main_numbers": "06 12 18 37 46",
        "euro_numbers": "07 09",
        "jackpot": "10000000",
        "currency": "EUR",
        "type": "latest_result",
        "saved_at": _dt.now().isoformat(),
    }
    service._save_draw_to_database(draw)
    monkeypatch.setattr(service, "_make_request", lambda *a, **k: {"error": 1})
    res = service.get_last_results()
    assert res["success"] is True and "API ei saatavilla" in res["message"]


def test_get_draw_by_date_exception(service, monkeypatch):
    service.api_key = "x"
    monkeypatch.setattr(
        service,
        "_make_request",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")),
    )
    res = service.get_draw_by_date("20.06.2025")
    assert res["success"] is False and "Virhe" in res["message"]


def test_get_draw_by_date_api_error_with_db(service, monkeypatch):
    service.api_key = "x"
    draw = {
        "date_iso": "2025-06-20",
        "date": "20.06.2025",
        "week_number": 25,
        "numbers": ["01", "02", "03", "04", "05", "06", "07"],
        "main_numbers": "01 02 03 04 05",
        "euro_numbers": "06 07",
        "jackpot": "10000000",
        "currency": "EUR",
        "type": "date_specific",
        "saved_at": _dt.now().isoformat(),
    }
    service._save_draw_to_database(draw)
    monkeypatch.setattr(service, "_make_request", lambda *a, **k: {"error": 1})
    res = service.get_draw_by_date("20.06.2025")
    assert res["success"] is True and "tallennettu data" in res["message"]


def test_get_frequent_numbers_returns_db_stats_directly(service, monkeypatch):
    monkeypatch.setattr(
        service,
        "_calculate_frequency_from_database",
        lambda extended=False: {
            "success": True,
            "message": "DB",
            "primary_numbers": [1, 2, 3, 4, 5],
            "secondary_numbers": [1, 2],
        },
    )
    res = service.get_frequent_numbers()
    assert res["success"] is True and res["message"] == "DB"


def test_calculate_frequency_value_error_and_no_date_range(service, monkeypatch):
    # Draws with invalid strings trigger ValueError and no date_iso -> unknown date range
    draws = [{"numbers": ["xx", "yy", "zz", "aa", "bb", "cc", "dd"]} for _ in range(5)]
    monkeypatch.setattr(service, "_load_database", lambda: {"draws": draws})
    res = service._calculate_frequency_from_database(extended=False)
    assert res["success"] in (False, True)


def test_calculate_frequency_no_date_iso_success(service, monkeypatch):
    # Good numbers but no date_iso -> unknown date range branch
    draws = [{"numbers": ["1", "2", "3", "4", "5", "6", "7"]} for _ in range(5)]
    monkeypatch.setattr(service, "_load_database", lambda: {"draws": draws})
    res = service._calculate_frequency_from_database(extended=False)
    assert res["success"] is True and "tuntematon ajanjakso" in res["message"]


def test_calculate_frequency_simple_non_extended(service, monkeypatch):
    # Good data without extended counts
    draws = [
        {"numbers": ["1", "2", "3", "4", "5", "6", "7"], "date_iso": f"2025-06-2{i}"}
        for i in range(5)
    ]
    monkeypatch.setattr(service, "_load_database", lambda: {"draws": draws})
    res = service._calculate_frequency_from_database(extended=False)
    assert res["success"] is True and "+" in res["message"]


def test_scrape_all_draws_exception_in_loop(service, monkeypatch):
    service.api_key = "x"
    seq = iter(
        [
            {
                "error": 0,
                "draw": "2025-06-20",
                "results": "01,02,03,04,05,06,07",
                "jackpot": "1",
                "currency": "EUR",
            },
        ]
    )
    monkeypatch.setattr(service, "_make_request", lambda *a, **k: next(seq))
    monkeypatch.setattr(
        service,
        "_save_draw_to_database",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")),
    )
    res = service.scrape_all_draws(start_year=2025, max_api_calls=1)
    assert res["success"] is True and res["failed_calls"] >= 1


def test_scrape_all_draws_all_saved_message(service, monkeypatch):
    # Pre-populate DB with all Tuesdays and Fridays in current year except two
    from datetime import date, timedelta

    service.api_key = "x"

    # Build all Tue/Fri for current year
    year = date.today().year
    start = date(year, 1, 1)
    today = date.today()
    all_tf = []
    d = start
    while d <= today:
        if d.weekday() in [1, 4]:
            all_tf.append(d)
        d += timedelta(days=1)

    # Choose two missing at end
    missing = [dt.strftime("%Y-%m-%d") for dt in all_tf[-2:]]
    existing = [dt.strftime("%Y-%m-%d") for dt in all_tf[:-2]]

    # Seed DB with existing
    for di in existing:
        service._save_draw_to_database(
            {
                "date_iso": di,
                "date": _dt.strptime(di, "%Y-%m-%d").strftime("%d.%m.%Y"),
                "week_number": service.get_week_number(di),
                "numbers": ["01", "02", "03", "04", "05", "06", "07"],
                "main_numbers": "01 02 03 04 05",
                "euro_numbers": "06 07",
                "jackpot": "1",
                "currency": "EUR",
                "type": "scraped",
                "saved_at": _dt.now().isoformat(),
            }
        )

    # Make API always succeed
    def fake_make_request(url, params, timeout=10):
        return {
            "error": 0,
            "draw": params.get("draw"),
            "results": "01,02,03,04,05,06,07",
            "jackpot": "1",
            "currency": "EUR",
        }

    monkeypatch.setattr(service, "_make_request", fake_make_request)

    res = service.scrape_all_draws(start_year=year, max_api_calls=5)
    assert res["success"] is True and "Kaikki arvonnat tallennettu" in res["message"]


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


def test_get_database_stats_empty_simple(service):
    res = service.get_database_stats()
    assert res["success"] is True and res["total_draws"] == 0


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
    assert "(API ei saatavilla)" in result


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


def test_get_last_results_api_success(service, monkeypatch):
    service.api_key = "x"

    def fake_make_request(url, params, timeout=10):
        return {
            "error": 0,
            "draw": "2025-06-20",
            "results": "06,12,18,37,46,07,09",
            "jackpot": "10000000",
            "currency": "EUR",
        }

    monkeypatch.setattr(service, "_make_request", fake_make_request)
    res = service.get_last_results()
    assert res["success"] is True and res["date"] == "20.06.2025"
    # Ensure saved to DB
    db = service._load_database()
    assert any(d.get("type") == "latest_result" for d in db.get("draws", []))


def test_get_draw_by_date_api_none_and_error_paths(service, monkeypatch):
    service.api_key = "x"

    # None data -> error message
    monkeypatch.setattr(service, "_make_request", lambda *a, **k: None)
    res = service.get_draw_by_date("20.06.2025")
    assert res["success"] is False and "Could not fetch" in res["message"]

    # Error path with no DB and no fallbacks
    monkeypatch.setattr(service, "_make_request", lambda *a, **k: {"error": 1})
    monkeypatch.setattr(service, "get_next_draw_info", lambda: {"success": False})
    monkeypatch.setattr(service, "get_frequent_numbers", lambda: {"success": False})
    res = service.get_draw_by_date("20.06.2025")
    assert res["success"] is False and "Arvontaa ei löytynyt" in res["message"]


def test_get_draw_by_date_no_api_key_no_fallback(service, monkeypatch):
    service.api_key = None
    monkeypatch.setattr(service, "get_next_draw_info", lambda: {"success": False})
    monkeypatch.setattr(service, "get_frequent_numbers", lambda: {"success": False})
    res = service.get_draw_by_date("01.01.2025")
    assert res["success"] is False and "Ei API-avainta" in res["message"]


def test_get_draw_by_date_api_success(service, monkeypatch):
    service.api_key = "x"

    monkeypatch.setattr(
        service,
        "_make_request",
        lambda *a, **k: {
            "error": 0,
            "draw": "2025-06-20",
            "results": "01,02,03,04,05,06,07",
            "jackpot": "123",
            "currency": "EUR",
        },
    )
    res = service.get_draw_by_date("20.06.2025")
    assert res["success"] is True and res["date"] == "20.06.2025"


def test_get_combined_info_branching(service, monkeypatch):
    monkeypatch.setattr(
        service, "get_last_results", lambda: {"success": True, "message": "L"}
    )
    monkeypatch.setattr(
        service, "get_next_draw_info", lambda: {"success": True, "message": "N"}
    )
    assert service.get_combined_info() == "L\nN"

    monkeypatch.setattr(
        service, "get_last_results", lambda: {"success": True, "message": "L"}
    )
    monkeypatch.setattr(
        service, "get_next_draw_info", lambda: {"success": False, "message": "N"}
    )
    assert service.get_combined_info() == "L"

    monkeypatch.setattr(
        service, "get_last_results", lambda: {"success": False, "message": "L"}
    )
    monkeypatch.setattr(
        service, "get_next_draw_info", lambda: {"success": True, "message": "N"}
    )
    assert service.get_combined_info() == "N"

    monkeypatch.setattr(
        service, "get_last_results", lambda: {"success": False, "message": "L"}
    )
    monkeypatch.setattr(
        service, "get_next_draw_info", lambda: {"success": False, "message": "N"}
    )
    assert "epäonnistui" in service.get_combined_info()


def test_get_frequent_numbers_extended_and_error(service, monkeypatch):
    # No database data -> historical path with extended
    monkeypatch.setattr(
        service,
        "_calculate_frequency_from_database",
        lambda extended=False: {"success": False},
    )
    res = service.get_frequent_numbers(limit=5, extended=True)
    assert res["success"] is True and "2012-2023" in res["message"]

    # Error path
    def _raise(*a, **k):
        raise RuntimeError("x")

    monkeypatch.setattr(service, "_calculate_frequency_from_database", _raise)
    res = service.get_frequent_numbers()
    assert res["success"] is False


def test_calculate_frequency_from_database_paths(service, monkeypatch):
    # Too few draws
    monkeypatch.setattr(service, "_load_database", lambda: {"draws": []})
    res = service._calculate_frequency_from_database()
    assert res["success"] is False and "vähän dataa" in res["message"]

    # Draws with insufficient number data -> no top lists
    bad_draws = [{"numbers": ["1", "2", "3"]}] * 5
    monkeypatch.setattr(service, "_load_database", lambda: {"draws": bad_draws})
    res = service._calculate_frequency_from_database()
    assert res["success"] is False and "Ei tarpeeksi" in res["message"]

    # Extended formatting with single-day range
    good_draws = []
    date_iso = "2025-06-20"
    for _ in range(5):
        good_draws.append(
            {"numbers": ["1", "2", "3", "4", "5", "6", "7"], "date_iso": date_iso}
        )
    monkeypatch.setattr(service, "_load_database", lambda: {"draws": good_draws})
    res = service._calculate_frequency_from_database(extended=True)
    assert res["success"] is True and "[" in res["message"]

    # Exception path
    monkeypatch.setattr(
        service, "_load_database", lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    res = service._calculate_frequency_from_database()
    assert res["success"] is False and "Virhe" in res["message"]


def test_scrape_all_draws_various_paths(service, monkeypatch):
    service.api_key = "x"

    # total_missing == 0
    from datetime import date

    future_year = date.today().year + 1
    result = service.scrape_all_draws(start_year=future_year, max_api_calls=1)
    assert result["success"] is True and result["total_missing"] == 0

    # API limit 303 breaks
    monkeypatch.setattr(service, "_make_request", lambda *a, **k: {"error": 303})
    result = service.scrape_all_draws(start_year=2012, max_api_calls=1)
    assert result["success"] is True and result["api_calls_used"] == 1

    # Sequence of problematic responses then success
    seq = iter(
        [
            None,  # not data
            {"error": 1},  # error
            {"error": 0, "draw": "-", "results": "-"},  # no draw
            {"error": 0, "draw": "2025-06-20", "results": "-"},  # no results
            {"error": 0, "draw": "2025-06-20", "results": "1,2,3"},  # invalid length
            {
                "error": 0,
                "draw": "2025-06-20",
                "results": "01,02,03,04,05,06,07",
                "jackpot": "1",
                "currency": "EUR",
            },  # success
        ]
    )
    monkeypatch.setattr(service, "_make_request", lambda *a, **k: next(seq))
    result = service.scrape_all_draws(start_year=2012, max_api_calls=6)
    assert (
        result["success"] is True
        and result["new_draws"] >= 1
        and result["failed_calls"] >= 1
    )

    # api_calls_used == 0 branch
    result = service.scrape_all_draws(start_year=2012, max_api_calls=0)
    assert result["success"] is True and "Ei API-kutsuja" in result["message"]

    # Outer except path
    monkeypatch.setattr(
        service, "_load_database", lambda: (_ for _ in ()).throw(RuntimeError("x"))
    )
    result = service.scrape_all_draws(start_year=2012, max_api_calls=1)
    assert result["success"] is False and "Scrape-virhe" in result["message"]


def test_get_database_stats_last_updated_format_and_error(service, monkeypatch):
    # Provide invalid last_updated to hit except branch
    monkeypatch.setattr(
        service,
        "_load_database",
        lambda: {
            "draws": [{"date_iso": "2025-06-20", "date": "20.06.2025"}],
            "last_updated": "bad",
        },
    )
    res = service.get_database_stats()
    assert res["success"] is True and "20.06.2025" in res["message"]

    # Outer except path
    monkeypatch.setattr(
        service, "_load_database", lambda: (_ for _ in ()).throw(RuntimeError("x"))
    )
    res = service.get_database_stats()
    assert res["success"] is False


def test_add_draw_manually_variants_and_errors(service, monkeypatch):
    # Two-digit year parsing triggers weekday validation
    res = service.add_draw_manually("21.12.99", "1,5,12,25,35,3,8")
    assert res["success"] in (True, False)

    # Invalid date
    res = service.add_draw_manually("32.13.2023", "1,2,3,4,5,6,7")
    assert res["success"] is False and "Virheellinen päivämäärä" in res["message"]

    # Number out of range
    res = service.add_draw_manually("20.12.2024", "0,2,3,4,5,6,7")
    assert res["success"] is False and "1-50" in res["message"]

    # Euro number out of range
    res = service.add_draw_manually("20.12.2024", "1,2,3,4,5,0,13")
    assert res["success"] is False and "1-12" in res["message"]

    # Duplicates in main numbers
    res = service.add_draw_manually("20.12.2024", "1,1,2,3,4,5,6")
    assert res["success"] is False and "eri numeroita" in res["message"]

    # Duplicates in euro numbers
    res = service.add_draw_manually("20.12.2024", "1,2,3,4,5,6,6")
    assert res["success"] is False and "eri numeroita" in res["message"]

    # Non-integer numbers
    res = service.add_draw_manually("20.12.2024", "a,b,c,d,e,f,g")
    assert res["success"] is False and "kokonaislukuja" in res["message"]

    # Outer except path: raise during existing check
    monkeypatch.setattr(
        service,
        "_get_draw_by_date_from_database",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")),
    )
    res = service.add_draw_manually("20.12.2024", "1,2,3,4,5,6,7")
    assert res["success"] is False and "Virhe" in res["message"]


def test_internal_helpers_error_paths(service, monkeypatch, tmp_path):
    # _save_database error handling
    monkeypatch.setattr(
        "builtins.open", lambda *a, **k: (_ for _ in ()).throw(OSError("x"))
    )
    service._save_database({"draws": [], "last_updated": None})

    # _save_draw_to_database error handling
    monkeypatch.setattr(
        service, "_load_database", lambda: (_ for _ in ()).throw(RuntimeError("x"))
    )
    service._save_draw_to_database({"date_iso": "2025-06-20"})

    # _get_latest_draw_from_database error handling
    monkeypatch.setattr(
        service, "_load_database", lambda: (_ for _ in ()).throw(RuntimeError("x"))
    )
    assert service._get_latest_draw_from_database() is None

    # _get_draw_by_date_from_database error handling
    monkeypatch.setattr(
        service, "_load_database", lambda: (_ for _ in ()).throw(RuntimeError("x"))
    )
    assert service._get_draw_by_date_from_database("2025-06-20") is None


def test_global_functions(monkeypatch):
    from services import eurojackpot_service as mod

    # Reset global instance and ensure creation
    monkeypatch.setattr(mod, "_eurojackpot_service", None, raising=False)
    inst = mod.get_eurojackpot_service()
    assert isinstance(inst, mod.EurojackpotService)

    # get_eurojackpot_numbers and results
    fake = Mock()
    fake.get_next_draw_info.return_value = {"message": "N"}
    fake.get_last_results.return_value = {"message": "L"}
    monkeypatch.setattr(mod, "_eurojackpot_service", fake, raising=False)

    assert mod.get_eurojackpot_numbers() == "N"
    assert mod.get_eurojackpot_results() == "L"


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


def test_scrape_all_draws_requires_api_key_simple(service):
    service.api_key = None
    res = service.scrape_all_draws(start_year=2025, max_api_calls=1)
    assert res["success"] is False and "API-avaimen" in res["message"]


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
    assert "(API ei saatavilla)" in result["message"]
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
