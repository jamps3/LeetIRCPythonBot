import argparse
from datetime import datetime

import requests

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

API_KEY = "99fkw8m6wg9smg7gcylsaqbshu074sqjftlqfl8k"
BASE_URL = "https://www.meteosource.com/api/v1/free/point"
DEFAULT_CITY = "Joensuu"


def fetch(city: str) -> dict:
    params = {
        "place_id": city,
        "sections": "current,hourly",
        "language": "en",
        "units": "metric",
        "key": API_KEY,
    }
    r = requests.get(BASE_URL, params=params, timeout=10)
    if r.status_code != 200:
        snippet = (r.text or "").strip().replace("\n", " ")
        if len(snippet) > 200:
            snippet = snippet[:200] + "…"
        raise RuntimeError(f"API HTTP {r.status_code}: {snippet}")
    return r.json()


def sym(cond: str, icon: int | None) -> str:
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


def list_lines(data: dict, limit: int = 13) -> list[str]:
    hourly = (data.get("hourly") or {}).get("data", [])
    now = datetime.now(ZoneInfo("Europe/Helsinki")) if ZoneInfo else datetime.now()
    cutoff = now.replace(minute=0, second=0, microsecond=0)
    # API times are local and offset-naive; compare using naive datetimes
    cutoff = cutoff.replace(tzinfo=None)
    out = []
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
        s = sym(cond, h.get("icon"))

        def _fmt_num(val, decimals=1):
            try:
                s = f"{float(val):.{decimals}f}"
            except Exception:
                return str(val) if val is not None else "?"
            # If integer part is a single digit (e.g., 4.0), add one leading space for alignment
            try:
                int_part = s.split(".", 1)[0].lstrip("-")
                if len(int_part) == 1:
                    s = " " + s
            except Exception:
                pass
            return s

        temp_fmt = _fmt_num(temp, 1) + "°C"
        precip_fmt = _fmt_num(precip, 1) + "mm"
        wind_fmt = _fmt_num(wind, 1) + "m/s"

        out.append(
            f"{t.strftime('%H')}: 🌡️ {temp_fmt} | 🌧️ {precip_fmt} | 💨 {wind_fmt} {s}"
        )
        if len(out) >= limit:
            break
    return out


def main():
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("args", nargs="*")
    p.add_argument("--list", dest="list_mode", action="store_true")
    ns, _ = p.parse_known_args()

    # Support both "--list" and bare positional "list" mode
    list_mode = bool(ns.list_mode)
    parts = list(ns.args)
    if parts and isinstance(parts[0], str) and parts[0].lower() == "list":
        list_mode = True
        parts = parts[1:]

    # Optional trailing hours parameter
    hours = 8
    if parts:
        last = parts[-1]
        try:
            cand = int(last)
            if cand > 0:
                hours = min(cand, 24)
                parts = parts[:-1]
        except Exception:
            pass

    city = " ".join(parts).strip() or DEFAULT_CITY
    data = fetch(city)

    lines = list_lines(data, limit=hours)
    if list_mode:
        # City name on its own line, then hourly entries one per line
        print(city)
        for ln in lines:
            print(ln)
    else:
        # City first, then all hours on a single line
        print(f"{city}: " + " | ".join(lines))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Virhe: {e}")
