#!/usr/bin/env python3
"""
LeetIRC Python Bot - Multi-Server Edition

A modern IRC bot with support for multiple servers, comprehensive word tracking,
AI integration, and extensive functionality.

Features:
- Multiple IRC server support with independent connections
- Advanced word and drink tracking with JSON storage
- AI-powered conversations using OpenAI
- Weather, electricity prices, and various utility commands
- Tamagotchi-style virtual pet functionality
- Privacy controls and opt-out mechanisms
- Graceful shutdown and error handling

Usage:
    python main.py [options]

Options:
    -l, --loglevel LEVEL    Set logging level (ERROR, INFO, DEBUG)
    -nick, --nickname NAME  Set bot nickname
    -api                    Show API keys in logs (debugging)

Environment Configuration:
    Copy .env.sample to .env and configure:
    - API keys for OpenAI, Weather, etc.
    - Server configurations (SERVER1_HOST, SERVER2_HOST, etc.)
    - Bot settings (BOT_NAME, LOG_LEVEL, etc.)
"""

import argparse
import os
import sys
from datetime import datetime

# Import existing components that are still needed
from dotenv import load_dotenv


# Configure console encoding for Windows Unicode support
def setup_console_encoding():
    """Setup console encoding to handle Unicode characters on Windows."""
    try:
        # Try to set UTF-8 encoding for stdout/stderr
        if sys.platform.startswith("win"):
            import codecs
            import io

            # Force UTF-8 encoding with error handling
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding="utf-8", errors="replace"
            )
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer, encoding="utf-8", errors="replace"
            )
    except Exception as e:
        # If setting encoding fails, we'll handle Unicode characters safely below
        pass


# Safe print function that handles Unicode gracefully
def safe_print(text, fallback_text=None):
    """Print text with Unicode fallback for Windows console compatibility."""
    try:
        print(text)
    except UnicodeEncodeError:
        # Fall back to ASCII-safe version
        if fallback_text:
            print(fallback_text)
        else:
            # Replace common Unicode characters with ASCII equivalents
            safe_text = (
                text.replace("🤖", "[BOT]")
                .replace("🚀", "[START]")
                .replace("🛑", "[STOP]")
                .replace("✅", "[OK]")
                .replace("❌", "[ERROR]")
                .replace("💥", "[ERROR]")
            )
            print(safe_text)


# Import our new multi-server architecture
from bot_manager import BotManager
from config import load_env_file


def setup_environment():
    """Load environment variables and validate configuration."""
    # Load .env file
    if not load_env_file():
        print("Warning: Could not load .env file. Using defaults where possible.")

    # Validate essential configuration
    bot_name = os.getenv("BOT_NAME", "LeetIRCBot")

    # Check for at least one server configuration
    has_server_config = any(
        os.getenv(f"SERVER{i}_HOST")
        for i in range(1, 10)  # Check SERVER1 through SERVER9
    )

    if not has_server_config:
        print("ERROR: No server configurations found!")
        print("Please configure at least one server in your .env file:")
        print("  SERVER1_HOST=irc.example.com")
        print("  SERVER1_PORT=6667")
        print("  SERVER1_CHANNELS=#channel1,#channel2")
        print("  SERVER1_KEYS=")
        return None

    return bot_name


def setup_logging(log_level: str, show_api_keys: bool = False):
    """Setup logging configuration."""
    # Store log level in environment for other modules
    os.environ["LOG_LEVEL"] = log_level

    if show_api_keys:
        print("=== API KEYS ===")
        api_keys = [
            "OPENAI_API_KEY",
            "WEATHER_API_KEY",
            "ELECTRICITY_API_KEY",
            "YOUTUBE_API_KEY",
        ]

        for key in api_keys:
            value = os.getenv(key, "Not set")
            # Show first and last 5 characters for security
            if value and value != "Not set" and len(value) > 10:
                display_value = f"{value[:5]}...{value[-5:]}"
            else:
                display_value = value
            print(f"  {key}: {display_value}")
        print("================")


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="LeetIRC Python Bot - Multi-Server Edition",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                     # Start with default settings
  python main.py -l DEBUG           # Start with debug logging
  python main.py -nick MyBot        # Start with custom nickname
  python main.py -api               # Show API keys (for debugging)

Configuration:
  The bot reads configuration from a .env file. Copy .env.sample to .env
  and configure your servers, API keys, and bot settings.
        """,
    )

    parser.add_argument(
        "-l",
        "--loglevel",
        choices=["ERROR", "INFO", "DEBUG"],
        default="INFO",
        help="Set the logging level (default: INFO)",
    )

    parser.add_argument(
        "-nick",
        "--nickname",
        type=str,
        help="Set bot nickname (overrides .env BOT_NAME)",
    )

    parser.add_argument(
        "-api",
        "--show-api-keys",
        action="store_true",
        help="Show API key values in logs (for debugging)",
    )

    return parser.parse_args()


def main():
    """Main entry point for the multi-server IRC bot."""
    # Setup console encoding for Unicode support
    setup_console_encoding()

    print("=" * 60)
    safe_print(
        "🤖 LeetIRC Python Bot - Multi-Server Edition",
        "[BOT] LeetIRC Python Bot - Multi-Server Edition",
    )
    print("=" * 60)

    # Parse command line arguments
    args = parse_arguments()

    # Setup environment and get bot name
    bot_name = setup_environment()
    if not bot_name:
        return 1

    # Override bot name from command line if provided
    if args.nickname:
        bot_name = args.nickname
        print(f"Using nickname from command line: {bot_name}")

    # Setup logging
    setup_logging(args.loglevel, args.show_api_keys)

    print(f"Bot name: {bot_name}")
    print(f"Log level: {args.loglevel}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 60)

    # Create and start the bot manager
    bot_manager = BotManager(bot_name)

    try:
        # Start the bot
        if not bot_manager.start():
            print("ERROR: Failed to start bot manager")
            return 1

        safe_print("🚀 Bot started successfully!", "[START] Bot started successfully!")
        print("Press Ctrl+C to shutdown gracefully")
        print("-" * 60)

        # Wait for shutdown
        bot_manager.wait_for_shutdown()

    except KeyboardInterrupt:
        print("\n" + "=" * 60)
        safe_print("🛑 Shutdown signal received", "[STOP] Shutdown signal received")
        print("=" * 60)

    except Exception as e:
        safe_print(f"\n💥 Unexpected error: {e}", f"\n[ERROR] Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        return 1

    finally:
        # Ensure clean shutdown
        try:
            bot_manager.stop()
            safe_print(
                "✅ Bot shut down successfully", "[OK] Bot shut down successfully"
            )
        except Exception as e:
            safe_print(
                f"❌ Error during shutdown: {e}", f"[ERROR] Error during shutdown: {e}"
            )
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
