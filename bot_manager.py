"""
Bot Manager for Multiple IRC Servers

This module provides the BotManager class that orchestrates multiple IRC server
connections and integrates all bot functionality across servers.
"""
import os
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
from services.weather_service import WeatherService
from services.gpt_service import GPTService
from services.electricity_service import create_electricity_service
from services.youtube_service import create_youtube_service
from services.crypto_service import create_crypto_service
from nanoleet_detector import create_nanoleet_detector
from logger import get_logger
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
        
        # Initialize high-precision logger first
        self.logger = get_logger("BotManager")
        
        # Load USE_NOTICES setting
        use_notices_setting = os.getenv('USE_NOTICES', 'false').lower()
        self.use_notices = use_notices_setting in ('true', '1', 'yes', 'on')
        if self.use_notices:
            self.logger.info("📢 Using IRC NOTICEs for channel responses")
        else:
            self.logger.info("💬 Using regular PRIVMSGs for channel responses")
        
        # Load TAMAGOTCHI_ENABLED setting
        tamagotchi_setting = os.getenv('TAMAGOTCHI_ENABLED', 'true').lower()
        self.tamagotchi_enabled = tamagotchi_setting in ('true', '1', 'yes', 'on')
        if self.tamagotchi_enabled:
            self.logger.info("🐣 Tamagotchi responses enabled")
        else:
            self.logger.info("🐣 Tamagotchi responses disabled")
        
        # Initialize bot components
        self.data_manager = DataManager()
        self.drink_tracker = DrinkTracker(self.data_manager)
        self.general_words = GeneralWords(self.data_manager)
        self.tamagotchi = TamagotchiBot(self.data_manager)
        
        
        # Initialize weather service
        weather_api_key = get_api_key('WEATHER_API_KEY')
        if weather_api_key:
            self.weather_service = WeatherService(weather_api_key)
            self.logger.info("🌤️ Weather service initialized")
        else:
            self.logger.warning("⚠️  No weather API key found. Weather commands will not work.")
            self.weather_service = None
        
        # Initialize GPT service
        openai_api_key = get_api_key('OPENAI_API_KEY')
        history_file = os.getenv('HISTORY_FILE', 'conversation_history.json')
        history_limit = int(os.getenv('GPT_HISTORY_LIMIT', '100'))
        if openai_api_key:
            self.gpt_service = GPTService(openai_api_key, history_file, history_limit)
            self.logger.info(f"🤖 GPT chat service initialized (history limit: {history_limit} messages)")
        else:
            self.logger.warning("⚠️  No OpenAI API key found. AI chat will not work.")
            self.gpt_service = None
        
        # Initialize electricity service
        electricity_api_key = get_api_key('ELECTRICITY_API_KEY')
        if electricity_api_key:
            self.electricity_service = create_electricity_service(electricity_api_key)
            self.logger.info("⚡ Electricity price service initialized")
        else:
            self.logger.warning("⚠️  No electricity API key found. Electricity price commands will not work.")
            self.electricity_service = None
        
        # Initialize YouTube service
        youtube_api_key = get_api_key('YOUTUBE_API_KEY')
        if youtube_api_key:
            self.youtube_service = create_youtube_service(youtube_api_key)
            self.logger.info("▶️ YouTube service initialized")
        else:
            self.logger.warning("⚠️  No YouTube API key found. YouTube commands will not work.")
            self.youtube_service = None
        
        # Initialize crypto service
        self.crypto_service = create_crypto_service()
        self.logger.info("🪙 Crypto service initialized (using CoinGecko API)")
        
        # Initialize nanoleet detector
        self.nanoleet_detector = create_nanoleet_detector()
        self.logger.info("🎯 Nanosecond leet detector initialized")
        
        # Initialize lemmatizer with graceful fallback
        try:
            self.lemmatizer = Lemmatizer()
            self.logger.info("🔤 Lemmatizer component initialized")
        except Exception as e:
            self.logger.warning(f"⚠️  Could not initialize lemmatizer: {e}")
            self.lemmatizer = None
        
        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()
        
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(sig, frame):
            self.logger.info(f"Received signal {sig}, shutting down...")
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
            self.logger.warning("Could not load .env file")
        
        # Get server configurations
        server_configs = get_server_configs()
        
        if not server_configs:
            self.logger.error("No server configurations found!")
            return False
        
        # Create Server instances
        for config in server_configs:
            server = Server(config, self.bot_name, self.stop_event)
            self.servers[config.name] = server
            self.logger.info(f"Loaded server configuration: {config.name} ({config.host}:{config.port})")
        
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
            
            self.logger.info(f"Registered callbacks for server: {server_name}")
    
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
            
            # Process commands
            self._process_commands(context)
            
        except Exception as e:
            self.logger.error(f"Error handling message from {server.config.name}: {e}")
    
    def _handle_join(self, server: Server, sender: str, channel: str):
        """Handle user join events."""
        # Track user activity
        server_name = server.config.name
        self.logger.info(f"{sender} joined {channel}", server_name)
    
    def _handle_part(self, server: Server, sender: str, channel: str):
        """Handle user part events."""
        # Track user activity
        server_name = server.config.name
        self.logger.info(f"{sender} left {channel}", server_name)
    
    def _handle_quit(self, server: Server, sender: str):
        """Handle user quit events."""
        # Track user activity
        server_name = server.config.name
        self.logger.info(f"{sender} quit", server_name)
    
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
        
        # Update tamagotchi (only if enabled)
        if self.tamagotchi_enabled:
            should_respond, response = self.tamagotchi.process_message(
                server=server_name,
                nick=sender,
                text=text
            )
            
            # Send tamagotchi response if needed
            if should_respond and response:
                server = context['server']
                self._send_response(server, target, response)
    
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
            'tamagotchi': lambda text, irc, target: None,  # No-op for legacy compatibility
            'tamagotchi_bot': self.tamagotchi,
            'lemmat': self.lemmatizer,  # Legacy compatibility
            'server': server,
            'server_name': context['server_name'],
            'bot_name': self.bot_name,
            'latency_start': lambda: getattr(self, '_latency_start', 0),
            'set_latency_start': lambda value: setattr(self, '_latency_start', value),
            
            # Add legacy function implementations
            'count_kraks': self._count_kraks_legacy,
            'notice_message': lambda msg, irc=None, target=None: self._send_response(server, target or context['target'], msg),
            'send_electricity_price': self._send_electricity_price,
            'measure_latency': self._measure_latency,
            'get_crypto_price': self._get_crypto_price,
            'send_youtube_info': self._send_youtube_info,
            'send_crypto_price': self._send_crypto_price,
            'load_leet_winners': self._load_leet_winners,
            'save_leet_winners': self._save_leet_winners,
            'send_weather': self._send_weather,
            'send_scheduled_message': self._send_scheduled_message,
            'get_eurojackpot_numbers': self._get_eurojackpot_numbers,
            'search_youtube': self._search_youtube,
            'handle_ipfs_command': self._handle_ipfs_command,
            'lookup': lambda irc: context['server_name'],
            'format_counts': self._format_counts,
            'chat_with_gpt': lambda msg, sender=None: self._chat_with_gpt(msg, sender or context['sender']),
            'wrap_irc_message_utf8_bytes': self._wrap_irc_message_utf8_bytes,
            'send_message': lambda irc, target, msg: server.send_message(target, msg),
            'load': self._load_legacy_data,
            'save': self._save_legacy_data,
            'update_kraks': self._update_kraks_legacy,
            'log': self._log,
            'fetch_title': self._fetch_title,
            'subscriptions': self._get_subscriptions_module(),
            'DRINK_WORDS': self._get_drink_words(),
            'EKAVIKA_FILE': 'ekavika.json',
            'get_latency_start': lambda: getattr(self, '_latency_start', 0),
            'BOT_VERSION': '2.0.0',
            'toggle_tamagotchi': lambda: self.toggle_tamagotchi(server, target, sender)
        }
        
        # Create a mock IRC message format for commands.py compatibility
        mock_message = f":{sender}!{sender}@host.com PRIVMSG {target} :{text}"
        
        try:
            # Use existing commands.py with new context
            commands.process_message(server, mock_message, bot_functions)
        except Exception as e:
            self.logger.error(f"Error processing command: {e}")
    
    def start(self):
        """Start all servers and bot functionality."""
        if not self.load_configurations():
            return False
        
        self.register_callbacks()
        
        # Migrate legacy data if needed
        if not self.data_manager.migrate_from_pickle():
            self.logger.warning("Data migration failed, but continuing...")
        
        # Start each server in its own thread
        for server_name, server in self.servers.items():
            thread = threading.Thread(
                target=server.start,
                name=f"Server-{server_name}",
                daemon=False
            )
            thread.start()
            self.server_threads[server_name] = thread
            self.logger.info(f"Started server thread for {server_name}")
        
        self.logger.info(f"Bot manager started with {len(self.servers)} servers")
        return True
    
    def stop(self):
        """Stop all servers and bot functionality gracefully."""
        self.logger.info("Shutting down bot manager...")
        
        # Set stop event
        self.stop_event.set()
        
        # Stop all servers
        for server_name, server in self.servers.items():
            self.logger.info(f"Stopping server {server_name}...")
            try:
                server.stop()
            except Exception as e:
                self.logger.error(f"Error stopping server {server_name}: {e}")
        
        # Wait for all server threads to finish
        for server_name, thread in self.server_threads.items():
            self.logger.info(f"Waiting for server thread {server_name} to finish...")
            thread.join(timeout=10)
            if thread.is_alive():
                self.logger.warning(f"Server thread {server_name} did not finish cleanly")
        
        self.logger.info("Bot manager shut down complete")
    
    def wait_for_shutdown(self):
        """Wait for all server threads to complete."""
        try:
            while any(thread.is_alive() for thread in self.server_threads.values()):
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")
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
                self.logger.error(f"Error sending to {server.config.name}: {e}")
    
    def send_notice_to_all_servers(self, target: str, message: str):
        """Send a notice to the same target on all servers."""
        for server in self.servers.values():
            try:
                server.send_notice(target, message)
            except Exception as e:
                self.logger.error(f"Error sending notice to {server.config.name}: {e}")
    
    # Legacy function implementations for commands.py compatibility
    def _count_kraks_legacy(self, word: str, beverage: str):
        """Legacy drink counting function."""
        self.logger.debug(f"Legacy drink count: {word} ({beverage})")
        # This is now handled by DrinkTracker automatically
    
    def _send_notice(self, server, target: str, message: str):
        """Send a notice message."""
        if server:
            server.send_notice(target, message)
        else:
            self.logger.info(f"Console: {message}")
    
    def _send_electricity_price(self, irc, channel, text_or_parts):
        """Send electricity price information."""
        if not self.electricity_service:
            response = "⚡ Electricity price service not available. Please configure ELECTRICITY_API_KEY."
            self._send_response(irc, channel, response)
            return
        
        try:
            # Handle both string and list inputs for compatibility
            if isinstance(text_or_parts, list):
                # Called from IRC command with parts list
                args = text_or_parts[1:] if len(text_or_parts) > 1 else []
                if len(text_or_parts) > 1:
                    # Join back to string for further parsing
                    text = " ".join(text_or_parts[1:])
                else:
                    text = ""
            else:
                # Called with string (e.g., from tests or console)
                text = text_or_parts or ""
                args = text.split() if text else []
            
            # Parse command arguments
            parsed_args = self.electricity_service.parse_command_args(args)
            
            if parsed_args.get('error'):
                self._send_response(irc, channel, f"⚡ {parsed_args['error']}")
                return
            
            if parsed_args.get('show_stats'):
                # Show daily statistics
                stats_data = self.electricity_service.get_price_statistics(parsed_args['date'])
                response = self.electricity_service.format_statistics_message(stats_data)
            else:
                # Show specific hour price
                price_data = self.electricity_service.get_electricity_price(
                    hour=parsed_args['hour'],
                    date=parsed_args['date'],
                    include_tomorrow=not parsed_args['is_tomorrow']
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
        setattr(self, '_latency_start', time.time())
        return time.time()
    
    def _get_crypto_price(self, coin: str, currency: str = "eur"):
        """Get cryptocurrency price."""
        try:
            price_data = self.crypto_service.get_crypto_price(coin, currency)
            if price_data.get('error'):
                return f"Error: {price_data.get('message', 'Unknown error')}"
            return f"{price_data['price']:.2f} {currency.upper()}"
        except Exception as e:
            self.logger.error(f"Error getting crypto price: {e}")
            return "N/A"
    
    def _load_leet_winners(self):
        """Load leet winners data."""
        try:
            import json
            with open('leet_winners.json', 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def _save_leet_winners(self, data):
        """Save leet winners data."""
        try:
            import json
            with open('leet_winners.json', 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving leet winners: {e}")
    
    def _send_response(self, server, target: str, message: str):
        """Send a response using NOTICE or PRIVMSG based on USE_NOTICES setting."""
        if not server:
            print(message)
            return
            
        if self.use_notices:
            server.send_notice(target, message)
        else:
            server.send_message(target, message)
    
    def _send_weather(self, irc, channel, location):
        """Send weather information."""
        if not self.weather_service:
            response = "Weather service not available. Please configure WEATHER_API_KEY."
        else:
            try:
                weather_data = self.weather_service.get_weather(location)
                response = self.weather_service.format_weather_message(weather_data)
            except Exception as e:
                response = f"Error getting weather for {location}: {str(e)}"
        
        # Send response via IRC if we have server context, otherwise print to console
        if irc and hasattr(irc, 'send_message') and channel:
            self._send_response(irc, channel, response)
        elif irc and hasattr(irc, 'sendall') and channel:
            # Legacy IRC socket interface - use NOTICE or PRIVMSG based on setting
            msg_type = "NOTICE" if self.use_notices else "PRIVMSG"
            irc.sendall(f"{msg_type} {channel} :{response}\r\n".encode('utf-8'))
        else:
            print(response)
    
    def _send_scheduled_message(self, irc_client, channel, message, hour, minute, second, microsecond=0):
        """Send scheduled message."""
        try:
            from services.scheduled_message_service import send_scheduled_message
            message_id = send_scheduled_message(irc_client, channel, message, hour, minute, second, microsecond)
            self.logger.info(f"Scheduled message {message_id}: '{message}' to {channel} at {hour:02d}:{minute:02d}:{second:02d}.{microsecond:06d}")
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
    
    def _handle_ipfs_command(self, command_text, irc_client=None, target=None):
        """Handle IPFS commands."""
        try:
            from services.ipfs_service import handle_ipfs_command
            admin_password = os.getenv('ADMIN_PASSWORD')
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
                clean_message = clean_message[len(self.bot_name):].lstrip(':, ')
            
            # Get response from GPT service
            response = self.gpt_service.chat(clean_message, sender)
            return response
            
        except Exception as e:
            self.logger.error(f"Error in GPT chat: {e}")
            return "Sorry, I had trouble processing your message."
    
    def _wrap_irc_message_utf8_bytes(self, message, reply_target=None, max_lines=5, placeholder="..."):
        """Wrap IRC message for UTF-8 byte limits."""
        # Simple implementation - split by lines
        lines = message.split('\n')[:max_lines]
        if len(message.split('\n')) > max_lines:
            lines[-1] = lines[-1][:400] + placeholder
        return lines
    
    def _load_legacy_data(self):
        """Load legacy pickle data."""
        try:
            import pickle
            with open('data.pkl', 'rb') as f:
                return pickle.load(f)
        except (FileNotFoundError, pickle.PickleError):
            return {}
    
    def _save_legacy_data(self, data):
        """Save legacy pickle data."""
        try:
            import pickle
            with open('data.pkl', 'wb') as f:
                pickle.dump(data, f)
        except Exception as e:
            self.logger.error(f"Error saving legacy data: {e}")
    
    def _update_kraks_legacy(self, kraks, sender, words):
        """Update legacy kraks data."""
        if sender not in kraks:
            kraks[sender] = {}
        for word in words:
            if word not in kraks[sender]:
                kraks[sender][word] = 0
            kraks[sender][word] += 1
    
    def _log(self, message, level="INFO"):
        """Log a message."""
        self.logger.log(message, level)
    
    def _fetch_title(self, irc, target, text):
        """Fetch and display URL titles."""
        import re
        import requests
        from bs4 import BeautifulSoup
        
        # Find URLs in the text
        urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', text)
        
        for url in urls:
            try:
                response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    title = soup.find('title')
                    if title and title.string:
                        # Send title to IRC if we have a proper server object
                        if hasattr(irc, 'send_message'):
                            self._send_response(irc, target, f"📄 {title.string.strip()}")
                        else:
                            self.logger.info(f"Title: {title.string.strip()}")
            except Exception as e:
                self.logger.error(f"Error fetching title for {url}: {e}")
    
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
            "krak": 0, "kr1k": 0, "kr0k": 0, "narsk": 0, "parsk": 0,
            "tlup": 0, "marsk": 0, "tsup": 0, "plop": 0, "tsirp": 0
        }
    
    def toggle_tamagotchi(self, server, target, sender):
        """Toggle tamagotchi responses on/off."""
        self.tamagotchi_enabled = not self.tamagotchi_enabled
        
        status = "enabled" if self.tamagotchi_enabled else "disabled"
        emoji = "🐣" if self.tamagotchi_enabled else "💤"
        
        response = f"{emoji} Tamagotchi responses are now {status}."
        self._send_response(server, target, response)
        
        # Log the change
        self.logger.info(f"{sender} toggled tamagotchi to {status}", server.config.name)
        
        return response
    
    def _handle_youtube_urls(self, context: Dict[str, Any]):
        """Handle YouTube URLs by fetching and displaying video information."""
        server = context['server']
        target = context['target']
        text = context['text']
        
        # Only process in channels, not private messages
        if not target.startswith('#'):
            return
        
        try:
            video_id = self.youtube_service.extract_video_id(text)
            if video_id:
                video_data = self.youtube_service.get_video_info(video_id)
                message = self.youtube_service.format_video_info_message(video_data)
                self._send_response(server, target, message)
        except Exception as e:
            self.logger.error(f"Error handling YouTube URL: {e}")
    
    def _send_youtube_info(self, irc, channel, query_or_url):
        """Send YouTube video info or search results."""
        if not self.youtube_service:
            response = "YouTube service not available. Please configure YOUTUBE_API_KEY."
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
                search_data = self.youtube_service.search_videos(query_or_url, max_results=3)
                response = self.youtube_service.format_search_results_message(search_data)
            
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
                    self._send_response(irc, channel, "💸 Usage: !crypto <coin> [currency]. Example: !crypto btc eur")
                    return
                coin = args[0]
                currency = args[1] if len(args) > 1 else 'eur'
            else:
                # Called with string (e.g., from tests or console)
                args = text_or_parts.split() if text_or_parts else []
                if len(args) == 0:
                    self._send_response(irc, channel, "💸 Usage: !crypto <coin> [currency]. Example: !crypto btc eur")
                    return
                coin = args[0]
                currency = args[1] if len(args) > 1 else 'eur'
            
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
        server = context['server']
        target = context['target']
        sender = context['sender']
        
        # Only check in channels, not private messages
        if not target.startswith('#'):
            return
        
        try:
            # 🎯 CRITICAL: Get timestamp with MAXIMUM precision immediately upon message processing
            # This is the most accurate timestamp possible for when the message was processed
            timestamp = self.nanoleet_detector.get_timestamp_with_nanoseconds()
            
            # Check for leet achievement
            result = self.nanoleet_detector.check_message_for_leet(sender, timestamp)
            
            if result:
                achievement_message, achievement_level = result
                # Send achievement message to the channel immediately
                self._send_response(server, target, achievement_message)
                
                # Log the achievement with high precision
                self.logger.info(f"Nanoleet achievement: {achievement_level} for {sender} in {target} at {timestamp}")
                
        except Exception as e:
            self.logger.error(f"Error checking nanoleet achievement: {e}")
