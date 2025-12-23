"""
Tests for Alko Service

This module contains comprehensive tests for the Alko service functionality,
including file downloading, parsing, caching, and product searching.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# Import the service we're testing
from services.alko_service import AlkoService, create_alko_service


class TestAlkoService:
    """Test cases for AlkoService functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create a temporary directory for test data
        self.temp_dir = tempfile.mkdtemp()
        self.data_dir = self.temp_dir

        # Create mock Excel data
        self.mock_excel_path = (
            Path(self.temp_dir) / "alkon-hinnasto-tekstitiedostona.xlsx"
        )

        return self.data_dir

    def teardown_method(self):
        """Clean up test fixtures."""
        # Clean up temporary directory
        import shutil

        if hasattr(self, "temp_dir") and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_init_creates_data_directory(self):
        """Test that AlkoService creates data directory on initialization."""
        service = AlkoService(data_dir=self.data_dir)

        # Check that data directory was created
        assert os.path.exists(self.data_dir)
        assert os.path.isdir(self.data_dir)

    def test_init_sets_default_paths(self):
        """Test that AlkoService sets correct default paths."""
        service = AlkoService(data_dir=self.data_dir)

        # Check default paths
        expected_excel_path = (
            Path(self.data_dir) / "alkon-hinnasto-tekstitiedostona.xlsx"
        )
        expected_cache_path = Path(self.data_dir) / "alko_cache.json"

        assert (
            service.excel_url
            == "https://www.alko.fi/INTERSHOP/static/WFS/Alko-OnlineShop-Site/-/Alko-OnlineShop/fi_FI/Alkon%20Hinnasto%20Tekstitiedostona/alkon-hinnasto-tekstitiedostona.xlsx"
        )
        assert service.local_excel_path == expected_excel_path
        assert service.cache_file == expected_cache_path

    def test_should_download_file_when_no_local_file(self):
        """Test that service should download when no local file exists."""
        service = AlkoService(data_dir=self.data_dir)

        # Mock remote file info to indicate file should be downloaded
        with patch.object(service, "_get_remote_file_info") as mock_get_info:
            mock_get_info.return_value = {
                "content_length": 1000,
                "last_modified": "Wed, 01 Jan 2023 12:00:00 GMT",
            }

            # Mock download to succeed
            with patch.object(service, "_download_excel_file") as mock_download:
                mock_download.return_value = True

                result = service._should_download_file()

                assert result is True
                mock_get_info.assert_called_once()

    def test_should_not_download_when_local_file_exists_and_same_size(self):
        """Test that service should not download when local file exists with same size."""
        service = AlkoService(data_dir=self.data_dir)

        # Create a mock local file
        self.mock_excel_path.touch()
        self.mock_excel_path.write_bytes(b"mock content" * 100)

        with patch.object(service, "_get_remote_file_info") as mock_get_info:
            mock_get_info.return_value = {
                "content_length": 1000,  # Same size as local
                "last_modified": "Wed, 01 Jan 2023 12:00:00 GMT",
            }

            result = service._should_download_file()

            assert result is False
            mock_get_info.assert_called_once()

    def test_should_download_when_local_file_exists_but_different_size(self):
        """Test that service should download when local file exists but size differs."""
        service = AlkoService(data_dir=self.data_dir)

        # Create a mock local file with different size
        self.mock_excel_path.touch()
        self.mock_excel_path.write_bytes(b"mock content" * 500)  # Different size

        with patch.object(service, "_get_remote_file_info") as mock_get_info:
            mock_get_info.return_value = {
                "content_length": 1000,  # Different size
                "last_modified": "Wed, 01 Jan 2023 12:00:00 GMT",
            }

            result = service._should_download_file()

            assert result is True
            mock_get_info.assert_called_once()

    def test_download_excel_file_success(self):
        """Test successful Excel file download."""
        service = AlkoService(data_dir=self.data_dir)

        with patch.object(service, "_get_remote_file_info") as mock_get_info:
            mock_get_info.return_value = {
                "content_length": 1000,
                "last_modified": "Wed, 01 Jan 2023 12:00:00 GMT",
            }

            with patch("requests.get") as mock_get:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.iter_content = lambda: [b"test content"]

                mock_get.return_value = mock_response

                result = service._download_excel_file()

                assert result is True
                mock_get.assert_called_once_with(
                    service.excel_url, timeout=60, stream=True
                )

    def test_download_excel_file_failure(self):
        """Test Excel file download failure."""
        service = AlkoService(data_dir=self.data_dir)

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_get.return_value = mock_response

            result = service._download_excel_file()

            assert result is False
            mock_get.assert_called_once_with(service.excel_url, timeout=60, stream=True)

    def test_parse_bottle_size_various_formats(self):
        """Test parsing bottle size from various formats."""
        service = AlkoService(data_dir=self.data_dir)

        # Test various formats
        test_cases = [
            ("0.33 l", 0.33),
            ("33 cl", 0.33),
            ("330 ml", 0.33),
            ("0.5", 0.5),  # Default to liters
            ("1.5", 1.5),
        ]

        for size_str, expected in test_cases:
            result = service._parse_bottle_size(size_str)
            assert (
                result == expected
            ), f"Failed to parse '{size_str}': expected {expected}, got {result}"

    def test_parse_bottle_size_invalid_formats(self):
        """Test parsing bottle size from invalid formats."""
        service = AlkoService(data_dir=self.data_dir)

        # Test invalid formats
        invalid_cases = ["invalid", "", "abc ml", "0.5 cl"]

        for size_str in invalid_cases:
            result = service._parse_bottle_size(size_str)
            assert result is None, f"Expected None for '{size_str}', got {result}"

    def test_parse_alcohol_percent_valid_formats(self):
        """Test parsing alcohol percentage from various formats."""
        service = AlkoService(data_dir=self.data_dir)

        # Test various formats
        test_cases = [
            ("4.7%", 4.7),
            ("4,7%", 4.7),  # European decimal separator
            ("12.5", 12.5),
            ("40", 40.0),  # No percentage sign
            ("15.0 %", 15.0),  # With space and % sign
        ]

        for alcohol_str, expected in test_cases:
            result = service._parse_alcohol_percent(alcohol_str)
            assert (
                result == expected
            ), f"Failed to parse '{alcohol_str}': expected {expected}, got {result}"

    def test_parse_alcohol_percent_invalid_formats(self):
        """Test parsing alcohol percentage from invalid formats."""
        service = AlkoService(data_dir=self.data_dir)

        # Test invalid formats
        invalid_cases = ["invalid", "", "abc%", "not a number", "40.%", "15.0.0"]

        for alcohol_str in invalid_cases:
            result = service._parse_alcohol_percent(alcohol_str)
            assert result is None, f"Expected None for '{alcohol_str}', got {result}"

    def test_create_alko_service_factory(self):
        """Test the factory function creates AlkoService instance."""
        service = create_alko_service()

        assert isinstance(service, AlkoService)
        assert service.data_dir == "data"  # Default value

    def test_get_product_info_with_no_cache(self):
        """Test get_product_info when no cache is available."""
        service = AlkoService(data_dir=self.data_dir)
        service.products_cache = None

        result = service.get_product_info("test query")

        assert result is None
        assert service.products_cache is None

    def test_get_product_info_with_cache(self):
        """Test get_product_info with cached products."""
        service = AlkoService(data_dir=self.data_dir)

        # Mock cached products
        mock_products = [
            {
                "name": "Test Beer",
                "bottle_size": 0.33,
                "alcohol_percent": 4.7,
                "alcohol_grams": 10.8,
                "price": 5.50,
            },
            {
                "name": "Test Wine",
                "bottle_size": 0.75,
                "alcohol_percent": 12.0,
                "alcohol_grams": 71.1,
                "price": 12.90,
            },
        ]
        service.products_cache = mock_products

        # Test exact match
        result = service.get_product_info("Test Beer")
        assert result == mock_products[0]

        # Test case-insensitive partial match
        result = service.get_product_info("beer")
        assert result == mock_products[0]  # First match

        # Test no match
        result = service.get_product_info("nonexistent")
        assert result is None

    def test_search_products_with_no_cache(self):
        """Test search_products when no cache is available."""
        service = AlkoService(data_dir=self.data_dir)
        service.products_cache = None

        result = service.search_products("test query")

        assert result == []
        assert service.products_cache is None

    def test_search_products_with_cache(self):
        """Test search_products with cached products."""
        service = AlkoService(data_dir=self.data_dir)

        # Mock cached products
        mock_products = [
            {
                "name": "Test Beer",
                "bottle_size": 0.33,
                "alcohol_percent": 4.7,
                "alcohol_grams": 10.8,
                "price": 5.50,
            },
            {
                "name": "Testing Beer",
                "bottle_size": 0.33,
                "alcohol_percent": 4.7,
                "alcohol_grams": 10.8,
                "price": 5.50,
            },
            {
                "name": "Wine Test",
                "bottle_size": 0.75,
                "alcohol_percent": 12.0,
                "alcohol_grams": 71.1,
                "price": 12.90,
            },
        ]
        service.products_cache = mock_products

        # Test exact match
        result = service.search_products("Test Beer")
        assert len(result) == 1
        assert result[0] == mock_products[0]

        # Test partial match (case-insensitive)
        result = service.search_products("beer")
        assert len(result) == 2  # Both "Test Beer" and "Testing Beer" match
        assert result[0] == mock_products[0]
        assert result[1] == mock_products[1]

        # Test limit parameter
        result = service.search_products("test", limit=1)
        assert len(result) == 1

        # Test no match
        result = service.search_products("nonexistent")
        assert result == []

    def test_format_product_info_complete(self):
        """Test format_product_info with complete product data."""
        service = AlkoService(data_dir=self.data_dir)

        product = {
            "name": "Test Beer",
            "bottle_size_raw": "0.33 l",
            "bottle_size": 0.33,
            "alcohol_percent": 4.7,
            "alcohol_grams": 10.8,
            "price": 5.50,
        }

        result = service.format_product_info(product)

        # Check that all expected parts are present
        assert "🍺 Test Beer" in result
        assert "Pullokoko: 0.33 l" in result
        assert "Alkoholi: 4.7%" in result
        assert "Alkoholia: 10.8g" in result
        assert "Hinta: 5.50€" in result

    def test_format_product_info_partial(self):
        """Test format_product_info with partial product data."""
        service = AlkoService(data_dir=self.data_dir)

        # Test with missing optional fields
        product = {
            "name": "Test Beer",
            "bottle_size": 0.33,
            "alcohol_percent": 4.7,
            "alcohol_grams": 10.8,
            # Missing price, bottle_size_raw
        }

        result = service.format_product_info(product)

        # Check that available fields are present
        assert "🍺 Test Beer" in result
        assert "Pullokoko: 0.33 l" in result
        assert "Alkoholi: 4.7%" in result
        assert "Alkoholia: 10.8g" in result
        # Should not include price info
        assert "Hinta:" not in result
        assert "Pullokoko:" not in result

    def test_format_product_info_minimal(self):
        """Test format_product_info with minimal product data."""
        service = AlkoService(data_dir=self.data_dir)

        product = {
            "name": "Test Beer",
            # Only required fields
        }

        result = service.format_product_info(product)

        # Should only show name
        assert result == "🍺 Test Beer"

    def test_update_data_forces_download(self):
        """Test that update_data forces download when cache is empty."""
        service = AlkoService(data_dir=self.data_dir)
        service.products_cache = None

        with patch.object(service, "_should_download_file") as mock_should:
            mock_should.return_value = True

            with patch.object(service, "_download_excel_file") as mock_download:
                mock_download.return_value = True

                with patch.object(service, "_parse_excel_file") as mock_parse:
                    mock_parse.return_value = [{"name": "Test Product"}]

                    result = service.update_data(force=True)

                    assert result is True
                    mock_should.assert_called_once()
                    mock_download.assert_called_once()
                    mock_parse.assert_called_once()

    def test_update_data_skips_download_when_unchanged(self):
        """Test that update_data skips download when file is unchanged."""
        service = AlkoService(data_dir=self.data_dir)
        service.products_cache = [{"name": "Cached Product"}]

        with patch.object(service, "_should_download_file") as mock_should:
            mock_should.return_value = False  # File unchanged

            result = service.update_data(force=False)

            assert result is False  # No update needed
            mock_should.assert_called_once()

    def test_get_stats(self):
        """Test get_stats method."""
        service = AlkoService(data_dir=self.data_dir)

        # Create mock files
        self.mock_excel_path.touch()
        self.mock_excel_path.write_bytes(b"mock content" * 100)

        # Create cache file with mock data
        cache_file = Path(self.data_dir) / "alko_cache.json"
        with open(cache_file, "w") as f:
            json.dump(
                {
                    "products": [{"name": "Test Product"}],
                    "last_updated": "2023-01-01T12:00:00",
                },
                f,
            )

        result = service.get_stats()

        assert result["total_products"] == 1
        assert result["file_exists"] is True
        assert result["file_size"] > 0
        assert result["last_modified"] is not None
        assert result["cache_file"] == str(cache_file)

    def test_save_and_load_cache(self):
        """Test cache saving and loading."""
        service = AlkoService(data_dir=self.data_dir)

        # Mock products
        mock_products = [{"name": "Test Product"}]
        service.products_cache = mock_products

        # Save cache
        service._save_cache()

        # Create new service instance to test loading
        new_service = AlkoService(data_dir=self.data_dir)
        new_service._load_cache()

        assert new_service.products_cache == mock_products

    def test_alcohol_calculation(self):
        """Test alcohol content calculation."""
        service = AlkoService(data_dir=self.data_dir)

        # Test cases: volume(L) * 0.789 g/mL * alcohol% / 100 * 1000 mL/L
        test_cases = [
            (0.33, 4.7, 10.8),  # 0.33L * 0.789 * 4.7% * 10 = 12.3g
            (0.75, 12.0, 71.1),  # 0.75L * 0.789 * 12.0% * 10 = 71.1g
            (1.0, 40.0, 315.6),  # 1.0L * 0.789 * 40.0% * 10 = 315.6g
        ]

        for volume, alcohol_percent, expected_grams in test_cases:
            # Calculate using the service's method (internally)
            product_info = {"bottle_size": volume, "alcohol_percent": alcohol_percent}
            service._parse_product_row(
                {"Name": "Test"}
            )  # This will calculate alcohol_grams

            # Get the calculated value from the service
            calculated_grams = product_info.get("alcohol_grams")

            assert (
                calculated_grams == expected_grams
            ), f"For {volume}L at {alcohol_percent}%: expected {expected_grams}g, got {calculated_grams}g"

    @patch("pandas.read_excel")
    def test_parse_excel_file_with_mock_data(self, mock_read_excel):
        """Test Excel file parsing with mock data."""
        service = AlkoService(data_dir=self.data_dir)

        # Mock DataFrame to simulate Excel data
        mock_df = MagicMock()
        mock_df.__len__ = MagicMock(return_value=2)
        mock_df.__getitem__ = MagicMock(return_value=MagicMock())
        mock_df.__iter__ = MagicMock(
            return_value=iter(
                [
                    {
                        "Nimi": "Test Beer 1",
                        "Pullokoko": "0.33 l",
                        "Alkoholiprosentti": "4.7%",
                    },
                    {
                        "Nimi": "Test Wine 1",
                        "Pullokoko": "0.75 l",
                        "Alkoholiprosentti": "12.0%",
                    },
                ]
            )
        )
        mock_row = {
            "Nimi": "Test Beer 1",
            "Pullokoko": "0.33 l",
            "Alkoholiprosentti": "4.7%",
        }

        # Configure mock to return our test data
        mock_read_excel.return_value = mock_df

        result = service._parse_excel_file()

        # Verify parsing was called
        mock_read_excel.assert_called_once_with(
            self.mock_excel_path, sheet_name=0, header=0
        )

        # Verify results
        assert len(result) == 2
        assert result[0]["name"] == "Test Beer 1"
        assert result[0]["bottle_size"] == 0.33
        assert result[0]["alcohol_percent"] == 4.7
        assert result[0]["alcohol_grams"] == 10.8

    def test_parse_excel_file_missing_file(self):
        """Test Excel file parsing when file doesn't exist."""
        service = AlkoService(data_dir=self.data_dir)

        result = service._parse_excel_file()

        assert result is None

    @patch("pandas.read_excel")
    def test_parse_excel_file_read_error(self, mock_read_excel):
        """Test Excel file parsing when read raises exception."""
        service = AlkoService(data_dir=self.data_dir)

        # Configure mock to raise exception
        mock_read_excel.side_effect = Exception("Read error")

        result = service._parse_excel_file()

        assert result is None

    def test_search_products_case_insensitive(self):
        """Test that search_products is case-insensitive."""
        service = AlkoService(data_dir=self.data_dir)

        # Mock cached products with different cases
        mock_products = [
            {"name": "Lapin Kulta", "bottle_size": 0.33, "alcohol_percent": 5.5},
            {"name": "KOSKENKORVA", "bottle_size": 0.40, "alcohol_percent": 8.0},
            {"name": "Karhu", "bottle_size": 0.50, "alcohol_percent": 4.6},
        ]
        service.products_cache = mock_products

        # Test various case combinations
        test_cases = [
            ("lapin kulta", ["Lapin Kulta"]),  # Exact match
            ("LAPIN KULTA", ["Lapin Kulta"]),  # Upper case
            ("lapin", ["Lapin Kulta", "KOSKENKORVA"]),  # Partial match
            ("karhu", ["Karhu"]),  # Exact match
            ("KARHU", ["Karhu"]),  # Upper case
            ("unknown", []),  # No match
        ]

        for query, expected_matches in test_cases:
            result = service.search_products(query, limit=10)

            assert len(result) == len(expected_matches)
            for match in expected_matches:
                assert (
                    match in result
                ), f"Expected '{match}' in results for query '{query}'"

    def test_update_data_cache_miss_persistence(self):
        """Test that update_data properly saves cache."""
        service = AlkoService(data_dir=self.data_dir)

        with patch.object(service, "_should_download_file") as mock_should:
            with patch.object(service, "_download_excel_file") as mock_download:
                with patch.object(service, "_parse_excel_file") as mock_parse:
                    mock_should.return_value = True
                    mock_download.return_value = True
                    mock_parse.return_value = [{"name": "Test Product"}]

                    service.update_data(force=True)

                    # Verify cache was saved
                    service._save_cache.assert_called_once()

                    # Create new service instance to verify persistence
                    new_service = AlkoService(data_dir=self.data_dir)
                    new_service._load_cache.assert_called_once()
                    assert new_service.products_cache == [{"name": "Test Product"}]

    def test_integration_with_real_service(self):
        """Integration test with real service creation and basic operations."""
        # This test verifies the service can be instantiated and basic methods work
        service = create_alko_service()

        # Test that service is properly initialized
        assert service is not None
        assert hasattr(service, "excel_url")
        assert hasattr(service, "local_excel_path")
        assert hasattr(service, "cache_file")

        # Test that default methods don't crash
        try:
            service.get_stats()
            service.search_products("test")
            service.get_product_info("test")
            service.format_product_info({"name": "test"})
        except Exception as e:
            pytest.fail(f"Service methods should not raise exceptions: {e}")

    def test_error_handling(self):
        """Test error handling in service methods."""
        service = AlkoService(data_dir=self.data_dir)

        # Test with invalid data that should be handled gracefully
        try:
            # This should not crash
            result = service._parse_bottle_size("invalid format")
            assert result is None
        except Exception as e:
            pytest.fail(f"Unexpected exception in _parse_bottle_size: {e}")

        try:
            # This should not crash
            result = service._parse_alcohol_percent("invalid")
            assert result is None
        except Exception as e:
            pytest.fail(f"Unexpected exception in _parse_alcohol_percent: {e}")


if __name__ == "__main__":
    pytest.main([__file__])
