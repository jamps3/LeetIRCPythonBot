"""
Bot Manager for Multiple IRC Servers

This module provides the BotManager class that orchestrates multiple IRC server
connections and integrates all bot functionality across servers.
"""

import os
import threading
import time
from typing import Any, Dict, List, Optional

from config import get_api_key, get_server_configs, load_env_file
from leet_detector import create_nanoleet_detector
from lemmatizer import Lemmatizer
from logger import get_logger, safe_print
from server import Server
from word_tracking import DataManager, DrinkTracker, GeneralWords, TamagotchiBot

# Try to import readline, but handle gracefully if not available (Windows)
try:
    import readline

    READLINE_AVAILABLE = True
except ImportError:
    READLINE_AVAILABLE = False

    # Create a dummy readline module for compatibility
    class DummyReadline:
        def set_history_length(self, length):
            pass

        def read_history_file(self, filename):
            raise FileNotFoundError()

        def write_history_file(self, filename):
            pass

        def parse_and_bind(self, string):
            pass

        def redisplay(self):
            pass

    readline = DummyReadline()


class BotManager:
    """
    Manages multiple IRC server connections and coordinates bot functionality.

    This class:
    1. Loads server configurations from environment variables
    2. Creates and manages Server instances for each configured server
    3. Registers callbacks for bot functionality
    4. Coordinates cross-server features
    5. Handles graceful shutdown
    """

    def __init__(self, bot_name: str):
        """
        Initialize the bot manager.

        Args:
            bot_name: The nickname for the bot across all servers
        """
        print("Starting BotManager initialization...")
        self.bot_name = bot_name
        self.servers: Dict[str, Server] = {}
        self.server_threads: Dict[str, threading.Thread] = {}
        self.stop_event = threading.Event()
        # Read default quit message from environment or use fallback
        self.quit_message = os.getenv("QUIT_MESSAGE", "Disconnecting")

        # Initialize high-precision logger first
        print("Initializing logger...")
        self.logger = get_logger("BotManager")
        self.logger.debug("Logger initialized.")

        # Configure readline for command history and console output protection
        self.logger.debug("Setting up readline history...")
        try:
            self._setup_readline_history()
            self.logger.debug("Readline history setup complete.")
        except Exception as e:
            self.logger.debug(f"Readline history setup failed: {e}")

        self.logger.debug("Setting up console output protection...")
        try:
            self._setup_console_output_protection()
            self.logger.debug("Console output protection setup complete.")
        except Exception as e:
            self.logger.debug(f"Console output protection setup failed: {e}")

        self.logger.debug("Readline and console setup complete.")

        # Optional service imports - handle gracefully if dependencies are missing
        try:
            from services.crypto_service import create_crypto_service
        except ImportError as e:
            self.logger.warning(f"Warning: Crypto service not available: {e}")
            create_crypto_service = None

        try:
            from services.electricity_service import create_electricity_service
        except ImportError as e:
            self.logger.warning(f"Electricity service not available: {e}")
            create_electricity_service = None

        try:
            from services.fmi_warning_service import create_fmi_warning_service
        except ImportError as e:
            self.logger.warning(f"FMI warning service not available: {e}")
            create_fmi_warning_service = None

        try:
            from services.gpt_service import GPTService
        except ImportError as e:
            self.logger.warning(f"GPT service not available: {e}")
            GPTService = None

        try:
            from services.otiedote_service import create_otiedote_service
        except ImportError as e:
            self.logger.warning(f"Otiedote service not available: {e}")
            create_otiedote_service = None

        try:
            from services.weather_service import WeatherService
        except ImportError as e:
            self.logger.warning(f"Weather service not available: {e}")
            WeatherService = None

        try:
            from services.youtube_service import create_youtube_service
        except ImportError as e:
            self.logger.warning(f"YouTube service not available: {e}")
            create_youtube_service = None

        # Load USE_NOTICES setting
        use_notices_setting = os.getenv("USE_NOTICES", "false").lower()
        self.use_notices = use_notices_setting in ("true", "1", "yes", "on")
        if self.use_notices:
            self.logger.info("📢 Using IRC NOTICEs for channel responses")
        else:
            self.logger.info("💬 Using regular PRIVMSGs for channel responses")

        # Load TAMAGOTCHI_ENABLED setting from .env file
        tamagotchi_setting = os.getenv("TAMAGOTCHI_ENABLED", "true").lower()
        self.tamagotchi_enabled = tamagotchi_setting in ("true", "1", "yes", "on")
        if self.tamagotchi_enabled:
            self.logger.info("🐣 Tamagotchi responses enabled")
        else:
            self.logger.info("🐣 Tamagotchi responses disabled")

        # Initialize bot components
        self.logger.debug("Initializing data manager...")
        self.data_manager = DataManager()
        self.logger.debug("Initializing drink tracker...")
        self.drink_tracker = DrinkTracker(self.data_manager)
        self.logger.debug("Initializing general words...")
        self.general_words = GeneralWords(self.data_manager)
        self.logger.debug("Initializing tamagotchi...")
        self.tamagotchi = TamagotchiBot(self.data_manager)
        self.logger.debug("Bot components initialized.")

        # Initialize weather service
        if WeatherService is not None:
            weather_api_key = get_api_key("WEATHER_API_KEY")
            if weather_api_key:
                self.weather_service = WeatherService(weather_api_key)
                self.logger.info("🌤️ Weather service initialized")
            else:
                self.logger.warning(
                    "⚠️  No weather API key found. Weather commands will not work."
                )
                self.weather_service = None
        else:
            self.weather_service = None

        # Initialize GPT service
        if GPTService is not None:
            openai_api_key = get_api_key("OPENAI_API_KEY")
            history_file = os.getenv("HISTORY_FILE", "conversation_history.json")
            history_limit = int(os.getenv("GPT_HISTORY_LIMIT", "100"))
            if openai_api_key:
                self.gpt_service = GPTService(
                    openai_api_key, history_file, history_limit
                )
                self.logger.info(
                    f"🤖 GPT chat service initialized (history limit: {history_limit} messages)"
                )
                # Log the OpenAI model in use at startup
                self.logger.info(f"🧠 OpenAI model: {self.gpt_service.model}")
            else:
                self.logger.warning(
                    "⚠️  No OpenAI API key found. AI chat will not work."
                )
                self.gpt_service = None
        else:
            self.gpt_service = None

        # Initialize electricity service
        if create_electricity_service is not None:
            electricity_api_key = get_api_key("ELECTRICITY_API_KEY")
            if electricity_api_key:
                self.electricity_service = create_electricity_service(
                    electricity_api_key
                )
                self.logger.info("⚡ Electricity price service initialized")
            else:
                self.logger.warning(
                    "⚠️  No electricity API key found. Electricity price commands will not work."
                )
                self.electricity_service = None
        else:
            self.electricity_service = None

        # Initialize YouTube service
        if create_youtube_service is not None:
            youtube_api_key = get_api_key("YOUTUBE_API_KEY")
            if youtube_api_key:
                self.youtube_service = create_youtube_service(youtube_api_key)
                self.logger.info("▶️ YouTube service initialized")
            else:
                self.logger.warning(
                    "⚠️  No YouTube API key found. YouTube commands will not work."
                )
                self.youtube_service = None
        else:
            self.youtube_service = None

        # Initialize crypto service
        if create_crypto_service is not None:
            self.crypto_service = create_crypto_service()
            self.logger.info("🪙 Crypto service initialized (using CoinGecko API)")
        else:
            self.crypto_service = None

        # Initialize nanoleet detector
        self.nanoleet_detector = create_nanoleet_detector()
        self.logger.info("🎯 Nanosecond leet detector initialized")

        # Initialize FMI warning service
        if create_fmi_warning_service is not None:
            self.fmi_warning_service = create_fmi_warning_service(
                callback=self._handle_fmi_warnings
            )
            self.logger.info("⚠️ FMI warning service initialized")
        else:
            self.fmi_warning_service = None

        # Storage for the latest Otiedote release info
        self.latest_otiedote: Optional[dict] = None

        # Initialize Otiedote service
        if create_otiedote_service is not None:
            self.otiedote_service = create_otiedote_service(
                callback=self._handle_otiedote_release
            )
            self.logger.info("📢 Otiedote monitoring service initialized")
        else:
            self.otiedote_service = None

        # Initialize lemmatizer with graceful fallback
        self.logger.debug("Initializing lemmatizer...")
        try:
            self.lemmatizer = Lemmatizer()
            self.logger.info("🔤 Lemmatizer component initialized")
        except Exception as e:
            self.logger.warning(f"Could not initialize lemmatizer: {e}")
            self.lemmatizer = None

        # Note: Signal handling is done in main.py
        self.logger.debug("BotManager initialization complete!")

    def _is_interactive_terminal(self):
        """Check if we're running in an interactive terminal."""
        try:
            import sys

            # Check if stdin is a TTY and we're not being piped to
            return sys.stdin.isatty() and sys.stdout.isatty()
        except (AttributeError, OSError):
            return False

    def _setup_readline_history(self):
        """Configure readline for command history and editing."""
        try:
            # Only set up readline if we're in an interactive terminal
            if not self._is_interactive_terminal():
                self.logger.debug("Non-interactive terminal, skipping readline setup")
                self._history_file = None
                return

            # Set history file
            history_file = os.path.expanduser("~/.leetbot_history")

            # Set history length (number of commands to remember)
            readline.set_history_length(1000)

            # Try to read existing history
            try:
                readline.read_history_file(history_file)
                self.logger.debug(f"Loaded command history from {history_file}")
            except FileNotFoundError:
                # History file doesn't exist yet, that's fine
                pass
            except Exception as e:
                self.logger.warning(f"Could not load command history: {e}")

            # Configure readline for better editing (Linux/Unix compatible)
            if READLINE_AVAILABLE:
                try:
                    # Enable tab completion
                    readline.parse_and_bind("tab: complete")
                    # Set editing mode to emacs (supports arrow keys)
                    readline.parse_and_bind("set editing-mode emacs")
                    # Enable arrow key navigation
                    readline.parse_and_bind("\\C-p: previous-history")  # Up arrow
                    readline.parse_and_bind("\\C-n: next-history")  # Down arrow
                    readline.parse_and_bind("\\C-b: backward-char")  # Left arrow
                    readline.parse_and_bind("\\C-f: forward-char")  # Right arrow
                    # Enable better line editing
                    readline.parse_and_bind("\\C-a: beginning-of-line")  # Ctrl+A
                    readline.parse_and_bind("\\C-e: end-of-line")  # Ctrl+E
                    readline.parse_and_bind("\\C-k: kill-line")  # Ctrl+K
                    self.logger.debug("Readline key bindings configured")
                except Exception as e:
                    self.logger.warning(f"Could not configure readline bindings: {e}")

            # Store history file path for saving later
            self._history_file = history_file

        except ImportError:
            # readline not available (e.g., on some Windows installations)
            self.logger.warning(
                "readline module not available, command history disabled"
            )
            self._history_file = None
        except Exception as e:
            self.logger.warning(f"Could not configure readline: {e}")
            self._history_file = None

    def _save_command_history(self):
        """Save command history to file."""
        if hasattr(self, "_history_file") and self._history_file:
            try:
                readline.write_history_file(self._history_file)
                self.logger.debug(f"Saved command history to {self._history_file}")
            except Exception as e:
                self.logger.warning(f"Could not save command history: {e}")

    def load_configurations(self) -> bool:
        """
        Load server configurations from environment variables.

        Returns:
            True if configurations were loaded successfully, False otherwise
        """
        # Load environment file
        if not load_env_file():
            self.logger.warning("Could not load .env file")

        # Get server configurations
        server_configs = get_server_configs()

        if not server_configs:
            self.logger.error("No server configurations found!")
            return False

        # Create Server instances
        for config in server_configs:
            server = Server(config, self.bot_name, self.stop_event)
            # Set the quit message from bot manager to server
            server.quit_message = self.quit_message
            self.servers[config.name] = server
            self.logger.info(
                f"Loaded server configuration: {config.name} ({config.host}:{config.port})"
            )

        return True

    def register_callbacks(self):
        """Register all bot functionality callbacks with each server."""
        for server_name, server in self.servers.items():
            # Register message callback for command processing
            server.register_callback("message", self._handle_message)

            # Register notice callback for processing notices
            server.register_callback("notice", self._handle_notice)

            # Register join callback for user tracking
            server.register_callback("join", self._handle_join)

            # Register part callback for cleanup
            server.register_callback("part", self._handle_part)

            # Register quit callback for cleanup
            server.register_callback("quit", self._handle_quit)

            self.logger.info(f"Registered callbacks for server: {server_name}")

    def _handle_notice(self, server: Server, sender: str, target: str, text: str):
        """
        Handle incoming notices from any server.

        Args:
            server: The Server instance that received the notice
            sender: The nickname who sent the notice
            target: The target (channel or bot's nick)
            text: The notice content
        """
        try:
            # Create context for the notice
            context = {
                "server": server,
                "server_name": server.config.name,
                "sender": sender,
                "target": target,
                "text": text,
                "is_private": not target.startswith("#"),
                "bot_name": self.bot_name,
            }

            # Process leet winners summary lines (first/last/multileet)
            try:
                self._process_leet_winner_summary(text, sender)
            except Exception as e:
                self.logger.warning(f"Error processing leet winners summary: {e}")

        except Exception as e:
            self.logger.error(f"Error handling notice from {server.config.name}: {e}")

    def _handle_message(self, server: Server, sender: str, target: str, text: str):
        """
        Handle incoming messages from any server.

        Args:
            server: The Server instance that received the message
            sender: The nickname who sent the message
            target: The target (channel or bot's nick)
            text: The message content
        """
        try:
            # Create context for the message
            context = {
                "server": server,
                "server_name": server.config.name,
                "sender": sender,
                "target": target,
                "text": text,
                "is_private": not target.startswith("#"),
                "bot_name": self.bot_name,
            }

            # 🎯 FIRST PRIORITY: Check for nanoleet achievements for maximum timestamp accuracy
            # This must be the very first thing we do to get the most accurate timestamp
            if sender.lower() != self.bot_name.lower():
                self._check_nanoleet_achievement(context)

            # Track words if not from the bot itself
            if sender.lower() != self.bot_name.lower():
                self._track_words(context)

            # Check for YouTube URLs and display video info
            if self.youtube_service and sender.lower() != self.bot_name.lower():
                self._handle_youtube_urls(context)

            # Minimal AI chat for IRC: respond to private messages or mentions
            try:
                is_private = not target.startswith("#")
                bot_lower = self.bot_name.lower()
                text_lower = text.lower() if isinstance(text, str) else ""
                is_mention = text_lower.startswith(
                    f"{bot_lower}:"
                ) or text_lower.startswith(f"{bot_lower},")
                if (
                    self.gpt_service
                    and (is_private or is_mention)
                    and not text.startswith("!")
                ):
                    ai_response = self._chat_with_gpt(text, sender)
                    if ai_response:
                        reply_target = sender if is_private else target
                        # Send as multiple IRC lines (split by newline, wrap long lines)
                        for line in str(ai_response).split("\n"):
                            line = line.rstrip()
                            if not line:
                                continue
                            try:
                                parts = self._wrap_irc_message_utf8_bytes(
                                    line, reply_target
                                )
                            except Exception:
                                parts = [line]
                            for part in parts:
                                if part:
                                    self._send_response(server, reply_target, part)
            except Exception as e:
                self.logger.warning(f"AI chat processing error: {e}")

            # Fetch and display page titles for URLs posted in channels (non-commands)
            if (
                sender.lower() != self.bot_name.lower()
                and target.startswith("#")
                and not text.startswith("!")
            ):
                try:
                    self._fetch_title(context["server"], target, text)
                except Exception as e:
                    self.logger.warning(f"Error in URL title fetcher: {e}")

            # Process commands
            self._process_commands(context)

        except Exception as e:
            self.logger.error(f"Error handling message from {server.config.name}: {e}")

    def _handle_join(self, server: Server, sender: str, channel: str):
        """Handle user join events."""
        # Track user activity
        server_name = server.config.name
        self.logger.info(f"{sender} joined {channel}", server_name)

    def _handle_part(self, server: Server, sender: str, channel: str):
        """Handle user part events."""
        # Track user activity
        server_name = server.config.name
        self.logger.info(f"{sender} left {channel}", server_name)

    def _handle_quit(self, server: Server, sender: str):
        """Handle user quit events."""
        # Track user activity
        server_name = server.config.name
        self.logger.info(f"{sender} quit", server_name)

    def _track_words(self, context: Dict[str, Any]):
        """Track words for statistics and drink tracking."""
        server_name = context["server_name"]
        sender = context["sender"]
        text = context["text"]
        target = context["target"]

        # Only track in channels, not private messages
        if not target.startswith("#"):
            return

        # Track drink words
        self.drink_tracker.process_message(server=server_name, nick=sender, text=text)

        # Track general words
        self.general_words.process_message(
            server=server_name, nick=sender, text=text, target=target
        )

        # Update tamagotchi (only if enabled)
        if self.tamagotchi_enabled:
            should_respond, response = self.tamagotchi.process_message(
                server=server_name, nick=sender, text=text
            )

            # Send tamagotchi response if needed
            if should_respond and response:
                server = context["server"]
                self._send_response(server, target, response)

    def _process_commands(self, context: Dict[str, Any]):
        """Process IRC commands and bot interactions."""
        server = context["server"]
        sender = context["sender"]
        target = context["target"]
        text = context["text"]

        # Quick built-in handler for latest Otiedote description
        try:
            if isinstance(text, str) and text.strip().lower().startswith("!otiedote"):
                self._send_latest_otiedote(server, target)
                return
        except Exception as e:
            self.logger.warning(f"Error handling !otiedote: {e}")

        bot_functions = {
            "data_manager": self.data_manager,
            "drink_tracker": self.drink_tracker,
            "general_words": self.general_words,
            "tamagotchi_bot": self.tamagotchi,
            "lemmat": self.lemmatizer,
            "server": server,
            "server_name": context["server_name"],
            "bot_name": self.bot_name,
            "latency_start": lambda: getattr(self, "_latency_start", 0),
            "set_latency_start": lambda value: setattr(self, "_latency_start", value),
            "notice_message": lambda msg, irc=None, target=None: self._send_response(
                server, target or context["target"], msg
            ),
            "send_electricity_price": self._send_electricity_price,
            "measure_latency": self._measure_latency,
            "get_crypto_price": self._get_crypto_price,
            "send_youtube_info": self._send_youtube_info,
            "send_crypto_price": self._send_crypto_price,
            "load_leet_winners": self._load_leet_winners,
            "save_leet_winners": self._save_leet_winners,
            "send_weather": self._send_weather,
            "send_scheduled_message": self._send_scheduled_message,
            "get_eurojackpot_numbers": self._get_eurojackpot_numbers,
            "search_youtube": self._search_youtube,
            "handle_ipfs_command": self._handle_ipfs_command,
            "lookup": lambda irc: context["server_name"],
            "format_counts": self._format_counts,
            "chat_with_gpt": lambda msg, sender=None: self._chat_with_gpt(
                msg, sender or context["sender"]
            ),
            "wrap_irc_message_utf8_bytes": self._wrap_irc_message_utf8_bytes,
            "send_message": lambda irc, target, msg: server.send_message(target, msg),
            "log": self._log,
            "fetch_title": self._fetch_title,
            "subscriptions": self._get_subscriptions_module(),
            "DRINK_WORDS": self._get_drink_words(),
            "get_latency_start": lambda: getattr(self, "_latency_start", 0),
            "BOT_VERSION": "2.1.0",
            "toggle_tamagotchi": lambda srv, tgt, snd: self.toggle_tamagotchi(
                srv, tgt, snd
            ),
            "stop_event": self.stop_event,  # Allow IRC commands to trigger shutdown
            "set_quit_message": self.set_quit_message,  # Allow setting custom quit message
            "set_openai_model": self.set_openai_model,  # Allow changing OpenAI model at runtime
        }

        # Create a mock IRC message format for commands.py compatibility
        mock_message = f":{sender}!{sender}@host.com PRIVMSG {target} :{text}"

        try:
            # Use enhanced command processing system
            from command_loader import enhanced_process_irc_message

            enhanced_process_irc_message(server, mock_message, bot_functions)
        except Exception as e:
            self.logger.error(f"Error processing command: {e}")

    def start(self):
        """Start all servers and bot functionality."""
        if not self.load_configurations():
            return False

        self.register_callbacks()

        # Start monitoring services
        if self.fmi_warning_service is not None:
            self.fmi_warning_service.start()
        if self.otiedote_service is not None:
            self.otiedote_service.start()

        # Start console listener thread
        self.console_thread = threading.Thread(
            target=self._listen_for_console_commands,
            daemon=True,
            name="Console-Listener",
        )
        self.console_thread.start()
        self.logger.info("Started console input listener")

        # Start each server in its own thread
        for server_name, server in self.servers.items():
            thread = threading.Thread(
                target=server.start, name=f"Server-{server_name}", daemon=False
            )
            thread.start()
            self.server_threads[server_name] = thread
            self.logger.info(f"Started server thread for {server_name}")

        self.logger.info(f"Bot manager started with {len(self.servers)} servers")
        safe_print(
            "💬 Console is ready! Type commands (!help) or chat messages.",
            "[CHAT] Console is ready! Type commands (!help) or chat messages.",
        )
        safe_print(
            "🔧 Commands: !help, !version, !s <location>, !ping, etc.",
            "[CONFIG] Commands: !help, !version, !s <location>, !ping, etc.",
        )
        safe_print(
            "🗣️  Chat: Type any message (without !) to chat with AI",
            "[TALK] Chat: Type any message (without !) to chat with AI",
        )
        safe_print(
            "🛑 Exit: Type 'quit' or 'exit' or press Ctrl+C",
            "[STOP] Exit: Type 'quit' or 'exit' or press Ctrl+C",
        )
        print("-" * 60)
        return True

    def _handle_fmi_warnings(self, warnings: List[str]):
        """Handle new FMI weather warnings."""
        # Get subscriptions module
        subscriptions = self._get_subscriptions_module()

        for warning in warnings:
            # Get subscribers for varoitukset (returns (nick, server) tuples)
            subscribers = subscriptions.get_subscribers("varoitukset")

            if not subscribers:
                self.logger.debug("No subscribers for varoitukset, skipping warning")
                continue

            # Send warnings to subscribed channels/users
            for subscriber_nick, server_name in subscribers:
                try:
                    # Find the server by name
                    server = self.servers.get(server_name)
                    if not server:
                        self.logger.warning(
                            f"Server {server_name} not found for subscriber {subscriber_nick}"
                        )
                        continue

                    # Send the warning
                    self._send_response(server, subscriber_nick, warning)
                    self.logger.info(
                        f"Sent FMI warning to {subscriber_nick} on {server_name}"
                    )

                except Exception as e:
                    self.logger.error(
                        f"Error sending FMI warning to {subscriber_nick} on {server_name}: {e}"
                    )

    def _handle_otiedote_release(
        self, title: str, url: str, description: Optional[str] = None
    ):
        """Handle new Otiedote press release.

        Uses the subscriptions system to deliver messages only to explicit
        onnettomuustiedotteet subscribers per server, mirroring FMI warnings.

        Automatically broadcasts only title + URL.
        Stores the full info for the !otiedote command to display description on-demand.
        """
        # Persist latest release info for on-demand access via !otiedote
        try:
            self.latest_otiedote = {
                "title": title,
                "url": url,
                "description": description or "",
            }
        except Exception:
            # Never fail the broadcast due to caching issues
            pass

        header_message = f"📢 {title} | {url}"

        # Get subscriptions module and subscribers for onnettomuustiedotteet
        subscriptions = self._get_subscriptions_module()
        subscribers = []
        try:
            subscribers = subscriptions.get_subscribers("onnettomuustiedotteet")
        except Exception as e:
            self.logger.error(f"Error getting onnettomuustiedotteet subscribers: {e}")
            return

        if not subscribers:
            self.logger.debug(
                "No subscribers for onnettomuustiedotteet, not broadcasting Otiedote release"
            )
            return

        # Send to subscribed channels/users on their respective servers
        for subscriber_nick, server_name in subscribers:
            try:
                server = self.servers.get(server_name)
                if not server:
                    self.logger.warning(
                        f"Server {server_name} not found for Otiedote subscriber {subscriber_nick}"
                    )
                    continue

                # Broadcast only the header (no description here)
                self._send_response(server, subscriber_nick, header_message)
                self.logger.info(
                    f"Sent Otiedote release to {subscriber_nick} on {server_name}"
                )
            except Exception as e:
                self.logger.error(
                    f"Error sending Otiedote release to {subscriber_nick} on {server_name}: {e}"
                )

    def stop(self, quit_message: str = None):
        """Stop all servers and bot functionality gracefully.

        Args:
            quit_message (str, optional): Custom quit message to use. If not provided, uses the stored quit_message.
        """
        if quit_message:
            self.quit_message = quit_message

        self.logger.info(
            f"Shutting down bot manager with message: {self.quit_message}..."
        )

        # Stop monitoring services with logging
        try:
            if self.fmi_warning_service is not None:
                self.logger.info("Stopping FMI warning service...")
                self.fmi_warning_service.stop()
        except Exception as e:
            self.logger.error(f"Error stopping FMI warning service: {e}")

        try:
            if self.otiedote_service is not None:
                self.logger.info(
                    "Stopping Otiedote service (may take up to 10 seconds)..."
                )
                self.otiedote_service.stop()
                time.sleep(10)  # Grace period for the monitor thread
                self.logger.info("Otiedote service stopped")
        except Exception as e:
            self.logger.error(f"Error stopping Otiedote service: {e}")

        # Set stop event
        self.stop_event.set()

        # Stop all servers with custom quit message
        for server_name, server in self.servers.items():
            self.logger.info(
                f"Stopping server {server_name} with quit message: {self.quit_message}..."
            )
            try:
                server.stop(quit_message=self.quit_message)
            except Exception as e:
                self.logger.error(f"Error stopping server {server_name}: {e}")

        # Wait for all server threads to finish with shorter timeout
        for server_name, thread in self.server_threads.items():
            self.logger.info(f"Waiting for server thread {server_name} to finish...")
            thread.join(timeout=3.0)  # Reduced timeout for faster shutdown
            if thread.is_alive():
                self.logger.warning(
                    f"Server thread {server_name} did not finish cleanly within 3s timeout"
                )

        # Stop console thread if it exists
        if hasattr(self, "console_thread") and self.console_thread.is_alive():
            self.logger.info("Stopping console listener...")
            # Console thread will stop when stop_event is set

        self.logger.info("Bot manager shut down complete")

    def wait_for_shutdown(self):
        """Wait for all server threads to complete or for shutdown signal."""
        try:
            while any(thread.is_alive() for thread in self.server_threads.values()):
                # Check if shutdown was requested
                if self.stop_event.is_set():
                    break
                time.sleep(0.1)  # Check more frequently for faster response
        except KeyboardInterrupt:
            # Handle KeyboardInterrupt by setting stop event to prevent reconnects
            self.logger.info("Keyboard interrupt received, stopping all servers...")
            self.stop_event.set()

            # Call stop() immediately to force quit IRC connections
            try:
                for server in self.servers.values():
                    if server.connected:
                        server.quit("Keyboard interrupt")
            except Exception as e:
                self.logger.error(f"Error during immediate quit: {e}")

            # Re-raise to let main.py handle the shutdown message
            raise

    def _listen_for_console_commands(self):
        """Listen for console commands in a separate thread with readline history support."""
        try:
            # Check if we're running in an interactive terminal
            if not self._is_interactive_terminal():
                self.logger.info(
                    "Non-interactive terminal detected, disabling console input"
                )
                # Just wait for stop event without trying to read input
                while not self.stop_event.is_set():
                    time.sleep(0.5)
                return

            while not self.stop_event.is_set():
                try:
                    # Mark that input is active for output protection
                    self._input_active = True
                    user_input = input("💬 > ")
                    # Mark that input is no longer active
                    self._input_active = False

                    if not user_input or not user_input.strip():
                        continue

                    user_input = user_input.strip()

                    if user_input.lower() in ("quit", "exit"):
                        self.logger.info("Console quit command received")
                        safe_print(
                            "🛑 Shutting down bot...", "[STOP] Shutting down bot..."
                        )
                        self.stop_event.set()
                        break

                    if user_input.startswith("!"):
                        # Process console commands
                        try:
                            from command_loader import process_console_command

                            # Create bot functions for console use
                            bot_functions = self._create_console_bot_functions()
                            process_console_command(user_input, bot_functions)
                        except Exception as e:
                            self.logger.error(f"Console command error: {e}")
                    else:
                        # Send to AI chat
                        try:
                            if self.gpt_service:
                                response = self.gpt_service.chat(user_input, "Console")
                                if response:
                                    self.logger.info(f"🤖 AI: {response}")
                            else:
                                self.logger.error(
                                    "🤖 AI service not available (no OpenAI API key configured)"
                                )
                        except Exception as e:
                            self.logger.error(f"AI chat error: {e}")

                except (EOFError, KeyboardInterrupt):
                    self.logger.error("\n🛑 Console input interrupted")
                    self.stop_event.set()
                    break
        except Exception as e:
            self.logger.error(f"Console listener error: {e}")
        finally:
            # Save command history on exit
            self._save_command_history()

    def _create_console_bot_functions(self):
        """Create bot functions dictionary for console commands."""
        return {
            # Core functions
            "notice_message": lambda msg, irc=None, target=None: self.logger.info(
                f"✅ {msg}"
            ),
            "log": self.logger.info,
            "send_weather": self._console_weather,
            "send_electricity_price": self._console_electricity,
            "get_crypto_price": self._get_crypto_price,
            "send_scheduled_message": self._send_scheduled_message,
            "get_eurojackpot_numbers": self._get_eurojackpot_numbers,
            "get_eurojackpot_results": self._get_eurojackpot_results,
            "search_youtube": self._search_youtube,
            "handle_ipfs_command": self._handle_ipfs_command,
            "chat_with_gpt": lambda msg, sender="Console": (
                self.gpt_service.chat(msg, sender)
                if self.gpt_service
                else "AI not available"
            ),
            "BOT_VERSION": "2.1.0",
            "server_name": "console",
            "stop_event": self.stop_event,  # Allow console commands to trigger shutdown
            "set_quit_message": self.set_quit_message,  # Allow setting custom quit message
            "set_openai_model": self.set_openai_model,  # Allow changing OpenAI model at runtime
        }

    def set_quit_message(self, message: str):
        """Set a custom quit message for all servers.

        Args:
            message (str): The quit message to use when stopping servers.
        """
        self.quit_message = message
        self.logger.info(f"Quit message set to: {message}")

        # Update quit message for all existing servers
        for server_name, server in self.servers.items():
            server.quit_message = message
            self.logger.debug(
                f"Updated quit message for server {server_name}: {message}"
            )

    def set_openai_model(self, model: str) -> str:
        """Set the OpenAI model used by the GPT service and persist to .env.

        Returns a user-friendly status string.
        """
        try:
            if not hasattr(self, "gpt_service") or not self.gpt_service:
                self.logger.warning(
                    "Attempted to set OpenAI model but GPT service is not initialized"
                )
                return "❌ AI chat is not available (no OpenAI API key configured)"

            old = getattr(self.gpt_service, "model", None)
            self.gpt_service.model = model
            # Persist to environment and .env file
            os.environ["OPENAI_MODEL"] = model
            persisted = self._update_env_file("OPENAI_MODEL", model)
            self.logger.info(f"🧠 OpenAI model changed from {old} to {model}")
            if persisted:
                return f"✅ OpenAI model set to '{model}' (persisted)"
            else:
                return f"✅ OpenAI model set to '{model}' (session only)"
        except Exception as e:
            self.logger.error(f"Error setting OpenAI model: {e}")
            return f"❌ Failed to set OpenAI model: {e}"

    def _console_weather(self, irc, channel, location):
        """Console weather command."""
        if not self.weather_service:
            self.logger.error("☁️ Weather service not available (no WEATHER_API_KEY)")
            return

        try:
            weather_data = self.weather_service.get_weather(location)
            response = self.weather_service.format_weather_message(weather_data)
            self.logger.info(f"🌤️ {response}")
        except Exception as e:
            self.logger.info(f"❌ Weather error: {e}")

    def _console_electricity(self, irc, channel, args):
        """Console electricity price command."""
        if not self.electricity_service:
            self.logger.error(
                "⚡ Electricity service not available (no ELECTRICITY_API_KEY)"
            )
            return

        try:
            import datetime

            current_hour = datetime.datetime.now().hour
            price_data = self.electricity_service.get_electricity_price(
                hour=current_hour
            )
            response = self.electricity_service.format_price_message(price_data)
            self.logger.info(f"⚡ {response}")
        except Exception as e:
            self.logger.info(f"❌ Electricity error: {e}")

    def get_server_by_name(self, name: str) -> Optional[Server]:
        """Get a server instance by name."""
        return self.servers.get(name)

    def get_all_servers(self) -> Dict[str, Server]:
        """Get all server instances."""
        return self.servers.copy()

    def send_to_all_servers(self, target: str, message: str):
        """Send a message to the same target on all servers."""
        for server in self.servers.values():
            try:
                server.send_message(target, message)
            except Exception as e:
                self.logger.error(f"Error sending to {server.config.name}: {e}")

    def send_notice_to_all_servers(self, target: str, message: str):
        """Send a notice to the same target on all servers."""
        for server in self.servers.values():
            try:
                server.send_notice(target, message)
            except Exception as e:
                self.logger.error(f"Error sending notice to {server.config.name}: {e}")

    def _send_notice(self, server, target: str, message: str):
        """Send a notice message."""
        if server:
            server.send_notice(target, message)
        else:
            self.logger.info(f"Console: {message}")

    def _send_electricity_price(self, irc, channel, text_or_parts):
        """Handle the !sähkö command for hourly or 15-minute prices."""
        if not self.electricity_service:
            response = "⚡ Electricity price service not available. Please configure ELECTRICITY_API_KEY."
            self._send_response(irc, channel, response)
            return

        try:
            # Handle both string and list inputs for compatibility
            if isinstance(text_or_parts, list):
                # Called from IRC command with parts list
                args = text_or_parts[1:] if len(text_or_parts) > 1 else []
                text = " ".join(args)
            else:
                # Called with string (e.g., from tests or console)
                text = text_or_parts or ""
                args = text.split() if text else []

            # Parse command arguments (extended for 15-minute support)
            parsed_args = self.electricity_service.parse_command_args(args)

            if parsed_args.get("error"):
                self._send_response(irc, channel, f"⚡ {parsed_args['error']}")
                return

            if parsed_args.get("show_stats"):
                # Show daily statistics
                stats_data = self.electricity_service.get_price_statistics(
                    parsed_args["date"]
                )
                response = self.electricity_service.format_statistics_message(
                    stats_data
                )
            elif parsed_args.get("show_all_hours"):
                # Show all hours for the day
                all_prices = []
                for h in range(24):
                    price_data = self.electricity_service.get_electricity_price(
                        hour=h, date=parsed_args["date"]
                    )
                    if price_data.get("error"):
                        all_prices.append({"hour": h, "error": price_data["message"]})
                    else:
                        all_prices.append(price_data)
                response = self.electricity_service.format_daily_prices_message(
                    all_prices, is_tomorrow=parsed_args["is_tomorrow"]
                )
            else:
                # Handle specific hour or 15-minute interval
                price_data = self.electricity_service.get_electricity_price(
                    hour=parsed_args.get("hour"),
                    quarter=parsed_args.get("quarter"),
                    date=parsed_args["date"],
                )
                response = self.electricity_service.format_price_message(price_data)

            self._send_response(irc, channel, response)

        except Exception as e:
            error_msg = f"⚡ Error getting electricity price: {str(e)}"
            self.logger.error(f"Electricity price error: {e}")
            self._send_response(irc, channel, error_msg)

    def _measure_latency(self):
        """Measure latency."""
        import time

        # Set latency measurement start time
        setattr(self, "_latency_start", time.time())
        return time.time()

    def _get_crypto_price(self, coin: str, currency: str = "eur"):
        """Get cryptocurrency price."""
        try:
            price_data = self.crypto_service.get_crypto_price(coin, currency)
            if price_data.get("error"):
                return f"Error: {price_data.get('message', 'Unknown error')}"
            return f"{price_data['price']:.2f} {currency.upper()}"
        except Exception as e:
            self.logger.error(f"Error getting crypto price: {e}")
            return "N/A"

    def _load_leet_winners(self):
        """Load leet winners data."""
        try:
            import json

            with open("leet_winners.json", "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_leet_winners(self, data):
        """Save leet winners data."""
        try:
            import json

            with open("leet_winners.json", "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving leet winners: {e}")

    def _send_response(self, server, target: str, message: str):
        """Send a response using NOTICE or PRIVMSG based on USE_NOTICES setting."""
        if not server:  # Console output
            self.logger.msg(message, "MSG")
            return

        if self.use_notices:
            server.send_notice(target, message)
        else:
            server.send_message(target, message)

    def _send_latest_otiedote(self, server, target):
        """Send the latest cached Otiedote description on-demand (no header)."""
        try:
            info = getattr(self, "latest_otiedote", None)
            if not info:
                self._send_response(
                    server,
                    target,
                    "📢 Ei tallennettua Onnettomuustiedotetta vielä. Odota uutta ilmoitusta.",
                )
                return

            desc = (info.get("description") or "").strip()
            if not desc:
                response = f"📢 Ei kuvausta saatavilla. | {info.get('url', '')}"
                self._send_response(server, target, response)
                return

            # Wrap and send description only
            for line in self._wrap_irc_message_utf8_bytes(
                f"Kuvaus: {desc}", reply_target=target
            ):
                if line:
                    self._send_response(server, target, line)
        except Exception as e:
            self.logger.error(f"Error sending latest Otiedote: {e}")
            self._send_response(server, target, f"❌ Virhe: {e}")

    def _send_weather(self, irc, channel, location):
        """Send weather information."""
        if not self.weather_service:
            response = (
                "Weather service not available. Please configure WEATHER_API_KEY."
            )
        else:
            try:
                weather_data = self.weather_service.get_weather(location)
                response = self.weather_service.format_weather_message(weather_data)
            except Exception as e:
                response = f"Error getting weather for {location}: {str(e)}"

        # Send response via IRC if we have server context, otherwise print to console
        if irc and hasattr(irc, "send_message") and channel:
            self._send_response(irc, channel, response)
        else:
            self.logger.info(response)

    def _send_scheduled_message(
        self, irc_client, channel, message, hour, minute, second, microsecond=0
    ):
        """Send scheduled message."""
        try:
            from services.scheduled_message_service import send_scheduled_message

            message_id = send_scheduled_message(
                irc_client, channel, message, hour, minute, second, microsecond
            )
            self.logger.info(
                f"Scheduled message {message_id}: '{message}' to {channel} at {hour:02d}:{minute:02d}:{second:02d}.{microsecond:06d}"
            )
            return f"✅ Message scheduled with ID: {message_id}"
        except Exception as e:
            self.logger.error(f"Error scheduling message: {e}")
            return f"❌ Error scheduling message: {str(e)}"

    def _get_eurojackpot_numbers(self):
        """Get Eurojackpot numbers."""
        try:
            from services.eurojackpot_service import get_eurojackpot_numbers

            return get_eurojackpot_numbers()
        except Exception as e:
            self.logger.error(f"Error getting Eurojackpot numbers: {e}")
            return f"❌ Error getting Eurojackpot info: {str(e)}"

    def _get_eurojackpot_results(self):
        """Get Eurojackpot results."""
        try:
            from services.eurojackpot_service import get_eurojackpot_results

            return get_eurojackpot_results()
        except Exception as e:
            self.logger.error(f"Error getting Eurojackpot results: {e}")
            return f"❌ Error getting Eurojackpot results: {str(e)}"

    def _search_youtube(self, query):
        """Search YouTube."""
        if not self.youtube_service:
            return "YouTube service not available. Please configure YOUTUBE_API_KEY."

        try:
            search_data = self.youtube_service.search_videos(query, max_results=3)
            return self.youtube_service.format_search_results_message(search_data)
        except Exception as e:
            self.logger.error(f"Error searching YouTube: {e}")
            return f"Error searching YouTube: {str(e)}"

    def _process_leet_winner_summary(self, text: str, sender: str = None):
        """Parser for leet winners summary lines.

        Updates leet_winners.json counts for categories:
        - "first" (first)
        - "last" (last)
        - "multileet" (closest to 13:37)

        Only accepts messages from authorized nicks (Beici, Beibi, Beiki)
        or messages that start with admin password.

        This keeps !leetwinners in sync with external announcer messages.
        """
        import re
        from datetime import datetime

        from config import get_config

        # Define allowed nicks for leet winner tracking
        ALLOWED_NICKS = {"beici", "beibi", "beiki"}

        # Check if message starts with admin password (case-sensitive check)
        admin_override = False
        if text and text.strip():
            config = get_config()
            admin_password = config.admin_password
            if admin_password and text.startswith(admin_password):
                admin_override = True
                # Remove admin password from text for processing
                text = text[
                    len(admin_password) :  # noqa E203 - Black formatting
                ].strip()

        # Check sender authorization (case-insensitive)
        if not admin_override and (not sender or sender.lower() not in ALLOWED_NICKS):
            return

        self.logger.debug(f"Processing leet winner summary: {text} from {sender}")

        # Regex pattern for detection
        pattern = r"Ensimmäinen leettaaja oli (\S+) .*?, viimeinen oli (\S+) .*?Lähimpänä multileettiä oli (\S+)"
        match = re.search(pattern, text)
        if not match:
            return

        first, last, multileet = match.groups()

        # Load current winners
        winners = self._load_leet_winners()

        # Initialize metadata if this is the first time we're tracking
        if not winners or "_metadata" not in winners:
            current_date = datetime.now().strftime("%d.%m.%Y")
            winners["_metadata"] = {"statistics_started": current_date}

        # Helper to bump count in winners dict
        def bump(name: str, category: str):
            if not name:
                return
            if name in winners:
                winners[name][category] = winners[name].get(category, 0) + 1
            else:
                winners[name] = {category: 1}

        bump(first, "first")
        bump(last, "last")
        bump(multileet, "multileet")

        self._save_leet_winners(winners)

        # Log with authorization info
        auth_info = "admin override" if admin_override else f"authorized nick: {sender}"
        self.logger.info(
            f"Updated leet winners (first={first}, last={last}, multileet={multileet}) via {auth_info}"
        )

    def _handle_ipfs_command(self, command_text, irc_client=None, target=None):
        """Handle IPFS commands."""
        try:
            from services.ipfs_service import handle_ipfs_command

            admin_password = os.getenv("ADMIN_PASSWORD")
            response = handle_ipfs_command(command_text, admin_password)

            if irc_client and target:
                self._send_response(irc_client, target, response)
            else:
                self.logger.info(f"IPFS command result: {response}")
                return response

        except Exception as e:
            error_msg = f"❌ IPFS error: {str(e)}"
            self.logger.error(f"Error handling IPFS command: {e}")
            if irc_client and target:
                self._send_response(irc_client, target, error_msg)
            else:
                return error_msg

    def _format_counts(self, data):
        """Format word counts."""
        if isinstance(data, dict):
            return ", ".join(f"{k}: {v}" for k, v in data.items())
        return str(data)

    def _chat_with_gpt(self, message, sender="user"):
        """Chat with GPT."""
        if not self.gpt_service:
            return "Sorry, AI chat is not available. Please configure OPENAI_API_KEY."

        try:
            # Clean the message by removing bot name mentions
            clean_message = message
            if clean_message.lower().startswith(self.bot_name.lower()):
                # Remove bot name and common separators
                clean_message = clean_message[
                    len(self.bot_name) :  # noqa E203 - Black formatting
                ].lstrip(":, ")

            # Get response from GPT service
            response = self.gpt_service.chat(clean_message, sender)
            return response

        except Exception as e:
            self.logger.error(f"Error in GPT chat: {e}")
            return "Sorry, I had trouble processing your message."

    def _wrap_irc_message_utf8_bytes(
        self, message, reply_target=None, max_lines=10, placeholder="..."
    ):
        """Wrap a message into IRC-safe UTF-8 lines by byte length.

        - IRC protocol limits a message line to 512 bytes total, including prefix.
          We keep content around ~450 bytes to be safe across networks.
        - Preserves existing newlines by wrapping each paragraph separately.
        - Tries to break on spaces; falls back to hard byte-split if needed.
        - Caps the number of output lines to max_lines and appends a placeholder to the last line if truncated.
        """
        if message is None:
            return []

        safe_byte_limit = 425  # conservative payload limit per line
        paragraphs = str(message).split("\n")
        out_lines: list[str] = []

        def flush_chunk(chunk_words: list[str]):
            if not chunk_words:
                return
            out_lines.append(" ".join(chunk_words))

        for para in paragraphs:
            # If paragraph already short, keep it
            if not para:
                out_lines.append("")
                continue

            words = para.split(" ")
            current_words: list[str] = []
            current_bytes = 0

            for w in words:
                # Compute tentative length with a space if needed
                sep = 1 if current_words else 0
                tentative = (len(w.encode("utf-8"))) + sep
                if current_bytes + tentative <= safe_byte_limit:
                    current_words.append(w)
                    current_bytes += tentative
                else:
                    # Flush current as a line
                    flush_chunk(current_words)
                    if len(out_lines) >= max_lines:
                        break
                    # If single word longer than limit, hard split by bytes
                    if len(w.encode("utf-8")) > safe_byte_limit:
                        b = w.encode("utf-8")
                        start = 0
                        while start < len(b):
                            remaining_lines = max_lines - len(out_lines)
                            if remaining_lines <= 0:
                                break
                            take = min(safe_byte_limit, len(b) - start)
                            # Ensure we don't cut a multibyte char: backtrack within current chunk until valid utf-8
                            while take > 0:
                                try:
                                    chunk = b[
                                        start : start  # noqa E203 - Black formatting
                                        + take
                                    ].decode("utf-8")
                                    break
                                except UnicodeDecodeError:
                                    take -= 1
                            if take <= 0:
                                # Fallback: skip problematic byte (shouldn't happen often)
                                start += 1
                                continue
                            out_lines.append(chunk)
                            start += take
                            if len(out_lines) >= max_lines:
                                break
                        current_words = []
                        current_bytes = 0
                    else:
                        # Start new line with this word
                        current_words = [w]
                        current_bytes = len(w.encode("utf-8"))
            # Flush any remaining words for this paragraph
            if len(out_lines) < max_lines and current_words:
                flush_chunk(current_words)

            if len(out_lines) >= max_lines:
                break

        # If we exceeded line cap, trim and append placeholder
        if len(out_lines) > max_lines:
            out_lines = out_lines[:max_lines]
        if len(out_lines) == max_lines:
            # Append placeholder to last line conservatively by bytes
            last = out_lines[-1]
            last_bytes = last.encode("utf-8")
            ph_bytes = placeholder.encode("utf-8")
            if len(last_bytes) + len(ph_bytes) > safe_byte_limit:
                # Trim to fit placeholder
                trim_to = safe_byte_limit - len(ph_bytes)
                # Backtrack to valid utf-8 boundary
                while trim_to > 0:
                    try:
                        last = last_bytes[:trim_to].decode("utf-8")
                        break
                    except UnicodeDecodeError:
                        trim_to -= 1
                out_lines[-1] = last + placeholder
            else:
                out_lines[-1] = last + placeholder

        return out_lines

    def _log(self, message, level="INFO"):
        """Log a message."""
        self.logger.log(message, level)

    def _fetch_title(self, irc, target, text):
        """Fetch and display URL titles (excluding blacklisted URLs and file types)."""
        import re

        import requests

        # Try to import BeautifulSoup, but fall back to regex if unavailable
        try:
            from bs4 import BeautifulSoup  # type: ignore
        except Exception:
            BeautifulSoup = None  # type: ignore

        # Find URLs in the text
        urls = re.findall(
            r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
            text,
        )

        for url in urls:
            # Skip blacklisted URLs
            if self._is_url_blacklisted(url):
                continue

            try:
                response = requests.get(
                    url, timeout=10, headers={"User-Agent": "Mozilla/5.0"}
                )
                if response.status_code == 200:
                    # Check content type before processing
                    content_type = response.headers.get("Content-Type", "").lower()
                    if (
                        "text/html" not in content_type
                        and "application/xhtml+xml" not in content_type
                    ):
                        self.logger.debug(f"Skipping non-HTML content: {content_type}")
                        continue

                    cleaned_title = None
                    if BeautifulSoup is not None:
                        try:
                            soup = BeautifulSoup(response.content, "html.parser")
                            title_tag = soup.find("title")
                            if title_tag and getattr(title_tag, "string", None):
                                cleaned_title = re.sub(
                                    r"\s+", " ", title_tag.string.strip()
                                )
                        except Exception:
                            cleaned_title = None

                    # Fallback: extract title with regex if bs4 is not available or failed
                    if not cleaned_title:
                        try:
                            # Decode bytes safely; ignore errors
                            text_content = (
                                response.content.decode("utf-8", errors="ignore")
                                if isinstance(response.content, (bytes, bytearray))
                                else str(response.content)
                            )
                            m = re.search(
                                r"<title[^>]*>(.*?)</title>",
                                text_content,
                                re.IGNORECASE | re.DOTALL,
                            )
                            if m:
                                cleaned_title = re.sub(r"\s+", " ", m.group(1).strip())
                        except Exception:
                            cleaned_title = None

                    if cleaned_title:
                        # Check if title is banned
                        if self._is_title_banned(cleaned_title):
                            self.logger.debug(f"Skipping banned title: {cleaned_title}")
                            continue

                        # Send title to IRC if we have a proper server object
                        if hasattr(irc, "send_message"):
                            self._send_response(irc, target, f"📄 {cleaned_title}")
                        else:
                            self.logger.info(f"Title: {cleaned_title}")
            except Exception as e:
                self.logger.error(f"Error fetching title for {url}: {e}")

    def _is_youtube_url(self, url: str) -> bool:
        """Check if a URL is a YouTube URL."""
        import re

        youtube_patterns = [
            r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([\w\-_]*)",  # Allow empty video ID
            r"(?:https?://)?(?:www\.)?youtu\.be/([\w\-_]+)",
            r"(?:https?://)?(?:www\.)?youtube\.com/embed/([\w\-_]*)",
            r"(?:https?://)?(?:www\.)?youtube\.com/v/([\w\-_]*)",
            r"(?:https?://)?(?:m\.)?youtube\.com/watch\?v=([\w\-_]*)",
            r"(?:https?://)?(?:music\.)?youtube\.com/watch\?v=([\w\-_]*)",
            r"(?:https?://)?(?:www\.)?youtube\.com/shorts/([\w\-_]+)",  # YouTube Shorts
        ]

        for pattern in youtube_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return True
        return False

    def _is_url_blacklisted(self, url: str) -> bool:
        """Check if a URL should be blacklisted from title fetching."""
        # Skip YouTube URLs as they are already handled by the YouTube service
        if self._is_youtube_url(url):
            return True

        # Get blacklisted domains from environment
        blacklisted_domains = os.getenv(
            "TITLE_BLACKLIST_DOMAINS",
            "youtube.com,youtu.be,facebook.com,fb.com,x.com,twitter.com,instagram.com,tiktok.com,discord.com,reddit.com,imgur.com",
        ).split(",")

        # Get blacklisted extensions from environment
        blacklisted_extensions = os.getenv(
            "TITLE_BLACKLIST_EXTENSIONS",
            ".jpg,.jpeg,.png,.gif,.mp4,.webm,.pdf,.zip,.rar,.mp3,.wav,.flac",
        ).split(",")

        url_lower = url.lower()

        # Check domains
        for domain in blacklisted_domains:
            domain = domain.strip()
            if domain and domain in url_lower:
                self.logger.debug(
                    f"Skipping URL with blacklisted domain '{domain}': {url}"
                )
                return True

        # Check file extensions
        for ext in blacklisted_extensions:
            ext = ext.strip()
            if ext and url_lower.endswith(ext):
                self.logger.debug(
                    f"Skipping URL with blacklisted extension '{ext}': {url}"
                )
                return True

        return False

    def _is_title_banned(self, title: str) -> bool:
        """Check if a title should be banned from being displayed."""
        # Get banned titles from environment
        banned_titles = os.getenv(
            "TITLE_BANNED_TEXTS",
            "Bevor Sie zu Google Maps weitergehen;Just a moment...;403 Forbidden;404 Not Found;Access Denied",
        ).split(";")

        title_lower = title.lower().strip()

        # Check if title contains any banned text
        for banned_text in banned_titles:
            banned_text = banned_text.strip().lower()
            if banned_text and banned_text in title_lower:
                self.logger.debug(
                    f"Skipping title with banned text '{banned_text}': {title}"
                )
                return True

        return False

    def _get_subscriptions_module(self):
        """Get subscriptions module."""
        try:
            import subscriptions

            return subscriptions
        except ImportError:
            # Return a mock object with basic functionality
            class MockSubscriptions:
                def get_subscribers(self, topic):
                    return []

            return MockSubscriptions()

    def _get_drink_words(self):
        """Get drink words dictionary."""
        return {
            "krak": 0,
            "kr1k": 0,
            "kr0k": 0,
            "narsk": 0,
            "parsk": 0,
            "tlup": 0,
            "marsk": 0,
            "tsup": 0,
            "plop": 0,
            "tsirp": 0,
        }

    def _update_env_file(self, key: str, value: str) -> bool:
        """Update a key-value pair in the .env file."""
        env_file = ".env"
        if not os.path.exists(env_file):
            self.logger.warning("No .env file found, cannot persist tamagotchi setting")
            return False

        try:
            # Read current .env file
            with open(env_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Find and update the key, or add it if not found
            key_found = False
            for i, line in enumerate(lines):
                # Check if this line contains our key (handle comments and whitespace)
                stripped = line.strip()
                if stripped.startswith(f"{key}=") or stripped.startswith(f"#{key}="):
                    # Replace the line with the new value
                    lines[i] = f"{key}={value}\n"
                    key_found = True
                    break

            # If key wasn't found, add it
            if not key_found:
                lines.append(f"{key}={value}\n")

            # Write back to .env file
            with open(env_file, "w", encoding="utf-8") as f:
                f.writelines(lines)

            # Update environment variable for current session
            os.environ[key] = value

            return True

        except IOError as e:
            self.logger.error(f"Could not update .env file: {e}")
            return False

    def toggle_tamagotchi(self, server, target, sender):
        """Toggle tamagotchi responses on/off with .env file persistence."""
        self.tamagotchi_enabled = not self.tamagotchi_enabled

        # Save the new state to .env file
        new_value = "true" if self.tamagotchi_enabled else "false"
        success = self._update_env_file("TAMAGOTCHI_ENABLED", new_value)

        status = "enabled" if self.tamagotchi_enabled else "disabled"
        emoji = "🐣" if self.tamagotchi_enabled else "💤"

        if success:
            response = f"{emoji} Tamagotchi responses are now {status}."
        else:
            response = f"{emoji} Tamagotchi responses are now {status} (session only - .env update failed)."

        self._send_response(server, target, response)

        # Log the change
        self.logger.info(f"{sender} toggled tamagotchi to {status}", server.config.name)

        return response

    def _handle_youtube_urls(self, context: Dict[str, Any]):
        """Handle YouTube URLs by fetching and displaying video information."""
        server = context["server"]
        target = context["target"]
        text = context["text"]

        # Only process in channels, not private messages
        if not target.startswith("#"):
            return

        try:
            video_id = self.youtube_service.extract_video_id(text)
            if video_id:
                video_data = self.youtube_service.get_video_info(video_id)
                message = self.youtube_service.format_video_info_message(video_data)
                self._send_response(server, target, message)
        except Exception as e:
            self.logger.error(f"Error handling YouTube URL: {e}")

    def _send_youtube_info(self, irc, channel, query_or_url):
        """Send YouTube video info or search results."""
        if not self.youtube_service:
            response = (
                "YouTube service not available. Please configure YOUTUBE_API_KEY."
            )
            self._send_response(irc, channel, response)
            return

        try:
            # Check if it's a URL or search query
            video_id = self.youtube_service.extract_video_id(query_or_url)

            if video_id:
                # It's a URL, get video info
                video_data = self.youtube_service.get_video_info(video_id)
                response = self.youtube_service.format_video_info_message(video_data)
            else:
                # It's a search query
                search_data = self.youtube_service.search_videos(
                    query_or_url, max_results=3
                )
                response = self.youtube_service.format_search_results_message(
                    search_data
                )

            self._send_response(irc, channel, response)

        except Exception as e:
            error_msg = f"🎥 Error with YouTube request: {str(e)}"
            self.logger.error(f"YouTube error: {e}")
            self._send_response(irc, channel, error_msg)

    def _send_crypto_price(self, irc, channel, text_or_parts):
        """Send cryptocurrency price information."""
        try:
            # Handle both string and list inputs for compatibility
            if isinstance(text_or_parts, list):
                # Called from IRC command with parts list
                args = text_or_parts[1:] if len(text_or_parts) > 1 else []
                if len(args) == 0:
                    self._send_response(
                        irc,
                        channel,
                        "💸 Usage: !crypto <coin> [currency]. Example: !crypto btc eur",
                    )
                    return
                coin = args[0]
                currency = args[1] if len(args) > 1 else "eur"
            else:
                # Called with string (e.g., from tests or console)
                args = text_or_parts.split() if text_or_parts else []
                if len(args) == 0:
                    self._send_response(
                        irc,
                        channel,
                        "💸 Usage: !crypto <coin> [currency]. Example: !crypto btc eur",
                    )
                    return
                coin = args[0]
                currency = args[1] if len(args) > 1 else "eur"

            # Get cryptocurrency price
            price_data = self.crypto_service.get_crypto_price(coin, currency)
            response = self.crypto_service.format_price_message(price_data)

            self._send_response(irc, channel, response)

        except Exception as e:
            error_msg = f"💸 Error getting crypto price: {str(e)}"
            self.logger.error(f"Crypto price error: {e}")
            self._send_response(irc, channel, error_msg)

    def _check_nanoleet_achievement(self, context: Dict[str, Any]):
        """Check for nanoleet achievements in message timestamp."""
        server = context["server"]
        target = context["target"]
        sender = context["sender"]
        user_message = context["text"]

        # Only check in channels, not private messages
        if not target.startswith("#"):
            return

        try:
            # 🎯 CRITICAL: Get timestamp with MAXIMUM precision immediately upon message processing
            # This is the most accurate timestamp possible for when the message was processed
            timestamp = self.nanoleet_detector.get_timestamp_with_nanoseconds()

            # Check for leet achievement, including the user's message text
            result = self.nanoleet_detector.check_message_for_leet(
                sender, timestamp, user_message
            )

            if result:
                achievement_message, achievement_level = result
                if achievement_level != "leet":  # Filter out regular leet messages
                    # Send achievement message to the channel immediately
                    self._send_response(server, target, achievement_message)

                # Log the achievement with high precision
                self.logger.info(
                    f"Leet achievement: {achievement_level} for {sender} in {target} at {timestamp} - message: {user_message}"
                )

        except Exception as e:
            self.logger.error(f"Error checking nanoleet achievement: {e}")
