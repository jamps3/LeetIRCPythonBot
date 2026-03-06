"""
Word Associations Tracking

Handles automatic detection and tracking of word associations in the format:
"word (thing)" -> stores: word -> thing

Example: "sauna (Harvia Vega)" -> stores: "sauna" -> "Harvia Vega"
"""

import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.logger import get_logger

# Regex pattern to match "word (thing)" format
# Captures the word before parentheses and the thing inside parentheses
# Supports Finnish letters: äöåÄÖÅé
ASSOCIATION_PATTERN = re.compile(
    r"\b([a-zA-ZäöåÄÖÅé]+\w*)\s*\(\s*([^)]+)\s*\)", re.IGNORECASE
)


class WordAssociations:
    """Tracks word associations in format 'word (association)'."""

    def __init__(self, data_manager):
        """
        Initialize the word associations tracker.

        Args:
            data_manager: DataManager instance for data persistence
        """
        self.data_manager = data_manager
        self.associations_file = os.path.join(
            data_manager.data_dir, "word_associations.json"
        )
        self._ensure_data_file()

    def _ensure_data_file(self):
        """Ensure the associations data file exists with proper structure."""
        if not os.path.exists(self.associations_file):
            default_structure = {
                "associations": {},
                "last_updated": datetime.now().isoformat(),
                "version": "1.0.0",
            }
            self.data_manager.save_json(self.associations_file, default_structure)

    def _load_associations(self) -> Dict[str, Any]:
        """Load associations from the JSON file."""
        try:
            return self.data_manager.load_json(self.associations_file)
        except Exception as e:
            get_logger(__name__).warning(f"Failed to load word associations: {e}")
            return {"associations": {}, "last_updated": datetime.now().isoformat()}

    def _save_associations(self, data: Dict[str, Any]):
        """Save associations to the JSON file."""
        data["last_updated"] = datetime.now().isoformat()
        self.data_manager.save_json(self.associations_file, data)

    def process_message(self, server: str, text: str) -> List[tuple]:
        """
        Process a message to detect word associations.

        Args:
            server: Server name (for future server-specific associations)
            text: Message text to scan

        Returns:
            List of tuples (word, association) that were found and stored
        """
        # Skip commands
        if text.strip().startswith("!"):
            return []

        found_associations = []

        # Find all matches of "word (thing)" pattern
        matches = ASSOCIATION_PATTERN.findall(text)

        if not matches:
            return []

        # Load current associations
        data = self._load_associations()
        associations = data.get("associations", {})

        for word, association in matches:
            # Normalize to lowercase for consistency
            word_lower = word.lower().strip()
            association_clean = association.strip()

            if not word_lower or not association_clean:
                continue

            # Store or update the association
            # If word already exists, we can optionally track multiple associations
            if word_lower not in associations:
                associations[word_lower] = []

            # Check if this association already exists for this word
            existing = associations[word_lower]
            if association_clean not in existing:
                existing.append(association_clean)
                found_associations.append((word_lower, association_clean))
                get_logger(__name__).debug(
                    f"New association stored: '{word_lower}' -> '{association_clean}'"
                )

        # Save if we found new associations
        if found_associations:
            data["associations"] = associations
            self._save_associations(data)

        return found_associations

    def get_association(self, word: str) -> Optional[List[str]]:
        """
        Get associations for a specific word.

        Args:
            word: The word to look up

        Returns:
            List of associations for the word, or None if not found
        """
        data = self._load_associations()
        associations = data.get("associations", {})
        return associations.get(word.lower().strip())

    def get_all_associations(self) -> Dict[str, List[str]]:
        """
        Get all word associations.

        Returns:
            Dictionary of all word -> associations mappings
        """
        data = self._load_associations()
        return data.get("associations", {})

    def search_associations(self, query: str) -> Dict[str, List[str]]:
        """
        Search for associations matching a query (partial match).

        Args:
            query: Search query (case-insensitive)

        Returns:
            Dictionary of matching word -> associations
        """
        data = self._load_associations()
        associations = data.get("associations", {})
        query_lower = query.lower().strip()

        # Search in both words and associations
        results = {}
        for word, assocs in associations.items():
            if query_lower in word:
                results[word] = assocs
            else:
                # Also check if query matches any association
                matching_assocs = [a for a in assocs if query_lower in a.lower()]
                if matching_assocs:
                    results[word] = matching_assocs

        return results

    def delete_association(self, word: str, association: str = None) -> bool:
        """
        Delete an association or all associations for a word.

        Args:
            word: The word to delete associations for
            association: Specific association to delete (if None, deletes all for word)

        Returns:
            True if deletion was successful
        """
        data = self._load_associations()
        associations = data.get("associations", {})
        word_lower = word.lower().strip()

        if word_lower not in associations:
            return False

        if association is None:
            # Delete all associations for this word
            del associations[word_lower]
            get_logger(__name__).info(
                f"Deleted all associations for word: '{word_lower}'"
            )
        else:
            # Delete specific association
            assoc_list = associations[word_lower]
            association_clean = association.strip()
            if association_clean in assoc_list:
                assoc_list.remove(association_clean)
                get_logger(__name__).info(
                    f"Deleted association: '{word_lower}' -> '{association_clean}'"
                )
                if not assoc_list:
                    del associations[word_lower]

        data["associations"] = associations
        self._save_associations(data)
        return True

    def add_association(self, word: str, association: str) -> bool:
        """
        Manually add an association.

        Args:
            word: The word to associate
            association: The association

        Returns:
            True if addition was successful
        """
        data = self._load_associations()
        associations = data.get("associations", {})
        word_lower = word.lower().strip()
        assoc_clean = association.strip()

        if not word_lower or not assoc_clean:
            return False

        if word_lower not in associations:
            associations[word_lower] = []

        if assoc_clean not in associations[word_lower]:
            associations[word_lower].append(assoc_clean)

        data["associations"] = associations
        self._save_associations(data)
        return True

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about stored associations.

        Returns:
            Dictionary with stats
        """
        data = self._load_associations()
        associations = data.get("associations", {})

        total_words = len(associations)
        total_associations = sum(len(v) for v in associations.values())
        words_with_multiple = sum(1 for v in associations.values() if len(v) > 1)

        return {
            "total_words": total_words,
            "total_associations": total_associations,
            "words_with_multiple": words_with_multiple,
            "last_updated": data.get("last_updated"),
        }
