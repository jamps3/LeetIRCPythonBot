"""
Tests for the !kraks Command

This module contains comprehensive tests for the !kraks command functionality including:
- Basic command execution
- Response formatting
- Integration with drink tracking system
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

# Add parent directory to sys.path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from word_tracking import DataManager, DrinkTracker


class TestKraksCommand(unittest.TestCase):
    """Test suite for the !kraks command."""

    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directory for test data
        self.temp_dir = tempfile.mkdtemp()

        # Clear the opt-out environment variable to ensure clean test environment
        os.environ["DRINK_TRACKING_OPT_OUT"] = ""

        self.data_manager = DataManager(self.temp_dir)
        self.drink_tracker = DrinkTracker(self.data_manager)

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_kraks_command_empty_stats(self):
        """Test !kraks command with no drink words recorded."""
        server_name = "test_server"
        stats = self.drink_tracker.get_server_stats(server_name)

        # Should return empty stats
        self.assertEqual(stats["total_drink_words"], 0)
        self.assertEqual(stats["top_users"], [])

    def test_kraks_command_with_data(self):
        """Test !kraks command with recorded drink words."""
        server_name = "test_server"

        # Add some test data
        alice_matches = self.drink_tracker.process_message(
            server_name, "alice", "krak krak krak"
        )
        bob_matches = self.drink_tracker.process_message(
            server_name, "bob", "narsk narsk"
        )
        charlie_matches = self.drink_tracker.process_message(
            server_name, "charlie", "parsk"
        )

        # Verify matches were found
        self.assertEqual(len(alice_matches), 3)  # 3 kraks
        self.assertEqual(len(bob_matches), 2)  # 2 narsks
        self.assertEqual(len(charlie_matches), 1)  # 1 parsk

        # Get stats
        stats = self.drink_tracker.get_server_stats(server_name)

        # Should have recorded drink words
        self.assertEqual(stats["total_drink_words"], 6)
        self.assertEqual(len(stats["top_users"]), 3)
        self.assertEqual(stats["top_users"][0], ("alice", 3))  # alice has most
        self.assertEqual(stats["top_users"][1], ("bob", 2))  # bob has second most
        self.assertEqual(stats["top_users"][2], ("charlie", 1))  # charlie has least

    def test_kraks_command_drink_word_breakdown(self):
        """Test !kraks command breakdown by drink word."""
        server_name = "test_server"

        # Add some test data
        self.drink_tracker.process_message(server_name, "alice", "krak krak krak")
        self.drink_tracker.process_message(server_name, "bob", "narsk narsk")
        self.drink_tracker.process_message(server_name, "charlie", "krak")

        # Get breakdown
        breakdown = self.drink_tracker.get_drink_word_breakdown(server_name)

        # Should have correct breakdown
        self.assertEqual(len(breakdown), 2)  # krak and narsk
        self.assertEqual(breakdown[0], ("krak", 4, "alice"))  # krak: 4 total, alice top
        self.assertEqual(breakdown[1], ("narsk", 2, "bob"))  # narsk: 2 total, bob top

    def test_kraks_command_response_format(self):
        """Test !kraks command response formatting."""
        server_name = "test_server"

        # Add some test data
        self.drink_tracker.process_message(server_name, "alice", "krak krak")
        self.drink_tracker.process_message(server_name, "bob", "narsk")

        # Get stats and breakdown
        stats = self.drink_tracker.get_server_stats(server_name)
        breakdown = self.drink_tracker.get_drink_word_breakdown(server_name)

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
        self.assertEqual(response, expected_response)

    def test_kraks_command_empty_response(self):
        """Test !kraks command response when no data exists."""
        server_name = "test_server"

        # Get stats (should be empty)
        stats = self.drink_tracker.get_server_stats(server_name)

        # Test response construction
        if stats["total_drink_words"] > 0:
            response = f"Krakit yhteensä: {stats['total_drink_words']}"
        else:
            response = "Ei vielä krakkauksia tallennettuna."

        self.assertEqual(response, "Ei vielä krakkauksia tallennettuna.")

    def test_kraks_command_with_specific_drinks(self):
        """Test !kraks command with specific drink information."""
        server_name = "test_server"

        # Add some test data with specific drinks
        self.drink_tracker.process_message(server_name, "alice", "krak (Karhu 5,5%)")
        self.drink_tracker.process_message(server_name, "bob", "narsk (Olvi III)")
        self.drink_tracker.process_message(server_name, "alice", "krak (Karhu 5,5%)")

        # Get user stats to verify specific drinks are tracked
        alice_stats = self.drink_tracker.get_user_stats(server_name, "alice")
        bob_stats = self.drink_tracker.get_user_stats(server_name, "bob")

        # Verify specific drinks are recorded
        self.assertEqual(alice_stats["total_drink_words"], 2)
        self.assertEqual(alice_stats["drink_words"]["krak"]["drinks"]["Karhu 5,5%"], 2)

        self.assertEqual(bob_stats["total_drink_words"], 1)
        self.assertEqual(bob_stats["drink_words"]["narsk"]["drinks"]["Olvi III"], 1)

    def test_kraks_command_user_privacy(self):
        """Test !kraks command respects user privacy settings."""
        server_name = "test_server"

        # Add some test data
        self.drink_tracker.process_message(server_name, "alice", "krak krak")

        # Opt alice out
        self.data_manager.set_user_opt_out(server_name, "alice", True)

        # Try to add more data - should be ignored
        self.drink_tracker.process_message(server_name, "alice", "krak krak")

        # Get stats - should only have the original data
        stats = self.drink_tracker.get_server_stats(server_name)
        alice_stats = self.drink_tracker.get_user_stats(server_name, "alice")

        self.assertEqual(stats["total_drink_words"], 2)  # Only original data
        self.assertEqual(alice_stats["total_drink_words"], 2)  # No new data added

    def test_kraks_command_multiple_servers(self):
        """Test !kraks command with multiple servers."""
        server1 = "server1"
        server2 = "server2"

        # Add data to both servers
        self.drink_tracker.process_message(server1, "alice", "krak krak")
        self.drink_tracker.process_message(server2, "bob", "narsk")

        # Get stats for each server
        stats1 = self.drink_tracker.get_server_stats(server1)
        stats2 = self.drink_tracker.get_server_stats(server2)

        # Should be separate
        self.assertEqual(stats1["total_drink_words"], 2)
        self.assertEqual(stats2["total_drink_words"], 1)

        # Global stats should show both
        global_stats = self.drink_tracker.get_global_stats()
        self.assertEqual(global_stats["total_drink_words"], 3)

    def test_kraks_command_drink_word_patterns(self):
        """Test !kraks command recognizes all drink word patterns."""
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
            self.drink_tracker.process_message(server_name, "testuser", word)

        # Get stats
        stats = self.drink_tracker.get_server_stats(server_name)
        breakdown = self.drink_tracker.get_drink_word_breakdown(server_name)

        # Should have recorded all drink words
        self.assertEqual(stats["total_drink_words"], len(drink_words))
        self.assertEqual(len(breakdown), len(drink_words))

    def test_kraks_command_case_insensitive(self):
        """Test !kraks command is case insensitive."""
        server_name = "test_server"

        # Add data with different cases
        self.drink_tracker.process_message(server_name, "alice", "KRAK")
        self.drink_tracker.process_message(server_name, "bob", "krak")
        self.drink_tracker.process_message(server_name, "charlie", "Krak")

        # Get breakdown
        breakdown = self.drink_tracker.get_drink_word_breakdown(server_name)

        # Should all be counted as the same word
        self.assertEqual(len(breakdown), 1)
        self.assertEqual(breakdown[0][0], "krak")  # Should be lowercase
        self.assertEqual(breakdown[0][1], 3)  # Total count should be 3


if __name__ == "__main__":
    unittest.main()
