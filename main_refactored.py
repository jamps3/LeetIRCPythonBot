#!/usr/bin/env python3
"""
Refactored IRC Bot Main Application

This is the new main application using the refactored IRC client system
and modular command registry. It maintains compatibility with existing
functionality while providing a cleaner architecture.
"""

import argparse
import signal
import sys
import threading
import time
from typing import Any, Dict

from command_loader import load_all_commands
from config import get_config, get_config_manager
# Import refactored components
from irc_client import IRCClient, create_irc_client
from irc_processor import create_message_processor
# Import legacy functions for compatibility
from main import (  # Core functions; Bot functions; Advanced functions; Configuration; Services
    BOT_VERSION, DRINK_WORDS, EKAVIKA_FILE, chat_with_gpt, count_kraks,
    fetch_title, format_counts, get_crypto_price, get_eurojackpot_numbers,
    handle_ipfs_command, lemmat, load, load_leet_winners, lookup,
    measure_latency, save, save_leet_winners, search_youtube,
    send_electricity_price, send_scheduled_message, send_weather,
    split_message_intelligently, subscriptions, update_kraks,
    wrap_irc_message_utf8_bytes)


class RefactoredBot:
    """
    Refactored IRC bot with clean architecture.
    """

    def __init__(
        self,
        server_name: str = "SERVER1",
        nickname: str = None,
        log_level: str = "INFO",
    ):
        """
        Initialize the bot.

        Args:
            server_name: Server configuration name
            nickname: Bot nickname (uses config default if None)
            log_level: Logging level
        """
        self.config = get_config()
        self.log_level = log_level

        # Use configured nickname if none provided
        if not nickname:
            nickname = self.config.name

        # Create IRC client
        self.irc_client = create_irc_client(server_name, nickname, self._log)

        # Create stop event for graceful shutdown
        self.stop_event = threading.Event()

        # Console input thread
        self.console_thread: threading.Thread = None

        # Bot functions for compatibility
        self.bot_functions = self._create_bot_functions()

        # Create message processor
        self.message_processor = create_message_processor(
            self.irc_client, self.bot_functions
        )

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _log(self, message: str, level: str = "INFO"):
        """Enhanced logging with timestamp."""
        import datetime

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Simple level filtering
        levels = ["ERROR", "WARNING", "INFO", "DEBUG"]
        if level in levels and levels.index(level) <= levels.index(self.log_level):
            print(f"[{timestamp}] [{level:^7}] {message}")

    def _signal_handler(self, sig, frame):
        """Handle shutdown signals."""
        self._log("Shutdown signal received", "INFO")
        self.stop_event.set()

    def _create_bot_functions(self) -> Dict[str, Any]:
        """Create bot functions dictionary for compatibility."""
        return {
            # Core data functions
            "load": load,
            "save": save,
            "update_kraks": update_kraks,
            "load_leet_winners": load_leet_winners,
            "save_leet_winners": save_leet_winners,
            # Communication functions
            "notice_message": self._notice_message,
            "send_message": self._send_message,
            "log": self._log,
            # Bot features
            "send_weather": send_weather,
            "send_electricity_price": send_electricity_price,
            "fetch_title": fetch_title,
            "handle_ipfs_command": handle_ipfs_command,
            "chat_with_gpt": chat_with_gpt,
            "wrap_irc_message_utf8_bytes": wrap_irc_message_utf8_bytes,
            "split_message_intelligently": split_message_intelligently,
            "get_crypto_price": get_crypto_price,
            "measure_latency": measure_latency,
            "count_kraks": count_kraks,
            # Advanced features
            "search_youtube": search_youtube,
            "get_eurojackpot_numbers": get_eurojackpot_numbers,
            "send_scheduled_message": send_scheduled_message,
            "format_counts": format_counts,
            "lookup": lookup,
            # Services
            "lemmat": lemmat,
            "subscriptions": subscriptions,
            # Configuration and constants
            "DRINK_WORDS": DRINK_WORDS,
            "EKAVIKA_FILE": EKAVIKA_FILE,
            "BOT_VERSION": BOT_VERSION,
            "bot_name": self.config.name,
            "server_name": self.irc_client.server_config.name,
            # New IRC client access
            "irc_client": self.irc_client,
        }

    def _notice_message(self, message: str, irc_socket=None, target: str = None):
        """Send notice message (compatibility wrapper)."""
        if target:
            self.irc_client.send_notice(target, message)
        else:
            # Console output
            self._log(f"NOTICE: {message}", "MSG")

    def _send_message(self, irc_socket, target: str, message: str):
        """Send regular message (compatibility wrapper)."""
        self.irc_client.send_message(target, message)

    def _listen_for_console_commands(self):
        """Listen for console commands in a separate thread."""
        try:
            while not self.stop_event.is_set():
                try:
                    user_input = input("")
                    if not user_input:
                        continue

                    if user_input.lower() in ("quit", "exit"):
                        self._log("Console quit command received", "INFO")
                        self.stop_event.set()
                        break

                    if user_input.startswith("!"):
                        # Process console commands
                        try:
                            from command_loader import \
                                enhanced_process_console_command

                            enhanced_process_console_command(
                                user_input, self.bot_functions
                            )
                        except Exception as e:
                            self._log(f"Console command error: {e}", "ERROR")
                    else:
                        # Send to AI chat
                        try:
                            response = chat_with_gpt(user_input)
                            if response:
                                parts = wrap_irc_message_utf8_bytes(
                                    response,
                                    reply_target="",
                                    max_lines=5,
                                    placeholder="...",
                                )
                                for part in parts:
                                    self._log(f"AI: {part}", "MSG")
                        except Exception as e:
                            self._log(f"AI chat error: {e}", "ERROR")

                except (EOFError, KeyboardInterrupt):
                    self.stop_event.set()
                    break
        except Exception as e:
            self._log(f"Console listener error: {e}", "ERROR")

    def connect(self) -> bool:
        """Connect to IRC server."""
        self._log(f"Connecting to {self.irc_client.server_config.host}...", "INFO")

        if self.irc_client.connect():
            self._log("Connected successfully!", "INFO")
            return True
        else:
            self._log("Connection failed", "ERROR")
            return False

    def run(self):
        """Run the bot main loop."""
        self._log("Starting LeetIRC Bot (Refactored)", "INFO")
        self._log(f"Bot version: {BOT_VERSION}", "INFO")

        # Load all commands
        load_all_commands()

        try:
            while not self.stop_event.is_set():
                # Connect to IRC
                if not self.connect():
                    self._log("Retrying connection in 30 seconds...", "INFO")
                    for _ in range(30):
                        if self.stop_event.is_set():
                            break
                        time.sleep(1)
                    continue

                # Start console listener
                if not self.console_thread or not self.console_thread.is_alive():
                    self.console_thread = threading.Thread(
                        target=self._listen_for_console_commands,
                        daemon=True,
                        name="Console-Listener",
                    )
                    self.console_thread.start()

                # Start IRC message processing
                try:
                    while not self.stop_event.is_set() and self.irc_client.is_connected:
                        try:
                            # Process messages
                            messages = self.irc_client.read_messages()

                            # Small delay to prevent busy waiting
                            time.sleep(0.1)

                        except Exception as e:
                            self._log(f"Message processing error: {e}", "ERROR")
                            break

                except KeyboardInterrupt:
                    self._log("Interrupted by user", "INFO")
                    break

                # If we get here, connection was lost
                if not self.stop_event.is_set():
                    self._log(
                        "Connection lost, reconnecting in 30 seconds...", "WARNING"
                    )
                    for _ in range(30):
                        if self.stop_event.is_set():
                            break
                        time.sleep(1)

        except Exception as e:
            self._log(f"Fatal error: {e}", "ERROR")
            import traceback

            self._log(traceback.format_exc(), "DEBUG")

        finally:
            self.shutdown()

    def shutdown(self):
        """Perform graceful shutdown."""
        self._log("Shutting down bot...", "INFO")

        # Stop all threads
        self.stop_event.set()

        # Disconnect IRC
        if self.irc_client.is_connected:
            self.irc_client.disconnect(self.config.quit_message)

        # Wait for console thread
        if self.console_thread and self.console_thread.is_alive():
            self.console_thread.join(timeout=2)

        # Save data
        try:
            kraks = load()
            save(kraks)
            self._log("Data saved successfully", "INFO")
        except Exception as e:
            self._log(f"Error saving data: {e}", "ERROR")

        self._log("Bot shutdown complete", "INFO")


def main():
    """Main entry point."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="LeetIRC Bot (Refactored)")
    parser.add_argument(
        "-l",
        "--loglevel",
        choices=["ERROR", "WARNING", "INFO", "DEBUG"],
        default="INFO",
        help="Set logging level (default: INFO)",
    )
    parser.add_argument(
        "-s",
        "--server",
        default="SERVER1",
        help="Server configuration name (default: SERVER1)",
    )
    parser.add_argument(
        "-n", "--nick", help="Bot nickname (uses config default if not specified)"
    )
    parser.add_argument(
        "--test-config", action="store_true", help="Test configuration and exit"
    )

    args = parser.parse_args()

    # Test configuration if requested
    if args.test_config:
        try:
            config_manager = get_config_manager()
            config = config_manager.config

            print("🔧 Configuration Test")
            print(f"✓ Bot name: {config.name}")
            print(f"✓ Version: {config.version}")
            print(f"✓ Servers configured: {len(config.servers)}")

            for server in config.servers:
                print(f"  - {server.name}: {server.host}:{server.port}")
                print(f"    Channels: {', '.join(server.channels)}")

            # Validate configuration
            errors = config_manager.validate_config()
            if errors:
                print("\n⚠️ Configuration Issues:")
                for error in errors:
                    print(f"  - {error}")
            else:
                print("\n✅ Configuration is valid")

            return 0

        except Exception as e:
            print(f"❌ Configuration test failed: {e}")
            return 1

    # Create and run bot
    try:
        bot = RefactoredBot(
            server_name=args.server, nickname=args.nick, log_level=args.loglevel
        )
        bot.run()
        return 0

    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")
        return 0
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
