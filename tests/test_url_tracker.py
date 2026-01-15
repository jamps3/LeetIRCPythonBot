#!/usr/bin/env python3
"""
Pytest URL Tracker tests

Comprehensive tests for URL tracker service and command functionality.
"""

import os
import sys
from unittest.mock import Mock

import pytest

# Add the parent directory to Python path to ensure imports work in CI
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


@pytest.fixture
def url_tracker_service(tmp_path):
    """Create a URL tracker service instance for testing with temporary data directory."""
    from services.url_tracker_service import URLTrackerService

    # Use temporary directory for tests
    return URLTrackerService(str(tmp_path / "test_data"))


@pytest.fixture
def mock_bot_functions():
    """Mock bot functions for command testing."""
    return Mock()


@pytest.fixture
def sample_urls(url_tracker_service):
    """Set up sample URLs for testing."""
    # Track some sample URLs
    url_tracker_service.track_url(
        "https://www.tiede.fi", "testuser1", "testserver", "2026-01-14T19:26:59.792672"
    )
    url_tracker_service.track_url(
        "https://yle.fi", "testuser2", "testserver", "2026-01-14T21:04:48.150752"
    )
    url_tracker_service.track_url(
        "https://example.com", "testuser3", "testserver", "2026-01-14T19:25:23.822279"
    )
    return url_tracker_service


def test_url_tracker_service_creation():
    """Test URL tracker service creation."""
    from services.url_tracker_service import (
        URLTrackerService,
        create_url_tracker_service,
    )

    # Test direct instantiation
    service = URLTrackerService()
    assert isinstance(
        service, URLTrackerService
    ), "Should create URLTrackerService instance"
    assert hasattr(service, "urls_data"), "Should have urls_data attribute"
    assert hasattr(service, "data_dir"), "Should have data_dir attribute"

    # Test factory function
    service2 = create_url_tracker_service()
    assert isinstance(
        service2, URLTrackerService
    ), "Factory should return URLTrackerService instance"


def test_url_tracking_basic(url_tracker_service):
    """Test basic URL tracking functionality."""
    # Track a new URL
    is_duplicate, timestamp = url_tracker_service.track_url(
        "https://example.com", "testuser", "testserver"
    )

    assert is_duplicate is False, "Should not be duplicate for new URL"
    assert timestamp is None, "Should not have first seen timestamp for new URL"

    # Track the same URL again
    is_duplicate2, timestamp2 = url_tracker_service.track_url(
        "https://example.com", "testuser2", "testserver"
    )

    assert is_duplicate2 is True, "Should be duplicate for existing URL"
    assert timestamp2 is not None, "Should have first seen timestamp for duplicate"


def test_url_normalization(url_tracker_service):
    """Test URL normalization for tracking."""
    # Track URL with trailing slash
    url_tracker_service.track_url("https://test.com/", "user1", "server")

    # Should find it without trailing slash
    info = url_tracker_service.get_url_info("https://test.com")
    assert info is not None, "Should find URL without trailing slash"

    # Should find it with trailing slash
    info2 = url_tracker_service.get_url_info("https://test.com/")
    assert info2 is not None, "Should find URL with trailing slash"

    # Should be the same entry
    assert info["count"] == info2["count"], "Should be the same URL entry"


def test_get_url_info(url_tracker_service, sample_urls):
    """Test getting URL information."""
    # Test existing URL
    info = sample_urls.get_url_info("https://www.tiede.fi")
    assert info is not None, "Should find existing URL"
    assert info["count"] == 1, "Should have correct count"
    assert len(info["posters"]) == 1, "Should have one poster"
    assert info["posters"][0]["nick"] == "testuser1", "Should have correct poster"

    # Test non-existent URL
    info2 = sample_urls.get_url_info("https://nonexistent.com")
    assert info2 is None, "Should return None for non-existent URL"


def test_find_closest_match(sample_urls):
    """Test finding closest URL matches."""
    # Test exact match
    match = sample_urls.find_closest_match("https://www.tiede.fi")
    assert match is not None, "Should find exact match"
    url, info = match
    assert url == "https://www.tiede.fi", "Should return correct URL"
    assert info["count"] == 1, "Should have correct info"

    # Test partial match
    match2 = sample_urls.find_closest_match("tiede.fi")
    assert match2 is not None, "Should find partial match"
    url2, info2 = match2
    assert "tiede.fi" in url2, "Should contain search term"
    assert url2 == "https://www.tiede.fi", "Should match the tracked URL"

    # Test another partial match
    match3 = sample_urls.find_closest_match("yle.fi")
    assert match3 is not None, "Should find partial match for yle.fi"
    url3, info3 = match3
    assert url3 == "https://yle.fi", "Should match the tracked URL"

    # Test non-existent partial
    match4 = sample_urls.find_closest_match("nonexistent.com")
    assert match4 is None, "Should return None for non-existent partial"


def test_search_urls(sample_urls):
    """Test URL search functionality."""
    # Search for URLs containing "tiede"
    results = sample_urls.search_urls("tiede")
    assert len(results) > 0, "Should find URLs containing 'tiede'"
    urls = [url for url, info in results]
    assert any("tiede.fi" in url for url in urls), "Should include tiede.fi URL"

    # Search for non-existent term
    results2 = sample_urls.search_urls("xyz123")
    assert len(results2) == 0, "Should find no results for non-existent term"


def test_get_stats(sample_urls):
    """Test statistics functionality."""
    stats = sample_urls.get_stats()

    assert stats["total_urls"] > 0, "Should have URLs tracked"
    assert stats["total_posts"] > 0, "Should have posts tracked"
    assert stats["most_popular_url"] is not None, "Should have most popular URL"
    assert stats["oldest_url"] is not None, "Should have oldest URL"


def test_url_info_formatting(sample_urls):
    """Test URL info formatting."""
    info = sample_urls.get_url_info("https://www.tiede.fi")
    assert info is not None, "Should have URL info"

    formatted = sample_urls.format_url_info("https://www.tiede.fi", info)
    assert "🔗 https://www.tiede.fi" in formatted, "Should include URL"
    assert "First:" in formatted, "Should include first seen info"
    assert "Last:" in formatted, "Should include last seen info"
    assert "Total:" in formatted, "Should include total count"


def test_search_result_formatting(sample_urls):
    """Test search result formatting."""
    info = sample_urls.get_url_info("https://www.tiede.fi")
    assert info is not None, "Should have URL info"

    formatted = sample_urls.format_search_result("https://www.tiede.fi", info)
    assert "🔗 https://www.tiede.fi" in formatted, "Should include URL"
    assert "first seen:" in formatted, "Should include first seen info"


def test_url_command_no_args(url_tracker_service, mock_bot_functions):
    """Test URL command with no arguments."""
    from command_registry import CommandContext
    from commands_services import url_command

    context = CommandContext(
        command="url",
        args=[],
        raw_message="!url",
        sender="testuser",
        target="#testchannel",
        is_console=False,
        server_name="testserver",
    )

    result = url_command(context, mock_bot_functions)
    assert "URL tracking:" in result, "Should show general stats"


def test_url_command_stats(url_tracker_service, mock_bot_functions):
    """Test URL command stats subcommand."""
    from command_registry import CommandContext
    from commands_services import url_command

    context = CommandContext(
        command="url",
        args=["stats"],
        raw_message="!url stats",
        sender="testuser",
        target="#testchannel",
        is_console=False,
        server_name="testserver",
    )

    result = url_command(context, mock_bot_functions)
    assert "🔗 URL Stats:" in result, "Should show detailed stats"


def test_url_command_exact_match(sample_urls, mock_bot_functions):
    """Test URL command with exact URL match."""
    from command_registry import CommandContext
    from commands_services import url_command

    context = CommandContext(
        command="url",
        args=["https://www.tiede.fi"],
        raw_message="!url https://www.tiede.fi",
        sender="testuser",
        target="#testchannel",
        is_console=False,
        server_name="testserver",
    )

    result = url_command(context, mock_bot_functions)
    assert "🔗 https://www.tiede.fi" in result, "Should show URL info"
    assert "First:" in result, "Should include timing info"


def test_url_command_partial_match(sample_urls, mock_bot_functions):
    """Test URL command with partial URL match."""
    from command_registry import CommandContext
    from commands_services import url_command

    context = CommandContext(
        command="url",
        args=["tiede.fi"],
        raw_message="!url tiede.fi",
        sender="testuser",
        target="#testchannel",
        is_console=False,
        server_name="testserver",
    )

    result = url_command(context, mock_bot_functions)
    assert "🔗 https://www.tiede.fi" in result, "Should find partial match"
    assert "First:" in result, "Should include timing info"


def test_url_command_no_match(url_tracker_service, mock_bot_functions):
    """Test URL command with no match found."""
    from command_registry import CommandContext
    from commands_services import url_command

    context = CommandContext(
        command="url",
        args=["nonexistent.xyz"],
        raw_message="!url nonexistent.xyz",
        sender="testuser",
        target="#testchannel",
        is_console=False,
        server_name="testserver",
    )

    result = url_command(context, mock_bot_functions)
    assert (
        "🔗 URL not found in tracking database: nonexistent.xyz" == result
    ), "Should show not found message"


def test_url_command_search(sample_urls, mock_bot_functions):
    """Test URL command search functionality."""
    from command_registry import CommandContext
    from commands_services import url_command

    context = CommandContext(
        command="url",
        args=["search", "tiede"],
        raw_message="!url search tiede",
        sender="testuser",
        target="#testchannel",
        is_console=False,
        server_name="testserver",
    )

    result = url_command(context, mock_bot_functions)
    assert "🔗 https://www.tiede.fi" in result, "Should find URL in search"
    assert "first seen:" in result, "Should format as search result"


def test_url_command_search_no_results(url_tracker_service, mock_bot_functions):
    """Test URL command search with no results."""
    from command_registry import CommandContext
    from commands_services import url_command

    context = CommandContext(
        command="url",
        args=["search", "xyz123"],
        raw_message="!url search xyz123",
        sender="testuser",
        target="#testchannel",
        is_console=False,
        server_name="testserver",
    )

    result = url_command(context, mock_bot_functions)
    assert (
        result == "🔗 No URLs found matching 'xyz123'"
    ), "Should show no results message"


def test_duplicate_message_formatting(sample_urls):
    """Test duplicate URL message formatting."""
    first_timestamp = "2026-01-14T19:26:59.792672"

    result = sample_urls.format_duplicate_message(
        "https://www.tiede.fi", first_timestamp, "testuser1"
    )

    assert "Wanha!" in result, "Should contain 'Wanha!'"
    assert "https://www.tiede.fi" in result, "Should contain URL"
    assert "testuser1" in result, "Should contain nickname"


def test_url_tracker_case_insensitive(sample_urls):
    """Test that URL tracking is case insensitive."""
    # Track URL with different case
    sample_urls.track_url("https://EXAMPLE.COM", "user4", "server")

    # Should find it regardless of case
    info1 = sample_urls.get_url_info("https://example.com")
    info2 = sample_urls.get_url_info("https://EXAMPLE.COM")

    assert info1 is not None, "Should find URL with original case"
    assert info2 is not None, "Should find URL with different case"
    assert info1["count"] == info2["count"], "Should be the same entry"


def test_multiple_posters_same_url(sample_urls):
    """Test tracking multiple posters for the same URL."""
    # Track the same URL multiple times with different users
    sample_urls.track_url(
        "https://example.com", "user4", "server", "2026-01-15T10:00:00"
    )
    sample_urls.track_url(
        "https://example.com", "user5", "server", "2026-01-15T11:00:00"
    )

    info = sample_urls.get_url_info("https://example.com")
    assert info["count"] == 3, "Should have 3 total posts"
    assert len(info["posters"]) == 3, "Should have 3 posters"

    # Check posters are sorted by timestamp
    nicks = [p["nick"] for p in info["posters"]]
    assert nicks == ["testuser3", "user4", "user5"], "Should be sorted by timestamp"
