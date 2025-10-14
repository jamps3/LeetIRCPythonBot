"""
Electricity Service Module 2.1
Provides Finnish electricity price information using ENTSO-E API.
Supports caching, fetching prices for specific hours, 15-minute intervals, and statistics.
"""

import xml.etree.ElementTree as ElementTree
from datetime import datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from io import StringIO
from typing import Any, Dict, List, Optional, Tuple

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
                if q_prices:
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
                    if q_prices:
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

        # Check cache
        cached = self._cache.get(date_key)
        if cached and now - cached["timestamp"] < self._cache_ttl:
            log(
                f"Using cached data for {date_key}",
                level="DEBUG",
                context="ELECTRICITY",
            )
            return cached["data"]

        try:
            local_start = self.timezone.localize(datetime.combine(date, time(0, 0)))
            utc_start = local_start.astimezone(pytz.utc)
            period_start = utc_start.strftime("%Y%m%d%H%M")

            local_end = local_start + timedelta(days=1)
            utc_end = local_end.astimezone(pytz.utc)
            period_end = utc_end.strftime("%Y%m%d%H%M")

            log(
                f"Fetching electricity prices for {date_key}: {period_start} to {period_end} UTC",
                level="INFO",
                context="ELECTRICITY",
            )

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

            interval_prices: Dict[tuple[int, int], float] = {}

            timeseries = tree.findall(".//ns:TimeSeries", ns)
            for ts in timeseries:
                period = ts.find("ns:Period", ns)
                if period is None:
                    continue
                ti = period.find("ns:timeInterval", ns)
                start_str = ti.find("ns:start", ns).text
                res = period.find("ns:resolution", ns).text

                if res == "PT15M":
                    res_min = 15
                elif res == "PT60M":
                    res_min = 60
                else:
                    continue  # Unsupported

                start_time = datetime.strptime(start_str, "%Y-%m-%dT%H:%MZ").replace(
                    tzinfo=pytz.utc
                )

                for point in period.findall("ns:Point", ns):
                    pos = int(point.find("ns:position", ns).text)
                    price = float(point.find("ns:price.amount", ns).text)
                    minutes_offset = (pos - 1) * res_min
                    interval_utc = start_time + timedelta(minutes=minutes_offset)
                    interval_local = interval_utc.astimezone(self.timezone)
                    hour = interval_local.hour
                    minute = interval_local.minute
                    quarter = (minute // 15) + 1
                    interval_prices[(hour, quarter)] = price

            # If resolution is 60M, duplicate price for all quarters in the hour
            if res == "PT60M":
                for (h, q), price in list(interval_prices.items()):
                    if q == 1:  # Only set for quarter 1 in hourly
                        for extra_q in [2, 3, 4]:
                            interval_prices[(h, extra_q)] = price

            # Debug print all interval_prices
            # for (h, q), price in interval_prices.items():
            #     log(f"Interval: hour={h}, quarter={q}, price={price}")

            result = {
                "error": False,
                "date": date_key,
                "interval_prices": interval_prices,
            }

            self._cache[date_key] = {"timestamp": now, "data": result}
            return result

        except Exception as e:
            return {"error": True, "message": f"Failed to fetch daily prices: {str(e)}"}

    # ---------- Helpers ----------

    def clear_cache(self) -> None:
        """Clear the price cache."""
        self._cache.clear()
        log("Cleared electricity price cache", level="INFO", context="ELECTRICITY")

    def get_cache_info(self) -> Dict[str, Any]:
        """Get information about cached data."""
        now = datetime.now(self.timezone)
        cache_info = {}

        for date_key, cached_data in self._cache.items():
            age = now - cached_data["timestamp"]
            cache_info[date_key] = {
                "age_minutes": int(age.total_seconds() / 60),
                "is_expired": age > self._cache_ttl,
                "timestamp": cached_data["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
            }

        return cache_info

    def diagnose_timezone_handling(self, date: datetime) -> Dict[str, Any]:
        """Diagnostic function to debug timezone handling issues."""
        if isinstance(date, datetime):
            date = date.date()

        # Helsinki timezone info
        local_start = self.timezone.localize(datetime.combine(date, time(0, 0)))
        utc_start = local_start.astimezone(pytz.utc)
        local_end = local_start + timedelta(days=1)
        utc_end = local_end.astimezone(pytz.utc)

        return {
            "requested_date": date.strftime("%Y-%m-%d"),
            "helsinki_start": local_start.strftime("%Y-%m-%d %H:%M:%S %Z%z"),
            "utc_start": utc_start.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "helsinki_end": local_end.strftime("%Y-%m-%d %H:%M:%S %Z%z"),
            "utc_end": utc_end.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "api_period_start": utc_start.strftime("%Y%m%d%H%M"),
            "api_period_end": utc_end.strftime("%Y%m%d%H%M"),
            "timezone_offset": str(local_start.utcoffset()),
        }

    def _convert_price(self, eur_per_mwh: float) -> float:
        eur = Decimal(str(eur_per_mwh))
        snt = (eur / Decimal("10")) * Decimal(str(self.vat_rate))
        return float(snt.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    def parse_command_args(self, args: List[str]) -> Dict[str, Any]:
        """Parse !sahko commands (tänään/huomenna/hour.quarter/stats)."""
        now = datetime.now(self.timezone)
        result = {
            "hour": now.hour,
            "quarter": (now.minute // 15) + 1,
            "date": now.date(),
            "is_tomorrow": False,
            "show_stats": False,
            "show_all_hours": False,
            "error": None,
        }  # Return date object

        if not args:
            return result

        try:
            # Check for special keywords
            if len(args) >= 1:
                arg = args[0].lower()
                if arg in ["tilastot", "stats"]:
                    result["show_stats"] = True
                    return result
                elif arg in ["tänään", "tanaan", "today"]:
                    # Show all hours for today (accept multiple variations)
                    result["show_all_hours"] = True
                    result["is_tomorrow"] = False
                    return result
                elif arg in ["huomenna", "tomorrow"]:
                    result["is_tomorrow"] = True
                    result["date"] = (now + timedelta(days=1)).date()

                    # Check if hour is specified after "huomenna"
                    if len(args) >= 2:
                        try:
                            result["hour"], result["quarter"] = (
                                self._parse_hour_quarter(args[1])
                            )
                        except ValueError:
                            result["error"] = (
                                f"Virheellinen arvo: {args[1]}. Käytä muotoa HH tai HH.1–HH.4"
                            )
                    else:
                        # Show all hours for tomorrow
                        result["show_all_hours"] = True
                    return result
                elif arg.replace(".", "").replace("-", "").isdigit() or "." in arg:
                    # Hour or hour.quarter specified
                    try:
                        result["hour"], result["quarter"] = self._parse_hour_quarter(
                            arg
                        )
                    except ValueError:
                        result["error"] = (
                            f"Virheellinen arvo: {arg}. Käytä muotoa HH tai HH.1–HH.4"
                        )
                    return result
                else:
                    result["error"] = (
                        "Virheellinen komento! Käytä: !sahko [tänään|huomenna] [tunti] tai !sahko tilastot/stats"
                    )

        except Exception as e:
            result["error"] = (
                "Virheellinen komento! Käytä: !sahko [tänään|huomenna] [tunti] tai !sahko tilastot/stats"
            )

        return result

    def _parse_hour_quarter(self, arg: str) -> tuple[int, int]:
        """Parse '13' or '13.2' → hour, quarter."""
        try:
            if "." in arg:
                h_str, q_str = arg.split(".")
                h, q = int(h_str), int(q_str)
                if not (0 <= h <= 23) or not (1 <= q <= 4):
                    raise ValueError(
                        f"Hour must be 0-23 and quarter must be 1-4, got {h}.{q}"
                    )
                return h, q
            else:
                h = int(arg)
                if not (0 <= h <= 23):
                    raise ValueError(f"Hour must be 0-23, got {h}")
                return h, 1
        except (ValueError, IndexError) as e:
            if "invalid literal" in str(e):
                raise ValueError(f"Invalid number format: {arg}")
            else:
                raise

    def get_price_statistics(self, date: datetime) -> Dict[str, Any]:
        """
        Get price statistics for a specific date.

        Args:
            date: Date to get statistics for

        Returns:
            Dictionary containing price statistics or error details
        """
        try:
            if isinstance(date, datetime):
                date = date.date()

            daily_prices = self.get_daily_prices(date)

            if daily_prices.get("error"):
                return daily_prices

            interval_prices = daily_prices.get("interval_prices", {})
            if not interval_prices:
                return {
                    "error": True,
                    "message": "No price data available for statistics",
                }

            # Convert to snt/kWh with VAT for statistics
            prices_snt = []
            hour_prices = {}  # hour -> list of quarter prices

            for (hour, quarter), eur_mwh in interval_prices.items():
                price_snt = self._convert_price(eur_mwh)
                prices_snt.append(price_snt)

                if hour not in hour_prices:
                    hour_prices[hour] = []
                hour_prices[hour].append(price_snt)

            # Calculate hourly averages for min/max hour determination
            hourly_averages = {}
            for hour, quarter_prices in hour_prices.items():
                hourly_averages[hour] = sum(quarter_prices) / len(quarter_prices)

            if not prices_snt:
                return {
                    "error": True,
                    "message": "No price data available for statistics",
                }

            min_hour = min(hourly_averages.keys(), key=lambda h: hourly_averages[h])
            max_hour = max(hourly_averages.keys(), key=lambda h: hourly_averages[h])

            return {
                "error": False,
                "date": date.strftime("%Y-%m-%d"),
                "min_price": {
                    "hour": min_hour,
                    "snt_per_kwh_with_vat": hourly_averages[min_hour],
                },
                "max_price": {
                    "hour": max_hour,
                    "snt_per_kwh_with_vat": hourly_averages[max_hour],
                },
                "avg_price": {
                    "snt_per_kwh_with_vat": sum(prices_snt) / len(prices_snt),
                },
                "total_intervals": len(prices_snt),
                "total_hours": len(hourly_averages),
            }

        except Exception as e:
            return {
                "error": True,
                "message": f"Error calculating statistics: {str(e)}",
            }

    def _create_price_bar_graph(
        self, interval_prices: Dict[Tuple[int, int], float], avg_price_snt: float
    ) -> str:
        """
        Create a colorful bar graph showing 15-minute interval prices relative to average.

        Args:
            interval_prices: Dictionary of (hour, quarter) -> price in EUR/MWh
            avg_price_snt: Average price in snt/kWh with VAT

        Returns:
            String representation of the bar graph
        """
        # Define bar symbols for different heights (low to high)
        bar_symbols = ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]

        # IRC color codes: 3=green, 7=orange/yellow, 4=red
        green = "\x033"  # Below average (good price)
        yellow = "\x037"  # At average
        red = "\x034"  # Above average (expensive)
        reset = "\x03"  # Reset color

        # Convert prices to snt/kWh and create time-price pairs
        time_prices = []
        for hour in range(24):
            for quarter in range(1, 5):
                if (hour, quarter) in interval_prices:
                    price_eur_mwh = interval_prices[(hour, quarter)]
                    price_snt_kwh = self._convert_price(price_eur_mwh)
                    time_prices.append((hour, quarter, price_snt_kwh))

        if not time_prices:
            return "No data"

        # Find min/max for bar height scaling
        all_prices = [price for _, _, price in time_prices]
        min_price = min(all_prices)
        max_price = max(all_prices)
        price_range = max_price - min_price if max_price > min_price else 1

        # Create bar graph - one bar per hour (showing hourly average)
        hourly_bars = []
        current_hour = -1
        hour_prices = []

        for hour, quarter, price in time_prices:
            if hour != current_hour:
                # Process previous hour if we have data
                if current_hour >= 0 and hour_prices:
                    avg_hour_price = sum(hour_prices) / len(hour_prices)

                    # Calculate bar height (0-7 index into bar_symbols)
                    if price_range > 0:
                        height_ratio = (avg_hour_price - min_price) / price_range
                        bar_height = min(7, int(height_ratio * 8))
                    else:
                        bar_height = 4  # Middle height if all prices are same

                    # Choose color based on comparison to average
                    if abs(avg_hour_price - avg_price_snt) < 0.01:  # Essentially equal
                        color = yellow
                    elif avg_hour_price < avg_price_snt:
                        color = green  # Below average = good = green
                    else:
                        color = red  # Above average = expensive = red

                    # Create colored bar
                    bar = f"{color}{bar_symbols[bar_height]}{reset}"
                    hourly_bars.append(bar)

                # Start new hour
                current_hour = hour
                hour_prices = [price]
            else:
                hour_prices.append(price)

        # Process the last hour
        if hour_prices:
            avg_hour_price = sum(hour_prices) / len(hour_prices)

            if price_range > 0:
                height_ratio = (avg_hour_price - min_price) / price_range
                bar_height = min(7, int(height_ratio * 8))
            else:
                bar_height = 4

            if abs(avg_hour_price - avg_price_snt) < 0.01:
                color = yellow
            elif avg_hour_price < avg_price_snt:
                color = green
            else:
                color = red

            bar = f"{color}{bar_symbols[bar_height]}{reset}"
            hourly_bars.append(bar)

        return "".join(hourly_bars)

    def format_statistics_message(self, stats_data: Dict[str, Any]) -> str:
        """
        Format statistics data into a readable message with bar graph.

        Args:
            stats_data: Statistics data dictionary

        Returns:
            Formatted statistics message string with colorful bar graph
        """
        if stats_data.get("error"):
            return f"📊 Sähkön tilastojen haku epäonnistui: {stats_data.get('message', 'Tuntematon virhe')}"

        date_str = stats_data["date"]
        min_price = stats_data["min_price"]
        max_price = stats_data["max_price"]
        avg_price = stats_data["avg_price"]

        message = (
            f"📊 Sähkön hintatilastot {date_str}: "
            f"🔹 Min: {min_price['snt_per_kwh_with_vat']:.2f} snt/kWh (klo {min_price['hour']:02d}) "
            f"🔸 Max: {max_price['snt_per_kwh_with_vat']:.2f} snt/kWh (klo {max_price['hour']:02d}) "
            f"🔹 Keskiarvo: {avg_price['snt_per_kwh_with_vat']:.2f} snt/kWh"
        )

        # Add bar graph if daily prices available
        try:
            from datetime import datetime

            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            daily_prices = self.get_daily_prices(date_obj)

            if not daily_prices.get("error") and daily_prices.get("interval_prices"):
                bar_graph = self._create_price_bar_graph(
                    daily_prices["interval_prices"], avg_price["snt_per_kwh_with_vat"]
                )
                message += f" | {bar_graph}"
        except Exception as e:
            log(
                f"Error adding bar graph to stats: {e}",
                level="WARNING",
                context="ELECTRICITY",
            )

        return message

    def format_price_message(self, price_data: Dict[str, Any]) -> str:
        """
        Format electricity price data into a readable message with 15-minute interval support.
        Safely handles missing quarter data.
        """
        if price_data.get("error"):
            return f" Sähkön hintatietojen haku epäonnistui: {price_data.get('message', 'Tuntematon virhe')}"

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
                f" Tänään {date_str} {format_single(today_price, hour, quarter)}"
            )

        # Tomorrow's price
        if tomorrow_price and tomorrow_available:
            tomorrow_date = (
                datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)
            ).strftime("%Y-%m-%d")
            message_parts.append(
                f" Huomenna {tomorrow_date} {format_single(tomorrow_price, hour, quarter)}"
            )
        elif price_data.get("include_tomorrow", True) and not tomorrow_available:
            message_parts.append(" Huomisen hintaa ei vielä saatavilla")

        if not message_parts:
            return f" Sähkön hintatietoja ei saatavilla tunnille {hour:02d}. Lisätietoja: {self.sahko_url}"

        return " | ".join(message_parts)


# ---------- Factory function ----------
def create_electricity_service(api_key: str) -> ElectricityService:
    return ElectricityService(api_key)
