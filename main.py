"""
Main module for the IRC bot.

This module orchestrates the multi-server IRC bot, managing server connections,
console commands, auxiliary threads (e.g., leet countdown), and graceful shutdown.
"""

import os
import sys
import threading
import signal
import time
from datetime import datetime, timedelta
import pickle
import json
import argparse

from config import get_server_configs, get_api_key
from server import Server
from message_handlers import (
    log,
    output_message,
    split_message_intelligently,
    handle_weather,
    handle_time,
    handle_echo,
    handle_word_count,
    handle_top_words,
    handle_leaderboard,
    handle_euribor,
    handle_leet_winners,
    handle_url_title,
    handle_leet,
    handle_kraks,
    handle_ekavika,
    handle_crypto,
    handle_youtube_search,
    handle_eurojackpot,
    send_weather,
    send_electricity_price,
    search_youtube,
    chat_with_gpt,
)


class ServerManager:
    """Manages multiple IRC server connections."""

    def __init__(self, show_api_keys: bool = False):
        """
        Initialize the ServerManager.

        Args:
            show_api_keys (bool): Whether to display API keys during initialization
        """
        if sys.gettrace():
            self.bot_name = "jL3b2"
        else:
            self.bot_name = "jL3b2"
        self.stop_event = threading.Event()
        self.servers = []
        self.server_configs = get_server_configs()
        self.statuses = {}
        self.show_api_keys = show_api_keys
        self.initialize_servers()

    def initialize_servers(self):
        """Initialize server instances from configurations."""
        for server_config in self.server_configs:
            server = Server(server_config, self.bot_name, self.stop_event)
            server.set_status_callback(self._update_status)
            self.setup_handlers(server)
            self.servers.append(server)
            self.statuses[server_config.name] = False
            log(
                f"Initialized server {server_config.name} ({server_config.host})",
                "INFO",
            )

        if self.show_api_keys:
            self.display_api_keys()

    def _update_status(self, server_name: str, connected: bool):
        """Update the connection status of a server."""
        self.statuses[server_name] = connected
        log(
            f"Server {server_name} status: {'Connected' if connected else 'Disconnected'}",
            "INFO",
        )

    def setup_handlers(self, server):
        """Register command handlers for a server."""
        handlers = {
            "sää": handle_weather,
            "aika": handle_time,
            "kaiku": handle_echo,
            "sana": handle_word_count,
            "top": handle_top_words,
            "leaderboard": handle_leaderboard,
            "euribor": handle_euribor,
            "leet_winners": handle_leet_winners,
            "title": handle_url_title,
            "leet": handle_leet,
            "kraks": handle_kraks,
            "ekavika": handle_ekavika,
            "crypto": handle_crypto,
            "youtube": handle_youtube_search,
            "eurojackpot": handle_eurojackpot,
        }
        for command, handler in handlers.items():
            server.register_handler(command, handler)
            log(f"Registered handler for {command} on {server.config.name}", "DEBUG")

    def display_api_keys(self):
        """Display API keys for debugging."""
        api_keys = {
            "WEATHER_API_KEY": get_api_key("WEATHER_API_KEY"),
            "ELECTRICITY_API_KEY": get_api_key("ELECTRICITY_API_KEY"),
            "OPENAI_API_KEY": get_api_key("OPENAI_API_KEY"),
            "YOUTUBE_API_KEY": get_api_key("YOUTUBE_API_KEY"),
        }
        for key_name, key_value in api_keys.items():
            status = "OK" if key_value else "MISSING"
            log(f"{key_name}: {status}", "INFO")

    def start_servers(self):
        """Start all server connections in separate threads."""
        for server in self.servers:
            server_thread = threading.Thread(
                target=server.start, daemon=True, name=f"{server.config.name}-main"
            )
            server_thread.start()
            log(f"Started server thread for {server.config.name}", "INFO")

    def stop_servers(self):
        """Stop all server connections."""
        self.stop_event.set()
        for server in self.servers:
            server.stop()
            log(f"Stopped server {server.config.name}", "INFO")


def listen_for_commands(
    stop_event: threading.Event, server_manager: ServerManager = None
):
    """
    Listen for console commands and process them.

    Args:
        stop_event: Event to signal shutdown
        server_manager: ServerManager instance for accessing servers
    """
    try:
        while not stop_event.is_set():
            user_input = input("")
            if not user_input:
                continue

            if user_input.lower() == "quit":
                log("Exiting bot...", "INFO")
                stop_event.set()
                break

            if user_input.startswith("!"):
                command_parts = user_input.split(" ", 2)
                command = command_parts[0].lower()
                target_server = None
                args = command_parts[1] if len(command_parts) > 1 else ""

                if len(command_parts) > 1 and command_parts[1].startswith("@"):
                    server_name = command_parts[1][1:]
                    args = command_parts[2] if len(command_parts) > 2 else ""
                    if server_manager:
                        for server in server_manager.servers:
                            if server.config.name.lower() == server_name.lower():
                                target_server = server
                                break
                    if not target_server:
                        output_message(f"Server '{server_name}' not found")
                        continue

                log(f"Processing command {command} with args: {args}", "COMMAND")

                if command == "!send" and server_manager:
                    parts = args.split(" ", 1)
                    if len(parts) == 2:
                        channel, message = parts
                        if target_server:
                            target_server.send_message(channel, message)
                            output_message(
                                f"Sent message to {target_server.config.name} {channel}: {message}"
                            )
                        else:
                            for server in server_manager.servers:
                                server.send_message(channel, message)
                            output_message(
                                f"Sent message to all servers {channel}: {message}"
                            )
                    else:
                        output_message("Usage: !send #channel message")

                elif command == "!debug" and server_manager:
                    if target_server:
                        target_server.debug = not target_server.debug
                        output_message(
                            f"Debug mode for {target_server.config.name} set to {target_server.debug}"
                        )
                    else:
                        for server in server_manager.servers:
                            server.debug = not server.debug
                        output_message(
                            f"Debug mode for all servers set to {server_manager.servers[0].debug}"
                        )

                elif command == "!servers" and server_manager:
                    server_list = "\n".join(
                        f"{i+1}. {s.config.name} ({s.config.host}:{s.config.port}) - Connected: {s.connected} - Channels: {', '.join(s.config.channels)}"
                        for i, s in enumerate(server_manager.servers)
                    )
                    output_message(f"Connected servers:\n{server_list}")

                elif command in ("!s", "!sää"):
                    location = args.strip() if args else "Joensuu"
                    result = send_weather(
                        None, None, location
                    )  # Console-only, no server
                    output_message(result)
                    if target_server:
                        for channel in target_server.config.channels:
                            target_server.send_message(channel, result)

                elif command in ("!sahko", "!sähkö"):
                    result = send_electricity_price(None, None, [command, args])
                    output_message(result)
                    if target_server:
                        for channel in target_server.config.channels:
                            target_server.send_message(channel, result)

                elif command == "!youtube" and server_manager:
                    if args:
                        result = search_youtube(None, None, args)
                        output_message(result)
                        if target_server:
                            for channel in target_server.config.channels:
                                target_server.send_message(channel, result)
                    else:
                        output_message("Usage: !youtube <search query>")

                elif command == "!gpt" and server_manager:
                    if args:
                        result = chat_with_gpt(None, None, args)
                        output_message(result)
                        if target_server:
                            for channel in target_server.config.channels:
                                for part in split_message_intelligently(result):
                                    target_server.send_message(channel, part)
                    else:
                        output_message("Usage: !gpt <prompt>")

                else:
                    output_message(f"Unknown command: {command}")

    except (EOFError, KeyboardInterrupt):
        log("Console input interrupted, shutting down...", "INFO")
        stop_event.set()


def countdown(server: Server, channel: str, stop_event: threading.Event):
    """
    Send leet time (13:37) notifications to a channel.

    Args:
        server: Server instance to send messages
        channel: Channel to send notifications to
        stop_event: Event to signal shutdown
    """
    while not stop_event.is_set():
        now = datetime.now()
        leet_time = now.replace(hour=13, minute=37, second=0, microsecond=0)
        if now > leet_time:
            leet_time += timedelta(days=1)

        time_to_leet = (leet_time - now).total_seconds()
        if time_to_leet > 0:
            stop_event.wait(time_to_leet)

        if stop_event.is_set():
            break

        try:
            server.send_message(channel, "Leet time! (13:37)")
            log(f"Sent leet notification to {server.config.name} {channel}", "INFO")
            time.sleep(60)  # Wait to avoid duplicate notifications
        except Exception as e:
            log(f"Error sending leet notification to {channel}: {e}", "ERROR")


def start_auxiliary_threads(server_manager: ServerManager, stop_event: threading.Event):
    """
    Start auxiliary threads for console commands and leet countdowns.

    Args:
        server_manager: ServerManager instance
        stop_event: Event to signal shutdown
    """
    # Start command listener
    command_thread = threading.Thread(
        target=listen_for_commands,
        args=(stop_event, server_manager),
        daemon=True,
        name="command-listener",
    )
    command_thread.start()
    log("Started command listener thread", "INFO")

    # Start leet countdown for specific channels
    for server in server_manager.servers:
        for channel in server.config.channels:
            if channel == "#joensuu":  # Example: Only for #joensuu
                countdown_thread = threading.Thread(
                    target=countdown,
                    args=(server, channel, stop_event),
                    daemon=True,
                    name=f"leet-countdown-{server.config.name}-{channel}",
                )
                countdown_thread.start()
                log(
                    f"Started leet countdown thread for {server.config.name} {channel}",
                    "INFO",
                )


def signal_handler(sig, frame):
    """Handle shutdown signals."""
    log(f"Received signal {sig}, shutting down...", "INFO")
    stop_event.set()


def main():
    """Main entry point for the IRC bot."""
    global stop_event
    stop_event = threading.Event()

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Multi-server IRC bot")
    parser.add_argument(
        "-api", "--show-api-keys", action="store_true", help="Display API keys"
    )
    args = parser.parse_args()

    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Initialize server manager
    server_manager = ServerManager(show_api_keys=args.show_api_keys)

    # Start auxiliary threads
    start_auxiliary_threads(server_manager, stop_event)

    # Start server connections
    server_manager.start_servers()

    # Wait for stop event
    try:
        stop_event.wait()
    except KeyboardInterrupt:
        log("Keyboard interrupt received, shutting down...", "INFO")
        stop_event.set()

    # Stop all servers
    server_manager.stop_servers()

    # Save data (if needed)
    log("Bot shutdown complete", "INFO")
    sys.exit(0)


if __name__ == "__main__":
    main()
