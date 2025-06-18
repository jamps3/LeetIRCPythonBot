#!/usr/bin/env python3
"""
Test script to verify bot manager loads GPT history limit from .env correctly.
"""

import os
import sys

# Add current directory to path to import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import load_env_file


def test_env_loading():
    """Test that GPT_HISTORY_LIMIT is loaded from .env file."""
    
    print("Testing environment variable loading...")
    
    # Load .env file
    if load_env_file():
        print("✅ .env file loaded successfully!")
    else:
        print("❌ Failed to load .env file!")
        return False
    
    # Check if GPT_HISTORY_LIMIT is set
    gpt_history_limit = os.getenv('GPT_HISTORY_LIMIT')
    
    if gpt_history_limit:
        print(f"✅ GPT_HISTORY_LIMIT found: {gpt_history_limit}")
        
        # Try to convert to int
        try:
            limit_int = int(gpt_history_limit)
            print(f"✅ GPT_HISTORY_LIMIT is valid integer: {limit_int}")
            return True
        except ValueError:
            print(f"❌ GPT_HISTORY_LIMIT is not a valid integer: {gpt_history_limit}")
            return False
    else:
        print("❌ GPT_HISTORY_LIMIT not found in environment")
        return False


def main():
    """Run the test."""
    print("Testing Bot Manager GPT Configuration")
    print("=" * 40)
    
    success = test_env_loading()
    
    print("\n" + "=" * 40)
    if success:
        print("🎉 Environment configuration test passed!")
    else:
        print("❌ Environment configuration test failed!")
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

