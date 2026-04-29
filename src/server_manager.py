"""
Server Manager Module

Handles server connection management, channel operations, and server lifecycle
extracted from bot_manager.py.
"""

import os
import threading
from typing import Dict, List, Optional

from config import AUTO_CONNECT, get_config
from logger import get_logger
from server import Server

logger = get_logger("ServerManager")


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

    def __init__(self, bot_name: str, stop_event: threading.Event, bot_config=None):
        """
        Initialize the server manager.

        Args:
            bot_name: The bot's nickname
            stop_event: Event to signal shutdown
            bot_config: Global bot configuration
        """
        self.bot_name = bot_name
        self.stop_event = stop_event
        self.bot_config = bot_config

        # Server storage
        self.servers: Dict[str, Server] = {}
        self.server_threads: Dict[str, threading.Thread] = {}

        # Channel tracking
        self.joined_channels: Dict[str, List[str]] = (
            {}
        )  # server_name -> list of channels

        # Connection settings
        if self.bot_config:
            self.auto_connect = self.bot_config.auto_connect
        else:
            self.auto_connect = os.getenv(
                "AUTO_CONNECT", str(AUTO_CONNECT)
            ).lower() in (
                "true",
                "1",
                "yes",
                "on",
            )
        if self.bot_config:
            self.quit_message = self.bot_config.quit_message
        else:
            self.quit_message = os.getenv("QUIT_MESSAGE", "Disconnecting")

        # Midnight scheduler
        self.midnight_scheduler_thread = None
        self._scheduler_running = False

        # Load server configurations
        self._load_server_configurations()

        logger.info(
            f"Server manager initialized with {len(self.servers)} server configurations"
        )

    def _load_server_configurations(self):
        """Load server configurations from environment."""
        server_configs = get_config().servers
        logger.info(f"Loading {len(server_configs)} server configurations")

        if not server_configs:
            logger.error("No server configurations found!")
            return

        # Create Server instances
        for config in server_configs:
            server = Server(config, self.bot_name, self.stop_event, self.bot_config)
            # Set the quit message
            server.quit_message = self.quit_message
            self.servers[config.name] = server
            self.joined_channels[config.name] = []
            logger.info(
                f"Loaded server configuration: {config.name} ({config.host}:{config.port})"
            )

        logger.info(f"Server manager auto_connect: {self.auto_connect}")

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
        logger.info(
            f"Starting servers, auto_connect={self.auto_connect}, servers={list(self.servers.keys())}"
        )

        if not self.servers:
            logger.error("No servers configured")
            return False

        # Only auto-connect if explicitly enabled
        if self.auto_connect:
            logger.info("Auto-connect enabled, connecting to servers...")
            self.connect_to_servers()
            logger.info(
                f"Server manager started with {len(self.servers)} servers (auto-connected)"
            )
        else:
            logger.info(
                f"Server manager started with {len(self.servers)} servers configured (not connected)"
            )
            logger.info("🔌 Use !connect to connect to servers")

        # Start midnight scheduler
        self._start_midnight_scheduler()

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
                    logger.info(f"Sent quit command to {server_name}")
                    server.quit(quit_msg)
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
        server = Server(config, self.bot_name, self.stop_event, self.bot_config)
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

    def _start_midnight_scheduler(self):
        """Start the midnight scheduler thread."""
        if self._scheduler_running:
            logger.warning("Midnight scheduler already running")
            return

        self._scheduler_running = True
        self.midnight_scheduler_thread = threading.Thread(
            target=self._midnight_scheduler_loop, name="MidnightScheduler", daemon=True
        )
        self.midnight_scheduler_thread.start()
        logger.info("🌙 Midnight scheduler started")

    def _midnight_scheduler_loop(self):
        """Main loop for midnight scheduler."""
        import time
        from datetime import datetime, timedelta

        while not self.stop_event.is_set() and self._scheduler_running:
            try:
                # Check if it's time for lag measurement (1:01:00.010101010 - 1:01:01.010101010)
                now = datetime.now()

                # Target time: 1:01:01.010101010 AM
                target_time = now.replace(hour=1, minute=1, second=1, microsecond=10101)

                # If we've passed 1:01:01 today, target tomorrow's 1:01:01
                if now > target_time:
                    target_time = target_time + timedelta(days=1)

                # Calculate time until target
                time_until_target = target_time - now

                # If we're in the 10-second window before target time, measure lag
                if 0 < time_until_target.total_seconds() <= 10:
                    self._measure_and_send_dreams()

                # Sleep for 1 second to avoid busy waiting
                self.stop_event.wait(1)

            except Exception as e:
                logger.error(f"Error in midnight scheduler: {e}")
                self.stop_event.wait(1)

    def _measure_and_send_dreams(self):
        """Measure lag and send dreams at 1:01:01.010101010."""
        import time
        from datetime import datetime, timedelta

        try:
            # Measure lag to each connected server
            lag_measurements = {}
            for server_name, server in self.get_connected_servers().items():
                if server.connected:
                    lag_ns = self._measure_server_lag(server)
                    if lag_ns is not None:
                        lag_measurements[server_name] = lag_ns
                        logger.debug(f"Lag to {server_name}: {lag_ns:,} ns")

            # Calculate average lag
            if lag_measurements:
                avg_lag_ns = sum(lag_measurements.values()) / len(lag_measurements)
                logger.info(
                    f"Average lag: {avg_lag_ns:,.0f} ns ({avg_lag_ns/1_000_000:.3f} ms)"
                )
            else:
                avg_lag_ns = 0
                logger.warning("No lag measurements available")

            # Wait until exactly 1:01:01.010101010 minus average lag
            now = datetime.now()

            # Target time: 1:01:01.010101010 AM
            target_time = now.replace(hour=1, minute=1, second=1, microsecond=10101)

            # If we've passed 1:01:01 today, target tomorrow's 1:01:01
            if now > target_time:
                target_time = target_time + timedelta(days=1)

            # Calculate optimal send time
            send_time = target_time - timedelta(seconds=avg_lag_ns / 1_000_000_000)

            # Wait until send time
            time_until_send = (send_time - datetime.now()).total_seconds()
            if time_until_send > 0:
                self.stop_event.wait(time_until_send)

            # Send dreams to enabled channels
            self._send_midnight_dreams()

        except Exception as e:
            logger.error(f"Error in dream sending: {e}")

    def _measure_server_lag(self, server):
        """Measure lag to a specific server."""
        import time

        try:
            # Send a simple PING command and measure round-trip time
            start_time = time.time_ns()

            # Send PING to server
            if hasattr(server, "send") and callable(getattr(server, "send", None)):
                ping_msg = f"PING {int(time.time())}\r\n"
                server.send(ping_msg.encode("utf-8"))

                # For now, we'll use a basic timing approach
                # In a real implementation, we'd wait for PONG response
                end_time = time.time_ns()
                return end_time - start_time

        except Exception as e:
            logger.warning(f"Failed to measure lag to {server.config.name}: {e}")
            return None

        return None

    def _send_midnight_dreams(self):
        """Send dreams to all enabled channels."""
        try:
            # Get enabled channels from state
            from config import get_config

            config = get_config()
            state = config.data_manager.load_state()
            enabled_channels = state.get("dream_channels", [])

            if not enabled_channels:
                logger.debug("No channels have dreams enabled")
                return

            # Get dream service
            from services.dream_service import create_dream_service

            dream_service = create_dream_service(config.data_manager)

            # Send dreams to each enabled channel
            for channel in enabled_channels:
                try:
                    # Extract server name from channel (format: #channel@server or #channel)
                    if "@" in channel:
                        channel_name, server_name = channel.split("@", 1)
                    else:
                        # Use first connected server if no server specified
                        connected_servers = self.get_connected_servers()
                        if not connected_servers:
                            continue
                        server_name = list(connected_servers.keys())[0]
                        channel_name = channel

                    # Ensure channel has # prefix
                    if not channel_name.startswith("#"):
                        channel_name = f"#{channel_name}"

                    # Generate and send dream
                    dream_content = dream_service.generate_dream(
                        server_name, channel_name, "surrealist", "narrative"
                    )

                    # Send to channel
                    server = self.servers.get(server_name)
                    if server and server.connected:
                        server.send_message(channel_name, dream_content)
                        logger.info(
                            f"🌙 Sent midnight dream to {channel_name}@{server_name}"
                        )
                    else:
                        logger.warning(
                            f"Server {server_name} not connected for {channel_name}"
                        )

                except Exception as e:
                    logger.error(f"Failed to send dream to {channel}: {e}")

        except Exception as e:
            logger.error(f"Error sending midnight dreams: {e}")

    def shutdown(self, quit_message: Optional[str] = None):
        """
        Shutdown all servers gracefully.

        Args:
            quit_message: Optional custom quit message
        """
        logger.info("Shutting down server manager...")

        # Stop midnight scheduler
        self._scheduler_running = False
        if self.midnight_scheduler_thread and self.midnight_scheduler_thread.is_alive():
            self.midnight_scheduler_thread.join(timeout=1.0)

        # Disconnect from all servers
        self.disconnect_from_servers(quit_message=quit_message)

        # Clear server storage
        self.servers.clear()
        self.server_threads.clear()
        self.joined_channels.clear()

        logger.info("Server manager shutdown complete")


def create_server_manager(
    bot_name: str, stop_event: threading.Event, bot_config=None
) -> ServerManager:
    """
    Factory function to create a server manager instance.

    Args:
        bot_name: The bot's nickname
        stop_event: Event to signal shutdown
        bot_config: Global bot configuration

    Returns:
        ServerManager instance
    """
    return ServerManager(bot_name, stop_event, bot_config)
