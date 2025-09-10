#!/usr/bin/env python3
"""
Subscription-related tests.
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, mock_open, patch

# Add the parent directory to sys.path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot_manager import BotManager  # noqa: E402
from subscriptions import (  # noqa: E402
    VALID_TOPICS,
    format_all_subscriptions,
    format_channel_subscriptions,
    format_server_subscriptions,
    format_user_subscriptions,
    get_all_subscriptions,
    get_server_subscribers,
    get_subscribers,
    get_user_subscriptions,
    is_valid_nick_or_channel,
    load_subscriptions,
    save_subscriptions,
    toggle_subscription,
    validate_and_clean_data,
)


class TestSubscriptionToggle(unittest.TestCase):

    def setUp(self):
        # Create a temporary file for testing
        self.temp_file = tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".json"
        )
        self.temp_file.write("{}")
        self.temp_file.close()

        # Patch the SUBSCRIBERS_FILE constant
        self.patcher = patch("subscriptions.SUBSCRIBERS_FILE", self.temp_file.name)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)

    def test_toggle_subscription_add(self):
        """Test adding a subscription."""
        result = toggle_subscription("#test", "test_server", "varoitukset")
        self.assertIn("✅ Tilaus lisätty", result)

        # Verify subscription was added
        subscribers = get_subscribers("varoitukset")
        self.assertIn(("#test", "test_server"), subscribers)

    def test_toggle_subscription_remove(self):
        """Test removing a subscription."""
        # First add a subscription
        toggle_subscription("#test", "test_server", "varoitukset")

        # Then remove it
        result = toggle_subscription("#test", "test_server", "varoitukset")
        self.assertIn("❌ Poistettu tilaus", result)

        # Verify subscription was removed
        subscribers = get_subscribers("varoitukset")
        self.assertNotIn(("#test", "test_server"), subscribers)

    def test_multiple_subscriptions(self):
        """Test handling multiple subscriptions."""
        # Add multiple subscriptions
        toggle_subscription("#test1", "test_server", "varoitukset")
        toggle_subscription("#test2", "test_server", "varoitukset")
        toggle_subscription("#test1", "test_server", "onnettomuustiedotteet")

        # Check varoitukset subscribers
        varoitukset_subscribers = get_subscribers("varoitukset")
        self.assertIn(("#test1", "test_server"), varoitukset_subscribers)
        self.assertIn(("#test2", "test_server"), varoitukset_subscribers)

        # Check onnettomuustiedotteet subscribers
        onnettomuustiedotteet_subscribers = get_subscribers("onnettomuustiedotteet")
        self.assertIn(("#test1", "test_server"), onnettomuustiedotteet_subscribers)
        self.assertNotIn(("#test2", "test_server"), onnettomuustiedotteet_subscribers)

    def test_get_subscribers_empty(self):
        """Test getting subscribers when none exist."""
        subscribers = get_subscribers("varoitukset")
        self.assertEqual(subscribers, [])

    def test_persistence(self):
        """Test that subscriptions persist between calls."""
        # Add a subscription
        toggle_subscription("#test", "test_server", "varoitukset")

        # Check that it's persisted by reading file directly
        with open(self.temp_file.name, "r") as f:
            data = json.load(f)

        self.assertIn("test_server", data)
        self.assertIn("#test", data["test_server"])
        self.assertIn("varoitukset", data["test_server"]["#test"])


class TestSubscriptionWarnings(unittest.TestCase):

    def setUp(self):
        # Mock all the external dependencies
        with patch("bot_manager.DataManager"), patch(
            "bot_manager.get_api_key", return_value=None
        ), patch("bot_manager.create_crypto_service", return_value=Mock()), patch(
            "bot_manager.create_nanoleet_detector", return_value=Mock()
        ), patch(
            "bot_manager.create_fmi_warning_service", return_value=Mock()
        ), patch(
            "bot_manager.create_otiedote_service", return_value=Mock()
        ), patch(
            "bot_manager.Lemmatizer", side_effect=Exception("Mock error")
        ):

            self.bot_manager = BotManager("TestBot")

        # Create mock server configuration
        self.mock_server = Mock()
        self.mock_server.config.name = "test_server"
        self.mock_server.config.channels = ["test", "main"]
        self.bot_manager.servers = {"test_server": self.mock_server}

    def test_handle_fmi_warnings_with_subscribers(self):
        """Test that FMI warnings are sent to subscribers."""
        # Mock the subscriptions module - new format returns (nick, server) tuples
        mock_subscriptions = Mock()
        mock_subscriptions.get_subscribers.return_value = [
            ("#test", "test_server"),
            ("user1", "test_server"),
        ]

        with patch.object(
            self.bot_manager,
            "_get_subscriptions_module",
            return_value=mock_subscriptions,
        ):
            # Mock the _send_response method to track calls
            with patch.object(self.bot_manager, "_send_response") as mock_send:
                # Call the method with a test warning
                self.bot_manager._handle_fmi_warnings(["Test warning"])

                # Verify that the warning was sent to the channel
                mock_send.assert_any_call(self.mock_server, "#test", "Test warning")

                # Verify that the warning was sent to the user
                mock_send.assert_any_call(self.mock_server, "user1", "Test warning")

    def test_handle_fmi_warnings_no_subscribers(self):
        """Test that FMI warnings are not sent when no subscribers."""
        # Mock the subscriptions module to return empty subscribers
        mock_subscriptions = Mock()
        mock_subscriptions.get_subscribers.return_value = []

        with patch.object(
            self.bot_manager,
            "_get_subscriptions_module",
            return_value=mock_subscriptions,
        ):
            # Mock the _send_response method to track calls
            with patch.object(self.bot_manager, "_send_response") as mock_send:
                # Call the method with a test warning
                self.bot_manager._handle_fmi_warnings(["Test warning"])

                # Verify that no messages were sent
                mock_send.assert_not_called()

    def test_handle_fmi_warnings_server_not_found(self):
        """Test handling of subscribers on non-existent servers."""
        # Mock the subscriptions module to return a subscriber on non-existent server
        mock_subscriptions = Mock()
        mock_subscriptions.get_subscribers.return_value = [
            ("#test", "nonexistent_server")
        ]

        with patch.object(
            self.bot_manager,
            "_get_subscriptions_module",
            return_value=mock_subscriptions,
        ):
            # Mock the _send_response method to track calls
            with patch.object(self.bot_manager, "_send_response") as mock_send:
                # Call the method with a test warning
                self.bot_manager._handle_fmi_warnings(["Test warning"])

                # Verify that no messages were sent
                mock_send.assert_not_called()


class TestSubscriptionIntegration(unittest.TestCase):
    """Integration tests for subscription system."""

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

    def test_end_to_end_subscription_workflow(self):
        """Test complete subscription workflow from command to notification."""
        # Test adding subscriptions for different servers
        result1 = toggle_subscription("user1", "server1", "varoitukset")
        self.assertIn("✅ Tilaus lisätty", result1)
        self.assertIn("user1 on network server1", result1)

        result2 = toggle_subscription("#channel", "server2", "onnettomuustiedotteet")
        self.assertIn("✅ Tilaus lisätty", result2)
        self.assertIn("#channel on network server2", result2)

        # Test getting subscribers for notification system
        varoitukset_subscribers = get_subscribers("varoitukset")
        self.assertIn(("user1", "server1"), varoitukset_subscribers)

        onnettomuus_subscribers = get_subscribers("onnettomuustiedotteet")
        self.assertIn(("#channel", "server2"), onnettomuus_subscribers)

        # Test server-specific subscribers
        server1_subscribers = get_server_subscribers("varoitukset", "server1")
        self.assertIn("user1", server1_subscribers)

        server2_subscribers = get_server_subscribers("onnettomuustiedotteet", "server2")
        self.assertIn("#channel", server2_subscribers)

        # Test removing subscription
        result3 = toggle_subscription("user1", "server1", "varoitukset")
        self.assertIn("❌ Poistettu tilaus", result3)

        # Verify removal
        varoitukset_subscribers = get_subscribers("varoitukset")
        self.assertNotIn(("user1", "server1"), varoitukset_subscribers)

    def test_subscription_validation(self):
        """Test that subscriptions are validated properly."""
        # Test invalid topic
        result = toggle_subscription("user1", "server1", "invalid_topic")
        self.assertIn("❌ Invalid topic", result)

        # Test invalid nick
        result = toggle_subscription("123invalid", "server1", "varoitukset")
        self.assertIn("❌ Invalid nick/channel", result)

        # Test valid channel
        result = toggle_subscription("#test", "server1", "varoitukset")
        self.assertIn("✅ Tilaus lisätty", result)

    def test_cross_server_subscriptions(self):
        """Test that subscriptions work correctly across multiple servers."""
        # Add same user to different servers
        toggle_subscription("user1", "server1", "varoitukset")
        toggle_subscription("user1", "server2", "varoitukset")

        # Both should be in global subscribers
        all_subscribers = get_subscribers("varoitukset")
        self.assertIn(("user1", "server1"), all_subscribers)
        self.assertIn(("user1", "server2"), all_subscribers)

        # Server-specific lists should be separate
        server1_subscribers = get_server_subscribers("varoitukset", "server1")
        server2_subscribers = get_server_subscribers("varoitukset", "server2")

        self.assertIn("user1", server1_subscribers)
        self.assertIn("user1", server2_subscribers)

        # Remove from one server shouldn't affect the other
        toggle_subscription("user1", "server1", "varoitukset")

        server1_subscribers = get_server_subscribers("varoitukset", "server1")
        server2_subscribers = get_server_subscribers("varoitukset", "server2")

        self.assertNotIn("user1", server1_subscribers)
        self.assertIn("user1", server2_subscribers)

    def test_message_format_details(self):
        """Test that subscription messages contain all necessary details."""
        # Test subscription message format
        result = toggle_subscription("testuser", "test.server.com", "varoitukset")

        # Should contain all key information
        self.assertIn("✅ Tilaus lisätty", result)
        self.assertIn("testuser", result)
        self.assertIn("test.server.com", result)
        self.assertIn("varoitukset", result)

        # Test removal message format
        result = toggle_subscription("testuser", "test.server.com", "varoitukset")

        self.assertIn("❌ Poistettu tilaus", result)
        self.assertIn("testuser", result)
        self.assertIn("test.server.com", result)
        self.assertIn("varoitukset", result)

    def test_channel_and_nick_handling(self):
        """Test proper handling of both channels and nicks."""
        # Test channel subscription
        result = toggle_subscription("#alerts", "server1", "varoitukset")
        self.assertIn("✅ Tilaus lisätty", result)
        self.assertIn("#alerts", result)

        # Test nick subscription
        result = toggle_subscription("alertuser", "server1", "varoitukset")
        self.assertIn("✅ Tilaus lisätty", result)
        self.assertIn("alertuser", result)

        # Both should be in subscribers
        subscribers = get_server_subscribers("varoitukset", "server1")
        self.assertIn("#alerts", subscribers)
        self.assertIn("alertuser", subscribers)

    def test_data_persistence(self):
        """Test that subscription data persists correctly."""
        # Add subscription
        toggle_subscription("persistuser", "server1", "varoitukset")

        # Verify it exists
        subscribers = get_server_subscribers("varoitukset", "server1")
        self.assertIn("persistuser", subscribers)

        # Create new subscription system instance (simulating restart)
        data = load_subscriptions()

        # Data should still be there
        self.assertIn("server1", data)
        self.assertIn("persistuser", data["server1"])
        self.assertIn("varoitukset", data["server1"]["persistuser"])


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
        self.assertTrue(is_valid_nick_or_channel("jamps3"))
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
            "server1": {"jamps3": ["varoitukset"], "#test": ["onnettomuustiedotteet"]},
            "server2": {"user123": ["varoitukset", "onnettomuustiedotteet"]},
        }
        cleaned = validate_and_clean_data(valid_data)
        self.assertEqual(cleaned, valid_data)

        # Invalid data that should be cleaned
        invalid_data = {
            "server1": {
                "jamps3": ["varoitukset", "invalid_topic"],  # Invalid topic
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
            "server1": {"jamps3": ["varoitukset"], "#test": ["onnettomuustiedotteet"]}
        }
        self.assertEqual(cleaned, expected)

    def test_load_subscriptions_empty_file(self):
        """Test loading subscriptions from empty file."""
        result = load_subscriptions()
        self.assertEqual(result, {})

    def test_load_subscriptions_valid_data(self):
        """Test loading subscriptions with valid data."""
        test_data = {
            "server1": {"jamps3": ["varoitukset"], "#test": ["onnettomuustiedotteet"]}
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
                "jamps3": ["varoitukset", "invalid_topic"],
                "123invalid": ["varoitukset"],
                "#test": ["onnettomuustiedotteet"],
            }
        }

        with open(self.temp_file.name, "w", encoding="utf-8") as f:
            json.dump(malformed_data, f)

        result = load_subscriptions()
        expected = {
            "server1": {"jamps3": ["varoitukset"], "#test": ["onnettomuustiedotteet"]}
        }
        self.assertEqual(result, expected)

        # Check that cleaned data was saved back
        with open(self.temp_file.name, "r", encoding="utf-8") as f:
            saved_data = json.load(f)
        self.assertEqual(saved_data, expected)

    def test_save_subscriptions_success(self):
        """Test successful subscription saving."""
        test_data = {
            "server1": {"jamps3": ["varoitukset"], "#test": ["onnettomuustiedotteet"]}
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
        result = toggle_subscription("jamps3", "server1", "varoitukset")
        self.assertIn("✅ Tilaus lisätty", result)
        self.assertIn("jamps3", result)
        self.assertIn("server1", result)
        self.assertIn("varoitukset", result)

        # Verify subscription was added
        subscribers = get_subscribers("varoitukset")
        self.assertIn(("jamps3", "server1"), subscribers)

    def test_toggle_subscription_remove(self):
        """Test removing a subscription."""
        # First add a subscription
        toggle_subscription("jamps3", "server1", "varoitukset")

        # Then remove it
        result = toggle_subscription("jamps3", "server1", "varoitukset")
        self.assertIn("❌ Poistettu tilaus", result)
        self.assertIn("jamps3", result)
        self.assertIn("server1", result)
        self.assertIn("varoitukset", result)

        # Verify subscription was removed
        subscribers = get_subscribers("varoitukset")
        self.assertNotIn(("jamps3", "server1"), subscribers)

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
        toggle_subscription("jamps3", "server1", "varoitukset")
        toggle_subscription("jamps3", "server1", "onnettomuustiedotteet")
        toggle_subscription("jamps3", "server2", "varoitukset")

        # Get subscriptions for user on server1
        subscriptions = get_user_subscriptions("jamps3", "server1")
        self.assertEqual(
            sorted(subscriptions), sorted(["varoitukset", "onnettomuustiedotteet"])
        )

        # Get subscriptions for user on server2
        subscriptions = get_user_subscriptions("jamps3", "server2")
        self.assertEqual(subscriptions, ["varoitukset"])

        # Test non-existent user
        empty_subscriptions = get_user_subscriptions("nonexistent", "server1")
        self.assertEqual(empty_subscriptions, [])

    def test_multiple_subscriptions_same_user(self):
        """Test handling multiple subscriptions for the same user."""
        # Add multiple subscriptions
        toggle_subscription("jamps3", "server1", "varoitukset")
        toggle_subscription("jamps3", "server1", "onnettomuustiedotteet")

        # Check both subscriptions exist
        varoitukset_subs = get_server_subscribers("varoitukset", "server1")
        onnettomuus_subs = get_server_subscribers("onnettomuustiedotteet", "server1")

        self.assertIn("jamps3", varoitukset_subs)
        self.assertIn("jamps3", onnettomuus_subs)

        # Remove one subscription
        toggle_subscription("jamps3", "server1", "varoitukset")

        # Check that only one was removed
        varoitukset_subs = get_server_subscribers("varoitukset", "server1")
        onnettomuus_subs = get_server_subscribers("onnettomuustiedotteet", "server1")

        self.assertNotIn("jamps3", varoitukset_subs)
        self.assertIn("jamps3", onnettomuus_subs)

    def test_cleanup_empty_entries(self):
        """Test that empty entries are cleaned up properly."""
        # Add a subscription
        toggle_subscription("jamps3", "server1", "varoitukset")

        # Remove it
        toggle_subscription("jamps3", "server1", "varoitukset")

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

    def test_format_user_subscriptions_empty(self):
        """Test formatting user subscriptions when user has no subscriptions."""
        result = format_user_subscriptions("testuser", "server1")
        self.assertIn("ei ole tilannut", result)
        self.assertIn("testuser", result)

    def test_format_user_subscriptions_with_data(self):
        """Test formatting user subscriptions when user has subscriptions."""
        # Add some subscriptions
        toggle_subscription("testuser", "server1", "varoitukset")
        toggle_subscription("testuser", "server1", "onnettomuustiedotteet")

        result = format_user_subscriptions("testuser", "server1")
        self.assertIn("on tilannut", result)
        self.assertIn("testuser", result)
        self.assertIn("varoitukset", result)
        self.assertIn("onnettomuustiedotteet", result)

    def test_get_all_subscriptions_empty(self):
        """Test getting all subscriptions when none exist."""
        result = get_all_subscriptions()
        self.assertEqual(result, {})

    def test_get_all_subscriptions_with_data(self):
        """Test getting all subscriptions with data."""
        toggle_subscription("user1", "server1", "varoitukset")
        toggle_subscription("user2", "server2", "onnettomuustiedotteet")

        result = get_all_subscriptions()
        expected = {
            "server1": {"user1": ["varoitukset"]},
            "server2": {"user2": ["onnettomuustiedotteet"]},
        }
        self.assertEqual(result, expected)

    def test_format_all_subscriptions_empty(self):
        """Test formatting all subscriptions when none exist."""
        result = format_all_subscriptions()
        self.assertIn("Ei tilauksia", result)

    def test_format_all_subscriptions_with_data(self):
        """Test formatting all subscriptions with data."""
        toggle_subscription("user1", "server1", "varoitukset")
        toggle_subscription("#channel", "server2", "onnettomuustiedotteet")

        result = format_all_subscriptions()
        self.assertIn("Kaikki tilaukset", result)
        self.assertIn("server1", result)
        self.assertIn("user1", result)
        self.assertIn("varoitukset", result)
        self.assertIn("server2", result)
        self.assertIn("#channel", result)
        self.assertIn("onnettomuustiedotteet", result)

    def test_format_server_subscriptions_empty(self):
        """Test formatting server subscriptions when none exist."""
        result = format_server_subscriptions("server1")
        self.assertIn("Ei tilauksia", result)
        self.assertIn("server1", result)

    def test_format_server_subscriptions_with_data(self):
        """Test formatting server subscriptions with data."""
        toggle_subscription("user1", "server1", "varoitukset")
        toggle_subscription("#channel", "server1", "onnettomuustiedotteet")
        toggle_subscription("user2", "server2", "varoitukset")  # Different server

        result = format_server_subscriptions("server1")
        self.assertIn("Tilaukset palvelimella server1", result)
        self.assertIn("user1", result)
        self.assertIn("#channel", result)
        self.assertNotIn("user2", result)

    def test_format_channel_subscriptions_empty(self):
        """Test formatting channel subscriptions when none exist."""
        result = format_channel_subscriptions("#channel", "server1")
        self.assertIn("ei ole tilannut", result)
        self.assertIn("#channel", result)

    def test_format_channel_subscriptions_with_data(self):
        """Test formatting channel subscriptions with data."""
        toggle_subscription("#channel", "server1", "varoitukset")

        result = format_channel_subscriptions("#channel", "server1")
        self.assertIn("on tilannut", result)
        self.assertIn("#channel", result)
        self.assertIn("varoitukset", result)


class TestTilaaChannelFix(unittest.TestCase):
    """Test that !tilaa command correctly handles channel subscriptions."""

    def setUp(self):
        # Create temporary file for subscriptions
        self.temp_file = tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".json"
        )
        self.temp_file.write("{}")
        self.temp_file.close()

        # Patch the SUBSCRIBERS_FILE constant
        self.patcher = patch("subscriptions.SUBSCRIBERS_FILE", self.temp_file.name)
        self.patcher.start()

        # Create mock IRC connection and simple data manager stub
        self.mock_irc = Mock()

    def tearDown(self):
        self.patcher.stop()
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)

    def test_tilaa_subscribes_channel_when_called_from_channel(self):
        import subscriptions

        responses = []

        def mock_notice(msg, irc, target):
            responses.append(msg)

        def mock_log(msg, level="INFO"):
            pass

        # Minimal bot_functions needed for enhanced_process_irc_message
        bot_functions = {
            "notice_message": mock_notice,
            "log": mock_log,
            "subscriptions": subscriptions,
            "data_manager": Mock(get_server_name=Mock(return_value="test_server")),
            "send_electricity_price": lambda *args: None,
            "measure_latency": lambda *args: None,
            "get_crypto_price": lambda *args: "1000",
            "load_leet_winners": lambda: {},
            "save_leet_winners": lambda x: None,
            "send_weather": lambda *args: None,
            "send_scheduled_message": lambda *args: None,
            "search_youtube": lambda x: "YouTube result",
            "handle_ipfs_command": lambda *args: None,
            "lookup": lambda x: "test_server",
            "format_counts": lambda x: "formatted counts",
            "chat_with_gpt": lambda x: f"AI: {x}",
            "wrap_irc_message_utf8_bytes": lambda msg, **kwargs: [msg],
            "send_message": lambda irc, target, msg: None,
            "fetch_title": lambda *args: None,
            "lemmat": Mock(),
            "EKAVIKA_FILE": "test_ekavika.json",
            "bot_name": "testbot",
            "latency_start": lambda: 0,
            "set_latency_start": lambda x: None,
        }

        test_message = ":jamps!user@host.com PRIVMSG #joensuu :!tilaa varoitukset"
        from command_loader import enhanced_process_irc_message

        enhanced_process_irc_message(self.mock_irc, test_message, bot_functions)

        self.assertTrue(responses, "Should have gotten a response")
        response = responses[0]
        self.assertIn("✅", response)
        self.assertIn("#joensuu", response)
        self.assertIn("varoitukset", response)

        all_subs = subscriptions.get_all_subscriptions()
        channel_subscribed = any(
            "#joensuu" in server_subs and "varoitukset" in server_subs["#joensuu"]
            for server_subs in all_subs.values()
        )
        self.assertTrue(
            channel_subscribed,
            f"Channel should be subscribed somewhere, got: {all_subs}",
        )

    def test_tilaa_subscribes_user_when_called_from_private_message(self):
        import subscriptions

        responses = []

        def mock_notice(msg, irc, target):
            responses.append(msg)

        def mock_log(msg, level="INFO"):
            pass

        bot_functions = {
            "notice_message": mock_notice,
            "log": mock_log,
            "subscriptions": subscriptions,
            "data_manager": Mock(get_server_name=Mock(return_value="test_server")),
            "bot_name": "testbot",
            "send_electricity_price": lambda *args: None,
            "measure_latency": lambda *args: None,
            "get_crypto_price": lambda *args: "1000",
            "load_leet_winners": lambda: {},
            "save_leet_winners": lambda x: None,
            "send_weather": lambda *args: None,
            "send_scheduled_message": lambda *args: None,
            "search_youtube": lambda x: "YouTube result",
            "handle_ipfs_command": lambda *args: None,
            "lookup": lambda x: "test_server",
            "format_counts": lambda x: "formatted counts",
            "chat_with_gpt": lambda x: f"AI: {x}",
            "wrap_irc_message_utf8_bytes": lambda msg, **kwargs: [msg],
            "send_message": lambda irc, target, msg: None,
            "fetch_title": lambda *args: None,
            "lemmat": Mock(),
            "EKAVIKA_FILE": "test_ekavika.json",
            "latency_start": lambda: 0,
            "set_latency_start": lambda x: None,
        }

        test_message = ":jamps3!user@host.com PRIVMSG testbot :!tilaa varoitukset"
        from command_loader import enhanced_process_irc_message

        enhanced_process_irc_message(self.mock_irc, test_message, bot_functions)

        self.assertTrue(responses, "Should have gotten a response")
        response = responses[0]
        self.assertIn("✅", response)
        self.assertIn("jamps3", response)
        self.assertIn("varoitukset", response)

        all_subs = subscriptions.get_all_subscriptions()
        user_subscribed = any(
            "jamps3" in server_subs and "varoitukset" in server_subs["jamps3"]
            for server_subs in all_subs.values()
        )
        self.assertTrue(
            user_subscribed, f"User should be subscribed somewhere, got: {all_subs}"
        )

    def test_tilaa_allows_override_with_third_parameter(self):
        import subscriptions

        responses = []

        def mock_notice(msg, irc, target):
            responses.append(msg)

        def mock_log(msg, level="INFO"):
            pass

        bot_functions = {
            "notice_message": mock_notice,
            "log": mock_log,
            "subscriptions": subscriptions,
            "data_manager": Mock(get_server_name=Mock(return_value="test_server")),
            "send_electricity_price": lambda *args: None,
            "measure_latency": lambda *args: None,
            "get_crypto_price": lambda *args: "1000",
            "load_leet_winners": lambda: {},
            "save_leet_winners": lambda x: None,
            "send_weather": lambda *args: None,
            "send_scheduled_message": lambda *args: None,
            "search_youtube": lambda x: "YouTube result",
            "handle_ipfs_command": lambda *args: None,
            "lookup": lambda x: "test_server",
            "format_counts": lambda x: "formatted counts",
            "chat_with_gpt": lambda x: f"AI: {x}",
            "wrap_irc_message_utf8_bytes": lambda msg, **kwargs: [msg],
            "send_message": lambda irc, target, msg: None,
            "fetch_title": lambda *args: None,
            "lemmat": Mock(),
            "EKAVIKA_FILE": "test_ekavika.json",
            "bot_name": "testbot",
            "latency_start": lambda: 0,
            "set_latency_start": lambda x: None,
        }

        test_message = (
            ":jamps3!user@host.com PRIVMSG #joensuu :!tilaa varoitukset #other-channel"
        )
        from command_loader import enhanced_process_irc_message

        enhanced_process_irc_message(self.mock_irc, test_message, bot_functions)

        self.assertTrue(responses, "Should have gotten a response")
        response = responses[0]
        self.assertIn("✅", response)
        self.assertIn("#other-channel", response)

        all_subs = subscriptions.get_all_subscriptions()
        override_subscribed = any(
            "#other-channel" in server_subs
            and "varoitukset" in server_subs["#other-channel"]
            for server_subs in all_subs.values()
        )
        original_subscribed = any(
            "#joensuu" in server_subs and "varoitukset" in server_subs["#joensuu"]
            for server_subs in all_subs.values()
        )
        self.assertTrue(
            override_subscribed,
            f"Override channel should be subscribed somewhere, got: {all_subs}",
        )
        self.assertFalse(
            original_subscribed,
            f"Original channel should not be subscribed, got: {all_subs}",
        )

    def test_tilaa_list_shows_channel_subscriptions(self):
        import subscriptions

        responses = []

        def mock_notice(msg, irc, target):
            responses.append(msg)

        def mock_log(msg, level="INFO"):
            pass

        bot_functions = {
            "notice_message": mock_notice,
            "log": mock_log,
            "subscriptions": subscriptions,
            "data_manager": Mock(get_server_name=Mock(return_value="test_server")),
            "send_electricity_price": lambda *args: None,
            "measure_latency": lambda *args: None,
            "get_crypto_price": lambda *args: "1000",
            "load_leet_winners": lambda: {},
            "save_leet_winners": lambda x: None,
            "send_weather": lambda *args: None,
            "send_scheduled_message": lambda *args: None,
            "search_youtube": lambda x: "YouTube result",
            "handle_ipfs_command": lambda *args: None,
            "lookup": lambda x: "test_server",
            "format_counts": lambda x: "formatted counts",
            "chat_with_gpt": lambda x: f"AI: {x}",
            "wrap_irc_message_utf8_bytes": lambda msg, **kwargs: [msg],
            "send_message": lambda irc, target, msg: None,
            "fetch_title": lambda *args: None,
            "lemmat": Mock(),
            "EKAVIKA_FILE": "test_ekavika.json",
            "bot_name": "testbot",
            "latency_start": lambda: 0,
            "set_latency_start": lambda x: None,
        }

        # Add a subscription first
        from command_loader import enhanced_process_irc_message

        enhanced_process_irc_message(
            self.mock_irc,
            ":jamps3!user@host.com PRIVMSG #testchannel :!tilaa varoitukset",
            bot_functions,
        )

        responses.clear()
        # Now list
        enhanced_process_irc_message(
            self.mock_irc,
            ":jamps3!user@host.com PRIVMSG #testchannel :!tilaa list",
            bot_functions,
        )

        self.assertTrue(responses, "Should have gotten a response")
        full_response = " ".join(responses)
        self.assertIn("#testchannel", full_response)
        self.assertNotIn("ei ole tilannut mitään", full_response)


# =========================
# Otiedote subscription tests
# =========================


class TestOtiedoteSubscriptions(unittest.TestCase):
    def setUp(self):
        # Minimal env to avoid external service initialization side effects
        os.environ.setdefault("USE_NOTICES", "false")

        # Create BotManager with one server configured via environment
        # Simulate one server in config by patching get_server_configs
        self.server_name = "test_server"

        server_config_mock = Mock()
        server_config_mock.name = self.server_name
        server_config_mock.host = "localhost"
        server_config_mock.port = 6667
        server_config_mock.channels = ["#general", "#random"]

        # Create a fake Server with send_message/notice capturing
        self.fake_server = Mock()
        self.fake_server.config.name = self.server_name
        self.sent_messages = []

        def capture_send_message(target, message):
            self.sent_messages.append((target, message))

        def capture_send_notice(target, message):
            self.sent_messages.append((target, message))

        self.fake_server.send_message.side_effect = capture_send_message
        self.fake_server.send_notice.side_effect = capture_send_notice

        # Patch BotManager dependencies to control environment
        patches = [
            patch("config.get_server_configs", return_value=[server_config_mock]),
            patch(
                "services.electricity_service.create_electricity_service",
                side_effect=ImportError("skip"),
            ),
            patch("services.gpt_service.GPTService", side_effect=ImportError("skip")),
            patch(
                "services.youtube_service.create_youtube_service",
                side_effect=ImportError("skip"),
            ),
            patch(
                "services.fmi_warning_service.create_fmi_warning_service",
                side_effect=ImportError("skip"),
            ),
            patch(
                "services.crypto_service.create_crypto_service",
                side_effect=ImportError("skip"),
            ),
        ]
        self._patchers = [p.start() for p in patches]
        self.addCleanup(lambda: [p.stop() for p in patches])

        # Build BotManager and inject our server
        self.manager = BotManager("TestBot")
        self.manager.servers = {self.server_name: self.fake_server}

    def test_otiedote_sends_only_to_subscribers(self):
        # Mock subscriptions to return explicit onnettomuustiedotteet subscribers
        mock_subscriptions = Mock()
        mock_subscriptions.get_subscribers.return_value = [
            ("#general", self.server_name),
            ("user1", self.server_name),
        ]

        with patch.object(
            self.manager, "_get_subscriptions_module", return_value=mock_subscriptions
        ):
            # Trigger Otiedote release
            self.manager._handle_otiedote_release("Test Title", "https://example.com")

        # Verify messages sent only to listed subscribers
        targets = [t for (t, _msg) in self.sent_messages]
        assert "#general" in targets
        assert "user1" in targets
        # Should NOT send to other configured channels like #random by broadcast
        assert "#random" not in targets

    def test_otiedote_no_subscribers_sends_nothing(self):
        mock_subscriptions = Mock()
        mock_subscriptions.get_subscribers.return_value = []

        with patch.object(
            self.manager, "_get_subscriptions_module", return_value=mock_subscriptions
        ):
            # Trigger Otiedote release
            self.manager._handle_otiedote_release("Test Title", "https://example.com")

        # Nothing should be sent
        assert self.sent_messages == []


if __name__ == "__main__":
    unittest.main()
