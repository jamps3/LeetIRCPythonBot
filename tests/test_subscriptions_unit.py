import json
import os
import sys
import tempfile
import unittest
from unittest.mock import mock_open, patch

# Add the parent directory to the path to import the subscriptions module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from subscriptions import (
    VALID_TOPICS,
    get_server_subscribers,
    get_subscribers,
    get_user_subscriptions,
    is_valid_nick_or_channel,
    load_subscriptions,
    save_subscriptions,
    toggle_subscription,
    validate_and_clean_data,
)


class TestSubscriptionsEnhanced(unittest.TestCase):
    """Test suite for the enhanced subscription system with server support and error handling."""

    def setUp(self):
        """Set up test environment with temporary file."""
        self.temp_file = tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".json"
        )
        self.temp_file.write("{}")
        self.temp_file.close()

        # Patch the SUBSCRIBERS_FILE constant
        self.patcher = patch("subscriptions.SUBSCRIBERS_FILE", self.temp_file.name)
        self.patcher.start()

    def tearDown(self):
        """Clean up test environment."""
        self.patcher.stop()
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)

    def test_is_valid_nick_or_channel(self):
        """Test IRC nick and channel validation."""
        # Valid nicks
        self.assertTrue(is_valid_nick_or_channel("jampsix"))
        self.assertTrue(is_valid_nick_or_channel("test_user"))
        self.assertTrue(is_valid_nick_or_channel("user-123"))
        self.assertTrue(is_valid_nick_or_channel("nick[]{}"))

        # Valid channels
        self.assertTrue(is_valid_nick_or_channel("#test"))
        self.assertTrue(is_valid_nick_or_channel("#test-channel"))
        self.assertTrue(is_valid_nick_or_channel("#channel123"))

        # Invalid nicks/channels
        self.assertFalse(is_valid_nick_or_channel(""))
        self.assertFalse(is_valid_nick_or_channel("123nick"))  # Can't start with digit
        self.assertFalse(is_valid_nick_or_channel("nick with spaces"))
        self.assertFalse(is_valid_nick_or_channel("nick,comma"))
        self.assertFalse(is_valid_nick_or_channel("#"))  # Channel too short
        self.assertFalse(is_valid_nick_or_channel("a" * 31))  # Too long
        self.assertFalse(is_valid_nick_or_channel("#channel with spaces"))

    def test_validate_and_clean_data(self):
        """Test data validation and cleaning."""
        # Valid data
        valid_data = {
            "server1": {"jampsix": ["varoitukset"], "#test": ["onnettomuustiedotteet"]},
            "server2": {"user123": ["varoitukset", "onnettomuustiedotteet"]},
        }
        cleaned = validate_and_clean_data(valid_data)
        self.assertEqual(cleaned, valid_data)

        # Invalid data that should be cleaned
        invalid_data = {
            "server1": {
                "jampsix": ["varoitukset", "invalid_topic"],  # Invalid topic
                "123invalid": ["varoitukset"],  # Invalid nick
                "#test": ["onnettomuustiedotteet"],
            },
            "": {"user": ["varoitukset"]},  # Empty server name
            "server2": {
                "user with spaces": ["varoitukset"],  # Invalid nick
                "validuser": [],  # Empty topics list
            },
        }

        cleaned = validate_and_clean_data(invalid_data)
        expected = {
            "server1": {"jampsix": ["varoitukset"], "#test": ["onnettomuustiedotteet"]}
        }
        self.assertEqual(cleaned, expected)

    def test_load_subscriptions_empty_file(self):
        """Test loading subscriptions from empty file."""
        result = load_subscriptions()
        self.assertEqual(result, {})

    def test_load_subscriptions_valid_data(self):
        """Test loading subscriptions with valid data."""
        test_data = {
            "server1": {"jampsix": ["varoitukset"], "#test": ["onnettomuustiedotteet"]}
        }

        with open(self.temp_file.name, "w", encoding="utf-8") as f:
            json.dump(test_data, f)

        result = load_subscriptions()
        self.assertEqual(result, test_data)

    def test_load_subscriptions_corrupted_json(self):
        """Test loading subscriptions from corrupted JSON file."""
        # Write invalid JSON
        with open(self.temp_file.name, "w", encoding="utf-8") as f:
            f.write('{"invalid": json}')

        result = load_subscriptions()
        self.assertEqual(result, {})

        # Check that backup file was created
        backup_files = [
            f
            for f in os.listdir(os.path.dirname(self.temp_file.name))
            if f.startswith(os.path.basename(self.temp_file.name) + ".corrupted")
        ]
        self.assertTrue(len(backup_files) > 0)

    def test_load_subscriptions_malformed_data(self):
        """Test loading subscriptions with malformed data that needs cleaning."""
        malformed_data = {
            "server1": {
                "jampsix": ["varoitukset", "invalid_topic"],
                "123invalid": ["varoitukset"],
                "#test": ["onnettomuustiedotteet"],
            }
        }

        with open(self.temp_file.name, "w", encoding="utf-8") as f:
            json.dump(malformed_data, f)

        result = load_subscriptions()
        expected = {
            "server1": {"jampsix": ["varoitukset"], "#test": ["onnettomuustiedotteet"]}
        }
        self.assertEqual(result, expected)

        # Check that cleaned data was saved back
        with open(self.temp_file.name, "r", encoding="utf-8") as f:
            saved_data = json.load(f)
        self.assertEqual(saved_data, expected)

    def test_save_subscriptions_success(self):
        """Test successful subscription saving."""
        test_data = {
            "server1": {"jampsix": ["varoitukset"], "#test": ["onnettomuustiedotteet"]}
        }

        result = save_subscriptions(test_data)
        self.assertTrue(result)

        # Verify data was saved
        with open(self.temp_file.name, "r", encoding="utf-8") as f:
            saved_data = json.load(f)
        self.assertEqual(saved_data, test_data)

    def test_save_subscriptions_with_backup(self):
        """Test that backup is created when saving over existing file."""
        # Create initial data
        initial_data = {"server1": {"user1": ["varoitukset"]}}
        with open(self.temp_file.name, "w", encoding="utf-8") as f:
            json.dump(initial_data, f)

        # Save new data
        new_data = {"server1": {"user2": ["onnettomuustiedotteet"]}}
        result = save_subscriptions(new_data)
        self.assertTrue(result)

        # Check backup was created
        backup_file = self.temp_file.name + ".backup"
        self.assertTrue(os.path.exists(backup_file))

        # Verify backup contains original data
        with open(backup_file, "r", encoding="utf-8") as f:
            backup_data = json.load(f)
        self.assertEqual(backup_data, initial_data)

        # Clean up backup
        os.unlink(backup_file)

    def test_toggle_subscription_add(self):
        """Test adding a subscription."""
        result = toggle_subscription("jampsix", "server1", "varoitukset")
        self.assertIn("✅ Tilaus lisätty", result)
        self.assertIn("jampsix", result)
        self.assertIn("server1", result)
        self.assertIn("varoitukset", result)

        # Verify subscription was added
        subscribers = get_subscribers("varoitukset")
        self.assertIn(("jampsix", "server1"), subscribers)

    def test_toggle_subscription_remove(self):
        """Test removing a subscription."""
        # First add a subscription
        toggle_subscription("jampsix", "server1", "varoitukset")

        # Then remove it
        result = toggle_subscription("jampsix", "server1", "varoitukset")
        self.assertIn("❌ Poistettu tilaus", result)
        self.assertIn("jampsix", result)
        self.assertIn("server1", result)
        self.assertIn("varoitukset", result)

        # Verify subscription was removed
        subscribers = get_subscribers("varoitukset")
        self.assertNotIn(("jampsix", "server1"), subscribers)

    def test_toggle_subscription_invalid_topic(self):
        """Test toggling subscription with invalid topic."""
        result = toggle_subscription("jampsix", "server1", "invalid_topic")
        self.assertIn("❌ Invalid topic", result)
        self.assertIn("invalid_topic", result)
        self.assertIn("varoitukset", result)
        self.assertIn("onnettomuustiedotteet", result)

    def test_toggle_subscription_invalid_nick(self):
        """Test toggling subscription with invalid nick."""
        result = toggle_subscription("123invalid", "server1", "varoitukset")
        self.assertIn("❌ Invalid nick/channel", result)
        self.assertIn("123invalid", result)

    def test_toggle_subscription_channel(self):
        """Test toggling subscription for a channel."""
        result = toggle_subscription("#test", "server1", "varoitukset")
        self.assertIn("✅ Tilaus lisätty", result)
        self.assertIn("#test", result)
        self.assertIn("server1", result)

        # Verify channel subscription
        subscribers = get_server_subscribers("varoitukset", "server1")
        self.assertIn("#test", subscribers)

    def test_get_subscribers_empty(self):
        """Test getting subscribers when none exist."""
        subscribers = get_subscribers("varoitukset")
        self.assertEqual(subscribers, [])

    def test_get_subscribers_multiple_servers(self):
        """Test getting subscribers from multiple servers."""
        # Add subscriptions on different servers
        toggle_subscription("user1", "server1", "varoitukset")
        toggle_subscription("user2", "server2", "varoitukset")
        toggle_subscription("#channel", "server1", "varoitukset")

        subscribers = get_subscribers("varoitukset")
        expected = [("user1", "server1"), ("user2", "server2"), ("#channel", "server1")]
        self.assertEqual(sorted(subscribers), sorted(expected))

    def test_get_server_subscribers(self):
        """Test getting subscribers for a specific server."""
        # Add subscriptions on different servers
        toggle_subscription("user1", "server1", "varoitukset")
        toggle_subscription("user2", "server2", "varoitukset")
        toggle_subscription("#channel", "server1", "varoitukset")

        server1_subscribers = get_server_subscribers("varoitukset", "server1")
        self.assertEqual(sorted(server1_subscribers), sorted(["user1", "#channel"]))

        server2_subscribers = get_server_subscribers("varoitukset", "server2")
        self.assertEqual(server2_subscribers, ["user2"])

        # Test non-existent server
        empty_subscribers = get_server_subscribers("varoitukset", "nonexistent")
        self.assertEqual(empty_subscribers, [])

    def test_get_user_subscriptions(self):
        """Test getting all subscriptions for a specific user."""
        # Add multiple subscriptions for a user
        toggle_subscription("jampsix", "server1", "varoitukset")
        toggle_subscription("jampsix", "server1", "onnettomuustiedotteet")
        toggle_subscription("jampsix", "server2", "varoitukset")

        # Get subscriptions for user on server1
        subscriptions = get_user_subscriptions("jampsix", "server1")
        self.assertEqual(
            sorted(subscriptions), sorted(["varoitukset", "onnettomuustiedotteet"])
        )

        # Get subscriptions for user on server2
        subscriptions = get_user_subscriptions("jampsix", "server2")
        self.assertEqual(subscriptions, ["varoitukset"])

        # Test non-existent user
        empty_subscriptions = get_user_subscriptions("nonexistent", "server1")
        self.assertEqual(empty_subscriptions, [])

    def test_multiple_subscriptions_same_user(self):
        """Test handling multiple subscriptions for the same user."""
        # Add multiple subscriptions
        toggle_subscription("jampsix", "server1", "varoitukset")
        toggle_subscription("jampsix", "server1", "onnettomuustiedotteet")

        # Check both subscriptions exist
        varoitukset_subs = get_server_subscribers("varoitukset", "server1")
        onnettomuus_subs = get_server_subscribers("onnettomuustiedotteet", "server1")

        self.assertIn("jampsix", varoitukset_subs)
        self.assertIn("jampsix", onnettomuus_subs)

        # Remove one subscription
        toggle_subscription("jampsix", "server1", "varoitukset")

        # Check that only one was removed
        varoitukset_subs = get_server_subscribers("varoitukset", "server1")
        onnettomuus_subs = get_server_subscribers("onnettomuustiedotteet", "server1")

        self.assertNotIn("jampsix", varoitukset_subs)
        self.assertIn("jampsix", onnettomuus_subs)

    def test_cleanup_empty_entries(self):
        """Test that empty entries are cleaned up properly."""
        # Add a subscription
        toggle_subscription("jampsix", "server1", "varoitukset")

        # Remove it
        toggle_subscription("jampsix", "server1", "varoitukset")

        # Check that empty entries are cleaned up
        data = load_subscriptions()
        self.assertEqual(data, {})

    def test_persistence_across_operations(self):
        """Test that subscriptions persist across multiple operations."""
        # Add subscriptions
        toggle_subscription("user1", "server1", "varoitukset")
        toggle_subscription("user2", "server1", "onnettomuustiedotteet")

        # Verify persistence by loading fresh data
        data = load_subscriptions()
        expected = {
            "server1": {"user1": ["varoitukset"], "user2": ["onnettomuustiedotteet"]}
        }
        self.assertEqual(data, expected)

    def test_atomic_writes(self):
        """Test that writes are atomic (using temporary file)."""
        # This test verifies that the atomic write mechanism works
        # by checking that the specific temp file for subscriptions is cleaned up
        test_data = {"server1": {"user1": ["varoitukset"]}}

        result = save_subscriptions(test_data)
        self.assertTrue(result)

        # Check that the specific subscription temp file is cleaned up
        # We can't check the entire temp directory on Windows as it's shared
        subscription_temp_file = f"{self.temp_file.name}.tmp"
        self.assertFalse(os.path.exists(subscription_temp_file))

    def test_valid_topics_constant(self):
        """Test that VALID_TOPICS contains expected topics."""
        self.assertIn("varoitukset", VALID_TOPICS)
        self.assertIn("onnettomuustiedotteet", VALID_TOPICS)
        self.assertEqual(len(VALID_TOPICS), 2)

    def test_concurrent_access_simulation(self):
        """Test handling of concurrent access patterns."""
        # Simulate multiple rapid operations
        for i in range(10):
            toggle_subscription(f"user{i}", "server1", "varoitukset")

        # Verify all subscriptions were added
        subscribers = get_server_subscribers("varoitukset", "server1")
        expected_users = [f"user{i}" for i in range(10)]
        self.assertEqual(sorted(subscribers), sorted(expected_users))

    def test_save_subscriptions_error_handling(self):
        """Test error handling in save_subscriptions."""
        # Test with invalid data that gets cleaned
        invalid_data = {
            "server1": {
                "123invalid": ["varoitukset"],  # Invalid nick
                "validuser": ["invalid_topic"],  # Invalid topic
            }
        }

        result = save_subscriptions(invalid_data)
        self.assertTrue(result)

        # Verify only valid data was saved
        data = load_subscriptions()
        self.assertEqual(data, {})  # All data was invalid, so empty result


if __name__ == "__main__":
    unittest.main()
