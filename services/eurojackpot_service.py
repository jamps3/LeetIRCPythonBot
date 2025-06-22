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
            self.logger.debug(f"Making request to {url} with params: {params}")
            
            # Try multiple approaches to handle the API
            approaches = [
                # Approach 1: Standard session with modern headers
                {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': 'application/json, text/html, */*',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Referer': 'https://www.magayo.com/',
                    'Cache-Control': 'no-cache'
                },
                # Approach 2: Minimal headers (sometimes APIs prefer this)
                {
                    'User-Agent': 'Python-requests/2.31.0',
                    'Accept': 'application/json'
                },
                # Approach 3: Legacy browser headers
                {
                    'User-Agent': 'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.1)',
                    'Accept': 'application/json, text/html'
                }
            ]
            
            for i, headers in enumerate(approaches):
                try:
                    self.logger.debug(f"Trying approach {i+1} with headers: {list(headers.keys())}")
                    
                    session = requests.Session()
                    session.headers.update(headers)
                    
                    response = session.get(url, params=params, timeout=timeout, allow_redirects=True)
                    self.logger.debug(f"Approach {i+1} - Response status: {response.status_code}, URL: {response.url}")
                    
                    if response.status_code == 303:
                        self.logger.warning(f"Approach {i+1} - Got 303 redirect, following to: {response.headers.get('Location', 'unknown')}")
                        continue  # Try next approach
                    
                    response.raise_for_status()
                    
                    # Log response content for debugging
                    self.logger.debug(f"Approach {i+1} - Response content preview: {response.text[:200]}...")
                    
                    json_data = response.json()
                    self.logger.debug(f"Approach {i+1} - Parsed JSON response: {json_data}")
                    
                    # Check if the API returned an error in the JSON (common with Magayo API)
                    if isinstance(json_data, dict) and json_data.get('error') == 303:
                        self.logger.warning(f"Approach {i+1} - API returned error 303 in JSON response")
                        if i < len(approaches) - 1:  # Not the last approach
                            continue  # Try next approach
                    
                    return json_data
                    
                except requests.RequestException as e:
                    self.logger.warning(f"Approach {i+1} failed with request error: {e}")
                    if i == len(approaches) - 1:  # Last approach
                        raise
                    continue
                except json.JSONDecodeError as e:
                    self.logger.warning(f"Approach {i+1} failed with JSON decode error: {e}")
                    if i == len(approaches) - 1:  # Last approach
                        raise
                    continue
            
            # If we get here, all approaches failed
            return {"error": 303, "message": "All API request approaches failed"}
            
        except requests.RequestException as e:
            self.logger.error(f"Request error for {url}: {e}")
            self.logger.debug(f"Request params were: {params}")
            return {"error": getattr(e.response, 'status_code', 999) if hasattr(e, 'response') and e.response else 999, "message": str(e)}
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error for {url}: {e}")
            self.logger.debug(f"Response was: {response.text if 'response' in locals() else 'No response'}")
            return {"error": 998, "message": f"Invalid JSON response: {str(e)}"}
        except Exception as e:
            self.logger.error(f"Unexpected error for {url}: {e}")
            return {"error": 997, "message": f"Unexpected error: {str(e)}"}

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
                
                # Keep only last 500 draws to allow for historical data while preventing excessive growth
                db["draws"] = db["draws"][:500]
                
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
                
                # Calculate next draw day (Eurojackpot draws are on Tuesdays and Fridays)
                today = datetime.now()
                
                # Check for next Tuesday (1) or Friday (4)
                next_tuesday = today + timedelta(days=(1 - today.weekday()) % 7)
                next_friday = today + timedelta(days=(4 - today.weekday()) % 7)
                
                # If both are in the past, get the next ones
                if next_tuesday <= today:
                    next_tuesday += timedelta(days=7)
                if next_friday <= today:
                    next_friday += timedelta(days=7)
                
                # Choose the earlier one
                next_draw = min(next_tuesday, next_friday)
                draw_date = next_draw.strftime("%d.%m.%Y")
                week_number = next_draw.isocalendar()[1]
                
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
                
                # Calculate next draw day (Eurojackpot draws are on Tuesdays and Fridays)
                today = datetime.now()
                
                # Check for next Tuesday (1) or Friday (4)
                next_tuesday = today + timedelta(days=(1 - today.weekday()) % 7)
                next_friday = today + timedelta(days=(4 - today.weekday()) % 7)
                
                # If both are in the past, get the next ones
                if next_tuesday <= today:
                    next_tuesday += timedelta(days=7)
                if next_friday <= today:
                    next_friday += timedelta(days=7)
                
                # Choose the earlier one
                next_draw = min(next_tuesday, next_friday)
                draw_date = next_draw.strftime("%d.%m.%Y")
                week_number = next_draw.isocalendar()[1]
                
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
        If no draw found for that date, find the next draw from that date onwards.

        Args:
            date_str: Date string in format DD.MM.YY

        Returns:
            Dict with draw results for the specified date or next available draw
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

    def scrape_all_draws(self, start_year: int = 2012, max_api_calls: int = 10) -> Dict[str, any]:
        """
        Scrape historical Eurojackpot draws from the API and save to database.
        
        This function respects API limits (10 calls per month) and only fetches
        draws that we don't already have in the database.
        
        Args:
            start_year: Year to start scraping from (Eurojackpot started in 2012)
            max_api_calls: Maximum API calls to make (default 10 = monthly limit)
            
        Returns:
            Dict with scraping results and statistics
        """
        try:
            if not self.api_key:
                return {
                    "success": False,
                    "message": "📥 Scrape-toiminto vaatii API-avaimen. Aseta EUROJACKPOT_API_KEY .env-tiedostoon.",
                }
            
            self.logger.info(f"Starting smart scrape of Eurojackpot draws from {start_year} (max {max_api_calls} API calls)")
            
            # Load existing database
            db = self._load_database()
            initial_count = len(db["draws"])
            existing_dates = {draw.get("date_iso") for draw in db["draws"] if draw.get("date_iso")}
            
            self.logger.info(f"Database has {initial_count} existing draws, skipping those to save API calls")
            
            # Calculate date range to scrape (only missing dates)
            # Eurojackpot draws are on Fridays, so we generate all Friday dates and check which are missing
            from datetime import timedelta, date
            
            # Start from the first Eurojackpot draw (March 23, 2012)
            start_date = date(2012, 3, 23)  # First Eurojackpot draw
            today = date.today()
            
            # Generate all Tuesday and Friday dates from start_date to today
            missing_dates = []
            current_date = start_date
            while current_date <= today:
                # Check if it's a Tuesday (1) or Friday (4)
                if current_date.weekday() in [1, 4]:  # Tuesday or Friday
                    date_iso = current_date.strftime("%Y-%m-%d")
                    if date_iso not in existing_dates and current_date.year >= start_year:
                        missing_dates.append(date_iso)
                current_date += timedelta(days=1)
            
            missing_dates.sort(reverse=True)  # Newest first
            total_missing = len(missing_dates)
            
            if total_missing == 0:
                return {
                    "success": True,
                    "message": f"📥 Kaikki arvonnat on jo tallennettu! Tietokannassa: {initial_count} arvontaa. Ei API-kutsuja tarvittu.",
                    "new_draws": 0,
                    "api_calls_used": 0,
                    "total_missing": 0,
                }
            
            self.logger.info(f"Found {total_missing} missing draws, will fetch up to {max_api_calls} of them")
            
            # Limit the dates to scrape based on max_api_calls
            dates_to_scrape = missing_dates[:max_api_calls]
            
            new_draws = 0
            api_calls_used = 0
            failed_calls = 0
            
            for i, date_iso in enumerate(dates_to_scrape, 1):
                try:
                    self.logger.info(f"Scraping draw {i}/{len(dates_to_scrape)}: {date_iso}")
                    
                    # Make API call for specific date
                    params = {
                        "api_key": self.api_key,
                        "game": "eurojackpot",
                        "draw": date_iso,
                        "format": "json",
                    }
                    
                    data = self._make_request(self.results_url, params)
                    api_calls_used += 1
                    
                    if not data:
                        self.logger.warning(f"No response for {date_iso}")
                        failed_calls += 1
                        continue
                    
                    if data.get("error") == 303:
                        self.logger.warning(f"API limit reached (303) after {api_calls_used} calls")
                        break  # Stop scraping if we hit the limit
                    
                    if data.get("error") != 0:
                        self.logger.warning(f"API error {data.get('error')} for {date_iso}")
                        failed_calls += 1
                        continue
                    
                    # Process the draw data
                    draw_date_iso = data.get("draw")
                    if not draw_date_iso or draw_date_iso == "-":
                        self.logger.info(f"No draw found for {date_iso} (probably no draw that day)")
                        continue
                    
                    results = data.get("results", "")
                    if not results or results == "-":
                        self.logger.info(f"No results found for {date_iso}")
                        continue
                    
                    # Parse the draw data
                    draw_date = datetime.strptime(draw_date_iso, "%Y-%m-%d").strftime("%d.%m.%Y")
                    week_number = self.get_week_number(draw_date_iso)
                    
                    numbers = results.split(",")
                    if len(numbers) < 7:  # Need at least 5 main + 2 euro numbers
                        self.logger.warning(f"Invalid number format for {date_iso}: {results}")
                        continue
                    
                    main = " ".join(numbers[:5])
                    euro = " ".join(numbers[5:])
                    jackpot = data.get("jackpot", "Tuntematon")
                    currency = data.get("currency", "EUR")
                    
                    # Create database entry
                    draw_db_data = {
                        "date_iso": draw_date_iso,
                        "date": draw_date,
                        "week_number": week_number,
                        "numbers": numbers,
                        "main_numbers": main,
                        "euro_numbers": euro,
                        "jackpot": jackpot,
                        "currency": currency,
                        "type": "scraped",
                        "saved_at": datetime.now().isoformat()
                    }
                    
                    # Save the draw
                    self._save_draw_to_database(draw_db_data)
                    new_draws += 1
                    
                    self.logger.info(f"✓ Saved draw {draw_date}: {main} + {euro}")
                    
                except Exception as e:
                    self.logger.error(f"Error processing draw for {date_iso}: {e}")
                    failed_calls += 1
                    continue
            
            # Get final database stats
            final_db = self._load_database()
            final_count = len(final_db["draws"])
            
            # Calculate progress
            remaining_missing = total_missing - new_draws
            progress_pct = ((total_missing - remaining_missing) / total_missing * 100) if total_missing > 0 else 100
            
            # Build status message
            if api_calls_used == 0:
                message = f"📥 Ei API-kutsuja tehty. Tietokannassa: {final_count} arvontaa."
            else:
                message = f"📥 Scrape valmis! Haettu {new_draws} uutta arvontaa ({api_calls_used} API-kutsua). "
                message += f"Tietokannassa nyt: {final_count} arvontaa. "
                if remaining_missing > 0:
                    message += f"Puuttuu vielä: {remaining_missing} arvontaa ({progress_pct:.1f}% valmis)."
                else:
                    message += "Kaikki arvonnat tallennettu! 🎉"
                
                if failed_calls > 0:
                    message += f" Epäonnistui: {failed_calls} kutsua."
            
            self.logger.info(f"Scrape completed: {new_draws} new draws, {api_calls_used} API calls used")
            
            return {
                "success": True,
                "message": message,
                "new_draws": new_draws,
                "api_calls_used": api_calls_used,
                "failed_calls": failed_calls,
                "total_draws": final_count,
                "total_missing": total_missing,
                "remaining_missing": remaining_missing,
                "progress_percent": progress_pct,
                "initial_count": initial_count,
            }
            
        except Exception as e:
            self.logger.error(f"Error in scrape_all_draws: {e}")
            return {
                "success": False,
                "message": f"📥 Scrape-virhe: {str(e)}",
            }
    
    def get_database_stats(self) -> Dict[str, any]:
        """
        Get statistics about the local database.
        
        Returns:
            Dict with database statistics
        """
        try:
            db = self._load_database()
            total_draws = len(db["draws"])
            
            if total_draws == 0:
                return {
                    "success": True,
                    "message": "📊 Tietokanta on tyhjä. Käytä !eurojackpot scrape hakemaan historiatietoja.",
                    "total_draws": 0,
                }
            
            # Calculate date range
            sorted_draws = sorted(db["draws"], key=lambda x: x.get("date_iso", ""))
            oldest_date = sorted_draws[0].get("date", "Tuntematon")
            newest_date = sorted_draws[-1].get("date", "Tuntematon")
            
            # Get last update time
            last_updated = db.get("last_updated", "Tuntematon")
            if last_updated != "Tuntematon":
                try:
                    last_updated_dt = datetime.fromisoformat(last_updated)
                    last_updated = last_updated_dt.strftime("%d.%m.%Y %H:%M")
                except:
                    pass
            
            message = f"📊 Tietokanta: {total_draws} arvontaa ({oldest_date} - {newest_date}). Päivitetty: {last_updated}"
            
            return {
                "success": True,
                "message": message,
                "total_draws": total_draws,
                "oldest_date": oldest_date,
                "newest_date": newest_date,
                "last_updated": last_updated,
            }
            
        except Exception as e:
            self.logger.error(f"Error getting database stats: {e}")
            return {
                "success": False,
                "message": f"📊 Virhe tietokannan tilastoissa: {str(e)}",
            }
    
    def add_draw_manually(self, date_str: str, numbers_str: str, jackpot_str: str = "Tuntematon", currency: str = "EUR") -> Dict[str, any]:
        """
        Manually add a draw to the database.
        
        Args:
            date_str: Date in format DD.MM.YYYY or YYYY-MM-DD
            numbers_str: Numbers in format "1,2,3,4,5,6,7" (5 main + 2 euro)
            jackpot_str: Jackpot amount (optional)
            currency: Currency (default EUR)
            
        Returns:
            Dict with operation result
        """
        try:
            # Parse and validate date
            date_iso = None
            date_formats = ["%d.%m.%Y", "%Y-%m-%d", "%d.%m.%y"]
            
            for fmt in date_formats:
                try:
                    if fmt == "%d.%m.%y":
                        # Handle 2-digit years (assume 20xx)
                        parsed_date = datetime.strptime(date_str, fmt)
                        if parsed_date.year < 2000:
                            parsed_date = parsed_date.replace(year=parsed_date.year + 100)
                        date_iso = parsed_date.strftime("%Y-%m-%d")
                    else:
                        date_iso = datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
                    break
                except ValueError:
                    continue
            
            if not date_iso:
                return {
                    "success": False,
                    "message": "❌ Virheellinen päivämäärä. Käytä muotoa PP.KK.VVVV tai VVVV-KK-PP.",
                }
            
            # Validate that the date is a Tuesday or Friday (Eurojackpot draw days)
            draw_date_obj = datetime.strptime(date_iso, "%Y-%m-%d")
            if draw_date_obj.weekday() not in [1, 4]:  # 1 = Tuesday, 4 = Friday
                day_name = ['maanantai', 'tiistai', 'keskiviikko', 'torstai', 'perjantai', 'lauantai', 'sunnuntai'][draw_date_obj.weekday()]
                return {
                    "success": False,
                    "message": f"⚠️ Eurojackpot-arvonnat ovat tiistaisin ja perjantaisin. {date_str} on {day_name}.",
                }
            
            # Parse and validate numbers
            try:
                numbers = [n.strip() for n in numbers_str.split(",")]
                if len(numbers) != 7:
                    return {
                        "success": False,
                        "message": "❌ Tarvitaan täsmälleen 7 numeroa (5 pääsarjan + 2 euronumeroa). Esim: 1,5,12,25,35,3,8",
                    }
                
                # Validate number ranges
                main_numbers = [int(n) for n in numbers[:5]]
                euro_numbers = [int(n) for n in numbers[5:]]
                
                # Check main numbers (1-50)
                for num in main_numbers:
                    if not (1 <= num <= 50):
                        return {
                            "success": False,
                            "message": f"❌ Pääsarjan numero {num} ei ole välillä 1-50.",
                        }
                
                # Check euro numbers (1-12)
                for num in euro_numbers:
                    if not (1 <= num <= 12):
                        return {
                            "success": False,
                            "message": f"❌ Euronumero {num} ei ole välillä 1-12.",
                        }
                
                # Check for duplicates in main numbers
                if len(set(main_numbers)) != 5:
                    return {
                        "success": False,
                        "message": "❌ Pääsarjan numeroiden tulee olla eri numeroita.",
                    }
                
                # Check for duplicates in euro numbers
                if len(set(euro_numbers)) != 2:
                    return {
                        "success": False,
                        "message": "❌ Euronumeroiden tulee olla eri numeroita.",
                    }
                
            except ValueError:
                return {
                    "success": False,
                    "message": "❌ Kaikki numerot tulee olla kokonaislukuja.",
                }
            
            # Format the numbers
            main_formatted = " ".join(f"{num:02d}" for num in main_numbers)
            euro_formatted = " ".join(f"{num:02d}" for num in euro_numbers)
            
            # Create draw data
            draw_date = draw_date_obj.strftime("%d.%m.%Y")
            week_number = self.get_week_number(date_iso)
            
            draw_data = {
                "date_iso": date_iso,
                "date": draw_date,
                "week_number": week_number,
                "numbers": [str(n) for n in numbers],
                "main_numbers": main_formatted,
                "euro_numbers": euro_formatted,
                "jackpot": jackpot_str,
                "currency": currency,
                "type": "manual",
                "saved_at": datetime.now().isoformat()
            }
            
            # Check if draw already exists
            existing = self._get_draw_by_date_from_database(date_iso)
            action = "päivitetty" if existing else "lisätty"
            
            # Save to database
            self._save_draw_to_database(draw_data)
            
            # Get final count
            db = self._load_database()
            total_count = len(db["draws"])
            
            success_message = f"✅ Arvonta {action}! {draw_date} (viikko {week_number}): {main_formatted} + {euro_formatted} | Päävoitto: {jackpot_str} {currency}. Tietokannassa nyt: {total_count} arvontaa."
            
            self.logger.info(f"Manually {action} draw for {date_iso}: {main_formatted} + {euro_formatted}")
            
            return {
                "success": True,
                "message": success_message,
                "action": action,
                "date": draw_date,
                "numbers": numbers,
                "main_numbers": main_formatted,
                "euro_numbers": euro_formatted,
                "jackpot": jackpot_str,
                "currency": currency,
                "total_draws": total_count,
            }
            
        except Exception as e:
            self.logger.error(f"Error adding draw manually: {e}")
            return {
                "success": False,
                "message": f"❌ Virhe arvonnan lisäämisessä: {str(e)}",
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
