import unittest
from unittest.mock import Mock, patch
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot_manager import BotManager

class TestSubscriptionWarnings(unittest.TestCase):

    def setUp(self):
        # Mock all the external dependencies
        with patch('bot_manager.DataManager'), \
             patch('bot_manager.get_api_key', return_value=None), \
             patch('bot_manager.create_crypto_service', return_value=Mock()), \
             patch('bot_manager.create_nanoleet_detector', return_value=Mock()), \
             patch('bot_manager.create_fmi_warning_service', return_value=Mock()), \
             patch('bot_manager.create_otiedote_service', return_value=Mock()), \
             patch('bot_manager.Lemmatizer', side_effect=Exception("Mock error")):
            
            self.bot_manager = BotManager("TestBot")
            
        # Create mock server configuration
        self.mock_server = Mock()
        self.mock_server.config.name = "test_server"
        self.mock_server.config.channels = ["test", "main"]
        self.bot_manager.servers = {"test_server": self.mock_server}

    def test_handle_fmi_warnings_with_subscribers(self):
        """Test that FMI warnings are sent to subscribers."""
        # Mock the subscriptions module
        mock_subscriptions = Mock()
        mock_subscriptions.get_subscribers.return_value = ["#test", "user1"]
        
        with patch.object(self.bot_manager, '_get_subscriptions_module', return_value=mock_subscriptions):
            # Mock the _send_response method to track calls
            with patch.object(self.bot_manager, '_send_response') as mock_send:
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
        
        with patch.object(self.bot_manager, '_get_subscriptions_module', return_value=mock_subscriptions):
            # Mock the _send_response method to track calls
            with patch.object(self.bot_manager, '_send_response') as mock_send:
                # Call the method with a test warning
                self.bot_manager._handle_fmi_warnings(["Test warning"])
                
                # Verify that no messages were sent
                mock_send.assert_not_called()

    def test_handle_fmi_warnings_channel_not_in_server(self):
        """Test handling of channels not in server configuration."""
        # Mock the subscriptions module to return a channel not in server config
        mock_subscriptions = Mock()
        mock_subscriptions.get_subscribers.return_value = ["#nonexistent"]
        
        with patch.object(self.bot_manager, '_get_subscriptions_module', return_value=mock_subscriptions):
            # Mock the _send_response method to track calls
            with patch.object(self.bot_manager, '_send_response') as mock_send:
                # Call the method with a test warning
                self.bot_manager._handle_fmi_warnings(["Test warning"])
                
                # Verify that no messages were sent
                mock_send.assert_not_called()

if __name__ == '__main__':
    unittest.main()
