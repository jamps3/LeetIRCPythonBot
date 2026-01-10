"""
Drug Data Scraper for TripSit

Fetches drug information from TripSit GitHub repository.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

import requests

sys.path.insert(0, "src")
from logger import get_logger

logger = get_logger("DrugScraper")


class DrugScraper:
    """Scraper for TripSit drug factsheets using APIs."""

    def __init__(self, data_dir: str = "data"):
        """
        Initialize the drug scraper.

        Args:
            data_dir: Directory where data files are stored
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.drugs_file = self.data_dir / "drugs.json"
        self.github_drugs_file = Path("github_drugs_full.json")

        # API URLs
        self.github_api_url = (
            "https://raw.githubusercontent.com/TripSit/drugs/master/drugs.json"
        )
        self.combos_api_url = (
            "https://raw.githubusercontent.com/TripSit/drugs/main/combos.json"
        )

    def scrape_from_github(self) -> Dict[str, Dict]:
        """
        Scrape drug data from TripSit GitHub repository.

        Returns:
            Dictionary of drug data
        """
        logger.info("Fetching drug data from TripSit GitHub repository...")
        try:
            response = requests.get(self.github_api_url, timeout=15)
            response.raise_for_status()

            github_data = response.json()
            logger.info(
                f"GitHub data: {type(github_data)} with {len(github_data) if hasattr(github_data, '__len__') else 'N/A'} items"
            )
            if isinstance(github_data, dict) and len(github_data) > 100:
                logger.info(
                    f"*** SUCCESS! Found {len(github_data)} drugs in GitHub repo ***"
                )
                sample_key = list(github_data.keys())[0]
                logger.info(
                    f"Sample drug '{sample_key}': {list(github_data[sample_key].keys()) if isinstance(github_data[sample_key], dict) else 'not dict'}"
                )

                # Save to github_drugs_full.json
                with open(self.github_drugs_file, "w") as f:
                    json.dump(github_data, f, indent=2)
                logger.info("Saved to github_drugs_full.json")

                return github_data
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching from GitHub API: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing GitHub API response: {e}")

        logger.warning("Failed to fetch drug data from GitHub")
        return {}

    def scrape_interactions(self) -> Dict[str, Dict]:
        """
        Scrape drug interaction data from TripSit combos.json.

        Returns:
            Dictionary of interaction data
        """
        logger.info("Fetching drug interactions from TripSit combos.json...")
        try:
            response = requests.get(self.combos_api_url, timeout=15)
            response.raise_for_status()

            interactions_data = response.json()
            logger.info(
                f"Successfully fetched interactions data: {type(interactions_data)}"
            )

            if isinstance(interactions_data, dict):
                logger.info(f"Found {len(interactions_data)} interaction entries")
                # Show sample
                if interactions_data:
                    sample_key = list(interactions_data.keys())[0]
                    logger.info(f"Sample interaction: {sample_key}")

            return interactions_data

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching interactions data: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing interactions JSON response: {e}")

        logger.warning("Failed to fetch interactions data")
        return {}

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


def test_service():
    """Test the drug service functionality."""
    print("Testing Drug Service...")

    try:
        # Import the service
        sys.path.insert(0, "src")
        from services.drug_service import DrugService

        # Create service instance
        service = DrugService()

        # Get stats
        stats = service.get_stats()
        print(f"Service stats: {stats}")

        if stats["total_drugs"] == 0:
            print(
                "No drug data loaded. Run with 'scrape' parameter to scrape data first."
            )
            return

        # Test basic drug lookup
        test_drugs = ["cannabis", "alcohol", "mdma", "caffeine"]
        print("\nTesting drug lookups:")
        for drug_name in test_drugs:
            drug_info = service.get_drug_info(drug_name)
            if drug_info:
                formatted = service.format_drug_info(drug_info)
                print(f"✓ Found {drug_name}: {formatted}")
            else:
                print(f"✗ Drug '{drug_name}' not found")

        # Test search
        print("\nTesting search:")
        search_results = service.search_drugs("can", limit=3)
        print(f"Search 'can' returned {len(search_results)} results:")
        for result in search_results:
            print(f"  - {result.get('name', 'Unknown')}")

        # Test interactions
        print("\nTesting interactions:")
        interaction_result = service.check_interactions(["cannabis", "alcohol"])
        print(
            f"Interactions check: {len(interaction_result['interactions'])} interactions found"
        )
        if interaction_result["warnings"]:
            print("Warnings:")
            for warning in interaction_result["warnings"]:
                print(f"  ⚠️ {warning}")

        print("\n✓ Service test completed successfully!")

    except Exception as e:
        print(f"✗ Service test failed: {e}")
        import traceback

        traceback.print_exc()


def main():
    """Main function - handle command line arguments."""
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command == "scrape":
            print("Starting drug data scraping from TripSit GitHub repository...")
            scraper = DrugScraper()

            # Scrape drug data from GitHub
            drugs_data = scraper.scrape_from_github()

            if drugs_data:
                print(f"Successfully fetched {len(drugs_data)} drugs from GitHub!")
                scraper.save_drugs_data(drugs_data)
                print(f"Saved drug data to {scraper.drugs_file}")
            else:
                print(
                    "Failed to fetch drug data from GitHub. Using fallback sample data..."
                )
                drugs_data = get_sample_drugs()
                scraper.save_drugs_data(drugs_data)
                print(f"Saved fallback sample data with {len(drugs_data)} drugs.")

            # Scrape interactions data
            print("\nScraping drug interactions...")
            interactions_data = scraper.scrape_interactions()

            if interactions_data:
                # Save interactions data
                interactions_file = scraper.data_dir / "interactions.json"
                try:
                    with open(interactions_file, "w", encoding="utf-8") as f:
                        json.dump(interactions_data, f, ensure_ascii=False, indent=2)
                    print(
                        f"Successfully saved {len(interactions_data)} interaction entries to {interactions_file}"
                    )
                except Exception as e:
                    print(f"Error saving interactions data: {e}")
            else:
                print("Failed to fetch interactions data.")

        elif command in ["help", "-h", "--help"]:
            print("Usage:")
            print("  python debug_drugs.py            # Test the drug service")
            print(
                "  python debug_drugs.py scrape     # Scrape drug data and interactions from TripSit GitHub repository"
            )
            print("  python debug_drugs.py help       # Show this help")

        else:
            print(f"Unknown command: {command}")
            print("Use 'help' for usage information.")

    else:
        # No arguments - test the service
        test_service()


def get_sample_drugs():
    """Get sample drug data for fallback."""
    return {
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


if __name__ == "__main__":
    main()
