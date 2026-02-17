#!/usr/bin/env python3
"""
Leet IRC Python Bot - Multi-Server Edition

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
import time
from datetime import datetime

import logger
from bot_manager import BotManager
from config import load_env_file

# Suppress Voikko's buggy __del__ error messages during startup
# This is a known bug in libvoikko where it accesses a non-existent attribute during garbage collection
# Redirect stderr to a file that we can discard after startup
_stderr_file = open(os.devnull, "w")
sys.stderr = _stderr_file

# Create logger with MAIN context
main_logger = logger.get_logger("MAIN")

# Global file handle for logging
_log_file_handle = None


def setup_file_logging(log_file: str = "data/leet.log"):
    """
    Set up file logging to capture all logs from startup.

    This ensures logs from before the TUI is ready are still saved to file.
    Uses the custom file hook in the logger module.
    """
    global _log_file_handle

    # Ensure data directory exists
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    # Open the log file in append mode
    _log_file_handle = open(log_file, "a", encoding="utf-8")

    # Define the file hook function that writes to the file
    def file_hook(timestamp, level, message):
        """Write log message to file."""
        # message already includes level and context, so just write it directly
        _log_file_handle.write(f"{timestamp} {message}\n")
        _log_file_handle.flush()  # Ensure it's written immediately

    # Register the file hook with the logger
    logger.set_file_hook(file_hook)

    return _log_file_handle


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
  and configure your servers, API keys and bot settings.
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

    parser.add_argument(
        "-console",
        "--console",
        action="store_true",
        help="Use console interface instead of TUI (fallback mode)",
    )

    return parser.parse_args()


def setup_environment():
    """Load environment variables and validate configuration."""
    # Load .env file
    if not load_env_file():
        main_logger.warning(
            "Warning: Could not load .env file. Using defaults where possible."
        )

    # Validate essential configuration
    bot_name = os.getenv("BOT_NAME", "LeetIRCBot")

    # Check for at least one server configuration
    has_server_config = any(
        os.getenv(f"SERVER{i}_HOST")
        for i in range(1, 10)  # Check SERVER1 through SERVER9
    )

    if not has_server_config:
        main_logger.error("ERROR: No server configurations found!")
        main_logger.error("Please configure at least one server in your .env file:")
        main_logger.error("  SERVER1_HOST=irc.example.com")
        main_logger.error("  SERVER1_PORT=6667")
        main_logger.error("  SERVER1_CHANNELS=#channel1,#channel2")
        main_logger.error("  SERVER1_KEYS=")
        return None

    return bot_name


def main():
    """Main entry point for the multi-server IRC bot."""
    # Setup console encoding for Unicode support - broken
    # setup_console_encoding()

    # Set up file logging FIRST to capture all logs from startup
    setup_file_logging()

    # Parse command line arguments
    args = parse_arguments()

    # Determine interface mode
    use_console = args.console or os.getenv("FORCE_CONSOLE", "false").lower() == "true"

    # Store log level in environment for other modules
    if args:
        os.environ["LOG_LEVEL"] = args.loglevel
        if args.show_api_keys:
            main_logger.log("=== API KEYS ===", "INFO")
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
                main_logger.log(f"  {key}: {display_value}", "INFO")
            main_logger.log("=" * 60, "INFO")

    main_logger.log("=" * 60, "INFO")
    main_logger.log(
        "🤖 Leet IRC Python Bot - Multi-Server Edition",
        "INFO",
        fallback_text="[BOT] Leet IRC Python Bot - Multi-Server Edition",
    )
    main_logger.log("=" * 60, "INFO")

    # Setup environment and get bot name
    bot_name = setup_environment()
    if not bot_name:
        return 1

    # Override bot name from command line if provided
    if args.nickname:
        bot_name = args.nickname
        main_logger.log(f"Using nickname from command line: {bot_name}", "INFO")

    main_logger.log(f"Bot name: {bot_name}", "INFO")
    main_logger.log(f"Log level: {args.loglevel}", "INFO")
    main_logger.log(
        f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "INFO"
    )
    main_logger.log("-" * 60, "INFO")

    # Initialize TUI early for immediate visual feedback (before BotManager)
    tui_manager = None
    if not use_console:
        main_logger.log("Starting TUI interface...", "INFO")

        try:
            from tui import TUIManager

            # Show startup message and delay before TUI loads
            print("\n" + "=" * 60)
            print("  LeetIRCPythonBot v2.x - Starting up...")
            print("  Loading TUI in 5 seconds... (Press Ctrl+C to abort)")
            print("=" * 60 + "\n")
            time.sleep(5)

            # Create TUI manager early (will be updated with bot_manager after creation)
            tui_manager = TUIManager()
        except ImportError as e:
            main_logger.error(f"TUI not available: {e}")
            main_logger.log("Falling back to console interface...", "INFO")
            use_console = True  # Force console mode

            # Re-enable file logging if we fell back to console mode
            setup_file_logging()

    # Create the bot manager (this initializes console manager immediately)
    bot_manager = BotManager(bot_name, console_mode=use_console)

    # Set bot manager in TUI
    if tui_manager:
        tui_manager.set_bot_manager(bot_manager)

        # Clear file hook now that TUI has taken over file logging
        # This prevents duplicate entries in leet.log
        logger.clear_file_hook()
        if _log_file_handle:
            try:
                _log_file_handle.close()
            except Exception:
                pass

    try:
        # Decide whether to use TUI or console interface
        if use_console:
            main_logger.log("Using console interface (fallback mode)", "INFO")

            # Start the bot
            if not bot_manager.start():
                main_logger.error("ERROR: Failed to start bot manager")
                return 1

            main_logger.log(
                "🚀 Bot started successfully!",
                "INFO",
                fallback_text="[START] Bot started successfully!",
            )
            main_logger.log("Press Ctrl+C to shutdown gracefully", "INFO")
            main_logger.log("-" * 60, "INFO")

            # Wait for shutdown
            bot_manager.wait_for_shutdown()
        else:
            # Start the bot in the background
            if not bot_manager.start():
                main_logger.error("ERROR: Failed to start bot manager")
                return 1

            # Run the TUI (blocking)
            tui_manager.run()

    except KeyboardInterrupt:
        main_logger.log("" + "=" * 60, "INFO")
        main_logger.log(
            "🛑 Shutdown signal received",
            "INFO",
            fallback_text="[STOP] Shutdown signal received",
        )
        main_logger.log("=" * 60, "INFO")

    except Exception as e:
        main_logger.error(f"Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        return 1

    finally:
        # Ensure clean shutdown
        try:
            bot_manager.stop()
            main_logger.log(
                "✅ Bot shut down successfully",
                "INFO",
                fallback_text="[OK] Bot shut down successfully",
            )
        except Exception as e:
            main_logger.log(
                f"❌ Error during shutdown: {e}",
                "ERROR",
                fallback_text=f"[ERROR] Error during shutdown: {e}",
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
