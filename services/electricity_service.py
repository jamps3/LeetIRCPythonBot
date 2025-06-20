"""
Electricity Service Module

Provides Finnish electricity price information using ENTSO-E API.
"""

import requests
import xml.etree.ElementTree as ElementTree
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from io import StringIO


class ElectricityService:
    """Service for fetching Finnish electricity price information."""

    def __init__(self, api_key: str):
        """
        Initialize electricity service.

        Args:
            api_key: ENTSO-E API key
        """
        self.api_key = api_key
        self.base_url = "https://web-api.tp.entsoe.eu/api"
        self.finland_domain = "10YFI-1--------U"
        self.vat_rate = 1.255  # Finnish VAT 25.5%

    def get_electricity_price(
        self,
        hour: Optional[int] = None,
        date: Optional[datetime] = None,
        include_tomorrow: bool = True,
    ) -> Dict[str, Any]:
        """
        Get electricity price information for specific hour and date.

        Args:
            hour: Hour to get price for (0-23). If None, uses current hour
            date: Date to get price for. If None, uses current date
            include_tomorrow: Whether to include tomorrow's price if available

        Returns:
            Dictionary containing price information or error details
        """
        try:
            # Set defaults
            if date is None:
                date = datetime.now()
            if hour is None:
                hour = date.hour

            # Validate hour
            if not (0 <= hour <= 23):
                return {
                    "error": True,
                    "message": f"Invalid hour: {hour}. Must be between 0-23.",
                }

            # Get prices for today
            today_prices = self._fetch_daily_prices(date)
            result = {
                "error": False,
                "date": date.strftime("%Y-%m-%d"),
                "hour": hour,
                "today_price": None,
                "tomorrow_price": None,
                "today_available": not today_prices.get("error", True),
                "tomorrow_available": False,
            }

            # Add today's price if available
            if not today_prices.get("error") and hour + 1 in today_prices["prices"]:
                price_eur_mwh = today_prices["prices"][hour + 1]
                price_snt_kwh = self._convert_price(price_eur_mwh)
                result["today_price"] = {
                    "eur_per_mwh": price_eur_mwh,
                    "snt_per_kwh_with_vat": price_snt_kwh,
                    "snt_per_kwh_no_vat": price_eur_mwh / 10,
                }

            # Get tomorrow's price if requested
            if include_tomorrow:
                tomorrow_date = date + timedelta(days=1)
                tomorrow_prices = self._fetch_daily_prices(tomorrow_date)

                if (
                    not tomorrow_prices.get("error")
                    and hour + 1 in tomorrow_prices["prices"]
                ):
                    price_eur_mwh = tomorrow_prices["prices"][hour + 1]
                    price_snt_kwh = self._convert_price(price_eur_mwh)
                    result["tomorrow_price"] = {
                        "eur_per_mwh": price_eur_mwh,
                        "snt_per_kwh_with_vat": price_snt_kwh,
                        "snt_per_kwh_no_vat": price_eur_mwh / 10,
                    }
                    result["tomorrow_available"] = True

            return result

        except Exception as e:
            return {
                "error": True,
                "message": f"Unexpected error: {str(e)}",
                "exception": str(e),
            }

    def get_daily_prices(self, date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Get all electricity prices for a specific date.

        Args:
            date: Date to get prices for. If None, uses current date

        Returns:
            Dictionary containing daily prices or error details
        """
        if date is None:
            date = datetime.now()

        return self._fetch_daily_prices(date)

    def get_price_statistics(self, date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Get price statistics for a specific date.

        Args:
            date: Date to get statistics for. If None, uses current date

        Returns:
            Dictionary containing price statistics or error details
        """
        try:
            daily_prices = self.get_daily_prices(date)

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
                "date": date.strftime("%Y-%m-%d") if date else None,
                "min_price": {
                    "hour": prices.index(min(prices)),
                    "eur_per_mwh": min(prices),
                    "snt_per_kwh_with_vat": min(prices_snt),
                },
                "max_price": {
                    "hour": prices.index(max(prices)),
                    "eur_per_mwh": max(prices),
                    "snt_per_kwh_with_vat": max(prices_snt),
                },
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

    def _fetch_daily_prices(self, date: datetime) -> Dict[str, Any]:
        """
        Fetch electricity prices for a specific date.

        Args:
            date: Date to fetch prices for

        Returns:
            Dictionary containing daily prices or error details
        """
        try:
            date_str = date.strftime("%Y%m%d")

            url = f"{self.base_url}"
            params = {
                "securityToken": self.api_key,
                "documentType": "A44",  # Price document
                "in_Domain": self.finland_domain,
                "out_Domain": self.finland_domain,
                "periodStart": f"{date_str}0000",
                "periodEnd": f"{date_str}2300",
            }

            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 401:
                return {
                    "error": True,
                    "message": "Invalid ENTSO-E API key",
                    "status_code": 401,
                }
            elif response.status_code != 200:
                return {
                    "error": True,
                    "message": f"ENTSO-E API returned status code {response.status_code}",
                    "status_code": response.status_code,
                }

            # Parse XML response
            try:
                xml_data = ElementTree.parse(StringIO(response.text))
                ns = {"ns": "urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3"}

                prices = {}
                for point in xml_data.findall(".//ns:Point", ns):
                    position = int(point.find("ns:position", ns).text)
                    price = float(point.find("ns:price.amount", ns).text)
                    prices[position] = price

                return {
                    "error": False,
                    "date": date.strftime("%Y-%m-%d"),
                    "prices": prices,
                    "total_hours": len(prices),
                }

            except ElementTree.ParseError as e:
                return {
                    "error": True,
                    "message": f"Failed to parse XML response: {str(e)}",
                    "exception": str(e),
                }

        except requests.exceptions.Timeout:
            return {
                "error": True,
                "message": "ENTSO-E API request timed out",
                "exception": "timeout",
            }
        except requests.exceptions.RequestException as e:
            return {
                "error": True,
                "message": f"ENTSO-E API request failed: {str(e)}",
                "exception": str(e),
            }
        except Exception as e:
            return {
                "error": True,
                "message": f"Unexpected error fetching prices: {str(e)}",
                "exception": str(e),
            }

    def _convert_price(self, eur_per_mwh: float) -> float:
        """
        Convert EUR/MWh to snt/kWh with VAT.

        Args:
            eur_per_mwh: Price in EUR/MWh

        Returns:
            Price in snt/kWh including VAT
        """
        return (eur_per_mwh / 10) * self.vat_rate

    def format_price_message(self, price_data: Dict[str, Any]) -> str:
        """
        Format price data into a readable message.

        Args:
            price_data: Price data dictionary

        Returns:
            Formatted price message string
        """
        if price_data.get("error"):
            return f"⚡ Sähkön hintatietojen haku epäonnistui: {price_data.get('message', 'Tuntematon virhe')}"

        date_str = price_data["date"]
        hour = price_data["hour"]
        today_price = price_data.get("today_price")
        tomorrow_price = price_data.get("tomorrow_price")

        message_parts = []

        if today_price:
            price_snt = today_price["snt_per_kwh_with_vat"]
            message_parts.append(
                f"⚡ Tänään {date_str} klo {hour:02d}: {price_snt:.2f} snt/kWh (ALV 25,5%)"
            )

        if tomorrow_price:
            tomorrow_date = (
                datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)
            ).strftime("%Y-%m-%d")
            price_snt = tomorrow_price["snt_per_kwh_with_vat"]
            message_parts.append(
                f"⚡ Huomenna {tomorrow_date} klo {hour:02d}: {price_snt:.2f} snt/kWh (ALV 25,5%)"
            )

        if not message_parts:
            return f"⚡ Sähkön hintatietoja ei saatavilla tunnille {hour:02d}. https://sahko.tk"

        return " | ".join(message_parts)

    def format_statistics_message(self, stats_data: Dict[str, Any]) -> str:
        """
        Format statistics data into a readable message.

        Args:
            stats_data: Statistics data dictionary

        Returns:
            Formatted statistics message string
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

        return message

    def parse_command_args(self, args: List[str]) -> Dict[str, Any]:
        """
        Parse command arguments for electricity price queries.

        Args:
            args: List of command arguments

        Returns:
            Dictionary containing parsed arguments
        """
        result = {
            "hour": datetime.now().hour,
            "date": datetime.now(),
            "is_tomorrow": False,
            "show_stats": False,
            "error": None,
        }

        if not args:
            return result

        try:
            # Check for special keywords
            if len(args) >= 1:
                if args[0].lower() == "tilastot":
                    result["show_stats"] = True
                    return result
                elif args[0].lower() == "huomenna":
                    result["is_tomorrow"] = True
                    result["date"] += timedelta(days=1)

                    # Check if hour is specified after "huomenna"
                    if len(args) >= 2 and args[1].isdigit():
                        hour = int(args[1])
                        if 0 <= hour <= 23:
                            result["hour"] = hour
                        else:
                            result["error"] = f"Virheellinen tunti: {hour}. Käytä 0-23."
                    return result
                elif args[0].isdigit():
                    # Just hour specified
                    hour = int(args[0])
                    if 0 <= hour <= 23:
                        result["hour"] = hour
                    else:
                        result["error"] = f"Virheellinen tunti: {hour}. Käytä 0-23."
                    return result

            result["error"] = (
                "Virheellinen komento! Käytä: !sahko [huomenna] [tunti] tai !sahko tilastot"
            )

        except ValueError:
            result["error"] = (
                "Virheellinen komento! Käytä: !sahko [huomenna] [tunti] tai !sahko tilastot"
            )

        return result


def create_electricity_service(api_key: str) -> ElectricityService:
    """
    Factory function to create an electricity service instance.

    Args:
        api_key: ENTSO-E API key

    Returns:
        ElectricityService instance
    """
    return ElectricityService(api_key)
