"""
Test file for Tamagotchi toggle functionality.

This test verifies that the toggle function properly turns tamagotchi responses on/off
and persists the setting to the .env file.
"""

import os
import tempfile
import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import shutil

# Add the project root to the path
sys.path.insert(0, os.path.dirname(__file__))

from bot_manager import BotManager
from word_tracking.tamagotchi_bot import TamagotchiBot
from word_tracking.data_manager import DataManager

class TestTamagotchiToggle(unittest.TestCase):
    """Test cases for tamagotchi toggle functionality."""

    def setUp(self):
        """Set up test environment with temporary .env file."""
        # Create a temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        
        # Create a test .env file
        self.env_content = """# Test environment file
BOT_NAME=TestBot
TAMAGOTCHI_ENABLED=true
USE_NOTICES=false
"""
        with open(".env", "w", encoding="utf-8") as f:
            f.write(self.env_content)
        
        # Mock the data manager to avoid file system operations
        self.mock_data_manager = Mock(spec=DataManager)
        self.mock_data_manager.load_tamagotchi_state.return_value = {"servers": {}}
        self.mock_data_manager.save_tamagotchi_state.return_value = None
        
        # Mock the data methods to return proper dictionaries instead of Mock objects
        self.mock_data_manager.load_general_words_data.return_value = {"servers": {}}
        self.mock_data_manager.save_general_words_data.return_value = None
        self.mock_data_manager.load_drink_data.return_value = {"servers": {}}
        self.mock_data_manager.save_drink_data.return_value = None
        self.mock_data_manager.get_server_name.return_value = "test_server"
        
        # Create test bot manager
        with patch('bot_manager.DataManager', return_value=self.mock_data_manager):
            with patch('bot_manager.get_api_key', return_value=None):
                with patch('bot_manager.create_crypto_service', return_value=Mock()):
                    with patch('bot_manager.create_nanoleet_detector', return_value=Mock()):
                        with patch('bot_manager.create_fmi_warning_service', return_value=Mock()):
                            with patch('bot_manager.create_otiedote_service', return_value=Mock()):
                                with patch('bot_manager.Lemmatizer', side_effect=Exception("Mock error")):
                                    self.bot_manager = BotManager("TestBot")
        
        # Mock server and target
        self.mock_server = Mock()
        self.mock_server.config.name = "test_server"
        self.test_target = "#test_channel"
        self.test_sender = "test_user"

    def tearDown(self):
        """Clean up test environment."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    def test_toggle_tamagotchi_enabled_to_disabled(self):
        """Test toggling tamagotchi from enabled to disabled."""
        # Initially enabled
        self.assertTrue(self.bot_manager.tamagotchi_enabled)
        
        # Mock the _send_response method
        self.bot_manager._send_response = Mock()
        
        # Toggle to disabled
        response = self.bot_manager.toggle_tamagotchi(
            self.mock_server, self.test_target, self.test_sender
        )
        
        # Check that it's now disabled
        self.assertFalse(self.bot_manager.tamagotchi_enabled)
        
        # Check response message
        self.assertIn("disabled", response)
        self.assertIn("💤", response)
        
        # Check that _send_response was called
        self.bot_manager._send_response.assert_called_once()
        
        # Verify .env file was updated
        with open(".env", "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("TAMAGOTCHI_ENABLED=false", content)

    def test_toggle_tamagotchi_disabled_to_enabled(self):
        """Test toggling tamagotchi from disabled to enabled."""
        # Start with disabled
        self.bot_manager.tamagotchi_enabled = False
        
        # Mock the _send_response method
        self.bot_manager._send_response = Mock()
        
        # Toggle to enabled
        response = self.bot_manager.toggle_tamagotchi(
            self.mock_server, self.test_target, self.test_sender
        )
        
        # Check that it's now enabled
        self.assertTrue(self.bot_manager.tamagotchi_enabled)
        
        # Check response message
        self.assertIn("enabled", response)
        self.assertIn("🐣", response)
        
        # Check that _send_response was called
        self.bot_manager._send_response.assert_called_once()
        
        # Verify .env file was updated
        with open(".env", "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("TAMAGOTCHI_ENABLED=true", content)

    def test_toggle_multiple_times(self):
        """Test toggling multiple times to ensure it works correctly."""
        initial_state = self.bot_manager.tamagotchi_enabled
        
        # Mock the _send_response method
        self.bot_manager._send_response = Mock()
        
        # Toggle twice
        self.bot_manager.toggle_tamagotchi(
            self.mock_server, self.test_target, self.test_sender
        )
        first_toggle_state = self.bot_manager.tamagotchi_enabled
        
        self.bot_manager.toggle_tamagotchi(
            self.mock_server, self.test_target, self.test_sender
        )
        second_toggle_state = self.bot_manager.tamagotchi_enabled
        
        # Should be opposite of initial, then back to initial
        self.assertEqual(initial_state, not first_toggle_state)
        self.assertEqual(initial_state, second_toggle_state)

    def test_tamagotchi_responses_when_disabled(self):
        """Test that tamagotchi doesn't respond when disabled."""
        # Disable tamagotchi
        self.bot_manager.tamagotchi_enabled = False
        
        # Create mock context for message handling
        context = {
            "server": self.mock_server,
            "server_name": "test_server",
            "sender": "test_user",
            "target": "#test_channel",
            "text": "ruoka pizza",  # Should trigger tamagotchi if enabled
            "is_private": False,
            "bot_name": "TestBot"
        }
        
        # Mock the _send_response method to capture any responses
        self.bot_manager._send_response = Mock()
        
        # Process the message through _track_words which should respect tamagotchi_enabled
        self.bot_manager._track_words(context)
        
        # Check that tamagotchi would respond if enabled
        should_respond, response = self.bot_manager.tamagotchi.process_message(
            "test_server", "test_user", "ruoka pizza"
        )
        
        # If tamagotchi would respond to this message but tamagotchi_enabled is False,
        # then _send_response should not be called for tamagotchi
        # Note: _send_response might be called for other tracking purposes, so we need to check calls
        
        # We expect no tamagotchi response when disabled - check that tamagotchi logic was skipped
        # The key test: verify that when tamagotchi_enabled=False, no tamagotchi responses are sent
        
        # Since other tracking might call _send_response, let's be more specific:
        # If tamagotchi would have responded, but it's disabled, the specific tamagotchi response
        # should not be in the calls
        if should_respond and response:
            # Verify the tamagotchi response was NOT sent
            call_args_list = [call[0] for call in self.bot_manager._send_response.call_args_list]
            tamagotchi_response_sent = any(response in str(args) for args in call_args_list)
            self.assertFalse(tamagotchi_response_sent, "Tamagotchi response was sent when disabled")
        
        # Additional verification: check that tamagotchi_enabled flag is respected
        self.assertFalse(self.bot_manager.tamagotchi_enabled)

    def test_tamagotchi_responses_when_enabled(self):
        """Test that tamagotchi responds when enabled."""
        # Ensure tamagotchi is enabled
        self.bot_manager.tamagotchi_enabled = True
        
        # Create mock context for message handling
        context = {
            "server": self.mock_server,
            "server_name": "test_server",
            "sender": "test_user",
            "target": "#test_channel",
            "text": "ruoka pizza",  # Should trigger tamagotchi
            "is_private": False,
            "bot_name": "TestBot"
        }
        
        # Mock the _send_response method to capture responses
        self.bot_manager._send_response = Mock()
        
        # Check if tamagotchi would respond to this message
        should_respond, response = self.bot_manager.tamagotchi.process_message(
            "test_server", "test_user", "ruoka pizza"
        )
        
        # Process the message through _track_words
        self.bot_manager._track_words(context)
        
        # If tamagotchi is supposed to respond and it's enabled, verify response was sent
        if should_respond and response:
            # Verify that _send_response was called with the tamagotchi response
            call_args_list = [call[0] for call in self.bot_manager._send_response.call_args_list]
            tamagotchi_response_sent = any(response in str(args) for args in call_args_list)
            self.assertTrue(tamagotchi_response_sent, "Tamagotchi response was not sent when enabled")
        
        # Verify that tamagotchi_enabled flag is True
        self.assertTrue(self.bot_manager.tamagotchi_enabled)

    def test_env_file_update_failure_handling(self):
        """Test handling of .env file update failures."""
        # Make the .env file read-only to simulate failure
        os.chmod(".env", 0o444)
        
        try:
            # Mock the _send_response method
            self.bot_manager._send_response = Mock()
            
            # Toggle should still work in memory
            initial_state = self.bot_manager.tamagotchi_enabled
            response = self.bot_manager.toggle_tamagotchi(
                self.mock_server, self.test_target, self.test_sender
            )
            
            # State should change in memory
            self.assertEqual(self.bot_manager.tamagotchi_enabled, not initial_state)
            
            # Response should indicate .env update failed
            self.assertIn("session only", response)
            
        finally:
            # Restore file permissions
            os.chmod(".env", 0o644)

    def test_env_file_missing_handling(self):
        """Test handling when .env file doesn't exist."""
        # Remove the .env file
        os.remove(".env")
        
        # Mock the _send_response method
        self.bot_manager._send_response = Mock()
        
        # Toggle should still work in memory
        initial_state = self.bot_manager.tamagotchi_enabled
        response = self.bot_manager.toggle_tamagotchi(
            self.mock_server, self.test_target, self.test_sender
        )
        
        # State should change in memory
        self.assertEqual(self.bot_manager.tamagotchi_enabled, not initial_state)
        
        # Response should indicate .env update failed
        self.assertIn("session only", response)

    def test_toggle_command_integration(self):
        """Test the toggle command through the command processing system."""
        # This would require mocking the full command processing chain
        # For now, we'll test the integration point directly
        
        # Mock all required bot functions
        bot_functions = {
            "toggle_tamagotchi": lambda: self.bot_manager.toggle_tamagotchi(
                self.mock_server, self.test_target, self.test_sender
            )
        }
        
        # Test that the toggle function can be called without parameters
        # This simulates how it's called from commands.py
        initial_state = self.bot_manager.tamagotchi_enabled
        
        # Mock the _send_response method
        self.bot_manager._send_response = Mock()
        
        # Call the toggle function as it would be called from commands.py
        toggle_func = bot_functions.get("toggle_tamagotchi")
        if toggle_func:
            result = toggle_func()
            
        # Verify state changed
        self.assertEqual(self.bot_manager.tamagotchi_enabled, not initial_state)


if __name__ == "__main__":
    # Run the tests
    unittest.main(verbosity=2)
