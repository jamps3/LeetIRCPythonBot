"""
Tests for the !kraks Command

This module contains comprehensive tests for the !kraks command functionality including:
- Basic command execution
- Response formatting
- Integration with drink tracking system
Pure pytest implementation with fixtures and proper assertions.
"""

import os
import tempfile

import pytest

from word_tracking import DataManager, DrinkTracker


@pytest.fixture
def temp_dir():
    """Create and clean up a temporary directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir

    # Cleanup
    import shutil

    shutil.rmtree(temp_dir)


@pytest.fixture
def data_manager(temp_dir):
    """Create a DataManager instance for testing."""
    # Clear the opt-out environment variable to ensure clean test environment
    os.environ["DRINK_TRACKING_OPT_OUT"] = ""
    return DataManager(temp_dir)


@pytest.fixture
def drink_tracker(data_manager):
    """Create a DrinkTracker instance for testing."""
    return DrinkTracker(data_manager)


def test_kraks_command_empty_stats(drink_tracker):
    """Test !kraks command with no drink words recorded."""
    server_name = "test_server"
    stats = drink_tracker.get_server_stats(server_name)

    # Should return empty stats
    assert stats["total_drink_words"] == 0, "Should have no drink words initially"
    assert stats["top_users"] == [], "Should have no top users initially"


def test_kraks_command_with_data(drink_tracker):
    """Test !kraks command with recorded drink words."""
    server_name = "test_server"

    # Add some test data
    alice_matches = drink_tracker.process_message(
        server_name, "alice", "krak krak krak"
    )
    bob_matches = drink_tracker.process_message(server_name, "bob", "narsk narsk")
    charlie_matches = drink_tracker.process_message(server_name, "charlie", "parsk")

    # Verify matches were found
    assert len(alice_matches) == 3, "Alice should have 3 kraks"
    assert len(bob_matches) == 2, "Bob should have 2 narsks"
    assert len(charlie_matches) == 1, "Charlie should have 1 parsk"

    # Get stats
    stats = drink_tracker.get_server_stats(server_name)

    # Should have recorded drink words
    assert stats["total_drink_words"] == 6, "Should have 6 total drink words"
    assert len(stats["top_users"]) == 3, "Should have 3 users"
    assert stats["top_users"][0] == ("alice", 3), "Alice should have most drinks"
    assert stats["top_users"][1] == ("bob", 2), "Bob should have second most drinks"
    assert stats["top_users"][2] == ("charlie", 1), "Charlie should have least drinks"


def test_kraks_command_drink_word_breakdown(drink_tracker):
    """Test !kraks command breakdown by drink word."""
    server_name = "test_server"

    # Add some test data
    drink_tracker.process_message(server_name, "alice", "krak krak krak")
    drink_tracker.process_message(server_name, "bob", "narsk narsk")
    drink_tracker.process_message(server_name, "charlie", "krak")

    # Get breakdown
    breakdown = drink_tracker.get_drink_word_breakdown(server_name)

    # Should have correct breakdown
    assert len(breakdown) == 2, "Should have 2 different drink words"
    assert breakdown[0] == (
        "krak",
        4,
        "alice",
    ), "Krak should have 4 total with alice as top user"
    assert breakdown[1] == (
        "narsk",
        2,
        "bob",
    ), "Narsk should have 2 total with bob as top user"


def test_kraks_command_response_format(drink_tracker):
    """Test !kraks command response formatting."""
    server_name = "test_server"

    # Add some test data
    drink_tracker.process_message(server_name, "alice", "krak krak")
    drink_tracker.process_message(server_name, "bob", "narsk")

    # Get stats and breakdown
    stats = drink_tracker.get_server_stats(server_name)
    breakdown = drink_tracker.get_drink_word_breakdown(server_name)

    # Test response construction
    if stats["total_drink_words"] > 0:
        if breakdown:
            details = ", ".join(
                f"{word}: {count} [{top_user}]"
                for word, count, top_user in breakdown[:10]
            )
            response = f"Krakit yhteensä: {stats['total_drink_words']}, {details}"
        else:
            response = f"Krakit yhteensä: {stats['total_drink_words']}. Top 5: {', '.join([f'{nick}:{count}' for nick, count in stats['top_users'][:5]])}"
    else:
        response = "Ei vielä krakkauksia tallennettuna."

    expected_response = "Krakit yhteensä: 3, krak: 2 [alice], narsk: 1 [bob]"
    assert response == expected_response, "Response format should match expected format"


def test_kraks_command_empty_response(drink_tracker):
    """Test !kraks command response when no data exists."""
    server_name = "test_server"

    # Get stats (should be empty)
    stats = drink_tracker.get_server_stats(server_name)

    # Test response construction
    if stats["total_drink_words"] > 0:
        response = f"Krakit yhteensä: {stats['total_drink_words']}"
    else:
        response = "Ei vielä krakkauksia tallennettuna."

    assert (
        response == "Ei vielä krakkauksia tallennettuna."
    ), "Should show no drinks message"


def test_kraks_command_with_specific_drinks(drink_tracker):
    """Test !kraks command with specific drink information."""
    server_name = "test_server"

    # Add some test data with specific drinks
    drink_tracker.process_message(server_name, "alice", "krak (Karhu 5,5%)")
    drink_tracker.process_message(server_name, "bob", "narsk (Olvi III)")
    drink_tracker.process_message(server_name, "alice", "krak (Karhu 5,5%)")

    # Get user stats to verify specific drinks are tracked
    alice_stats = drink_tracker.get_user_stats(server_name, "alice")
    bob_stats = drink_tracker.get_user_stats(server_name, "bob")

    # Verify specific drinks are recorded
    assert (
        alice_stats["total_drink_words"] == 2
    ), "Alice should have 2 total drink words"
    assert (
        alice_stats["drink_words"]["krak"]["drinks"]["Karhu 5,5%"] == 2
    ), "Alice should have 2 Karhu 5,5%"

    assert bob_stats["total_drink_words"] == 1, "Bob should have 1 total drink word"
    assert (
        bob_stats["drink_words"]["narsk"]["drinks"]["Olvi III"] == 1
    ), "Bob should have 1 Olvi III"


def test_kraks_command_user_privacy(drink_tracker, data_manager):
    """Test !kraks command respects user privacy settings."""
    server_name = "test_server"

    # Add some test data
    drink_tracker.process_message(server_name, "alice", "krak krak")

    # Opt alice out
    data_manager.set_user_opt_out(server_name, "alice", True)

    # Try to add more data - should be ignored
    drink_tracker.process_message(server_name, "alice", "krak krak")

    # Get stats - should only have the original data
    stats = drink_tracker.get_server_stats(server_name)
    alice_stats = drink_tracker.get_user_stats(server_name, "alice")

    assert stats["total_drink_words"] == 2, "Should only have original data"
    assert (
        alice_stats["total_drink_words"] == 2
    ), "No new data should be added for opted-out user"


def test_kraks_command_multiple_servers(drink_tracker):
    """Test !kraks command with multiple servers."""
    server1 = "server1"
    server2 = "server2"

    # Add data to both servers
    drink_tracker.process_message(server1, "alice", "krak krak")
    drink_tracker.process_message(server2, "bob", "narsk")

    # Get stats for each server
    stats1 = drink_tracker.get_server_stats(server1)
    stats2 = drink_tracker.get_server_stats(server2)

    # Should be separate
    assert stats1["total_drink_words"] == 2, "Server1 should have 2 drink words"
    assert stats2["total_drink_words"] == 1, "Server2 should have 1 drink word"

    # Global stats should show both
    global_stats = drink_tracker.get_global_stats()
    assert (
        global_stats["total_drink_words"] == 3
    ), "Global stats should show all drink words"


@pytest.mark.parametrize(
    "drink_word",
    [
        "krak",
        "kr1k",
        "kr0k",
        "narsk",
        "parsk",
        "tlup",
        "marsk",
        "tsup",
        "plop",
        "tsirp",
    ],
)
def test_kraks_command_drink_word_patterns(drink_tracker, drink_word):
    """Test !kraks command recognizes all drink word patterns."""
    server_name = "test_server"

    # Test individual drink word
    matches = drink_tracker.process_message(server_name, "testuser", drink_word)

    # Should recognize the drink word
    assert len(matches) == 1, f"Should recognize {drink_word} as a drink word"


def test_kraks_command_all_drink_word_patterns(drink_tracker):
    """Test !kraks command recognizes all drink word patterns together."""
    server_name = "test_server"

    # Test various drink words
    drink_words = [
        "krak",
        "kr1k",
        "kr0k",
        "narsk",
        "parsk",
        "tlup",
        "marsk",
        "tsup",
        "plop",
        "tsirp",
    ]

    for word in drink_words:
        drink_tracker.process_message(server_name, "testuser", word)

    # Get stats
    stats = drink_tracker.get_server_stats(server_name)
    breakdown = drink_tracker.get_drink_word_breakdown(server_name)

    # Should have recorded all drink words
    assert stats["total_drink_words"] == len(
        drink_words
    ), f"Should have recorded {len(drink_words)} drink words"
    assert len(breakdown) == len(
        drink_words
    ), f"Breakdown should have {len(drink_words)} different words"


@pytest.mark.parametrize(
    "word,expected_normalized",
    [
        ("KRAK", "krak"),
        ("krak", "krak"),
        ("Krak", "krak"),
        ("KrAk", "krak"),
    ],
)
def test_kraks_command_case_insensitive(drink_tracker, word, expected_normalized):
    """Test !kraks command is case insensitive."""
    server_name = "test_server"

    # Add data with different cases
    drink_tracker.process_message(server_name, "alice", "KRAK")
    drink_tracker.process_message(server_name, "bob", "krak")
    drink_tracker.process_message(server_name, "charlie", "Krak")

    # Get breakdown
    breakdown = drink_tracker.get_drink_word_breakdown(server_name)

    # Should all be counted as the same word
    assert len(breakdown) == 1, "All case variations should be counted as one word"
    assert breakdown[0][0] == "krak", "Should be normalized to lowercase"
    assert breakdown[0][1] == 3, "Total count should be 3"


def test_kraks_command_mixed_messages(drink_tracker):
    """Test !kraks command with mixed drink and non-drink content."""
    server_name = "test_server"

    # Add messages with mixed content
    drink_tracker.process_message(
        server_name, "alice", "Hello everyone, krak! How are you?"
    )
    drink_tracker.process_message(server_name, "bob", "Just had a beer, narsk narsk!")
    drink_tracker.process_message(
        server_name, "charlie", "No drinks here, just chatting"
    )

    # Get stats
    stats = drink_tracker.get_server_stats(server_name)
    breakdown = drink_tracker.get_drink_word_breakdown(server_name)

    # Should only count the drink words
    assert (
        stats["total_drink_words"] == 3
    ), "Should count only drink words from mixed messages"
    assert len(breakdown) == 2, "Should have krak and narsk"


def test_kraks_command_user_stats_detail(drink_tracker):
    """Test detailed user statistics for !kraks command."""
    server_name = "test_server"

    # Add varied data for one user
    drink_tracker.process_message(server_name, "alice", "krak krak")
    drink_tracker.process_message(server_name, "alice", "narsk")
    drink_tracker.process_message(server_name, "alice", "krak (Karhu)")

    # Get detailed user stats
    alice_stats = drink_tracker.get_user_stats(server_name, "alice")

    # Verify detailed breakdown
    assert (
        alice_stats["total_drink_words"] == 4
    ), "Alice should have 4 total drink words"
    assert "krak" in alice_stats["drink_words"], "Alice should have krak words"
    assert "narsk" in alice_stats["drink_words"], "Alice should have narsk words"
