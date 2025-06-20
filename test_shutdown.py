#!/usr/bin/env python3
"""
Quick test script to verify the shutdown fix.
Start this, then press Ctrl+C and see if it shuts down quickly.
"""

import time
from bot_manager import BotManager

def main():
    print("🧪 Testing shutdown behavior...")
    print("⚠️ This will start the bot briefly to test shutdown")
    print("📋 Instructions:")
    print("   1. Wait for the bot to connect")
    print("   2. Press Ctrl+C ONCE")
    print("   3. It should shut down within 2-3 seconds")
    print("   4. If it takes too long, press Ctrl+C again for forced shutdown")
    print()
    
    try:
        bot = BotManager("TestBot")
        
        if not bot.load_configurations():
            print("❌ No server configurations found!")
            print("💡 Make sure your .env file has SERVER1_HOST, SERVER1_PORT, etc.")
            return
            
        bot.register_callbacks()
        
        print("🚀 Starting bot... (Press Ctrl+C to test shutdown)")
        
        # Start the bot
        if bot.start():
            print("✅ Bot started successfully")
            # Wait for shutdown signal
            bot.wait_for_shutdown()
        else:
            print("❌ Bot failed to start")
            
    except KeyboardInterrupt:
        print("\n🛑 Shutdown signal received (this shouldn't appear due to signal handler)")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        print("👋 Test completed")

if __name__ == "__main__":
    main()
