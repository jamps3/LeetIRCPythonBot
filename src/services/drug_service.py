"""
Drug Service Module

Provides drug information and interaction checking from TripSit data.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, "src")
from logger import get_logger  # noqa: E402

logger = get_logger("DrugService")


class DrugService:
    """Service for drug information and interaction checking."""

    def __init__(self, data_dir: str = "data"):
        """
        Initialize drug service.

        Args:
            data_dir: Directory where data files are stored
        """
        self.data_dir = Path(data_dir)
        self.drugs_file = self.data_dir / "drugs.json"
        self.interactions_file = self.data_dir / "interactions.json"
        self.drugs_data: Dict[str, Dict] = {}
        self.interactions_data: Dict[str, Dict] = {}

        # Load drug data
        self._load_drugs_data()
        self._load_interactions_data()

    def _load_drugs_data(self):
        """Load drug data from JSON file."""
        try:
            if self.drugs_file.exists():
                with open(self.drugs_file, "r", encoding="utf-8") as f:
                    self.drugs_data = json.load(f)
                logger.info(
                    f"Loaded {len(self.drugs_data)} drugs from {self.drugs_file}"
                )
            else:
                logger.warning(f"Drugs data file not found: {self.drugs_file}")
                logger.warning("Run src/debug/debug_drugs.py to scrape drug data first")
        except Exception as e:
            logger.error(f"Error loading drugs data: {e}")
            self.drugs_data = {}

    def _load_interactions_data(self):
        """Load interactions data from JSON file."""
        try:
            if self.interactions_file.exists():
                with open(self.interactions_file, "r", encoding="utf-8") as f:
                    self.interactions_data = json.load(f)
                logger.info(
                    f"Loaded {len(self.interactions_data)} interaction entries from {self.interactions_file}"
                )
            else:
                logger.warning(
                    f"Interactions data file not found: {self.interactions_file}"
                )
                logger.warning(
                    "Run src/debug/scrape_interactions.py to scrape interaction data"
                )
        except Exception as e:
            logger.error(f"Error loading interactions data: {e}")
            self.interactions_data = {}

    def get_drug_info(self, drug_name: str) -> Optional[Dict]:
        """
        Get information about a specific drug.

        Args:
            drug_name: Name of the drug (case-insensitive)

        Returns:
            Drug information dictionary or None if not found
        """
        drug_name_lower = drug_name.lower()

        # Direct match
        if drug_name_lower in self.drugs_data:
            return self.drugs_data[drug_name_lower]

        # Check aliases
        for drug_key, drug_info in self.drugs_data.items():
            aliases = drug_info.get("aliases", [])
            if any(alias.lower() == drug_name_lower for alias in aliases):
                return drug_info

        # Fuzzy match on name
        for drug_key, drug_info in self.drugs_data.items():
            if drug_name_lower in drug_key.lower():
                return drug_info
            name = drug_info.get("name", "")
            if name and drug_name_lower in name.lower():
                return drug_info

        return None

    def search_drugs(self, query: str, limit: int = 5) -> List[Dict]:
        """
        Search for drugs by name or alias.

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            List of matching drug info dictionaries
        """
        query_lower = query.lower()
        matches = []

        for drug_key, drug_info in self.drugs_data.items():
            # Check primary name
            name = drug_info.get("name", "")
            if query_lower in name.lower():
                matches.append(drug_info)
                continue

            # Check aliases
            aliases = drug_info.get("aliases", [])
            if any(query_lower in alias.lower() for alias in aliases):
                matches.append(drug_info)
                continue

            # Check categories
            categories = drug_info.get("categories", [])
            if any(query_lower in cat.lower() for cat in categories):
                matches.append(drug_info)
                continue

        return matches[:limit]

    def check_interactions(
        self, drug_names: List[str]
    ) -> Dict[str, List[Tuple[str, str, str]]]:
        """
        Check for interactions between multiple drugs.

        Args:
            drug_names: List of drug names to check

        Returns:
            Dictionary with interaction results:
            {
                'interactions': [(drug1, drug2, risk_level), ...],
                'warnings': [warning_messages],
                'unknown_drugs': [drug_names_not_found]
            }
        """
        result = {"interactions": [], "warnings": [], "unknown_drugs": []}

        # Validate and normalize drug names
        valid_drugs = []
        for drug_name in drug_names:
            drug_info = self.get_drug_info(drug_name)
            drug_name_lower = drug_name.lower()

            # Accept drug if it exists in drugs.json OR interactions.json
            if drug_info or drug_name_lower in self.interactions_data:
                valid_drugs.append((drug_name, drug_info))
            else:
                result["unknown_drugs"].append(drug_name)

        # Check all pairs for interactions using interactions.json data first
        for i, (name1, info1) in enumerate(valid_drugs):
            for j, (name2, info2) in enumerate(valid_drugs):
                if i >= j:  # Avoid duplicate checks
                    continue

                interaction_found = False

                # Try to find interaction in interactions.json data
                if self.interactions_data:
                    # Check drug1 -> drug2 in interactions.json
                    drug1_interactions = self.interactions_data.get(name1.lower(), {})
                    interaction_data = drug1_interactions.get(name2.lower())
                    if interaction_data and isinstance(interaction_data, dict):
                        risk = interaction_data.get("status")
                        if risk:
                            result["interactions"].append((name1, name2, risk))
                            interaction_found = True
                            continue

                    # Check drug2 -> drug1 in interactions.json
                    drug2_interactions = self.interactions_data.get(name2.lower(), {})
                    interaction_data = drug2_interactions.get(name1.lower())
                    if interaction_data and isinstance(interaction_data, dict):
                        risk = interaction_data.get("status")
                        if risk:
                            result["interactions"].append((name1, name2, risk))
                            interaction_found = True
                            continue

                # If not found in interactions.json, fall back to individual drug interactions
                if not interaction_found:
                    interactions1 = info1.get("interactions", {})

                    # Check drug1 -> drug2 interaction
                    risk1 = interactions1.get(name2)
                    if risk1:
                        result["interactions"].append((name1, name2, risk1))
                        continue

                    # Check drug2 -> drug1 interaction
                    interactions2 = info2.get("interactions", {})
                    risk2 = interactions2.get(name1)
                    if risk2:
                        result["interactions"].append((name1, name2, risk2))
                        continue

                    # Check aliases
                    aliases1 = info1.get("aliases", [])
                    aliases2 = info2.get("aliases", [])

                    # Check if drug2 name matches any alias of drug1
                    for alias in aliases1:
                        if interactions1.get(alias):
                            result["interactions"].append(
                                (name1, name2, interactions1[alias])
                            )
                            break

                    # Check if drug1 name matches any alias of drug2
                    for alias in aliases2:
                        if interactions2.get(alias):
                            result["interactions"].append(
                                (name1, name2, interactions2[alias])
                            )
                            break

        # Generate warnings based on risk levels with emojis and definitions
        INTERACTION_STATUSES = {
            "Dangerous": {
                "emoji": "☠️",
                "definition": "These combinations are considered extremely harmful and should always be avoided. Reactions to these drugs taken in combination are highly unpredictable and have a potential to cause death.",
            },
            "Unsafe": {
                "emoji": "🛑",
                "definition": "There is considerable risk of physical harm when taking these combinations, they should be avoided where possible.",
            },
            "Caution": {
                "emoji": "⚠️",
                "definition": "These combinations are not usually physically harmful, but may produce undesirable effects, such as physical discomfort or overstimulation. Extreme use may cause physical health issues. Synergistic effects may be unpredictable. Care should be taken when choosing to use this combination.",
            },
            "Low Risk & Decrease": {
                "emoji": "↘",
                "definition": "Effects are subtractive. The combination is unlikely to cause any adverse or undesirable reaction beyond those that might ordinarily be expected from these drugs.",
            },
            "Low Risk & No Synergy": {
                "emoji": "➡",
                "definition": "Effects are additive. The combination is unlikely to cause any adverse or undesirable reaction beyond those that might ordinarily be expected from these drugs.",
            },
            "Low Risk & Synergy": {
                "emoji": "↗",
                "definition": "These drugs work together to cause an effect greater than the sum of its parts, and they aren't likely to cause an adverse or undesirable reaction when used carefully. Additional research should always be done before combining drugs.",
            },
            "Unknown": {"emoji": "❓", "definition": "Effects are unknown."},
        }

        for drug1, drug2, risk in result["interactions"]:
            # Find matching status (case-insensitive)
            status_info = None
            for status_name, status_data in INTERACTION_STATUSES.items():
                if status_name.lower() in risk.lower():
                    status_info = status_data
                    break

            if status_info:
                emoji = status_info["emoji"]
                definition = status_info["definition"]
                warning = f"{emoji} {drug1} + {drug2}: {definition}"
                result["warnings"].append(warning)

        return result

    def format_drug_info(self, drug_info: Dict) -> str:
        """
        Format drug information for display.

        Args:
            drug_info: Drug information dictionary

        Returns:
            Formatted string
        """
        parts = []

        name = drug_info.get("name", "Unknown")
        parts.append(f"💊 {name}")

        aliases = drug_info.get("aliases", [])
        if aliases:
            parts.append(f"Aliases: {', '.join(aliases)}")

        categories = drug_info.get("categories", [])
        if categories:
            parts.append(f"Categories: {', '.join(categories)}")

        if drug_info.get("summary"):
            summary = drug_info["summary"][:200]  # Truncate long summaries
            if len(drug_info["summary"]) > 200:
                summary += "..."
            parts.append(f"Summary: {summary}")

        return " | ".join(parts)

    def get_stats(self) -> Dict[str, int]:
        """
        Get statistics about the loaded drug data.

        Returns:
            Dictionary with statistics
        """
        total_drugs = len(self.drugs_data)
        total_interactions = sum(
            len(drug.get("interactions", {})) for drug in self.drugs_data.values()
        )

        return {
            "total_drugs": total_drugs,
            "total_interactions": total_interactions,
            "data_file": str(self.drugs_file),
            "file_exists": self.drugs_file.exists(),
        }


def create_drug_service() -> DrugService:
    """
    Factory function to create a drug service instance.

    Returns:
        DrugService instance
    """
    return DrugService()
