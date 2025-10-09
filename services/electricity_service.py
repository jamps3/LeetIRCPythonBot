"""
Electricity Service Module 2.1

Provides Finnish electricity price information using ENTSO-E API.
Supports caching, fetching prices for specific hours, 15-minute intervals, and statistics.
"""

import xml.etree.ElementTree as ElementTree
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from io import StringIO
from typing import Any, Dict, List, Optional

import pytz
import requests

from logger import log


class ElectricityService:
    """Service for fetching Finnish electricity price information."""

    def __init__(self, api_key: str, cache_ttl_hours: int = 3):
        self.api_key = api_key
        self.base_url = "https://web-api.tp.entsoe.eu/api"
        self.finland_domain = "10YFI-1--------U"
        self.vat_rate = 1.255  # Finnish VAT 25.5%
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = timedelta(hours=cache_ttl_hours)
        self.sahko_url = "https://liukuri.fi"
        self.timezone = pytz.timezone("Europe/Helsinki")
        self.api_timezone = pytz.timezone("Europe/Brussels")  # ENTSO-E uses CET

    # ---------- Public API ----------

    def get_electricity_price(
        self,
        hour: Optional[int] = None,
        quarter: Optional[int] = None,
        date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get electricity price for a specific hour and quarter (15-min interval).
        Returns prices with VAT included in snt/kWh.
        """
        try:
            now = datetime.now(self.timezone)
            if date is None:
                date = now.date()
            elif isinstance(date, datetime):
                date = date.date()  # Ensure date is a date object

            if hour is None:
                hour = now.hour
            if quarter is None:
                quarter = (now.minute // 15) + 1  # 1-4

            # Fetch daily 15-min prices
            daily_data = self.get_daily_prices(date)
            if daily_data.get("error"):
                return daily_data

            interval_prices: Dict[tuple[int, int], float] = daily_data.get(
                "interval_prices", {}
            )
            if not interval_prices:
                return {
                    "error": True,
                    "message": "No 15-minute interval data available.",
                }

            # Prepare hourly data
            hourly_prices: Dict[int, Dict[str, Any]] = {}
            for (h, q), price in interval_prices.items():
                if h not in hourly_prices:
                    hourly_prices[h] = {"quarter_prices": {}, "avg_hour_eur_mwh": 0}
                hourly_prices[h]["quarter_prices"][q] = price

            # Compute hourly averages
            for h, data in hourly_prices.items():
                q_prices = list(data["quarter_prices"].values())
                data["avg_hour_eur_mwh"] = sum(q_prices) / len(q_prices)

            # Check if requested hour exists
            if hour not in hourly_prices:
                return {"error": True, "message": f"No price data for hour {hour}."}

            today_price = hourly_prices[hour]
            result = {
                "date": date.strftime("%Y-%m-%d"),
                "hour": hour,
                "quarter": quarter,
                "today_price": {
                    "avg_hour_eur_mwh": today_price["avg_hour_eur_mwh"],
                    "hour_avg_snt_kwh": self._convert_price(
                        today_price["avg_hour_eur_mwh"]
                    ),
                    "quarter_prices": today_price["quarter_prices"],
                    "quarter_prices_snt": {
                        q: self._convert_price(v)
                        for q, v in today_price["quarter_prices"].items()
                    },
                },
                "include_tomorrow": True,
            }

            # Tomorrow's data if available
            tomorrow_data = self.get_daily_prices(date + timedelta(days=1))
            if not tomorrow_data.get("error") and tomorrow_data.get("interval_prices"):
                interval_prices_tomorrow: Dict[tuple[int, int], float] = tomorrow_data[
                    "interval_prices"
                ]
                hourly_prices_tomorrow: Dict[int, Dict[str, Any]] = {}
                for (h, q), price in interval_prices_tomorrow.items():
                    if h not in hourly_prices_tomorrow:
                        hourly_prices_tomorrow[h] = {
                            "quarter_prices": {},
                            "avg_hour_eur_mwh": 0,
                        }
                    hourly_prices_tomorrow[h]["quarter_prices"][q] = price
                for h, data in hourly_prices_tomorrow.items():
                    q_prices = list(data["quarter_prices"].values())
                    data["avg_hour_eur_mwh"] = sum(q_prices) / len(q_prices)
                if hour in hourly_prices_tomorrow:
                    tomorrow_price = hourly_prices_tomorrow[hour]
                    result["tomorrow_price"] = {
                        "avg_hour_eur_mwh": tomorrow_price["avg_hour_eur_mwh"],
                        "hour_avg_snt_kwh": self._convert_price(
                            tomorrow_price["avg_hour_eur_mwh"]
                        ),
                        "quarter_prices": tomorrow_price["quarter_prices"],
                        "quarter_prices_snt": {
                            q: self._convert_price(v)
                            for q, v in tomorrow_price["quarter_prices"].items()
                        },
                    }
                    result["tomorrow_available"] = True
                else:
                    result["tomorrow_price"] = None
                    result["tomorrow_available"] = False
            else:
                result["tomorrow_price"] = None
                result["tomorrow_available"] = False

            return result

        except Exception as e:
            return {"error": True, "message": f"Unexpected error: {str(e)}"}

    def get_daily_prices(self, date: datetime) -> Dict[str, Any]:
        """Fetch ENTSO-E prices for a given date and map them to 15-min intervals (1–96)."""
        date_key = date.strftime("%Y-%m-%d")
        now = datetime.now(self.timezone)  # Use timezone-aware timestamp

        # Check cache - bypassed for debugging
        # cached = self._cache.get(date_key)
        # if cached and now - cached["timestamp"] < self._cache_ttl:
        #    return cached["data"]

        try:
            period_start = date.strftime("%Y%m%d") + "0000"
            period_end = (date + timedelta(days=1)).strftime("%Y%m%d") + "0000"
            params = {
                "securityToken": self.api_key,
                "documentType": "A44",
                "in_Domain": self.finland_domain,
                "out_Domain": self.finland_domain,
                "periodStart": period_start,
                "periodEnd": period_end,
            }

            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()

            tree = ElementTree.parse(StringIO(response.text))
            ns = {"ns": tree.getroot().tag.split("}")[0].strip("{")}

            prices: Dict[int, float] = {}
            for p in tree.findall(".//ns:Point", ns):
                pos = int(p.find("ns:position", ns).text)
                price = float(p.find("ns:price.amount", ns).text)
                prices[pos] = price

            # Map positions to 15-min intervals in EEST (adjust for CET to EEST): (hour, quarter)
            interval_prices: Dict[tuple[int, int], float] = {}
            for pos, price in prices.items():
                # ENTSO-E positions are in CET; adjust to EEST (UTC+3 in October 2025)
                cet_time = datetime.strptime(f"{date_key} 00:00", "%Y-%m-%d %H:%M")
                cet_time = self.api_timezone.localize(cet_time)  # CET time
                eest_time = cet_time.astimezone(self.timezone)  # Convert to EEST
                minutes_offset = (pos - 1) * 15  # Each position is 15 minutes
                eest_time = eest_time + timedelta(minutes=minutes_offset)
                hour = eest_time.hour
                quarter = ((pos - 1) % 4) + 1
                interval_prices[(hour, quarter)] = price

            # Debug print all interval_prices
            for (h, q), price in interval_prices.items():
                print(f"Interval: hour={h}, quarter={q}, price={price}")

            result = {
                "error": False,
                "date": date_key,
                "prices": prices,
                "interval_prices": interval_prices,
            }

            self._cache[date_key] = {"timestamp": now, "data": result}
            return result

        except Exception as e:
            return {"error": True, "message": f"Failed to fetch daily prices: {str(e)}"}

    # ---------- Helpers ----------

    def _convert_price(self, eur_per_mwh: float) -> float:
        eur = Decimal(str(eur_per_mwh))
        snt = (eur / Decimal("10")) * Decimal(str(self.vat_rate))
        return float(snt.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    def parse_command_args(self, args: List[str]) -> Dict[str, Any]:
        """Parse !sahko commands (tänään/huomenna/hour.quarter)."""
        now = datetime.now(self.timezone)
        result = {
            "hour": now.hour,
            "quarter": (now.minute // 15) + 1,
            "date": now.date(),
        }  # Return date object

        if not args:
            return result

        arg = args[0].lower()
        if arg in ["tänään", "today"]:
            result["date"] = now.date()
            if len(args) > 1:
                result["hour"], result["quarter"] = self._parse_hour_quarter(args[1])
        elif arg in ["huomenna", "tomorrow"]:
            result["date"] = (now + timedelta(days=1)).date()
            if len(args) > 1:
                result["hour"], result["quarter"] = self._parse_hour_quarter(args[1])
        else:
            result["hour"], result["quarter"] = self._parse_hour_quarter(arg)

        return result

    def _parse_hour_quarter(self, arg: str) -> tuple[int, int]:
        """Parse '13' or '13.2' → hour, quarter."""
        if "." in arg:
            h, q = arg.split(".")
            return int(h), int(q)
        else:
            return int(arg), 1

    def format_price_message(self, price_data: Dict[str, Any]) -> str:
        """
        Format electricity price data into a readable message with 15-minute interval support.
        Safely handles missing quarter data.
        """
        if price_data.get("error"):
            return f"⚡ Sähkön hintatietojen haku epäonnistui: {price_data.get('message', 'Tuntematon virhe')}"

        date_str = price_data["date"]
        hour = price_data["hour"]
        quarter = price_data.get("quarter")
        today_price = price_data.get("today_price")
        tomorrow_price = price_data.get("tomorrow_price")
        tomorrow_available = price_data.get("tomorrow_available", False)

        def format_single(
            price_entry: Dict[str, Any], hour: int, quarter: Optional[int] = None
        ) -> str:
            """Format either full-hour or specific 15-minute interval."""
            avg_hour_eur_mwh = price_entry.get("avg_hour_eur_mwh", 0.0)
            quarter_prices_snt = price_entry.get("quarter_prices_snt", {})
            avg_hour_snt = price_entry.get("hour_avg_snt_kwh", 0.0)

            if quarter is not None and quarter in quarter_prices_snt:
                q_price_snt = quarter_prices_snt[quarter]
                return f"{hour:02d}.{quarter}: {q_price_snt:.2f} snt/kWh (tunnin keskiarvo {avg_hour_snt:.2f})"
            else:
                # Fallback: full-hour average
                return f"{hour:02d}:00 - {avg_hour_snt:.2f} snt/kWh"

        message_parts = []

        # Today's price
        if today_price:
            message_parts.append(
                f"⚡ Tänään {date_str} {format_single(today_price, hour, quarter)}"
            )

        # Tomorrow's price
        if tomorrow_price and tomorrow_available:
            tomorrow_date = (
                datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)
            ).strftime("%Y-%m-%d")
            message_parts.append(
                f"⚡ Huomenna {tomorrow_date} {format_single(tomorrow_price, hour, quarter)}"
            )
        elif price_data.get("include_tomorrow", True) and not tomorrow_available:
            message_parts.append("⚡ Huomisen hintaa ei vielä saatavilla")

        if not message_parts:
            return f"⚡ Sähkön hintatietoja ei saatavilla tunnille {hour:02d}. Lisätietoja: {self.sahko_url}"

        return " | ".join(message_parts)


# ---------- Factory function ----------


def create_electricity_service(api_key: str) -> ElectricityService:
    return ElectricityService(api_key)
