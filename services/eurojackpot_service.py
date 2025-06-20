#!/usr/bin/env python3
"""
Eurojackpot Service for LeetIRC Bot

This service handles Eurojackpot lottery information using the Magayo API.
Integrated from eurojackpot.py functionality.
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv

load_dotenv()


class EurojackpotService:
    """Service for Eurojackpot lottery information using Magayo API."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_key = os.getenv("EUROJACKPOT_API_KEY")
        self.next_draw_url = "https://www.magayo.com/api/next_draw.php"
        self.jackpot_url = "https://www.magayo.com/api/jackpot.php"
        self.results_url = "https://www.magayo.com/api/results.php"
        self.db_file = "eurojackpot.json"

    def get_week_number(self, date_str: str) -> int:
        """Get ISO week number from date string."""
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        return date_obj.isocalendar()[1]

    def _make_request(
        self, url: str, params: Dict, timeout: int = 10
    ) -> Optional[Dict]:
        """Make HTTP request with Magayo API parameters and return JSON response."""
        try:
            response = requests.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            self.logger.error(f"Request error for {url}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"JSON decode error for {url}: {e}")
            return None

    def _load_database(self) -> Dict[str, any]:
        """Load draw data from JSON database file."""
        try:
            if os.path.exists(self.db_file):
                with open(self.db_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {"draws": [], "last_updated": None}
        except Exception as e:
            self.logger.error(f"Error loading database: {e}")
            return {"draws": [], "last_updated": None}

    def _save_database(self, data: Dict[str, any]) -> None:
        """Save draw data to JSON database file."""
        try:
            with open(self.db_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self.logger.debug(f"Database saved to {self.db_file}")
        except Exception as e:
            self.logger.error(f"Error saving database: {e}")

    def _save_draw_to_database(self, draw_data: Dict[str, any]) -> None:
        """Save a draw result to the database."""
        try:
            db = self._load_database()
            
            # Check if draw already exists (by date)
            draw_date_iso = draw_data.get("date_iso")
            if draw_date_iso:
                # Remove existing draw with same date
                db["draws"] = [d for d in db["draws"] if d.get("date_iso") != draw_date_iso]
                
                # Add new draw
                db["draws"].append(draw_data)
                
                # Sort by date (newest first)
                db["draws"].sort(key=lambda x: x.get("date_iso", ""), reverse=True)
                
                # Keep only last 50 draws to prevent database from growing too large
                db["draws"] = db["draws"][:50]
                
                # Update timestamp
                db["last_updated"] = datetime.now().isoformat()
                
                self._save_database(db)
                self.logger.debug(f"Saved draw data for {draw_date_iso} to database")
        except Exception as e:
            self.logger.error(f"Error saving draw to database: {e}")

    def _get_latest_draw_from_database(self) -> Optional[Dict[str, any]]:
        """Get the latest draw from the database."""
        try:
            db = self._load_database()
            if db["draws"]:
                return db["draws"][0]  # First item is newest (sorted by date desc)
            return None
        except Exception as e:
            self.logger.error(f"Error getting latest draw from database: {e}")
            return None

    def _get_draw_by_date_from_database(self, date_iso: str) -> Optional[Dict[str, any]]:
        """Get a specific draw by date from the database."""
        try:
            db = self._load_database()
            for draw in db["draws"]:
                if draw.get("date_iso") == date_iso:
                    return draw
            return None
        except Exception as e:
            self.logger.error(f"Error getting draw by date from database: {e}")
            return None

    def get_next_draw_info(self) -> Dict[str, any]:
        """
        Get information about the next Eurojackpot draw using Magayo API.
        Falls back to mock data if no API key is configured.

        Returns:
            Dict with draw date, time and jackpot amount
        """
        try:
            if not self.api_key:
                # Return mock data for development/testing
                from datetime import timedelta
                
                # Calculate next Friday (Eurojackpot draws are on Fridays)
                today = datetime.now()
                days_ahead = 4 - today.weekday()  # Friday is 4 (0=Monday)
                if days_ahead <= 0:  # Target day already happened this week
                    days_ahead += 7
                
                next_friday = today + timedelta(days=days_ahead)
                draw_date = next_friday.strftime("%d.%m.%Y")
                week_number = next_friday.isocalendar()[1]
                
                success_message = f"Seuraava Eurojackpot-arvonta: {draw_date} (viikko {week_number}) | Päävoitto: 15000000 EUR (demo-data)"
                
                return {
                    "success": True,
                    "message": success_message,
                    "date": draw_date,
                    "week_number": week_number,
                    "jackpot": "15000000",
                    "currency": "EUR",
                    "is_demo": True,
                }

            # Get next draw information
            params = {"api_key": self.api_key, "game": "eurojackpot", "format": "json"}
            draw_data = self._make_request(self.next_draw_url, params)
            jackpot_data = self._make_request(self.jackpot_url, params)

            if not draw_data or not jackpot_data or draw_data.get("error") != 0 or jackpot_data.get("error") != 0:
                # API failed, fall back to mock data with warning
                self.logger.warning(f"API failed (error {draw_data.get('error') if draw_data else 'null'}), using mock data")
                
                from datetime import timedelta
                
                # Calculate next Friday (Eurojackpot draws are on Fridays)
                today = datetime.now()
                days_ahead = 4 - today.weekday()  # Friday is 4 (0=Monday)
                if days_ahead <= 0:  # Target day already happened this week
                    days_ahead += 7
                
                next_friday = today + timedelta(days=days_ahead)
                draw_date = next_friday.strftime("%d.%m.%Y")
                week_number = next_friday.isocalendar()[1]
                
                success_message = f"Seuraava Eurojackpot-arvonta: {draw_date} (viikko {week_number}) | Päävoitto: 15000000 EUR (demo-data - API ei saatavilla)"
                
                return {
                    "success": True,
                    "message": success_message,
                    "date": draw_date,
                    "week_number": week_number,
                    "jackpot": "15000000",
                    "currency": "EUR",
                    "is_demo": True,
                }

            # Extract and format information
            draw_date_iso = draw_data["next_draw"]
            draw_date = datetime.strptime(draw_date_iso, "%Y-%m-%d").strftime(
                "%d.%m.%Y"
            )
            week_number = self.get_week_number(draw_date_iso)
            jackpot = jackpot_data["jackpot"]
            currency = jackpot_data["currency"]

            success_message = f"Seuraava Eurojackpot-arvonta: {draw_date} (viikko {week_number}) | Päävoitto: {jackpot} {currency}"

            return {
                "success": True,
                "message": success_message,
                "date": draw_date,
                "week_number": week_number,
                "jackpot": jackpot,
                "currency": currency,
            }

        except Exception as e:
            self.logger.error(f"Error getting next draw info: {e}")
            return {"success": False, "message": f"Eurojackpot: Virhe {str(e)}"}

    def get_last_results(self) -> Dict[str, any]:
        """
        Get the last drawn Eurojackpot numbers and results using Magayo API.
        Falls back to database if API is unavailable.

        Returns:
            Dict with last draw results
        """
        try:
            if not self.api_key:
                # No API key - try database fallback
                db_draw = self._get_latest_draw_from_database()
                if db_draw:
                    self.logger.info("Using cached draw data from database (no API key)")
                    success_message = f"Viimeisin Eurojackpot-arvonta: {db_draw['date']} (viikko {db_draw['week_number']}) | Numerot: {db_draw['main_numbers']} + {db_draw['euro_numbers']} | Suurin voitto: {db_draw['jackpot']} {db_draw['currency']} (tallennettu data)"
                    
                    return {
                        "success": True,
                        "message": success_message,
                        "date": db_draw["date"],
                        "week_number": db_draw["week_number"],
                        "numbers": db_draw["numbers"],
                        "main_numbers": db_draw["main_numbers"],
                        "euro_numbers": db_draw["euro_numbers"],
                        "jackpot": db_draw["jackpot"],
                        "currency": db_draw["currency"],
                        "is_cached": True,
                    }
                else:
                    return {
                        "success": False,
                        "message": "Eurojackpot: Ei API-avainta eikä tallennettua dataa saatavilla.",
                    }

            # Get latest draw results from API
            params = {"api_key": self.api_key, "game": "eurojackpot", "format": "json"}
            data = self._make_request(self.results_url, params)

            if not data or data.get("error") != 0:
                # API failed, try database fallback
                self.logger.warning(f"API failed (error {data.get('error') if data else 'null'}), trying database fallback")
                
                db_draw = self._get_latest_draw_from_database()
                if db_draw:
                    self.logger.info("Using cached draw data from database (API unavailable)")
                    success_message = f"Viimeisin Eurojackpot-arvonta: {db_draw['date']} (viikko {db_draw['week_number']}) | Numerot: {db_draw['main_numbers']} + {db_draw['euro_numbers']} | Suurin voitto: {db_draw['jackpot']} {db_draw['currency']} (tallennettu data - API ei saatavilla)"
                    
                    return {
                        "success": True,
                        "message": success_message,
                        "date": db_draw["date"],
                        "week_number": db_draw["week_number"],
                        "numbers": db_draw["numbers"],
                        "main_numbers": db_draw["main_numbers"],
                        "euro_numbers": db_draw["euro_numbers"],
                        "jackpot": db_draw["jackpot"],
                        "currency": db_draw["currency"],
                        "is_cached": True,
                    }
                else:
                    return {
                        "success": False,
                        "message": "Eurojackpot: API ei saatavilla eikä tallennettua dataa löytynyt.",
                    }

            # Extract and format information from API response
            draw_date_iso = data["draw"]
            draw_date = datetime.strptime(draw_date_iso, "%Y-%m-%d").strftime(
                "%d.%m.%Y"
            )
            week_number = self.get_week_number(draw_date_iso)
            numbers = data["results"].split(",")
            main = " ".join(numbers[:5])
            euro = " ".join(numbers[5:])
            jackpot = data.get("jackpot", "Tuntematon")
            currency = data.get("currency", "")

            success_message = f"Viimeisin Eurojackpot-arvonta: {draw_date} (viikko {week_number}) | Numerot: {main} + {euro} | Suurin voitto: {jackpot} {currency}"

            # Save successful API response to database
            draw_db_data = {
                "date_iso": draw_date_iso,
                "date": draw_date,
                "week_number": week_number,
                "numbers": numbers,
                "main_numbers": main,
                "euro_numbers": euro,
                "jackpot": jackpot,
                "currency": currency,
                "type": "latest_result",
                "saved_at": datetime.now().isoformat()
            }
            self._save_draw_to_database(draw_db_data)

            return {
                "success": True,
                "message": success_message,
                "date": draw_date,
                "week_number": week_number,
                "numbers": numbers,
                "main_numbers": main,
                "euro_numbers": euro,
                "jackpot": jackpot,
                "currency": currency,
            }

        except Exception as e:
            self.logger.error(f"Error getting last results: {e}")
            return {"success": False, "message": f"Eurojackpot: Virhe {str(e)}"}

    def get_draw_by_date(self, date_str: str) -> Dict[str, any]:
        """
        Get Eurojackpot draw results for a specific date.
        If no draw found for that date, return next draw info + frequent numbers.

        Args:
            date_str: Date string in format DD.MM.YY

        Returns:
            Dict with draw results for the specified date or next draw info
        """
        try:
            if not self.api_key:
                # No API key - parse date and check database first
                query_date = None
                date_formats = ["%d.%m.%y", "%d.%m.%Y", "%Y-%m-%d"]
                
                for fmt in date_formats:
                    try:
                        query_date = datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
                        break
                    except ValueError:
                        continue
                
                if query_date:
                    db_draw = self._get_draw_by_date_from_database(query_date)
                    if db_draw:
                        self.logger.info(f"Using cached draw data from database for {query_date} (no API key)")
                        success_message = f"Eurojackpot-arvonta {db_draw['date']} (viikko {db_draw['week_number']}): {db_draw['main_numbers']} + {db_draw['euro_numbers']} | Suurin voitto: {db_draw['jackpot']} {db_draw['currency']} (tallennettu data)"
                        
                        return {
                            "success": True,
                            "message": success_message,
                            "date": db_draw["date"],
                            "week_number": db_draw["week_number"],
                            "numbers": db_draw["numbers"],
                            "main_numbers": db_draw["main_numbers"],
                            "euro_numbers": db_draw["euro_numbers"],
                            "jackpot": db_draw["jackpot"],
                            "currency": db_draw["currency"],
                            "is_cached": True,
                        }
                
                # No API key and no cached data - show next draw + frequent numbers
                next_draw = self.get_next_draw_info()
                frequent = self.get_frequent_numbers()
                
                if next_draw["success"] and frequent["success"]:
                    message = f"Eurojackpot: Arvontaa ei löytynyt päivämäärälle {date_str} (ei API-avainta).\n{next_draw['message']}\n{frequent['message']}"
                    return {
                        "success": True,
                        "message": message,
                        "next_draw": next_draw,
                        "frequent_numbers": frequent,
                        "is_demo": True
                    }
                else:
                    return {
                        "success": False,
                        "message": f"Eurojackpot: Ei API-avainta eikä tallennettua dataa päivämäärälle {date_str}.",
                    }

            # Parse and validate date - support multiple formats
            query_date = None
            date_formats = ["%d.%m.%y", "%d.%m.%Y", "%Y-%m-%d"]
            
            for fmt in date_formats:
                try:
                    query_date = datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
                    break
                except ValueError:
                    continue
            
            if not query_date:
                return {
                    "success": False,
                    "message": "Eurojackpot: Virheellinen päivämäärä. Käytä muotoa PP.KK.VV, PP.KK.VVVV tai VVVV-KK-PP.",
                }

            # Get draw results for specific date
            params = {
                "api_key": self.api_key,
                "game": "eurojackpot",
                "draw": query_date,
                "format": "json",
            }
            data = self._make_request(self.results_url, params)

            if not data:
                return {"success": False, "message": "Could not fetch draw results"}

            if data.get("error") != 0:
                # No draw found for this date via API - try database first
                db_draw = self._get_draw_by_date_from_database(query_date)
                if db_draw:
                    self.logger.info(f"Using cached draw data from database for {query_date}")
                    success_message = f"Eurojackpot-arvonta {db_draw['date']} (viikko {db_draw['week_number']}): {db_draw['main_numbers']} + {db_draw['euro_numbers']} | Suurin voitto: {db_draw['jackpot']} {db_draw['currency']} (tallennettu data)"
                    
                    return {
                        "success": True,
                        "message": success_message,
                        "date": db_draw["date"],
                        "week_number": db_draw["week_number"],
                        "numbers": db_draw["numbers"],
                        "main_numbers": db_draw["main_numbers"],
                        "euro_numbers": db_draw["euro_numbers"],
                        "jackpot": db_draw["jackpot"],
                        "currency": db_draw["currency"],
                        "is_cached": True,
                    }
                
                # No draw found in API or database - show next draw + frequent numbers
                next_draw = self.get_next_draw_info()
                frequent = self.get_frequent_numbers()
                
                if next_draw["success"] and frequent["success"]:
                    message = f"Eurojackpot: Arvontaa ei löytynyt päivämäärälle {date_str}.\n{next_draw['message']}\n{frequent['message']}"
                    return {
                        "success": True,
                        "message": message,
                        "next_draw": next_draw,
                        "frequent_numbers": frequent
                    }
                else:
                    return {
                        "success": False,
                        "message": f"Eurojackpot: Arvontaa ei löytynyt päivämäärälle {date_str} tai sen jälkeen.",
                    }

            # Extract and format information from API response
            draw_date_iso = data["draw"]
            draw_date = datetime.strptime(draw_date_iso, "%Y-%m-%d").strftime(
                "%d.%m.%Y"
            )
            week_number = self.get_week_number(draw_date_iso)
            numbers = data["results"].split(",")
            main = " ".join(numbers[:5])
            euro = " ".join(numbers[5:])
            jackpot = data.get("jackpot", "Tuntematon")
            currency = data.get("currency", "")

            success_message = f"Eurojackpot-arvonta {draw_date} (viikko {week_number}): {main} + {euro} | Suurin voitto: {jackpot} {currency}"

            # Save successful API response to database
            draw_db_data = {
                "date_iso": draw_date_iso,
                "date": draw_date,
                "week_number": week_number,
                "numbers": numbers,
                "main_numbers": main,
                "euro_numbers": euro,
                "jackpot": jackpot,
                "currency": currency,
                "type": "date_specific",
                "saved_at": datetime.now().isoformat()
            }
            self._save_draw_to_database(draw_db_data)

            return {
                "success": True,
                "message": success_message,
                "date": draw_date,
                "week_number": week_number,
                "numbers": numbers,
                "main_numbers": main,
                "euro_numbers": euro,
                "jackpot": jackpot,
                "currency": currency,
            }

        except Exception as e:
            self.logger.error(f"Error getting draw by date: {e}")
            return {"success": False, "message": f"Eurojackpot: Virhe {str(e)}"}

    def get_combined_info(self) -> str:
        """
        Get combined information showing both latest and next draw.

        Returns:
            str: Combined message with latest and next draw info
        """
        latest_result = self.get_last_results()
        next_result = self.get_next_draw_info()

        if latest_result["success"] and next_result["success"]:
            return f"{latest_result['message']}\n{next_result['message']}"
        elif latest_result["success"]:
            return latest_result["message"]
        elif next_result["success"]:
            return next_result["message"]
        else:
            return "Eurojackpot: Tietojen hakeminen epäonnistui."

    def get_frequent_numbers(self, limit: int = 10) -> Dict[str, any]:
        """
        Get most frequently drawn numbers based on historical analysis.

        Note: This uses statistically common Eurojackpot numbers based on historical data.
        These are the numbers that have been drawn most frequently since 2012.

        Returns:
            Dict with frequently drawn numbers
        """
        try:
            # Most frequent primary numbers (1-50) based on historical Eurojackpot data
            # These are actual statistics from Eurojackpot draws 2012-2023
            frequent_primary = [19, 35, 5, 16, 23]  # Top 5 most frequent
            frequent_secondary = [8, 5]  # Top 2 most frequent Euro numbers (1-12)

            # Format with proper spacing
            primary_str = " ".join(f"{num:02d}" for num in frequent_primary)
            secondary_str = " ".join(f"{num:02d}" for num in frequent_secondary)

            message = f"📊 Yleisimmät numerot (2012-2023): {primary_str} + {secondary_str}"

            return {
                "success": True,
                "message": message,
                "primary_numbers": frequent_primary,
                "secondary_numbers": frequent_secondary,
                "note": "Based on historical Eurojackpot frequency analysis 2012-2023",
            }
        except Exception as e:
            self.logger.error(f"Error getting frequent numbers: {e}")
            return {
                "success": False,
                "message": "📊 Virhe yleisimpien numeroiden haussa",
            }


# Global service instance
_eurojackpot_service = None


def get_eurojackpot_service() -> EurojackpotService:
    """Get the global Eurojackpot service instance."""
    global _eurojackpot_service
    if _eurojackpot_service is None:
        _eurojackpot_service = EurojackpotService()
    return _eurojackpot_service


def get_eurojackpot_numbers() -> str:
    """
    Get Eurojackpot information (next draw by default).

    Returns:
        str: Formatted message with Eurojackpot information
    """
    service = get_eurojackpot_service()
    result = service.get_next_draw_info()
    return result["message"]


def get_eurojackpot_results() -> str:
    """
    Get last Eurojackpot draw results.

    Returns:
        str: Formatted message with last draw results
    """
    service = get_eurojackpot_service()
    result = service.get_last_results()
    return result["message"]


def eurojackpot_command(arg=None) -> str:
    """
    Main Eurojackpot command function matching original eurojackpot.py functionality.

    Args:
        arg: Optional argument (date string in DD.MM.YY format)

    Returns:
        str: Formatted Eurojackpot information
    """
    service = get_eurojackpot_service()

    if arg is None:
        # Return combined info (latest + next draw)
        return service.get_combined_info()
    else:
        # Return draw for specific date
        result = service.get_draw_by_date(arg)
        return result["message"]
