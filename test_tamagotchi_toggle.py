#!/usr/bin/env python3
"""
Test script to verify tamagotchi toggle persistence fix
"""

import json
import os
import tempfile
from unittest.mock import Mock

from bot_manager import BotManager


def test_tamagotchi_toggle_persistence():
    """Test that tamagotchi toggle state persists across bot restarts."""
    print("🧪 Testing tamagotchi toggle persistence...")
    
    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        # Change to temp directory for this test
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        
        try:
            # Mock environment variables to avoid loading real configs
            os.environ["SERVER1_HOST"] = "test.example.com"
            os.environ["SERVER1_PORT"] = "6667"
            os.environ["SERVER1_CHANNELS"] = "#test"
            os.environ["SERVER1_NICK"] = "testbot"
            os.environ["TAMAGOTCHI_ENABLED"] = "true"
            
            print("📋 Test 1: Initial state should be enabled (from env)")
            # Create first bot manager instance
            bot1 = BotManager("testbot")
            assert bot1.tamagotchi_enabled is True
            print("✅ Initial state is enabled")
            
            print("📋 Test 2: Toggle to disabled and verify state file is created")
            # Mock server and target for toggle function
            mock_server = Mock()
            mock_server.config.name = "test_server"
            
            # Toggle tamagotchi off
            bot1.toggle_tamagotchi(mock_server, "#test", "testuser")
            assert bot1.tamagotchi_enabled is False
            print("✅ Tamagotchi toggled to disabled")
            
            # Check that state file was created
            state_file = "tamagotchi_enabled.json"
            assert os.path.exists(state_file)
            with open(state_file, "r") as f:
                state_data = json.load(f)
                assert state_data["enabled"] is False
            print("✅ State file created with correct disabled state")
            
            print("📋 Test 3: Create new bot instance and verify it loads disabled state")
            # Create second bot manager instance (simulating restart)
            bot2 = BotManager("testbot")
            assert bot2.tamagotchi_enabled is False
            print("✅ New bot instance loaded disabled state from file")
            
            print("📋 Test 4: Toggle back to enabled and verify persistence")
            # Toggle tamagotchi back on
            bot2.toggle_tamagotchi(mock_server, "#test", "testuser")
            assert bot2.tamagotchi_enabled is True
            
            # Verify state file is updated
            with open(state_file, "r") as f:
                state_data = json.load(f)
                assert state_data["enabled"] is True
            print("✅ Tamagotchi toggled back to enabled and state file updated")
            
            print("📋 Test 5: Create third bot instance to verify enabled state persists")
            # Create third bot manager instance
            bot3 = BotManager("testbot")
            assert bot3.tamagotchi_enabled is True
            print("✅ Third bot instance loaded enabled state from file")
            
            print("📋 Test 6: Test fallback to environment variable")
            # Remove state file and test fallback
            os.remove(state_file)
            os.environ["TAMAGOTCHI_ENABLED"] = "false"
            bot4 = BotManager("testbot")
            assert bot4.tamagotchi_enabled is False
            print("✅ Fallback to environment variable works when state file missing")
            
            print("🎯 All tests passed! Tamagotchi toggle persistence is working correctly.")
            
        finally:
            # Restore original working directory
            os.chdir(original_cwd)
            # Clean up environment variables
            for key in ["SERVER1_HOST", "SERVER1_PORT", "SERVER1_CHANNELS", "SERVER1_NICK", "TAMAGOTCHI_ENABLED"]:
                if key in os.environ:
                    del os.environ[key]


def test_tamagotchi_processing():
    """Test that tamagotchi messages are only processed when enabled."""
    print("\n🧪 Testing tamagotchi message processing...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        
        try:
            # Set up environment
            os.environ["TAMAGOTCHI_ENABLED"] = "true"
            
            # Create bot manager
            bot = BotManager("testbot")
            
            # Mock the tamagotchi process_message method
            original_process = bot.tamagotchi.process_message
            call_count = 0
            
            def mock_process(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                return original_process(*args, **kwargs)
            
            bot.tamagotchi.process_message = mock_process
            
            # Create mock context
            context = {
                "server_name": "test",
                "sender": "testuser", 
                "text": "hello world",
                "target": "#test",
                "server": Mock()
            }
            
            print("📋 Test 1: Messages should be processed when tamagotchi is enabled")
            bot.tamagotchi_enabled = True
            bot._track_words(context)
            assert call_count == 1
            print("✅ Message processed when enabled")
            
            print("📋 Test 2: Messages should NOT be processed when tamagotchi is disabled")
            bot.tamagotchi_enabled = False
            bot._track_words(context)
            assert call_count == 1  # Should still be 1, not incremented
            print("✅ Message NOT processed when disabled")
            
            print("🎯 Tamagotchi processing test passed!")
            
        finally:
            os.chdir(original_cwd)
            if "TAMAGOTCHI_ENABLED" in os.environ:
                del os.environ["TAMAGOTCHI_ENABLED"]


if __name__ == "__main__":
    print("🔧 Testing tamagotchi toggle persistence fix...")
    print("=" * 60)
    
    try:
        test_tamagotchi_toggle_persistence()
        test_tamagotchi_processing()
        
        print("\n" + "=" * 60)
        print("🎉 ALL TESTS PASSED!")
        print("✅ Tamagotchi toggle now properly persists state")
        print("✅ Tamagotchi processing respects the enabled/disabled state")
        print("✅ State is saved to tamagotchi_enabled.json file")
        print("✅ Bot loads previous state on startup")
        print("✅ Fallback to environment variable works")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
