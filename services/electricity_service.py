"""
Electricity Service Module 2.0

Provides Finnish electricity price information using ENTSO-E API.
Supports caching, fetching prices for specific hours(average), 15-minute intervals and statistics.
"""

import xml.etree.ElementTree as ElementTree
from datetime import datetime, timedelta
from io import StringIO
from typing import Any, Dict, List, Optional

import pytz
import requests

from logger import log


class ElectricityService:
    """Service for fetching Finnish electricity price information."""

    def __init__(self, api_key: str, cache_ttl_hours: int = 3):
        """
        Initialize electricity service.

        Args:
            api_key: ENTSO-E API key
            cache_ttl_hours: How long to cache daily price results (in hours)
        """
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
        Get electricity price information for a given hour or 15-minute interval and date.
        If quarter is given (1-4), return that 15-min interval and the hourly average.
        If only hour is given, return the hourly average computed from quarter intervals.

        Args:
            hour: int (optional) Hour to get price for (0-23). If None, uses current hour
            quarter: int (optional) 15-min interval (1-4) within the hour. If None, returns hourly average
            date: (optional) Date to get price for. If None, uses current date

        Returns a dict with:
            - date: YYYY-MM-DD
            - hour: int
            - quarter: int (optional)
            - today_price: dict with quarter_prices & hourly avg
            - tomorrow_price: same structure for tomorrow if available
            - include_tomorrow: bool
            - tomorrow_available: bool
        """
        try:
            # Set defaults
            if date is None:
                date = datetime.now(self.timezone).date()
            if hour is None:
                hour = date.hour
            else:  # Validate hour
                if not (0 <= hour <= 23):
                    return {
                        "error": True,
                        "message": f"Invalid hour: {hour}. Must be between 0-23.",
                    }

            log("[DEBUG] Fetching...")  # <-- debug here

            data = self._fetch_daily_prices(date)
            if data.get("error"):
                return data

            # API data may contain 15-min intervals, e.g., "00:00", "00:15", ...
            prices = data["prices"]
            log(f"[DEBUG] Fetched daily prices for {date}: {prices}")  # <-- debug here
            hourly_prices = {}

            # Group 15-minute prices into hourly averages
            for h in range(24):
                quarter_prices = {}
                for q in range(4):
                    key = f"{h:02d}:{q*15:02d}"
                    if key in prices:
                        quarter_prices[q + 1] = prices[key]  # 1-4
                if quarter_prices:
                    hourly_prices[h] = {
                        "avg_hour_price": sum(quarter_prices.values())
                        / len(quarter_prices),
                        "quarter_prices": quarter_prices,
                    }
                else:
                    hourly_prices[h] = {
                        "avg_hour_price": None,
                        "quarter_prices": {},
                    }

            # Prepare today's price
            today_price = hourly_prices.get(hour)
            if not today_price or today_price["avg_hour_price"] is None:
                return {"error": True, "message": f"No price data for hour {hour}."}

            result = {
                "date": date.strftime("%Y-%m-%d"),
                "hour": hour,
                "quarter": quarter,
                "today_price": today_price,
                "include_tomorrow": True,
            }

            # Include specific quarter price if requested
            if quarter is not None:
                if quarter < 1 or quarter > 4:
                    return {"error": True, "message": "Quarter must be 1-4."}
                if quarter not in today_price["quarter_prices"]:
                    return {
                        "error": True,
                        "message": f"No data for {hour:02d}:{(quarter-1)*15:02d}.",
                    }

            # Fetch tomorrow's data if available
            tomorrow_date = date + timedelta(days=1)
            tomorrow_data = self._fetch_daily_prices(tomorrow_date)
            if not tomorrow_data.get("error"):
                tomorrow_prices = tomorrow_data["prices"]
                hourly_prices_tomorrow = {}
                for h in range(24):
                    quarter_prices = {}
                    for q in range(4):
                        key = f"{h:02d}:{q*15:02d}"
                        if key in tomorrow_prices:
                            quarter_prices[q + 1] = tomorrow_prices[key]
                    if quarter_prices:
                        hourly_prices_tomorrow[h] = {
                            "avg_hour_price": sum(quarter_prices.values())
                            / len(quarter_prices),
                            "quarter_prices": quarter_prices,
                        }
                    else:
                        hourly_prices_tomorrow[h] = {
                            "avg_hour_price": None,
                            "quarter_prices": {},
                        }
                result["tomorrow_price"] = hourly_prices_tomorrow.get(hour)
                result["tomorrow_available"] = (
                    result["tomorrow_price"] is not None
                    and result["tomorrow_price"]["avg_hour_price"] is not None
                )
            else:
                result["tomorrow_price"] = None
                result["tomorrow_available"] = False

            # Convert prices to snt/kWh for today and tomorrow
            def convert_prices(p):
                if not p:
                    return None
                return {
                    "avg_hour_price": p["avg_hour_price"],
                    "hour_avg_snt_kwh": (
                        self._convert_price(p["avg_hour_price"])
                        if p["avg_hour_price"]
                        else None
                    ),
                    "quarter_prices": {
                        q: self._convert_price(v)
                        for q, v in p["quarter_prices"].items()
                    },
                }

            result["today_price"] = convert_prices(result["today_price"])
            if result.get("tomorrow_price"):
                result["tomorrow_price"] = convert_prices(result["tomorrow_price"])

            return result

        except Exception as e:
            return {
                "error": True,
                "message": f"Unexpected error: {str(e)}",
                "exception": str(e),
            }

    def _parse_hour_quarter(self, hour_arg: str) -> tuple[int, int]:
        """
        Parse an hour or 15-min interval argument.

        Examples:
            "13"   -> (13, 0)
            "13.2" -> (13, 2)

        Returns:
            Tuple of (hour, quarter)
        """
        try:
            if "." in hour_arg:
                hour_str, quarter_str = hour_arg.split(".")
                hour = int(hour_str)
                quarter = int(quarter_str)
                if not (0 <= hour <= 23 and 1 <= quarter <= 4):
                    raise ValueError
                return hour, quarter
            else:
                hour = int(hour_arg)
                if not (0 <= hour <= 23):
                    raise ValueError
                return hour, 0
        except Exception:
            raise ValueError(
                "Virheellinen tunti- tai neljännestuntiargumentti. Käytä 0-23 tai 0-23.1-4."
            )

    def get_price_statistics(self, date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Get price statistics for a specific date (min, max, average).

        Args:
            date: Date to get statistics for. If None, uses current date

        Returns:
            Dictionary containing price statistics or error details
        """
        try:
            daily_prices = self._fetch_daily_prices(date)

            if daily_prices.get("error"):
                return daily_prices

            prices = list(daily_prices["prices"].values())

            if not prices:
                return {
                    "error": True,
                    "message": "No price data available for statistics",
                }

            # Convert to snt/kWh with VAT for statistics
            prices_snt = [self._convert_price(p) for p in prices]

            return {
                "error": False,
                "date": daily_prices["date"],
                "min_price": self._stat_entry(prices, prices_snt, min),
                "max_price": self._stat_entry(prices, prices_snt, max),
                "avg_price": {
                    "eur_per_mwh": sum(prices) / len(prices),
                    "snt_per_kwh_with_vat": sum(prices_snt) / len(prices_snt),
                },
                "total_hours": len(prices),
            }

        except Exception as e:
            return {
                "error": True,
                "message": f"Error calculating statistics: {str(e)}",
                "exception": str(e),
            }

    # ---------- Internal helpers ----------

    def _fetch_daily_prices(self, date: datetime) -> Dict[str, Any]:
        """
        Fetch daily electricity prices for a specific date.
        Supports caching and namespace auto-detection.

        The ENTSO-E API returns data in periods that align with local time zones.
        For Finnish electricity prices:
        - Position 1 = 00:00-01:00 Finnish time (hour 0)
        - Position 2 = 01:00-02:00 Finnish time (hour 1)
        - ...
        - Position 24 = 23:00-24:00 Finnish time (hour 23)

        But for hour 0 specifically, position 24 from the PREVIOUS day contains
        the price for midnight (00:00) of the requested date.

        Args:
            date: Date to fetch prices for (in Finnish time)

        Returns:
            Dictionary containing daily prices or error details
        """
        date_key = date.strftime("%Y-%m-%d")
        now = datetime.now()

        log(f"[DEBUG] Fetching daily prices for {date_key}...")  # <-- debug here

        # Cache lookup
        cached = self._cache.get(date_key)
        if cached and now - cached["timestamp"] < self._cache_ttl:
            return cached["data"]

        log("[DEBUG] Not using cache...")  # <-- debug here

        # Fetch from API
        try:
            period_start = date.strftime("%Y%m%d") + "0000"
            period_end = (date + timedelta(days=1)).strftime(
                "%Y%m%d"
            ) + "0000"  # FIXED: include next midnight
            params = {
                "securityToken": self.api_key,
                "documentType": "A44",
                "in_Domain": self.finland_domain,
                "out_Domain": self.finland_domain,
                "periodStart": period_start,
                "periodEnd": period_end,
            }

            response = requests.get(self.base_url, params=params, timeout=30)
            if response.status_code == 401:
                return {"error": True, "message": "Invalid API key", "status": 401}
            if response.status_code != 200:
                return {
                    "error": True,
                    "message": f"HTTP {response.status_code}",
                    "status": response.status_code,
                }

            # Parse XML safely
            tree = ElementTree.parse(StringIO(response.text))
            root = tree.getroot()
            ns = {"ns": root.tag.split("}")[0].strip("{")}  # Auto namespace

            prices = {}
            for p in tree.findall(".//ns:Point", ns):
                pos = int(p.find("ns:position", ns).text)
                price = float(p.find("ns:price.amount", ns).text)
                prices[pos] = price

            result = {
                "error": False,
                "date": date_key,
                "prices": prices,
                "total_hours": len(prices),
            }

            # Detect if data is 15-minute intervals (96 points)
            interval_prices = {}
            if len(prices) > 24:
                for pos, price in prices.items():
                    hour = (pos - 1) // 4
                    quarter = ((pos - 1) % 4) + 1
                    interval_prices[(hour, quarter)] = price

            result["interval_prices"] = interval_prices if interval_prices else None

            # Cache it
            self._cache[date_key] = {"timestamp": now, "data": result}
            log(f"[DEBUG] Fetched daily prices for {date}: {result}")  # <-- debug here
            return result

        except ElementTree.ParseError:
            return {"error": True, "message": "Invalid XML response"}
        except requests.Timeout:
            return {"error": True, "message": "Request timed out"}
        except requests.RequestException as e:
            return {"error": True, "message": f"Request failed: {e}"}
        except Exception as e:
            return {"error": True, "message": f"Unexpected: {e}"}

    def _convert_price(self, eur_per_mwh: float) -> float:
        """
        Convert EUR/MWh to snt/kWh (VAT included).

        Args:
            eur_per_mwh: Price in EUR/MWh

        Returns:
            Price in snt/kWh including VAT
        """
        return (eur_per_mwh / 10) * self.vat_rate

    def _price_dict(self, eur_per_mwh: float) -> Dict[str, float]:
        """Create a standard price dict."""
        return {
            "eur_per_mwh": eur_per_mwh,
            "snt_per_kwh_with_vat": self._convert_price(eur_per_mwh),
            "snt_per_kwh_no_vat": eur_per_mwh / 10,
        }

    def _stat_entry(
        self, prices: List[float], snt_prices: List[float], func
    ) -> Dict[str, float]:
        """Helper for statistics."""
        val = func(prices)
        idx = prices.index(val)
        return {
            "hour": idx,
            "eur_per_mwh": val,
            "snt_per_kwh_with_vat": snt_prices[idx],
        }

    def _create_price_bar_graph(
        self, prices: Dict[int, float], avg_price_snt: float
    ) -> str:
        """
        Create a colorful bar graph showing hourly prices relative to average.

        Args:
            prices: Dictionary of position -> price in EUR/MWh
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

        # Convert prices to snt/kWh and create hour-price pairs
        hour_prices = []
        for position in range(1, 25):  # Positions 1-24 (hours 1-23 and 0)
            if position in prices:
                hour = position if position != 24 else 0
                price_eur_mwh = prices[position]
                price_snt_kwh = self._convert_price(price_eur_mwh)
                hour_prices.append((hour, price_snt_kwh))

        if not hour_prices:
            return "No data"

        # Sort by hour
        hour_prices.sort(key=lambda x: x[0])

        # Find min/max for bar height scaling
        all_prices = [price for _, price in hour_prices]
        min_price = min(all_prices)
        max_price = max(all_prices)
        price_range = max_price - min_price if max_price > min_price else 1

        # Create bar graph
        bars = []
        for hour, price in hour_prices:
            # Calculate bar height (0-7 index into bar_symbols)
            if price_range > 0:
                height_ratio = (price - min_price) / price_range
                bar_height = min(7, int(height_ratio * 8))
            else:
                bar_height = 4  # Middle height if all prices are same

            # Choose color based on comparison to average
            if abs(price - avg_price_snt) < 0.01:  # Essentially equal (within 0.01 snt)
                color = yellow
            elif price < avg_price_snt:
                color = green  # Below average = good = green
            else:
                color = red  # Above average = expensive = red

            # Create colored bar
            bar = f"{color}{bar_symbols[bar_height]}{reset}"
            bars.append(bar)

        return "".join(bars)

    def format_price_message(self, price_data: Dict[str, Any]) -> str:
        """
        Format price data into a readable message with 15-minute support.

        Args:
            price_data: Price data dictionary

        Returns:
            Formatted price message string
        """
        if price_data.get("error"):
            return f"⚡ Sähkön hintatietojen haku epäonnistui: {price_data.get('message', 'Tuntematon virhe')}"

        date_str = price_data["date"]
        hour = price_data["hour"]
        quarter = price_data.get("quarter", 0)
        today_price = price_data.get("today_price")
        tomorrow_price = price_data.get("tomorrow_price")
        tomorrow_available = price_data.get("tomorrow_available", False)

        def format_single(price_entry):
            """Format either full-hour or specific 15-minute interval."""
            avg_hour = price_entry.get("avg_hour_price", price_entry["eur_per_mwh"])
            quarter_prices = price_entry.get("quarter_prices", {})
            if quarter in (1, 2, 3, 4) and quarter_prices.get(quarter) is not None:
                q_price = quarter_prices[quarter]
                return f"{hour:02d}.{quarter}: {self._convert_price(q_price):.2f} snt/kWh (tunnin keskiarvo {self._convert_price(avg_hour):.2f})"
            # fallback: full-hour
            return f"{hour:02d}:00 - {self._convert_price(avg_hour):.2f} snt/kWh"

        message_parts = []

        if today_price:
            message_parts.append(f"⚡ Tänään {date_str} {format_single(today_price)}")

        if tomorrow_price and tomorrow_available:
            tomorrow_date = (
                datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)
            ).strftime("%Y-%m-%d")
            message_parts.append(
                f"⚡ Huomenna {tomorrow_date} {format_single(tomorrow_price)}"
            )
        elif price_data.get("include_tomorrow", True) and not tomorrow_available:
            message_parts.append("⚡ Huomisen hintaa ei vielä saatavilla")

        if not message_parts:
            return f"⚡ Sähkön hintatietoja ei saatavilla tunnille {hour:02d}. {self.sahko_url}"

        return " | ".join(message_parts)

    def format_daily_prices_message(
        self, price_list: list, is_tomorrow: bool = False
    ) -> str:
        """
        Format daily price data into a readable message showing all hours or 15-minute intervals.

        Args:
            price_list: List of hourly/quarter price dictionaries from get_electricity_price
            is_tomorrow: Whether the prices are for tomorrow

        Returns:
            Formatted daily prices message string
        """
        day_text = "huomenna" if is_tomorrow else "tänään"
        if not price_list:
            return f"⚡ Sähkön hintatietoja ei saatavilla {day_text}, {self.sahko_url}"

        # Get date from first item or fallback
        first_date = price_list[0].get("date")
        if not first_date:
            from datetime import datetime, timedelta

            dt = datetime.now()
            if is_tomorrow:
                dt += timedelta(days=1)
            first_date = dt.strftime("%Y-%m-%d")

        day_text = "Huomenna" if is_tomorrow else "Tänään"
        messages = []

        for price_data in price_list:
            # Handle errors for individual hours
            if price_data.get("error"):
                hour = price_data.get("hour", "?")
                messages.append(
                    f"{hour:02d}: ⚠ {price_data.get('message', 'Ei tietoja')}"
                )
                continue

            hour = price_data["hour"]
            quarter = price_data.get("quarter")
            price_snt = price_data.get("price_snt_kwh")
            hour_avg = price_data.get("hour_avg_snt_kwh")

            if quarter in (1, 2, 3, 4):
                messages.append(
                    f"{hour:02d}.{quarter}: {price_snt:.2f} snt/kWh (ALV 25,5%)"
                    f"(tunnin keskiarvo {hour_avg:.2f})"
                )
            else:
                messages.append(f"{hour:02d}:00 - {price_snt:.2f} snt/kWh")

        return f"⚡ {day_text} {first_date}: " + " | ".join(messages)

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

        # Get daily prices to create bar graph
        daily_prices = self._fetch_daily_prices(
            datetime.strptime(date_str, "%Y-%m-%d") if date_str else None
        )

        message = (
            f"📊 Sähkön hintatilastot {date_str}: "
            f"🔹 Min: {min_price['snt_per_kwh_with_vat']:.2f} snt/kWh (klo {min_price['hour']:02d}) "
            f"🔸 Max: {max_price['snt_per_kwh_with_vat']:.2f} snt/kWh (klo {max_price['hour']:02d}) "
            f"🔹 Keskiarvo: {avg_price['snt_per_kwh_with_vat']:.2f} snt/kWh"
        )

        # Add bar graph if daily prices available
        if not daily_prices.get("error") and daily_prices.get("prices"):
            bar_graph = self._create_price_bar_graph(
                daily_prices["prices"], avg_price["snt_per_kwh_with_vat"]
            )
            message += f" | {bar_graph}"

        return message

    def parse_command_args(self, args: List[str]) -> Dict[str, Any]:
        """
        Parse command arguments for electricity price queries, including 15-minute intervals.

        Args:
            args: List of command arguments

        Returns:
            Dictionary containing parsed arguments, including optional 'quarter'
        """
        now = datetime.now()
        result = {
            "hour": now.hour,
            "quarter": 0,  # 0 means full hour; 1-4 are 15-min intervals
            "date": now,
            "is_tomorrow": False,
            "show_stats": False,
            "show_all_hours": False,
            "error": None,
        }

        if not args:
            return result

        try:
            first_arg = args[0].lower()

            # ----- Special keywords -----
            if first_arg in ["tilastot", "stats"]:
                result["show_stats"] = True
                return result
            elif first_arg in ["tänään", "tanaan", "today"]:
                # Show all hours for today
                result["show_all_hours"] = True
                result["is_tomorrow"] = False
                # Check if hour or hour.quarter is specified next
                if len(args) >= 2:
                    hour, quarter = self._parse_hour_quarter(args[1])
                    result["hour"] = hour
                    result["quarter"] = quarter
                    result["show_all_hours"] = False
                return result
            elif first_arg in ["huomenna", "tomorrow"]:
                result["is_tomorrow"] = True
                result["date"] += timedelta(days=1)
                # Check if hour or hour.quarter is specified next
                if len(args) >= 2:
                    hour, quarter = self._parse_hour_quarter(args[1])
                    result["hour"] = hour
                    result["quarter"] = quarter
                    result["show_all_hours"] = False
                else:
                    # Show all hours for tomorrow
                    result["show_all_hours"] = True
                return result

            # ----- Hour or hour.quarter directly -----
            hour, quarter = self._parse_hour_quarter(args[0])
            result["hour"] = hour
            result["quarter"] = quarter
            return result

        except ValueError as e:
            result["error"] = (
                f"Virheellinen komento: {e}. Käytä: !sahko [tänään|huomenna] [tunti] tai !sahko tilastot/stats"
            )

        return result


def format_price_report(
    service: ElectricityService, date: Optional[datetime] = None
) -> str:
    """Generate a formatted daily price report with 15-minute interval support."""
    data = service._fetch_daily_prices(date)
    if data.get("error"):
        return f"Error: {data['message']}"

    stats = service.get_price_statistics(date)
    report_lines = [f"Sähkön hinnat {data['date']}:"]

    # Handle 15-minute intervals if available
    interval_prices = data.get("interval_prices")
    if interval_prices:
        report_lines.append("(15 minuutin keskihinnat)")
        for hour in range(24):
            hour_prices = [
                interval_prices.get((hour, q))
                for q in range(1, 5)
                if interval_prices.get((hour, q)) is not None
            ]
            if not hour_prices:
                continue
            avg_hour_price = sum(hour_prices) / len(hour_prices)
            formatted_intervals = ", ".join(
                f"{hour:02d}.{q}: {service._convert_price(interval_prices[(hour, q)]):.2f} snt/kWh"
                for q in range(1, 5)
                if (hour, q) in interval_prices
            )
            report_lines.append(
                f"{hour:02d}:00 ({service._convert_price(avg_hour_price):.2f} snt/kWh avg) - {formatted_intervals}"
            )
    else:
        # Fallback to hourly prices only
        for hour, price in sorted(data["prices"].items()):
            report_lines.append(
                f"{hour:02d}:00 - {service._convert_price(price):.2f} snt/kWh ({price:.2f} €/MWh)"
            )

    if not stats.get("error"):
        report_lines.append("")
        report_lines.append(
            f"Minimi: {stats['min_price']['snt_per_kwh_with_vat']:.2f} snt/kWh klo {stats['min_price']['hour']:02d}:00"
        )
        report_lines.append(
            f"Maksimi: {stats['max_price']['snt_per_kwh_with_vat']:.2f} snt/kWh klo {stats['max_price']['hour']:02d}:00"
        )
        report_lines.append(
            f"Keskihinta: {stats['avg_price']['snt_per_kwh_with_vat']:.2f} snt/kWh"
        )

    return "\n".join(report_lines)


def parse_15min_command(hour_arg: str) -> tuple[int, int]:
    """Parse hour or 15-min interval syntax (e.g. 13 or 13.2)."""
    try:
        if "." in hour_arg:
            hour_str, quarter_str = hour_arg.split(".")
            hour = int(hour_str)
            quarter = int(quarter_str)
            if not (0 <= hour <= 23 and 1 <= quarter <= 4):
                raise ValueError
            return hour, quarter
        else:
            hour = int(hour_arg)
            if not (0 <= hour <= 23):
                raise ValueError
            return hour, 0
    except ValueError:
        raise ValueError(
            "Virheellinen tunti- tai neljännestuntiargumentti. Käytä 0-23 tai 0-23.1-4."
        )


def create_electricity_service(api_key: str) -> ElectricityService:
    """
    Factory function to create an electricity service instance.

    Args:
        api_key: ENTSO-E API key

    Returns:
        ElectricityService instance
    """
    return ElectricityService(api_key)
