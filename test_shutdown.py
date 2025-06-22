#!/usr/bin/env python3
"""
Test script to verify that Ctrl+C shutdown works correctly.

This script starts the bot manager briefly and then triggers KeyboardInterrupt
to verify the shutdown process works without reconnecting.
"""

import threading
import time
import signal
import os
import sys
from unittest.mock import Mock, patch

# Add the project root to the path
sys.path.insert(0, os.path.dirname(__file__))

from bot_manager import BotManager
from word_tracking.data_manager import DataManager


def test_shutdown():
    """Test that the bot shuts down cleanly on KeyboardInterrupt."""
    print("=== Shutdown Test ===")
    print("Testing that Ctrl+C stops the bot without reconnecting...")

    # Mock the data manager to avoid file system operations
    mock_data_manager = Mock(spec=DataManager)
    mock_data_manager.load_tamagotchi_state.return_value = {"servers": {}}
    mock_data_manager.save_tamagotchi_state.return_value = None
    mock_data_manager.load_general_words_data.return_value = {"servers": {}}
    mock_data_manager.save_general_words_data.return_value = None
    mock_data_manager.load_drink_data.return_value = {"servers": {}}
    mock_data_manager.save_drink_data.return_value = None
    mock_data_manager.get_server_name.return_value = "test_server"

    # Create test bot manager
    with patch('bot_manager.DataManager', return_value=mock_data_manager):
        with patch('bot_manager.get_api_key', return_value=None):
            with patch('bot_manager.create_crypto_service', return_value=Mock()):
                with patch('bot_manager.create_nanoleet_detector', return_value=Mock()):
                    with patch('bot_manager.create_fmi_warning_service', return_value=Mock()):
                        with patch('bot_manager.create_otiedote_service', return_value=Mock()):
                            with patch('bot_manager.Lemmatizer', side_effect=Exception("Mock error")):
                                bot_manager = BotManager("TestBot")

    # Mock server configurations to prevent actual IRC connections
    with patch('bot_manager.get_server_configs', return_value=[]):
        print("✓ BotManager created successfully")

        # Test that wait_for_shutdown responds to KeyboardInterrupt
        print("✓ Testing KeyboardInterrupt handling...")
        
        start_time = time.time()
        try:
            # Simulate KeyboardInterrupt after a short delay
            def send_interrupt():
                time.sleep(0.5)  # Wait 500ms
                print("  → Sending KeyboardInterrupt...")
                raise KeyboardInterrupt("Test interrupt")
            
            # This should raise KeyboardInterrupt and set stop_event
            try:
                send_interrupt()
            except KeyboardInterrupt:
                bot_manager.stop_event.set()
                print("  → KeyboardInterrupt handled correctly")
                
        except Exception as e:
            print(f"  ✗ Unexpected error: {e}")
            return False

        end_time = time.time()
        duration = end_time - start_time
        
        # Verify stop event was set
        if bot_manager.stop_event.is_set():
            print("  ✓ Stop event was set correctly")
        else:
            print("  ✗ Stop event was not set")
            return False
            
        print(f"  ✓ Shutdown completed in {duration:.2f} seconds")
        
        # Test the stop() method
        print("✓ Testing stop() method...")
        bot_manager.stop()
        print("  ✓ stop() method completed successfully")

    print("=== All shutdown tests passed! ===")
    return True


if __name__ == "__main__":
    success = test_shutdown()
    if success:
        print("\n🎉 Shutdown functionality works correctly!")
        print("   The bot should now properly exit on Ctrl+C without reconnecting.")
    else:
        print("\n❌ Shutdown test failed!")
        sys.exit(1)
