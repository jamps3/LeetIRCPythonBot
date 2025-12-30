"""
Console Manager Module

Handles console/TUI interface, command processing, and input/output management
extracted from bot_manager.py.
"""

import os
import threading
import time
from typing import Any, Dict

import logger

logger = logger.get_logger("ConsoleManager")


class ConsoleManager:
    """
    Manages console/TUI interface and command processing.

    This class handles:
    - Console input reading and processing
    - Command history management
    - Readline setup and configuration
    - Console output protection
    - Interactive terminal detection
    """

    def __init__(
        self,
        service_manager=None,
        message_handler=None,
        server_manager=None,
        stop_event: threading.Event = None,
    ):
        """
        Initialize the console manager.

        Args:
            service_manager: ServiceManager instance (optional, can be set later)
            message_handler: MessageHandler instance (optional, can be set later)
            server_manager: ServerManager instance (optional, can be set later)
            stop_event: Event to signal shutdown (optional, can be set later)
        """
        self.service_manager = service_manager
        self.message_handler = message_handler
        self.server_manager = server_manager
        self.stop_event = stop_event

        # Console mode settings
        self.console_mode = True  # Always console mode for this manager
        self.readline_available = False
        self.readline = None
        self._history_file = None
        self._input_active = False

        # Active channel tracking for console
        self.active_channel = None
        self.active_server = None

        # Setup readline and console features (can work without service_manager)
        self._setup_readline()
        self._setup_console_output_protection()

        logger.info("Console manager initialized")

    def set_message_handler(self, message_handler):
        """Set the message handler after initialization."""
        self.message_handler = message_handler

    def set_server_manager(self, server_manager):
        """Set the server manager after initialization."""
        self.server_manager = server_manager

    def set_stop_event(self, stop_event: threading.Event):
        """Set the stop event after initialization."""
        self.stop_event = stop_event

    def _is_interactive_terminal(self) -> bool:
        """Check if we're running in an interactive terminal."""
        try:
            import sys

            # Check if stdin is a TTY and we're not being piped to
            return sys.stdin.isatty() and sys.stdout.isatty()
        except (AttributeError, OSError):
            return False

    def _setup_readline(self):
        """Configure readline for command history and editing."""
        try:
            # Only set up readline if we're in an interactive terminal
            if not self._is_interactive_terminal():
                logger.debug("Non-interactive terminal, skipping readline setup")
                self._history_file = None
                return

            # Try to import readline only when needed
            try:
                import readline

                self.readline = readline
                self.readline_available = True
                logger.debug("Readline imported successfully")
            except ImportError:
                logger.warning(
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

            # Configure readline for better editing
            logger.debug("Setting up readline history...")
            try:
                self._setup_readline_history()
                logger.debug("Readline history setup complete.")
            except Exception as e:
                logger.debug(f"Readline history setup failed: {e}")

        except ImportError:
            logger.warning("readline module not available, command history disabled")
            self._history_file = None
        except Exception as e:
            logger.warning(f"Could not configure readline: {e}")
            self._history_file = None

    def _setup_readline_history(self):
        """Configure readline history file and settings."""
        if not self.readline:
            return

        # Set history file
        history_file = os.path.expanduser("~/.leetbot_history")

        # Set history length (number of commands to remember)
        self.readline.set_history_length(1000)

        # Try to read existing history
        try:
            self.readline.read_history_file(history_file)
            logger.debug(f"Loaded command history from {history_file}")
        except FileNotFoundError:
            # History file doesn't exist yet, that's fine
            pass
        except Exception as e:
            logger.warning(f"Could not load command history: {e}")

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
                logger.debug("Readline key bindings configured")
            except Exception as e:
                logger.warning(f"Could not configure readline bindings: {e}")

        # Store history file path for saving later
        self._history_file = history_file

    def _setup_console_output_protection(self):
        """Set up console output protection to prevent interference with input prompts."""
        try:
            # Initialize the input active flag for output protection
            self._input_active = False
            logger.debug("Console output protection initialized")
        except Exception as e:
            logger.warning(f"Could not set up console output protection: {e}")

    def _save_command_history(self):
        """Save command history to file."""
        if self.console_mode and self._history_file and self.readline:
            try:
                self.readline.write_history_file(self._history_file)
                logger.debug(f"Saved command history to {self._history_file}")
            except Exception as e:
                logger.warning(f"Could not save command history: {e}")

    def start_console_listener(self):
        """Start the console command listener thread."""
        console_thread = threading.Thread(
            target=self._listen_for_console_commands,
            daemon=True,
            name="Console-Listener",
        )
        console_thread.start()
        logger.debug("Started console input listener")

    def _listen_for_console_commands(self):
        """Listen for console commands in a separate thread with readline history support."""
        try:
            # Check if we're running in an interactive terminal
            if not self._is_interactive_terminal():
                logger.info(
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
                    self._process_console_input(user_input)

                except (EOFError, KeyboardInterrupt):
                    logger.error("Console input interrupted! Exiting...")
                    self.stop_event.set()
                    break
        except Exception as e:
            logger.error(f"Console listener error: {e}")
        finally:
            # Save command history on exit
            self._save_command_history()

    def _process_console_input(self, user_input: str):
        """Process a line of console input."""
        if user_input.lower() in ("quit", "exit"):
            self._handle_console_quit()
        elif user_input.startswith("!"):
            self._handle_console_command(user_input)
        elif user_input.startswith("#"):
            self._handle_channel_command(user_input)
        elif user_input.startswith("-"):
            self._handle_ai_chat_command(user_input)
        else:
            self._handle_channel_message(user_input)

    def _handle_console_quit(self):
        """Handle quit command from console."""
        logger.info("Console quit command received")
        logger.log(
            "🛑 Shutting down bot...",
            "INFO",
            fallback_text="[STOP] Shutting down bot...",
        )
        self.stop_event.set()

    def _handle_console_command(self, user_input: str):
        """Handle bot commands from console."""
        try:
            command_parts = user_input[1:].split()
            command = command_parts[0].lower() if command_parts else ""
            args = command_parts[1:] if len(command_parts) > 1 else []

            if command == "connect":
                result = self._console_connect(*args)
                logger.info(result)
            elif command == "disconnect":
                result = self._console_disconnect(*args)
                logger.info(result)
            elif command == "status":
                result = self._console_status(*args)
                logger.info(result)
            elif command == "channels":
                result = self._get_channel_status()
                logger.info(result)
            else:
                # Process other commands via command_loader
                from command_loader import process_console_command

                bot_functions = self._create_console_bot_functions()
                process_console_command(user_input, bot_functions)
        except Exception as e:
            logger.error(f"Console command error: {e}")

    def _handle_channel_command(self, user_input: str):
        """Handle channel join/part commands from console."""
        try:
            channel_name = user_input[1:].strip()
            if channel_name:
                result = self._console_join_or_part_channel(channel_name)
                logger.info(result)
            else:
                result = self._get_channel_status()
                logger.info(result)
        except Exception as e:
            logger.error(f"Channel command error: {e}")

    def _handle_ai_chat_command(self, user_input: str):
        """Handle AI chat commands from console."""
        ai_message = user_input[1:].strip()
        if ai_message:
            if self.service_manager.is_service_available("gpt"):
                logger.log(
                    "🤖 AI: Processing...", "MSG", fallback_text="AI: Processing..."
                )
                ai_thread = threading.Thread(
                    target=self._process_ai_request,
                    args=(ai_message, "Console"),
                    daemon=True,
                )
                ai_thread.start()
            else:
                logger.error("AI service not available (no OpenAI API key configured)")
        else:
            logger.error("Empty AI message. Use: -<message>")

    def _handle_channel_message(self, user_input: str):
        """Handle regular messages to be sent to active channel."""
        try:
            result = self._console_send_to_channel(user_input)
            logger.info(result)
        except Exception as e:
            logger.error(f"Channel message error: {e}")

    def _process_ai_request(self, user_input: str, sender: str):
        """Process AI request in a separate thread to avoid blocking console input."""
        try:
            response = self.service_manager.get_service("gpt").chat(user_input, sender)
            if response:
                logger.log(f"🤖 AI: {response}", "MSG", fallback_text=f"AI: {response}")
            else:
                logger.log(
                    "🤖 AI: (no response)", "MSG", fallback_text="AI: (no response)"
                )
        except Exception as e:
            logger.error(f"AI chat error: {e}")

    def _console_connect(self, *args) -> str:
        """Console command to connect to servers."""
        if not args:
            # Connect to all configured servers
            if not self.server_manager.servers:
                return "No servers configured. Load configurations first."

            self.server_manager.connect_to_servers()
            connected_servers = [
                name
                for name, thread in self.server_manager.server_threads.items()
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
                self.server_manager.add_server_and_connect(
                    server_name, server_host, server_port, channels, use_tls=use_tls
                )
                return f"Added and connected to {server_name} ({server_host}:{server_port})"
            except Exception as e:
                logger.error(f"Error connecting to new server: {e}")
                return f"Error: {e}"
        else:
            return "Usage: !connect [server_name host [port] [channels] [tls]]"

    def _console_disconnect(self, *args) -> str:
        """Console command to disconnect from servers."""
        if not any(
            thread.is_alive() for thread in self.server_manager.server_threads.values()
        ):
            return "No servers currently connected"

        if not args:
            # Disconnect from all servers
            self.server_manager.disconnect_from_servers()
            return "Disconnected from all servers"
        else:
            # Disconnect from specific servers
            server_names = list(args)
            self.server_manager.disconnect_from_servers(server_names)
            return f"Disconnected from: {', '.join(server_names)}"

    def _console_status(self, *args) -> str:
        """Console command to show connection status."""
        if not self.server_manager.servers:
            return "No servers configured"

        status_lines = ["Server Status:"]
        for name, server in self.server_manager.servers.items():
            thread = self.server_manager.server_threads.get(name)
            if thread and thread.is_alive():
                connected = "✅ Connected" if server.connected else "🔄 Connecting"
            else:
                connected = "❌ Disconnected"
            status_lines.append(
                f"  {name} ({server.config.host}:{server.config.port}): {connected}"
            )

        return "\n".join(status_lines)

    def _console_join_or_part_channel(self, channel_name: str) -> str:
        """Console command to join or part a channel."""
        # Ensure channel name has # prefix
        if not channel_name.startswith("#"):
            channel_name = f"#{channel_name}"

        # Find target server (first connected server)
        target_server = None
        server_name = None
        for name, server in self.server_manager.servers.items():
            if (
                name in self.server_manager.server_threads
                and self.server_manager.server_threads[name].is_alive()
                and server.connected
            ):
                target_server = server
                server_name = name
                break

        if not target_server:
            return "No connected servers available. Use !connect first."

        # Initialize joined channels for this server if needed
        if server_name not in self.server_manager.joined_channels:
            self.server_manager.joined_channels[server_name] = []

        # Check if already in channel
        if channel_name in self.server_manager.joined_channels[server_name]:
            # Part the channel
            try:
                target_server.part_channel(channel_name)
                self.server_manager.joined_channels[server_name].remove(channel_name)

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
                self.server_manager.joined_channels[server_name].append(channel_name)

                # Set as active channel
                self.active_channel = channel_name
                self.active_server = server_name

                return f"Joined {channel_name} on {server_name} (now active)"
            except Exception as e:
                return f"Error joining {channel_name}: {e}"

    def _console_send_to_channel(self, message: str) -> str:
        """Send a message to the currently active channel."""
        if not self.active_channel or not self.active_server:
            return "No active channel. Use #channel to join and activate a channel."

        server = self.server_manager.get_server(self.active_server)
        if not server or not server.connected:
            return f"Server {self.active_server} is not connected."

        try:
            server.send_message(self.active_channel, message)
            return f"[{self.active_server}:{self.active_channel}] <{self.server_manager.bot_name}> {message}"
        except Exception as e:
            return f"Error sending message: {e}"

    def _get_channel_status(self) -> str:
        """Get status of joined channels and active channel."""
        joined_channels = self.server_manager.get_joined_channels()
        if not joined_channels:
            return "No channels joined."

        status_lines = ["Channel Status:"]
        for server_name, channels in joined_channels.items():
            if channels:
                server = self.server_manager.get_server(server_name)
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

    def _create_console_bot_functions(self) -> Dict[str, Any]:
        """Create bot functions dictionary for console commands."""
        return {
            # Core functions
            "notice_message": lambda msg, irc=None, target=None: logger.msg(msg),
            "log": logger.msg,
            "send_weather": lambda irc, channel, location: self._console_weather(
                location
            ),
            "send_electricity_price": lambda irc, channel, args: self._console_electricity(
                args
            ),
            "get_crypto_price": self.message_handler._get_crypto_price,
            "send_scheduled_message": self.message_handler._send_scheduled_message,
            "get_eurojackpot_numbers": self.message_handler._get_eurojackpot_numbers,
            "search_youtube": self.message_handler._search_youtube,
            "handle_ipfs_command": self.message_handler._handle_ipfs_command,
            "load_leet_winners": self.message_handler._load_leet_winners,
            "save_leet_winners": self.message_handler._save_leet_winners,
            "chat_with_gpt": lambda msg, sender="Console": (
                self.service_manager.get_service("gpt").chat(msg, sender)
                if self.service_manager.is_service_available("gpt")
                else "AI not available"
            ),
            "BOT_VERSION": self._get_current_version(),
            "server_name": "console",
            "stop_event": self.stop_event,
            "set_quit_message": lambda msg: (
                setattr(self.server_manager, "quit_message", msg)
                or
                # Also set on individual servers for consistency
                [
                    setattr(server, "quit_message", msg)
                    for server in self.server_manager.get_all_servers().values()
                ]
            )
            and None,
            "set_openai_model": self._set_openai_model,
            "connect": self._console_connect,
            "disconnect": self._console_disconnect,
            "status": self._console_status,
            "channels": self._get_channel_status,
            "join_channel": self._console_join_or_part_channel,
            "send_to_channel": self._console_send_to_channel,
            "bot_manager": None,  # Will be set by main bot manager
            "bac_tracker": self.message_handler.bac_tracker,
            "drink_tracker": self.message_handler.drink_tracker,
            "general_words": self.message_handler.general_words,
            "tamagotchi": self.message_handler.tamagotchi,
            "data_manager": self.message_handler.data_manager,
            "subscriptions": self.message_handler._get_subscriptions_module(),
        }

    def _get_current_version(self) -> str:
        """Get the current bot version from VERSION file."""
        try:
            with open("VERSION", "r", encoding="utf-8") as f:
                version = f.read().strip()
                # Basic validation
                import re

                if re.match(r"^\d+\.\d+\.\d+$", version):
                    return version
                else:
                    return "2.2.0"  # Fallback version
        except (FileNotFoundError, IOError):
            return "2.2.0"  # Fallback version

    def _set_openai_model(self, model: str) -> str:
        """Set the OpenAI model used by the GPT service and persist to .env."""
        try:
            gpt_service = self.service_manager.get_service("gpt")
            if not gpt_service:
                return "AI chat is not available (no OpenAI API key configured)"

            old = getattr(gpt_service, "model", None)
            gpt_service.model = model
            # Persist to environment and .env file
            os.environ["OPENAI_MODEL"] = model
            persisted = self._update_env_file("OPENAI_MODEL", model)
            logger.info(f"OpenAI model changed from {old} to {model}")
            if persisted:
                return f"OpenAI model set to '{model}' (persisted)"
            else:
                return f"OpenAI model set to '{model}' (session only)"
        except Exception as e:
            logger.error(f"Error setting OpenAI model: {e}")
            return f"Failed to set OpenAI model: {e}"

    def _console_weather(self, location: str):
        """Console weather command."""
        weather_service = self.service_manager.get_service("weather")
        if not weather_service:
            logger.error("Weather service not available (no WEATHER_API_KEY)")
            return

        try:
            weather_data = weather_service.get_weather(location)
            response = weather_service.format_weather_message(weather_data)
            logger.info(f"Weather: {response}")
        except Exception as e:
            logger.error(f"Weather error: {e}")

    def _console_electricity(self, args):
        """Console electricity price command."""
        electricity_service = self.service_manager.get_service("electricity")
        if not electricity_service:
            logger.error("Electricity service not available (no ELECTRICITY_API_KEY)")
            return

        try:
            import datetime

            current_hour = datetime.datetime.now().hour
            price_data = electricity_service.get_electricity_price(hour=current_hour)
            response = electricity_service.format_price_message(price_data)
            logger.info(f"Electricity: {response}")
        except Exception as e:
            logger.error(f"Electricity error: {e}")

    def _update_env_file(self, key: str, value: str) -> bool:
        """Update a key-value pair in the .env file. Creates the file if it doesn't exist."""
        env_file = ".env"
        try:
            # Create .env file if it doesn't exist
            if not os.path.exists(env_file):
                with open(env_file, "w", encoding="utf-8") as f:
                    f.write("")

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
            logger.error(f"Could not update .env file: {e}")
            return False

    def shutdown(self):
        """Shutdown the console manager."""
        logger.info("Shutting down console manager...")
        # Save command history
        self._save_command_history()
        logger.info("Console manager shutdown complete")


def create_console_manager(
    service_manager, message_handler, server_manager, stop_event: threading.Event
) -> ConsoleManager:
    """
    Factory function to create a console manager instance.

    Args:
        service_manager: ServiceManager instance
        message_handler: MessageHandler instance
        server_manager: ServerManager instance
        stop_event: Event to signal shutdown

    Returns:
        ConsoleManager instance
    """
    return ConsoleManager(service_manager, message_handler, server_manager, stop_event)
