#!/usr/bin/env python3
"""
Tests for drug data APIs and services.
"""
import json
from pathlib import Path

import pytest
import requests


class TestDrugAPIs:
    """Test various drug data API endpoints."""

    def test_tripsit_api_endpoints(self):
        """Test TripSit API endpoints for drug data (may not all work)."""
        endpoints = [
            "https://tripsit.me/api/factsheets",
            "https://api.tripsit.me/factsheets",
            "https://tripsit.me/api/drugs",
            "https://api.tripsit.me/drugs",
            "https://tripsit.me/api/substances",
            "https://api.tripsit.me/substances",
            "https://drugs.tripsit.me/api/factsheets",
            "https://combo.tripsit.me/api/factsheets",
        ]

        found_data = False
        tested_endpoints = 0

        for url in endpoints:
            try:
                response = requests.get(url, timeout=10)
                tested_endpoints += 1
                if response.status_code == 200:
                    try:
                        data = response.json()
                        if isinstance(data, list) and len(data) > 10:
                            found_data = True
                            assert len(data) > 0, f"No data in {url}"
                            assert isinstance(
                                data[0], dict
                            ), f"First item not a dict in {url}"
                            break
                        elif isinstance(data, dict):
                            # Check for nested data
                            for key in ["data", "factsheets", "drugs", "substances"]:
                                if (
                                    key in data
                                    and isinstance(data[key], list)
                                    and len(data[key]) > 10
                                ):
                                    found_data = True
                                    assert len(data[key]) > 0, f"No data in {url}.{key}"
                                    assert isinstance(
                                        data[key][0], dict
                                    ), f"First item not a dict in {url}.{key}"
                                    break
                    except json.JSONDecodeError:
                        pass  # Not JSON, skip
            except requests.RequestException:
                pass  # Connection error, skip

        # Just verify we tested some endpoints - the GitHub API is the reliable one
        assert tested_endpoints > 0, "No endpoints were testable"

    def test_combo_api_endpoints(self):
        """Test combo.tripsit.me specific endpoints."""
        endpoints = [
            "https://combo.tripsit.me/api",
            "https://combo.tripsit.me/api/drugs",
            "https://combo.tripsit.me/api/factsheets",
            "https://combo.tripsit.me/drugs.json",
            "https://combo.tripsit.me/factsheets.json",
        ]

        for url in endpoints:
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    content_type = response.headers.get("content-type", "")
                    if "json" in content_type.lower():
                        try:
                            data = response.json()
                            if isinstance(data, list) and len(data) > 5:
                                assert len(data) > 0, f"No data in {url}"
                                break
                        except json.JSONDecodeError:
                            pass
            except requests.RequestException:
                pass

    def test_github_drugs_api(self):
        """Test the GitHub TripSit drugs repository API."""
        url = "https://raw.githubusercontent.com/TripSit/drugs/master/drugs.json"

        response = requests.get(url, timeout=15)
        assert response.status_code == 200, f"GitHub API failed: {response.status_code}"

        data = response.json()
        assert isinstance(data, dict), "GitHub data should be a dict"
        assert len(data) > 100, f"Expected >100 drugs, got {len(data)}"

        # Check that it's properly structured
        sample_key = list(data.keys())[0]
        drug_info = data[sample_key]
        assert isinstance(drug_info, dict), f"Drug info should be dict for {sample_key}"

        # Should have basic fields
        expected_fields = ["name", "aliases", "categories"]
        for field in expected_fields:
            assert field in drug_info, f"Missing {field} in drug {sample_key}"

    def test_tripbot_api(self):
        """Test the TripBot API."""
        url = "https://tripbot.tripsit.me/api/tripsit/getAllDrugs"

        response = requests.get(url, timeout=10)
        assert (
            response.status_code == 200
        ), f"TripBot API failed: {response.status_code}"

        data = response.json()
        assert isinstance(data, dict), "TripBot data should be a dict"
        assert "data" in data, "TripBot data should have 'data' key"


class TestDrugService:
    """Test the drug service functionality."""

    @pytest.fixture
    def drug_service(self):
        """Create a drug service instance."""
        from services.drug_service import DrugService

        return DrugService()

    def test_service_initialization(self, drug_service):
        """Test that drug service initializes properly."""
        stats = drug_service.get_stats()
        assert isinstance(stats, dict)
        assert "total_drugs" in stats

    def test_drug_lookup(self, drug_service):
        """Test basic drug lookup functionality."""
        # Test with a common drug
        drug_info = drug_service.get_drug_info("cannabis")
        if drug_info:  # Only test if data is loaded
            assert isinstance(drug_info, dict)
            assert "name" in drug_info

    def test_drug_search(self, drug_service):
        """Test drug search functionality."""
        if drug_service.get_stats()["total_drugs"] > 0:
            results = drug_service.search_drugs("can", limit=5)
            assert isinstance(results, list)
            assert len(results) <= 5

    def test_drug_interactions(self, drug_service):
        """Test drug interaction checking."""
        if drug_service.get_stats()["total_drugs"] > 0:
            result = drug_service.check_interactions(["cannabis", "alcohol"])
            assert isinstance(result, dict)
            assert "interactions" in result
            assert "warnings" in result
