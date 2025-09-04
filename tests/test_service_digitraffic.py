import datetime as dt
import os
import sys
from unittest.mock import Mock, patch

import pytest
import requests

# Ensure project root on path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import services.digitraffic_service as ds


@pytest.fixture(autouse=True)
def reset_station_index(monkeypatch):
    # Reset station index globals between tests
    ds._STATION_INDEX = {}
    ds._STATION_NAME_BY_CODE = {}
    ds._STATION_INDEX_LOADED = False
    # Provide a small default mapping to avoid metadata fetch unless needed
    ds.STATION_ALIASES.update({"test": "TST", "tst": "TST"})
    yield
    # cleanup
    ds._STATION_INDEX = {}
    ds._STATION_NAME_BY_CODE = {}
    ds._STATION_INDEX_LOADED = False


def test_strip_accents_basic():
    assert ds._strip_accents("Joensuü") == "Joensuu"


def test_strip_accents_exception_path():
    obj = object()
    # Passing a non-string triggers exception and returns the input as-is
    assert ds._strip_accents(obj) is obj


def test_ensure_station_index_loaded_success(monkeypatch):
    # Mock metadata endpoint with station names including " asema" and accents
    stations = [
        {
            "stationShortCode": "JNS",
            "stationName": "Joensuun asema",
            "passengerTraffic": True,
        },
        {
            "stationShortCode": "HKI",
            "stationName": "Helsinki",
            "passengerTraffic": True,
        },
    ]
    resp = Mock(status_code=200)
    resp.json.return_value = stations
    with patch("services.digitraffic_service.requests.get", return_value=resp):
        ds._ensure_station_index_loaded()

    assert ds._STATION_INDEX_LOADED is True
    # name without " asema" becomes index and display mapping
    assert ds._STATION_INDEX.get("joensuun") == "JNS"
    assert ds._STATION_NAME_BY_CODE.get("JNS") == "Joensuun"


def test_ensure_station_index_loaded_http_non_200(monkeypatch):
    resp = Mock(status_code=500)
    with patch("services.digitraffic_service.requests.get", return_value=resp):
        ds._ensure_station_index_loaded()
    assert ds._STATION_INDEX_LOADED is True
    # Fallback contains built-ins
    assert ds._STATION_INDEX.get("joensuu") == "JNS"
    assert ds._STATION_NAME_BY_CODE.get("JNS") == "JNS"


def test_ensure_station_index_loaded_exception(monkeypatch):
    with patch(
        "services.digitraffic_service.requests.get", side_effect=RuntimeError("boom")
    ):
        ds._ensure_station_index_loaded()
    assert ds._STATION_INDEX_LOADED is True
    assert ds._STATION_INDEX.get("joensuu") == "JNS"


def test_normalize_station_variants(monkeypatch):
    # Preload small station index to avoid network
    ds._STATION_INDEX = {"joensuu": "JNS", "helsinki": "HKI", "joensuun": "JNS"}
    ds._STATION_NAME_BY_CODE = {"JNS": "Joensuu", "HKI": "Helsinki"}
    ds._STATION_INDEX_LOADED = True

    assert ds._normalize_station(None) == "JNS"
    assert ds._normalize_station("") == "JNS"
    assert ds._normalize_station("jns") == "JNS"  # short code
    assert ds._normalize_station("Joensuu") == "JNS"
    assert ds._normalize_station("Joensuü") == "JNS"  # accentless match
    assert ds._normalize_station("Joensuun asema") == "JNS"  # trim suffix
    assert ds._normalize_station("Unknown") == "UNKNOWN"
    # String that becomes empty after strip
    assert ds._normalize_station("   ") == "JNS"


def test_code_to_name_uses_mapping():
    ds._STATION_NAME_BY_CODE = {"JNS": "Joensuu"}
    ds._STATION_INDEX_LOADED = True
    assert ds._code_to_name("JNS") == "Joensuu"
    assert ds._code_to_name("XXX") == "XXX"
    assert ds._code_to_name(None) == "?"


def test_to_local_time_valid_and_invalid(monkeypatch):
    # Valid
    iso = "2025-08-20T12:15:00.000Z"
    out = ds._to_local_time(iso)
    assert isinstance(out, str) and len(out) == 5 and ":" in out
    # Invalid -> fallback
    assert ds._to_local_time("not-a-time") == "--:--"

    # Force zoneinfo path to succeed to cover astimezone(ZoneInfo)
    class FakeTZ(dt.tzinfo):
        def utcoffset(self, d):
            return dt.timedelta(0)

        def dst(self, d):
            return dt.timedelta(0)

        def tzname(self, d):
            return "Fake"

    import sys as _sys
    import types

    fake_mod = types.SimpleNamespace(ZoneInfo=lambda _tz: FakeTZ())
    orig = _sys.modules.get("zoneinfo")
    _sys.modules["zoneinfo"] = fake_mod  # type: ignore
    try:
        out2 = ds._to_local_time(iso)
        assert isinstance(out2, str)
    finally:
        if orig is not None:
            _sys.modules["zoneinfo"] = orig
        else:
            del _sys.modules["zoneinfo"]


def _mk_row(
    code: str,
    typ: str,
    sched: str = None,
    live: str = None,
    track: str = None,
    actual: str = None,
):
    r = {"stationShortCode": code, "type": typ}
    if sched:
        r["scheduledTime"] = sched
    if live:
        r["liveEstimateTime"] = live
    if track is not None:
        r["commercialTrack"] = track
    if actual:
        r["actualTime"] = actual
    return r


def _iso(dtobj):
    return dtobj.strftime("%Y-%m-%dT%H:%M:%SZ")


def test_station_index_invalid_entries_continue_and_except(monkeypatch):
    # Include an entry missing name (triggers 'continue') and a non-dict entry (triggers except -> continue)
    stations = [
        {"stationShortCode": "JNS", "stationName": ""},  # missing name -> continue
        123,  # non-dict -> exception
    ]
    resp = Mock(status_code=200)
    resp.json.return_value = stations
    with patch("services.digitraffic_service.requests.get", return_value=resp):
        ds._ensure_station_index_loaded()
    assert ds._STATION_INDEX_LOADED is True


def test_format_train_row_basic_with_delay_and_tracks():
    station = "JNS"
    now = dt.datetime.now(dt.timezone.utc)
    sched = _iso(now)
    live = _iso(now + dt.timedelta(minutes=5))

    rows = [
        _mk_row("JNS", "DEPARTURE", sched=sched, live=live, track="3"),
        _mk_row("HKI", "ARRIVAL", sched=_iso(now + dt.timedelta(hours=5)), track="8"),
    ]
    train = {
        "trainNumber": 7,
        "trainType": "IC",
        "runningCurrently": True,
        "timeTableRows": rows,
    }

    out = ds._format_train_row(train, station, kind="DEPARTURE")
    assert out is not None
    assert "(+5 min)" in out
    assert "raide 3" in out and "raide 8" in out
    assert "IC7" in out

    # Also cover: to_code missing, and _get_track_for exception path
    class BadRow:
        def __init__(self, code, typ):
            self.code = code
            self.typ = typ

        def get(self, key, default=None):
            if key == "stationShortCode":
                return self.code
            if key == "type":
                return self.typ
            if key == "commercialTrack":
                raise RuntimeError("bad track")
            return default

    rows_extra = [
        _mk_row("JNS", "DEPARTURE", sched=sched),
        BadRow(
            "JNS", "DEPARTURE"
        ),  # triggers exception in _get_track_for without breaking earlier filters
        {},  # missing stationShortCode -> to_code becomes None (and ensure last element is dict)
    ]
    train2 = {
        "trainNumber": 9,
        "trainType": "IC",
        "runningCurrently": True,
        "timeTableRows": rows_extra,
    }
    out2 = ds._format_train_row(train2, station, kind="DEPARTURE")
    assert out2 is not None

    # Diff parse exception path (bad ISO)
    rows_bad = [
        _mk_row("JNS", "DEPARTURE", sched="bad", live="also-bad"),
        _mk_row("HKI", "ARRIVAL", sched=_iso(now + dt.timedelta(hours=5))),
    ]
    train3 = {"trainNumber": 10, "timeTableRows": rows_bad}
    out3 = ds._format_train_row(train3, station, kind="DEPARTURE")
    assert out3 is not None
    assert "(+" not in out3 and "(-" not in out3


def test_format_train_row_negative_delay_and_arrival_only():
    station = "JNS"
    now = dt.datetime.now(dt.timezone.utc)
    sched = _iso(now)
    live = _iso(now - dt.timedelta(minutes=3))

    rows = [
        _mk_row("HKI", "DEPARTURE", sched=_iso(now - dt.timedelta(hours=5))),
        _mk_row("JNS", "ARRIVAL", sched=sched, live=live),
    ]
    train = {
        "trainNumber": 1,
        "trainType": "P",
        "runningCurrently": False,
        "timeTableRows": rows,
    }

    out = ds._format_train_row(train, station, kind="ARRIVAL")
    assert out is not None
    assert "(-3 min)" in out


def test_format_train_row_no_rows_for_station_returns_none():
    rows = [_mk_row("HKI", "DEPARTURE", sched=_iso(dt.datetime.now(dt.timezone.utc)))]
    train = {"trainNumber": 1, "trainType": "IC", "timeTableRows": rows}
    assert ds._format_train_row(train, "JNS") is None


def test_format_train_row_handles_exception():
    # Malformed train data triggers exception path
    train = {"timeTableRows": None}
    assert ds._format_train_row(train, "JNS") is None
    # Outer exception path: passing non-dict train
    assert ds._format_train_row(None, "JNS") is None


def test_has_terminated_cases():
    now = dt.datetime.now(dt.timezone.utc)
    # Final arrival with actualTime -> True
    rows1 = [_mk_row("JNS", "ARRIVAL", actual=_iso(now))]
    t1 = {"timeTableRows": rows1}
    assert ds._has_terminated(t1) is True

    # Not running and past final arrival -> True
    rows2 = [_mk_row("JNS", "ARRIVAL", sched=_iso(now - dt.timedelta(minutes=1)))]
    t2 = {"timeTableRows": rows2, "runningCurrently": False}
    assert ds._has_terminated(t2) is True

    # Not running with bad timestamp -> True
    rows3 = [{"stationShortCode": "JNS", "type": "ARRIVAL", "scheduledTime": "bad"}]
    t3 = {"timeTableRows": rows3, "runningCurrently": False}
    assert ds._has_terminated(t3) is True

    # Running or missing rows -> False
    assert (
        ds._has_terminated({"timeTableRows": rows2, "runningCurrently": True}) is False
    )
    assert ds._has_terminated({"timeTableRows": []}) is False
    assert ds._has_terminated({}) is False
    # Not running and no timestamp -> returns True
    t4 = {
        "timeTableRows": [{"stationShortCode": "JNS", "type": "ARRIVAL"}],
        "runningCurrently": False,
    }
    assert ds._has_terminated(t4) is True
    # Exception path -> False
    assert ds._has_terminated([]) is False


def test_get_trains_for_station_error_and_empty(monkeypatch):
    # HTTP error
    resp = Mock(status_code=500)
    with patch("services.digitraffic_service.requests.get", return_value=resp):
        out = ds.get_trains_for_station("JNS")
    assert "HTTP 500" in out

    # Empty list
    resp2 = Mock(status_code=200)
    resp2.json.return_value = []
    with patch("services.digitraffic_service.requests.get", return_value=resp2):
        out = ds.get_trains_for_station("JNS")
    assert "Ei junia" in out


def test_get_trains_for_station_filters_and_limits(monkeypatch):
    st = "JNS"
    now = dt.datetime.now(dt.timezone.utc)

    def mk_train(num, dep_minutes):
        rows = [
            _mk_row(
                st, "DEPARTURE", sched=_iso(now + dt.timedelta(minutes=dep_minutes))
            ),
            _mk_row(
                "HKI",
                "ARRIVAL",
                sched=_iso(now + dt.timedelta(hours=dep_minutes / 60 + 4)),
            ),
        ]
        return {
            "trainNumber": num,
            "trainType": "IC",
            "timeTableRows": rows,
            "runningCurrently": True,
        }

    # Include one terminated and one without DEPARTURE at station which should be filtered out
    terminated_rows = [_mk_row(st, "ARRIVAL", actual=_iso(now))]
    terminated = {"timeTableRows": terminated_rows, "runningCurrently": False}
    wrong_station = {"timeTableRows": [_mk_row("HKI", "DEPARTURE", sched=_iso(now))]}

    trains = [terminated, wrong_station, mk_train(7, 30), mk_train(3, 10)]

    resp = Mock(status_code=200)
    resp.json.return_value = trains

    # Provide simple name mapping for header
    ds._STATION_NAME_BY_CODE = {st: "Joensuu"}
    ds._STATION_INDEX_LOADED = True

    with patch("services.digitraffic_service.requests.get", return_value=resp):
        out = ds.get_trains_for_station(st, max_rows=1)

    assert out.startswith("🚉 Asema Joensuu")
    # Should list only one due to limit
    assert out.count("IC") == 1

    # Only terminated -> early no arrivals after termination filter
    resp_term_only = Mock(status_code=200)
    resp_term_only.json.return_value = [
        {
            "timeTableRows": [_mk_row(st, "ARRIVAL", actual=_iso(now))],
            "runningCurrently": False,
        }
    ]
    with patch(
        "services.digitraffic_service.requests.get", return_value=resp_term_only
    ):
        out2 = ds.get_arrivals_for_station(st)
    assert "Ei saapuvia" in out2

    # Only wrong-station trains -> early no arrivals after ARRIVAL filter
    resp_wrong_only = Mock(status_code=200)
    resp_wrong_only.json.return_value = [
        {"timeTableRows": [_mk_row("HKI", "ARRIVAL", sched=_iso(now))]}
    ]
    with patch(
        "services.digitraffic_service.requests.get", return_value=resp_wrong_only
    ):
        out3 = ds.get_arrivals_for_station(st)
    assert "Ei saapuvia" in out3

    # Rows containing non-dict to exercise exception path in arrival filter loop
    resp_bad_row = Mock(status_code=200)
    resp_bad_row.json.return_value = [
        {"timeTableRows": [123, _mk_row("XXX", "DEPARTURE", sched=_iso(now))]}
    ]
    with patch("services.digitraffic_service.requests.get", return_value=resp_bad_row):
        out_bad = ds.get_arrivals_for_station(st)
    assert isinstance(out_bad, str)

    # ARRIVAL row with no times -> exercise next_arr_iso fallback
    resp_no_times = Mock(status_code=200)
    resp_no_times.json.return_value = [
        {"timeTableRows": [_mk_row(st, "ARRIVAL")]},
        mk_train(3, 10),
    ]
    with patch("services.digitraffic_service.requests.get", return_value=resp_no_times):
        out4 = ds.get_arrivals_for_station(st)
    assert out4.startswith("🚉 Asema ")

    # Force formatter to None -> len(lines)==1 fallback
    with patch.object(ds, "_format_train_row", return_value=None), patch(
        "services.digitraffic_service.requests.get", return_value=resp_no_times
    ):
        out5 = ds.get_arrivals_for_station(st)
    assert "Ei saapuvia" in out5

    # Only terminated trains -> early "no trains" after termination filter
    resp_only_term = Mock(status_code=200)
    resp_only_term.json.return_value = [
        {
            "timeTableRows": [_mk_row(st, "ARRIVAL", actual=_iso(now))],
            "runningCurrently": False,
        }
    ]
    with patch(
        "services.digitraffic_service.requests.get", return_value=resp_only_term
    ):
        out2 = ds.get_trains_for_station(st)
    assert "Ei junia" in out2

    # Only wrong-station trains -> early "no trains" after DEPARTURE filter
    resp_wrong_only = Mock(status_code=200)
    resp_wrong_only.json.return_value = [
        {"timeTableRows": [_mk_row("HKI", "DEPARTURE", sched=_iso(now))]}
    ]
    with patch(
        "services.digitraffic_service.requests.get", return_value=resp_wrong_only
    ):
        out3 = ds.get_trains_for_station(st)
    assert "Ei junia" in out3

    # Train with DEPARTURE but no times -> exercise next_dep_iso fallback
    resp_no_times = Mock(status_code=200)
    resp_no_times.json.return_value = [
        {"timeTableRows": [_mk_row(st, "DEPARTURE")]},
        mk_train(9, 20),
    ]
    with patch("services.digitraffic_service.requests.get", return_value=resp_no_times):
        out4 = ds.get_trains_for_station(st)
    # Should produce a valid header and not crash; exact rows may vary
    assert out4.startswith("🚉 Asema ")

    # Force format_train_row to return None -> triggers len(lines)==1 fallback
    with patch.object(ds, "_format_train_row", return_value=None), patch(
        "services.digitraffic_service.requests.get", return_value=resp_no_times
    ):
        out5 = ds.get_trains_for_station(st)
    assert "Ei junia" in out5


def test_departures_filter_exception_path(monkeypatch):
    st = "JNS"
    now = dt.datetime.now(dt.timezone.utc)
    resp = Mock(status_code=200)
    resp.json.return_value = [
        {"timeTableRows": [123, _mk_row("XXX", "DEPARTURE", sched=_iso(now))]}
    ]
    with patch("services.digitraffic_service.requests.get", return_value=resp):
        out = ds.get_trains_for_station(st)
    assert "Ei junia" in out


def test_get_trains_for_station_timeout_and_exception(monkeypatch):
    with patch(
        "services.digitraffic_service.requests.get", side_effect=requests.Timeout()
    ):
        out = ds.get_trains_for_station("JNS")
    assert "aikakatkaisu" in out

    with patch(
        "services.digitraffic_service.requests.get", side_effect=RuntimeError("boom")
    ):
        out = ds.get_trains_for_station("JNS")
    assert "virhe" in out


def test_get_arrivals_for_station_paths(monkeypatch):
    st = "JNS"
    now = dt.datetime.now(dt.timezone.utc)

    def mk_train(num, arr_minutes):
        rows = [
            _mk_row("HKI", "DEPARTURE", sched=_iso(now)),
            _mk_row(st, "ARRIVAL", sched=_iso(now + dt.timedelta(minutes=arr_minutes))),
        ]
        return {"trainNumber": num, "trainType": "IC", "timeTableRows": rows}

    # HTTP non-200
    resp_err = Mock(status_code=404)
    with patch("services.digitraffic_service.requests.get", return_value=resp_err):
        out = ds.get_arrivals_for_station(st)
    assert "HTTP 404" in out

    # Empty list
    resp_empty = Mock(status_code=200)
    resp_empty.json.return_value = []
    with patch("services.digitraffic_service.requests.get", return_value=resp_empty):
        out = ds.get_arrivals_for_station(st)
    assert "Ei saapuvia" in out

    # Filtered to arrivals
    trains = [mk_train(1, 30), mk_train(2, 10)]
    resp_ok = Mock(status_code=200)
    resp_ok.json.return_value = trains

    ds._STATION_NAME_BY_CODE = {st: "Joensuu"}
    ds._STATION_INDEX_LOADED = True

    with patch("services.digitraffic_service.requests.get", return_value=resp_ok):
        out = ds.get_arrivals_for_station(st, max_rows=1)

    assert out.startswith("🚉 Asema Joensuu")
    assert out.count("IC") == 1

    # Timeout and generic exception
    with patch(
        "services.digitraffic_service.requests.get", side_effect=requests.Timeout()
    ):
        out = ds.get_arrivals_for_station(st)
    assert "aikakatkaisu" in out

    with patch(
        "services.digitraffic_service.requests.get", side_effect=RuntimeError("boom")
    ):
        out = ds.get_arrivals_for_station(st)
    assert "virhe" in out
