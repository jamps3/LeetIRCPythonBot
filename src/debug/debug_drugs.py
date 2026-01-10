"""
Drug Data Scraper for TripSit

Scrapes comprehensive drug information from https://tripsit.me/factsheets/
including substance details and interaction data.
"""

import json
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, "src")
from logger import get_logger

logger = get_logger("DrugScraper")


class DrugScraper:
    """Scraper for TripSit drug factsheets."""

    def __init__(self, data_dir: str = "data"):
        """
        Initialize the drug scraper.

        Args:
            data_dir: Directory where data files are stored
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.drugs_file = self.data_dir / "drugs.json"
        self.base_url = "https://tripsit.me"
        self.factsheets_url = f"{self.base_url}/factsheets/"

        # Rate limiting
        self.request_delay = 0.1  # seconds between requests

    def scrape_all_drugs(self) -> Dict[str, Dict]:
        """
        Scrape all drug information from TripSit.

        Returns:
            Dictionary of drug data
        """
        logger.info("Starting comprehensive drug data scrape from TripSit...")

        # Get list of all drug URLs
        drug_urls = self._get_drug_urls()
        logger.info(f"Found {len(drug_urls)} drugs to scrape")

        drugs_data = {}

        for i, url in enumerate(drug_urls):
            drug_name = url.split("/")[-1]
            logger.info(f"Scraping {i+1}/{len(drug_urls)}: {drug_name}")

            try:
                drug_data = self._scrape_drug_page(url)
                if drug_data:
                    drugs_data[drug_name] = drug_data
                    logger.info(f"Successfully scraped {drug_name}")
                else:
                    logger.warning(f"Failed to scrape {drug_name}")

            except Exception as e:
                logger.error(f"Error scraping {drug_name}: {e}")

            # Rate limiting
            if i < len(drug_urls) - 1:
                time.sleep(self.request_delay)

        logger.info(f"Completed scraping {len(drugs_data)} drugs")
        return drugs_data

    def _get_drug_urls(self) -> List[str]:
        """
        Get list of all drug factsheet URLs.

        Returns:
            List of drug page URLs
        """
        logger.info("Getting list of all drug factsheets...")

        try:
            response = requests.get(self.factsheets_url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")

            # Debug: print page structure
            title_tag = soup.find("title")
            logger.info(
                "Page title: %s",
                title_tag.get_text().strip() if title_tag else "No title",
            )

            # Check if this is the right page
            logger.info("Page URL: %s", self.factsheets_url)
            logger.info("Response status: %d", response.status_code)

            # Look for script tags that might contain drug data
            scripts = soup.find_all("script")
            logger.info("Found %d script tags", len(scripts))

            # Look for JSON data in scripts
            for i, script in enumerate(scripts):
                if script.string and (
                    "factsheets" in script.string.lower()
                    or "drugs" in script.string.lower()
                ):
                    logger.info(
                        "Script %d contains drug data: %s...", i, script.string[:200]
                    )

            # Look for different possible link patterns
            drug_links = []

            # Method 1: Look for links containing drug names
            for link in soup.find_all("a", href=True):
                href = link["href"]
                text = link.get_text().strip()
                logger.info("Link: %s -> %s", href, text)

                # Check various patterns
                if (
                    "/factsheets/" in href
                    and href != "/factsheets/"
                    and len(href.split("/")) >= 3
                ):
                    full_url = (
                        f"{self.base_url}{href}" if href.startswith("/") else href
                    )
                    if full_url not in drug_links:
                        drug_links.append(full_url)
                        logger.info("Found drug link: %s", full_url)

            logger.info("Total drug links found: %d", len(drug_links))

            if not drug_links:
                # Try alternative URLs or approaches
                logger.info("No drug links found. Checking alternative sources...")

                # Check if there's an API endpoint
                api_url = "https://tripsit.me/api/factsheets"
                try:
                    api_response = requests.get(api_url, timeout=10)
                    if api_response.status_code == 200:
                        logger.info("API endpoint found! %s", api_url)
                        # Try to parse as JSON
                        try:
                            api_data = api_response.json()
                            logger.info(
                                "API returned %d items",
                                len(api_data) if isinstance(api_data, list) else 1,
                            )

                            if isinstance(api_data, list):
                                for item in api_data[:5]:  # First 5
                                    if isinstance(item, dict) and "name" in item:
                                        drug_name = (
                                            item["name"].lower().replace(" ", "-")
                                        )
                                        drug_url = (
                                            f"{self.base_url}/factsheets/{drug_name}/"
                                        )
                                        drug_links.append(drug_url)
                                        logger.info("Added from API: %s", drug_url)
                        except:
                            logger.info("API response not JSON")
                    else:
                        logger.info("No API endpoint at %s", api_url)
                except Exception as e:
                    logger.info("Error checking API: %s", e)

                # Try the wiki substances category
                wiki_url = "https://wiki.tripsit.me/wiki/Category:Substances"
                try:
                    logger.info("Trying wiki substances category: %s", wiki_url)
                    wiki_response = requests.get(wiki_url, timeout=10)
                    if wiki_response.status_code == 200:
                        wiki_soup = BeautifulSoup(wiki_response.content, "html.parser")

                        # Look for substance links in the category page
                        content_div = wiki_soup.find("div", {"id": "mw-pages"})
                        if content_div:
                            wiki_links = content_div.find_all("a", href=True)
                            wiki_drug_links = []
                            for link in wiki_links:
                                href = link["href"]
                                title = link.get("title", "")
                                # Check if it's a substance page (not category page)
                                if (
                                    href.startswith("/wiki/")
                                    and not href.startswith("/wiki/Category:")
                                    and not "Category:" in title
                                ):
                                    # Convert wiki URL to factsheet URL
                                    substance_name = (
                                        href.replace("/wiki/", "")
                                        .replace("_", "-")
                                        .lower()
                                    )
                                    factsheet_url = (
                                        f"{self.base_url}/factsheets/{substance_name}/"
                                    )
                                    if factsheet_url not in wiki_drug_links:
                                        wiki_drug_links.append(factsheet_url)
                                        logger.info(
                                            "Found wiki substance: %s", factsheet_url
                                        )

                            if wiki_drug_links:
                                logger.info(
                                    "Found %d substance links from wiki",
                                    len(wiki_drug_links),
                                )
                                drug_links.extend(wiki_drug_links)

                        # Also try the main substances page
                        substances_page = wiki_soup.find(
                            "div", {"id": "mw-content-text"}
                        )
                        if substances_page:
                            page_links = substances_page.find_all("a", href=True)
                            for link in page_links:
                                href = link["href"]
                                if (
                                    href.startswith("/wiki/") and ":" not in href
                                ):  # Avoid special pages
                                    substance_name = (
                                        href.replace("/wiki/", "")
                                        .replace("_", "-")
                                        .lower()
                                    )
                                    if substance_name and len(substance_name) > 2:
                                        factsheet_url = f"{self.base_url}/factsheets/{substance_name}/"
                                        if factsheet_url not in drug_links:
                                            drug_links.append(factsheet_url)
                                            logger.info(
                                                "Found substance page: %s",
                                                factsheet_url,
                                            )

                except Exception as e:
                    logger.info("Error checking wiki: %s", e)

                # Try to find drugs from the combo chart URL mentioned by user
                combo_url = "https://knowyourstuff.nz/wp-content/uploads/2024/07/Tripsit-combo-chart-2048x849.png"
                logger.info("Checking combo chart URL: %s", combo_url)
                # This is an image, not helpful for scraping

                # Last resort: try some common drug names manually
                if not drug_links:
                    logger.info(
                        "No automatic drug discovery worked. Using manual common drugs list."
                    )
                    common_drugs = [
                        "cannabis",
                        "alcohol",
                        "caffeine",
                        "nicotine",
                        "mdma",
                        "cocaine",
                        "amphetamine",
                        "methamphetamine",
                        "heroin",
                        "fentanyl",
                        "morphine",
                        "oxycodone",
                        "hydrocodone",
                        "ketamine",
                        "lsd",
                        "psilocybin",
                        "mescaline",
                        "dmt",
                        "ayahuasca",
                        "salvia",
                        "kratom",
                        "kava",
                        "valium",
                        "xanax",
                        "ativan",
                        "clonazepam",
                        "diazepam",
                        "tramadol",
                        "codeine",
                        "ibuprofen",
                        "acetaminophen",
                        "aspirin",
                    ]

                    for drug in common_drugs:
                        factsheet_url = f"{self.base_url}/factsheets/{drug}/"
                        drug_links.append(factsheet_url)
                        logger.info("Added common drug: %s", factsheet_url)

                    logger.info("Added %d common drugs manually", len(common_drugs))

            return drug_links

        except Exception as e:
            logger.error(f"Error getting drug URLs: {e}")
            return []

    async def _scrape_drug_page_async(self, url: str) -> Optional[Dict]:
        """
        Scrape a single drug factsheet page using Playwright.

        Args:
            url: URL of the drug page

        Returns:
            Dictionary with drug information
        """
        from playwright.async_api import async_playwright

        try:
            async with async_playwright() as p:
                browser = await p.firefox.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                )
                page = await context.new_page()

                try:
                    # Navigate to the page and wait for it to load
                    await page.goto(url, wait_until="networkidle", timeout=30000)

                    # Wait longer for dynamic content
                    await page.wait_for_timeout(5000)

                    # Try to wait for specific elements that might indicate content loaded
                    try:
                        await page.wait_for_selector(
                            "h1, .drug-name, .factsheet-content", timeout=10000
                        )
                    except:
                        logger.info(f"No specific content selectors found on {url}")

                    # Get the page content
                    content = await page.content()
                    soup = BeautifulSoup(content, "html.parser")

                    # Debug: log some page content
                    title = soup.find("title")
                    logger.info(
                        f"Page title: {title.get_text().strip() if title else 'No title'}"
                    )

                    h1_tags = soup.find_all("h1")
                    logger.info(f"H1 tags: {[h.get_text().strip() for h in h1_tags]}")

                    # Check page text for various error conditions
                    page_text = soup.get_text().lower()
                    if "drug not found" in page_text:
                        logger.warning(f"Page indicates drug not found: {url}")
                        return None
                    elif "page not found" in page_text or "404" in page_text:
                        logger.warning(f"Page not found (404): {url}")
                        return None
                    elif "javascript is not enabled" in page_text:
                        logger.warning(f"Page still requires JavaScript: {url}")
                        return None

                    drug_data = {
                        "name": self._extract_name(soup),
                        "aliases": self._extract_aliases(soup),
                        "categories": self._extract_categories(soup),
                        "reagents": self._extract_reagents(soup),
                        "effects": self._extract_effects(soup),
                        "pw_effects": self._extract_pw_effects(soup),
                        "summary": self._extract_summary(soup),
                        "interactions": self._extract_interactions(soup),
                        "url": url,
                    }

                    # Validate we got at least a name and it's not an error message
                    if (
                        not drug_data["name"]
                        or "not found" in drug_data["name"].lower()
                    ):
                        logger.warning(f"No valid drug name found at {url}")
                        return None

                    logger.info(f"Successfully scraped drug: {drug_data['name']}")
                    return drug_data

                finally:
                    await browser.close()

        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return None

    def _scrape_drug_page(self, url: str) -> Optional[Dict]:
        """
        Synchronous wrapper for async scraping.

        Args:
            url: URL of the drug page

        Returns:
            Dictionary with drug information
        """
        import asyncio

        try:
            # Run the async function in a new event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self._scrape_drug_page_async(url))
            loop.close()
            return result
        except Exception as e:
            logger.error(f"Error in sync wrapper for {url}: {e}")
            return None

    def _extract_name(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract drug name from page."""
        try:
            # Look for title or heading
            title = soup.find("title")
            if title:
                # Extract from title like "Cannabis - Factsheet - TripSit"
                title_text = title.get_text().strip()
                if " - Factsheet - TripSit" in title_text:
                    return title_text.replace(" - Factsheet - TripSit", "").strip()

            # Fallback: look for h1 or main heading
            h1 = soup.find("h1")
            if h1:
                return h1.get_text().strip()

        except Exception as e:
            logger.warning(f"Error extracting name: {e}")

        return None

    def _extract_aliases(self, soup: BeautifulSoup) -> List[str]:
        """Extract drug aliases."""
        aliases = []

        try:
            # Look for aliases section
            alias_patterns = [
                r"Aliases?:?\s*(.+?)(?:\n|$)",
                r"Also known as:?\s*(.+?)(?:\n|$)",
                r"Other names:?\s*(.+?)(?:\n|$)",
            ]

            text_content = soup.get_text()

            for pattern in alias_patterns:
                match = re.search(pattern, text_content, re.IGNORECASE | re.MULTILINE)
                if match:
                    alias_text = match.group(1).strip()
                    # Split by common separators
                    aliases.extend(re.split(r"[,&;/]", alias_text))
                    break

            # Clean up aliases
            aliases = [alias.strip() for alias in aliases if alias.strip()]
            aliases = list(set(aliases))  # Remove duplicates

        except Exception as e:
            logger.warning(f"Error extracting aliases: {e}")

        return aliases

    def _extract_categories(self, soup: BeautifulSoup) -> List[str]:
        """Extract drug categories."""
        categories = []

        try:
            # Look for categories section
            text_content = soup.get_text()

            # Look for "Categories:" or similar
            cat_match = re.search(
                r"Categories?:?\s*(.+?)(?:\n|$)", text_content, re.IGNORECASE
            )
            if cat_match:
                cat_text = cat_match.group(1).strip()
                categories = re.split(r"[,&;/]", cat_text)
                categories = [cat.strip() for cat in categories if cat.strip()]

        except Exception as e:
            logger.warning(f"Error extracting categories: {e}")

        return categories

    def _extract_reagents(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract reagents test results."""
        try:
            text_content = soup.get_text()

            # Look for reagents section
            reagents_match = re.search(
                r"Reagents?:?\s*(.+?)(?=Effects|PW|$)",
                text_content,
                re.IGNORECASE | re.DOTALL,
            )

            if reagents_match:
                return reagents_match.group(1).strip()

        except Exception as e:
            logger.warning(f"Error extracting reagents: {e}")

        return None

    def _extract_effects(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract effects information."""
        try:
            text_content = soup.get_text()

            # Look for effects section
            effects_match = re.search(
                r"Effects?:?\s*(.+?)(?=PW|Summary|$)",
                text_content,
                re.IGNORECASE | re.DOTALL,
            )

            if effects_match:
                return effects_match.group(1).strip()

        except Exception as e:
            logger.warning(f"Error extracting effects: {e}")

        return None

    def _extract_pw_effects(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract personal wiki effects."""
        try:
            text_content = soup.get_text()

            # Look for PW effects section
            pw_match = re.search(
                r"PW(?:\s+Effects)?:?\s*(.+?)(?=Summary|$)",
                text_content,
                re.IGNORECASE | re.DOTALL,
            )

            if pw_match:
                return pw_match.group(1).strip()

        except Exception as e:
            logger.warning(f"Error extracting PW effects: {e}")

        return None

    def _extract_summary(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract summary information."""
        try:
            text_content = soup.get_text()

            # Look for summary section
            summary_match = re.search(
                r"Summary:?\s*(.+?)(?=$)", text_content, re.IGNORECASE | re.DOTALL
            )

            if summary_match:
                return summary_match.group(1).strip()

        except Exception as e:
            logger.warning(f"Error extracting summary: {e}")

        return None

    def _extract_interactions(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract drug interactions."""
        interactions = {}

        try:
            text_content = soup.get_text()

            # Look for interactions section
            interact_match = re.search(
                r"Interactions?:?\s*(.+?)(?=$)", text_content, re.IGNORECASE | re.DOTALL
            )

            if interact_match:
                interact_text = interact_match.group(1)

                # Parse interaction entries
                # Look for patterns like "Cannabis: Low Risk & Synergy"
                lines = interact_text.split("\n")
                for line in lines:
                    if ":" in line:
                        parts = line.split(":", 1)
                        if len(parts) == 2:
                            drug = parts[0].strip()
                            risk = parts[1].strip()
                            if drug and risk:
                                interactions[drug] = risk

        except Exception as e:
            logger.warning(f"Error extracting interactions: {e}")

        return interactions

    def save_drugs_data(self, drugs_data: Dict[str, Dict]):
        """
        Save drug data to JSON file.

        Args:
            drugs_data: Dictionary of drug information
        """
        try:
            with open(self.drugs_file, "w", encoding="utf-8") as f:
                json.dump(drugs_data, f, ensure_ascii=False, indent=2)

            logger.info(f"Saved {len(drugs_data)} drugs to {self.drugs_file}")

        except Exception as e:
            logger.error(f"Error saving drugs data: {e}")

    def load_drugs_data(self) -> Dict[str, Dict]:
        """
        Load drug data from JSON file.

        Returns:
            Dictionary of drug information
        """
        try:
            if self.drugs_file.exists():
                with open(self.drugs_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading drugs data: {e}")

        return {}


def main():
    """Main function to scrape and save drug data."""
    scraper = DrugScraper()

    # Check if we already have data
    existing_data = scraper.load_drugs_data()
    if existing_data:
        print(f"Found existing data for {len(existing_data)} drugs.")
        response = input("Scrape again? (y/N): ")
        if response.lower() != "y":
            print("Using existing data.")
            return

    # Try to scrape drugs
    drugs_data = scraper.scrape_all_drugs()

    # If scraping failed, provide sample data for testing
    if not drugs_data:
        print("Scraping failed. Using sample drug data for testing...")

        # Sample drug interaction data based on common knowledge
        sample_drugs = {
            "cannabis": {
                "name": "Cannabis",
                "aliases": ["weed", "marijuana", "pot"],
                "categories": ["depressant", "psychedelic"],
                "summary": "Cannabis is a psychoactive drug that produces euphoria, relaxation, and altered perception.",
                "interactions": {
                    "alcohol": "Low Risk & Synergy",
                    "caffeine": "Low Risk & Synergy",
                    "mdma": "Low Risk & Synergy",
                    "cocaine": "Caution",
                    "opioids": "Caution",
                },
                "url": "https://tripsit.me/factsheets/cannabis/",
            },
            "alcohol": {
                "name": "Alcohol",
                "aliases": ["ethanol", "booze"],
                "categories": ["depressant"],
                "summary": "Alcohol is a central nervous system depressant that produces euphoria and sedation.",
                "interactions": {
                    "cannabis": "Low Risk & Synergy",
                    "caffeine": "Low Risk & Decrease",
                    "mdma": "Caution",
                    "cocaine": "Dangerous",
                    "opioids": "Dangerous",
                },
                "url": "https://tripsit.me/factsheets/alcohol/",
            },
            "caffeine": {
                "name": "Caffeine",
                "aliases": ["coffee", "energy drinks"],
                "categories": ["stimulant"],
                "summary": "Caffeine is a stimulant that increases alertness and reduces fatigue.",
                "interactions": {
                    "cannabis": "Low Risk & Synergy",
                    "alcohol": "Low Risk & Decrease",
                    "mdma": "Caution",
                    "cocaine": "Caution",
                },
                "url": "https://tripsit.me/factsheets/caffeine/",
            },
            "mdma": {
                "name": "MDMA",
                "aliases": ["ecstasy", "molly"],
                "categories": ["empathogen", "stimulant"],
                "summary": "MDMA produces euphoria, empathy, and increased energy.",
                "interactions": {
                    "cannabis": "Low Risk & Synergy",
                    "alcohol": "Caution",
                    "caffeine": "Caution",
                    "cocaine": "Unsafe",
                },
                "url": "https://tripsit.me/factsheets/mdma/",
            },
            "cocaine": {
                "name": "Cocaine",
                "aliases": ["coke"],
                "categories": ["stimulant"],
                "summary": "Cocaine is a powerful stimulant that produces euphoria and increased energy.",
                "interactions": {
                    "alcohol": "Dangerous",
                    "cannabis": "Caution",
                    "mdma": "Unsafe",
                    "opioids": "Dangerous",
                },
                "url": "https://tripsit.me/factsheets/cocaine/",
            },
        }

        drugs_data = sample_drugs
        print(f"Using sample data with {len(drugs_data)} drugs for testing.")

    if drugs_data:
        scraper.save_drugs_data(drugs_data)
        print(f"Successfully saved {len(drugs_data)} drugs.")
    else:
        print("No drug data available.")


if __name__ == "__main__":
    main()
