import unittest
from unittest.mock import Mock, patch, mock_open
import tempfile
import os
import json
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from subscriptions import toggle_subscription, get_subscribers, get_server_subscribers

class TestSubscriptionToggle(unittest.TestCase):

    def setUp(self):
        # Create a temporary file for testing
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_file.write('{}')
        self.temp_file.close()
        
        # Patch the SUBSCRIBERS_FILE constant
        self.patcher = patch('subscriptions.SUBSCRIBERS_FILE', self.temp_file.name)
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
        with open(self.temp_file.name, 'r') as f:
            data = json.load(f)
        
        self.assertIn("test_server", data)
        self.assertIn("#test", data["test_server"])
        self.assertIn("varoitukset", data["test_server"]["#test"])

if __name__ == '__main__':
    unittest.main()
