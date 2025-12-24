"""
Server Manager Module

Handles server connection management, channel operations, and server lifecycle
extracted from bot_manager.py.
"""

import os
import threading
from typing import Dict, List, Optional

import logger
from config import get_config
from server import Server

logger = logger.get_logger("ServerManager")


class ServerManager:
    """
    Manages IRC server connections and channel operations.

    This class handles:
    - Server configuration loading
    - Server connection lifecycle (connect/disconnect)
    - Channel management and joining
    - Server status tracking
    - Connection pooling
    """

    def __init__(self, bot_name: str, stop_event: threading.Event):
        """
        Initialize the server manager.

        Args:
            bot_name: The bot's nickname
            stop_event: Event to signal shutdown
        """
        self.bot_name = bot_name
        self.stop_event = stop_event

        # Server storage
        self.servers: Dict[str, Server] = {}
        self.server_threads: Dict[str, threading.Thread] = {}

        # Channel tracking
        self.joined_channels: Dict[str, List[str]] = (
            {}
        )  # server_name -> list of channels

        # Connection settings
        self.auto_connect = os.getenv("AUTO_CONNECT", "false").lower() in (
            "true",
            "1",
            "yes",
            "on",
        )
        self.quit_message = os.getenv("QUIT_MESSAGE", "Disconnecting")

        # Load server configurations
        self._load_server_configurations()

        logger.info(
            f"Server manager initialized with {len(self.servers)} server configurations"
        )

    def _load_server_configurations(self):
        """Load server configurations from environment."""
        server_configs = get_config().servers

        if not server_configs:
            logger.error("No server configurations found!")
            return

        # Create Server instances
        for config in server_configs:
            server = Server(config, self.bot_name, self.stop_event)
            # Set the quit message
            server.quit_message = self.quit_message
            self.servers[config.name] = server
            self.joined_channels[config.name] = []
            logger.info(
                f"Loaded server configuration: {config.name} ({config.host}:{config.port})"
            )

    def register_message_callbacks(self, message_handler):
        """
        Register message callbacks with all servers.

        Args:
            message_handler: MessageHandler instance with callback methods
        """
        for server_name, server in self.servers.items():
            # Register message callback for command processing
            server.register_callback("message", message_handler.handle_message)

            # Register notice callback for processing notices
            server.register_callback("notice", message_handler._handle_notice)

            # Register join callback for user tracking
            server.register_callback("join", message_handler._handle_join)

            # Register part callback
            server.register_callback("part", message_handler._handle_part)

            # Register quit callback
            server.register_callback("quit", message_handler._handle_quit)

            # Register numeric callback for handling IRC numeric responses
            server.register_callback("numeric", message_handler._handle_numeric)

            logger.info(f"Registered callbacks for server: {server_name}")

    def start_servers(self) -> bool:
        """
        Start all configured servers.

        Returns:
            True if configurations were loaded successfully, False otherwise
        """
        if not self.servers:
            logger.error("No servers configured")
            return False

        # Only auto-connect if explicitly enabled
        if self.auto_connect:
            self.connect_to_servers()
            logger.info(
                f"Server manager started with {len(self.servers)} servers (auto-connected)"
            )
        else:
            logger.info(
                f"Server manager started with {len(self.servers)} servers configured (not connected)"
            )
            logger.info("🔌 Use !connect to connect to servers")

        return True

    def connect_to_servers(self, server_names: Optional[List[str]] = None) -> bool:
        """
        Connect to configured servers or specific servers by name.

        Args:
            server_names: Optional list of server names to connect to.
                         If None, connects to all configured servers.

        Returns:
            True if any servers were connected, False otherwise
        """
        servers_to_connect = server_names or list(self.servers.keys())
        connected_any = False

        for server_name in servers_to_connect:
            if server_name not in self.servers:
                logger.warning(f"Server {server_name} not found in configurations")
                continue

            if (
                server_name in self.server_threads
                and self.server_threads[server_name].is_alive()
            ):
                logger.info(f"Server {server_name} is already connected")
                continue

            server = self.servers[server_name]
            thread = threading.Thread(
                target=server.start, name=f"Server-{server_name}", daemon=False
            )
            thread.start()
            self.server_threads[server_name] = thread
            connected_any = True
            logger.info(f"Started server thread for {server_name}")

        return connected_any

    def disconnect_from_servers(
        self,
        server_names: Optional[List[str]] = None,
        quit_message: Optional[str] = None,
    ) -> bool:
        """
        Disconnect from servers.

        Args:
            server_names: Optional list of server names to disconnect from.
                         If None, disconnects from all servers.
            quit_message: Optional custom quit message.

        Returns:
            True if any servers were disconnected, False otherwise
        """
        servers_to_disconnect = server_names or list(self.servers.keys())
        quit_msg = quit_message or self.quit_message
        disconnected_any = False

        for server_name in servers_to_disconnect:
            if server_name not in self.servers:
                logger.warning(f"Server {server_name} not found")
                continue

            server = self.servers[server_name]
            if server.connected:
                try:
                    server.quit(quit_msg)
                    logger.info(f"Sent quit command to {server_name}")
                    disconnected_any = True
                except Exception as e:
                    logger.error(f"Error quitting server {server_name}: {e}")

            # Wait for thread to finish
            if server_name in self.server_threads:
                thread = self.server_threads[server_name]
                thread.join(timeout=5.0)
                if thread.is_alive():
                    logger.warning(
                        f"Server thread {server_name} did not finish cleanly"
                    )
                del self.server_threads[server_name]

        return disconnected_any

    def add_server_and_connect(
        self,
        name: str,
        host: str,
        port: int = 6667,
        channels: Optional[List[str]] = None,
        keys: Optional[List[str]] = None,
        use_tls: bool = False,
    ) -> bool:
        """
        Add a new server configuration and connect to it.

        Args:
            name: Server name
            host: Server hostname
            port: Server port (default 6667)
            channels: List of channels to join
            keys: List of channel keys
            use_tls: Whether to use TLS/SSL

        Returns:
            True if server was added and connected successfully
        """
        from server import ServerConfig

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
        self.joined_channels[name] = []

        # Register callbacks for the new server (will be done by caller)
        # Note: Callbacks need to be registered after message_handler is available

        # Connect to the new server
        success = self.connect_to_servers([name])

        if success:
            logger.info(f"Added and connected to new server: {name} ({host}:{port})")

        return success

    def get_server(self, name: str) -> Optional[Server]:
        """
        Get a server instance by name.

        Args:
            name: Server name

        Returns:
            Server instance or None if not found
        """
        return self.servers.get(name)

    def get_all_servers(self) -> Dict[str, Server]:
        """
        Get all server instances.

        Returns:
            Dictionary of server name -> Server instance
        """
        return self.servers.copy()

    def get_connected_servers(self) -> Dict[str, Server]:
        """
        Get all connected server instances.

        Returns:
            Dictionary of server name -> Server instance for connected servers
        """
        return {
            name: server
            for name, server in self.servers.items()
            if name in self.server_threads
            and self.server_threads[name].is_alive()
            and server.connected
        }

    def is_server_connected(self, server_name: str) -> bool:
        """
        Check if a specific server is connected.

        Args:
            server_name: Name of the server to check

        Returns:
            True if server is connected, False otherwise
        """
        if server_name not in self.servers:
            return False

        thread = self.server_threads.get(server_name)
        server = self.servers[server_name]

        return thread is not None and thread.is_alive() and server.connected

    def get_server_status(self, server_name: Optional[str] = None) -> Dict[str, any]:
        """
        Get status information for servers.

        Args:
            server_name: Specific server name, or None for all servers

        Returns:
            Dictionary with server status information
        """
        if server_name:
            if server_name not in self.servers:
                return {"error": f"Server '{server_name}' not found"}

            server = self.servers[server_name]
            thread = self.server_threads.get(server_name)

            return {
                "name": server_name,
                "host": server.config.host,
                "port": server.config.port,
                "connected": server.connected,
                "thread_alive": thread.is_alive() if thread else False,
                "channels": self.joined_channels.get(server_name, []),
            }

        # Return status for all servers
        status = {}
        for name, server in self.servers.items():
            thread = self.server_threads.get(name)
            status[name] = {
                "host": server.config.host,
                "port": server.config.port,
                "connected": server.connected,
                "thread_alive": thread.is_alive() if thread else False,
                "channels": self.joined_channels.get(name, []),
            }

        return status

    def send_to_all_servers(self, target: str, message: str):
        """
        Send a message to the same target on all connected servers.

        Args:
            target: Target channel/nick
            message: Message to send
        """
        for server in self.servers.values():
            try:
                server.send_message(target, message)
            except Exception as e:
                logger.error(f"Error sending to {server.config.name}: {e}")

    def send_notice_to_all_servers(self, target: str, message: str):
        """
        Send a notice to the same target on all connected servers.

        Args:
            target: Target channel/nick
            message: Notice to send
        """
        for server in self.servers.values():
            try:
                server.send_notice(target, message)
            except Exception as e:
                logger.error(f"Error sending notice to {server.config.name}: {e}")

    def join_channel(self, server_name: str, channel: str, key: str = ""):
        """
        Join a channel on a specific server.

        Args:
            server_name: Name of the server
            channel: Channel name (with or without #)
            key: Channel key if required
        """
        if server_name not in self.servers:
            logger.warning(f"Server '{server_name}' not found")
            return False

        server = self.servers[server_name]

        # Ensure channel has # prefix
        if not channel.startswith("#"):
            channel = f"#{channel}"

        try:
            server.join_channel(channel, key)
            if channel not in self.joined_channels[server_name]:
                self.joined_channels[server_name].append(channel)
            logger.info(f"Joined {channel} on {server_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to join {channel} on {server_name}: {e}")
            return False

    def part_channel(self, server_name: str, channel: str, reason: str = ""):
        """
        Leave a channel on a specific server.

        Args:
            server_name: Name of the server
            channel: Channel name (with or without #)
            reason: Part reason/message
        """
        if server_name not in self.servers:
            logger.warning(f"Server '{server_name}' not found")
            return False

        server = self.servers[server_name]

        # Ensure channel has # prefix
        if not channel.startswith("#"):
            channel = f"#{channel}"

        try:
            server.part_channel(channel, reason)
            if channel in self.joined_channels[server_name]:
                self.joined_channels[server_name].remove(channel)
            logger.info(f"Parted {channel} on {server_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to part {channel} on {server_name}: {e}")
            return False

    def get_joined_channels(
        self, server_name: Optional[str] = None
    ) -> Dict[str, List[str]]:
        """
        Get joined channels for servers.

        Args:
            server_name: Specific server name, or None for all servers

        Returns:
            Dictionary of server_name -> list of channels
        """
        if server_name:
            return {server_name: self.joined_channels.get(server_name, [])}
        return self.joined_channels.copy()

    def wait_for_shutdown(self):
        """Wait for all server threads to finish during shutdown."""
        try:
            while not self.stop_event.is_set():
                # Check if we have any active server threads
                active_server_threads = [
                    thread
                    for thread in self.server_threads.values()
                    if thread.is_alive()
                ]

                # If no server threads, we should exit
                if not active_server_threads:
                    if self.stop_event.is_set():
                        logger.debug("Stop event set, exiting server manager wait loop")
                        break
                    # If no active threads but stop event not set, wait a bit more
                    self.stop_event.wait(1)
                    continue

                # Wait for threads to finish
                self.stop_event.wait(0.1)  # Check frequently for faster response

        except Exception as e:
            logger.error(f"Error in server manager wait loop: {e}")

    def shutdown(self, quit_message: Optional[str] = None):
        """
        Shutdown all servers gracefully.

        Args:
            quit_message: Optional custom quit message
        """
        logger.info("Shutting down server manager...")

        # Disconnect from all servers
        self.disconnect_from_servers(quit_message=quit_message)

        # Clear server storage
        self.servers.clear()
        self.server_threads.clear()
        self.joined_channels.clear()

        logger.info("Server manager shutdown complete")


def create_server_manager(bot_name: str, stop_event: threading.Event) -> ServerManager:
    """
    Factory function to create a server manager instance.

    Args:
        bot_name: The bot's nickname
        stop_event: Event to signal shutdown

    Returns:
        ServerManager instance
    """
    return ServerManager(bot_name, stop_event)
