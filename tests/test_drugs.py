#!/usr/bin/env python3
"""
Tests for drug data APIs and services.
"""

import json

import pytest

DRUGS_DATA = {
    "cannabis": {
        "name": "Cannabis",
        "aliases": ["weed", "marijuana"],
        "categories": ["depressant", "psychedelic"],
        "summary": "A test fixture entry for cannabis.",
    },
    "alcohol": {
        "name": "Alcohol",
        "aliases": ["ethanol"],
        "categories": ["depressant"],
        "summary": "A test fixture entry for alcohol.",
    },
}

INTERACTIONS_DATA = {
    "cannabis": {
        "alcohol": {
            "status": "Caution",
            "note": "Fixture interaction used by tests.",
        }
    }
}


@pytest.fixture
def drug_data_dir(tmp_path):
    """Create local drug data files without touching the repository data dir."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "drugs.json").write_text(json.dumps(DRUGS_DATA), encoding="utf-8")
    (data_dir / "interactions.json").write_text(
        json.dumps(INTERACTIONS_DATA), encoding="utf-8"
    )
    return data_dir


class TestDrugDataSnapshots:
    """Test the local TripSit-style data structure used by the service."""

    def test_drugs_snapshot_structure(self, drug_data_dir):
        """Test the local TripSit-style drugs snapshot structure."""
        with open(drug_data_dir / "drugs.json", encoding="utf-8") as f:
            data = json.load(f)

        assert isinstance(data, dict), "Drug data should be a dict"
        assert len(data) >= 2

        # Check that it's properly structured
        sample_key = list(data.keys())[0]
        drug_info = data[sample_key]
        assert isinstance(drug_info, dict), f"Drug info should be dict for {sample_key}"

        # Should have basic fields
        expected_fields = ["name", "aliases", "categories"]
        for field in expected_fields:
            assert field in drug_info, f"Missing {field} in drug {sample_key}"

    def test_interactions_snapshot_structure(self, drug_data_dir):
        """Test the local TripSit-style interaction snapshot structure."""
        with open(drug_data_dir / "interactions.json", encoding="utf-8") as f:
            data = json.load(f)

        assert isinstance(data, dict), "Interaction data should be a dict"
        assert data

        interaction_groups = [
            value for value in data.values() if isinstance(value, dict)
        ]
        assert interaction_groups, "Expected at least one interaction group"

        sample_group = next(
            value for value in interaction_groups if any(value.values())
        )
        sample_interaction = next(
            value for value in sample_group.values() if isinstance(value, dict)
        )
        assert "status" in sample_interaction


class TestDrugService:
    """Test the drug service functionality."""

    @pytest.fixture
    def drug_service(self, drug_data_dir):
        """Create a drug service instance."""
        from services.drug_service import DrugService

        return DrugService(data_dir=str(drug_data_dir))

    def test_service_initialization(self, drug_service):
        """Test that drug service initializes properly."""
        stats = drug_service.get_stats()
        assert isinstance(stats, dict)
        assert "total_drugs" in stats

    def test_drug_lookup(self, drug_service):
        """Test basic drug lookup functionality."""
        drug_info = drug_service.get_drug_info("cannabis")
        assert isinstance(drug_info, dict)
        assert drug_info["name"] == "Cannabis"

    def test_drug_search(self, drug_service):
        """Test drug search functionality."""
        results = drug_service.search_drugs("can", limit=5)
        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0]["name"] == "Cannabis"

    def test_drug_interactions(self, drug_service):
        """Test drug interaction checking."""
        result = drug_service.check_interactions(["cannabis", "alcohol"])
        assert isinstance(result, dict)
        assert result["interactions"] == [("cannabis", "alcohol", "Caution")]
        assert result["warnings"]
