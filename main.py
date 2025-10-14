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
    -l, --loglevel LEVEL    Set logging level (ERROR, INFO, DEBUG), specified in .env (default: INFO)
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

import logger
from bot_manager import BotManager
from config import load_env_file


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Leet IRC Python Bot - Multi-Server Edition",
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
        choices=["ERROR", "INFO", "DEBUG"],  # TODO: Add all levels
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


def setup_environment():
    """Load environment variables and validate configuration."""
    # Load .env file
    if not load_env_file():
        logger.warning(
            "Warning: Could not load .env file. Using defaults where possible."
        ), "MAIN"

    # Validate essential configuration
    bot_name = os.getenv("BOT_NAME", "LeetIRCBot")

    # Check for at least one server configuration
    has_server_config = any(
        os.getenv(f"SERVER{i}_HOST")
        for i in range(1, 10)  # Check SERVER1 through SERVER9
    )

    if not has_server_config:
        logger.error("ERROR: No server configurations found!"), "MAIN"
        logger.error("Please configure at least one server in your .env file:"), "MAIN"
        logger.error("  SERVER1_HOST=irc.example.com"), "MAIN"
        logger.error("  SERVER1_PORT=6667"), "MAIN"
        logger.error("  SERVER1_CHANNELS=#channel1,#channel2"), "MAIN"
        logger.error("  SERVER1_KEYS="), "MAIN"
        return None

    return bot_name


def main():
    """Main entry point for the multi-server IRC bot."""
    # Setup console encoding for Unicode support - broken
    # setup_console_encoding()

    # Parse command line arguments
    args = parse_arguments()

    # Store log level in environment for other modules
    if args:
        os.environ["LOG_LEVEL"] = args.loglevel
        if args.show_api_keys:
            logger.log("=== API KEYS ==="), "INFO", "MAIN"
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
                logger.log(f"  {key}: {display_value}"), "INFO", "MAIN"
            logger.log("=" * 60), "INFO", "MAIN"

    logger.log("=" * 60), "INFO", "MAIN"
    logger.log(
        "🤖 LeetIRC Python Bot - Multi-Server Edition",
        "INFO",
        "MAIN" "[BOT] LeetIRC Python Bot - Multi-Server Edition",
    )
    logger.log("=" * 60), "INFO", "MAIN"

    # Setup environment and get bot name
    bot_name = setup_environment()
    if not bot_name:
        return 1

    # Override bot name from command line if provided
    if args.nickname:
        bot_name = args.nickname
        logger.log(f"Using nickname from command line: {bot_name}"), "INFO", "MAIN"

    logger.log(f"Bot name: {bot_name}"), "INFO", "MAIN"
    logger.log(f"Log level: {args.loglevel}"), "INFO", "MAIN"
    logger.log(
        f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    ), "INFO", "MAIN"
    logger.log("-" * 60), "INFO", "MAIN"

    # Create and start the bot manager
    bot_manager = BotManager(bot_name)

    try:
        # Start the bot
        if not bot_manager.start():
            logger.error("ERROR: Failed to start bot manager")
            return 1

        logger.log(
            "🚀 Bot started successfully!",
            "INFO",
            "MAIN",
            "[START] Bot started successfully!",
        )
        logger.log("Press Ctrl+C to shutdown gracefully"), "INFO", "MAIN"
        logger.log("-" * 60), "INFO", "MAIN"

        # Wait for shutdown
        bot_manager.wait_for_shutdown()

    except KeyboardInterrupt:
        logger.log("" + "=" * 60), "INFO", "MAIN"
        logger.log(
            "🛑 Shutdown signal received",
            "INFO",
            "MAIN",
            "[STOP] Shutdown signal received",
        )
        logger.log("=" * 60), "INFO", "MAIN"

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        return 1

    finally:
        # Ensure clean shutdown
        try:
            bot_manager.stop()
            logger.log(
                "✅ Bot shut down successfully",
                "INFO",
                "MAIN",
                "[OK] Bot shut down successfully",
            )
        except Exception as e:
            logger.log(
                f"❌ Error during shutdown: {e}",
                "ERROR",
                "MAIN",
                f"[ERROR] Error during shutdown: {e}",
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
