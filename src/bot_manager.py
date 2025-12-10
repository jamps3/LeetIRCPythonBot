"""
Bot Manager for Multiple IRC Servers

This module provides the BotManager class that orchestrates multiple IRC server
connections and integrates all bot functionality across servers.
"""

import datetime
import json
import os
import re
import threading
import time
from typing import Any, Dict, List, Optional

import requests

import logger
from config import get_api_key, get_config, get_server_configs, load_env_file
from leet_detector import create_leet_detector
from lemmatizer import Lemmatizer
from server import Server
from tamagotchi import TamagotchiBot
from word_tracking import DataManager, DrinkTracker, GeneralWords

# Optional service imports - handle gracefully if dependencies are missing
try:
    from services.crypto_service import create_crypto_service
except ImportError as e:
    logger.warning(f"Warning: Crypto service not available: {e}")
    create_crypto_service = None

try:
    from services.electricity_service import create_electricity_service
except ImportError as e:
    logger.warning(f"Electricity service not available: {e}")
    create_electricity_service = None

try:
    from services.fmi_warning_service import create_fmi_warning_service
except ImportError as e:
    logger.warning(f"FMI warning service not available: {e}")
    create_fmi_warning_service = None

try:
    from services.gpt_service import GPTService
except ImportError as e:
    logger.warning(f"GPT service not available: {e}")
    GPTService = None

try:
    from services.otiedote_json_service import create_otiedote_service
except ImportError as e:
    logger.warning(f"Otiedote service not available: {e}")
    create_otiedote_service = None

try:
    from services.weather_service import WeatherService
except ImportError as e:
    logger.warning(f"Warning: Weather service not available: {e}")
    WeatherService = None

try:
    from services.youtube_service import create_youtube_service
except ImportError as e:
    logger.warning(f"YouTube service not available: {e}")
    create_youtube_service = None

# Initialize X API client
try:
    from xdk import Client as XClient

    x_client_available = True
except ImportError as e:
    logger.warning(f"X API client not available: {e}")
    XClient = None
    x_client_available = False


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

    def __init__(self, bot_name: str, console_mode: bool = False):
        """
        Initialize the bot manager.

        Args:
            bot_name: The nickname for the bot across all servers
            console_mode: Whether to use console mode (with readline) or TUI mode
        """
        self.bot_name = bot_name
        self.console_mode = console_mode
        self.servers: Dict[str, Server] = {}
        self.server_threads: Dict[str, threading.Thread] = {}
        self.stop_event = threading.Event()
        # Connection control - default to unconnected
        self.auto_connect = os.getenv("AUTO_CONNECT", "false").lower() in (
            "true",
            "1",
            "yes",
            "on",
        )
        self.connected = False
        # Channel management
        self.active_channel = None  # Currently active channel for messaging
        self.active_server = None  # Server for the active channel
        self.joined_channels = {}  # Dict of server_name -> set of joined channels
        # Read default quit message from environment or use fallback
        self.quit_message = os.getenv("QUIT_MESSAGE", "Disconnecting")
        self.logger = logger.get_logger("BotManager")

        # Only import readline and set up console features when in console mode
        if self.console_mode:
            # Try to import readline only when needed
            try:
                import readline

                self.readline = readline
                self.readline_available = True
                self.logger.debug("Readline imported successfully for console mode")
            except ImportError:
                self.logger.warning(
                    "readline module not available, console history disabled"
                )

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

                self.readline = DummyReadline()
                self.readline_available = False

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
        else:
            self.logger.debug("TUI mode enabled - skipping readline setup")

        # Load USE_NOTICES setting
        use_notices_setting = os.getenv("USE_NOTICES", "false").lower()
        self.use_notices = use_notices_setting in ("true", "1", "yes", "on")
        if self.use_notices:
            self.logger.info(
                "📢 Using IRC NOTICEs for channel responses",
                fallback_text="Using IRC NOTICEs for channel responses",
            )
        else:
            self.logger.info(
                "💬 Using regular PRIVMSGs for channel responses",
                fallback_text="Using regular PRIVMSGs for channel responses",
            )

        # Load TAMAGOTCHI_ENABLED setting from .env file
        tamagotchi_setting = os.getenv("TAMAGOTCHI_ENABLED", "true").lower()
        self.tamagotchi_enabled = tamagotchi_setting in ("true", "1", "yes", "on")
        if self.tamagotchi_enabled:
            self.logger.info(
                "🐣 Tamagotchi responses enabled",
                fallback_text="Tamagotchi responses enabled",
            )
        else:
            self.logger.info(
                "🐣 Tamagotchi responses disabled",
                fallback_text="Tamagotchi responses disabled",
            )

        # Initialize bot components
        config = get_config()  # Load config after environment setup
        self.logger.debug("Initializing data manager...")
        self.data_manager = DataManager(state_file=config.state_file)
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
                self.logger.info(
                    "🌤️ Weather service initialized",
                    fallback_text="Weather service initialized",
                )
            else:
                self.logger.warning(
                    "⚠️  No weather API key found. Weather commands will not work.",
                    fallback_text="No weather API key found. Weather commands will not work.",
                )
                self.weather_service = None
        else:
            self.weather_service = None

        # Initialize GPT service
        if GPTService is not None:
            openai_api_key = get_api_key("OPENAI_API_KEY")
            history_file = os.getenv("HISTORY_FILE", "data/conversation_history.json")
            history_limit = int(os.getenv("GPT_HISTORY_LIMIT", "100"))
            if openai_api_key:
                self.gpt_service = GPTService(
                    openai_api_key, history_file, history_limit
                )
                self.logger.info(
                    f"🤖 GPT chat service initialized (history limit: {history_limit} messages).",
                    fallback_text=f"GPT chat service initialized (history limit: {history_limit} messages).",
                )
                # Log the OpenAI model in use at startup
                self.logger.info(
                    f"🧠 OpenAI model: {self.gpt_service.model}",
                    fallback_text=f"OpenAI model: {self.gpt_service.model}",
                )
            else:
                self.logger.warning(
                    "⚠️  No OpenAI API key found. AI chat will not work.",
                    fallback_text="No OpenAI API key found. AI chat will not work.",
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
                self.logger.info(
                    "⚡ Electricity price service initialized.",
                    fallback_text="Electricity price service initialized.",
                )
            else:
                self.logger.warning(
                    "⚠️  No electricity API key found. Electricity price commands will not work.",
                    fallback_text="No electricity API key found. Electricity price commands will not work.",
                )
                self.electricity_service = None
        else:
            self.electricity_service = None

        # Initialize YouTube service
        if create_youtube_service is not None:
            youtube_api_key = get_api_key("YOUTUBE_API_KEY")
            if youtube_api_key:
                self.youtube_service = create_youtube_service(youtube_api_key)
                self.logger.info(
                    "▶️ YouTube service initialized.",
                    fallback_text="YouTube service initialized.",
                )
            else:
                self.logger.warning(
                    "⚠️  No YouTube API key found. YouTube commands will not work.",
                    fallback_text="No YouTube API key found. YouTube commands will not work.",
                )
                self.youtube_service = None
        else:
            self.youtube_service = None

        # Initialize crypto service
        if create_crypto_service is not None:
            self.crypto_service = create_crypto_service()
            self.logger.info(
                "🪙 Crypto service initialized (using CoinGecko API).",
                fallback_text="Crypto service initialized (using CoinGecko API).",
            )
        else:
            self.crypto_service = None

        # Initialize nanoleet detector
        self.leet_detector = create_leet_detector()
        self.logger.info(
            "🎯 Leet detector initialized.",
            fallback_text="Leet detector initialized.",
        )

        # Initialize FMI warning service
        if create_fmi_warning_service is not None:
            self.fmi_warning_service = create_fmi_warning_service(
                callback=self._handle_fmi_warnings,
                state_file=config.state_file,
            )
            self.logger.info(
                "⚠️ FMI warning service initialized.",
                fallback_text="FMI warning service initialized.",
            )
        else:
            self.fmi_warning_service = None

        # Storage for the latest Otiedote release info
        self.latest_otiedote: Optional[dict] = None

        # Initialize Otiedote service
        if create_otiedote_service is not None:
            self.otiedote_service = create_otiedote_service(
                callback=self._handle_otiedote_release,
                state_file=config.state_file,
            )
            self.logger.info(
                "📢 Otiedote monitoring service initialized.",
                fallback_text="Otiedote monitoring service initialized.",
            )
        else:
            self.otiedote_service = None

        # Initialize lemmatizer with graceful fallback
        self.logger.debug("Initializing lemmatizer...")
        try:
            self.lemmatizer = Lemmatizer()
            self.logger.info(
                "🔤 Lemmatizer component initialized.",
                fallback_text="Lemmatizer component initialized.",
            )
        except Exception as e:
            self.logger.warning(
                f"Could not initialize lemmatizer: {e}",
                fallback_text=f"Could not initialize lemmatizer: {e}",
            )
            self.lemmatizer = None

        # Initialize X API queue for rate limiting (1 read per 5 minutes)
        self.x_api_queue = []  # List of (irc, target, url) tuples
        self.x_api_queue_lock = threading.Lock()
        self.x_api_last_request_time = 0
        self.x_api_rate_limit_seconds = 300  # 5 minutes = 300 seconds
        self.x_api_queue_thread = None

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
            self.readline.set_history_length(1000)

            # Try to read existing history
            try:
                self.readline.read_history_file(history_file)
                self.logger.debug(f"Loaded command history from {history_file}")
            except FileNotFoundError:
                # History file doesn't exist yet, that's fine
                pass
            except Exception as e:
                self.logger.warning(f"Could not load command history: {e}")

            # Configure readline for better editing (Linux/Unix compatible)
            if self.readline_available:
                try:
                    # Enable tab completion
                    self.readline.parse_and_bind("tab: complete")
                    # Set editing mode to emacs (supports arrow keys)
                    self.readline.parse_and_bind("set editing-mode emacs")
                    # Enable arrow key navigation
                    self.readline.parse_and_bind("\\C-p: previous-history")  # Up arrow
                    self.readline.parse_and_bind("\\C-n: next-history")  # Down arrow
                    self.readline.parse_and_bind("\\C-b: backward-char")  # Left arrow
                    self.readline.parse_and_bind("\\C-f: forward-char")  # Right arrow
                    # Enable better line editing
                    self.readline.parse_and_bind("\\C-a: beginning-of-line")  # Ctrl+A
                    self.readline.parse_and_bind("\\C-e: end-of-line")  # Ctrl+E
                    self.readline.parse_and_bind("\\C-k: kill-line")  # Ctrl+K
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

    def _setup_console_output_protection(self):
        """Set up console output protection to prevent interference with input prompts."""
        try:
            # Initialize the input active flag for output protection
            self._input_active = False
            self.logger.debug("Console output protection initialized")
        except Exception as e:
            self.logger.warning(f"Could not set up console output protection: {e}")

    def _save_command_history(self):
        """Save command history to file (console mode only)."""
        if self.console_mode and hasattr(self, "_history_file") and self._history_file:
            try:
                self.readline.write_history_file(self._history_file)
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

            # Register part callback
            server.register_callback("part", self._handle_part)

            # Register quit callback
            server.register_callback("quit", self._handle_quit)

            # Register numeric callback for handling IRC numeric responses
            server.register_callback("numeric", self._handle_numeric)

            self.logger.info(f"Registered callbacks for server: {server_name}")

            # Initialize pending ops data structure for each server
            if not hasattr(self, "_pending_ops"):
                self._pending_ops = {}
            if server_name not in self._pending_ops:
                self._pending_ops[server_name] = {}

    def _handle_notice(
        self, server: Server, sender: str, ident_host: str, target: str, text: str
    ):
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
                "ident_host": ident_host,
                "target": target,
                "text": text,
                "is_private": not target.startswith("#"),
                "bot_name": self.bot_name,
            }

            # Process leet winners summary lines (first/last/multileet)
            try:
                self._process_leet_winner_summary(context)
            except Exception as e:
                self.logger.warning(f"Error processing leet winners summary: {e}")

            # Process ekavika winners summary lines (vika/eka winners)
            try:
                self._process_ekavika_winner_summary(context)
            except Exception as e:
                self.logger.warning(f"Error processing ekavika winners summary: {e}")

        except Exception as e:
            self.logger.error(f"Error handling notice from {server.config.name}: {e}")

    async def _handle_message(
        self, server: Server, sender: str, ident_host: str, target: str, text: str
    ):
        """
        Handle incoming messages from any server.

        Args:
            server: The Server instance that received the message
            sender: The nickname who sent the message
            ident_host: The ident@host of the sender
            target: The target (channel or bot's nick)
            text: The message content
        """
        try:
            # Create context for the message
            context = {
                "server": server,
                "server_name": server.config.name,
                "sender": sender,
                "ident_host": ident_host,
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
            await self._process_commands(context)

        except Exception as e:
            self.logger.error(f"Error handling message from {server.config.name}: {e}")

    def _handle_join(self, server: Server, sender: str, ident_host: str, channel: str):
        """Handle user join events."""
        server_name = server.config.name

        # Track when the bot itself joins a channel
        if sender.lower() == self.bot_name.lower():
            # Initialize joined channels for this server if needed
            if server_name not in self.joined_channels:
                self.joined_channels[server_name] = set()

            # Add channel to joined channels tracking
            self.joined_channels[server_name].add(channel)

            # Set as active channel if no active channel is set
            if not self.active_channel or not self.active_server:
                self.active_channel = channel
                self.active_server = server_name
            self.logger.info(f"Bot joined {channel} on {server_name}")
        else:
            # Track other user activity
            self.logger.server(f"{sender} joined {channel}", server_name)

    def _handle_part(self, server: Server, sender: str, channel: str, ident_host: str):
        """Handle user part events."""
        # Track user activity
        server_name = server.config.name
        self.logger.server(f"{sender} left {channel}", server_name)

    def _handle_quit(self, server: Server, sender: str, ident_host: str):
        """Handle user quit events."""
        # Track user activity
        server_name = server.config.name
        self.logger.server(f"{sender} quit", server_name)

    def _track_words(self, context: Dict[str, Any]):
        """Track words for statistics and drink tracking."""
        server_name = context["server_name"]
        sender = context["sender"]
        text = context["text"]
        target = context["target"]

        # Only track in channels, not private messages
        if not target.startswith("#"):
            return

        # Skip tracking if this is a command (starts with !)
        if text.strip().startswith("!"):
            return

        # Track drink words and get any drink word detections
        drink_words_found = self.drink_tracker.process_message(
            server=server_name, nick=sender, text=text
        )

        # Track general words
        self.general_words.process_message(
            server=server_name, nick=sender, text=text, target=target
        )

        # Check kraksdebug configuration for notifications
        kraksdebug_config = self.data_manager.load_kraksdebug_state()

        # Send drink word notifications to configured channels
        if drink_words_found and kraksdebug_config.get("channels"):
            server = context["server"]
            for channel in kraksdebug_config["channels"]:
                # Only send to channels that exist on this server
                if (
                    server_name in self.joined_channels
                    and channel in self.joined_channels[server_name]
                ):
                    notification = (
                        f"🐧 {sender} said drink words: {', '.join(drink_words_found)}"
                    )
                    self._send_response(server, channel, notification)

        # Send drink word notifications as notices to the sender
        if drink_words_found and kraksdebug_config.get("nick_notices", False):
            server = context["server"]
            notification = f"🐧 You said drink words: {', '.join(drink_words_found)}"
            # Send as notice to the sender
            try:
                if self.use_notices:
                    server.send_notice(sender, notification)
                else:
                    server.send_message(sender, notification)
            except Exception as e:
                self.logger.warning(
                    f"Failed to send drink word notice to {sender}: {e}"
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

    async def _process_commands(self, context: Dict[str, Any]):
        """Process IRC commands and bot interactions."""
        server = context["server"]
        sender = context["sender"]
        ident_host = context["ident_host"]
        target = context["target"]
        text = context["text"]

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
                irc or server, target or context["target"], msg
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
            "log": self.logger,
            "fetch_title": self._fetch_title,
            "subscriptions": self._get_subscriptions_module(),
            "DRINK_WORDS": self._get_drink_words(),
            "get_latency_start": lambda: getattr(self, "_latency_start", 0),
            "toggle_tamagotchi": lambda srv, tgt, snd: self.toggle_tamagotchi(
                srv, tgt, snd
            ),
            "stop_event": self.stop_event,  # Allow IRC commands to trigger shutdown
            "set_quit_message": self.set_quit_message,  # Allow setting custom quit message
            "set_openai_model": self.set_openai_model,  # Allow changing OpenAI model at runtime
            "bot_manager": self,  # Reference to the bot manager itself (needed for commands)
        }

        # Create a mock IRC message format for commands.py compatibility
        # mock_message = f":{sender}!{sender}@host.com PRIVMSG {target} :{text}"
        # Build a proper IRC line with all info
        message = f":{sender}!{ident_host} PRIVMSG {target.lower()} :{text}"
        self.logger.debug(f"Constructed IRC message: {message}")

        try:
            self.logger.debug(
                f"Processing command from {sender} on {server.config.name}: {text}"
            )
            from command_loader import process_irc_command

            await process_irc_command(
                text,  # message body (!s, !np, etc)
                sender,  # nick
                target,  # channel or private target
                server,  # connection instance
                ident_host,  # ident@host
                bot_functions,  # function table
            )

            self.logger.debug(f"Finished processing command from {sender}")
        except Exception as e:
            self.logger.error(f"Error @ _process_commands: {e}")

    def start(self):
        """Start all servers and bot functionality."""
        if not self.load_configurations():
            return False

        self.register_callbacks()

        # Start monitoring services
        if self.fmi_warning_service is not None:
            self.fmi_warning_service.start()
        if self.otiedote_service is not None:
            # Start Otiedote service in background thread to avoid blocking startup
            def start_otiedote_background():
                try:
                    import asyncio

                    # Create a new event loop in this thread
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        # Start the service
                        new_loop.run_until_complete(self.otiedote_service.start())
                        # Keep the loop running to handle async operations
                        # The monitor loop will run until self.running is False
                        new_loop.run_forever()
                    except Exception as e:
                        self.logger.error(
                            f"Otiedote service background loop error: {e}"
                        )
                    finally:
                        try:
                            # Stop the service
                            if self.otiedote_service.running:
                                new_loop.run_until_complete(
                                    self.otiedote_service.stop()
                                )
                            # Cancel all remaining tasks
                            pending = asyncio.all_tasks(new_loop)
                            for task in pending:
                                task.cancel()
                            # Wait for tasks to complete cancellation
                            if pending:
                                new_loop.run_until_complete(
                                    asyncio.gather(*pending, return_exceptions=True)
                                )
                        except Exception:
                            pass
                        finally:
                            new_loop.close()
                            asyncio.set_event_loop(None)
                except Exception as e:
                    self.logger.error(
                        f"Could not start Otiedote service in background: {e}"
                    )

            otiedote_thread = threading.Thread(
                target=start_otiedote_background,
                daemon=True,
                name="OtiedoteService",
            )
            otiedote_thread.start()
            self.logger.debug("Otiedote service started in background thread")
            # Store reference to thread for potential cleanup
            self.otiedote_thread = otiedote_thread

        # Start console listener thread only in console mode
        if self.console_mode:
            self.console_thread = threading.Thread(
                target=self._listen_for_console_commands,
                daemon=True,
                name="Console-Listener",
            )
            self.console_thread.start()
            self.logger.debug("Started console input listener")
        else:
            self.logger.debug("TUI mode - console input listener not started")

        # Only auto-connect if explicitly enabled
        if self.auto_connect:
            self.connect_to_servers()
            self.logger.info(
                f"Bot manager started with {len(self.servers)} servers (auto-connected)"
            )
        else:
            self.logger.info(
                f"Bot manager started with {len(self.servers)} servers configured (not connected)"
            )
            self.logger.info(
                "🔌 Use !connect to connect to servers",
                fallback_text="Use !connect to connect to servers",
            )
        # Show console-specific instructions only in console mode
        if self.console_mode:
            self.logger.log("-" * 60)
            self.logger.log(
                "💬 Console is ready! Type commands (!help) or chat messages.",
                fallback_text="[CHAT] Console is ready! Type commands (!help) or chat messages.",
            )
            self.logger.log(
                "🔧 Commands: !help, !version, !s <location>, !ping, !connect, !disconnect, !status, !channels, etc.",
                fallback_text="[CONFIG] Commands: !help, !version, !s <location>, !ping, !connect, !disconnect, !status, !channels, etc.",
            )
            self.logger.log(
                "💬 Channels: #channel to join/part, send messages directly to active channel",
                "INFO",
                fallback_text="[CHANNEL] Channels: #channel to join/part, send messages directly to active channel",
            )
            self.logger.log(
                "🤖 AI Chat: -message to chat with AI",
                "INFO",
                fallback_text="[AI] AI Chat: -message to chat with AI",
            )
            self.logger.log(
                "🛑 Exit: Type 'quit' or 'exit' or press Ctrl+C",
                "INFO",
                fallback_text="[STOP] Exit: Type 'quit' or 'exit' or press Ctrl+C",
            )
            self.logger.log("-" * 60)
        else:
            self.logger.log("Bot manager started in TUI mode")
        return True

    def connect_to_servers(self, server_names: List[str] = None):
        """Connect to configured servers or specific servers by name.

        Args:
            server_names: Optional list of server names to connect to. If None, connects to all configured servers.
        """
        servers_to_connect = server_names or list(self.servers.keys())

        for server_name in servers_to_connect:
            if server_name not in self.servers:
                self.logger.warning(f"Server {server_name} not found in configurations")
                continue

            if (
                server_name in self.server_threads
                and self.server_threads[server_name].is_alive()
            ):
                self.logger.info(f"Server {server_name} is already connected")
                continue

            server = self.servers[server_name]
            thread = threading.Thread(
                target=server.start, name=f"Server-{server_name}", daemon=False
            )
            thread.start()
            self.server_threads[server_name] = thread
            self.logger.info(f"Started server thread for {server_name}")

        if servers_to_connect:
            self.connected = True

    def disconnect_from_servers(
        self, server_names: List[str] = None, quit_message: str = None
    ):
        """Disconnect from servers.

        Args:
            server_names: Optional list of server names to disconnect from. If None, disconnects from all servers.
            quit_message: Optional custom quit message.
        """
        servers_to_disconnect = server_names or list(self.servers.keys())
        quit_msg = quit_message or self.quit_message

        for server_name in servers_to_disconnect:
            if server_name not in self.servers:
                self.logger.warning(f"Server {server_name} not found")
                continue

            server = self.servers[server_name]
            if server.connected:
                try:
                    server.quit(quit_msg)
                    self.logger.info(f"Sent quit command to {server_name}")
                except Exception as e:
                    self.logger.error(f"Error quitting server {server_name}: {e}")

            # Wait for thread to finish
            if server_name in self.server_threads:
                thread = self.server_threads[server_name]
                thread.join(timeout=5.0)
                if thread.is_alive():
                    self.logger.warning(
                        f"Server thread {server_name} did not finish cleanly"
                    )
                del self.server_threads[server_name]

        # Update connected state
        if not any(thread.is_alive() for thread in self.server_threads.values()):
            self.connected = False

    def add_server_and_connect(
        self,
        name: str,
        host: str,
        port: int = 6667,
        channels: List[str] = None,
        keys: List[str] = None,
        use_tls: bool = False,
    ):
        """Add a new server configuration and connect to it.

        Args:
            name: Server name
            host: Server hostname
            port: Server port (default 6667)
            channels: List of channels to join
            keys: List of channel keys
            use_tls: Whether to use TLS/SSL
        """
        from server import Server, ServerConfig

        # Create server configuration
        config = ServerConfig(
            host=host,
            port=port,
            channels=channels or [],
            keys=keys or [],
            tls=use_tls,
            name=name,
        )

        # Create and register server
        server = Server(config, self.bot_name, self.stop_event)
        server.quit_message = self.quit_message
        self.servers[name] = server

        # Register callbacks for the new server
        server.register_callback("message", self._handle_message)
        server.register_callback("notice", self._handle_notice)
        server.register_callback("join", self._handle_join)
        server.register_callback("part", self._handle_part)
        server.register_callback("quit", self._handle_quit)

        # Connect to the new server
        self.connect_to_servers([name])

        self.logger.info(f"Added and connected to new server: {name} ({host}:{port})")
        return True

    def _handle_fmi_warnings(self, warnings: List[str]):
        """Handle new FMI weather warnings.

        Delays announcements until server is connected and channels defined in .env are joined.
        """
        # Check if we're connected and have joined channels
        if not self.connected:
            self.logger.debug("Delaying FMI warning announcement: server not connected")
            return

        # Check if we have joined any channels at all
        if not self.joined_channels:
            self.logger.debug("Delaying FMI warning announcement: no channels joined")
            return

        # Check if we have joined channels defined in .env configuration
        config = get_config()
        env_channels_joined = False
        for server_config in config.servers:
            server_name = server_config.name
            if server_name in self.joined_channels:
                # Check if any of the configured channels for this server are joined
                configured_channels = set(server_config.channels)
                joined_channels = self.joined_channels[server_name]
                if configured_channels.intersection(joined_channels):
                    env_channels_joined = True
                    break

        if not env_channels_joined:
            self.logger.debug(
                "Delaying FMI warning announcement: no .env configured channels joined"
            )
            return

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

    def _handle_otiedote_release(self, release: dict):
        """Handle new Otiedote press release.

        Uses the subscriptions system to deliver messages only to explicit
        onnettomuustiedotteet subscribers per server, with channel-specific filtering.

        Automatically broadcasts only title + URL from filtered releases to channels.
        Stores the full info for the !otiedote command to display description on-demand.

        Delays announcements until server is connected and channels defined in .env are joined.
        """
        self.logger.info(
            f"_handle_otiedote_release: Processing release #{release.get('id')} - {release.get('title')}"
        )

        # Check if we're connected and have joined channels
        if not self.connected:
            self.logger.debug(
                f"Delaying Otiedote announcement #{release.get('id', 'unknown')}: server not connected"
            )
            return

        # Check if we have joined any channels at all
        if not self.joined_channels:
            self.logger.debug(
                f"Delaying Otiedote announcement #{release.get('id', 'unknown')}: no channels joined"
            )
            return

        # Check if we have joined channels defined in .env configuration
        config = get_config()
        env_channels_joined = False
        for server_config in config.servers:
            server_name = server_config.name
            if server_name in self.joined_channels:
                # Check if any of the configured channels for this server are joined
                configured_channels = set(server_config.channels)
                joined_channels = self.joined_channels[server_name]
                if configured_channels.intersection(joined_channels):
                    env_channels_joined = True
                    break

        if not env_channels_joined:
            self.logger.debug(
                f"Delaying Otiedote announcement #{release.get('id', 'unknown')}: no .env configured channels joined"
            )
            return

        # Persist latest release info for on-demand access via !otiedote
        try:
            self.latest_otiedote = release
        except Exception:
            # Never fail the broadcast due to caching issues
            pass

        header_message = f"📢 {release['title']} | {release['url']}"

        # Get subscriptions module and subscribers for onnettomuustiedotteet
        subscriptions = self._get_subscriptions_module()
        subscribers = []
        try:
            subscribers = subscriptions.get_subscribers("onnettomuustiedotteet")
            self.logger.info(
                f"_handle_otiedote_release: Found {len(subscribers)} subscribers for onnettomuustiedotteet: {subscribers}"
            )
        except Exception as e:
            self.logger.error(f"Error getting onnettomuustiedotteet subscribers: {e}")
            return

        if not subscribers:
            self.logger.warning(
                "No subscribers for onnettomuustiedotteet, not broadcasting Otiedote release"
            )
            return

        # Load state for filters
        filters = {}
        try:
            state = self.data_manager.load_state()
            filters = state.get("otiedote", {}).get("filters", {})
            self.logger.info(f"_handle_otiedote_release: Loaded filters: {filters}")
        except Exception:
            filters = {}

        # Send to subscribed channels/users on their respective servers with filtering
        for subscriber_nick, server_name in subscribers:
            try:
                self.logger.info(
                    f"_handle_otiedote_release: Processing subscriber {subscriber_nick} on {server_name}"
                )
                server = self.servers.get(server_name)
                if not server:
                    self.logger.warning(
                        f"Server {server_name} not found for Otiedote subscriber {subscriber_nick}"
                    )
                    continue

                # Check if this channel has filters
                channel_filters = filters.get(subscriber_nick, [])
                self.logger.info(
                    f"_handle_otiedote_release: Channel {subscriber_nick} has filters: {channel_filters}"
                )
                should_send = True

                if channel_filters:
                    # Check if any filter matches
                    should_send = False
                    for filter_entry in channel_filters:
                        self.logger.info(
                            f"_handle_otiedote_release: Checking filter: {filter_entry}"
                        )
                        if ":" in filter_entry:
                            organization, field = filter_entry.split(":", 1)
                        else:
                            organization = filter_entry
                            field = "organization"

                        # Check if the field matches the filter
                        if field == "organization":
                            # Check if organization matches the organization field
                            release_org = release.get("organization", "")
                            if organization.lower() in release_org.lower():
                                should_send = True
                                self.logger.info(
                                    f"_handle_otiedote_release: Filter match found for organization '{organization}' in organization field"
                                )
                                break
                        elif field == "*":
                            # Match any field
                            release_text = json.dumps(
                                release, ensure_ascii=False
                            ).lower()
                            if organization.lower() in release_text:
                                should_send = True
                                self.logger.info(
                                    f"_handle_otiedote_release: Filter match found for '{organization}' in any field"
                                )
                                break
                        else:
                            # Check specific field
                            field_value = release.get(field, "")
                            if isinstance(field_value, list):
                                field_value = " ".join(field_value)
                            if organization.lower() in str(field_value).lower():
                                should_send = True
                                self.logger.info(
                                    f"_handle_otiedote_release: Filter match found for '{organization}' in field '{field}'"
                                )
                                break

                self.logger.info(
                    f"_handle_otiedote_release: should_send = {should_send} for {subscriber_nick}"
                )
                if should_send:
                    # Broadcast only the header (no description)
                    self._send_response(server, subscriber_nick, header_message)
                    self.logger.info(
                        f"Sent Otiedote release to {subscriber_nick} on {server_name}"
                    )
                else:
                    self.logger.debug(
                        f"Filtered Otiedote release for {subscriber_nick} on {server_name}"
                    )
            except Exception as e:
                self.logger.error(
                    f"Error sending Otiedote release to {subscriber_nick} on {server_name}: {e}"
                )

    def stop(self, quit_message: str = None):
        """Quit all servers, stop all services and shutdown bot gracefully.

        Args:
            quit_message (str, optional): Custom quit message to use. If not provided, uses the stored quit_message.
        """
        self.logger.info(
            f"Shutting down bot manager with message: {self.quit_message}..."
        )

        # Set stop event
        self.stop_event.set()

        # Update quit message if provided
        if quit_message:
            self.quit_message = quit_message

        # Stop monitoring services
        try:
            if self.fmi_warning_service is not None:
                self.logger.info("Stopping FMI warning service...")
                self.fmi_warning_service.stop()
        except Exception as e:
            self.logger.error(f"Error stopping FMI warning service: {e}")

        try:
            if self.otiedote_service is not None:
                self.logger.info(
                    "Stopping Otiedote service (may take up to 5 seconds)..."
                )
                # Signal the service to stop - it runs in its own background thread
                # Setting running=False will cause the monitor loop to exit
                if hasattr(self.otiedote_service, "running"):
                    self.otiedote_service.running = False
                    # The service's stop() method should be called from its own event loop
                    # but since we can't easily access it, just wait for the thread to exit
                    # The daemon thread will exit when the process exits anyway

                # Give it a moment to detect the stop signal
                time.sleep(1)

                self.logger.info("Otiedote service stop signaled")
        except Exception as e:
            self.logger.error(f"Error stopping Otiedote service: {e}")

        self.logger.info("Bot manager shut down complete")

    def wait_for_shutdown(self):
        """Wait for console thread, server threads, or shutdown signal."""
        try:
            while not self.stop_event.is_set():
                # Check if we have any active server threads
                active_server_threads = [
                    thread
                    for thread in self.server_threads.values()
                    if thread.is_alive()
                ]

                # Check if console thread is still running
                console_active = (
                    hasattr(self, "console_thread") and self.console_thread.is_alive()
                )

                # If no server threads and no console, we should exit
                if not active_server_threads and not console_active:
                    if self.stop_event.is_set():
                        self.logger.debug("Stop event set, exiting wait loop")
                        break
                    # If no active threads but stop event not set, wait a bit more
                    time.sleep(1)
                    continue

                time.sleep(0.1)  # Check frequently for faster response
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
                    now = time.strftime("%H:%M:%S", time.localtime())
                    user_input = input(f"{now}💬 > ")
                    # Mark that input is no longer active
                    self._input_active = False

                    if not user_input or not user_input.strip():
                        continue

                    user_input = user_input.strip()

                    if user_input.lower() in ("quit", "exit"):
                        self.logger.info("Console quit command received")
                        self.logger.log(
                            "🛑 Shutting down bot...",
                            "INFO",
                            fallback_text="[STOP] Shutting down bot...",
                        )
                        self.stop_event.set()
                        break

                    if user_input.startswith("!"):
                        # Process console commands
                        try:
                            # Handle built-in connection commands first
                            command_parts = user_input[1:].split()
                            command = command_parts[0].lower() if command_parts else ""
                            args = command_parts[1:] if len(command_parts) > 1 else []

                            if command == "connect":
                                result = self._console_connect(*args)
                                self.logger.info(result)
                            elif command == "disconnect":
                                result = self._console_disconnect(*args)
                                self.logger.info(result)
                            elif command == "status":
                                result = self._console_status(*args)
                                self.logger.info(result)
                            elif command == "channels":
                                result = self._get_channel_status()
                                self.logger.info(result)
                            else:
                                # Process other console commands via command_loader
                                from command_loader import process_console_command

                                bot_functions = self._create_console_bot_functions()
                                process_console_command(user_input, bot_functions)
                        except Exception as e:
                            self.logger.error(f"Console command error: {e}")
                    elif user_input.startswith("#"):
                        # Channel join/part command
                        try:
                            channel_name = user_input[1:].strip()
                            if channel_name:
                                result = self._console_join_or_part_channel(
                                    channel_name
                                )
                                self.logger.info(result)
                            else:
                                result = self._get_channel_status()
                                self.logger.info(result)
                        except Exception as e:
                            self.logger.error(f"Channel command error: {e}")
                    elif user_input.startswith("-"):
                        # AI chat command - send asynchronously to prevent blocking input
                        ai_message = user_input[1:].strip()
                        if ai_message:
                            if self.gpt_service:
                                self.logger.log(
                                    "🤖 AI: Processing...",
                                    "MSG",
                                    fallback_text="AI: Processing...",
                                )
                                ai_thread = threading.Thread(
                                    target=self._process_ai_request,
                                    args=(ai_message, "Console"),
                                    daemon=True,
                                )
                                ai_thread.start()
                            else:
                                self.logger.error(
                                    "AI service not available (no OpenAI API key configured)"
                                )
                        else:
                            self.logger.error("Empty AI message. Use: -<message>")
                    else:
                        # Send to active channel
                        try:
                            result = self._console_send_to_channel(user_input)
                            self.logger.info(result)
                        except Exception as e:
                            self.logger.error(f"Channel message error: {e}")

                except (EOFError, KeyboardInterrupt):
                    self.logger.error("Console input interrupted! Exiting...")
                    self.stop_event.set()
                    break
        except Exception as e:
            self.logger.error(f"Console listener error: {e}")
        finally:
            # Save command history on exit
            self._save_command_history()

    def _process_ai_request(self, user_input: str, sender: str):
        """Process AI request in a separate thread to avoid blocking console input."""
        try:
            response = self.gpt_service.chat(user_input, sender)
            if response:
                self.logger.log(
                    f"🤖 AI: {response}", "MSG", fallback_text=f"AI: {response}"
                )
            else:
                self.logger.log(
                    "🤖 AI: (no response)", "MSG", fallback_text="AI: (no response)"
                )
        except Exception as e:
            self.logger.error(f"AI chat error: {e}")

    def _console_connect(self, *args):
        """Console command to connect to servers."""
        if not args:
            # Connect to all configured servers
            if not self.servers:
                self.logger.error("No servers configured. Load configurations first.")
                return "No servers configured"

            self.connect_to_servers()
            connected_servers = [
                name
                for name, thread in self.server_threads.items()
                if thread.is_alive()
            ]
            return f"Connected to {len(connected_servers)} servers: {', '.join(connected_servers)}"

        # Parse arguments for new server connection
        if len(args) >= 2:
            server_name = args[0]
            server_host = args[1]
            server_port = int(args[2]) if len(args) > 2 and args[2].isdigit() else 6667
            channels = args[3].split(",") if len(args) > 3 else []
            use_tls = len(args) > 4 and args[4].lower() in ("tls", "ssl", "true")

            try:
                self.add_server_and_connect(
                    server_name, server_host, server_port, channels, use_tls=use_tls
                )
                return f"Added and connected to {server_name} ({server_host}:{server_port})"
            except Exception as e:
                self.logger.error(f"Error connecting to new server: {e}")
                return f"Error: {e}"
        else:
            return "Usage: !connect [server_name host [port] [channels] [tls]]"

    def _console_disconnect(self, *args):
        """Console command to disconnect from servers."""
        if not self.connected:
            return "No servers currently connected"

        if not args:
            # Disconnect from all servers
            self.disconnect_from_servers()
            return "Disconnected from all servers"
        else:
            # Disconnect from specific servers
            server_names = list(args)
            self.disconnect_from_servers(server_names)
            return f"Disconnected from: {', '.join(server_names)}"

    def _console_status(self, *args):
        """Console command to show connection status."""
        if not self.servers:
            return "No servers configured"

        status_lines = ["Server Status:"]
        for name, server in self.servers.items():
            thread = self.server_threads.get(name)
            if thread and thread.is_alive():
                connected = "✅ Connected" if server.connected else "🔄 Connecting"
            else:
                connected = "❌ Disconnected"
            status_lines.append(
                f"  {name} ({server.config.host}:{server.config.port}): {connected}"
            )

        return "\n".join(status_lines)

    def _console_select_channel(self, channel_name: str, server_name: str = None):
        """Console command to select an active channel (must already be joined).

        Args:
            channel_name: Channel name (with or without # prefix)
            server_name: Optional server name. If None, uses first connected server.
        """
        # Ensure channel name has # prefix
        if not channel_name.startswith("#"):
            channel_name = f"#{channel_name}"

        # Find target server
        target_server = None
        if server_name:
            target_server = self.servers.get(server_name)
            if not target_server:
                return f"Server '{server_name}' not found"
        else:
            # Use first connected server
            for name, server in self.servers.items():
                if (
                    name in self.server_threads
                    and self.server_threads[name].is_alive()
                    and server.connected
                ):
                    target_server = server
                    server_name = name
                    break

        if not target_server:
            return "No connected servers available. Use !connect first."

        # Initialize joined channels for this server if needed
        if server_name not in self.joined_channels:
            self.joined_channels[server_name] = set()

        # Check if already in channel
        if channel_name in self.joined_channels[server_name]:
            # Set as active channel
            self.active_channel = channel_name
            self.active_server = server_name
            return f"Selected {channel_name} on {server_name} (now active)"
        else:
            return f"Not joined to {channel_name} on {server_name}. Use !join {channel_name[1:]} first."

    def _console_join_or_part_channel(self, channel_name: str, server_name: str = None):
        """Console command to join or part a channel.

        Args:
            channel_name: Channel name (with or without # prefix)
            server_name: Optional server name. If None, uses first connected server.
        """
        # Ensure channel name has # prefix
        if not channel_name.startswith("#"):
            channel_name = f"#{channel_name}"

        # Find target server
        target_server = None
        if server_name:
            target_server = self.servers.get(server_name)
            if not target_server:
                return f"Server '{server_name}' not found"
        else:
            # Use first connected server
            for name, server in self.servers.items():
                if (
                    name in self.server_threads
                    and self.server_threads[name].is_alive()
                    and server.connected
                ):
                    target_server = server
                    server_name = name
                    break

        if not target_server:
            return "No connected servers available. Use !connect first."

        # Initialize joined channels for this server if needed
        if server_name not in self.joined_channels:
            self.joined_channels[server_name] = set()

        # Check if already in channel
        if channel_name in self.joined_channels[server_name]:
            # Part the channel
            try:
                target_server.part_channel(channel_name)
                self.joined_channels[server_name].discard(channel_name)

                # If this was the active channel, clear it
                if (
                    self.active_channel == channel_name
                    and self.active_server == server_name
                ):
                    self.active_channel = None
                    self.active_server = None

                return f"Parted {channel_name} on {server_name}"
            except Exception as e:
                return f"Error parting {channel_name}: {e}"
        else:
            # Join the channel
            try:
                target_server.join_channel(channel_name)
                self.joined_channels[server_name].add(channel_name)

                # Set as active channel
                self.active_channel = channel_name
                self.active_server = server_name

                return f"Joined {channel_name} on {server_name} (now active)"
            except Exception as e:
                return f"Error joining {channel_name}: {e}"

    def _console_send_to_channel(self, message: str):
        """Send a message to the currently active channel.

        Args:
            message: Message to send
        """
        if not self.active_channel or not self.active_server:
            return "No active channel. Use #channel to join and activate a channel."

        server = self.servers.get(self.active_server)
        if not server or not server.connected:
            return f"Server {self.active_server} is not connected."

        try:
            server.send_message(self.active_channel, message)
            return f"[{self.active_server}:{self.active_channel}] <{self.bot_name}> {message}"
        except Exception as e:
            return f"Error sending message: {e}"

    def _get_channel_status(self):
        """Get status of joined channels and active channel."""
        if not self.joined_channels:
            return "No channels joined."

        status_lines = ["Channel Status:"]
        for server_name, channels in self.joined_channels.items():
            if channels:
                server = self.servers.get(server_name)
                server_status = "🟢" if server and server.connected else "🔴"
                status_lines.append(f"  {server_status} {server_name}:")
                for channel in sorted(channels):
                    active_marker = (
                        " (active)"
                        if channel == self.active_channel
                        and server_name == self.active_server
                        else ""
                    )
                    status_lines.append(f"    {channel}{active_marker}")

        return "\n".join(status_lines)

    def _create_console_bot_functions(self):
        """Create bot functions dictionary for console commands."""
        return {
            # Core functions
            "notice_message": lambda msg, irc=None, target=None: self.logger.msg(
                f"{msg}"
            ),
            "log": self.logger.msg,
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
            "BOT_VERSION": "2.2.0",
            "server_name": "console",
            "stop_event": self.stop_event,  # Allow console commands to trigger shutdown
            "set_quit_message": self.set_quit_message,  # Allow setting custom quit message
            "set_openai_model": self.set_openai_model,  # Allow changing OpenAI model at runtime
            "connect": self._console_connect,  # Connect to servers
            "disconnect": self._console_disconnect,  # Disconnect from servers
            "status": self._console_status,  # Show server status
            "channels": self._get_channel_status,  # Show channel status
            "join_channel": self._console_join_or_part_channel,  # Join/part channels
            "send_to_channel": self._console_send_to_channel,  # Send messages to channels
            "bot_manager": self,  # Reference to the bot manager itself
            "subscriptions": self._get_subscriptions_module(),  # Subscription management
        }

    def set_quit_message(self, message: str):
        """Set a custom quit message for all servers.

        Args:
            message (str): The quit message to use when stopping servers.
        """
        self.quit_message = message
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
                return "AI chat is not available (no OpenAI API key configured)"

            old = getattr(self.gpt_service, "model", None)
            self.gpt_service.model = model
            # Persist to environment and .env file
            os.environ["OPENAI_MODEL"] = model
            persisted = self._update_env_file("OPENAI_MODEL", model)
            self.logger.info(f"OpenAI model changed from {old} to {model}")
            if persisted:
                return f"OpenAI model set to '{model}' (persisted)"
            else:
                return f"OpenAI model set to '{model}' (session only)"
        except Exception as e:
            self.logger.error(f"Error setting OpenAI model: {e}")
            return f"Failed to set OpenAI model: {e}"

    def _console_weather(self, irc, channel, location):
        """Console weather command."""
        if not self.weather_service:
            self.logger.error("Weather service not available (no WEATHER_API_KEY)")
            return

        try:
            weather_data = self.weather_service.get_weather(location)
            response = self.weather_service.format_weather_message(weather_data)
            self.logger.info(f"Weather: {response}")
        except Exception as e:
            self.logger.error(f"Weather error: {e}")

    def _console_electricity(self, irc, channel, args):
        """Console electricity price command."""
        if not self.electricity_service:
            self.logger.error(
                "Electricity service not available (no ELECTRICITY_API_KEY)"
            )
            return

        try:
            import datetime

            current_hour = datetime.datetime.now().hour
            price_data = self.electricity_service.get_electricity_price(
                hour=current_hour
            )
            response = self.electricity_service.format_price_message(price_data)
            self.logger.info(f"Electricity: {response}")
        except Exception as e:
            self.logger.error(f"Electricity error: {e}")

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
            self.logger.error(
                "Electricity service not available (no ELECTRICITY_API_KEY)"
            )
            response = "⚡ Electricity price service not available. Please configure ELECTRICITY_API_KEY."
            self._send_response(irc, channel, response)
            return

        try:
            # Handle both string and list inputs for compatibility
            if isinstance(text_or_parts, list):
                # Called from IRC command with parts list or new command system
                args = text_or_parts
                text = " ".join(args) if args else ""
            else:
                # Called with string (e.g., from tests or console)
                text = text_or_parts or ""
                args = text.split() if text else []

            # Parse command arguments (extended for 15-minute support)
            parsed_args = self.electricity_service.parse_command_args(args)

            if parsed_args.get("error"):
                self.logger.error(
                    f"Electricity command parse error: {parsed_args['error']}"
                )
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

        # Don't send or log messages if we're not connected to the server
        if not server.connected:
            self.logger.debug(f"Not sending message to {target}: server not connected")
            return

        # Don't send or log messages if target is a channel and we haven't joined it
        # However, if we're receiving messages from a channel, we're clearly in it,
        # so we'll allow sending even if the join event wasn't tracked properly
        if target.startswith("#"):
            server_name = server.config.name
            # Normalize channel name to lowercase for case-insensitive comparison (IRC channels are case-insensitive)
            target_normalized = target.lower()
            if server_name not in self.joined_channels:
                self.joined_channels[server_name] = set()

            # Check if any case variant of the channel is in joined_channels
            joined_channels_normalized = {
                ch.lower() for ch in self.joined_channels[server_name]
            }
            if target_normalized not in joined_channels_normalized:
                # If channel not tracked, add it now (we're clearly in it if we're sending to it)
                # Store with the original case as received, but check case-insensitively
                self.logger.debug(
                    f"Channel {target} not in joined_channels, adding it now (server: {server_name})"
                )
                self.joined_channels[server_name].add(target)

        # Log IRC responses to console for visibility
        server_name = getattr(server.config, "name", "unknown")
        # Clean message for logging - replace newlines with separators to avoid TUI display issues
        clean_message = message.replace("\n", " | ").replace("\r", "").strip()
        self.logger.debug(
            f"Sending response to {target} on {server_name}: {clean_message[:100]}"
        )
        self.logger.msg(f"[{server_name}:{target}] {clean_message}", "MSG")

        try:
            if self.use_notices:
                server.send_notice(target, message)
            else:
                server.send_message(target, message)
        except Exception as e:
            self.logger.error(f"Error sending message to {target}: {e}", exc_info=True)

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

    def _get_otiedote_info(self, mode: str, number: int = None, offset: int = None):
        """Get otiedote information based on mode.

        Args:
            mode: One of 'latest_full', 'current_number', 'by_number', 'nth_latest'
            number: Release number for 'by_number' mode
            offset: Offset from latest for 'nth_latest' mode (1=latest, 2=second latest, etc.)

        Returns:
            Dictionary with 'error' (bool) and 'message' (str) keys
        """
        try:
            # Mode 1: Latest full description (the cached one)
            if mode == "latest_full":
                info = getattr(self, "latest_otiedote", None)
                if not info:
                    return {
                        "error": True,
                        "message": "📢 Ei tallennettua Onnettomuustiedotetta vielä. Odota uutta ilmoitusta.",
                    }

                desc = (info.get("description") or "").strip()
                url = info.get("url", "")
                title = info.get("title", "")

                if not desc:
                    return {
                        "error": False,
                        "message": f"📢 Ei kuvausta saatavilla. | {url}",
                    }

                return {"error": False, "message": f"📢 {title} | {desc} | {url}"}

            # Mode 2: Current release number
            elif mode == "current_number":
                if not self.otiedote_service:
                    return {
                        "error": True,
                        "message": "❌ Otiedote service not available",
                    }

                info = self.otiedote_service.get_latest_release_info()
                latest_num = info.get("latest_release", 0)
                return {
                    "error": False,
                    "message": f"📢 Viimeisin seurattu Otiedote: #{latest_num}",
                }

            # Mode 3: Fetch specific release by number
            elif mode == "by_number":
                if number is None:
                    return {"error": True, "message": "❌ Release number required"}

                if not self.otiedote_service:
                    return {
                        "error": True,
                        "message": "❌ Otiedote service not available",
                    }

                # Fetch the release from the service
                try:
                    release_data = self._fetch_otiedote_by_number(number)
                    if release_data.get("error"):
                        return release_data
                    return {"error": False, "message": release_data["message"]}
                except Exception as e:
                    return {
                        "error": True,
                        "message": f"❌ Error fetching otiedote #{number}: {e}",
                    }

            # Mode 4: Nth latest (1=latest, 2=second latest, etc.)
            elif mode == "nth_latest":
                if offset is None or offset < 1:
                    return {
                        "error": True,
                        "message": "❌ Valid offset required (1=latest, 2=second latest, etc.)",
                    }

                if not self.otiedote_service:
                    return {
                        "error": True,
                        "message": "❌ Otiedote service not available",
                    }

                # Calculate the release number
                info = self.otiedote_service.get_latest_release_info()
                latest_num = info.get("latest_release", 0)
                target_num = latest_num - (offset - 1)

                if target_num < 1:
                    return {
                        "error": True,
                        "message": f"❌ Not enough history. Latest is #{latest_num}",
                    }

                # Fetch the release
                try:
                    release_data = self._fetch_otiedote_by_number(target_num)
                    if release_data.get("error"):
                        return release_data
                    return {"error": False, "message": release_data["message"]}
                except Exception as e:
                    return {
                        "error": True,
                        "message": f"❌ Error fetching otiedote: {e}",
                    }

            else:
                return {"error": True, "message": "❌ Unknown mode"}

        except Exception as e:
            self.logger.error(f"Error getting otiedote info: {e}")
            return {"error": True, "message": f"❌ Error: {e}"}

    def _send_weather(self, irc, channel, location):
        """Send weather information."""
        if not self.weather_service:
            response = (
                "Weather service not available. Please configure WEATHER_API_KEY."
            )
            self.logger.error("Weather service not available (no WEATHER_API_KEY)")
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

    def _process_leet_winner_summary(self, context: Dict[str, Any]):
        """Parser for leet winners summary lines.

        Updates leet_winners.json counts for categories:
        - "first" (first)
        - "last" (last)
        - "multileet" (closest to 13:37)

        Only accepts messages from authorized nicks (Beici, Beibi, Beiki)
        or messages that start with admin password.

        This keeps !leetwinners in sync with external announcer messages.

        TODO: When only one leetwinner is announced, handle that too.
        """
        import re
        from datetime import datetime

        from config import get_config

        # Extract text and sender from context
        text = context.get("text", "")
        sender = context.get("sender", "")

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

    def _process_ekavika_winner_summary(self, context: Dict[str, Any]):
        """Parser for ekavika winners summary lines.

        Updates state.json ekavika section with competition data:
        - vika winner (closest before ekavika time)
        - eka winner (closest after ekavika time)

        Only accepts messages from authorized nicks (Beici, Beibi, Beiki)
        or messages that start with admin password.

        This keeps ekavika winners in sync with external announcer messages.
        """
        import re
        from datetime import datetime

        from config import get_config

        # Extract text and sender from context
        text = context.get("text", "")
        sender = context.get("sender", "")
        server_name = context.get("server_name", "unknown")

        # Define allowed nicks for ekavika winner tracking
        ALLOWED_NICKS = {"beici", "beibi", "beiki", "jamps"}

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

        self.logger.debug(f"Processing ekavika winner summary: {text} from {sender}")

        # Regex pattern for ekavika detection - matches the format from your messages
        # Pattern: "𝙫𝙞𝙠𝙖 oli [name] kello [time] ([note]), ja 𝖊𝖐𝖆 oli [name] kello [time] ([note])"
        pattern = r"𝙫𝙞𝙠𝙖 oli (\S+) kello ([^,]+),\s*\(([^)]+)\),\s*ja 𝖊𝖐𝖆 oli (\S+) kello ([^,]+),\s*\(([^)]+)\)"
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            self.logger.debug(f"No ekavika pattern match in: {text}")
            return

        vikq_winner, vikq_time, vikq_note, eka_winner, eka_time, eka_note = (
            match.groups()
        )

        # Extract server info from the message context
        # The server name should be available in the context
        server_host = getattr(context.get("server", {}).config, "host", server_name)

        # Load current state
        state = self.data_manager.load_state()

        # Initialize ekavika section if it doesn't exist
        if "ekavika" not in state:
            state["ekavika"] = {
                "competitions": [],
                "winners": {},
                "last_updated": datetime.now().isoformat(),
                "version": "1.0.0",
            }

        # Create competition record
        competition = {
            "event": "ekavika48_00:00:11",  # Default event name, could be parsed from message
            "server": server_host,
            "channel": "#joensuu",  # Default channel, could be parsed
            "vikq_winner": vikq_winner,
            "vikq_time": vikq_time.strip(),
            "vikq_note": vikq_note.strip(),
            "eka_winner": eka_winner,
            "eka_time": eka_time.strip(),
            "eka_note": eka_note.strip(),
            "announced_by": sender,
            "timestamp": datetime.now().isoformat(),
        }

        # Add competition to list
        state["ekavika"]["competitions"].append(competition)

        # Update winners statistics
        winners = state["ekavika"]["winners"]

        # Update vikq winner stats
        if vikq_winner not in winners:
            winners[vikq_winner] = {
                "vikq_wins": 0,
                "eka_wins": 0,
                "total_wins": 0,
                "servers": [],
            }
        winners[vikq_winner]["vikq_wins"] += 1
        winners[vikq_winner]["total_wins"] += 1
        if server_host not in winners[vikq_winner]["servers"]:
            winners[vikq_winner]["servers"].append(server_host)

        # Update eka winner stats
        if eka_winner not in winners:
            winners[eka_winner] = {
                "vikq_wins": 0,
                "eka_wins": 0,
                "total_wins": 0,
                "servers": [],
            }
        winners[eka_winner]["eka_wins"] += 1
        winners[eka_winner]["total_wins"] += 1
        if server_host not in winners[eka_winner]["servers"]:
            winners[eka_winner]["servers"].append(server_host)

        # Update last_updated timestamp
        state["ekavika"]["last_updated"] = datetime.now().isoformat()

        # Save updated state
        self.data_manager.save_state(state)

        # Log with authorization info
        auth_info = "admin override" if admin_override else f"authorized nick: {sender}"
        self.logger.info(
            f"Updated ekavika winners (vikq={vikq_winner}, eka={eka_winner}) via {auth_info} on {server_host}"
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

    def _fetch_title(self, irc, target, text):
        """Fetch and display URL titles or X/Twitter post content (excluding blacklisted URLs and file types)."""
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
            # Handle X/Twitter URLs specially
            if self._is_x_url(url):
                self._fetch_x_post_content(irc, target, url)
                continue

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

    @staticmethod
    def _is_youtube_url(url: str) -> bool:
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

    @staticmethod
    def _is_x_url(url: str) -> bool:
        """Check if a URL is an X/Twitter URL."""
        import re

        # Match x.com or twitter.com URLs with status and post ID
        x_patterns = [
            r"(?:https?://)?(?:www\.)?(?:x\.com|twitter\.com)/(\w+)/status/(\d+)",
        ]

        for pattern in x_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return True
        return False

    def _fetch_x_post_content(self, irc, target, url: str):
        """Fetch X/Twitter post content using X API and send to channel."""
        try:
            # Extract post ID from URL
            import re

            match = re.search(
                r"(?:https?://)?(?:www\.)?(?:x\.com|twitter\.com)/\w+/status/(\d+)",
                url,
                re.IGNORECASE,
            )

            if not match:
                self.logger.warning(f"Could not parse X URL: {url}")
                return

            post_id = match.group(1)

            # Check if X client is available
            if not x_client_available or not XClient:
                self.logger.warning("X API client not available")
                return

            # Get bearer token from environment
            bearer_token = os.getenv("X_BEARER_TOKEN")
            if not bearer_token:
                self.logger.warning("X_BEARER_TOKEN not configured")
                return

            # Check if enough time has passed since last request
            current_time = time.time()
            time_since_last_request = current_time - self.x_api_last_request_time

            if time_since_last_request < self.x_api_rate_limit_seconds:
                # Rate limited - add to queue instead of processing immediately
                self.logger.info(
                    f"X API rate limited, queuing request for post {post_id}"
                )
                with self.x_api_queue_lock:
                    self.x_api_queue.append((irc, target, url))
                # Start queue processing thread if not already running
                if (
                    self.x_api_queue_thread is None
                    or not self.x_api_queue_thread.is_alive()
                ):
                    self.x_api_queue_thread = threading.Thread(
                        target=self._process_x_api_queue,
                        daemon=True,
                        name="X-API-Queue",
                    )
                    self.x_api_queue_thread.start()
                return

            # Process the request immediately
            self._process_x_api_request(irc, target, url, post_id, bearer_token)

        except Exception as e:
            self.logger.error(f"Error fetching X post content for {url}: {e}")

    def _process_x_api_request(self, irc, target, url, post_id, bearer_token):
        """Process a single X API request."""
        try:
            # Update last request time
            self.x_api_last_request_time = time.time()

            # Create X client
            try:
                x_client = XClient(bearer_token=bearer_token)
            except Exception as e:
                self.logger.error(f"Failed to create X client: {e}")
                if hasattr(irc, "send_message"):
                    self._send_response(
                        irc, target, f"🐦 Error creating X API client: {str(e)[:100]}"
                    )
                return

            # Fetch post by ID
            try:
                response = x_client.posts.get_by_id(post_id)
                if response and hasattr(response, "data") and response.data:
                    post_data = response.data

                    # Extract the text content (response.data is a dict)
                    post_text = post_data.get("text", "")
                    if post_text:
                        # Clean up the text (remove extra whitespace)
                        post_text = re.sub(r"\s+", " ", post_text).strip()

                        # Send the post content
                        if hasattr(irc, "send_message"):
                            self._send_response(irc, target, f"🐦 {post_text}")
                        else:
                            self.logger.info(f"X Post: {post_text}")
                    else:
                        self.logger.debug(f"No text content found in X post {post_id}")
                else:
                    self.logger.debug(f"No data returned for X post {post_id}")

            except Exception as e:
                # Handle rate limiting, auth issues, etc.
                error_str = str(e).lower()

                # Helper: extract reset time from exception/headers/error string
                def _extract_reset_time_from_exception(exc):
                    reset_time_local = None

                    # Try direct response headers
                    response_obj = getattr(exc, "response", None)
                    if response_obj is None and hasattr(exc, "__dict__"):
                        response_obj = exc.__dict__.get("response")

                    headers = None
                    if response_obj is not None:
                        # Many HTTP client responses have .headers as a mapping-like object
                        headers = getattr(response_obj, "headers", None)
                        # If response is dict-like with 'headers'
                        if headers is None and isinstance(response_obj, dict):
                            headers = response_obj.get("headers")

                    # Normalize headers and read x-rate-limit-reset
                    try:
                        if headers:
                            # Convert to plain dict; support objects with .items()
                            if hasattr(headers, "items"):
                                header_dict = {
                                    str(k).lower(): v for k, v in headers.items()
                                }
                            elif isinstance(headers, dict):
                                header_dict = {
                                    str(k).lower(): v for k, v in headers.items()
                                }
                            else:
                                # Fallback: try getattr/get style access
                                header_dict = {}
                                for key_name in [
                                    "x-rate-limit-reset",
                                    "x-rate-limit-remaining",
                                    "x-rate-limit-limit",
                                ]:
                                    val = None
                                    if hasattr(headers, "get"):
                                        val = headers.get(key_name)
                                    elif hasattr(headers, "__getitem__"):
                                        try:
                                            val = headers[key_name]
                                        except Exception:
                                            val = None
                                    if val is not None:
                                        header_dict[key_name] = val

                            reset_header = header_dict.get("x-rate-limit-reset")
                            if reset_header is not None:
                                reset_time_local = int(str(reset_header).strip())
                                return reset_time_local
                    except Exception as header_error:
                        self.logger.debug(
                            f"Could not parse x-rate-limit-reset header: {header_error}"
                        )

                    # Regex fallback: look in exception string
                    try:
                        exc_str = str(exc)
                        match = re.search(
                            r"x-rate-limit-reset[:\s]+(\d+)", exc_str, re.IGNORECASE
                        )
                        if match:
                            reset_time_local = int(match.group(1))
                            return reset_time_local

                        # If no explicit header found, try guessing from 10-digit future timestamps (within 1h)
                        timestamp_matches = re.findall(r"\b(\d{10})\b", exc_str)
                        if timestamp_matches:
                            now = int(time.time())
                            future_candidates = [
                                int(ts)
                                for ts in timestamp_matches
                                if now < int(ts) < now + 3600
                            ]
                            if future_candidates:
                                reset_time_local = max(future_candidates)
                                return reset_time_local
                    except Exception as regex_error:
                        self.logger.debug(
                            f"Regex parsing for reset time failed: {regex_error}"
                        )

                    return reset_time_local

                if "429" in error_str or "too many requests" in error_str:
                    self.logger.warning(f"X API rate limited for post {post_id}: {e}")

                    # Try to get the rate limit reset time
                    reset_time = _extract_reset_time_from_exception(e)

                    # Log reset time if found
                    if reset_time:
                        reset_dt = datetime.datetime.fromtimestamp(reset_time)
                        self.logger.info(
                            f"Rate limit resets at {reset_dt} (unix {reset_time})"
                        )
                        self.x_api_rate_limit_reset = reset_time
                        wait_seconds = max(0, reset_time - int(time.time()))
                        self.logger.debug(
                            f"Calculated wait time from header: {wait_seconds} seconds"
                        )
                    else:
                        # Default wait (e.g., 5 minutes)
                        wait_seconds = getattr(self, "x_api_rate_limit_seconds", 300)
                        self.logger.warning(
                            f"No reset header found; using default wait time: {wait_seconds} seconds"
                        )

                    # Re-queue this request with calculated delay
                    scheduled_time = time.time() + wait_seconds
                    with self.x_api_queue_lock:
                        # Store as (irc, target, url, scheduled_time) tuple
                        self.x_api_queue.append((irc, target, url, scheduled_time))

                    # Start queue processing thread if not already running
                    if (
                        self.x_api_queue_thread is None
                        or not self.x_api_queue_thread.is_alive()
                    ):
                        self.x_api_queue_thread = threading.Thread(
                            target=self._process_x_api_queue,
                            daemon=True,
                            name="X-API-Queue",
                        )
                        self.x_api_queue_thread.start()

                    # Inform user with specific wait time
                    wait_minutes = int(wait_seconds // 60)
                    if wait_minutes > 0:
                        wait_msg = f"🐦 X API rate limited. Request queued for ~{wait_minutes} minute{'s' if wait_minutes != 1 else ''}."
                    else:
                        wait_msg = f"🐦 X API rate limited. Request queued; retrying in ~{wait_seconds} seconds."

                    if hasattr(irc, "send_message"):
                        self._send_response(irc, target, wait_msg)
                    else:
                        self.logger.info(wait_msg)

                    return  # Stop processing now; it will be retried later

                elif "401" in error_str or "unauthorized" in error_str:
                    self.logger.error(
                        f"X API authentication failed for post {post_id}: {e}"
                    )
                elif "403" in error_str or "forbidden" in error_str:
                    self.logger.error(f"X API access forbidden for post {post_id}: {e}")
                else:
                    self.logger.error(f"Error fetching X post {post_id}: {e}")

        except Exception as e:
            self.logger.error(f"Error processing X API request for {url}: {e}")

    def _process_x_api_queue(self):
        """Process queued X API requests with proper rate limiting."""
        self.logger.info("Started X API queue processing thread")

        while True:
            try:
                # Check if there are requests in the queue
                with self.x_api_queue_lock:
                    if not self.x_api_queue:
                        break  # No more requests, exit thread

                    # Get the next request (can be 3 or 4 tuple depending on format)
                    request = self.x_api_queue.pop(0)
                    if len(request) == 4:
                        irc, target, url, scheduled_time = request
                        # Check if it's time to process this request
                        current_time = time.time()
                        if current_time < scheduled_time:
                            # Not yet time to process, put it back in queue
                            self.x_api_queue.append(request)
                            # Sleep for a bit before checking again
                            time.sleep(1)
                            continue
                    elif len(request) == 3:
                        irc, target, url = request
                    else:
                        self.logger.error(f"Invalid queue request format: {request}")
                        continue

                self.logger.info(f"Processing queued X API request: {url}")

                # Extract post ID from URL
                import re

                match = re.search(
                    r"(?:https?://)?(?:www\.)?(?:x\.com|twitter\.com)/\w+/status/(\d+)",
                    url,
                    re.IGNORECASE,
                )

                if not match:
                    self.logger.warning(f"Could not parse queued X URL: {url}")
                    continue

                post_id = match.group(1)

                # Get bearer token from environment
                bearer_token = os.getenv("X_BEARER_TOKEN")
                if not bearer_token:
                    self.logger.warning(
                        "X_BEARER_TOKEN not configured for queued request"
                    )
                    continue

                # Process the request
                self._process_x_api_request(irc, target, url, post_id, bearer_token)

                # Wait before processing next request (respect rate limit)
                time.sleep(self.x_api_rate_limit_seconds)

            except Exception as e:
                self.logger.error(f"Error in X API queue processing: {e}")
                # Continue processing other requests
                time.sleep(1)

        self.logger.info("X API queue processing thread finished")
        self.x_api_queue_thread = None

    def _is_url_blacklisted(self, url: str) -> bool:
        """Check if a URL should be blacklisted from title fetching."""
        # Skip YouTube URLs as they are already handled by the YouTube service
        if self._is_youtube_url(url):
            return True

        # Skip X/Twitter URLs as they are handled by the X post content fetcher
        if self._is_x_url(url):
            return True

        # Get blacklisted domains from environment
        blacklisted_domains = os.getenv(
            "TITLE_BLACKLIST_DOMAINS",
            "youtube.com,youtu.be,facebook.com,fb.com,instagram.com,tiktok.com,discord.com,reddit.com,imgur.com",
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
                self.logger.info(
                    f"Skipping URL with blacklisted domain '{domain}': {url}"
                )
                return True

        # Check file extensions
        for ext in blacklisted_extensions:
            ext = ext.strip()
            if ext and url_lower.endswith(ext):
                self.logger.info(
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
                self.logger.info(
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
        """Update a key-value pair in the .env file. Creates the file if it doesn't exist."""
        env_file = ".env"
        try:
            # Create .env file if it doesn't exist
            if not os.path.exists(env_file):
                with open(env_file, "w", encoding="utf-8") as f:
                    f.write("")  # Create empty .env file

            # Read current .env file
            with open(env_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Find and update the key, or add it if not found
            key_found = False
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith(f"{key}=") or stripped.startswith(f"#{key}="):
                    lines[i] = f"{key}={value}\n"
                    key_found = True
                    break

            if not key_found:
                lines.append(f"{key}={value}\n")

            # Write back to .env file
            with open(env_file, "w", encoding="utf-8") as f:
                f.writelines(lines)

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
            self.logger.info(f"Tamagotchi responses toggled to {status} by {sender}")
            response = f"{emoji} Tamagotchi responses are now {status}."
        else:
            self.logger.info(
                f"Tamagotchi responses toggled to {status} by {sender} (but .env update failed)"
            )
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

        try:
            video_id = self.youtube_service.extract_video_id(text)
            if video_id:
                video_data = self.youtube_service.get_video_info(video_id)
                message = self.youtube_service.format_video_info_message(video_data)
                self._send_response(server, target, message)
                self.logger.info(f"Displayed YouTube info for video ID: {video_id}")
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
            timestamp = self.leet_detector.get_timestamp_with_nanoseconds()
            # Check for leet achievement, including the user's message text
            result = self.leet_detector.check_message_for_leet(
                sender, timestamp, user_message
            )

            if result:
                achievement_message, achievement_level = result
                if (
                    achievement_level != "leet"
                ):  # Filter out regular leet level messages
                    # Send achievement message to the channel immediately
                    self._send_response(server, target, achievement_message)

                # Log the achievement
                self.logger.info(
                    f"Leet achievement: {achievement_level} for {sender} in {target} at {timestamp} - message: {user_message}"
                )

        except Exception as e:
            self.logger.error(f"Error checking nanoleet achievement: {e}")

    def _handle_numeric(self, server: Server, code: int, target: str, params: str):
        """
        Handle IRC numeric responses.

        Args:
            server: The Server instance that received the response
            code: The numeric response code (e.g., 353, 366)
            target: The target (usually the bot's nick)
            params: The response parameters
        """
        server_name = server.config.name

        try:
            # Only process NAMES responses if they were explicitly triggered by !ops command
            # Check if we have pending ops for this server
            if server_name not in self._pending_ops:
                return  # No pending ops, ignore this NAMES response

            # Handle RPL_NAMREPLY (353) - user list for a channel
            if code == 353:
                # Format: :server 353 botnick = #channel :user1 user2 user3 ...
                # Extract channel and user list
                parts = params.split(":", 1)
                if len(parts) == 2:
                    channel_part, user_list = parts
                    # channel_part might be "= #channel" or just "#channel"
                    channel = channel_part.strip().split()[
                        -1
                    ]  # Get the last part (channel name)

                    # Only process if we have pending ops for this channel
                    if channel not in self._pending_ops[server_name]:
                        return  # Not a channel we're opping

                    # Add users to the list (split by spaces, strip @+ prefixes for ops/voiced)
                    users = [
                        user.lstrip("@+").strip()
                        for user in user_list.split()
                        if user.strip()
                    ]
                    self._pending_ops[server_name][channel]["users"].extend(users)

                    self.logger.debug(
                        f"Collected {len(users)} users for {channel} on {server_name} (!ops command)"
                    )

            # Handle RPL_ENDOFNAMES (366) - end of names list
            elif code == 366:
                # Format: :server 366 botnick #channel :End of /NAMES list.
                # Extract channel name
                channel = params.split()[0] if params else ""

                # Only process if we have pending ops for this channel
                if (
                    channel in self._pending_ops[server_name]
                    and self._pending_ops[server_name][channel]["users"]
                ):

                    users = self._pending_ops[server_name][channel]["users"]

                    # Remove the bot's own nick from the list to avoid opping itself
                    users = [
                        user for user in users if user.lower() != self.bot_name.lower()
                    ]

                    if users:
                        # Send MODE commands to op all users
                        # IRC allows multiple users per MODE command, but we'll do it in batches
                        batch_size = 10  # Conservative batch size to avoid flooding

                        for i in range(0, len(users), batch_size):
                            batch = users[
                                i : i + batch_size  # noqa E203 - Black formatting
                            ]

                            # Send MODE +o for each user in the batch
                            for user in batch:
                                try:
                                    server.send_raw(f"MODE {channel} +o {user}")
                                    self.logger.info(
                                        f"Opped {user} in {channel} on {server_name}"
                                    )
                                except Exception as e:
                                    self.logger.error(
                                        f"Failed to op {user} in {channel}: {e}"
                                    )

                    # Clean up the pending ops data
                    del self._pending_ops[server_name][channel]
                    if not self._pending_ops[server_name]:
                        del self._pending_ops[server_name]

                    self.logger.info(
                        f"Completed !ops for {channel} on {server_name} ({len(users)} users)"
                    )

        except Exception as e:
            self.logger.error(f"Error handling numeric response {code}: {e}")
