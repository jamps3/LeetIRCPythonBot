from __future__ import annotations

import os
from datetime import datetime

import requests

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:  # pragma: no cover
    ZoneInfo = None

# Load API key from environment (.env)
API_KEY = os.getenv("WEATHER_FORECAST_API_KEY", "")
BASE_URL = "https://www.meteosource.com/api/v1/free/point"
DEFAULT_CITY = "Joensuu"


def _fetch(city: str) -> dict:
    if not API_KEY:
        raise RuntimeError(
            "Weather forecast API key missing. Set WEATHER_FORECAST_API_KEY in .env"
        )
    params = {
        "place_id": city,
        "sections": "current,hourly",
        "language": "en",
        "units": "metric",
        "key": API_KEY,
    }
    try:
        r = requests.get(BASE_URL, params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.HTTPError as e:
        status = None
        try:
            status = e.response.status_code if e.response is not None else None
        except Exception:
            status = None
            status = None
        msg = f"API request failed (HTTP {status})" if status else "API request failed"
        raise RuntimeError(msg)
    except requests.exceptions.RequestException:
        raise RuntimeError("Network error contacting weather API")
    except ValueError:
        raise RuntimeError("Invalid JSON from weather API")


def _sym(cond: str, icon: int | None) -> str:
    c = (cond or "").lower()
    if any(k in c for k in ("thunder", "storm")):
        return "⛈️"
    if "snow" in c or "sleet" in c:
        return "❄️"
    if "light_rain" in c or ("rain" in c and "shower" in c):
        return "🌦️"
    if "rain" in c:
        return "🌧️"
    if "overcast" in c or "cloud" in c:
        return "☁️"
    if "clear" in c or "sunny" in c:
        return "☀️"
    if "fog" in c or "mist" in c or "haze" in c:
        return "🌁"
    return "🌈"


def _fmt_num(val, decimals: int = 1) -> str:
    try:
        s = f"{float(val):.{decimals}f}"
    except Exception:
        return str(val) if val is not None else "?"
    # Add one leading space if integer part is a single digit for alignment
    try:
        int_part = s.split(".", 1)[0].lstrip("-")
        if len(int_part) == 1:
            s = " " + s
    except Exception:
        pass
    return s


def _list_lines(data: dict, limit: int = 8) -> list[str]:
    hourly = (data.get("hourly") or {}).get("data", [])
    now = datetime.now(ZoneInfo("Europe/Helsinki")) if ZoneInfo else datetime.now()
    cutoff = now.replace(minute=0, second=0, microsecond=0).replace(tzinfo=None)
    out: list[str] = []
    for h in hourly:
        ts = h.get("date")
        if not ts:
            continue
        try:
            t = datetime.fromisoformat(ts)
        except Exception:
            continue
        if t < cutoff:
            continue
        temp = h.get("temperature")
        precip = (h.get("precipitation") or {}).get("total", 0)
        wind = (h.get("wind") or {}).get("speed", "?")
        cond = h.get("summary") or h.get("weather", "")
        s = _sym(cond, h.get("icon"))
        temp_fmt = _fmt_num(temp, 1) + "°C"
        precip_fmt = _fmt_num(precip, 1) + "mm"
        wind_fmt = _fmt_num(wind, 1) + "m/s"
        out.append(f"{t.strftime('%H')}: 🌡️{temp_fmt} 🌧️{precip_fmt} 💨{wind_fmt} {s}")
        if len(out) >= limit:
            break
    return out


def format_single_line(city: str | None = None, hours: int | None = None) -> str:
    """Return a single line: 'City: HH: ... | HH: ...' with up to 'hours' items (default 8)."""
    city_use = (city or DEFAULT_CITY).strip() or DEFAULT_CITY
    limit = hours if (isinstance(hours, int) and hours > 0) else 8
    limit = min(limit, 48)
    data = _fetch(city_use)
    segments = _list_lines(data, limit=limit)
    return f"{city_use}: " + " | ".join(segments)


def format_multi_line(city: str | None = None, hours: int | None = None) -> list[str]:
    """Return a list of lines: first the city, then up to 'hours' hourly lines (default 8)."""
    city_use = (city or DEFAULT_CITY).strip() or DEFAULT_CITY
    limit = hours if (isinstance(hours, int) and hours > 0) else 8
    limit = min(limit, 48)
    data = _fetch(city_use)
    segments = _list_lines(data, limit=limit)
    return [city_use] + segments
