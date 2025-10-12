"""
IRC Client Module

This module provides a clean abstraction for IRC protocol handling,
replacing the scattered IRC code in main.py with a proper class-based approach.
"""

import re
import socket
import threading
import time
import traceback
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional

import logger
from config import ServerConfig, get_config


class IRCMessageType(Enum):
    """Types of IRC messages."""

    PRIVMSG = "PRIVMSG"
    NOTICE = "NOTICE"
    JOIN = "JOIN"
    PART = "PART"
    QUIT = "QUIT"
    NICK = "NICK"
    KICK = "KICK"
    MODE = "MODE"
    PING = "PING"
    PONG = "PONG"
    NUMERIC = "NUMERIC"
    UNKNOWN = "UNKNOWN"


@dataclass
class IRCMessage:
    """Parsed IRC message with all relevant information."""

    raw: str  # Original raw message
    type: IRCMessageType  # Message type
    sender: Optional[str] = None  # Sender nickname (None for server messages)
    sender_host: Optional[str] = None  # Full sender host (nick!user@host)
    target: Optional[str] = None  # Target channel/nick
    text: Optional[str] = None  # Message text content
    command: Optional[str] = None  # IRC command (for numerics, etc.)
    params: List[str] = field(default_factory=list)  # Command parameters
    tags: Dict[str, str] = field(default_factory=dict)  # IRCv3 tags

    @property
    def is_private_message(self) -> bool:
        """Check if this is a private message to the bot."""
        return (
            self.type == IRCMessageType.PRIVMSG
            and self.target
            and not self.target.startswith("#")
        )

    @property
    def is_channel_message(self) -> bool:
        """Check if this is a channel message."""
        return (
            self.type == IRCMessageType.PRIVMSG
            and self.target
            and self.target.startswith("#")
        )

    @property
    def is_command(self) -> bool:
        """Check if this message contains a bot command (starts with !)."""
        return self.text and self.text.startswith("!")

    @property
    def nick(self) -> Optional[str]:
        """Get nickname from sender_host (nick!user@host)."""
        if self.sender_host and "!" in self.sender_host:
            return self.sender_host.split("!")[0]
        return self.sender

    @property
    def user(self) -> Optional[str]:
        """Get username from sender_host (nick!user@host)."""
        if self.sender_host and "!" in self.sender_host and "@" in self.sender_host:
            user_host = self.sender_host.split("!", 1)[1]
            return user_host.split("@")[0]
        return None

    @property
    def host(self) -> Optional[str]:
        """Get hostname from sender_host (nick!user@host)."""
        if self.sender_host and "@" in self.sender_host:
            return self.sender_host.split("@", 1)[1]
        return None


class IRCConnectionState(Enum):
    """IRC connection states."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    AUTHENTICATING = "authenticating"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"


@dataclass
class IRCConnectionInfo:
    """Information about current IRC connection."""

    server_config: ServerConfig
    nickname: str
    state: IRCConnectionState = IRCConnectionState.DISCONNECTED
    connected_at: Optional[float] = None
    last_ping: Optional[float] = None
    channels: List[str] = field(default_factory=list)

    @property
    def uptime(self) -> Optional[float]:
        """Get connection uptime in seconds."""
        if self.connected_at:
            return time.time() - self.connected_at
        return None


class IRCClient:
    """
    Clean IRC client implementation with proper abstraction.
    """

    def __init__(
        self,
        server_config: ServerConfig,
        nickname: str,
        log_callback: Optional[Callable[[str, str], None]] = None,
    ):
        """
        Initialize IRC client.

        Args:
            server_config: Server configuration
            nickname: Bot nickname
            log_callback: Optional logging callback function(message, level)
        """
        self.server_config = server_config
        self.nickname = nickname
        self.log = log_callback or self._default_log

        # Connection state
        self.socket: Optional[socket.socket] = None
        self.connection_info = IRCConnectionInfo(server_config, nickname)
        self._stop_event = threading.Event()
        self._keepalive_thread: Optional[threading.Thread] = None

        # Message handlers
        self._message_handlers: Dict[
            IRCMessageType, List[Callable[[IRCMessage], None]]
        ] = {}
        self._raw_handlers: List[Callable[[str], None]] = []

        # Rate limiting
        self._last_send_time = 0
        self._send_delay = 1.0  # Minimum delay between messages

    def _default_log(self, message: str, level: str = "INFO"):
        """Default logging implementation."""
        # Main log output for irc_client.py
        logger.log(message, level, context="IRC")

    def add_message_handler(
        self, message_type: IRCMessageType, handler: Callable[[IRCMessage], None]
    ):
        """Add a handler for specific message types."""
        if message_type not in self._message_handlers:
            self._message_handlers[message_type] = []
        self._message_handlers[message_type].append(handler)

    def add_raw_handler(self, handler: Callable[[str], None]):
        """Add a handler for raw IRC messages."""
        self._raw_handlers.append(handler)

    def remove_message_handler(
        self, message_type: IRCMessageType, handler: Callable[[IRCMessage], None]
    ):
        """Remove a message handler."""
        if message_type in self._message_handlers:
            try:
                self._message_handlers[message_type].remove(handler)
            except ValueError:
                pass

    def connect(self) -> bool:
        """
        Connect to IRC server and authenticate.

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            self.log(
                f"Connecting to {self.server_config.host}:{self.server_config.port}...",
                "INFO",
            )
            self.connection_info.state = IRCConnectionState.CONNECTING

            # Create socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(30)  # 30 second timeout
            self.socket.connect((self.server_config.host, self.server_config.port))

            # Send authentication
            self.connection_info.state = IRCConnectionState.AUTHENTICATING
            self._send_raw(f"NICK {self.nickname}")
            self._send_raw(f"USER {self.nickname} 0 * :{self.nickname}")

            # Wait for welcome message or error
            welcomed = False
            start_time = time.time()

            while time.time() - start_time < 30 and not welcomed:
                try:
                    data = self.socket.recv(4096)
                    if not data:
                        raise ConnectionError(
                            "Server closed connection during authentication"
                        )

                    response = data.decode("utf-8", errors="ignore")
                    for line in response.strip().split("\r\n"):
                        if not line:
                            continue

                        self.log(f"AUTH: {line}", "DEBUG")

                        # Handle PING during auth
                        if line.startswith("PING"):
                            ping_value = line.split(":", 1)[1].strip()
                            self._send_raw(f"PONG :{ping_value}")
                            continue

                        # Check for nickname conflicts
                        if "Nickname is already in use" in line or " 433 " in line:
                            self.nickname += str(int(time.time()) % 1000)
                            self.connection_info.nickname = self.nickname
                            self._send_raw(f"NICK {self.nickname}")
                            continue

                        # Check for welcome (001) or MOTD end (376/422)
                        if " 001 " in line or " 376 " in line or " 422 " in line:
                            welcomed = True
                            break

                except socket.timeout:
                    continue

            if not welcomed:
                raise ConnectionError("Authentication timeout")

            # Join channels
            self._join_channels()

            # Start keepalive
            self._start_keepalive()

            # Update connection state
            self.connection_info.state = IRCConnectionState.CONNECTED
            self.connection_info.connected_at = time.time()
            self.connection_info.last_ping = time.time()

            self.log(f"Connected successfully as {self.nickname}", "INFO")
            return True

        except Exception as e:
            self.log(f"Connection failed: {e}", "ERROR")
            self.disconnect()
            return False

    def disconnect(self, quit_message: str = "Goodbye!"):
        """
        Disconnect from IRC server.

        Args:
            quit_message: Quit message to send
        """
        if self.connection_info.state == IRCConnectionState.DISCONNECTED:
            return

        self.log("Disconnecting from IRC...", "INFO")
        self.connection_info.state = IRCConnectionState.DISCONNECTING

        # Stop keepalive
        self._stop_event.set()
        if self._keepalive_thread and self._keepalive_thread.is_alive():
            self._keepalive_thread.join(timeout=2)

        # Send QUIT
        try:
            if self.socket:
                self._send_raw(f"QUIT :{quit_message}")
                time.sleep(0.5)  # Give server time to process
        except Exception as e:
            self.log(f"Error sending QUIT: {e}", "WARNING")

        # Close socket
        try:
            if self.socket:
                self.socket.shutdown(socket.SHUT_RDWR)
                self.socket.close()
        except Exception:
            pass  # Socket might already be closed

        self.socket = None
        self.connection_info.state = IRCConnectionState.DISCONNECTED
        self.connection_info.connected_at = None
        self.connection_info.channels.clear()

        self.log("Disconnected", "INFO")

    def _join_channels(self):
        """Join configured channels."""
        for i, channel in enumerate(self.server_config.channels):
            key = ""
            if self.server_config.keys and i < len(self.server_config.keys):
                key = self.server_config.keys[i]

            if key:
                self._send_raw(f"JOIN {channel} {key}")
                self.log(f"Joining {channel} with key", "INFO")
            else:
                self._send_raw(f"JOIN {channel}")
                self.log(f"Joining {channel}", "INFO")

            self.connection_info.channels.append(channel)

    def _start_keepalive(self):
        """Start keepalive thread."""
        self._stop_event.clear()
        self._keepalive_thread = threading.Thread(
            target=self._keepalive_worker, daemon=True, name="IRC-Keepalive"
        )
        self._keepalive_thread.start()

    def _keepalive_worker(self):
        """Keepalive worker thread."""
        while not self._stop_event.is_set():
            try:
                # Check if we need to send ping
                if (time.time() - self.connection_info.last_ping) > 120:
                    self._send_raw("PING :keepalive")
                    self.connection_info.last_ping = time.time()

                # Sleep in small increments to be responsive to stop event
                for _ in range(30):  # 30 seconds total
                    if self._stop_event.is_set():
                        break
                    time.sleep(1)

            except Exception as e:
                self.log(f"Keepalive error: {e}", "ERROR")
                break

    def _send_raw(self, message: str):
        """Send raw IRC message with rate limiting."""
        if (
            not self.socket
            or self.connection_info.state == IRCConnectionState.DISCONNECTED
        ):
            raise ConnectionError("Not connected to IRC")

        # Rate limiting
        now = time.time()
        if now - self._last_send_time < self._send_delay:
            time.sleep(self._send_delay - (now - self._last_send_time))

        try:
            encoded = f"{message}\r\n".encode("utf-8")
            self.socket.sendall(encoded)
            self._last_send_time = time.time()
            self.log(f"SENT: {message}", "DEBUG")
        except Exception as e:
            self.log(f"Send error: {e}", "ERROR")
            raise

    def send_message(self, target: str, message: str):
        """Send PRIVMSG to target."""
        self._send_raw(f"PRIVMSG {target} :{message}")

    def send_notice(self, target: str, message: str):
        """Send NOTICE to target."""
        self._send_raw(f"NOTICE {target} :{message}")

    def send_action(self, target: str, action: str):
        """Send CTCP ACTION (/me) to target."""
        self._send_raw(f"PRIVMSG {target} :\x01ACTION {action}\x01")

    def send_raw(self, message: str):
        """Send raw IRC message (public interface)."""
        self._send_raw(message)

    def join_channel(self, channel: str, key: str = ""):
        """Join a channel."""
        if key:
            self._send_raw(f"JOIN {channel} {key}")
        else:
            self._send_raw(f"JOIN {channel}")

        if channel not in self.connection_info.channels:
            self.connection_info.channels.append(channel)

    def part_channel(self, channel: str, reason: str = ""):
        """Leave a channel."""
        if reason:
            self._send_raw(f"PART {channel} :{reason}")
        else:
            self._send_raw(f"PART {channel}")

        if channel in self.connection_info.channels:
            self.connection_info.channels.remove(channel)

    def change_nickname(self, new_nick: str):
        """Change nickname."""
        self._send_raw(f"NICK {new_nick}")
        self.nickname = new_nick
        self.connection_info.nickname = new_nick

    def parse_message(self, raw_line: str) -> Optional[IRCMessage]:
        """
        Parse raw IRC message into structured format.

        Args:
            raw_line: Raw IRC message line

        Returns:
            IRCMessage object or None if parsing failed
        """
        if not raw_line:
            return None

        try:
            # Handle IRCv3 tags (starting with @)
            tags = {}
            if raw_line.startswith("@"):
                tag_part, raw_line = raw_line[1:].split(" ", 1)
                for tag in tag_part.split(";"):
                    if "=" in tag:
                        key, value = tag.split("=", 1)
                        tags[key] = value
                    else:
                        tags[tag] = True

            # Parse prefix (sender)
            sender = None
            sender_host = None
            if raw_line.startswith(":"):
                prefix, raw_line = raw_line[1:].split(" ", 1)
                sender_host = prefix
                if "!" in prefix:
                    sender = prefix.split("!")[0]
                else:
                    sender = prefix

            # Parse command and parameters
            parts = raw_line.split(" ")
            command = parts[0].upper()
            params = parts[1:] if len(parts) > 1 else []

            # Extract text (everything after first :)
            text = None
            if ":" in raw_line:
                colon_index = raw_line.find(" :")
                if colon_index != -1:
                    text = raw_line[colon_index + 2 :]  # noqa E203 - Black formatting
                    # Remove text from params
                    params = [p for p in params if not p.startswith(":")]

            # Determine message type
            msg_type = IRCMessageType.UNKNOWN
            target = None

            if command == "PRIVMSG" and len(params) >= 1:
                msg_type = IRCMessageType.PRIVMSG
                target = params[0]
            elif command == "NOTICE" and len(params) >= 1:
                msg_type = IRCMessageType.NOTICE
                target = params[0]
            elif command == "JOIN" and len(params) >= 1:
                msg_type = IRCMessageType.JOIN
                target = params[0]
            elif command == "PART" and len(params) >= 1:
                msg_type = IRCMessageType.PART
                target = params[0]
            elif command == "QUIT":
                msg_type = IRCMessageType.QUIT
            elif command == "NICK":
                msg_type = IRCMessageType.NICK
            elif command == "KICK" and len(params) >= 2:
                msg_type = IRCMessageType.KICK
                target = params[0]  # Channel
            elif command == "MODE" and len(params) >= 1:
                msg_type = IRCMessageType.MODE
                target = params[0]
            elif command == "PING":
                msg_type = IRCMessageType.PING
            elif command == "PONG":
                msg_type = IRCMessageType.PONG
            elif command.isdigit():
                msg_type = IRCMessageType.NUMERIC

            return IRCMessage(
                raw=raw_line,
                type=msg_type,
                sender=sender,
                sender_host=sender_host,
                target=target,
                text=text,
                command=command,
                params=params,
                tags=tags,
            )

        except Exception as e:
            self.log(f"Message parsing error: {e} (line: {raw_line})", "WARNING")
            return None

    def read_messages(self) -> List[IRCMessage]:
        """
        Read and parse messages from IRC server.

        Returns:
            List of parsed IRCMessage objects
        """
        if (
            not self.socket
            or self.connection_info.state != IRCConnectionState.CONNECTED
        ):
            return []

        try:
            data = self.socket.recv(4096)
            if not data:
                raise ConnectionError("Server closed connection")

            response = data.decode("utf-8", errors="ignore")
            messages = []

            for line in response.strip().split("\r\n"):
                if not line:
                    continue

                self.log(f"RECV: {line}", "DEBUG")

                # Call raw handlers
                for handler in self._raw_handlers:
                    try:
                        handler(line)
                    except Exception as e:
                        self.log(f"Raw handler error: {e}", "ERROR")

                # Parse message
                parsed = self.parse_message(line)
                if parsed:
                    messages.append(parsed)

                    # Handle special messages
                    if parsed.type == IRCMessageType.PING:
                        # Auto-respond to PING
                        ping_value = parsed.text or "pong"
                        self._send_raw(f"PONG :{ping_value}")
                        self.connection_info.last_ping = time.time()

                    # Call message type handlers
                    if parsed.type in self._message_handlers:
                        for handler in self._message_handlers[parsed.type]:
                            try:
                                handler(parsed)
                            except Exception as e:
                                self.log(f"Message handler error: {e}", "ERROR")
                                self.log(traceback.format_exc(), "DEBUG")

            return messages

        except socket.timeout:
            return []  # No data available
        except Exception as e:
            self.log(f"Read error: {e}", "ERROR")
            raise

    def run_forever(self, stop_event: Optional[threading.Event] = None):
        """
        Run message processing loop until stopped.

        Args:
            stop_event: Optional event to signal stop
        """
        if not stop_event:
            stop_event = threading.Event()

        self.log("Starting message loop...", "INFO")

        try:
            while (
                not stop_event.is_set()
                and self.connection_info.state == IRCConnectionState.CONNECTED
            ):
                try:
                    self.read_messages()
                    time.sleep(0.05)  # Shorter delay for faster shutdown response
                except socket.timeout:
                    continue
                except Exception as e:
                    self.log(f"Message loop error: {e}", "ERROR")
                    break
        finally:
            self.log("Message loop stopped", "INFO")

    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self.connection_info.state == IRCConnectionState.CONNECTED

    def get_status(self) -> str:
        """Get connection status string."""
        info = self.connection_info
        status_parts = [
            f"State: {info.state.value}",
            f"Nick: {info.nickname}",
            f"Server: {info.server_config.host}:{info.server_config.port}",
        ]

        if info.uptime:
            status_parts.append(f"Uptime: {info.uptime:.1f}s")

        if info.channels:
            status_parts.append(f"Channels: {', '.join(info.channels)}")

        return " | ".join(status_parts)


def create_irc_client(
    server_name: str = "SERVER1",
    nickname: str = None,
    log_callback: Optional[Callable[[str, str], None]] = None,
) -> IRCClient:
    """
    Factory function to create IRC client from configuration.

    Args:
        server_name: Server configuration name from .env
        nickname: Bot nickname (uses config default if None)
        log_callback: Optional logging callback

    Returns:
        Configured IRCClient instance
    """
    from config import get_config_manager

    config_manager = get_config_manager()
    config = config_manager.config

    # Get server configuration
    server_config = config_manager.get_server_by_name(server_name)
    if not server_config:
        server_config = config_manager.get_primary_server()

    if not server_config:
        raise ValueError(f"No server configuration found for '{server_name}'")

    # Use configured nickname if none provided
    if not nickname:
        nickname = config.name

    return IRCClient(server_config, nickname, log_callback)
