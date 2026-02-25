#!/usr/bin/env python3
"""
Eurojackpot scraper using Playwright for JS-based scraping from Veikkaus.fi

This script scrapes the latest Eurojackpot draw results from the Veikkaus website
using a headless browser to execute JavaScript and render the page.
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, Optional

from playwright.sync_api import sync_playwright

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# URLs to try
EUROJACKPOT_OFFICIAL_URL = "https://www.eurojackpot.com/"
EUROJACKPOT_URL = EUROJACKPOT_OFFICIAL_URL  # Use official Eurojackpot website


class EurojackpotScraper:
    """Scraper for Eurojackpot draw results from Veikkaus.fi"""

    def __init__(self):
        self.url = EUROJACKPOT_URL

    def scrape_draw_results(self, start_date: str = "2022-03-25") -> list:
        """
        Scrape Eurojackpot draw results from start_date until now by making direct API calls.

        Args:
            start_date: Start date in YYYY-MM-DD format (default: 2022-03-25, week 12)

        Returns:
            List of draw data dictionaries
        """
        try:
            import requests

            logger.info(
                f"Starting Eurojackpot scrape using direct API calls, collecting draws from {start_date}"
            )

            # Generate all Eurojackpot draw dates (Tuesdays and Fridays) from start_date to now
            draw_dates = self._generate_draw_dates(start_date)
            logger.info(f"Generated {len(draw_dates)} potential draw dates to check")

            all_draws = []
            base_url = "https://www.eurojackpot.com/wlinfo/WL_InfoService"

            for i, draw_date in enumerate(draw_dates):
                if i % 2 == 0:  # Progress logging every 2 draws
                    logger.info(f"Processing draw {i+1}/{len(draw_dates)}: {draw_date}")

                try:
                    # Try different parameter combinations to get historical data
                    param_combinations = [
                        {
                            "client": "jsn",
                            "gruppe": "ZahlenUndQuoten",
                            "ewGewsum": "ja",
                            "spielart": "EJ",
                            "adg": "ja",
                            "lang": "en",
                            "historie": "ja",
                            "datum": draw_date,
                        },
                        {
                            "client": "jsn",
                            "gruppe": "ZahlenUndQuoten",
                            "ewGewsum": "ja",
                            "spielart": "EJ",
                            "adg": "ja",
                            "lang": "en",
                            "historie": "ja",
                        },
                    ]

                    draw_found = False
                    for params in param_combinations:
                        try:
                            response = requests.get(
                                base_url,
                                params=params,
                                timeout=10,
                                headers={
                                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                                },
                            )

                            if response.status_code == 200:
                                try:
                                    data = response.json()
                                    draws = self._parse_historical_api_response(data)
                                    if draws:
                                        # Filter draws for this specific date
                                        for draw in draws:
                                            if draw.get("date_iso") == draw_date:
                                                all_draws.append(draw)
                                                draw_found = True
                                                logger.debug(
                                                    f"Found draw for {draw_date}: {draw['main_numbers']} + {draw['euro_numbers']}"
                                                )
                                                break
                                        if draw_found:
                                            break
                                except json.JSONDecodeError:
                                    continue
                        except requests.RequestException:
                            continue

                    if not draw_found:
                        logger.debug(f"No draw data found for {draw_date}")

                except Exception as e:
                    logger.warning(f"Error processing draw {draw_date}: {e}")
                    continue

            logger.info(
                f"Successfully scraped {len(all_draws)} draws out of {len(draw_dates)} possible dates"
            )
            return all_draws

        except Exception as e:
            logger.error(f"Error during scraping: {e}")
            return []

    def _generate_draw_dates(self, start_date: str) -> list:
        """
        Generate all Eurojackpot draw dates (Tuesdays and Fridays) from start_date to now.

        Args:
            start_date: Start date in YYYY-MM-DD format

        Returns:
            List of date strings in YYYY-MM-DD format
        """
        try:
            from datetime import date, timedelta

            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            today = date.today()

            draw_dates = []
            current = start

            while current <= today:
                # Eurojackpot draws on Tuesdays (1) and Fridays (4)
                if current.weekday() in [1, 4]:  # Tuesday=1, Friday=4
                    draw_dates.append(current.strftime("%Y-%m-%d"))
                current += timedelta(days=1)

            return draw_dates

        except Exception as e:
            logger.error(f"Error generating draw dates: {e}")
            return []

    def _extract_draw_data(self, page) -> Optional[Dict]:
        """
        Extract draw data from the page using various selectors.

        Args:
            page: Playwright page object

        Returns:
            Dict with extracted draw data or None
        """
        try:
            # Method 1: Look for structured data in JSON-LD or data attributes
            structured_data = page.evaluate(
                """
                () => {
                    // Look for JSON-LD structured data
                    const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                    for (let script of scripts) {
                        try {
                            const data = JSON.parse(script.textContent);
                            if (data['@type'] === 'Event' || data.name?.includes('Eurojackpot')) {
                                return data;
                            }
                        } catch (e) {}
                    }

                    // Look for global JavaScript variables
                    if (window.__INITIAL_STATE__ || window.__NEXT_DATA__) {
                        return window.__INITIAL_STATE__ || window.__NEXT_DATA__;
                    }

                    return null;
                }
            """
            )

            if structured_data:
                logger.info("Found structured data")
                return self._parse_structured_data(structured_data)

            # Method 2: Look for visible draw results in the DOM
            logger.info("Looking for draw results in DOM...")

            # Try to find numbers in various formats
            # Look for elements with winning numbers
            numbers_text = page.locator(
                "text=/\\d+\\s+\\d+\\s+\\d+\\s+\\d+\\s+\\d+/"
            ).first
            if numbers_text.is_visible():
                numbers_match = numbers_text.text_content().strip()
                logger.info(f"Found numbers text: {numbers_match}")
                # Parse numbers here
                return self._parse_numbers_text(numbers_match)

            # Method 3: Look for modal or popup with results
            modal_content = page.locator("[role='dialog'], .modal, .popup").first
            if modal_content.is_visible():
                modal_text = modal_content.text_content()
                logger.info(f"Found modal content: {modal_text[:200]}...")
                return self._parse_modal_text(modal_text)

            # Method 4: Look for any text containing Eurojackpot results
            result_elements = page.locator(
                "text=/Eurojackpot.*tulokset|Viimeisin.*arvonta|arvottu/i"
            ).all()
            for elem in result_elements:
                if elem.is_visible():
                    result_text = elem.text_content()
                    logger.info(f"Found result text: {result_text}")
                    return self._parse_result_text(result_text)

            # Method 5: Screenshot for debugging
            logger.info("Taking screenshot for debugging...")
            page.screenshot(path="eurojackpot_debug.png")
            logger.info("Screenshot saved as eurojackpot_debug.png")

            logger.warning("No draw data found on page")
            return None

        except Exception as e:
            logger.error(f"Error extracting draw data: {e}")
            return None

    def _parse_structured_data(self, data: Dict) -> Optional[Dict]:
        """Parse structured data from JSON-LD or page data"""
        try:
            # This would depend on the actual structure found
            # For now, return a basic structure
            return {
                "source": "structured_data",
                "raw_data": data,
                "parsed": False,  # Would need specific parsing logic
            }
        except Exception as e:
            logger.error(f"Error parsing structured data: {e}")
            return None

    def _parse_numbers_text(self, text: str) -> Optional[Dict]:
        """Parse numbers from text like '1 5 12 25 35 + 3 8'"""
        try:
            import re

            # Look for pattern like "X X X X X + X X"
            pattern = r"(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*\+\s*(\d+)\s+(\d+)"
            match = re.search(pattern, text)

            if match:
                main_numbers = [int(match.group(i)) for i in range(1, 6)]
                euro_numbers = [int(match.group(i)) for i in range(6, 8)]

                return {
                    "main_numbers": main_numbers,
                    "euro_numbers": euro_numbers,
                    "date": datetime.now().strftime(
                        "%d.%m.%Y"
                    ),  # Would need to extract actual date
                    "source": "numbers_text",
                    "raw_text": text,
                }

            return None
        except Exception as e:
            logger.error(f"Error parsing numbers text: {e}")
            return None

    def _parse_modal_text(self, text: str) -> Optional[Dict]:
        """Parse draw data from modal text"""
        try:
            # Look for numbers and date in modal content
            return {
                "source": "modal_text",
                "raw_text": text,
                "parsed": False,  # Would need specific parsing
            }
        except Exception as e:
            logger.error(f"Error parsing modal text: {e}")
            return None

    def _parse_historical_api_response(self, data: Dict) -> list:
        """Parse the WL_InfoService API response for historical draws"""
        try:
            if not data or data.get("error"):
                logger.warning(
                    f"API returned error: {data.get('error') if data else 'No data'}"
                )
                return []

            draws = []

            # Check if this is historical data (multiple draws) or single draw
            head = data.get("head", {})
            zahlen = data.get("zahlen", {})

            # For now, assume we get the latest draw. In the future, we might need to
            # modify this to parse multiple historical draws if the API supports it
            if zahlen and isinstance(zahlen, dict) and "hauptlotterie" in zahlen:
                hauptlotterie = zahlen["hauptlotterie"]
                if isinstance(hauptlotterie, dict) and "ziehungen" in hauptlotterie:
                    ziehungen = hauptlotterie["ziehungen"]
                    if isinstance(ziehungen, list) and len(ziehungen) >= 2:
                        # Extract draw date
                        draw_date_iso = head.get("datum")
                        if draw_date_iso:
                            try:
                                draw_date_obj = datetime.strptime(
                                    draw_date_iso, "%Y-%m-%d"
                                )
                                draw_date = draw_date_obj.strftime("%d.%m.%Y")
                                week_number = draw_date_obj.isocalendar()[1]
                            except ValueError:
                                draw_date = draw_date_iso
                                week_number = 1
                        else:
                            draw_date = datetime.now().strftime("%d.%m.%Y")
                            week_number = datetime.now().isocalendar()[1]

                        # Extract numbers
                        main_numbers = []
                        euro_numbers = []

                        # First entry should be "5 of 50" (main numbers)
                        main_entry = ziehungen[0]
                        if (
                            isinstance(main_entry, dict)
                            and main_entry.get("bezeichnung") == "5 of 50"
                            and "zahlen" in main_entry
                        ):
                            main_numbers = [int(n) for n in main_entry["zahlen"]]

                        # Second entry should be "2 of 12" (euro numbers)
                        euro_entry = ziehungen[1]
                        if (
                            isinstance(euro_entry, dict)
                            and euro_entry.get("bezeichnung") == "2 of 12"
                            and "zahlen" in euro_entry
                        ):
                            euro_numbers = [int(n) for n in euro_entry["zahlen"]]

                        if main_numbers and euro_numbers:
                            # Extract jackpot if available
                            jackpot = None
                            gewinnklassen = data.get("gewinnklassen", [])
                            if gewinnklassen and len(gewinnklassen) > 0:
                                first_tier = gewinnklassen[0]
                                if (
                                    isinstance(first_tier, dict)
                                    and "gewinn" in first_tier
                                ):
                                    jackpot = first_tier["gewinn"]

                            draw_data = {
                                "main_numbers": main_numbers,
                                "euro_numbers": euro_numbers,
                                "date": draw_date,
                                "date_iso": draw_date_iso,
                                "week_number": week_number,
                                "jackpot": jackpot,
                                "source": "api_wl_infoservice",
                                "spielart": head.get("spielart"),
                                "spielformel": head.get("spielformel"),
                            }
                            draws.append(draw_data)

            logger.info(f"Parsed {len(draws)} draws from API response")
            return draws

        except Exception as e:
            logger.error(f"Error parsing historical API response: {e}")
            return []

    def _parse_api_response(self, data: Dict) -> Optional[Dict]:
        """Parse the WL_InfoService API response (single draw)"""
        draws = self._parse_historical_api_response(data)
        return draws[0] if draws else None

    def _parse_result_text(self, text: str) -> Optional[Dict]:
        """Parse general result text"""
        try:
            return {
                "source": "result_text",
                "raw_text": text,
                "parsed": False,  # Would need specific parsing
            }
        except Exception as e:
            logger.error(f"Error parsing result text: {e}")
            return None


def load_database(filename: str = "eurojackpot.json") -> Dict:
    """Load existing database from JSON file"""
    try:
        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"draws": [], "last_updated": None}
    except Exception as e:
        logger.error(f"Error loading database: {e}")
        return {"draws": [], "last_updated": None}


def save_draw_to_database(draw_data: Dict, filename: str = "eurojackpot.json"):
    """Save a draw result to the database (compatible with eurojackpot_service.py)"""
    try:
        # Load existing database
        db = load_database(filename)

        # Check if draw already exists (by date)
        draw_date_iso = draw_data.get("date_iso")
        if draw_date_iso:
            # Remove existing draw with same date
            db["draws"] = [d for d in db["draws"] if d.get("date_iso") != draw_date_iso]

            # Add new draw
            db["draws"].append(draw_data)

            # Sort by date (newest first)
            db["draws"].sort(key=lambda x: x.get("date_iso", ""), reverse=True)

            # Keep only last 500 draws to prevent excessive growth
            db["draws"] = db["draws"][:500]

            # Update timestamp
            db["last_updated"] = datetime.now().isoformat()

            # Save database
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(db, f, indent=2, ensure_ascii=False)

            logger.info(f"Saved draw data for {draw_date_iso} to {filename}")
            return True
        else:
            logger.error("Draw data missing date_iso field")
            return False

    except Exception as e:
        logger.error(f"Error saving draw to database: {e}")
        return False


def main():
    """Main function to run the scraper"""
    scraper = EurojackpotScraper()
    results = scraper.scrape_draw_results(start_date="2022-03-25")

    if results and len(results) > 0:
        print(f"Scraping successful! Found {len(results)} draws")

        # Save to the shared eurojackpot.json database (in project root)
        import os

        root_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        db_path = os.path.join(root_dir, "eurojackpot.json")

        saved_count = 0
        for result in results:
            # Convert scraped data to database format
            db_draw_data = {
                "date_iso": result.get("date_iso"),
                "date": result.get("date"),
                "week_number": result.get("week_number", 1),  # Calculate if missing
                "numbers": [str(n) for n in result.get("main_numbers", [])]
                + [str(n) for n in result.get("euro_numbers", [])],
                "main_numbers": " ".join(
                    f"{n:02d}" for n in result.get("main_numbers", [])
                ),
                "euro_numbers": " ".join(
                    f"{n:02d}" for n in result.get("euro_numbers", [])
                ),
                "jackpot": result.get("jackpot"),
                "currency": "EUR",  # Default currency
                "type": "scraped",
                "saved_at": datetime.now().isoformat(),
            }

            # Calculate week number if missing
            if not db_draw_data.get("week_number") or db_draw_data["week_number"] == 1:
                try:
                    draw_date = datetime.strptime(db_draw_data["date_iso"], "%Y-%m-%d")
                    db_draw_data["week_number"] = draw_date.isocalendar()[1]
                except:
                    pass

            # Save this draw to database
            success = save_draw_to_database(db_draw_data, db_path)
            if success:
                saved_count += 1
            else:
                logger.warning(f"Failed to save draw for {result.get('date_iso')}")

        print(f"Successfully saved {saved_count} draws to eurojackpot.json database")
        return 0
    else:
        print("Scraping failed - no draws found!")
        return 1


if __name__ == "__main__":
    exit(main())
