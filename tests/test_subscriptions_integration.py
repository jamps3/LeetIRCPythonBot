"""
Integration test for the subscription system to ensure the enhanced functionality works.
"""

import unittest
import tempfile
import os
import sys
from unittest.mock import Mock, patch

# Add the parent directory to the path to import the subscriptions module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from subscriptions import toggle_subscription, get_subscribers, get_server_subscribers


class TestSubscriptionIntegration(unittest.TestCase):
    """Integration tests for subscription system."""

    def setUp(self):
        """Set up test environment with temporary file."""
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_file.write('{}')
        self.temp_file.close()
        
        # Patch the SUBSCRIBERS_FILE constant
        self.patcher = patch('subscriptions.SUBSCRIBERS_FILE', self.temp_file.name)
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
        from subscriptions import load_subscriptions
        data = load_subscriptions()
        
        # Data should still be there
        self.assertIn("server1", data)
        self.assertIn("persistuser", data["server1"])
        self.assertIn("varoitukset", data["server1"]["persistuser"])


if __name__ == '__main__':
    unittest.main()
