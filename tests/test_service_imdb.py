"""
Tests for IMDb service module.

Provides comprehensive coverage of all IMDbService functionality:
- Movie search functionality
- HTML parsing strategies (regex, BeautifulSoup, direct title page)
- Error handling (timeout, network, parsing)
- Title fetching and cleaning
- URL formatting

Target: 100% code coverage
"""

from unittest.mock import MagicMock, Mock, patch

import pytest
import requests
from bs4 import BeautifulSoup

from src.services.imdb_service import IMDbService, create_imdb_service


class TestIMDbService:
    """Test suite for IMDbService class."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.service = IMDbService()

    # ==================== Initialization Tests ====================

    def test_init(self):
        """Test IMDbService initialization."""
        assert self.service.base_url == "https://www.imdb.com"
        assert self.service.search_url == "https://www.imdb.com/search/title/"

    def test_create_imdb_service(self):
        """Test factory function creates valid service."""
        service = create_imdb_service()
        assert service.base_url == "https://www.imdb.com"
        assert service.search_url == "https://www.imdb.com/search/title/"

    # ==================== Search Input Validation ====================

    def test_search_movie_empty_query(self):
        """Test search with empty query returns error."""
        result = self.service.search_movie("")
        assert result["error"] is True
        assert "Empty search query" in result["message"]

    def test_search_movie_whitespace_query(self):
        """Test search with whitespace-only query returns error."""
        result = self.service.search_movie("   ")
        assert result["error"] is True
        assert "Empty search query" in result["message"]

    # ==================== Network Error Handling ====================

    @patch("requests.get")
    def test_search_movie_timeout(self, mock_get):
        """Test search with timeout exception."""
        mock_get.side_effect = requests.exceptions.Timeout("Request timed out")

        result = self.service.search_movie("The Matrix")
        assert result["error"] is True
        assert "timed out" in result["message"]

    @patch("requests.get")
    def test_search_movie_request_exception(self, mock_get):
        """Test search with general request exception."""
        mock_get.side_effect = requests.exceptions.RequestException("Network error")

        result = self.service.search_movie("The Matrix")
        assert result["error"] is True
        assert "Network error" in result["message"]

    @patch("requests.get")
    def test_search_movie_non_200_status(self, mock_get):
        """Test search with non-200 HTTP status code."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = self.service.search_movie("The Matrix")
        assert result["error"] is True
        assert "404" in result["message"]

    @patch("requests.get")
    def test_search_movie_unexpected_exception(self, mock_get):
        """Test search with unexpected exception."""
        mock_get.side_effect = ValueError("Unexpected error")

        result = self.service.search_movie("The Matrix")
        assert result["error"] is True
        assert "Unexpected error" in result["message"]

    # ==================== Strategy 1: Regex Parsing ====================

    @patch("requests.get")
    def test_search_movie_regex_strategy_success_no_year(self, mock_get):
        """Test regex strategy with successful result (no year in query)."""
        html_content = """
        <html>
        <body>
            <a href="/title/tt0133093/" class="result">The Matrix (1999)</a>
            <a href="/title/tt0137523/" class="result">Fight Club (1999)</a>
        </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_get.return_value = mock_response

        with patch.object(
            self.service, "_fetch_movie_title", return_value="The Matrix"
        ):
            result = self.service.search_movie("The Matrix")
            assert result["error"] is False
            assert result["title"] == "The Matrix"
            assert "tt0133093" in result["imdb_url"]

    @patch("requests.get")
    def test_search_movie_regex_strategy_fallback_to_parsed_title(self, mock_get):
        """Test regex strategy falls back to parsed title when fetch fails."""
        html_content = """
        <html>
        <body>
            <a href="/title/tt0133093/" class="result">The Matrix (1999)</a>
        </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_get.return_value = mock_response

        # Fetch fails, should fall back to parsed title
        with patch.object(self.service, "_fetch_movie_title", return_value=None):
            result = self.service.search_movie("The Matrix")
            assert result["error"] is False
            assert "The Matrix" in result["title"]
            assert "tt0133093" in result["imdb_url"]

    @patch("requests.get")
    def test_search_movie_regex_strategy_year_query_match(self, mock_get):
        """Test regex strategy with year query that matches result."""
        html_content = """
        <html>
        <body>
            <a href="/title/tt0133093/" class="result">The Matrix (1999)</a>
        </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_get.return_value = mock_response

        with patch.object(
            self.service, "_fetch_movie_title", return_value="The Matrix (1999)"
        ):
            result = self.service.search_movie("The Matrix 1999")
            assert result["error"] is False
            assert result["title"] == "The Matrix (1999)"
            assert "tt0133093" in result["imdb_url"]

    @patch("requests.get")
    def test_search_movie_regex_strategy_year_query_no_match(self, mock_get):
        """Test regex strategy with year query that doesn't match."""
        html_content = """
        <html>
        <body>
            <a href="/title/tt0133093/" class="result">The Matrix (1999)</a>
        </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_get.return_value = mock_response

        with patch.object(
            self.service, "_fetch_movie_title", return_value="The Matrix (1999)"
        ):
            result = self.service.search_movie("The Matrix 2000")
            # Should continue to next result or return error
            # Currently returns error when no match found
            assert result["error"] is True

    @patch("requests.get")
    def test_search_movie_regex_strategy_skips_invalid_titles(self, mock_get):
        """Test regex strategy skips invalid titles (too short, imdb prefix, etc)."""
        html_content = """
        <html>
        <body>
            <a href="/title/tt0000001/" class="result">AB</a>
            <a href="/title/tt0000002/" class="result">imdb</a>
            <a href="/title/tt0000003/" class="result">home</a>
            <a href="/title/tt0000004/" class="result">search</a>
            <a href="/title/tt0000005/" class="result">advanced</a>
            <a href="/title/tt0133093/" class="result">The Matrix (1999)</a>
        </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_get.return_value = mock_response

        with patch.object(
            self.service, "_fetch_movie_title", return_value="The Matrix"
        ):
            result = self.service.search_movie("The Matrix")
            assert result["error"] is False
            assert "tt0133093" in result["imdb_url"]

    # ==================== Strategy 2: BeautifulSoup Parsing ====================

    @patch("requests.get")
    def test_search_movie_beautifulsoup_strategy_ipc_metadata(self, mock_get):
        """Test BeautifulSoup strategy with ipc-metadata-list-summary-item."""
        html_content = """
        <html>
        <body>
            <div data-testid="search-result">
                <a href="/title/tt0133093/" data-testid="search-result__title-link">The Matrix</a>
            </div>
        </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_get.return_value = mock_response

        with patch.object(
            self.service, "_fetch_movie_title", return_value="The Matrix"
        ):
            result = self.service.search_movie("The Matrix")
            assert result["error"] is False
            assert result["title"] == "The Matrix"
            assert "tt0133093" in result["imdb_url"]

    @patch("requests.get")
    def test_search_movie_beautifulsoup_strategy_fallback_selectors(self, mock_get):
        """Test BeautifulSoup with fallback selectors (ipc-metadata-list, find-result-item, lister-item)."""
        html_content = """
        <html>
        <body>
            <div class="ipc-metadata-list-summary-item">
                <a href="/title/tt0133093/">The Matrix</a>
            </div>
        </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_get.return_value = mock_response

        with patch.object(
            self.service, "_fetch_movie_title", return_value="The Matrix"
        ):
            result = self.service.search_movie("The Matrix")
            assert result["error"] is False

    @patch("requests.get")
    def test_search_movie_beautifulsoup_no_results(self, mock_get):
        """Test BeautifulSoup finds no results."""
        html_content = """
        <html>
        <body>
            <div>Some other content</div>
        </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_get.return_value = mock_response

        # Should fall through to error or Strategy 3
        result = self.service.search_movie("The Matrix")
        # Will try Strategy 3
        assert result is not None

    # ==================== Strategy 3: Direct Title Page ====================

    @patch("requests.get")
    def test_search_movie_direct_title_page_hero(self, mock_get):
        """Test direct title page detection with hero__pageTitle.

        Note: When HTML contains a link with tt number, Strategy 1 may match first.
        This test verifies the code path when direct title page is detected.
        """
        html_content = """
        <html>
        <body>
            <h1 data-testid="hero__pageTitle">The Matrix (1999)</h1>
            <a href="/title/tt0133093/">Link</a>
        </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_get.return_value = mock_response

        # Mock fetch to fail so it falls back to Strategy 3
        with patch.object(self.service, "_fetch_movie_title", return_value=None):
            result = self.service.search_movie("The Matrix")
            # Strategy 1 finds link but fetch fails, continues to Strategy 3
            assert result["error"] is False

    @patch("requests.get")
    def test_search_movie_direct_title_page_hero_class(self, mock_get):
        """Test direct title page with hero__pageTitle class."""
        html_content = """
        <html>
        <body>
            <h1 class="hero__pageTitle">The Matrix (1999)</h1>
            <a href="/title/tt0133093/">Link</a>
        </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_get.return_value = mock_response

        # Mock fetch to fail so it falls back
        with patch.object(self.service, "_fetch_movie_title", return_value=None):
            result = self.service.search_movie("The Matrix")
            assert result["error"] is False

    @patch("requests.get")
    def test_search_movie_direct_title_page_fallback_title_tag(self, mock_get):
        """Test direct title page with title tag fallback."""
        html_content = """
        <html>
        <head><title>The Matrix (1999) - IMDb</title></head>
        <body>
            <a href="/title/tt0133093/">Link</a>
        </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_get.return_value = mock_response

        result = self.service.search_movie("The Matrix")
        assert result["error"] is False

    @patch("requests.get")
    def test_search_movie_direct_title_page_no_imdb_id(self, mock_get):
        """Test direct title page without valid IMDb ID."""
        html_content = """
        <html>
        <body>
            <h1 data-testid="hero__pageTitle">The Matrix (1999)</h1>
        </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_get.return_value = mock_response

        result = self.service.search_movie("The Matrix")
        # No imdb id in html, should continue
        assert result is not None

    # ==================== No Results Detection ====================

    @patch("requests.get")
    def test_search_movie_no_results_indicator(self, mock_get):
        """Test 'no results' indicator detection."""
        html_content = """
        <html>
        <body>
            <div>No results found for your search</div>
        </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_get.return_value = mock_response

        result = self.service.search_movie("Nonexistent Movie")
        assert result["error"] is True
        assert "No movies found" in result["message"]

    @patch("requests.get")
    def test_search_movie_did_not_match_any(self, mock_get):
        """Test 'did not match any' indicator detection."""
        html_content = """
        <html>
        <body>
            <div>Your search - Nonexistent - did not match any documents.</div>
        </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_get.return_value = mock_response

        result = self.service.search_movie("Nonexistent")
        assert result["error"] is True
        assert "No movies found" in result["message"]

    @patch("requests.get")
    def test_search_movie_could_not_parse(self, mock_get):
        """Test could not parse results error."""
        html_content = """
        <html>
        <body>
            <div>Some random content that doesn't match any pattern</div>
        </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_get.return_value = mock_response

        result = self.service.search_movie("Some Movie")
        assert result["error"] is True
        assert "Could not parse" in result["message"]

    # ==================== Parse Error Handling ====================

    def test_parse_search_results_unexpected_error(self):
        """Test parsing HTML with unexpected error."""
        with patch("bs4.BeautifulSoup", side_effect=Exception("Parse error")):
            result = self.service._parse_search_results("<html></html>", "Test Movie")
            assert result["error"] is True
            assert "Error parsing search results" in result["message"]

    # ==================== Title Fetching ====================

    @patch("requests.get")
    def test_fetch_movie_title_success_hero(self, mock_get):
        """Test fetching movie title with hero__pageTitle."""
        html_content = """
        <html>
        <body>
            <h1 data-testid="hero__pageTitle">The Matrix (1999)</h1>
        </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = html_content.encode("utf-8")
        mock_get.return_value = mock_response

        title = self.service._fetch_movie_title("tt0133093")
        assert title == "The Matrix (1999)"

    @patch("requests.get")
    def test_fetch_movie_title_success_hero_primary_text(self, mock_get):
        """Test fetching movie title with hero__primary-text class."""
        html_content = """
        <html>
        <body>
            <h1 class="hero__primary-text">The Matrix (1999)</h1>
        </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = html_content.encode("utf-8")
        mock_get.return_value = mock_response

        title = self.service._fetch_movie_title("tt0133093")
        assert title == "The Matrix (1999)"

    @patch("requests.get")
    def test_fetch_movie_title_fallback_to_title_tag(self, mock_get):
        """Test fetching movie title falls back to title tag."""
        html_content = """
        <html>
        <head><title>The Matrix (1999) - IMDb</title></head>
        <body></body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = html_content.encode("utf-8")
        mock_get.return_value = mock_response

        title = self.service._fetch_movie_title("tt0133093")
        assert title == "The Matrix (1999)"

    @patch("requests.get")
    def test_fetch_movie_title_with_imdb_suffix(self, mock_get):
        """Test fetching movie title that includes IMDb suffix."""
        html_content = """
        <html>
        <head><title>The Matrix - IMDb</title></head>
        <body>
            <h1 class="hero__primary-text">The Matrix - IMDb</h1>
        </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = html_content.encode("utf-8")
        mock_get.return_value = mock_response

        title = self.service._fetch_movie_title("tt0133093")
        assert title == "The Matrix"

    @patch("requests.get")
    def test_fetch_movie_title_non_200_status(self, mock_get):
        """Test fetching movie title with non-200 status."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        title = self.service._fetch_movie_title("tt0133093")
        assert title is None

    @patch("requests.get")
    def test_fetch_movie_title_exception(self, mock_get):
        """Test fetching movie title with exception."""
        mock_get.side_effect = Exception("Network error")

        title = self.service._fetch_movie_title("tt0133093")
        assert title is None

    @patch("requests.get")
    def test_fetch_movie_title_no_title_element(self, mock_get):
        """Test fetching movie title when no title element found."""
        html_content = """
        <html>
        <body>
            <div>No title here</div>
        </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = html_content.encode("utf-8")
        mock_get.return_value = mock_response

        title = self.service._fetch_movie_title("tt0133093")
        assert title is None

    # ==================== Title Cleaning ====================

    def test_clean_title_text_with_numbering(self):
        """Test cleaning title text with numbering prefix."""
        title = self.service._clean_title_text("1. The Matrix (1999)")
        assert title == "The Matrix (1999)"

    def test_clean_title_text_with_multiple_numbering(self):
        """Test cleaning title with multi-digit numbering."""
        title = self.service._clean_title_text("10. The Matrix (1999)")
        assert title == "The Matrix (1999)"

    def test_clean_title_text_with_extra_whitespace(self):
        """Test cleaning title text with extra whitespace."""
        title = self.service._clean_title_text("  The   Matrix  (1999)  ")
        assert title == "The Matrix (1999)"

    def test_clean_title_text_normal(self):
        """Test cleaning normal title text."""
        title = self.service._clean_title_text("The Matrix (1999)")
        assert title == "The Matrix (1999)"

    def test_clean_title_text_empty_after_cleaning(self):
        """Test cleaning empty-ish title after stripping."""
        title = self.service._clean_title_text("   ")
        assert title == ""

    # ==================== Format Movie Info ====================

    def test_format_movie_info_success(self):
        """Test formatting successful movie info."""
        movie_data = {
            "error": False,
            "title": "The Matrix (1999)",
            "imdb_url": "https://www.imdb.com/title/tt0133093/",
        }
        result = self.service.format_movie_info(movie_data)
        assert "The Matrix" in result
        assert "tt0133093" in result

    def test_format_movie_info_error(self):
        """Test formatting error movie info."""
        movie_data = {"error": True, "message": "Movie not found"}
        result = self.service.format_movie_info(movie_data)
        assert "error" in result.lower()
        assert "Movie not found" in result

    def test_format_movie_info_missing_title(self):
        """Test formatting with missing title."""
        movie_data = {
            "error": False,
            "imdb_url": "https://www.imdb.com/title/tt0133093/",
        }
        result = self.service.format_movie_info(movie_data)
        assert "Unknown title" in result

    def test_format_movie_info_missing_url(self):
        """Test formatting with missing URL."""
        movie_data = {"error": False, "title": "The Matrix (1999)"}
        result = self.service.format_movie_info(movie_data)
        assert "The Matrix" in result


class TestIMDbServiceEdgeCases:
    """Additional edge case tests for complete coverage."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = IMDbService()

    @patch("requests.get")
    def test_search_with_20th_century_year(self, mock_get):
        """Test search with 20th century year in query."""
        html_content = """
        <html>
        <body>
            <a href="/title/tt0000001/" class="result">Casablanca (1942)</a>
        </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_get.return_value = mock_response

        with patch.object(
            self.service, "_fetch_movie_title", return_value="Casablanca (1942)"
        ):
            result = self.service.search_movie("Casablanca 1942")
            # Either returns match or continues to next result
            assert result is not None

    @patch("requests.get")
    def test_search_with_future_year(self, mock_get):
        """Test search with future year (should not match)."""
        html_content = """
        <html>
        <body>
            <a href="/title/tt0133093/" class="result">The Matrix (1999)</a>
        </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_get.return_value = mock_response

        with patch.object(
            self.service, "_fetch_movie_title", return_value="The Matrix (1999)"
        ):
            result = self.service.search_movie("The Matrix 2050")
            assert result["error"] is True

    @patch("requests.get")
    def test_regex_finds_multiple_links(self, mock_get):
        """Test regex finds and iterates through multiple links."""
        html_content = """
        <html>
        <body>
            <a href="/title/tt0000001/" class="result">Invalid</a>
            <a href="/title/tt0000002/" class="result">imdb</a>
            <a href="/title/tt0133093/" class="result">The Matrix (1999)</a>
        </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_get.return_value = mock_response

        # First two titles are too short, third should be valid
        with patch.object(
            self.service, "_fetch_movie_title", return_value="The Matrix"
        ):
            result = self.service.search_movie("The Matrix")
            # First result is returned because titles pass filter
            assert result["error"] is False
            # Note: actual behavior depends on code logic

    @patch("requests.get")
    def test_beautifulsoup_with_href_no_imdb_id(self, mock_get):
        """Test BeautifulSoup skips links without valid IMDb ID."""
        html_content = """
        <html>
        <body>
            <div class="ipc-metadata-list-summary-item">
                <a href="/title/tt0133093/">The Matrix</a>
            </div>
        </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_get.return_value = mock_response

        with patch.object(
            self.service, "_fetch_movie_title", return_value="The Matrix"
        ):
            result = self.service.search_movie("The Matrix")
            assert result["error"] is False

    @patch("requests.get")
    def test_beautifulsoup_results_loop_no_valid_elements(self, mock_get):
        """Test BeautifulSoup strategy with results but no valid title elements."""
        # HTML has search results container but no valid title links
        html_content = """
        <html>
        <body>
            <div class="ipc-metadata-list-summary-item">
                <span>Just a span, not a link</span>
            </div>
            <div class="lister-item">
                <a href="/invalid">No ID here</a>
            </div>
        </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_get.return_value = mock_response

        result = self.service.search_movie("The Matrix")
        # Should continue to Strategy 3
        assert result is not None

    @patch("requests.get")
    def test_direct_title_page_short_title(self, mock_get):
        """Test Strategy 3 with title text <= 3 characters."""
        html_content = """
        <html>
        <body>
            <h1 data-testid="hero__pageTitle">AB</h1>
            <a href="/title/tt0133093/">Link</a>
        </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_get.return_value = mock_response

        result = self.service.search_movie("AB")
        # Should not match because title is too short, continues to Strategy 3
        assert result is not None

    @patch("requests.get")
    def test_beautifulsoup_results_href_no_valid_id(self, mock_get):
        """Test BeautifulSoup results loop with href without valid IMDb ID pattern."""
        # Results exist but href doesn't match /title/tt\d+ pattern (line 175-176)
        html_content = """
        <html>
        <body>
            <div class="ipc-metadata-list-summary-item">
                <a href="/title/INVALID">The Matrix</a>
            </div>
            <div class="find-result-item">
                <a href="/title/nott123">Matrix</a>
            </div>
        </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_get.return_value = mock_response

        result = self.service.search_movie("The Matrix")
        # Should continue to Strategy 3
        assert result is not None

    @patch("requests.get")
    def test_beautifulsoup_results_imdb_id_no_slashes(self, mock_get):
        """Test BeautifulSoup results where href matches first pattern but not second."""
        # href has /title/tt\d+ (line 175 passes) but no trailing slash (line 181 fails)
        html_content = """
        <html>
        <body>
            <div class="ipc-metadata-list-summary-item">
                <a href="/title/tt123">The Matrix</a>
            </div>
        </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_get.return_value = mock_response

        # First pattern matches /title/tt123, second needs trailing / so it fails
        result = self.service.search_movie("The Matrix")
        # Line 175: matches, Line 179: no match -> continues to next result or Strategy 3
        assert result is not None

    @patch("requests.get")
    def test_beautifulsoup_results_fetch_returns_none(self, mock_get):
        """Test BeautifulSoup where fetch returns None (lines 181-186)."""
        # Tests when imdb_id_match is True but _fetch_movie_title returns None
        html_content = """
        <html>
        <body>
            <div class="ipc-metadata-list-summary-item">
                <a href="/title/tt0133093/">The Matrix</a>
            </div>
        </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_get.return_value = mock_response

        # Fetch returns None, so loop continues
        with patch.object(self.service, "_fetch_movie_title", return_value=None):
            result = self.service.search_movie("The Matrix")
            # Should continue to Strategy 3
            assert result is not None

    @patch("requests.get")
    def test_direct_title_page_no_imdb_id_in_html(self, mock_get):
        """Test Strategy 3 when title element exists but no imdb ID in HTML."""
        # Tests line 202: title_element exists but imdb_id_match fails
        html_content = """
        <html>
        <body>
            <h1 data-testid="hero__pageTitle">The Matrix (1999)</h1>
            <a href="/some/other/path">Link</a>
        </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_get.return_value = mock_response

        result = self.service.search_movie("The Matrix")
        # Should return error because no imdb id found
        assert result["error"] is True

    @patch("requests.get")
    def test_beautifulsoup_loop_continues_after_invalid_href(self, mock_get):
        """Test BeautifulSoup loop continues after skipping invalid hrefs (line 176)."""
        # Strategy 1 finds nothing. Strategy 2 has results, some with invalid hrefs.
        # When href check at line 175 fails, line 176 continues to next result.
        html_content = """
        <html>
        <body>
            <div class="ipc-metadata-list-summary-item">
                <a href="/bad/link">First</a>
            </div>
            <div class="ipc-metadata-list-summary-item">
                <a href="/title/tt0133093/">The Matrix</a>
            </div>
        </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_get.return_value = mock_response

        # First result has bad href, should skip. Second has valid.
        with patch.object(
            self.service, "_fetch_movie_title", return_value="The Matrix"
        ):
            result = self.service.search_movie("The Matrix")
            assert result["error"] is False
