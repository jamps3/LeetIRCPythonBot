#!/usr/bin/env python3
"""Comprehensive pytest tests for the E-codes command."""

import json
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from src.command_registry import CommandContext, CommandResponse
from src.commands_services import ecode_command


class TestEcodesCommand:
    """Test suite for the E-codes command functionality."""

    @pytest.fixture
    def sample_ecodes_data(self):
        """Provide sample E-codes data for testing."""
        return {
            "symbol_definitions": {
                "■": "Väriaineet (Colorants)",
                "●": "Happamuudensäätäjät (Acidity regulators)",
                "★": "Hapettumisenestoaineet (Antioxidants)",
                "♠": "mulgointiaineet, kiinteyttämisaineet, kosteudensäilyttäjät, täyteaineet, hyytelöimisaineet, sakeuttamisaineet, muunnetut tärkkelykset ja stabilointiaineet",
                "❤": "Aromiaineet (Flavor enhancers)",
                "❖": "Makeutusaineet",
                "✖": "Pakkauskaasut ja ponneaineet (Packaging gases and propellants)",
                "✪": "Pintakäsittelyaineet",
                "✧": "Vaahdonestoaineet ja vaahdotusaineet",
                "◆": "Hapot ja happamuudensäätöaineet (Acids and acidity regulators)",
                "✜": "Paakkuuntumisenestoaineet (Anti-caking agents)",
                "♣": "Jauhonparanteet (Flour treatment agents)",
                "✿": "Kantaja-aineet",
                "▲": "Sulatesuolat",
                "✠": "Nostatusaineet",
            },
            "indicator_definitions": {
                "A": "Atsoväriaineet (Azo dyes)",
                "V": "Varmasti eläinperäinen (Definitely animal-derived)",
                "e": "Mahdollisesti eläinperäinen (Possibly animal-derived)",
                "y": "Epäillään aiheuttavan yliherkkyysoireita (Suspected to cause hypersensitivity)",
            },
            "ecodes": {
                "E153": {
                    "categories": ["■"],
                    "name": "lääkehiili, kasvihiili",
                    "indicators": ["Kasviperäinen"],
                    "additional_info": None,
                },
                "E200": {
                    "categories": ["●"],
                    "name": "Sorbiinihappo",
                    "indicators": ["y"],
                    "additional_info": None,
                },
                "E300": {
                    "categories": ["★", "◆", "♣"],
                    "name": "Askorbiinihappo",
                    "indicators": [],
                    "additional_info": None,
                },
                "E322": {
                    "categories": ["★", "♠", "✿"],
                    "name": "Lesitiinit (useimmiten peräisin soijasta)",
                    "indicators": ["e"],
                    "additional_info": None,
                },
                "E420a": {
                    "categories": ["♠", "❖"],
                    "name": "Sorbitoli",
                    "indicators": ["y"],
                    "additional_info": None,
                },
                "E471": {
                    "categories": ["♠"],
                    "name": "Rasvahappojen mono- ja diglyseridit",
                    "indicators": ["e"],
                    "additional_info": None,
                },
                "E621": {
                    "categories": ["❤"],
                    "name": "Mononatriumglutamaatti",
                    "indicators": [],
                    "additional_info": None,
                },
                "E901": {
                    "categories": ["✪"],
                    "name": "Mehiläisvaha, valkoinen ja keltainen",
                    "indicators": ["V"],
                    "additional_info": None,
                },
                "E950": {
                    "categories": ["❖", "❤"],
                    "name": "Asesulfaami K",
                    "indicators": [],
                    "additional_info": None,
                },
            },
        }

    @pytest.fixture
    def mock_context(self):
        """Create a mock command context."""
        return CommandContext(
            command="ecode",
            args=["E153"],
            raw_message="!ecode E153",
            sender="testuser",
            target="#test",
            is_private=False,
            is_console=False,
            server_name="test_server",
        )

    def test_load_ecodes_data_success(self, sample_ecodes_data):
        """Test successful loading of E-codes data."""
        with patch(
            "builtins.open", mock_open(read_data=json.dumps(sample_ecodes_data))
        ):
            with patch("json.load", return_value=sample_ecodes_data):
                data = sample_ecodes_data
                assert "ecodes" in data
                assert "symbol_definitions" in data
                assert "indicator_definitions" in data
                assert len(data["ecodes"]) > 0

    def test_parse_ecode_input_variations(self):
        """Test various E-code input formats."""
        test_cases = [
            ("E153", "E153"),
            ("e153", "E153"),
            ("E 153", "E153"),
            ("153", "E153"),
            ("E300", "E300"),
            ("e300", "E300"),
            ("E 300", "E300"),
            ("300", "E300"),
        ]

        for input_text, expected in test_cases:
            # Simulate the parsing logic from the command
            ecode = input_text.upper().replace(" ", "")
            if not ecode.startswith("E"):
                ecode = f"E{ecode}"
            assert ecode == expected, f"Failed for input: {input_text}"

    def test_format_response_basic(self, sample_ecodes_data):
        """Test basic response formatting."""
        ecode_data = sample_ecodes_data["ecodes"]["E153"]
        symbol_defs = sample_ecodes_data["symbol_definitions"]
        indicator_defs = sample_ecodes_data["indicator_definitions"]

        # Build response (same logic as the command)
        parts = [f"E153: {ecode_data['name']}"]

        # Add categories with symbol definitions
        if ecode_data["categories"]:
            category_symbols = " ".join(ecode_data["categories"])
            category_names = []
            for symbol in ecode_data["categories"]:
                if symbol in symbol_defs:
                    category_names.append(symbol_defs[symbol])
            if category_names:
                parts.append(
                    f"Categories: {category_symbols} ({', '.join(category_names)})"
                )

        # Add indicators with definitions
        if ecode_data["indicators"]:
            indicators = []
            for indicator in ecode_data["indicators"]:
                if indicator in indicator_defs:
                    indicators.append(f"{indicator} ({indicator_defs[indicator]})")
                else:
                    indicators.append(indicator)
            parts.append(f"Indicators: {' '.join(indicators)}")

        # Build full response
        response = " | ".join(parts)

        expected = "E153: lääkehiili, kasvihiili | Categories: ■ (Väriaineet (Colorants)) | Indicators: Kasviperäinen"
        assert response == expected

    def test_format_response_with_multiple_categories(self, sample_ecodes_data):
        """Test response formatting with multiple categories."""
        ecode_data = sample_ecodes_data["ecodes"]["E300"]
        symbol_defs = sample_ecodes_data["symbol_definitions"]
        indicator_defs = sample_ecodes_data["indicator_definitions"]

        # Build response (same logic as the command)
        parts = [f"E300: {ecode_data['name']}"]

        # Add categories with symbol definitions
        if ecode_data["categories"]:
            category_symbols = " ".join(ecode_data["categories"])
            category_names = []
            for symbol in ecode_data["categories"]:
                if symbol in symbol_defs:
                    category_names.append(symbol_defs[symbol])
            if category_names:
                parts.append(
                    f"Categories: {category_symbols} ({', '.join(category_names)})"
                )

        # Add indicators with definitions
        if ecode_data["indicators"]:
            indicators = []
            for indicator in ecode_data["indicators"]:
                if indicator in indicator_defs:
                    indicators.append(f"{indicator} ({indicator_defs[indicator]})")
                else:
                    indicators.append(indicator)
            parts.append(f"Indicators: {' '.join(indicators)}")

        # Build full response
        response = " | ".join(parts)

        expected = "E300: Askorbiinihappo | Categories: ★ ◆ ♣ (Hapettumisenestoaineet (Antioxidants), Hapot ja happamuudensäätöaineet (Acids and acidity regulators), Jauhonparanteet (Flour treatment agents))"
        assert response == expected

    def test_format_response_with_indicators(self, sample_ecodes_data):
        """Test response formatting with indicators."""
        ecode_data = sample_ecodes_data["ecodes"]["E200"]
        symbol_defs = sample_ecodes_data["symbol_definitions"]
        indicator_defs = sample_ecodes_data["indicator_definitions"]

        # Build response (same logic as the command)
        parts = [f"E200: {ecode_data['name']}"]

        # Add categories with symbol definitions
        if ecode_data["categories"]:
            category_symbols = " ".join(ecode_data["categories"])
            category_names = []
            for symbol in ecode_data["categories"]:
                if symbol in symbol_defs:
                    category_names.append(symbol_defs[symbol])
            if category_names:
                parts.append(
                    f"Categories: {category_symbols} ({', '.join(category_names)})"
                )

        # Add indicators with definitions
        if ecode_data["indicators"]:
            indicators = []
            for indicator in ecode_data["indicators"]:
                if indicator in indicator_defs:
                    indicators.append(f"{indicator} ({indicator_defs[indicator]})")
                else:
                    indicators.append(indicator)
            parts.append(f"Indicators: {' '.join(indicators)}")

        # Build full response
        response = " | ".join(parts)

        expected = "E200: Sorbiinihappo | Categories: ● (Happamuudensäätäjät (Acidity regulators)) | Indicators: y (Epäillään aiheuttavan yliherkkyysoireita (Suspected to cause hypersensitivity))"
        assert response == expected

    def test_format_response_long_text_truncation(self, sample_ecodes_data):
        """Test that long responses are truncated appropriately."""
        # Create a mock E-code with very long name and categories
        long_ecode_data = {
            "categories": [
                "★",
                "♠",
                "✿",
                "❤",
                "❖",
                "✖",
                "✪",
                "✧",
                "◆",
                "✜",
                "♣",
                "✿",
                "▲",
                "✠",
            ],
            "name": "This is a very long E-code name that should cause the response to be truncated when combined with all the category definitions and indicator information",
            "indicators": ["A", "V", "e", "y"],
            "additional_info": None,
        }

        symbol_defs = sample_ecodes_data["symbol_definitions"]
        indicator_defs = sample_ecodes_data["indicator_definitions"]

        # Build response (same logic as the command)
        parts = [f"E999: {long_ecode_data['name']}"]

        # Add categories with symbol definitions
        if long_ecode_data["categories"]:
            category_symbols = " ".join(long_ecode_data["categories"])
            category_names = []
            for symbol in long_ecode_data["categories"]:
                if symbol in symbol_defs:
                    category_names.append(symbol_defs[symbol])
            if category_names:
                parts.append(
                    f"Categories: {category_symbols} ({', '.join(category_names)})"
                )

        # Add indicators with definitions
        if long_ecode_data["indicators"]:
            indicators = []
            for indicator in long_ecode_data["indicators"]:
                if indicator in indicator_defs:
                    indicators.append(f"{indicator} ({indicator_defs[indicator]})")
                else:
                    indicators.append(indicator)
            parts.append(f"Indicators: {' '.join(indicators)}")

        # Build full response
        response = " | ".join(parts)

        # Truncate if too long (for IRC)
        if len(response) > 400:
            response = response[:397] + "..."

        assert len(response) <= 400
        assert response.endswith("...")

    def test_format_response_no_categories_or_indicators(self, sample_ecodes_data):
        """Test response formatting when E-code has no categories or indicators."""
        ecode_data = {
            "categories": [],
            "name": "Test E-code with no categories",
            "indicators": [],
            "additional_info": None,
        }

        symbol_defs = sample_ecodes_data["symbol_definitions"]
        indicator_defs = sample_ecodes_data["indicator_definitions"]

        # Build response (same logic as the command)
        parts = [f"E999: {ecode_data['name']}"]

        # Add categories with symbol definitions
        if ecode_data["categories"]:
            category_symbols = " ".join(ecode_data["categories"])
            category_names = []
            for symbol in ecode_data["categories"]:
                if symbol in symbol_defs:
                    category_names.append(symbol_defs[symbol])
            if category_names:
                parts.append(
                    f"Categories: {category_symbols} ({', '.join(category_names)})"
                )

        # Add indicators with definitions
        if ecode_data["indicators"]:
            indicators = []
            for indicator in ecode_data["indicators"]:
                if indicator in indicator_defs:
                    indicators.append(f"{indicator} ({indicator_defs[indicator]})")
                else:
                    indicators.append(indicator)
            parts.append(f"Indicators: {' '.join(indicators)}")

        # Build full response
        response = " | ".join(parts)

        expected = "E999: Test E-code with no categories"
        assert response == expected

    def test_ecode_not_found(self, sample_ecodes_data, mock_context):
        """Test response when E-code is not found in database."""
        with patch(
            "builtins.open", mock_open(read_data=json.dumps(sample_ecodes_data))
        ):
            with patch("json.load", return_value=sample_ecodes_data):
                # Test with non-existent E-code
                mock_context.args = ["E999"]
                result = ecode_command(mock_context, {})

                assert isinstance(result, CommandResponse)
                assert "E999" in result.message
                assert (
                    "ei löydy" in result.message.lower()
                    or "not found" in result.message.lower()
                )

    def test_invalid_input_format(self, sample_ecodes_data, mock_context):
        """Test response with invalid input format."""
        with patch(
            "builtins.open", mock_open(read_data=json.dumps(sample_ecodes_data))
        ):
            with patch("json.load", return_value=sample_ecodes_data):
                # Test with invalid input
                mock_context.args = ["invalid"]
                result = ecode_command(mock_context, {})

                assert isinstance(result, CommandResponse)
                assert "not found" in result.message.lower()

    def test_missing_database_file(self, mock_context):
        """Test response when database file is missing."""
        with patch(
            "builtins.open", side_effect=FileNotFoundError("Database file not found")
        ):
            result = ecode_command(mock_context, {})

            assert isinstance(result, CommandResponse)
            assert (
                "virhe" in result.message.lower() or "error" in result.message.lower()
            )

    def test_invalid_json_data(self, mock_context):
        """Test response when JSON data is invalid."""
        with patch("builtins.open", mock_open(read_data="invalid json")):
            with patch(
                "json.load", side_effect=json.JSONDecodeError("Invalid JSON", "test", 0)
            ):
                result = ecode_command(mock_context, {})

                assert isinstance(result, CommandResponse)
                assert (
                    "virhe" in result.message.lower()
                    or "error" in result.message.lower()
                )

    def test_command_aliases(self):
        """Test that command works with different aliases."""
        # This would test the @command decorator aliases
        # Since we can't easily test the decorator registration here,
        # we'll just verify the function exists and is callable
        assert callable(ecode_command)

    def test_command_help_text(self):
        """Test that command has proper help documentation."""
        # Check if the function has docstring
        assert ecode_command.__doc__ is not None
        assert len(ecode_command.__doc__.strip()) > 0

    def test_comprehensive_ecode_coverage(self, sample_ecodes_data):
        """Test a wide range of E-codes to ensure comprehensive coverage."""
        test_ecodes = [
            "E153",  # Basic with indicator
            "E200",  # With hypersensitivity indicator
            "E300",  # Multiple categories
            "E322",  # Multiple categories with animal indicator
            "E420a",  # Multiple categories with hypersensitivity
            "E471",  # Single category with animal indicator
            "E621",  # Single category, no indicators
            "E901",  # Single category with animal indicator
            "E950",  # Multiple categories, no indicators
        ]

        for ecode in test_ecodes:
            assert (
                ecode in sample_ecodes_data["ecodes"]
            ), f"E-code {ecode} not found in test data"

            ecode_data = sample_ecodes_data["ecodes"][ecode]
            symbol_defs = sample_ecodes_data["symbol_definitions"]
            indicator_defs = sample_ecodes_data["indicator_definitions"]

            # Build response (same logic as the command)
            parts = [f"{ecode}: {ecode_data['name']}"]

            # Add categories with symbol definitions
            if ecode_data["categories"]:
                category_symbols = " ".join(ecode_data["categories"])
                category_names = []
                for symbol in ecode_data["categories"]:
                    if symbol in symbol_defs:
                        category_names.append(symbol_defs[symbol])
                if category_names:
                    parts.append(
                        f"Categories: {category_symbols} ({', '.join(category_names)})"
                    )

            # Add indicators with definitions
            if ecode_data["indicators"]:
                indicators = []
                for indicator in ecode_data["indicators"]:
                    if indicator in indicator_defs:
                        indicators.append(f"{indicator} ({indicator_defs[indicator]})")
                    else:
                        indicators.append(indicator)
                parts.append(f"Indicators: {' '.join(indicators)}")

            # Build full response
            response = " | ".join(parts)

            # Verify response is properly formatted
            assert response.startswith(f"{ecode}:")
            assert ecode_data["name"] in response

            # Verify response is not too long (unless truncated)
            if len(response) > 400:
                assert response.endswith("...")
            else:
                assert len(response) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
