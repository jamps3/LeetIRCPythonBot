#!/usr/bin/env python3
"""
Digitraffic Service

Fetches live train information from the Finnish Digitraffic rail API.

Primary entrypoint:
- get_trains_for_station(station: str | None) -> str

Notes:
- Defaults to Joensuu (JNS) when station is None/empty.
- Accepts common forms like "Joensuu" or "JNS" (case-insensitive).
- Returns a short, IRC-friendly summary string. Multiple lines are separated by \n.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import unicodedata
from typing import Any, Dict, List, Optional

import requests

# Base URL for Digitraffic rail API
BASE_URL = "https://rata.digitraffic.fi/api/v1"

# Minimal built-in aliases as a fallback; full list is loaded from Digitraffic metadata
STATION_ALIASES = {
    "joensuu": "JNS",
    "jns": "JNS",
    "helsinki": "HKI",
    "hki": "HKI",
    "tampere": "TPE",
    "tpe": "TPE",
    "oulu": "OL",
    "turku": "TKU",
    "tku": "TKU",
}

# Lazy-loaded station index from Digitraffic metadata
_STATION_INDEX: Dict[str, str] = {}
# Mapping short code -> display name (e.g., "JNS" -> "Joensuu")
_STATION_NAME_BY_CODE: Dict[str, str] = {}
_STATION_INDEX_LOADED = False


def _strip_accents(text: str) -> str:
    try:
        return "".join(
            c
            for c in unicodedata.normalize("NFKD", text)
            if not unicodedata.combining(c)
        )
    except Exception:
        return text


def _ensure_station_index_loaded():
    global _STATION_INDEX_LOADED, _STATION_INDEX, _STATION_NAME_BY_CODE
    if _STATION_INDEX_LOADED:
        return
    try:
        url = f"{BASE_URL}/metadata/stations"
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            _STATION_INDEX_LOADED = True  # avoid refetch loops
            # Keep built-ins as minimal fallback mappings
            _STATION_INDEX = {k.lower(): v for k, v in STATION_ALIASES.items()}
            _STATION_NAME_BY_CODE = {v: v for v in set(STATION_ALIASES.values())}
            return
        data = resp.json()
        idx: Dict[str, str] = {}
        by_code: Dict[str, str] = {}
        if isinstance(data, list):
            for st in data:
                try:
                    short = (st.get("stationShortCode") or "").upper()
                    name = (st.get("stationName") or "").strip()
                    passenger = bool(st.get("passengerTraffic", False))
                    if not short or not name:
                        continue
                    # Prefer user-friendly display names without the trailing " asema"
                    disp = name
                    lname = name.lower()
                    if lname.endswith(" asema"):
                        base = name[:-6].strip()
                        if base:
                            disp = base
                    by_code[short] = disp

                    # Index both short code and names (with and without accents)
                    idx[short.lower()] = short
                    idx[lname] = short
                    idx[_strip_accents(lname)] = short
                    # Also index common patterns like removing " asema"
                    if lname.endswith(" asema"):
                        base = lname[:-6].strip()
                        if base:
                            idx[base] = short
                            idx[_strip_accents(base)] = short
                except Exception:
                    continue
        # Merge built-ins as a fallback
        for k, v in STATION_ALIASES.items():
            idx.setdefault(k.lower(), v)
            by_code.setdefault(v, by_code.get(v, v))
        _STATION_INDEX = idx
        _STATION_NAME_BY_CODE = by_code
    except Exception:
        # On failure, keep built-ins only
        _STATION_INDEX = {k.lower(): v for k, v in STATION_ALIASES.items()}
        _STATION_NAME_BY_CODE = {v: v for v in set(STATION_ALIASES.values())}
    finally:
        _STATION_INDEX_LOADED = True


def _normalize_station(input_station: Optional[str]) -> str:
    if not input_station:
        return "JNS"
    s_raw = str(input_station).strip()
    if not s_raw:
        return "JNS"
    s = s_raw.lower()
    # If looks like a short code already, return upper
    if 2 <= len(s) <= 5 and s.isalpha():
        return s.upper()
    # Ensure station index is loaded and try to resolve
    _ensure_station_index_loaded()
    # Try exact, accentless, and trimmed variants
    cand = _STATION_INDEX.get(s)
    if not cand:
        s2 = _strip_accents(s)
        cand = _STATION_INDEX.get(s2)
    if not cand and s.endswith(" asema"):
        base = s[:-6].strip()
        cand = _STATION_INDEX.get(base) or _STATION_INDEX.get(_strip_accents(base))
    if cand:
        return cand.upper()
    # Fallback to built-ins or uppercase guess
    return STATION_ALIASES.get(s, s_raw.upper())


def _code_to_name(code: Optional[str]) -> str:
    if not code:
        return "?"
    _ensure_station_index_loaded()
    return _STATION_NAME_BY_CODE.get(code.upper(), code.upper())


def _to_local_time(iso_str: str, tz: str = "Europe/Helsinki") -> str:
    try:
        # Parse ISO8601 time; API returns like 2025-08-20T12:15:00.000Z
        t = dt.datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        # Convert to Helsinki time for user-friendliness
        try:
            import zoneinfo  # Python 3.9+

            helsinki = zoneinfo.ZoneInfo(tz)
            t = t.astimezone(helsinki)
        except Exception:
            # Fallback: local time conversion without zoneinfo
            t = t.astimezone()
        return t.strftime("%H:%M")
    except Exception:
        return "--:--"


def _format_train_row(
    train: Dict[str, Any], station: str, kind: str = "DEPARTURE"
) -> Optional[str]:
    try:
        train_number = train.get("trainNumber")
        train_type = train.get("trainType") or "JR"
        running = train.get("runningCurrently", True)

        # Times are in timeTableRows; filter for this station and type
        rows = train.get("timeTableRows") or []
        st_rows = [r for r in rows if r.get("stationShortCode") == station]
        dep_rows = [r for r in st_rows if r.get("type") == "DEPARTURE"]
        arr_rows = [r for r in st_rows if r.get("type") == "ARRIVAL"]

        dep = dep_rows[0] if dep_rows else None
        arr = arr_rows[0] if arr_rows else None

        # If neither an arrival nor a departure exists for this station, skip
        if not dep and not arr:
            return None

        # Determine origin and destination from the full timetable order
        dest_code = rows[-1].get("stationShortCode") if rows else None
        orig_code = rows[0].get("stationShortCode") if rows else None

        # Compute both arrival and departure times (at this station)
        def row_time(tt):
            if not tt:
                return None
            ts = tt.get("liveEstimateTime") or tt.get("scheduledTime")
            return _to_local_time(ts) if ts else None

        arr_time_val = row_time(arr)
        dep_time_val = row_time(dep)

        # Build time string: show only existing parts and annotate special cases
        parts: List[str] = []
        terminus_only = bool(arr) and not bool(dep)
        origin_only = bool(dep) and not bool(arr)
        if arr_time_val:
            parts.append(f"Saapuu: {arr_time_val}")
        if dep_time_val:
            parts.append(f"Lähtö: {dep_time_val}")
        time_str = " • ".join(parts)

        # Choose a representative timetable row for delay: prefer dep, else arr
        tt_row = dep or arr

        # Delay info (based on the chosen tt_row)
        diff_min = 0
        if tt_row:
            est = tt_row.get("liveEstimateTime")
            sched = tt_row.get("scheduledTime")
            if est and sched:
                try:
                    e = dt.datetime.fromisoformat(est.replace("Z", "+00:00"))
                    s = dt.datetime.fromisoformat(sched.replace("Z", "+00:00"))
                    diff = e - s
                    diff_min = int(round(diff.total_seconds() / 60.0))
                except Exception:
                    diff_min = 0

        delay_str = ""
        if diff_min > 0:
            delay_str = f" (+{diff_min} min)"
        elif diff_min < 0:
            delay_str = f" ({diff_min} min)"

        status = "🟢" if running else "⚪"

        # Determine origin/destination station codes and display names
        to_code = rows[-1].get("stationShortCode") if rows else None
        from_code = rows[0].get("stationShortCode") if rows else None
        to_name = _code_to_name(to_code)
        from_name = _code_to_name(from_code)

        # Resolve platform/track for BOTH ends: origin (DEPARTURE row) and
        # destination (ARRIVAL row). If not available, omit.
        def _get_track_for(code: Optional[str], row_type: str) -> Optional[str]:
            if not code:
                return None
            for r in rows:
                try:
                    if r.get("stationShortCode") == code and r.get("type") == row_type:
                        tr = r.get("commercialTrack")
                        if tr:
                            return str(tr)
                except Exception:
                    continue
            return None

        from_track = _get_track_for(from_code, "DEPARTURE")
        to_track = _get_track_for(to_code, "ARRIVAL")

        def _maybe_track(s: Optional[str]) -> str:
            return f" (laituri {s})" if s else ""

        # Format the final output string with track shown for both ends
        if kind == "DEPARTURE":
            route_part = f"{from_name}{_maybe_track(from_track)} → {to_name}{_maybe_track(to_track)}"
        else:
            route_part = f"{from_name}{_maybe_track(from_track)} → {to_name}{_maybe_track(to_track)}"
        return (
            f"{status} {time_str} {route_part} {delay_str} [{train_type}{train_number}]"
        )
    except Exception:
        return None


def _has_terminated(train: Dict[str, Any]) -> bool:
    """Return True if the train has already arrived at its terminal station."""
    try:
        rows = train.get("timeTableRows") or []
        if not rows:
            return False
        last = rows[-1]
        if last.get("type") != "ARRIVAL":
            return False
        # If we have actualTime for the final ARRIVAL, it has terminated
        if last.get("actualTime"):
            return True
        # If not running and we've passed the final arrival's time, treat as terminated
        if not train.get("runningCurrently", True):
            ts = (
                last.get("liveEstimateTime")
                or last.get("scheduledTime")
                or last.get("actualTime")
            )
            if ts:
                try:
                    final_t = dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    now_utc = dt.datetime.now(dt.timezone.utc)
                    return now_utc >= final_t
                except Exception:
                    return True
            return True
        return False
    except Exception:
        return False


def get_trains_for_station(station: Optional[str] = None, max_rows: int = 8) -> str:
    """
    Fetch and format upcoming DEPARTURES for a station.

    Args:
        station: Station short code (e.g., JNS) or common name (e.g., Joensuu). Defaults to JNS.
        max_rows: Maximum lines to include in output.

    Returns:
        A concise, multi-line string suitable for IRC.
    """
    st = _normalize_station(station)

    # Prefer departures around now. live-trains endpoint returns active trains including timetable rows
    url = f"{BASE_URL}/live-trains?station={st}&include_nonstopping=false"

    try:
        resp = requests.get(url, timeout=8)
        if resp.status_code != 200:
            return f"❌ Digitraffic error: HTTP {resp.status_code}"
        trains = resp.json()
        if not isinstance(trains, list) or not trains:
            return f"Ei junia lähiaikoina asemalta {st}."

        # Filter out trains that have already arrived to their terminal station
        trains = [t for t in trains if not _has_terminated(t)]
        if not trains:
            return f"Ei junia lähiaikoina asemalta {st}."

        # Keep only trains that actually DEPART from this station (avoid mixing arrivals)
        def _has_row_type_at_station(t: Dict[str, Any], st_code: str, typ: str) -> bool:
            rows = t.get("timeTableRows") or []
            for r in rows:
                try:
                    if r.get("stationShortCode") == st_code and r.get("type") == typ:
                        return True
                except Exception:
                    continue
            return False

        trains = [t for t in trains if _has_row_type_at_station(t, st, "DEPARTURE")]
        if not trains:
            return f"Ei junia lähiaikoina asemalta {st}."

        lines: List[str] = []
        header_name = _code_to_name(st)
        lines.append(f"🚉 Asema {header_name} – lähtevät junat:")

        # Sort by next departure time at this station
        def next_dep_iso(t: Dict[str, Any]) -> str:
            rows = t.get("timeTableRows") or []
            for r in rows:
                if (
                    r.get("stationShortCode") == st
                    and r.get("type") == "DEPARTURE"
                    and (r.get("liveEstimateTime") or r.get("scheduledTime"))
                ):
                    return r.get("liveEstimateTime") or r.get("scheduledTime")
            return "9999-12-31T23:59:59Z"

        trains.sort(key=next_dep_iso)

        count = 0
        for t in trains:
            row = _format_train_row(t, st, kind="DEPARTURE")
            if row:
                lines.append(row)
                count += 1
                if count >= max_rows:
                    break

        if len(lines) == 1:
            return f"Ei junia lähiaikoina asemalta {st}."

        return "\n".join(lines)

    except requests.Timeout:
        return "❌ Digitraffic: aikakatkaisu (timeout)"
    except Exception as e:
        return f"❌ Digitraffic virhe: {e}"


def get_arrivals_for_station(station: Optional[str] = None, max_rows: int = 8) -> str:
    """
    Fetch and format upcoming ARRIVALS for a station.
    """
    st = _normalize_station(station)
    url = f"{BASE_URL}/live-trains?station={st}&include_nonstopping=false"
    try:
        resp = requests.get(url, timeout=8)
        if resp.status_code != 200:
            return f"❌ Digitraffic error: HTTP {resp.status_code}"
        trains = resp.json()
        if not isinstance(trains, list) or not trains:
            return f"Ei saapuvia junia lähiaikoina asemalle {st}."

        # Filter out trains that have already arrived to their terminal station
        trains = [t for t in trains if not _has_terminated(t)]
        if not trains:
            return f"Ei saapuvia junia lähiaikoina asemalle {st}."

        # Keep only trains that actually ARRIVE at this station (avoid mixing departures)
        def _has_row_type_at_station(t: Dict[str, Any], st_code: str, typ: str) -> bool:
            rows = t.get("timeTableRows") or []
            for r in rows:
                try:
                    if r.get("stationShortCode") == st_code and r.get("type") == typ:
                        return True
                except Exception:
                    continue
            return False

        trains = [t for t in trains if _has_row_type_at_station(t, st, "ARRIVAL")]
        if not trains:
            return f"Ei saapuvia junia lähiaikoina asemalle {st}."

        lines: List[str] = []
        header_name = _code_to_name(st)
        lines.append(f"🚉 Asema {header_name} – saapuvat junat:")

        # Sort by next arrival time at this station
        def next_arr_iso(t: Dict[str, Any]) -> str:
            rows = t.get("timeTableRows") or []
            for r in rows:
                if (
                    r.get("stationShortCode") == st
                    and r.get("type") == "ARRIVAL"
                    and (r.get("liveEstimateTime") or r.get("scheduledTime"))
                ):
                    return r.get("liveEstimateTime") or r.get("scheduledTime")
            return "9999-12-31T23:59:59Z"

        trains.sort(key=next_arr_iso)

        count = 0
        for t in trains:
            row = _format_train_row(t, st, kind="ARRIVAL")
            if row:
                lines.append(row)
                count += 1
                if count >= max_rows:
                    break

        if len(lines) == 1:
            return f"Ei saapuvia junia lähiaikoina asemalle {st}."

        return "\n".join(lines)
    except requests.Timeout:
        return "❌ Digitraffic: aikakatkaisu (timeout)"
    except Exception as e:
        return f"❌ Digitraffic virhe: {e}"
