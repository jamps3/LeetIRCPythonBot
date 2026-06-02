"""Offline lookup service for IU Flockhart Table prescription interactions."""

import json
import re
from itertools import combinations
from pathlib import Path
from typing import Dict, List, Optional

from logger import get_logger

logger = get_logger("PrescriptionInteractionService")

DISCLAIMER = "Educational CYP reference only; confirm with a clinician or pharmacist."


def normalize_drug_name(name: str) -> str:
    """Normalize a displayed drug name for exact, case-insensitive lookup."""
    return re.sub(r"\s+", " ", name.strip()).casefold()


class PrescriptionInteractionService:
    """Read and query a scraped IU Flockhart Table snapshot."""

    def __init__(self, data_dir: str = "data"):
        self.data_file = Path(data_dir) / "prescription_interactions.json"
        self.metadata: Dict = {}
        self.drugs: Dict[str, Dict] = {}
        self._load_data()

    def _load_data(self) -> None:
        try:
            with open(self.data_file, "r", encoding="utf-8") as file:
                payload = json.load(file)
            drugs = payload.get("drugs", {})
            if not isinstance(drugs, dict):
                raise ValueError("'drugs' must be an object")
            self.metadata = payload.get("metadata", {})
            self.drugs = {
                normalize_drug_name(key): value
                for key, value in drugs.items()
                if isinstance(value, dict)
            }
            logger.info(f"Loaded {len(self.drugs)} prescription drugs")
        except (OSError, ValueError, json.JSONDecodeError) as error:
            logger.warning(f"Prescription interaction data unavailable: {error}")
            self.metadata = {}
            self.drugs = {}

    def get_drug(self, name: str) -> Optional[Dict]:
        return self.drugs.get(normalize_drug_name(name))

    def format_profile(self, name: str) -> str:
        drug = self.get_drug(name)
        if not drug:
            return f"Rx: Unknown prescription drug: {name}"
        grouped: Dict[str, Dict[str, Optional[str]]] = {}
        for relationship in drug.get("relationships", []):
            role = relationship.get("role", "unknown")
            enzyme = relationship.get("enzyme", "unknown")
            strength = relationship.get("strength")
            role_enzymes = grouped.setdefault(role, {})
            if strength or enzyme not in role_enzymes:
                role_enzymes[enzyme] = strength
        parts = [
            f"{role.title()}: {', '.join(f'{enzyme} ({strength})' if strength else enzyme for enzyme, strength in sorted(enzymes.items()))}"
            for role, enzymes in sorted(grouped.items())
        ]
        details = " | ".join(parts) if parts else "No CYP relationships listed"
        return f"Rx: {drug.get('name', name)} | {details} | {DISCLAIMER}"

    def check_interactions(self, names: List[str]) -> str:
        unique_names = list(dict.fromkeys(normalize_drug_name(name) for name in names))
        found = [(key, self.drugs.get(key)) for key in unique_names]
        unknown = [key for key, drug in found if not drug]
        messages = []
        if unknown:
            messages.append(f"Rx: Unknown prescription drugs: {', '.join(unknown)}")

        for (_, left), (_, right) in combinations(
            [(key, drug) for key, drug in found if drug], 2
        ):
            messages.extend(self._compare_pair(left, right))

        if not messages:
            messages.append(
                "Rx: No CYP-mediated interaction found between the listed drugs."
            )
        messages.append(DISCLAIMER)
        return " | ".join(messages)

    def _compare_pair(self, left: Dict, right: Dict) -> List[str]:
        messages = []
        for substrate, modifier in ((left, right), (right, left)):
            substrate_enzymes = {
                rel.get("enzyme")
                for rel in substrate.get("relationships", [])
                if rel.get("role") == "substrate"
            }
            for relationship in modifier.get("relationships", []):
                role = relationship.get("role")
                enzyme = relationship.get("enzyme")
                if enzyme not in substrate_enzymes or role not in {
                    "inhibitor",
                    "inducer",
                }:
                    continue
                effect = (
                    "may increase exposure to"
                    if role == "inhibitor"
                    else "may reduce exposure to"
                )
                messages.append(
                    f"Rx: {modifier['name']} {role} of {enzyme} {effect} {substrate['name']}"
                )
        return list(dict.fromkeys(messages))


def create_prescription_interaction_service() -> PrescriptionInteractionService:
    return PrescriptionInteractionService()
