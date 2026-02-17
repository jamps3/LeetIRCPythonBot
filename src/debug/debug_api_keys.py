#!/usr/bin/env python3
"""
Test script to verify that the API key fix works correctly.
This script tests the get_api_key function to ensure it properly loads
API keys from the .env file.
"""

import os
import sys

# Add src directory to path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


def test_api_key_loading():
    """Test that API keys are loaded correctly from .env file."""
    print("Testing API key loading...")

    try:
        from config import get_api_key

        # Test YouTube API key
        youtube_key = get_api_key("YOUTUBE_API_KEY")
        print(
            f"YOUTUBE_API_KEY: {'Found' if youtube_key else 'Not found'} (length: {len(youtube_key) if youtube_key else 0})"
        )

        # Test other API keys
        weather_key = get_api_key("WEATHER_API_KEY")
        print(
            f"WEATHER_API_KEY: {'Found' if weather_key else 'Not found'} (length: {len(weather_key) if weather_key else 0})"
        )

        electricity_key = get_api_key("ELECTRICITY_API_KEY")
        print(
            f"ELECTRICITY_API_KEY: {'Found' if electricity_key else 'Not found'} (length: {len(electricity_key) if electricity_key else 0})"
        )

        openai_key = get_api_key("OPENAI_API_KEY")
        print(
            f"OPENAI_API_KEY: {'Found' if openai_key else 'Not found'} (length: {len(openai_key) if openai_key else 0})"
        )

        # Test that the YouTube service can be initialized
        print("\nTesting YouTube service initialization...")
        try:
            from services.youtube_service import create_youtube_service

            if youtube_key:
                youtube_service = create_youtube_service(youtube_key)
                print("✅ YouTube service initialized successfully!")

                # Test extracting a video ID
                test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
                video_id = youtube_service.extract_video_id(test_url)
                print(f"✅ Video ID extraction test: {video_id}")

            else:
                print("❌ Cannot test YouTube service - API key not found")
        except Exception as e:
            print(f"❌ Error testing YouTube service: {e}")

        # Summary
        print("\n" + "=" * 50)
        print("SUMMARY:")
        print(f"✅ YouTube API key: {'Loaded' if youtube_key else 'Missing'}")
        print(f"✅ Weather API key: {'Loaded' if weather_key else 'Missing'}")
        print(f"✅ Electricity API key: {'Loaded' if electricity_key else 'Missing'}")
        print(f"✅ OpenAI API key: {'Loaded' if openai_key else 'Missing'}")

        if youtube_key:
            print(
                "\n🎉 The YouTube command should now work! Try: !youtube python tutorial"
            )
        else:
            print("\n⚠️  YouTube API key still not found. Check your .env file.")

    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_api_key_loading()
