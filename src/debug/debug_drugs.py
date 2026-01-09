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
        self.request_delay = 1.0  # seconds between requests

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

            # Find all drug links - they should be in a list or grid
            drug_links = []

            # Look for links in the main content area
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if href.startswith("/factsheets/") and href != "/factsheets/":
                    full_url = f"{self.base_url}{href}"
                    if full_url not in drug_links:
                        drug_links.append(full_url)

            logger.info(f"Found {len(drug_links)} drug links")
            return drug_links

        except Exception as e:
            logger.error(f"Error getting drug URLs: {e}")
            return []

    def _scrape_drug_page(self, url: str) -> Optional[Dict]:
        """
        Scrape a single drug factsheet page.

        Args:
            url: URL of the drug page

        Returns:
            Dictionary with drug information
        """
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")

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

            # Validate we got at least a name
            if not drug_data["name"]:
                return None

            return drug_data

        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
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

    # Scrape all drugs
    drugs_data = scraper.scrape_all_drugs()

    if drugs_data:
        scraper.save_drugs_data(drugs_data)
        print(f"Successfully scraped and saved {len(drugs_data)} drugs.")
    else:
        print("Failed to scrape any drug data.")


if __name__ == "__main__":
    main()
