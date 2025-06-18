#!/usr/bin/env python3
"""
Test script for GPT service history limit functionality.
"""

import os
import sys
import tempfile
import json

# Add current directory to path to import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.gpt_service import GPTService


def test_history_limit():
    """Test that conversation history is limited correctly."""
    
    # Create a temporary file for testing
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as temp_file:
        temp_file_path = temp_file.name
    
    try:
        # Test with a small history limit for easy testing
        test_limit = 4  # 4 messages (2 user + 2 assistant)
        
        # Use a fake API key for testing (won't actually call OpenAI)
        service = GPTService("fake-key-for-testing", temp_file_path, test_limit)
        
        # Manually add messages to test history limiting
        # Start with system prompt (this doesn't count toward limit)
        service.conversation_history = [
            {"role": "system", "content": "You are a helpful assistant."}
        ]
        
        # Add messages beyond the limit
        for i in range(6):  # Add 6 messages (should exceed limit of 4)
            service.conversation_history.append({
                "role": "user", 
                "content": f"Test message {i + 1}"
            })
            service.conversation_history.append({
                "role": "assistant", 
                "content": f"Response {i + 1}"
            })
        
        # This should trigger history limiting when we save
        service._save_conversation_history()
        
        # Check that history was limited correctly
        # Should have: 1 system prompt + 4 messages (last 2 user + 2 assistant)
        expected_total = 5  # 1 system + 4 messages
        actual_total = len(service.conversation_history)
        
        print(f"History limit: {test_limit}")
        print(f"Expected total messages: {expected_total}")
        print(f"Actual total messages: {actual_total}")
        
        if actual_total == expected_total:
            print("✅ History limiting works correctly!")
            
            # Verify the system message is still first
            if service.conversation_history[0]["role"] == "system":
                print("✅ System prompt preserved!")
            else:
                print("❌ System prompt not preserved!")
                return False
                
            # Verify we have the most recent messages
            last_user_msg = None
            last_assistant_msg = None
            for msg in reversed(service.conversation_history):
                if msg["role"] == "user" and last_user_msg is None:
                    last_user_msg = msg["content"]
                elif msg["role"] == "assistant" and last_assistant_msg is None:
                    last_assistant_msg = msg["content"]
            
            if "Test message 6" in last_user_msg and "Response 6" in last_assistant_msg:
                print("✅ Most recent messages preserved!")
                return True
            else:
                print("❌ Most recent messages not preserved!")
                print(f"Last user message: {last_user_msg}")
                print(f"Last assistant message: {last_assistant_msg}")
                return False
        else:
            print("❌ History limiting failed!")
            print("Conversation history:")
            for i, msg in enumerate(service.conversation_history):
                print(f"  {i}: {msg['role']} - {msg['content']}")
            return False
            
    finally:
        # Clean up temp file
        try:
            os.unlink(temp_file_path)
        except:
            pass


def test_config_loading():
    """Test that the configuration is loaded correctly from environment."""
    
    # Test default value
    service = GPTService("fake-key", "test.json")
    if service.history_limit == 100:
        print("✅ Default history limit (100) works correctly!")
    else:
        print(f"❌ Default history limit incorrect: {service.history_limit}")
        return False
    
    # Test custom value
    service_custom = GPTService("fake-key", "test.json", 50)
    if service_custom.history_limit == 50:
        print("✅ Custom history limit works correctly!")
    else:
        print(f"❌ Custom history limit incorrect: {service_custom.history_limit}")
        return False
    
    return True


def main():
    """Run all tests."""
    print("Testing GPT Service History Limit Functionality")
    print("=" * 50)
    
    # Test configuration loading
    print("\n1. Testing configuration loading...")
    config_test = test_config_loading()
    
    # Test history limiting
    print("\n2. Testing history limiting...")
    history_test = test_history_limit()
    
    # Summary
    print("\n" + "=" * 50)
    if config_test and history_test:
        print("🎉 All tests passed!")
        return True
    else:
        print("❌ Some tests failed!")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

