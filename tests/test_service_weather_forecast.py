import builtins
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest
import requests

# Ensure project root on path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import services.weather_forecast_service as wf

# ---------------- Tests for _fetch ---------------- #


def test_fetch_raises_when_api_key_missing(monkeypatch):
    monkeypatch.setattr(wf, "API_KEY", "")
    with pytest.raises(RuntimeError) as ei:
        wf._fetch("Joensuu")
    assert "API key missing" in str(ei.value)


def test_fetch_success_calls_requests_with_params(monkeypatch):
    monkeypatch.setattr(wf, "API_KEY", "TESTKEY")

    mock_r = Mock()
    mock_r.raise_for_status.return_value = None
    mock_r.json.return_value = {"ok": True}

    with patch(
        "services.weather_forecast_service.requests.get", return_value=mock_r
    ) as g:
        data = wf._fetch("Helsinki")

    assert data == {"ok": True}
    assert g.call_count == 1
    args, kwargs = g.call_args
    assert args[0] == wf.BASE_URL
    assert kwargs["params"]["place_id"] == "Helsinki"
    assert kwargs["params"]["sections"] == "current,hourly"
    assert kwargs["params"]["language"] == "en"
    assert kwargs["params"]["units"] == "metric"
    assert kwargs["params"]["key"] == "TESTKEY"
    assert kwargs["timeout"] == 10


def test_fetch_http_error_with_status(monkeypatch):
    monkeypatch.setattr(wf, "API_KEY", "K")

    mock_resp = Mock()
    mock_resp.status_code = 404

    http_err = requests.exceptions.HTTPError("Not Found", response=mock_resp)

    mock_r = Mock()
    mock_r.raise_for_status.side_effect = http_err

    with patch("services.weather_forecast_service.requests.get", return_value=mock_r):
        with pytest.raises(RuntimeError) as ei:
            wf._fetch("X")
    assert "HTTP 404" in str(ei.value)


def test_fetch_http_error_without_status(monkeypatch):
    monkeypatch.setattr(wf, "API_KEY", "K")

    http_err = requests.exceptions.HTTPError("error", response=None)
    mock_r = Mock()
    mock_r.raise_for_status.side_effect = http_err

    with patch("services.weather_forecast_service.requests.get", return_value=mock_r):
        with pytest.raises(RuntimeError) as ei:
            wf._fetch("X")
    assert str(ei.value) == "API request failed"


def test_fetch_http_error_status_property_raises(monkeypatch):
    monkeypatch.setattr(wf, "API_KEY", "K")

    class BadResponse:
        @property
        def status_code(self):  # accessing this should raise
            raise RuntimeError("no status")

    http_err = requests.exceptions.HTTPError("error", response=BadResponse())
    mock_r = Mock()
    mock_r.raise_for_status.side_effect = http_err

    with patch("services.weather_forecast_service.requests.get", return_value=mock_r):
        with pytest.raises(RuntimeError) as ei:
            wf._fetch("X")
    # Falls back to generic message when status could not be retrieved
    assert str(ei.value) == "API request failed"


def test_fetch_request_exception(monkeypatch):
    monkeypatch.setattr(wf, "API_KEY", "K")

    with patch(
        "services.weather_forecast_service.requests.get",
        side_effect=requests.exceptions.RequestException("net"),
    ):
        with pytest.raises(RuntimeError) as ei:
            wf._fetch("X")
    assert "Network error" in str(ei.value)


def test_fetch_invalid_json(monkeypatch):
    monkeypatch.setattr(wf, "API_KEY", "K")

    mock_r = Mock()
    mock_r.raise_for_status.return_value = None
    mock_r.json.side_effect = ValueError("bad json")

    with patch("services.weather_forecast_service.requests.get", return_value=mock_r):
        with pytest.raises(RuntimeError) as ei:
            wf._fetch("X")
    assert "Invalid JSON" in str(ei.value)


# ---------------- Tests for _sym ---------------- #
@pytest.mark.parametrize(
    "cond,icon,expected",
    [
        ("Thunder", None, "⛈️"),
        ("storm", None, "⛈️"),
        ("heavy snow", None, "❄️"),
        ("sleet", None, "❄️"),
        ("light_rain", None, "🌦️"),
        ("rain showers", None, "🌦️"),
        ("rain", None, "🌧️"),
        ("overcast", None, "☁️"),
        ("cloudy", None, "☁️"),
        ("clear sky", None, "☀️"),
        ("sunny", None, "☀️"),
        ("fog", None, "🌁"),
        ("mist", None, "🌁"),
        ("haze", None, "🌁"),
        ("unknown", None, "🌈"),
    ],
)
def test_sym_mapping(cond, icon, expected):
    assert wf._sym(cond, icon) == expected


# ---------------- Tests for _fmt_num ---------------- #
@pytest.mark.parametrize(
    "val,dec,expected",
    [
        (1, 1, " 1.0"),
        (10, 1, "10.0"),
        (-3, 1, " -3.0"),
        (2.345, 2, " 2.35"),
    ],
)
def test_fmt_num_basic(val, dec, expected):
    assert wf._fmt_num(val, dec) == expected


def test_fmt_num_invalid_and_none():
    assert wf._fmt_num("x") == "x"
    assert wf._fmt_num(None) == "?"


def test_fmt_num_secondary_try_exception(monkeypatch):
    # Force the secondary try-block to raise via custom float and formatted string with bad split
    class EvilStr(str):
        def split(self, *args, **kwargs):
            raise RuntimeError("boom")

    class Evil:
        def __format__(self, spec):
            # Return a str subclass so formatting result is acceptable to f-string
            return EvilStr("1.0")

    def fake_float(_):
        return Evil()

    monkeypatch.setattr(builtins, "float", fake_float, raising=True)
    # Should not raise; returns the base formatted string without added padding
    assert wf._fmt_num(123, 1) == "1.0"


# ---------------- Tests for _list_lines ---------------- #


def test_list_lines_filters_and_formats(monkeypatch):
    # Avoid zoneinfo dependency during test
    monkeypatch.setattr(wf, "ZoneInfo", None)
    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    future0 = (now + timedelta(hours=0)).isoformat()
    future1 = (now + timedelta(hours=1)).isoformat()
    past1 = (now - timedelta(hours=1)).isoformat()

    data = {
        "hourly": {
            "data": [
                {},  # missing date -> skip
                {"date": "not-a-date"},  # invalid date -> skip
                {
                    "date": past1,
                    "temperature": 5,
                    "precipitation": {"total": 0.0},
                    "wind": {"speed": 1.2},
                    "summary": "clear",
                },  # past -> skip
                {
                    "date": future0,
                    "temperature": 5,
                    "precipitation": {"total": 0},
                    "wind": {"speed": 1},
                    "summary": "rain showers",
                },
                {
                    "date": future1,
                    "temperature": 12.3,
                    "precipitation": {"total": 2.5},
                    "wind": {"speed": 4.7},
                    "weather": "overcast",
                },
            ]
        }
    }

    lines = wf._list_lines(data, limit=5)
    # Should include two future lines
    assert len(lines) >= 2
    # Check formatting elements in first included line
    first = lines[0]
    assert ": " in first
    assert "🌡️" in first and "🌧️" in first and "💨" in first


def test_list_lines_respects_limit_break(monkeypatch):
    # Avoid zoneinfo dependency during test
    monkeypatch.setattr(wf, "ZoneInfo", None)
    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    future0 = (now + timedelta(hours=0)).isoformat()
    future1 = (now + timedelta(hours=1)).isoformat()

    data = {
        "hourly": {
            "data": [
                {
                    "date": future0,
                    "temperature": 5,
                    "precipitation": {"total": 0},
                    "wind": {"speed": 1},
                    "summary": "rain",
                },
                {
                    "date": future1,
                    "temperature": 6,
                    "precipitation": {"total": 0},
                    "wind": {"speed": 2},
                    "summary": "clear",
                },
            ]
        }
    }

    lines = wf._list_lines(data, limit=1)
    assert len(lines) == 1


# ---------------- Tests for format_single_line and format_multi_line ---------------- #


def test_format_single_line_uses_defaults_and_limit(monkeypatch):
    # Patch _fetch and _list_lines to isolate logic
    with patch.object(wf, "_fetch", return_value={}) as f, patch.object(
        wf, "_list_lines", return_value=["11: x", "12: y", "13: z"]
    ):
        out = wf.format_single_line(city="  ", hours=-5)
    assert out.startswith(wf.DEFAULT_CITY + ": ")
    assert "11: x" in out

    # Hours cap at 48
    with patch.object(wf, "_fetch", return_value={}) as f, patch.object(
        wf, "_list_lines", return_value=["x"] * 60
    ):
        out = wf.format_single_line(city="Helsinki", hours=100)
    assert out.startswith("Helsinki: ")


def test_format_multi_line(monkeypatch):
    with patch.object(wf, "_fetch", return_value={}), patch.object(
        wf, "_list_lines", return_value=["A", "B"]
    ):
        out = wf.format_multi_line("Helsinki", hours=2)
    assert out[0] == "Helsinki"
    assert out[1:] == ["A", "B"]
