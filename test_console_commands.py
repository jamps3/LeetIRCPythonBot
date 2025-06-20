#!/usr/bin/env python3
"""
Test console commands for bot functionality.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def test_console_command():
    """Test console command processing with bot services."""
    print("🎮 Testing Console Commands...\n")

    try:
        # Create a mock bot_functions dictionary with working services
        from services.crypto_service import create_crypto_service
        from services.weather_service import WeatherService
        from services.electricity_service import create_electricity_service
        from services.youtube_service import create_youtube_service

        # Initialize services
        crypto_service = create_crypto_service()
        print("🪙 Crypto service initialized")

        weather_api_key = os.getenv("WEATHER_API_KEY")
        weather_service = WeatherService(weather_api_key) if weather_api_key else None
        if weather_service:
            print("🌤️ Weather service initialized")

        electricity_api_key = os.getenv("ELECTRICITY_API_KEY")
        electricity_service = (
            create_electricity_service(electricity_api_key)
            if electricity_api_key
            else None
        )
        if electricity_service:
            print("⚡ Electricity service initialized")

        youtube_api_key = os.getenv("YOUTUBE_API_KEY")
        youtube_service = (
            create_youtube_service(youtube_api_key) if youtube_api_key else None
        )
        if youtube_service:
            print("▶️ YouTube service initialized")

        # Create a console message output function
        def console_notice_message(msg, irc=None, target=None):
            print(f"RESPONSE: {msg}")

        # Mock bot functions with working services
        def mock_send_weather(irc, channel, location):
            if weather_service:
                try:
                    weather_data = weather_service.get_weather(location)
                    response = weather_service.format_weather_message(weather_data)
                    console_notice_message(response)
                except Exception as e:
                    console_notice_message(f"Weather error: {e}")
            else:
                console_notice_message("Weather service not available")

        def mock_send_crypto_price(irc, channel, parts):
            try:
                if isinstance(parts, list) and len(parts) > 1:
                    coin = parts[1]
                    currency = parts[2] if len(parts) > 2 else "eur"
                else:
                    console_notice_message("Usage: !crypto <coin> [currency]")
                    return

                price_data = crypto_service.get_crypto_price(coin, currency)
                response = crypto_service.format_price_message(price_data)
                console_notice_message(response)
            except Exception as e:
                console_notice_message(f"Crypto error: {e}")

        def mock_send_youtube_info(irc, channel, query):
            if youtube_service:
                try:
                    video_id = youtube_service.extract_video_id(query)
                    if video_id:
                        # It's a URL, get video info
                        video_data = youtube_service.get_video_info(video_id)
                        response = youtube_service.format_video_info_message(video_data)
                    else:
                        # It's a search query
                        search_data = youtube_service.search_videos(
                            query, max_results=3
                        )
                        response = youtube_service.format_search_results_message(
                            search_data
                        )
                    console_notice_message(response)
                except Exception as e:
                    console_notice_message(f"YouTube error: {e}")
            else:
                console_notice_message("YouTube service not available")

        def mock_send_electricity_price(irc, channel, parts):
            if electricity_service:
                try:
                    import datetime

                    current_hour = datetime.datetime.now().hour
                    price_data = electricity_service.get_electricity_price(
                        hour=current_hour
                    )
                    response = electricity_service.format_price_message(price_data)
                    console_notice_message(response)
                except Exception as e:
                    console_notice_message(f"Electricity error: {e}")
            else:
                console_notice_message("Electricity service not available")

        # Create bot_functions dictionary
        bot_functions = {
            "notice_message": console_notice_message,
            "send_weather": mock_send_weather,
            "send_crypto_price": mock_send_crypto_price,
            "send_youtube_info": mock_send_youtube_info,
            "send_electricity_price": mock_send_electricity_price,
            "get_crypto_price": lambda coin, currency="eur": (
                crypto_service.get_crypto_price(coin, currency)["price"]
                if not crypto_service.get_crypto_price(coin, currency).get("error")
                else "N/A"
            ),
            "load_leet_winners": lambda: {},
            "send_scheduled_message": lambda *args: None,
            "load": lambda: {},
            "log": lambda msg, level="INFO": print(f"[{level}] {msg}"),
            "fetch_title": lambda *args: None,
            "handle_ipfs_command": lambda *args: None,
            "chat_with_gpt": lambda msg: f"Mock AI response to: {msg}",
            "wrap_irc_message_utf8_bytes": lambda msg, **kwargs: [msg],
        }

        # Import the console command processor
        import commands

        print("\n🧪 Testing commands:\n")

        # Test weather command
        print("1. Testing !s command (weather):")
        commands.process_console_command("!s Joensuu", bot_functions)

        # Test crypto command
        print("\n2. Testing !crypto command:")
        commands.process_console_command("!crypto btc eur", bot_functions)

        # Test electricity command
        print("\n3. Testing !sahko command:")
        commands.process_console_command("!sahko", bot_functions)

        # Test help command
        print("\n4. Testing !help command:")
        commands.process_console_command("!help", bot_functions)

        # Test version command
        print("\n5. Testing !version command:")
        commands.process_console_command("!version", bot_functions)

        print("\n✅ Console command tests completed!")

    except Exception as e:
        print(f"❌ Console command test failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_console_command()
