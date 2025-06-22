#!/usr/bin/env python3
"""
Direct test of console command processing to debug the issue.
"""

import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

def test_direct_console():
    """Test console commands directly."""
    print("🧪 Testing Direct Console Command Processing...")
    
    try:
        # Import the enhanced function
        from command_loader import enhanced_process_console_command
        
        # Create minimal bot_functions for testing
        def mock_notice(msg, irc=None, target=None):
            print(f"OUTPUT: {msg}")
        
        def mock_log(msg, level="INFO"):
            print(f"[{level}] {msg}")
        
        bot_functions = {
            "notice_message": mock_notice,
            "log": mock_log,
            "send_weather": lambda *args: mock_notice("Weather service called"),
            "send_electricity_price": lambda *args: mock_notice("Electricity service called"),
            "load_leet_winners": lambda: {},
            "send_scheduled_message": lambda *args: None,
            "load": lambda: {},
            "fetch_title": lambda *args: None,
            "handle_ipfs_command": lambda *args: None,
            "chat_with_gpt": lambda msg: f"AI: {msg}",
            "wrap_irc_message_utf8_bytes": lambda msg, **kwargs: [msg],
            "get_crypto_price": lambda coin, currency="eur": "1000",
        }
        
        print("\n1. Testing !help command:")
        enhanced_process_console_command("!help", bot_functions)
        
        print("\n2. Testing !version command:")
        enhanced_process_console_command("!version", bot_functions)
        
        print("\n3. Testing !s command:")
        enhanced_process_console_command("!s Helsinki", bot_functions)
        
        print("\n✅ Direct console test completed!")
        
    except Exception as e:
        print(f"❌ Direct console test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_direct_console()
