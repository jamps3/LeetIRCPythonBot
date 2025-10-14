"""
Server connection module for the IRC bot.

This module provides the Server class that encapsulates all the functionality
related to a single IRC server connection, including connection management,
reconnection logic, message handling, and maintaining the connection lifecycle.
"""

import os
import re
import socket  # For TLS support
import ssl  # For TLS support
import threading
import time
from typing import Callable

import logger
from config import ServerConfig


class Server:
    """
    Server class to manage a single IRC server connection.

    This class handles:
    1. Socket connection and reconnection
    2. IRC protocol handshake and authentication
    3. Message reading and parsing
    4. Keepalive pings
    5. Channel joining

    Attributes:
        config (ServerConfig): The server configuration object
        bot_name (str): The nickname for the bot on this server
        stop_event (threading.Event): Event to signal the server to stop
        callbacks (dict): Dictionary of message handler callbacks
        connected (bool): Flag indicating if the server is connected
        last_ping (float): Timestamp of the last ping
    """

    def __init__(
        self, config: ServerConfig, bot_name: str, stop_event: threading.Event
    ):
        """
        Initialize a new Server instance.

        Args:
            config (ServerConfig): Server configuration containing host, port, channels, etc.
            bot_name (str): The nickname for the bot
            stop_event (threading.Event): Event to signal the server to stop
        """
        self.config = config
        self.host = config.host
        self.bot_name = bot_name
        self.stop_event = stop_event
        self.socket = None
        self.connected = False
        self.last_ping = time.time()
        self.threads = []
        self.quit_message = "Disconnecting"  # Default quit message
        # Text encoding for IRC I/O (default UTF-8). Override with IRC_ENCODING=latin-1 if your network/client expects ISO-8859-1.
        self.encoding = os.getenv("IRC_ENCODING", "utf-8")
        self.callbacks = {
            "message": [],  # Callbacks for PRIVMSG
            "notice": [],  # Callbacks for NOTICE
            "join": [],  # Callbacks for user join events
            "part": [],  # Callbacks for user part events
            "quit": [],  # Callbacks for user quit events
        }

        # Flood protection - token bucket rate limiter
        # Allow 5 messages per 10 seconds (0.5 messages/second)
        self._rate_limit_tokens = 5.0  # Start with full bucket
        self._rate_limit_max_tokens = 5.0  # Maximum tokens
        self._rate_limit_refill_rate = 0.5  # Tokens per second
        self._rate_limit_last_refill = time.time()
        self._rate_limit_lock = threading.Lock()

        self.log = logger.get_logger(self.config.name)

    def _refill_rate_limit_tokens(self):
        """Refill rate limiting tokens based on time elapsed.

        To avoid tiny fractional increments causing flaky tests and negligible
        behavioral changes, skip refilling if less than 100ms has elapsed
        since the last refill. This preserves intended behavior while keeping
        deterministic token counts for rapid successive calls.
        """
        with self._rate_limit_lock:
            now = time.time()
            elapsed = now - self._rate_limit_last_refill

            # Skip negligible elapsed durations to avoid micro refills
            if elapsed < 0.1:
                return

            # Add tokens based on elapsed time
            tokens_to_add = elapsed * self._rate_limit_refill_rate
            self._rate_limit_tokens = min(
                self._rate_limit_max_tokens, self._rate_limit_tokens + tokens_to_add
            )

            self._rate_limit_last_refill = now

    def _can_send_message(self):
        """Check if we can send a message without hitting rate limits.

        Returns:
            bool: True if message can be sent, False if rate limited
        """
        self._refill_rate_limit_tokens()

        with self._rate_limit_lock:
            if self._rate_limit_tokens >= 1.0:
                self._rate_limit_tokens -= 1.0
                return True
            return False

    def _wait_for_rate_limit(self, timeout=10.0):
        """Wait until we can send a message or timeout.

        Args:
            timeout (float): Maximum time to wait in seconds

        Returns:
            bool: True if we can send, False if timed out
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            if self._can_send_message():
                return True

            # Sleep for a short time before checking again
            time.sleep(0.1)

        return False

    def register_callback(self, event_type: str, callback: Callable):
        """
        Register a callback function for a specific event type.

        Args:
            event_type (str): The type of event to register for (message, notice, join, part, quit)
            callback (Callable): The callback function to register
        """
        if event_type in self.callbacks:
            self.callbacks[event_type].append(callback)
            self.log.debug(f"Registered callback for {event_type} events")
        else:
            self.log.warning(f"Unknown event type: {event_type}")

    def connect_and_run(self):
        """
        Connect to the server and start the main loop.
        """
        self.start()

    def connect(self) -> bool:
        """
        Connect to the IRC server using TLS if configured.

        Returns:
            bool: True if connection succeeded, False otherwise.
        """
        try:
            raw_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            raw_socket.settimeout(60)

            if self.config.tls:
                self.log.info(
                    f"Connecting to {self.config.host}:{self.config.port} with TLS=True"
                )

                try:
                    context = ssl.create_default_context()

                    if self.config.allow_insecure_tls:
                        context.check_hostname = False
                        context.verify_mode = ssl.CERT_NONE
                        self.log.warning(
                            "Using unverified SSL context — insecure but allows expired/broken certs"
                        )
                    else:
                        context.check_hostname = True
                        context.verify_mode = ssl.CERT_REQUIRED

                    context.minimum_version = ssl.TLSVersion.TLSv1_2
                    context.options |= ssl.OP_LEGACY_SERVER_CONNECT
                    context.set_ciphers("HIGH:!aNULL:!MD5:!RC4:!LOW:!EXP")

                    self.socket = context.wrap_socket(
                        raw_socket,
                        server_hostname=(
                            None
                            if context.check_hostname is False
                            else self.config.host
                        ),
                    )
                    self.log.info("Wrapped socket with TLS")

                except Exception as e:
                    self.log.error(f"Failed to create SSL context: {e}")
                    return False

            else:
                self.log.info(
                    f"Connecting to {self.config.host}:{self.config.port} with TLS=False"
                )
                self.socket = raw_socket

            self.socket.connect((self.config.host, self.config.port))
            self.socket.settimeout(1.0)

            if isinstance(self.socket, ssl.SSLSocket):
                cert = self.socket.getpeercert()
                tls_version = self.socket.version()
                self.log.info(f"TLS handshake successful — using {tls_version}")
                if cert:
                    subject = dict(x[0] for x in cert.get("subject", []))
                    cn = subject.get("commonName", "(unknown)")
                    self.log.info(f"TLS certificate CN: {cn}")
            else:
                self.log.warning("Connected without TLS!")

            self.connected = True
            return True

        except ssl.SSLCertVerificationError as e:
            self.log.error(f"TLS certificate verification failed: {e}")
        except ssl.SSLError as e:
            self.log.error(
                f"SSL error during connect: {e}. Are you sure the server supports TLS? Is the PORT correct?"
            )
        except (socket.error, ConnectionError) as e:
            self.log.error(f"Failed to connect: {e}")
        except Exception as e:
            self.log.error(f"Unexpected error during connect: {e}")

        self.connected = False
        return False

    def is_tls(self) -> bool:
        return isinstance(self.socket, ssl.SSLSocket)

    def login(self) -> bool:
        """
        Log into the IRC server with the bot's nickname.

        Returns:
            bool: True if login was successful, False otherwise
        """
        try:
            nick = self.bot_name
            login = self.bot_name

            self.send_raw(f"NICK {nick}")
            self.send_raw(f"USER {login} 0 * :{nick}")

            last_response_time = time.time()

            while not self.stop_event.is_set():
                try:
                    response = self.socket.recv(2048).decode(
                        self.encoding, errors="ignore"
                    )
                    if response:
                        last_response_time = time.time()

                    for line in response.split("\r\n"):
                        if line:
                            self.log.server(line)

                        # If server says "Please wait while we process your connection", don't disconnect yet
                        if " 020 " in line:
                            self.log.debug(
                                "Server is still processing connection, continuing to wait..."
                            )
                            last_response_time = time.time()
                            continue

                        # If welcome (001) or MOTD completion (376/422) received, join channels
                        if " 001 " in line or " 376 " in line or " 422 " in line:
                            self.log.info("Login successful, joining channels...")
                            self.join_channels()
                            return True

                    # Timeout handling: If no response received in 30 seconds, assume failure
                    if time.time() - last_response_time > 30:
                        raise socket.timeout("No response from server for 30 seconds")

                except socket.timeout:
                    # Socket timeout just means no data yet, continue loop
                    pass

            return False  # Stop event was set

        except (
            socket.error,
            ConnectionResetError,
            BrokenPipeError,
            socket.timeout,
        ) as e:
            self.log.error(f"Login failed: {e}")
            self.connected = False
            return False

        except Exception as e:
            self.log.error(f"Unexpected error during login: {e}")
            self.connected = False
            return False

    def join_channels(self):
        """Join all channels specified in the server configuration."""
        for channel, key in zip(
            self.config.channels, self.config.keys or [""] * len(self.config.channels)
        ):
            if key:
                self.send_raw(f"JOIN {channel} {key}")
                self.log.info(f"Joining channel {channel} with key...")
            else:
                self.send_raw(f"JOIN {channel}")
                self.log.info(f"Joining channel {channel} (no key)...")

    def join_channel(self, channel: str, key: str = None):
        """Join a specific channel.

        Args:
            channel (str): Channel name to join
            key (str, optional): Channel key if required
        """
        if key:
            self.send_raw(f"JOIN {channel} {key}")
            self.log.info(f"Joining channel {channel} with key...")
        else:
            self.send_raw(f"JOIN {channel}")
            self.log.info(f"Joining channel {channel}...")

    def part_channel(self, channel: str, message: str = None):
        """Leave a specific channel.

        Args:
            channel (str): Channel name to leave
            message (str, optional): Part message
        """
        if message:
            self.send_raw(f"PART {channel} :{message}")
            self.log.info(f"Leaving channel {channel} with message: {message}")
        else:
            self.send_raw(f"PART {channel}")
            self.log.info(f"Leaving channel {channel}...")

    def send_raw(self, message: str, bypass_rate_limit: bool = False):
        """
        Send a raw IRC message to the server with flood protection.

        Args:
            message (str): The message to send
            bypass_rate_limit (bool): If True, bypass rate limiting (for critical messages like PONG)
        """
        if not self.connected or not self.socket:
            self.log.warning("Cannot send message: not connected")
            return

        # Apply rate limiting unless bypassed
        if not bypass_rate_limit:
            # Check if this is a critical protocol message that should bypass rate limiting
            critical_commands = ["PONG", "QUIT", "NICK", "USER"]
            is_critical = any(message.startswith(cmd) for cmd in critical_commands)

            if not is_critical:
                # Wait for rate limit, but don't wait forever
                if not self._wait_for_rate_limit(timeout=5.0):
                    self.log.warning(
                        f"Rate limit exceeded, dropping message: {message[:50]}..."
                    )
                    return

        try:
            self.socket.sendall(
                f"{message}\r\n".encode(self.encoding, errors="replace")
            )
            # self.log.debug(f"SENT: {message}")
        except (socket.error, BrokenPipeError) as e:
            self.log.error(f"Error sending message: {e}")
            self.connected = False

    def send_message(self, target: str, message: str):
        """
        Send a PRIVMSG to a channel or user.

        Args:
            target (str): The channel or nickname to send the message to
            message (str): The message content
        """
        self.send_raw(f"PRIVMSG {target} :{message}")

    def send_notice(self, target: str, message: str):
        """
        Send a NOTICE to a channel or user.

        Args:
            target (str): The channel or nickname to send the notice to
            message (str): The notice content
        """
        self.send_raw(f"NOTICE {target} :{message}")

    def _keepalive_ping(self):
        """Send periodic pings to keep the connection alive."""
        while not self.stop_event.is_set() and self.connected:
            # Check stop event more frequently for faster shutdown
            for _ in range(20):  # 20 * 0.1s = 2s total, but check stop event every 0.1s
                if self.stop_event.is_set():
                    return
                time.sleep(0.1)

            if time.time() - self.last_ping > 120:
                try:
                    self.send_raw("PING :keepalive")
                    self.last_ping = time.time()
                except Exception as e:
                    self.log.error(f"Error sending keepalive ping: {e}")
                    self.connected = False
                    break

    def _read_messages(self):
        """Read and process messages from the server."""
        # Set socket timeout to allow frequent checking of stop_event
        if self.socket:
            self.socket.settimeout(0.5)  # Shorter timeout for faster shutdown response

        while not self.stop_event.is_set() and self.connected:
            try:
                response = self.socket.recv(4096).decode(self.encoding, errors="ignore")
                if not response:
                    if not self.stop_event.is_set():
                        self.log.warning("Connection closed by server")
                        self.connected = False
                    break

                for line in response.strip().split("\r\n"):
                    self.log.server(line.strip())

                    # Handle PING
                    if line.startswith("PING"):
                        self.last_ping = time.time()
                        ping_value = line.split(":", 1)[1].strip()
                        self.send_raw(f"PONG :{ping_value}")
                        self.log.debug(f"Sent PONG response to {ping_value}")

                    # Process the message
                    self._process_message(line)

            except socket.timeout:
                # Socket timeout is normal, just continue
                continue

            except (socket.error, ConnectionResetError) as e:
                if not self.stop_event.is_set():
                    self.log.error(f"Connection error: {e}")
                    self.connected = False
                break

            except Exception as e:
                self.log.error(f"Unexpected error reading messages: {e}")
                if not self.stop_event.is_set():
                    self.connected = False
                break

    def _process_message(self, message: str):
        """
        Process an incoming IRC message.

        Args:
            message (str): The raw IRC message
        """
        # Process PRIVMSG
        privmsg_match = re.search(r":(\S+)!(\S+) PRIVMSG (\S+) :(.+)", message)
        if privmsg_match:
            sender, hostmask, target, text = privmsg_match.groups()
            # Call all registered message callbacks
            for callback in self.callbacks["message"]:
                try:
                    callback(self, sender, target, text)
                except Exception as e:
                    self.log.error(f"Error in message callback: {e}")
            return

        # Process NOTICE
        notice_match = re.search(r":(\S+)!(\S+) NOTICE (\S+) :(.+)", message)
        if notice_match:
            sender, hostmask, target, text = notice_match.groups()
            # Call all registered notice callbacks
            for callback in self.callbacks["notice"]:
                try:
                    callback(self, sender, target, text)
                except Exception as e:
                    self.log.error(f"Error in notice callback: {e}")
            return

        # Process JOIN
        join_match = re.search(r":(\S+)!(\S+) JOIN (\S+)", message)
        if join_match:
            sender, hostmask, channel = join_match.groups()
            for callback in self.callbacks["join"]:
                try:
                    callback(self, sender, channel)
                except Exception as e:
                    self.log.error(f"Error in join callback: {e}")
            return

        # Process PART
        part_match = re.search(r":(\S+)!(\S+) PART (\S+)", message)
        if part_match:
            sender, hostmask, channel = part_match.groups()
            for callback in self.callbacks["part"]:
                try:
                    callback(self, sender, channel)
                except Exception as e:
                    self.log.error(f"Error in part callback: {e}")
            return

        # Process QUIT
        quit_match = re.search(r":(\S+)!(\S+) QUIT", message)
        if quit_match:
            sender, hostmask = quit_match.groups()
            for callback in self.callbacks["quit"]:
                try:
                    callback(self, sender)
                except Exception as e:
                    self.log.error(f"Error in quit callback: {e}")
            return

    def _process_notice(self, message: str):
        """
        Process an incoming IRC notice.

        Args:
            message (str): The raw IRC message
        """
        # Process NOTICE
        notice_match = re.search(r":(\S+)!(\S+) NOTICE (\S+) :(.+)", message)
        if notice_match:
            sender, hostmask, target, text = notice_match.groups()
            # Call all registered message callbacks
            for callback in self.callbacks["notice"]:
                try:
                    callback(self, sender, target, text)
                except Exception as e:
                    self.log.error(f"Error in message callback: {e}")
            return

    def start(self):
        """
        Start the server connection and message processing threads.

        This method attempts to connect to the server, log in,
        and start the keepalive and message reading threads.

        If connection fails, it will retry with exponential backoff.
        If stop_event is set at any point, it will exit immediately.
        """
        retry_delay = 5  # Initial delay in seconds
        max_retry_delay = 300  # Maximum delay (5 minutes)

        while not self.stop_event.is_set():
            # Check stop event before attempting connection
            if self.stop_event.is_set():
                self.log.info("Stop event set, exiting connection loop")
                break

            if self.connect() and self.login():
                # Check stop event after successful connection
                if self.stop_event.is_set():
                    self.log.info("Stop event set after connection, disconnecting")
                    self.quit(self.quit_message)
                    break

                # Start keepalive ping thread
                keepalive_thread = threading.Thread(
                    target=self._keepalive_ping,
                    daemon=True,
                    name=f"{self.config.name}-keepalive",
                )
                keepalive_thread.start()
                self.threads.append(keepalive_thread)

                # Start message reading thread
                read_thread = threading.Thread(
                    target=self._read_messages,
                    daemon=True,
                    name=f"{self.config.name}-reader",
                )
                read_thread.start()
                self.threads.append(read_thread)

                # Wait for either thread to exit (check stop event frequently)
                while self.connected and not self.stop_event.is_set():
                    time.sleep(
                        0.1
                    )  # Check stop event more frequently for faster shutdown

                # If we're still connected but stop event is set, send QUIT
                if self.connected and self.stop_event.is_set():
                    self.log.info("Stop event set, sending QUIT")
                    self.quit(self.quit_message)

                retry_delay = 5  # Reset retry delay
            else:
                # Connection or login failed
                if self.stop_event.is_set():
                    self.log.info("Stop event set during connection failure, exiting")
                    break

            # Final check before considering reconnection
            if self.stop_event.is_set():
                self.log.info("Stop event set, not reconnecting")
                break

            # Only attempt reconnection if stop event is not set
            self.log.info(f"Reconnecting in {retry_delay} seconds...")
            for i in range(retry_delay):
                if self.stop_event.is_set():
                    self.log.info(
                        f"Stop event set during reconnect wait (after {i}s), exiting"
                    )
                    break
                time.sleep(1)

            # If stop event was set during the wait, exit immediately
            if self.stop_event.is_set():
                break

            # Increase retry delay with a cap
            retry_delay = min(retry_delay * 2, max_retry_delay)

        self.log.info("Server start() method exiting")

    def quit(self, message: str = "Disconnecting"):
        """
        Disconnect from the server with a quit message.

        Args:
            message (str): The quit message to send
        """
        if self.connected and self.socket:
            try:
                # Send QUIT message first
                self.send_raw(f"QUIT :{message}")
                time.sleep(0.5)  # Give the server a moment to process the QUIT

                # Close socket safely
                self._close_socket()

            except Exception as e:
                self.log.warning(f"Error during quit: {e}")
                # Still try to close socket even if QUIT failed
                self._close_socket()

            self.connected = False
            self.log.info("Disconnected from server")

    def _close_socket(self):
        """Safely close the socket connection."""
        if self.socket:
            try:
                # Try to shutdown the socket first
                self.socket.shutdown(socket.SHUT_RDWR)
            except (OSError, socket.error) as e:
                # Shutdown can fail if socket is already closed or not connected
                self.log.debug(f"Socket shutdown failed (expected): {e}")

            try:
                # Close the socket
                self.socket.close()
                self.log.debug("Socket closed successfully")
            except (OSError, socket.error) as e:
                # Close can fail if socket is already closed
                self.log.debug(f"Socket close failed (expected): {e}")
            finally:
                # Always clear the socket reference
                self.socket = None

    def stop(self, quit_message: str = None):
        """Stop the server and clean up all resources.

        Args:
            quit_message (str, optional): Custom quit message to use before disconnecting.
        """
        if quit_message:
            self.quit_message = quit_message

        if not self.stop_event.is_set():
            self.stop_event.set()

        if self.connected:
            try:
                self.log.info(
                    f"Stopping server connection with message: {self.quit_message}..."
                )

                # Send QUIT with custom message before closing socket
                try:
                    self.send_raw(f"QUIT :{self.quit_message}")
                    # Give server time to process the QUIT
                    import time

                    time.sleep(0.5)
                except Exception as e:
                    self.log.warning(f"Error sending QUIT message: {e}")

                # Use the safe socket closing method
                self._close_socket()

                # Wait for threads to finish with short timeout
                timeout_per_thread = 1.0  # Much shorter timeout
                for thread in self.threads:
                    self.log.debug(f"Waiting for thread {thread.name} to finish...")
                    thread.join(timeout=timeout_per_thread)
                    if thread.is_alive():
                        self.log.debug(
                            f"Thread {thread.name} did not finish within {timeout_per_thread}s timeout"
                        )

            except Exception as e:
                self.log.error(f"Error during server shutdown: {e}")
            finally:
                self.connected = False
                self.socket = None
                self.threads = []
                self.log.info("Server resources cleaned up")
