"""
Bot Manager for Multiple IRC Servers

This module provides the BotManager class that orchestrates multiple IRC server
connections and integrates all bot functionality across servers.

This is now a lightweight orchestrator that uses the new modular managers:
- ServiceManager: Handles external service initialization
- MessageHandler: Handles message processing and routing
- ServerManager: Handles server connections and channel management
- ConsoleManager: Handles console/TUI interface and input
"""

import threading
from typing import Optional

import logger
from config import get_config
from message_handler import create_message_handler
from server_manager import create_server_manager
from service_manager import create_service_manager


class BotManager:
    """
    Lightweight orchestrator that coordinates the new modular managers.

    This class:
    1. Initializes all managers (ServiceManager, MessageHandler, ServerManager, ConsoleManager)
    2. Coordinates startup and shutdown between managers
    3. Provides a unified interface for the main application
    """

    def __init__(self, bot_name: str, console_mode: bool = False):
        """
        Initialize the bot manager with all modular managers.

        Args:
            bot_name: The nickname for the bot across all servers
            console_mode: Whether to use console mode (with readline) or TUI mode
        """
        self.bot_name = bot_name
        self.console_mode = console_mode
        self.logger = logger.get_logger("BotManager")

        # Initialize shutdown event
        self.stop_event = threading.Event()

        # Initialize managers in dependency order
        # Initialize console manager FIRST for ultra-fast TUI startup (before ANY logs)
        from console_manager import ConsoleManager

        self.console_manager = ConsoleManager()

        self.logger.info("🚀 Initializing service manager...")
        self.service_manager = create_service_manager()

        # Get data manager from service manager (it has the word tracking components)
        from word_tracking import DataManager

        config = get_config()
        data_manager = DataManager(state_file=config.state_file)

        self.logger.info("📨 Initializing message handler...")
        self.message_handler = create_message_handler(
            self.service_manager, data_manager
        )

        self.logger.info("🌐 Initializing server manager...")
        self.server_manager = create_server_manager(bot_name, self.stop_event)

        # Set remaining dependencies in console manager
        self.console_manager.set_message_handler(self.message_handler)
        self.console_manager.set_server_manager(self.server_manager)
        self.console_manager.set_stop_event(self.stop_event)

        # Register message callbacks
        self.logger.info("🔗 Registering message callbacks...")
        self.server_manager.register_message_callbacks(self.message_handler)

        self.logger.info("✅ BotManager initialization complete!")

    def start(self):
        """Start all managers and begin bot operation."""
        self.logger.info("🚀 Starting bot managers...")

        # Start servers
        if not self.server_manager.start_servers():
            return False

        # Start console listener if in console mode
        if self.console_mode:
            self.console_manager.start_console_listener()

        self.logger.info("🎯 Bot startup complete!")
        return True

    def stop(self, quit_message: Optional[str] = None):
        """Stop all managers and shutdown gracefully."""
        self.logger.info("🛑 Shutting down bot managers...")

        # Set stop event
        self.stop_event.set()

        # Shutdown console manager
        if hasattr(self.console_manager, "shutdown"):
            self.console_manager.shutdown()

        # Shutdown server manager
        self.server_manager.shutdown(quit_message)

        self.logger.info("✅ Bot shutdown complete")

    def wait_for_shutdown(self):
        """Wait for all managers to complete shutdown."""
        # Wait for servers to finish
        self.server_manager.wait_for_shutdown()

    # Delegate methods to appropriate managers for backward compatibility
    def get_server(self, name: str):
        """Get server by name."""
        return self.server_manager.get_server(name)

    def get_all_servers(self):
        """Get all servers."""
        return self.server_manager.get_all_servers()

    def connect_to_servers(self, server_names=None):
        """Connect to servers."""
        return self.server_manager.connect_to_servers(server_names)

    def disconnect_from_servers(self, server_names=None, quit_message=None):
        """Disconnect from servers."""
        return self.server_manager.disconnect_from_servers(server_names, quit_message)

    def add_server_and_connect(
        self, name, host, port=6667, channels=None, keys=None, use_tls=False
    ):
        """Add server and connect."""
        return self.server_manager.add_server_and_connect(
            name, host, port, channels, keys, use_tls
        )


def create_bot_manager(bot_name: str, console_mode: bool = False) -> BotManager:
    """
    Factory function to create a bot manager instance.

    Args:
        bot_name: The nickname for the bot across all servers
        console_mode: Whether to use console mode (with readline) or TUI mode

    Returns:
        BotManager instance
    """
    return BotManager(bot_name, console_mode)
