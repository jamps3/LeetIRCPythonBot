#!/usr/bin/env python3
"""
Test script for YouTube and crypto services functionality.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def test_crypto_service():
    """Test cryptocurrency service."""
    print("🪙 Testing Crypto Service...")

    try:
        from services.crypto_service import create_crypto_service

        crypto_service = create_crypto_service()

        # Test Bitcoin price
        print("Testing Bitcoin price...")
        btc_data = crypto_service.get_crypto_price("bitcoin", "eur")
        message = crypto_service.format_price_message(btc_data)
        print(f"Result: {message}")

        # Test short alias
        print("\nTesting BTC alias...")
        btc_alias_data = crypto_service.get_crypto_price("btc", "usd")
        message = crypto_service.format_price_message(btc_alias_data)
        print(f"Result: {message}")

        # Test trending cryptos
        print("\nTesting trending cryptos...")
        trending_data = crypto_service.get_trending_cryptos()
        message = crypto_service.format_trending_message(trending_data)
        print(f"Result: {message}")

        print("✅ Crypto service test passed!")

    except Exception as e:
        print(f"❌ Crypto service test failed: {e}")
        import traceback

        traceback.print_exc()


def test_youtube_service():
    """Test YouTube service."""
    print("\n▶️ Testing YouTube Service...")

    youtube_api_key = os.getenv("YOUTUBE_API_KEY")
    if not youtube_api_key:
        print("⚠️ No YouTube API key found. Please set YOUTUBE_API_KEY in .env file.")
        return

    try:
        from services.youtube_service import create_youtube_service

        youtube_service = create_youtube_service(youtube_api_key)

        # Test video ID extraction
        print("Testing video ID extraction...")
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        video_id = youtube_service.extract_video_id(test_url)
        print(f"Extracted video ID: {video_id}")

        # Test video info retrieval
        if video_id:
            print(f"\nTesting video info for {video_id}...")
            video_data = youtube_service.get_video_info(video_id)
            if not video_data.get("error"):
                message = youtube_service.format_video_info_message(video_data)
                print(f"Result: {message}")
            else:
                print(f"Error: {video_data.get('message')}")

        # Test video search
        print("\nTesting video search...")
        search_data = youtube_service.search_videos("python programming", max_results=3)
        message = youtube_service.format_search_results_message(search_data)
        print(f"Result: {message}")

        print("✅ YouTube service test passed!")

    except Exception as e:
        print(f"❌ YouTube service test failed: {e}")
        import traceback

        traceback.print_exc()


def test_weather_service():
    """Test weather service."""
    print("\n🌤️ Testing Weather Service...")

    weather_api_key = os.getenv("WEATHER_API_KEY")
    if not weather_api_key:
        print("⚠️ No weather API key found. Please set WEATHER_API_KEY in .env file.")
        return

    try:
        from services.weather_service import WeatherService

        weather_service = WeatherService(weather_api_key)

        # Test weather for Joensuu
        print("Testing weather for Joensuu...")
        weather_data = weather_service.get_weather("Joensuu")
        message = weather_service.format_weather_message(weather_data)
        print(f"Result: {message}")

        print("✅ Weather service test passed!")

    except Exception as e:
        print(f"❌ Weather service test failed: {e}")
        import traceback

        traceback.print_exc()


def test_electricity_service():
    """Test electricity service."""
    print("\n⚡ Testing Electricity Service...")

    electricity_api_key = os.getenv("ELECTRICITY_API_KEY")
    if not electricity_api_key:
        print(
            "⚠️ No electricity API key found. Please set ELECTRICITY_API_KEY in .env file."
        )
        return

    try:
        from services.electricity_service import create_electricity_service

        electricity_service = create_electricity_service(electricity_api_key)

        # Test current hour price
        print("Testing current hour electricity price...")
        import datetime

        current_hour = datetime.datetime.now().hour
        price_data = electricity_service.get_electricity_price(hour=current_hour)
        message = electricity_service.format_price_message(price_data)
        print(f"Result: {message}")

        print("✅ Electricity service test passed!")

    except Exception as e:
        print(f"❌ Electricity service test failed: {e}")
        import traceback

        traceback.print_exc()


def main():
    """Run all service tests."""
    print("🔧 Testing bot services...\n")

    test_crypto_service()
    test_weather_service()
    test_electricity_service()
    test_youtube_service()

    print("\n🎉 All service tests completed!")


if __name__ == "__main__":
    main()
