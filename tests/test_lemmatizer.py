#!/usr/bin/env python3
"""
Pytest tests for lemmatizer module.

Tests word lemmatization functionality with and without Voikko.
"""

import json
import os
import tempfile
from unittest.mock import Mock, patch

import pytest

from lemmatizer import Lemmatizer


class TestLemmatizer:
    """Test Lemmatizer class functionality."""

    def test_lemmatizer_initialization_no_voikko(self):
        """Test lemmatizer initialization when Voikko is not available."""
        with patch("lemmatizer.VOIKKO_AVAILABLE", False):
            lem = Lemmatizer()
            assert lem.voikko_enabled is False
            assert lem.v is None

    def test_lemmatizer_initialization_with_voikko(self):
        """Test lemmatizer initialization when Voikko is available."""
        # Skip if Voikko is not actually available
        pytest.importorskip("libvoikko")

        # Try to actually initialize Voikko to see if it works
        try:
            import libvoikko

            test_v = libvoikko.Voikko("fi")
            test_v.terminate()  # Clean up
            voikko_working = True
        except Exception:
            voikko_working = False

        if not voikko_working:
            pytest.skip(
                "Voikko library is installed but cannot be initialized (missing system library)"
            )

        with patch("lemmatizer.VOIKKO_AVAILABLE", True), patch(
            "libvoikko.Voikko"
        ) as mock_voikko_class:
            mock_voikko = Mock()
            mock_voikko_class.return_value = mock_voikko

            lem = Lemmatizer()
            assert lem.voikko_enabled is True
            assert lem.v == mock_voikko
            mock_voikko_class.assert_called_once_with("fi")

    def test_lemmatizer_initialization_voikko_error(self):
        """Test lemmatizer initialization when Voikko fails."""
        # Skip if Voikko is not installed at all
        pytest.importorskip("libvoikko")

        with patch("lemmatizer.VOIKKO_AVAILABLE", True), patch(
            "libvoikko.Voikko", side_effect=Exception("Voikko error")
        ):
            lem = Lemmatizer()
            assert lem.voikko_enabled is False
            assert lem.v is None

    def test_simple_normalize_basic(self):
        """Test basic simple normalization."""
        lem = Lemmatizer()
        lem.voikko_enabled = False  # Force simple normalization

        # Test basic cases
        assert lem._simple_normalize("Kissa") == "kissa"
        assert (
            lem._simple_normalize("KOIRA") == "koi"
        )  # "koira" -> ends with "ra", remove 2 chars
        assert lem._simple_normalize("musta") == "musta"

    def test_simple_normalize_short_words(self):
        """Test simple normalization with short words."""
        lem = Lemmatizer()
        lem.voikko_enabled = False

        # Short words should be returned as-is
        assert lem._simple_normalize("a") == "a"
        assert lem._simple_normalize("on") == "on"

    def test_simple_normalize_plural_endings(self):
        """Test simple normalization with plural endings."""
        lem = Lemmatizer()
        lem.voikko_enabled = False

        # Test plural endings
        assert lem._simple_normalize("kissojen") == "kisso"
        assert lem._simple_normalize("koirien") == "koir"
        assert lem._simple_normalize("talojen") == "talo"

    def test_simple_normalize_case_endings(self):
        """Test simple normalization with case endings."""
        lem = Lemmatizer()
        lem.voikko_enabled = False

        # Test case endings
        assert lem._simple_normalize("kissalla") == "kissa"
        assert lem._simple_normalize("talossa") == "talo"
        assert (
            lem._simple_normalize("koirasta") == "koira"
        )  # "koirasta" ends with "sta", len > 5, remove 3 chars

    def test_simple_normalize_other_endings(self):
        """Test simple normalization with other common endings."""
        lem = Lemmatizer()
        lem.voikko_enabled = False

        # Test other endings
        assert (
            lem._simple_normalize("kissana") == "kissa"
        )  # "kissana" ends with "na", len > 4, remove 2 chars
        assert lem._simple_normalize("talona") == "talo"
        assert lem._simple_normalize("koirana") == "koira"

    def test_simple_normalize_single_letters(self):
        """Test simple normalization with single letter endings."""
        lem = Lemmatizer()
        lem.voikko_enabled = False

        # Test single letter endings (should be preserved for longer words)
        assert lem._simple_normalize("kissalla") == "kissa"
        assert (
            lem._simple_normalize("omena") == "ome"
        )  # "omena" ends with "na", len > 4, remove 2 chars

    def test_get_baseform_with_voikko(self):
        """Test getting base form when Voikko is available."""
        lem = Lemmatizer()
        lem.voikko_enabled = True
        lem.v = Mock()

        # Mock Voikko analysis
        lem.v.analyze.return_value = [{"BASEFORM": "kissa"}]

        result = lem._get_baseform("kissoja")
        assert result == "kissa"
        lem.v.analyze.assert_called_once_with("kissoja")

    def test_get_baseform_voikko_no_analysis(self):
        """Test getting base form when Voikko returns no analysis."""
        lem = Lemmatizer()
        lem.voikko_enabled = True
        lem.v = Mock()
        lem.v.analyze.return_value = []

        result = lem._get_baseform("UNKNOWN")
        assert result == "unknown"  # Should return word.lower()

    def test_get_baseform_voikko_error(self):
        """Test getting base form when Voikko raises an exception."""
        lem = Lemmatizer()
        lem.voikko_enabled = True
        lem.v = Mock()
        lem.v.analyze.side_effect = Exception("Voikko error")

        result = lem._get_baseform("kissoja")
        assert result == "kissoj"  # Should fall back to simple normalization

    def test_get_baseform_simple_fallback(self):
        """Test getting base form using simple normalization fallback."""
        lem = Lemmatizer()
        lem.voikko_enabled = False

        result = lem._get_baseform("KISSOJA")
        assert result == "kissoj"  # Should use simple normalization

    def test_get_filename(self):
        """Test filename generation for server data."""
        lem = Lemmatizer()

        # Test with normal server name
        filename = lem._get_filename("irc.example.com")
        # Just check that it contains the expected parts
        assert "irc.example.com_words.json" in filename

    def test_get_filename_special_chars(self):
        """Test filename generation with special characters."""
        lem = Lemmatizer()

        filename = lem._get_filename("irc.example.com:6667")
        assert "irc.example.com_6667_words.json" in filename

    def test_load_data_existing_file(self):
        """Test loading data from existing file."""
        lem = Lemmatizer()

        # Create temporary test data
        test_data = {"#channel": {"hello": 5, "world": 3}, "user1": {"test": 2}}

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test file
            test_file = os.path.join(temp_dir, "test_server_words.json")
            with open(test_file, "w", encoding="utf-8") as f:
                json.dump(test_data, f)

            # Mock the filename generation
            lem._get_filename = Mock(return_value=test_file)

            result = lem._load_data("test_server")

            # Should return defaultdicts
            assert "#channel" in result
            assert result["#channel"]["hello"] == 5
            assert result["#channel"]["world"] == 3
            assert "user1" in result
            assert result["user1"]["test"] == 2

    def test_load_data_nonexistent_file(self):
        """Test loading data when file doesn't exist."""
        lem = Lemmatizer()

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = os.path.join(temp_dir, "nonexistent_words.json")
            lem._get_filename = Mock(return_value=test_file)

            result = lem._load_data("nonexistent")

            # Should return empty defaultdict
            assert len(result) == 0
            # Test that it's a defaultdict
            assert result["new_key"]["new_word"] == 0

    def test_save_data(self):
        """Test saving data to file."""
        lem = Lemmatizer()

        from collections import defaultdict

        test_data = defaultdict(lambda: defaultdict(int))
        test_data["#channel"]["hello"] = 5
        test_data["#channel"]["world"] = 3
        test_data["user1"]["test"] = 2

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = os.path.join(temp_dir, "test_save_words.json")
            lem._get_filename = Mock(return_value=test_file)

            lem._save_data("test_server", test_data)

            # Verify file was created and contains correct data
            assert os.path.exists(test_file)

            with open(test_file, "r", encoding="utf-8") as f:
                saved_data = json.load(f)

            assert "#channel" in saved_data
            assert saved_data["#channel"]["hello"] == 5
            assert saved_data["#channel"]["world"] == 3
            assert "user1" in saved_data
            assert saved_data["user1"]["test"] == 2

    def test_process_message_basic(self):
        """Test basic message processing."""
        lem = Lemmatizer()

        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock file operations
            test_file = os.path.join(temp_dir, "test_process_words.json")
            lem._get_filename = Mock(return_value=test_file)

            # Mock load/save to avoid file I/O
            lem._load_data = Mock(return_value={"#test": {"old": 1}})
            lem._save_data = Mock()

            result = lem.process_message("Hello world test", "test_server", "#test")

            # Should return word counts including new words
            assert "hello" in result
            assert "world" in result
            assert "test" in result
            assert result["old"] == 1  # Existing word should be preserved

    def test_process_message_no_words(self):
        """Test message processing with no recognizable words."""
        lem = Lemmatizer()

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = os.path.join(temp_dir, "test_empty_words.json")
            lem._get_filename = Mock(return_value=test_file)

            lem._load_data = Mock(return_value={})
            lem._save_data = Mock()

            result = lem.process_message("!!! 123 ...", "test_server", "#test")

            # Should return empty or minimal result
            assert isinstance(result, dict)

    def test_get_total_counts(self):
        """Test getting total word counts across all sources."""
        lem = Lemmatizer()

        # Mock load_data to return test data
        mock_data = {
            "#channel1": {"hello": 2, "world": 1},
            "#channel2": {"hello": 3, "test": 1},
            "user1": {"world": 2},
        }
        lem._load_data = Mock(return_value=mock_data)

        result = lem.get_total_counts("test_server")

        # Should aggregate counts
        assert result["hello"] == 5  # 2 + 3
        assert result["world"] == 3  # 1 + 2
        assert result["test"] == 1

        # Should be sorted by frequency (descending)
        assert list(result.keys())[:3] == ["hello", "world", "test"]

    def test_get_counts_for_source(self):
        """Test getting word counts for a specific source."""
        lem = Lemmatizer()

        mock_data = {
            "#channel1": {"hello": 2, "world": 1},
            "#channel2": {"test": 1},
        }
        lem._load_data = Mock(return_value=mock_data)

        result = lem.get_counts_for_source("test_server", "#channel1")

        assert result["hello"] == 2
        assert result["world"] == 1
        assert "test" not in result

    def test_get_counts_for_source_not_found(self):
        """Test getting word counts for non-existent source."""
        lem = Lemmatizer()

        mock_data = {"#channel1": {"hello": 2}}
        lem._load_data = Mock(return_value=mock_data)

        result = lem.get_counts_for_source("test_server", "#nonexistent")

        assert result == {}

    def test_get_top_words(self):
        """Test getting top N words."""
        lem = Lemmatizer()

        # Mock get_total_counts
        lem.get_total_counts = Mock(
            return_value={"word1": 10, "word2": 8, "word3": 6, "word4": 4, "word5": 2}
        )

        result = lem.get_top_words("test_server", 3)

        assert len(result) == 3
        assert result[0] == ("word1", 10)
        assert result[1] == ("word2", 8)
        assert result[2] == ("word3", 6)

    def test_get_top_words_default_limit(self):
        """Test getting top words with default limit."""
        lem = Lemmatizer()

        lem.get_total_counts = Mock(return_value={"word1": 1})

        result = lem.get_top_words("test_server")

        assert len(result) == 1
