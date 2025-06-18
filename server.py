"""
Server connection module for the IRC bot.

This module provides the Server class that encapsulates all the functionality
related to a single IRC server connection, including connection management,
reconnection logic, message handling, and maintaining the connection lifecycle.
"""
import socket
import threading
import time
import re
from datetime import datetime
from typing import List, Tuple, Optional, Callable, Dict, Any

from config import ServerConfig
from logger import get_logger


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
    
    def __init__(self, config: ServerConfig, bot_name: str, stop_event: threading.Event):
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
        self.callbacks = {
            "message": [],  # Callbacks for PRIVMSG
            "join": [],     # Callbacks for user join events
            "part": [],     # Callbacks for user part events
            "quit": []      # Callbacks for user quit events
        }
        self.logger = get_logger(self.config.name)
    
    def register_callback(self, event_type: str, callback: Callable):
        """
        Register a callback function for a specific event type.
        
        Args:
            event_type (str): The type of event to register for (message, join, part, quit)
            callback (Callable): The callback function to register
        """
        if event_type in self.callbacks:
            self.callbacks[event_type].append(callback)
            self.logger.debug(f"Registered callback for {event_type} events")
        else:
            self.logger.warning(f"Unknown event type: {event_type}")
    
    def connect_and_run(self):
        """
        Connect to the server and start the main loop.
        """
        self.start()
    
    def connect(self) -> bool:
        """
        Connect to the IRC server.
        
        Returns:
            bool: True if connection was successful, False otherwise
        """
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.config.host, self.config.port))
            self.socket.settimeout(1.0)  # Timeout for socket operations
            self.logger.info(f"Connected to {self.config.host}:{self.config.port}")
            self.connected = True
            return True
        except (socket.error, ConnectionError) as e:
            self.logger.error(f"Failed to connect: {e}")
            self.connected = False
            return False
    
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
                    response = self.socket.recv(2048).decode("utf-8", errors="ignore")
                    if response:
                        last_response_time = time.time()
                    
                    for line in response.split("\r\n"):
                        if line:
                            self.logger.server(line)
                        
                        # If server says "Please wait while we process your connection", don't disconnect yet
                        if " 020 " in line:
                            self.logger.debug("Server is still processing connection, continuing to wait...")
                            last_response_time = time.time()
                            continue
                        
                        # If welcome (001) or MOTD completion (376/422) received, join channels
                        if " 001 " in line or " 376 " in line or " 422 " in line:
                            self.logger.info("Login successful, joining channels...")
                            self.join_channels()
                            return True
                    
                    # Timeout handling: If no response received in 30 seconds, assume failure
                    if time.time() - last_response_time > 30:
                        raise socket.timeout("No response from server for 30 seconds")
                    
                except socket.timeout:
                    # Socket timeout just means no data yet, continue loop
                    pass
            
            return False  # Stop event was set
            
        except (socket.error, ConnectionResetError, BrokenPipeError, socket.timeout) as e:
            self.logger.error(f"Login failed: {e}")
            self.connected = False
            return False
        
        except Exception as e:
            self.logger.error(f"Unexpected error during login: {e}")
            self.connected = False
            return False
    
    def join_channels(self):
        """Join all channels specified in the server configuration."""
        for channel, key in zip(self.config.channels, self.config.keys or [""]*len(self.config.channels)):
            if key:
                self.send_raw(f"JOIN {channel} {key}")
                self.logger.info(f"Joined channel {channel} with key")
            else:
                self.send_raw(f"JOIN {channel}")
                self.logger.info(f"Joined channel {channel} (no key)")
    
    def send_raw(self, message: str):
        """
        Send a raw IRC message to the server.
        
        Args:
            message (str): The message to send
        """
        if not self.connected or not self.socket:
            self.logger.warning("Cannot send message: not connected")
            return
        
        try:
            self.socket.sendall(f"{message}\r\n".encode("utf-8"))
            # self.logger.debug(f"SENT: {message}")
        except (socket.error, BrokenPipeError) as e:
            self.logger.error(f"Error sending message: {e}")
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
            time.sleep(2)  # Check frequently for stop event
            
            if self.stop_event.is_set():
                break
                
            if time.time() - self.last_ping > 120:
                try:
                    self.send_raw("PING :keepalive")
                    self.last_ping = time.time()
                except Exception as e:
                    self.logger.error(f"Error sending keepalive ping: {e}")
                    self.connected = False
                    break
    
    def _read_messages(self):
        """Read and process messages from the server."""
        while not self.stop_event.is_set() and self.connected:
            try:
                response = self.socket.recv(4096).decode("utf-8", errors="ignore")
                if not response:
                    if not self.stop_event.is_set():
                        self.logger.warning("Connection closed by server")
                        self.connected = False
                    break
                
                for line in response.strip().split("\r\n"):
                    self.logger.server(line.strip())
                    
                    # Handle PING
                    if line.startswith("PING"):
                        self.last_ping = time.time()
                        ping_value = line.split(":", 1)[1].strip()
                        self.send_raw(f"PONG :{ping_value}")
                        self.logger.debug(f"Sent PONG response to {ping_value}")
                    
                    # Process the message
                    self._process_message(line)
            
            except socket.timeout:
                # Socket timeout is normal, just continue
                continue
            
            except (socket.error, ConnectionResetError) as e:
                if not self.stop_event.is_set():
                    self.logger.error(f"Connection error: {e}")
                    self.connected = False
                break
            
            except Exception as e:
                self.logger.error(f"Unexpected error reading messages: {e}")
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
                    self.logger.error(f"Error in message callback: {e}")
            return
        
        # Process JOIN
        join_match = re.search(r":(\S+)!(\S+) JOIN (\S+)", message)
        if join_match:
            sender, hostmask, channel = join_match.groups()
            for callback in self.callbacks["join"]:
                try:
                    callback(self, sender, channel)
                except Exception as e:
                    self.logger.error(f"Error in join callback: {e}")
            return
        
        # Process PART
        part_match = re.search(r":(\S+)!(\S+) PART (\S+)", message)
        if part_match:
            sender, hostmask, channel = part_match.groups()
            for callback in self.callbacks["part"]:
                try:
                    callback(self, sender, channel)
                except Exception as e:
                    self.logger.error(f"Error in part callback: {e}")
            return
        
        # Process QUIT
        quit_match = re.search(r":(\S+)!(\S+) QUIT", message)
        if quit_match:
            sender, hostmask = quit_match.groups()
            for callback in self.callbacks["quit"]:
                try:
                    callback(self, sender)
                except Exception as e:
                    self.logger.error(f"Error in quit callback: {e}")
            return
    
    def start(self):
        """
        Start the server connection and message processing threads.
        
        This method attempts to connect to the server, log in,
        and start the keepalive and message reading threads.
        
        If connection fails, it will retry with exponential backoff.
        """
        retry_delay = 5  # Initial delay in seconds
        max_retry_delay = 300  # Maximum delay (5 minutes)
        
        while not self.stop_event.is_set():
            if self.connect() and self.login():
                # Start keepalive ping thread
                keepalive_thread = threading.Thread(
                    target=self._keepalive_ping, 
                    daemon=True,
                    name=f"{self.config.name}-keepalive"
                )
                keepalive_thread.start()
                self.threads.append(keepalive_thread)
                
                # Start message reading thread
                read_thread = threading.Thread(
                    target=self._read_messages,
                    daemon=True,
                    name=f"{self.config.name}-reader"
                )
                read_thread.start()
                self.threads.append(read_thread)
                
                # Wait for either thread to exit
                while self.connected and not self.stop_event.is_set():
                    time.sleep(1)
                
                # If we're still connected but stop event is set, send QUIT
                if self.connected and self.stop_event.is_set():
                    self.quit("Shutting down")
                
                retry_delay = 5  # Reset retry delay
            
            if self.stop_event.is_set():
                break
            
            # Wait before retry with exponential backoff
            self.logger.info(f"Reconnecting in {retry_delay} seconds...")
            for _ in range(retry_delay):
                if self.stop_event.is_set():
                    break
                time.sleep(1)
            
            # Increase retry delay with a cap
            retry_delay = min(retry_delay * 2, max_retry_delay)
    
    def quit(self, message: str = "Disconnecting"):
        """
        Disconnect from the server with a quit message.
        
        Args:
            message (str): The quit message to send
        """
        if self.connected and self.socket:
            try:
                self.send_raw(f"QUIT :{message}")
                time.sleep(1)  # Give the server a moment to process the QUIT
                self.socket.shutdown(socket.SHUT_RDWR)
                self.socket.close()
            except Exception as e:
                self.logger.warning(f"Error during quit: {e}")
            
            self.connected = False
            self.logger.info("Disconnected from server")
    
    def stop(self):
        """Stop the server and clean up all resources."""
        if not self.stop_event.is_set():
            self.stop_event.set()
        
        if self.connected:
            try:
                self.logger.info("Stopping server connection...")
                # Send quit message if connected
                self.quit("Bot shutting down")
                self.logger.debug("Quit message sent")
                
                # Wait for threads to finish with timeout
                timeout_per_thread = 5  # seconds
                for thread in self.threads:
                    self.logger.debug(f"Waiting for thread {thread.name} to finish...")
                    thread.join(timeout=timeout_per_thread)
                    if thread.is_alive():
                        self.logger.warning(f"Thread {thread.name} did not finish within timeout")
                
                # Ensure socket is closed
                if self.socket:
                    try:
                        self.socket.close()
                        self.logger.info("Socket connection closed")
                    except Exception as e:
                        self.logger.error(f"Error closing socket: {e}")
            except Exception as e:
                self.logger.error(f"Error during server shutdown: {e}")
            finally:
                self.connected = False
                self.socket = None
                self.threads = []
                self.logger.info("Server resources cleaned up")
