"""
Bot Manager for Multiple IRC Servers

This module provides the BotManager class that orchestrates multiple IRC server
connections and integrates all bot functionality across servers.
"""
import threading
import time
import signal
import sys
from typing import List, Dict, Any, Optional
from functools import partial

from config import get_server_configs, load_env_file, get_api_key
from server import Server
from word_tracking import DataManager, DrinkTracker, GeneralWords, TamagotchiBot
from lemmatizer import Lemmatizer
import commands


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
        self.bot_name = bot_name
        self.servers: Dict[str, Server] = {}
        self.server_threads: Dict[str, threading.Thread] = {}
        self.stop_event = threading.Event()
        
        # Initialize bot components
        self.data_manager = DataManager()
        self.drink_tracker = DrinkTracker(self.data_manager)
        self.general_words = GeneralWords(self.data_manager)
        self.tamagotchi = TamagotchiBot(self.data_manager)
        
        # Initialize lemmatizer with graceful fallback
        try:
            self.lemmatizer = Lemmatizer()
            print("🔤 Lemmatizer component initialized")
        except Exception as e:
            print(f"⚠️  Warning: Could not initialize lemmatizer: {e}")
            self.lemmatizer = None
        
        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()
        
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(sig, frame):
            print(f"\nReceived signal {sig}, shutting down...")
            self.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def load_configurations(self) -> bool:
        """
        Load server configurations from environment variables.
        
        Returns:
            True if configurations were loaded successfully, False otherwise
        """
        # Load environment file
        if not load_env_file():
            print("Warning: Could not load .env file")
        
        # Get server configurations
        server_configs = get_server_configs()
        
        if not server_configs:
            print("ERROR: No server configurations found!")
            return False
        
        # Create Server instances
        for config in server_configs:
            server = Server(config, self.bot_name, self.stop_event)
            self.servers[config.name] = server
            print(f"Loaded server configuration: {config.name} ({config.host}:{config.port})")
        
        return True
    
    def register_callbacks(self):
        """Register all bot functionality callbacks with each server."""
        for server_name, server in self.servers.items():
            # Register message callback for command processing
            server.register_callback("message", self._handle_message)
            
            # Register join callback for user tracking
            server.register_callback("join", self._handle_join)
            
            # Register part callback for cleanup
            server.register_callback("part", self._handle_part)
            
            # Register quit callback for cleanup
            server.register_callback("quit", self._handle_quit)
            
            print(f"Registered callbacks for server: {server_name}")
    
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
                'server': server,
                'server_name': server.config.name,
                'sender': sender,
                'target': target,
                'text': text,
                'is_private': not target.startswith('#'),
                'bot_name': self.bot_name
            }
            
            # Track words if not from the bot itself
            if sender.lower() != self.bot_name.lower():
                self._track_words(context)
            
            # Process commands
            self._process_commands(context)
            
        except Exception as e:
            print(f"Error handling message from {server.config.name}: {e}")
    
    def _handle_join(self, server: Server, sender: str, channel: str):
        """Handle user join events."""
        # Track user activity
        server_name = server.config.name
        print(f"[{server_name}] {sender} joined {channel}")
    
    def _handle_part(self, server: Server, sender: str, channel: str):
        """Handle user part events."""
        # Track user activity
        server_name = server.config.name
        print(f"[{server_name}] {sender} left {channel}")
    
    def _handle_quit(self, server: Server, sender: str):
        """Handle user quit events."""
        # Track user activity
        server_name = server.config.name
        print(f"[{server_name}] {sender} quit")
    
    def _track_words(self, context: Dict[str, Any]):
        """Track words for statistics and drink tracking."""
        server_name = context['server_name']
        sender = context['sender']
        text = context['text']
        target = context['target']
        
        # Only track in channels, not private messages
        if not target.startswith('#'):
            return
        
        # Track drink words
        self.drink_tracker.process_message(
            server=server_name,
            nick=sender,
            text=text
        )
        
        # Track general words
        self.general_words.process_message(
            server=server_name,
            nick=sender,
            text=text,
            target=target
        )
        
        # Update tamagotchi
        should_respond, response = self.tamagotchi.process_message(
            server=server_name,
            nick=sender,
            text=text
        )
        
        # Send tamagotchi response if needed
        if should_respond and response:
            server = context['server']
            server.send_message(target, response)
    
    def _process_commands(self, context: Dict[str, Any]):
        """Process IRC commands and bot interactions."""
        server = context['server']
        sender = context['sender']
        target = context['target']
        text = context['text']
        
        # Prepare bot functions for commands.py compatibility
        bot_functions = {
            'data_manager': self.data_manager,
            'drink_tracker': self.drink_tracker,
            'general_words': self.general_words,
            'tamagotchi': self.tamagotchi,
            'lemmat': self.lemmatizer,  # Legacy compatibility
            'server': server,
            'server_name': context['server_name'],
            'bot_name': self.bot_name,
            'latency_start': lambda: getattr(self, '_latency_start', 0),
            'set_latency_start': lambda value: setattr(self, '_latency_start', value)
        }
        
        # Create a mock IRC message format for commands.py compatibility
        mock_message = f":{sender}!{sender}@host.com PRIVMSG {target} :{text}"
        
        try:
            # Use existing commands.py with new context
            commands.process_message(server, mock_message, bot_functions)
        except Exception as e:
            print(f"Error processing command: {e}")
    
    def start(self):
        """Start all servers and bot functionality."""
        if not self.load_configurations():
            return False
        
        self.register_callbacks()
        
        # Migrate legacy data if needed
        if not self.data_manager.migrate_from_pickle():
            print("Warning: Data migration failed, but continuing...")
        
        # Start each server in its own thread
        for server_name, server in self.servers.items():
            thread = threading.Thread(
                target=server.start,
                name=f"Server-{server_name}",
                daemon=False
            )
            thread.start()
            self.server_threads[server_name] = thread
            print(f"Started server thread for {server_name}")
        
        print(f"Bot manager started with {len(self.servers)} servers")
        return True
    
    def stop(self):
        """Stop all servers and bot functionality gracefully."""
        print("Shutting down bot manager...")
        
        # Set stop event
        self.stop_event.set()
        
        # Stop all servers
        for server_name, server in self.servers.items():
            print(f"Stopping server {server_name}...")
            try:
                server.stop()
            except Exception as e:
                print(f"Error stopping server {server_name}: {e}")
        
        # Wait for all server threads to finish
        for server_name, thread in self.server_threads.items():
            print(f"Waiting for server thread {server_name} to finish...")
            thread.join(timeout=10)
            if thread.is_alive():
                print(f"Warning: Server thread {server_name} did not finish cleanly")
        
        print("Bot manager shut down complete")
    
    def wait_for_shutdown(self):
        """Wait for all server threads to complete."""
        try:
            while any(thread.is_alive() for thread in self.server_threads.values()):
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nKeyboard interrupt received")
            self.stop()
    
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
                print(f"Error sending to {server.config.name}: {e}")
    
    def send_notice_to_all_servers(self, target: str, message: str):
        """Send a notice to the same target on all servers."""
        for server in self.servers.values():
            try:
                server.send_notice(target, message)
            except Exception as e:
                print(f"Error sending notice to {server.config.name}: {e}")

