"""
Message Handler Module

Handles all IRC message processing, command routing, URL title fetching,
and related functionality extracted from bot_manager.py.
"""

import os
import re
import sys
import threading
import time
from typing import Any, Dict, Optional

# Add project root to path for imports
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import requests  # noqa: E402

from config import TITLE_BLACKLIST_DOMAINS, TITLE_BLACKLIST_EXTENSIONS  # noqa: E402

# Import handlers mixins
from handlers.latency_tracker import LatencyTrackerMixin
from handlers.url_handler import UrlHandlerMixin
from lemmatizer import Lemmatizer
from logger import get_logger
from server import Server
from tamagotchi import TamagotchiBot
from word_tracking import DataManager, DrinkTracker, GeneralWords, WordAssociations
from word_tracking.bac_tracker import BACTracker

logger = get_logger("MessageHandler")


class MessageHandler(LatencyTrackerMixin, UrlHandlerMixin):
    """
    Handles IRC message processing and routing.

    This class manages:
    - Message parsing and validation
    - Command processing
    - URL title fetching
    - Word tracking and statistics
    - Leet detection and achievements
    - X API integration for Twitter posts
    """

    def __init__(self, service_manager, data_manager: DataManager):
        """
        Initialize the message handler.

        Args:
            service_manager: ServiceManager instance for accessing services
            data_manager: DataManager instance for persistence
        """
        self.service_manager = service_manager
        self.data_manager = data_manager

        # Initialize word tracking components
        self.drink_tracker = DrinkTracker(data_manager)
        self.bac_tracker = BACTracker(data_manager)
        self.general_words = GeneralWords(data_manager)
        self.tamagotchi = TamagotchiBot(data_manager)
        self.word_associations = WordAssociations(data_manager)

        # Initialize lemmatizer
        self.lemmatizer = self._initialize_lemmatizer()

        # Load configuration settings
        self.use_notices = self._load_use_notices_setting()
        self.tamagotchi_enabled = self._load_tamagotchi_enabled_setting()
        self.four_twenty_enabled = self._load_420_enabled_setting()

        # Cache sanaketju game instance to prevent duplicate command imports
        self._sanaketju_game = None

        # Initialize X API queue for rate limiting
        self.x_api_queue = []
        self.x_api_queue_lock = threading.Lock()
        self.x_api_last_request_time = 0
        self.x_api_rate_limit_seconds = 300  # 5 minutes

        # Initialize X cache settings
        self._initialize_x_cache_settings()

        # Latency measurement: track pending ping requests
        # Key: (server_name, nick), Value: send_time_ns
        self._pending_latency_requests = {}
        self._latency_lock = threading.Lock()

        # Lag storage: persistent storage for measured lags
        # Key: (server_name, nick), Value: lag_ms (float)
        self._lag_storage: Dict[tuple, float] = {}
        self._lag_storage_lock = threading.Lock()
        self._load_lag_storage()

        logger.info("Message handler initialized")

    def _initialize_lemmatizer(self) -> Optional[Lemmatizer]:
        """Initialize lemmatizer with graceful fallback."""
        try:
            return Lemmatizer()
        except Exception as e:
            logger.warning(f"Could not initialize lemmatizer: {e}")
            return None

    def _load_use_notices_setting(self) -> bool:
        """Load USE_NOTICES setting from config."""
        from config import get_config

        return get_config().use_notices

    def _load_tamagotchi_enabled_setting(self) -> bool:
        """Load TAMAGOTCHI_ENABLED setting from config."""
        from config import get_config

        return get_config().tamagotchi_enabled

    def _load_420_enabled_setting(self) -> bool:
        """Load 420 feature enabled setting from data manager."""
        try:
            state = self.data_manager.load_state()
            return state.get("420_enabled", True)  # Default to True
        except Exception:
            return True  # Default to enabled

    def _save_420_enabled_setting(self, enabled: bool):
        """Save 420 feature enabled setting to data manager."""
        try:
            state = self.data_manager.load_state()
            state["420_enabled"] = enabled
            self.data_manager.save_state(state)
        except Exception as e:
            logger.error(f"Error saving 420 enabled setting: {e}")

    def _initialize_x_cache_settings(self):
        """Initialize X cache settings with defaults if not already set."""
        try:
            state = self.data_manager.load_state()
            if "x_cache_settings" not in state:
                state["x_cache_settings"] = {
                    "expiration_hours": 1,  # Default: 1 hour
                    "max_entries": 50,  # Default: 50 URLs
                }
                self.data_manager.save_state(state)
                logger.debug("Initialized X cache settings with defaults")
        except Exception as e:
            logger.warning(f"Error initializing X cache settings: {e}")

    async def handle_message(
        self, server: Server, sender: str, ident_host: str, target: str, text: str
    ):
        """
        Handle incoming IRC messages from any server.

        Args:
            server: The Server instance that received the message
            sender: The nickname who sent the message
            ident_host: The ident@host of the sender
            target: The target (channel or bot's nick)
            text: The message content
        """
        try:
            # Create context for the message
            context = {
                "server": server,
                "server_name": server.config.name,
                "sender": sender,
                "ident_host": ident_host,
                "target": target,
                "text": text,
                "is_private": not target.startswith("#"),
                "bot_name": server.bot_name,
            }

            # 🎯 FIRST PRIORITY: Check for nanoleet achievements for maximum timestamp accuracy
            if sender.lower() != server.bot_name.lower():
                self._check_nanoleet_achievement(context)

            # 🌿 Check for 420 auto-response (only if not a command)
            # NOTE: This handles both leet detection and auto-response to avoid double responses
            if (
                sender.lower() != server.bot_name.lower()
                and not text.strip().startswith("!")
            ):
                # Check current enabled state from data manager for each message
                try:
                    state = self.data_manager.load_state()
                    four_twenty_enabled = state.get("420_enabled", True)
                except Exception:
                    four_twenty_enabled = True

                if four_twenty_enabled:
                    self._handle_420_response(context)

            # Process commands FIRST (before AI chat) to ensure commands are handled properly
            await self._process_commands(context)

            # Track words if not from the bot itself (but skip if this was a command)
            if (
                sender.lower() != server.bot_name.lower()
                and not text.strip().startswith("!")
            ):
                self._track_words(context)

            # Check for YouTube URLs and display video info
            if (
                self.service_manager.is_service_available("youtube")
                and sender.lower() != server.bot_name.lower()
            ):
                self._handle_youtube_urls(context)

            # Minimal AI chat for IRC: respond to private messages or mentions (but NOT commands)
            try:
                await self._handle_ai_chat(text, sender, target, server)
            except Exception as e:
                logger.warning(f"AI chat processing error: {e}")

            # Fetch and display page titles for URLs posted in channels (non-commands)
            if (
                sender.lower() != server.bot_name.lower()
                and target.startswith("#")
                and not text.startswith("!")
            ):
                try:
                    self._fetch_title(context["server"], target, text)
                except Exception as e:
                    logger.warning(f"Error in URL title fetcher: {e}")

        except Exception as e:
            logger.error(f"Error handling message from {server.config.name}: {e}")

    def _handle_notice(
        self, server: Server, sender: str, ident_host: str, target: str, text: str
    ):
        """
        Handle incoming notices from any server.

        Args:
            server: The Server instance that received the notice
            sender: The nickname who sent the notice
            target: The target (channel or bot's nick)
            text: The notice content
        """
        try:
            # Create context for the notice
            context = {
                "server": server,
                "server_name": server.config.name,
                "sender": sender,
                "ident_host": ident_host,
                "target": target,
                "text": text,
                "is_private": not target.startswith("#"),
                "bot_name": server.bot_name,
            }

            # Check for latency response first
            latency_msg = self._check_latency_response(server, sender, text)
            if latency_msg:
                logger.msg(latency_msg)

            # Process leet winners summary lines (first/last/multileet)
            try:
                self._process_leet_winner_summary(context)
            except Exception as e:
                logger.warning(f"Error processing leet winners summary: {e}")

            # Process ekavika winners summary lines (vika/eka winners)
            try:
                self._process_ekavika_winner_summary(context)
            except Exception as e:
                logger.warning(f"Error processing ekavika winners summary: {e}")

        except Exception as e:
            logger.error(f"Error handling notice from {server.config.name}: {e}")

    def _process_leet_winner_summary(self, context: Dict[str, Any]):
        """Process leet winner summary lines."""
        text = context.get("text", "")

        # Load existing winners
        winners = self._load_leet_winners()
        if not winners:
            winners = {}

        # Patterns for different winner types
        patterns = {
            "first": r"Ensimmäinen leettaaja oli (\w+) kello",
            "last": r"viimeinen oli (\w+) kello",
            "multileet": r"Lähimpänä multileettiä oli (\w+) kello",
        }

        for winner_type, pattern in patterns.items():
            match = re.search(pattern, text)
            if match:
                nick = match.group(1)
                if nick not in winners:
                    winners[nick] = {}
                winners[nick][winner_type] = winners[nick].get(winner_type, 0) + 1

        # Save updated winners
        self._save_leet_winners(winners)

    def _process_ekavika_winner_summary(self, context: Dict[str, Any]):
        """Process ekavika winner summary lines."""
        # TODO: Implement ekavika winner processing
        pass

    def _handle_fmi_warnings(self, warnings_list):
        """Handle FMI warnings."""
        try:
            subscriptions = None
            if hasattr(self, "bot_manager"):
                subscriptions = self.bot_manager._get_subscriptions_module()
            else:
                subscriptions = self._get_subscriptions_module()
            if not subscriptions:
                return

            subscribers = subscriptions.get_subscribers("varoitukset")
            if not subscribers:
                return

            # Send each warning to subscribers
            for warning in warnings_list:
                for nick_or_channel, server_name in subscribers:
                    # Find the server
                    server = None
                    if (
                        hasattr(self, "bot_manager")
                        and hasattr(self.bot_manager, "servers")
                        and server_name in self.bot_manager.servers
                    ):
                        server = self.bot_manager.servers[server_name]

                    if server:
                        if hasattr(self, "bot_manager"):
                            self.bot_manager._send_response(
                                server, nick_or_channel, warning
                            )
                        else:
                            self._send_response(server, nick_or_channel, warning)

        except Exception as e:
            logger.error(f"Error handling FMI warnings: {e}")

    def _handle_otiedote_release(self, data):
        """Handle otiedote release."""
        try:
            subscriptions = None
            if hasattr(self, "bot_manager"):
                subscriptions = self.bot_manager._get_subscriptions_module()
            else:
                subscriptions = self._get_subscriptions_module()
            if not subscriptions:
                return

            subscribers = subscriptions.get_subscribers("onnettomuustiedotteet")
            if not subscribers:
                return

            title = data.get("title", "Unknown Title")
            url = data.get("url", "")
            description = data.get("description", "")

            # Format the message
            message = f"📢 {title}"
            if description:
                message += f" - {description}"
            if url:
                message += f" | {url}"

            # Send to each subscriber
            for nick_or_channel, server_name in subscribers:
                # Find the server
                server = None
                if (
                    hasattr(self, "bot_manager")
                    and hasattr(self.bot_manager, "servers")
                    and server_name in self.bot_manager.servers
                ):
                    server = self.bot_manager.servers[server_name]

                if server:
                    if hasattr(self, "bot_manager"):
                        self.bot_manager._send_response(
                            server, nick_or_channel, message
                        )
                    else:
                        self._send_response(server, nick_or_channel, message)

        except Exception as e:
            logger.error(f"Error handling otiedote release: {e}")

    def _console_weather(self, *args, **kwargs):
        """Console weather command."""
        # Mock implementation for tests
        pass

    def _send_latest_otiedote(self, server, target):
        """Send the latest otiedote information."""
        otiedote_service = self.service_manager.get_service("otiedote")
        if not otiedote_service:
            response = "📢 Otiedote service not available"
            self._send_response(server, target, response)
            return

        try:
            # Get latest otiedote from service
            latest_info = getattr(otiedote_service, "latest_otiedote", None)
            if latest_info:
                response = f"📢 {latest_info.get('title', 'No title')} - {latest_info.get('description', 'No description')}"
                if latest_info.get("url"):
                    response += f" | {latest_info['url']}"
            else:
                response = "📢 Ei tallennettua otiedote-tietoa"

            self._send_response(server, target, response)
        except Exception as e:
            logger.error(f"Error sending latest otiedote: {e}")
            response = "📢 Virhe otiedote-tiedoissa"
            self._send_response(server, target, response)

    def _handle_join(self, server: Server, sender: str, ident_host: str, channel: str):
        """Handle user join events."""
        server_name = server.config.name

        # Track when the bot itself joins a channel
        if sender.lower() == server.bot_name.lower():
            # Use bot_manager.joined_channels as the central tracking source
            if hasattr(self, "bot_manager") and self.bot_manager:
                if server_name not in self.bot_manager.joined_channels:
                    self.bot_manager.joined_channels[server_name] = set()
                self.bot_manager.joined_channels[server_name].add(channel)

                # Auto-select first automatically joined channel as active
                # This ensures there's always an active channel if any channels are joined
                if (
                    self.bot_manager.active_channel is None
                    and self.bot_manager.active_server is None
                ):
                    self.bot_manager.active_channel = channel
                    self.bot_manager.active_server = server_name

                    # Also sync with console_manager
                    if (
                        hasattr(self.bot_manager, "console_manager")
                        and self.bot_manager.console_manager
                    ):
                        self.bot_manager.console_manager.active_channel = channel
                        self.bot_manager.console_manager.active_server = server_name

                    logger.debug(
                        f"Auto-selected first joined channel {channel} on {server_name} as active"
                    )

            logger.info(f"Bot joined {channel} on {server_name}")
        else:
            # Track other user activity
            logger.server(f"{sender} joined {channel}", server_name)

    def _handle_part(self, server: Server, sender: str, channel: str, ident_host: str):
        """Handle user part events."""
        # Track user activity
        server_name = server.config.name
        logger.server(f"{sender} left {channel}", server_name)

    def _handle_quit(self, server: Server, sender: str, ident_host: str):
        """Handle user quit events."""
        # Track user activity
        server_name = server.config.name
        logger.server(f"{sender} quit", server_name)

    def _handle_numeric(self, server: Server, code: int, target: str, params: str):
        """
        Handle IRC numeric responses.

        Args:
            server: The Server instance that received the response
            code: The numeric response code (e.g., 353, 366)
            target: The target (usually the bot's nick)
            params: The response parameters
        """
        server_name = server.config.name

        try:
            # Only process NAMES responses if they were explicitly triggered by !ops command
            # Check if we have pending ops for this server
            if (
                not hasattr(server, "_pending_ops")
                or server_name not in server._pending_ops
            ):
                return  # No pending ops, ignore this NAMES response

            # Handle RPL_NAMREPLY (353) - user list for a channel
            if code == 353:
                # Extract channel and user list
                parts = params.split(":", 1)
                if len(parts) == 2:
                    channel_part, user_list = parts
                    channel = channel_part.strip().split()[-1]

                    # Only process if we have pending ops for this channel
                    if channel not in server._pending_ops[server_name]:
                        return

                    # Add users to the list
                    users = [
                        user.lstrip("@+").strip()
                        for user in user_list.split()
                        if user.strip()
                    ]
                    server._pending_ops[server_name][channel]["users"].extend(users)

                    logger.debug(
                        f"Collected {len(users)} users for {channel} on {server_name} (!ops command)"
                    )

            # Handle RPL_ENDOFNAMES (366) - end of names list
            elif code == 366:
                channel = params.split()[0] if params else ""

                # Only process if we have pending ops for this channel
                if (
                    channel in server._pending_ops[server_name]
                    and server._pending_ops[server_name][channel]["users"]
                ):
                    users = server._pending_ops[server_name][channel]["users"]

                    # Remove the bot's own nick from the list
                    users = [
                        user
                        for user in users
                        if user.lower() != server.bot_name.lower()
                    ]

                    if users:
                        # Send MODE commands to op all users
                        batch_size = 10
                        for i in range(0, len(users), batch_size):
                            batch = users[i : i + batch_size]  # noqa: E203
                            for user in batch:
                                try:
                                    server.send_raw(f"MODE {channel} +o {user}")
                                    logger.info(
                                        f"Opped {user} in {channel} on {server_name}"
                                    )
                                except Exception as e:
                                    logger.error(
                                        f"Failed to op {user} in {channel}: {e}"
                                    )

                    # Clean up the pending ops data
                    del server._pending_ops[server_name][channel]
                    if not server._pending_ops[server_name]:
                        del server._pending_ops[server_name]

                    logger.info(
                        f"Completed !ops for {channel} on {server_name} ({len(users)} users)"
                    )

        except Exception as e:
            logger.error(f"Error handling numeric response {code}: {e}")

    def _check_nanoleet_achievement(self, context: Dict[str, Any]):
        """Check for nanoleet achievements in message timestamp."""
        server = context["server"]
        target = context["target"]
        sender = context["sender"]
        user_message = context["text"]

        # Only check in channels, not private messages
        if not target.startswith("#"):
            return

        try:
            leet_detector = self.service_manager.get_service("leet_detector")
            if not leet_detector:
                return

            # Get timestamp with MAXIMUM precision immediately upon message processing
            timestamp = leet_detector.get_timestamp_with_nanoseconds()

            # Check for leet achievement, including the user's message text
            result = leet_detector.check_message_for_leet(
                sender, timestamp, user_message
            )

            if result:
                achievement_message, achievement_level = result
                if (
                    achievement_level != "leet"
                ):  # Filter out regular leet level messages
                    # Send achievement message to the channel immediately
                    self._send_response(server, target, achievement_message)

                # Log the achievement
                logger.info(
                    f"Leet achievement: {achievement_level} for {sender} in {target} at {timestamp} - message: {user_message}"
                )

        except Exception as e:
            logger.error(f"Error checking nanoleet achievement: {e}")

    def _check_420_leet_achievement(self, context: Dict[str, Any]):
        """Check for 420 special leet in message content and timestamp."""
        server = context["server"]
        target = context["target"]
        sender = context["sender"]
        user_message = context["text"]

        # Only check in channels, not private messages
        if not target.startswith("#"):
            return

        # Skip if it's a command
        if user_message.strip().startswith("!"):
            return

        try:
            leet_detector = self.service_manager.get_service("leet_detector")
            if not leet_detector:
                return

            # Get timestamp with nanoseconds for 420 detection
            timestamp = leet_detector.get_timestamp_with_nanoseconds()

            # Check for 420 leet achievement in the message content AND timestamp
            result = leet_detector.check_420_leet(sender, user_message, timestamp)

            if result:
                achievement_message, achievement_level = result
                # Send achievement message to the channel
                self._send_response(server, target, achievement_message)

                # Log the achievement
                logger.info(
                    f"420 leet: {achievement_level} for {sender} in {target} at {timestamp}"
                )

        except Exception as e:
            logger.error(f"Error checking 420 leet achievement: {e}")

    # 420 auto-response messages
    _420_AUTO_RESPONSES = [
        "🌿 420! 🌿",
        "🔥 Blaze it! 🔥",
        "🍃 High five! 🍃",
        "😎 420, man! 😎",
        "🌱 It's 420 somewhere! 🌱",
        "💨 Cloud nine! 💨",
        "🎉 4/20! 🎉",
        "🌿 Hyvä! 🌿",
        "💚 Green vibes! 💚",
        "✌️ Peace! ✌️",
        "☮️ Stay mellow! ☮️",
        "🌞 Good vibes! 🌞",
    ]

    def _handle_420_response(self, context: Dict[str, Any]):
        """Respond to 420 mentions in chat.

        This handles both the 420 auto-response AND the 420 leet achievement detection
        to avoid sending duplicate responses.
        """
        import random
        import re

        text = context["text"]
        target = context["target"]

        # Only check in channels, not private messages
        if not target.startswith("#"):
            return

        # Check if message contains "420" as a standalone number
        # Match 420 surrounded by word boundaries or whitespace
        if not re.search(r"\b420\b", text, re.IGNORECASE):
            return

        # Check current enabled state from data manager (not cached)
        try:
            state = self.data_manager.load_state()
            if not state.get("420_enabled", True):
                return  # 420 responses are disabled
        except Exception:
            pass  # If we can't load state, allow response

        # Check for 420 leet achievement in message AND timestamp
        try:
            sender = context["sender"]
            server = context["server"]
            leet_detector = self.service_manager.get_service("leet_detector")

            if leet_detector:
                timestamp = leet_detector.get_timestamp_with_nanoseconds()
                result = leet_detector.check_420_leet(sender, text, timestamp)

                if result:
                    # Send the special leet achievement message
                    achievement_message, achievement_level = result
                    self._send_response(server, target, achievement_message)
                    logger.info(
                        f"420 leet: {achievement_level} for {sender} in {target} at {timestamp}"
                    )
                    # Don't also send auto-response - leet achievement is special
                    return
        except Exception as e:
            logger.error(f"Error checking 420 leet achievement: {e}")

        # If no leet achievement, send regular auto-response
        response = random.choice(self._420_AUTO_RESPONSES)
        self._send_response(server, target, response)
        logger.debug(f"420 auto-response triggered in {target}")

    def _track_words(self, context: Dict[str, Any]):
        """Track words for statistics and drink tracking."""
        server_name = context["server_name"]
        sender = context["sender"]
        text = context["text"]
        target = context["target"]

        # Skip tracking if this is a command (starts with !)
        if text.strip().startswith("!"):
            return

        # Only track general words in channels, but allow drink tracking in private messages too
        is_private_message = not target.startswith("#")

        # Track drink words and get any drink word detections
        drink_words_found = self.drink_tracker.process_message(
            server=server_name, nick=sender, text=text
        )

        # Track general words
        self.general_words.process_message(
            server=server_name, nick=sender, text=text, target=target
        )

        # Track word associations (detected from "word (thing)" pattern)
        self.word_associations.process_message(server=server_name, text=text)

        # Track URLs in channels (not private messages)
        if target.startswith("#"):
            self._track_urls(context)

        # Check kraksdebug configuration for notifications
        kraksdebug_config = self.data_manager.load_kraksdebug_state()

        # Handle drink word notifications BEFORE adding to BAC tracker
        if drink_words_found:
            try:
                server = context["server"]

                # Send drink word notifications to the channel where the message originated (if configured)
                if (
                    target.startswith("#")
                    and kraksdebug_config.get("channels")
                    and target in kraksdebug_config["channels"]
                ):
                    self._send_drink_word_notifications(
                        server,
                        target,
                        sender,
                        server_name,
                        drink_words_found,
                        kraksdebug_config,
                    )

                # Send combined BAC and drink word notification to user in private messages
                # or when nick_notices is enabled and nick is whitelisted
                if not target.startswith("#"):  # Always send in private messages
                    self._send_drink_word_notifications_to_user(
                        server,
                        sender,
                        server_name,
                        drink_words_found,
                        kraksdebug_config,
                    )
                elif kraksdebug_config.get(
                    "nick_notices", False
                ) and sender in kraksdebug_config.get("nicks", []):
                    self._send_drink_word_notifications_to_user(
                        server,
                        sender,
                        server_name,
                        drink_words_found,
                        kraksdebug_config,
                    )

                # NOW add each drink to BAC tracker with actual alcohol content
                for (
                    drink_word,
                    specific_drink,
                    alcohol_grams,
                    opened_time,
                ) in drink_words_found:
                    self.bac_tracker.add_drink(
                        server_name, sender, alcohol_grams, opened_time
                    )
            except Exception as e:
                logger.error(f"Error updating BAC for {sender}: {e}")

        # Check for sanaketju word continuations (lazy load to prevent duplicate command imports)
        try:
            if self._sanaketju_game is None:
                from cmd_modules.games import get_sanaketju_game

                self._sanaketju_game = get_sanaketju_game()

            self._sanaketju_game._load_state(self.data_manager)

            if self._sanaketju_game.active and target.startswith("#"):
                # Only process words from whitelisted users
                sender_lower = sender.lower()
                if sender_lower not in self._sanaketju_game.notice_whitelist:
                    # User is not whitelisted, skip processing
                    pass
                else:
                    # Process words for potential chain continuation
                    words = re.findall(r"\b\w+\b", text.lower())
                    for word in words:
                        result = self._sanaketju_game.process_word(
                            word, sender, self.data_manager
                        )
                        if result:
                            # Valid word found! Send notice to all whitelisted participants
                            notice_msg = f"✅ {sender}: {word} (+{result['score']} pistettä, yhteensä {result['total_score']})"

                            # Send notice to all whitelisted participants (so the game can be played)
                            for participant in self._sanaketju_game.notice_whitelist:
                                try:
                                    if self.use_notices:
                                        context["server"].send_notice(
                                            participant, notice_msg
                                        )
                                    else:
                                        context["server"].send_message(
                                            participant, notice_msg
                                        )
                                except Exception as e:
                                    logger.warning(
                                        f"Failed to send sanaketju notice to {participant}: {e}"
                                    )

                            break  # Only process the first valid word in the message
        except Exception as e:
            logger.warning(f"Error processing sanaketju: {e}")

        # Update tamagotchi (only if enabled)
        if self.tamagotchi_enabled:
            should_respond, response = self.tamagotchi.process_message(
                server=server_name, nick=sender, text=text
            )

            # Send tamagotchi response if needed
            if should_respond and response:
                server = context["server"]
                self._send_response(server, target, response)

    def _send_drink_word_notifications(
        self, server, target, sender, server_name, drink_words_found, kraksdebug_config
    ):
        """Send drink word notifications to channel."""
        # Calculate current BAC (before this drink)
        current_bac_info = self.bac_tracker.get_user_bac(server_name, sender)
        current_bac = current_bac_info["current_bac"]

        # Calculate projected BAC after this drink
        total_grams = sum(alcohol_grams for _, _, alcohol_grams, _ in drink_words_found)
        projected_bac = current_bac + self._calculate_bac_increase(
            server_name, sender, total_grams
        )

        # Calculate sober time based on projected BAC
        projected_sober_time = self.bac_tracker._calculate_sober_time(
            server_name, sender, projected_bac
        )
        projected_driving_time = self.bac_tracker._calculate_driving_time(
            server_name, sender, projected_bac
        )

        # Get last drink grams (from this drink)
        last_drink_grams = total_grams

        # Format the message
        if projected_bac <= 0.0:
            bac_message = f"{sender}: 🍺 Promilles: {current_bac:.2f}‰ | After: {projected_bac:.2f}‰ (sober)"
        else:
            bac_message = f"{sender}: 🍺 Promilles: {current_bac:.2f}‰ | After: {projected_bac:.2f}‰"

        # Add last drink grams
        if last_drink_grams:
            bac_message += f" | Last: {last_drink_grams:.1f}g"

        # Add sober time (based on projected BAC)
        if projected_sober_time:
            bac_message += f" | Sober: ~{projected_sober_time}"

        # Add driving time (based on projected BAC)
        if projected_driving_time:
            bac_message += f" | Driving: ~{projected_driving_time}"

        combined_message = bac_message

        if drink_words_found:
            # Add drink word information to the message
            drink_words_formatted = []
            stats_messages = []
            for drink_word, info, _, _ in drink_words_found:
                if info:
                    drink_words_formatted.append(f"{drink_word} ({info})")
                else:
                    drink_words_formatted.append(drink_word)

                # Get drink word stats
                word_results = self.drink_tracker.search_drink_word(
                    drink_word, server_filter=server_name
                )
                word_total = word_results.get("total_occurrences", 0)

                # Get specific drink stats if info is provided
                drink_total = 0
                if info and info != "unspecified":
                    drink_results = self.drink_tracker.search_specific_drink(
                        info, server_filter=server_name
                    )
                    drink_total = drink_results.get("total_occurrences", 0)

                # Build stats message
                if drink_total > 0:
                    stats_messages.append(
                        f"{drink_word}: {word_total} total, {info}: {drink_total}"
                    )
                else:
                    stats_messages.append(f"{drink_word}: {word_total} total")

            # Remove duplicates
            drink_words_formatted = list(set(drink_words_formatted))
            drink_part = f" | {' | '.join(drink_words_formatted)}"
            stats_part = f" | {', '.join(set(stats_messages))}"
            combined_message += drink_part + stats_part

        # Send combined message as notice to the originating channel only
        try:
            if self.use_notices:
                server.send_notice(target, combined_message)
            else:
                server.send_message(target, combined_message)
        except Exception as e:
            logger.warning(f"Failed to send combined notice to {target}: {e}")

    def _calculate_bac_increase(
        self, server_name: str, nick: str, alcohol_grams: float
    ) -> float:
        """
        Calculate BAC increase for given alcohol amount.

        Args:
            server_name: Server name
            nick: User nickname
            alcohol_grams: Grams of pure alcohol

        Returns:
            BAC increase value
        """
        # Use the same Widmark formula calculation as in BACTacker.add_drink
        profile = self.bac_tracker.get_user_profile(server_name, nick)
        body_water = (
            self.bac_tracker._get_body_water_constant(profile["sex"])
            * profile["weight_kg"]
        )
        added_bac = alcohol_grams / body_water  # ‰
        return added_bac

    def _send_drink_word_notifications_to_user(
        self, server, sender, server_name, drink_words_found, kraksdebug_config
    ):
        """Send drink word notifications to user."""
        # Calculate current BAC (before this drink)
        current_bac_info = self.bac_tracker.get_user_bac(server_name, sender)
        current_bac = current_bac_info["current_bac"]

        # Calculate projected BAC after this drink
        total_grams = sum(alcohol_grams for _, _, alcohol_grams, _ in drink_words_found)
        projected_bac = current_bac + self._calculate_bac_increase(
            server_name, sender, total_grams
        )

        # Calculate sober time based on projected BAC
        projected_sober_time = self.bac_tracker._calculate_sober_time(
            server_name, sender, projected_bac
        )
        projected_driving_time = self.bac_tracker._calculate_driving_time(
            server_name, sender, projected_bac
        )

        # Get burn rate and peak
        burn_rate = self.bac_tracker.get_user_profile(server_name, sender).get(
            "burn_rate", 0.15
        )
        peak_bac = max(current_bac, projected_bac)

        # Get last drink grams (from this drink)
        last_drink_grams = total_grams

        # Format the message
        if projected_bac <= 0.0:
            bac_message = f"{sender}: 🍺 Promilles: {current_bac:.2f}‰ | After: {projected_bac:.2f}‰ (sober)"
        else:
            bac_message = f"{sender}: 🍺 Promilles: {current_bac:.2f}‰ | After: {projected_bac:.2f}‰"

        # Add burn rate
        bac_message += f" | Burn rate: {burn_rate:.2f}‰/h"

        # Add peak BAC
        bac_message += f" | Peak: {peak_bac:.2f}‰"

        # Add last drink grams
        if last_drink_grams:
            bac_message += f" | Last: {last_drink_grams:.1f}g"

        # Add sober time (based on projected BAC)
        if projected_sober_time:
            bac_message += f" | Sober: ~{projected_sober_time}"

        # Add driving time (based on projected BAC)
        if projected_driving_time:
            bac_message += f" | Driving: ~{projected_driving_time}"
            if projected_bac > 0.5:  # Add warning for high BAC
                bac_message += " ⚠️ Careful!"

        combined_message = bac_message

        if drink_words_found:
            # Add drink word information to the message
            drink_words_formatted = []
            stats_messages = []
            for drink_word, info, _, _ in drink_words_found:
                if info:
                    drink_words_formatted.append(f"{drink_word} ({info})")
                else:
                    drink_words_formatted.append(drink_word)

                # Get drink word stats
                word_results = self.drink_tracker.search_drink_word(
                    drink_word, server_filter=server_name
                )
                word_total = word_results.get("total_occurrences", 0)

                # Get specific drink stats if info is provided
                drink_total = 0
                if info and info != "unspecified":
                    drink_results = self.drink_tracker.search_specific_drink(
                        info, server_filter=server_name
                    )
                    drink_total = drink_results.get("total_occurrences", 0)

                # Build stats message
                if drink_total > 0:
                    stats_messages.append(
                        f"{drink_word}: {word_total} total, {info}: {drink_total}"
                    )
                else:
                    stats_messages.append(f"{drink_word}: {word_total} total")

            # Remove duplicates
            drink_words_formatted = list(set(drink_words_formatted))
            drink_part = f" | {' | '.join(drink_words_formatted)}"
            stats_part = f" | {', '.join(set(stats_messages))}"
            combined_message += drink_part + stats_part

        # Send combined message as notice to the sender
        try:
            if self.use_notices:
                server.send_notice(sender, combined_message)
            else:
                server.send_message(sender, combined_message)
        except Exception as e:
            logger.warning(f"Failed to send combined notice to {sender}: {e}")

    def _handle_youtube_urls(self, context: Dict[str, Any]):
        """Handle YouTube URLs by fetching and displaying video information."""
        server = context["server"]
        target = context["target"]
        text = context["text"]

        try:
            youtube_service = self.service_manager.get_service("youtube")
            if not youtube_service:
                return

            video_id = youtube_service.extract_video_id(text)
            if video_id:
                video_data = youtube_service.get_video_info(video_id)
                message = youtube_service.format_video_info_message(video_data)
                self._send_response(server, target, message)
                logger.info(f"Displayed YouTube info for video ID: {video_id}")
        except Exception as e:
            logger.error(f"Error handling YouTube URL: {e}")

    async def _handle_ai_chat(
        self, text: str, sender: str, target: str, server: Server
    ):
        """Handle AI chat responses for private messages and mentions."""
        gpt_service = self.service_manager.get_service("gpt")
        if not gpt_service:
            return

        is_private = not target.startswith("#")
        bot_lower = server.bot_name.lower()
        text_lower = text.lower() if isinstance(text, str) else ""

        is_mention = text_lower.startswith(f"{bot_lower}:") or text_lower.startswith(
            f"{bot_lower},"
        )

        # Check if message contains drink words (should be handled by drink tracking instead)
        contains_drink_words = False
        if self.drink_tracker:
            drink_words_found = self.drink_tracker.process_message(
                server=server.config.name, nick=sender, text=text
            )
            contains_drink_words = bool(drink_words_found)

        if (
            (is_private or is_mention)
            and not text.startswith("!")
            and not contains_drink_words
        ):
            ai_response = self._chat_with_gpt(text, sender)
            if ai_response:
                reply_target = sender if is_private else target
                # Send as multiple IRC lines (split by newline, wrap long lines)
                for line in str(ai_response).split("\n"):
                    line = line.rstrip()
                    if not line:
                        continue
                    try:
                        parts = self._wrap_irc_message_utf8_bytes(line, reply_target)
                    except Exception:
                        parts = [line]
                    for part in parts:
                        if part:
                            self._send_response(server, reply_target, part)

    async def _process_commands(self, context: Dict[str, Any]):
        """Process IRC commands and bot interactions."""
        server = context["server"]
        sender = context["sender"]
        ident_host = context["ident_host"]
        target = context["target"]
        text = context["text"]

        bot_functions = self._create_bot_functions(server, context)

        # Create a mock IRC message format for commands.py compatibility
        message = f":{sender}!{ident_host} PRIVMSG {target.lower()} :{text}"
        logger.debug(f"Constructed IRC message: {message}")

        try:
            logger.debug(
                f"Processing command from {sender} on {server.config.name}: {text}"
            )
            from command_loader import process_irc_command

            await process_irc_command(
                text,  # message body (!s, !np, etc)
                sender,  # nick
                target,  # channel or private target
                server,  # connection instance
                ident_host,  # ident@host
                bot_functions,  # function table
            )

            logger.debug(f"Finished processing command from {sender}")
        except Exception as e:
            logger.error(f"Error @ _process_commands: {e}")

    def _create_bot_functions(self, server: Server, context: Dict[str, Any]):
        """Create bot functions dictionary for command processing."""
        return {
            "data_manager": self.data_manager,
            "drink_tracker": self.drink_tracker,
            "bac_tracker": self.bac_tracker,
            "general_words": self.general_words,
            "word_associations": self.word_associations,
            "tamagotchi_bot": self.tamagotchi,
            "lemmat": self.lemmatizer,
            "server": server,
            "server_name": context["server_name"],
            "bot_name": server.bot_name,
            "dream_service": (
                self.service_manager.get_service("dream")
                if self.service_manager
                else None
            ),
            "latency_start": lambda: getattr(self, "_latency_start", 0),
            "set_latency_start": lambda value: setattr(self, "_latency_start", value),
            "notice_message": lambda msg, irc=None, target=None: self._send_response(
                irc or server, target or context["target"], msg
            ),
            "send_electricity_price": self._send_electricity_price,
            "measure_latency": self._measure_latency,
            "get_crypto_price": self._get_crypto_price,
            "send_youtube_info": self._send_youtube_info,
            "send_imdb_info": self._send_imdb_info,
            "send_crypto_price": self._send_crypto_price,
            "load_leet_winners": self._load_leet_winners,
            "save_leet_winners": self._save_leet_winners,
            "get_alko_product": self._get_alko_product,
            "check_drug_interactions": self._check_drug_interactions,
            "send_weather": self._send_weather,
            "send_scheduled_message": self._send_scheduled_message,
            "get_eurojackpot_numbers": self._get_eurojackpot_numbers,
            "search_youtube": self._search_youtube,
            "handle_ipfs_command": self._handle_ipfs_command,
            "lookup": lambda irc: context["server_name"],
            "format_counts": self._format_counts,
            "chat_with_gpt": lambda msg, sender=None: self._chat_with_gpt(
                msg, sender or context["sender"]
            ),
            "wrap_irc_message_utf8_bytes": self._wrap_irc_message_utf8_bytes,
            "send_message": lambda irc, target, msg: server.send_message(target, msg),
            "log": logger,
            "fetch_title": self._fetch_title,
            "subscriptions": self._get_subscriptions_module(),
            "DRINK_WORDS": self._get_drink_words(),
            "get_latency_start": lambda: getattr(self, "_latency_start", 0),
            "toggle_tamagotchi": lambda srv, tgt, snd: self.toggle_tamagotchi(
                srv, tgt, snd
            ),
            "stop_event": None,  # Will be set by bot manager
            "set_quit_message": None,  # Will be set by bot manager
            "set_openai_model": None,  # Will be set by bot manager
            "bot_manager": getattr(self, "bot_manager", None),
        }

    def _send_response(self, server, target: str, message: str):
        """Send a response using NOTICE or PRIVMSG based on USE_NOTICES setting."""
        # Handle console mode (no server) or None target
        if not server:  # Console output
            logger.msg(message, "MSG")
            return

        # Handle None target - default to console output
        if not target:
            logger.msg(message, "MSG")
            return

        # For console target, skip server connection check - console commands work offline
        if target == "console":
            logger.msg(message, "MSG")
            return

        # Don't send messages if we're not connected to the server
        if not server.connected:
            logger.debug(f"Not sending message to {target}: server not connected")
            return

        # Don't send messages if target is a channel and we haven't joined it
        if target.startswith("#"):
            # For test mocks, skip channel validation entirely to avoid Mock object issues
            try:
                server_name = server.config.name
                # If server_name is a Mock object, skip validation
                if hasattr(server_name, "_mock_name") or str(
                    type(server_name)
                ).startswith("<class 'unittest.mock."):
                    pass  # Skip validation for Mock objects
                else:
                    target_normalized = target.lower()

                    # Use bot_manager.joined_channels as the central tracking source
                    if hasattr(self, "bot_manager") and self.bot_manager:
                        if server_name not in self.bot_manager.joined_channels:
                            self.bot_manager.joined_channels[server_name] = set()
                        joined_channels_normalized = {
                            ch.lower()
                            for ch in self.bot_manager.joined_channels.get(
                                server_name, set()
                            )
                        }
                        if target_normalized not in joined_channels_normalized:
                            logger.debug(
                                f"Channel {target} not in joined_channels, adding it now (server: {server_name})"
                            )
                            self.bot_manager.joined_channels[server_name].add(target)
            except (AttributeError, TypeError):
                # If anything goes wrong with channel validation, skip it
                pass

        # Log IRC responses to console for visibility
        server_name = getattr(server.config, "name", "unknown")
        clean_message = message.replace("\n", " | ").replace("\r", "").strip()
        logger.debug(
            f"Sending response to {target} on {server_name}: {clean_message[:100]}"
        )
        logger.msg(f"[{server_name}:{target}] {clean_message}", "MSG")

        try:
            if self.use_notices:
                server.send_notice(target, message)
            else:
                server.send_message(target, message)
        except Exception as e:
            logger.error(f"Error sending message to {target}: {e}")

    def _chat_with_gpt(self, message, sender="user"):
        """Chat with GPT."""
        gpt_service = self.service_manager.get_service("gpt")
        if not gpt_service:
            return "Sorry, AI chat is not available. Please configure OPENAI_API_KEY."

        try:
            # Clean the message by removing bot name mentions
            clean_message = message
            if clean_message.lower().startswith(sender.lower()):
                # Remove sender name and common separators
                clean_message = clean_message[len(sender) :].lstrip(":, ")  # noqa: E203

            # Get response from GPT service
            response = gpt_service.chat(clean_message, sender)
            return response

        except Exception as e:
            logger.error(f"Error in GPT chat: {e}")
            return "Sorry, I had trouble processing your message."

    def _wrap_irc_message_utf8_bytes(
        self, message, reply_target=None, max_lines=10, placeholder="..."
    ):
        """Wrap a message into IRC-safe UTF-8 lines by byte length."""
        if message is None:
            return []

        safe_byte_limit = 425  # conservative payload limit per line
        paragraphs = str(message).split("\n")
        out_lines = []

        def flush_chunk(chunk_words):
            if not chunk_words:
                return
            out_lines.append(" ".join(chunk_words))

        for para in paragraphs:
            if not para:
                out_lines.append("")
                continue

            words = para.split(" ")
            current_words = []
            current_bytes = 0

            for w in words:
                sep = 1 if current_words else 0
                tentative = len(w.encode("utf-8")) + sep
                if current_bytes + tentative <= safe_byte_limit:
                    current_words.append(w)
                    current_bytes += tentative
                else:
                    flush_chunk(current_words)
                    if len(out_lines) >= max_lines:
                        break
                    if len(w.encode("utf-8")) > safe_byte_limit:
                        b = w.encode("utf-8")
                        start = 0
                        while start < len(b):
                            remaining_lines = max_lines - len(out_lines)
                            if remaining_lines <= 0:
                                break
                            take = min(safe_byte_limit, len(b) - start)
                            while take > 0:
                                try:
                                    chunk = b[
                                        start : start + take  # noqa: E203
                                    ].decode("utf-8")
                                    break
                                except UnicodeDecodeError:
                                    take -= 1
                            if take <= 0:
                                start += 1
                                continue
                            out_lines.append(chunk)
                            start += take
                            if len(out_lines) >= max_lines:
                                break
                        current_words = []
                        current_bytes = 0
                    else:
                        current_words = [w]
                        current_bytes = len(w.encode("utf-8"))

            if len(out_lines) < max_lines and current_words:
                flush_chunk(current_words)

            if len(out_lines) >= max_lines:
                break

        if len(out_lines) > max_lines:
            out_lines = out_lines[:max_lines]
        if len(out_lines) == max_lines:
            last = out_lines[-1]
            last_bytes = last.encode("utf-8")
            ph_bytes = placeholder.encode("utf-8")
            if len(last_bytes) + len(ph_bytes) > safe_byte_limit:
                trim_to = safe_byte_limit - len(ph_bytes)
                while trim_to > 0:
                    try:
                        last = last_bytes[:trim_to].decode("utf-8")
                        break
                    except UnicodeDecodeError:
                        trim_to -= 1
                out_lines[-1] = last + placeholder
            else:
                out_lines[-1] = last + placeholder

        return out_lines

    def _fetch_title(self, irc, target, text):
        """Fetch and display URL titles or X/Twitter post content (excluding blacklisted URLs and file types)."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            BeautifulSoup = None

        # Find URLs in the text
        urls = re.findall(
            r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
            text,
        )

        for url in urls:
            # Handle X/Twitter URLs specially
            if self._is_x_url(url):
                self._fetch_x_post_content(irc, target, url)
                continue

            # Skip blacklisted URLs
            if self._is_url_blacklisted(url):
                continue

            try:
                response = requests.get(
                    url, timeout=10, headers={"User-Agent": "Mozilla/5.0"}
                )
                if response.status_code == 200:
                    content_type = response.headers.get("Content-Type", "").lower()
                    if (
                        "text/html" not in content_type
                        and "application/xhtml+xml" not in content_type
                    ):
                        logger.debug(f"Skipping non-HTML content: {content_type}")
                        continue

                    cleaned_title = None
                    if BeautifulSoup is not None:
                        try:
                            soup = BeautifulSoup(response.content, "html.parser")
                            title_tag = soup.find("title")
                            if title_tag and getattr(title_tag, "string", None):
                                cleaned_title = re.sub(
                                    r"\s+", " ", title_tag.string.strip()
                                )
                        except Exception:
                            cleaned_title = None

                    if not cleaned_title:
                        try:
                            text_content = (
                                response.content.decode("utf-8", errors="ignore")
                                if isinstance(response.content, (bytes, bytearray))
                                else str(response.content)
                            )
                            m = re.search(
                                r"<title[^>]*>(.*?)</title>",
                                text_content,
                                re.IGNORECASE | re.DOTALL,
                            )
                            if m:
                                cleaned_title = re.sub(r"\s+", " ", m.group(1).strip())
                        except Exception:
                            cleaned_title = None

                    if cleaned_title:
                        if self._is_title_banned(cleaned_title):
                            logger.debug(f"Skipping banned title: {cleaned_title}")
                            continue

                        if hasattr(irc, "send_message"):
                            self._send_response(irc, target, f"📄 {cleaned_title}")
                        else:
                            logger.info(f"Title: {cleaned_title}")
            except Exception as e:
                logger.error(f"Error fetching title for {url}: {e}")

    @staticmethod
    def _is_youtube_url(url: str) -> bool:
        """Check if a URL is a YouTube URL."""
        youtube_patterns = [
            r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([\w\-_]*)",
            r"(?:https?://)?(?:www\.)?youtu\.be/([\w\-_]+)",
            r"(?:https?://)?(?:www\.)?youtube\.com/embed/([\w\-_]*)",
            r"(?:https?://)?(?:www\.)?youtube\.com/v/([\w\-_]*)",
            r"(?:https?://)?(?:m\.)?youtube\.com/watch\?v=([\w\-_]*)",
            r"(?:https?://)?(?:music\.)?youtube\.com/watch\?v=([\w\-_]*)",
            r"(?:https?://)?(?:www\.)?youtube\.com/shorts/([\w\-_]+)",
        ]

        for pattern in youtube_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return True
        return False

    @staticmethod
    def _is_x_url(url: str) -> bool:
        """Check if a URL is an X/Twitter URL."""
        x_patterns = [
            r"(?:https?://)?(?:www\.)?(?:x\.com|twitter\.com)",
        ]

        for pattern in x_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return True
        return False

    def _fetch_x_post_content(self, irc, target, url: str):
        """Fetch X/Twitter post content using X API and send to channel."""
        try:
            # Extract post ID from URL
            match = re.search(
                r"(?:https?://)?(?:www\.)?(?:x\.com|twitter\.com)/\w+/status/(\d+)",
                url,
                re.IGNORECASE,
            )

            if not match:
                logger.warning(f"Could not parse X URL: {url}")
                return

            post_id = match.group(1)

            # Check cache first
            cached_response = self._get_cached_x_response(url)
            if cached_response:
                logger.debug(f"Using cached X response for {url}")
                if hasattr(irc, "send_message"):
                    self._send_response(irc, target, f"🐦 {cached_response}")
                else:
                    logger.info(f"X Post (cached): {cached_response}")
                return

            # Check if enough time has passed since last request
            current_time = time.time()
            time_since_last_request = current_time - self.x_api_last_request_time

            if time_since_last_request < self.x_api_rate_limit_seconds:
                # Rate limited - add to queue instead of processing immediately
                logger.info(f"X API rate limited, queuing request for post {post_id}")
                with self.x_api_queue_lock:
                    self.x_api_queue.append((irc, target, url))
                # Start queue processing thread if not already running
                if (
                    not hasattr(self, "x_api_queue_thread")
                    or not self.x_api_queue_thread.is_alive()
                ):
                    self.x_api_queue_thread = threading.Thread(
                        target=self._process_x_api_queue,
                        daemon=True,
                        name="X-API-Queue",
                    )
                    self.x_api_queue_thread.start()
                return

            # Process the request immediately
            self._process_x_api_request(irc, target, url, post_id)

        except Exception as e:
            logger.error(f"Error fetching X post content for {url}: {e}")

    def _get_cached_x_response(self, url: str) -> Optional[str]:
        """Get cached X response for URL if available."""
        try:
            state = self.data_manager.load_state()
            x_cache = state.get("x_cache", {})
            cached_item = x_cache.get(url)

            if cached_item:
                cached_time = cached_item.get("timestamp", 0)
                current_time = time.time()

                x_cache_settings = state.get("x_cache_settings", {})
                cache_expiration_hours = x_cache_settings.get("expiration_hours", 1)
                cache_expiration_seconds = cache_expiration_hours * 3600

                if current_time - cached_time < cache_expiration_seconds:
                    return cached_item.get("response")

                else:
                    del x_cache[url]
                    self.data_manager.save_state(state)

        except Exception as e:
            logger.warning(f"Error checking X cache: {e}")

        return None

    def _cache_x_response(self, url: str, response: str):
        """Cache X response for URL."""
        try:
            state = self.data_manager.load_state()
            if "x_cache" not in state:
                state["x_cache"] = {}

            state["x_cache"][url] = {"response": response, "timestamp": time.time()}

            # Manage cache size
            self._manage_x_cache_size(state["x_cache"])
            self.data_manager.save_state(state)

        except Exception as e:
            logger.warning(f"Error caching X response: {e}")

    def _manage_x_cache_size(self, x_cache: Dict[str, Dict]):
        """Manage X cache size to prevent it from growing too large."""
        try:
            state = self.data_manager.load_state()
            x_cache_settings = state.get("x_cache_settings", {})
            max_entries = x_cache_settings.get("max_entries", 50)
            max_entries = max(max_entries, 10)

            if len(x_cache) > max_entries:
                sorted_entries = sorted(
                    x_cache.items(), key=lambda x: x[1]["timestamp"]
                )
                entries_to_keep = sorted_entries[-max_entries:]
                x_cache.clear()
                x_cache.update(dict(entries_to_keep))

        except Exception as e:
            logger.warning(f"Error reading X cache settings: {e}")
            max_entries = 50

    def _process_x_api_request(self, irc, target, url, post_id):
        """Process a single X API request."""
        try:
            # Update last request time
            self.x_api_last_request_time = time.time()

            try:
                from xdk import Client as XClient

                x_client_available = True
            except ImportError:
                x_client_available = False

            if not x_client_available or not XClient:
                logger.warning("X API client not available")
                return

            # Get bearer token from environment
            bearer_token = os.getenv("X_BEARER_TOKEN")
            if not bearer_token:
                logger.warning("X_BEARER_TOKEN not configured")
                return

            # Create X client
            try:
                x_client = XClient(bearer_token=bearer_token)
            except Exception as e:
                logger.error(f"Failed to create X client: {e}")
                if hasattr(irc, "send_message"):
                    self._send_response(
                        irc, target, f"🐦 Error creating X API client: {str(e)[:100]}"
                    )
                return

            # Fetch post by ID
            try:
                response = x_client.posts.get_by_id(post_id)
                if response and hasattr(response, "data") and response.data:
                    post_data = response.data
                    post_text = post_data.get("text", "")
                    if post_text:
                        post_text = re.sub(r"\s+", " ", post_text).strip()
                        self._cache_x_response(url, post_text)

                        if hasattr(irc, "send_message"):
                            self._send_response(irc, target, f"🐦 {post_text}")
                        else:
                            logger.info(f"X Post: {post_text}")
                    else:
                        logger.debug(f"No text content found in X post {post_id}")
                else:
                    logger.debug(f"No data returned for X post {post_id}")

            except Exception as e:
                error_str = str(e).lower()

                if "429" in error_str or "too many requests" in error_str:
                    logger.warning(f"X API rate limited for post {post_id}: {e}")
                    # Re-queue this request
                    with self.x_api_queue_lock:
                        scheduled_time = time.time() + self.x_api_rate_limit_seconds
                        self.x_api_queue.append((irc, target, url, scheduled_time))

                    if (
                        not hasattr(self, "x_api_queue_thread")
                        or not self.x_api_queue_thread.is_alive()
                    ):
                        self.x_api_queue_thread = threading.Thread(
                            target=self._process_x_api_queue,
                            daemon=True,
                            name="X-API-Queue",
                        )
                        self.x_api_queue_thread.start()

                    wait_minutes = int(self.x_api_rate_limit_seconds // 60)
                    logger.info(
                        f"🐦 X API rate limited. Request queued for ~{wait_minutes} minute{'s' if wait_minutes != 1 else ''}."
                    )

                    return

                elif "401" in error_str or "unauthorized" in error_str:
                    logger.error(f"X API authentication failed for post {post_id}: {e}")
                elif "403" in error_str or "forbidden" in error_str:
                    logger.error(f"X API access forbidden for post {post_id}: {e}")
                else:
                    logger.error(f"Error fetching X post {post_id}: {e}")

        except Exception as e:
            logger.error(f"Error processing X API request for {url}: {e}")

    def _process_x_api_queue(self):
        """Process queued X API requests with proper rate limiting."""
        logger.info("Started X API queue processing thread")

        while True:
            try:
                with self.x_api_queue_lock:
                    if not self.x_api_queue:
                        break

                    request = self.x_api_queue.pop(0)
                    if len(request) == 4:
                        irc, target, url, scheduled_time = request
                        current_time = time.time()
                        if current_time < scheduled_time:
                            self.x_api_queue.append(request)
                            time.sleep(1)
                            continue
                    elif len(request) == 3:
                        irc, target, url = request
                    else:
                        logger.error(f"Invalid queue request format: {request}")
                        continue

                logger.info(f"Processing queued X API request: {url}")

                match = re.search(
                    r"(?:https?://)?(?:www\.)?(?:x\.com|twitter\.com)/\w+/status/(\d+)",
                    url,
                    re.IGNORECASE,
                )

                if not match:
                    logger.warning(f"Could not parse queued X URL: {url}")
                    continue

                post_id = match.group(1)
                bearer_token = os.getenv("X_BEARER_TOKEN")
                if not bearer_token:
                    logger.warning("X_BEARER_TOKEN not configured for queued request")
                    continue

                self._process_x_api_request(irc, target, url, post_id)
                time.sleep(self.x_api_rate_limit_seconds)

            except Exception as e:
                logger.error(f"Error in X API queue processing: {e}")
                time.sleep(1)

        logger.info("X API queue processing thread finished")
        if hasattr(self, "x_api_queue_thread"):
            self.x_api_queue_thread = None

    def _is_url_blacklisted(self, url: str) -> bool:
        """Check if a URL should be blacklisted from title fetching."""
        if self._is_youtube_url(url):
            return True

        if self._is_x_url(url):
            return True

        blacklisted_domains = os.getenv(
            "TITLE_BLACKLIST_DOMAINS",
            TITLE_BLACKLIST_DOMAINS,
        ).split(",")

        blacklisted_extensions = os.getenv(
            "TITLE_BLACKLIST_EXTENSIONS",
            TITLE_BLACKLIST_EXTENSIONS,
        ).split(",")

        url_lower = url.lower()

        for domain in blacklisted_domains:
            domain = domain.strip()
            if domain and domain in url_lower:
                logger.info(f"Skipping URL with blacklisted domain '{domain}': {url}")
                return True

        for ext in blacklisted_extensions:
            ext = ext.strip()
            if ext and url_lower.endswith(ext):
                logger.info(f"Skipping URL with blacklisted extension '{ext}': {url}")
                return True

        return False

    def _is_title_banned(self, title: str) -> bool:
        """Check if a title should be banned from being displayed."""
        banned_titles = os.getenv(
            "TITLE_BANNED_TEXTS",
            "Bevor Sie zu Google Maps weitergehen;Just a moment...;403 Forbidden;404 Not Found;Access Denied",
        ).split(";")

        title_lower = title.lower().strip()

        for banned_text in banned_titles:
            banned_text = banned_text.strip().lower()
            if banned_text and banned_text in title_lower:
                logger.info(f"Skipping title with banned text '{banned_text}': {title}")
                return True

        return False

    def _get_subscriptions_module(self):
        """Get subscriptions module."""
        try:
            import subscriptions

            return subscriptions
        except ImportError:

            class MockSubscriptions:
                def get_subscribers(self, topic):
                    return []

            return MockSubscriptions()

    def _get_drink_words(self):
        """Get drink words dictionary."""
        return {
            "krak": 0,
            "kr1k": 0,
            "kr0k": 0,
            "narsk": 0,
            "parsk": 0,
            "tlup": 0,
            "marsk": 0,
            "tsup": 0,
            "plop": 0,
            "tsirp": 0,
        }

    # Service proxy methods - these delegate to the service manager
    def _send_electricity_price(self, irc, channel, text_or_parts):
        """Handle the !sähkö command for hourly or 15-minute prices."""
        electricity_service = self.service_manager.get_service("electricity")
        if not electricity_service:
            response = "⚡ Electricity price service not available. Please configure ELECTRICITY_API_KEY."
            self._send_response(irc, channel, response)
            return

        try:
            if isinstance(text_or_parts, list):
                args = text_or_parts
                text = " ".join(args) if args else ""
            else:
                text = text_or_parts or ""
                args = text.split() if text else []

            parsed_args = electricity_service.parse_command_args(args)

            if parsed_args.get("error"):
                logger.error(f"Electricity command parse error: {parsed_args['error']}")
                self._send_response(irc, channel, f"⚡ {parsed_args['error']}")
                return

            if parsed_args.get("show_stats"):
                stats_data = electricity_service.get_price_statistics(
                    parsed_args["date"]
                )
                response = electricity_service.format_statistics_message(
                    stats_data, parsed_args.get("palette", 1)
                )
            elif parsed_args.get("show_longbar"):
                # Get daily prices for longbar
                daily_prices = electricity_service.get_daily_prices(parsed_args["date"])
                if daily_prices.get("error"):
                    response = f"⚡ {daily_prices.get('message', 'Error getting daily prices')}"
                else:
                    response = electricity_service._create_long_price_bar_graph(
                        daily_prices["interval_prices"], parsed_args.get("palette", 1)
                    )
            elif parsed_args.get("show_all_hours"):
                all_prices = []
                for h in range(24):
                    price_data = electricity_service.get_electricity_price(
                        hour=h, date=parsed_args["date"]
                    )
                    if price_data.get("error"):
                        all_prices.append({"hour": h, "error": price_data["message"]})
                    else:
                        all_prices.append(price_data)
                response = electricity_service.format_daily_prices_message(
                    all_prices, is_tomorrow=parsed_args["is_tomorrow"]
                )
            else:
                price_data = electricity_service.get_electricity_price(
                    hour=parsed_args.get("hour"),
                    quarter=parsed_args.get("quarter"),
                    date=parsed_args["date"],
                )
                response = electricity_service.format_price_message(
                    price_data, is_tomorrow_request=parsed_args["is_tomorrow"]
                )

            self._send_response(irc, channel, response)

        except Exception as e:
            error_msg = f"⚡ Error getting electricity price: {str(e)}"
            logger.error(f"Electricity price error: {e}")
            self._send_response(irc, channel, error_msg)

    def _measure_latency(self):
        """Measure latency."""
        setattr(self, "_latency_start", time.time())
        return time.time()

    def _send_latency_ping(self, server, target: str) -> str:
        """
        Send a latency ping to a nick.

        Args:
            server: The Server instance
            target: The target nick to ping

        Returns:
            Confirmation message
        """
        import time

        send_time_ns = time.time_ns()
        with self._latency_lock:
            # Store the send time with (server_name, nick) as key
            key = (server.config.name, target.lower())
            self._pending_latency_requests[key] = send_time_ns

        # Send !ping to the target
        server.send_message(target, "!ping")

        return f"✅ Latency ping sent to {target}"

    def _check_latency_response(self, server, sender: str, text: str) -> Optional[str]:
        """
        Check if a notice is a latency response and calculate latency.

        Args:
            server: The Server instance
            sender: The nick who sent the notice
            text: The notice text

        Returns:
            Latency message if this was a latency response, None otherwise
        """
        import re
        import time

        # Pattern to match "Kello on HH.MM.SS,NNNNNNNNN" (Finnish time format)
        # Example: "Kello on 8.55.37,388420605"
        time_pattern = r"Kello on (\d+)\.(\d+)\.(\d+),(\d+)"
        match = re.search(time_pattern, text)

        if not match:
            return None

        # Check if we have a pending request for this nick
        key = (server.config.name, sender.lower())
        with self._latency_lock:
            send_time_ns = self._pending_latency_requests.get(key)
            if send_time_ns is None:
                return None
            # Remove the pending request
            del self._pending_latency_requests[key]

        # Calculate round-trip time
        receive_time_ns = time.time_ns()
        rtt_ns = receive_time_ns - send_time_ns
        rtt_ms = rtt_ns / 1_000_000.0

        # Store the lag for future use
        self._store_lag(server.config.name, sender, rtt_ms)

        return f"📡 Latency to {sender}: {rtt_ms:.2f} ms (RTT)"

    def _load_lag_storage(self):
        """Load lag storage from data file."""
        try:
            data = self.data_manager.load_data("lag_storage")
            if data and isinstance(data, dict):
                # Convert dict with string keys back to tuple keys
                for key_str, value in data.items():
                    if isinstance(key_str, str) and "|" in key_str:
                        parts = key_str.split("|")
                        if len(parts) == 2:
                            key = (parts[0], parts[1])
                            self._lag_storage[key] = float(value)
                logger.info(f"Loaded {len(self._lag_storage)} lag measurements")
        except Exception as e:
            logger.debug(f"Could not load lag storage: {e}")

    def _save_lag_storage(self):
        """Save lag storage to data file."""
        try:
            # Convert tuple keys to string keys for JSON serialization
            data = {}
            for key, value in self._lag_storage.items():
                if isinstance(key, tuple) and len(key) == 2:
                    key_str = f"{key[0]}|{key[1]}"
                    data[key_str] = value
            self.data_manager.save_data("lag_storage", data)
        except Exception as e:
            logger.error(f"Could not save lag storage: {e}")

    def _store_lag(self, server_name: str, nick: str, lag_ms: float):
        """
        Store lag measurement for a nick on a server.

        Args:
            server_name: Name of the server
            nick: Nick to store lag for
            lag_ms: Lag in milliseconds (RTT)
        """
        key = (server_name.lower(), nick.lower())
        with self._lag_storage_lock:
            self._lag_storage[key] = lag_ms
        # Save asynchronously
        threading.Thread(target=self._save_lag_storage, daemon=True).start()
        logger.debug(f"Stored lag for {nick} on {server_name}: {lag_ms:.2f} ms")

    def _get_lag(self, server_name: str, nick: str) -> Optional[float]:
        """
        Get stored lag for a nick on a server.

        Args:
            server_name: Name of the server
            nick: Nick to get lag for

        Returns:
            Lag in milliseconds, or None if not found
        """
        key = (server_name.lower(), nick.lower())
        with self._lag_storage_lock:
            return self._lag_storage.get(key)

    def _list_lags(self, server_name: Optional[str] = None) -> Dict[tuple, float]:
        """
        List all stored lags, optionally filtered by server.

        Args:
            server_name: Optional server name to filter by

        Returns:
            Dictionary of (server, nick) -> lag_ms
        """
        with self._lag_storage_lock:
            if server_name:
                return {
                    k: v
                    for k, v in self._lag_storage.items()
                    if k[0] == server_name.lower()
                }
            return dict(self._lag_storage)

    def _clear_lag(self, server_name: str, nick: str) -> bool:
        """
        Clear stored lag for a nick on a server.

        Args:
            server_name: Name of the server
            nick: Nick to clear lag for

        Returns:
            True if cleared, False if not found
        """
        key = (server_name.lower(), nick.lower())
        with self._lag_storage_lock:
            if key in self._lag_storage:
                del self._lag_storage[key]
                threading.Thread(target=self._save_lag_storage, daemon=True).start()
                return True
        return False

    def _get_crypto_price(self, coin: str, currency: str = "eur"):
        """Get cryptocurrency price."""
        crypto_service = self.service_manager.get_service("crypto")
        if crypto_service:
            try:
                price_data = crypto_service.get_crypto_price(coin, currency)
                if price_data.get("error"):
                    return f"Error: {price_data.get('message', 'Unknown error')}"
                return f"{price_data['price']:.2f} {currency.upper()}"
            except Exception as e:
                logger.error(f"Error getting crypto price: {e}")
        return "N/A"

    def _load_leet_winners(self):
        """Load leet winners data."""
        return self.data_manager.load_leet_winners_state()

    def _save_leet_winners(self, data):
        """Save leet winners data."""
        self.data_manager.save_leet_winners_state(data)

    def _get_alko_product(self, query: str) -> str:
        """Get Alko product information."""
        alko_service = self.service_manager.get_service("alko")
        if alko_service:
            try:
                product = alko_service.get_product_info(query)
                if product:
                    return alko_service.format_product_info(product)
                else:
                    return f"🍺 Product '{query}' not found"
            except Exception as e:
                logger.error(f"Error getting Alko product: {e}")
        return "🍺 Alko service not available"

    def _check_drug_interactions(self, drug_names: str) -> str:
        """Check drug interactions for given drug names."""
        drug_service = self.service_manager.get_service("drug")
        if not drug_service:
            return "💊 Drug service not available. Run src/debug/debug_drugs.py to scrape drug data first."

        try:
            # Split drug names and clean them
            drugs = [d.strip() for d in drug_names.split() if d.strip()]
            if not drugs:
                return "💊 Usage: !drugs <drug1> <drug2> ... (e.g., !drugs cannabis alcohol)"

            # Check interactions
            result = drug_service.check_interactions(drugs)

            # Format response
            messages = []

            # Add warnings first
            if result["warnings"]:
                messages.extend(result["warnings"])

            # Add unknown drugs
            if result["unknown_drugs"]:
                unknown_list = ", ".join(result["unknown_drugs"])
                messages.append(f"💊 Unknown drugs: {unknown_list}")

            # If no interactions or warnings, show basic info
            if (
                not result["interactions"]
                and not result["warnings"]
                and not result["unknown_drugs"]
            ):
                # Show info for first drug
                first_drug = drugs[0]
                drug_info = drug_service.get_drug_info(first_drug)
                if drug_info:
                    messages.append(drug_service.format_drug_info(drug_info))
                else:
                    messages.append(f"💊 No information found for '{first_drug}'")

            if messages:
                return " | ".join(messages)
            else:
                return "💊 No interactions found between the specified drugs."

        except Exception as e:
            logger.error(f"Error checking drug interactions: {e}")
            return f"💊 Error checking drug interactions: {str(e)}"

    def _send_weather(self, irc, channel, location):
        """Send weather information."""
        weather_service = self.service_manager.get_service("weather")
        if weather_service:
            try:
                weather_data = weather_service.get_weather(location)
                if weather_data.get("error"):
                    error_msg = weather_service.format_weather_message(weather_data)
                    logger.error(f"Weather error for {location}: {error_msg}")
                    return
                response = weather_service.format_weather_message(weather_data)
            except Exception as e:
                error_msg = f"Error getting weather for {location}: {str(e)}"
                logger.error(error_msg)
                return

            if irc and hasattr(irc, "send_message") and channel:
                self._send_response(irc, channel, response)
            else:
                logger.info(response)

    def _send_scheduled_message(
        self, irc_client, channel, message, hour, minute, second, microsecond=0
    ):
        """Send scheduled message."""
        try:
            from services.scheduled_message_service import send_scheduled_message

            message_id = send_scheduled_message(
                irc_client, channel, message, hour, minute, second, microsecond
            )
            logger.info(
                f"Scheduled message {message_id}: '{message}' to {channel} at {hour:02d}:{minute:02d}:{second:02d}.{microsecond:06d}"
            )
            return f"✅ Message scheduled with ID: {message_id}"
        except Exception as e:
            logger.error(f"Error scheduling message: {e}")
            return f"❌ Error scheduling message: {str(e)}"

    def _get_eurojackpot_numbers(self):
        """Get Eurojackpot numbers."""
        try:
            from services.eurojackpot_service import get_eurojackpot_numbers

            return get_eurojackpot_numbers()
        except Exception as e:
            logger.error(f"Error getting Eurojackpot numbers: {e}")
            return f"❌ Error getting Eurojackpot info: {str(e)}"

    def _get_eurojackpot_results(self):
        """Get Eurojackpot results."""
        try:
            from services.eurojackpot_service import get_eurojackpot_results

            return get_eurojackpot_results()
        except Exception as e:
            logger.error(f"Error getting Eurojackpot results: {e}")
            return f"❌ Error getting Eurojackpot results: {str(e)}"

    def _search_youtube(self, query):
        """Search YouTube."""
        youtube_service = self.service_manager.get_service("youtube")
        if youtube_service:
            try:
                search_data = youtube_service.search_videos(query, max_results=3)
                return youtube_service.format_search_results_message(search_data)
            except Exception as e:
                logger.error(f"Error searching YouTube: {e}")
        return "YouTube service not available. Please configure YOUTUBE_API_KEY."

    def _send_youtube_info(self, irc, channel, query_or_url, max_results=1):
        """Send YouTube video info or search results."""
        youtube_service = self.service_manager.get_service("youtube")
        if not youtube_service:
            response = (
                "YouTube service not available. Please configure YOUTUBE_API_KEY."
            )
            self._send_response(irc, channel, response)
            return

        try:
            video_id = youtube_service.extract_video_id(query_or_url)

            if video_id:
                video_data = youtube_service.get_video_info(video_id)
                response = youtube_service.format_video_info_message(video_data)
            else:
                search_data = youtube_service.search_videos(query_or_url, max_results)
                response = youtube_service.format_search_results_message(search_data)

            self._send_response(irc, channel, response)

        except Exception as e:
            error_msg = f"🎥 Error with YouTube request: {str(e)}"
            logger.error(f"YouTube error: {e}")
            self._send_response(irc, channel, error_msg)

    def _send_imdb_info(self, irc, channel, query):
        """Send IMDb movie search results."""
        try:
            from services.imdb_service import create_imdb_service

            imdb_service = create_imdb_service()
            movie_data = imdb_service.search_movie(query)
            response = imdb_service.format_movie_info(movie_data)

            self._send_response(irc, channel, response)

        except Exception as e:
            error_msg = f"🎬 Error with IMDb search: {str(e)}"
            logger.error(f"IMDb error: {e}")
            self._send_response(irc, channel, error_msg)

    def _send_crypto_price(self, irc, channel, text_or_parts):
        """Send cryptocurrency price information."""
        try:
            if isinstance(text_or_parts, list):
                args = text_or_parts[1:] if len(text_or_parts) > 1 else []
                if len(args) == 0:
                    self._send_response(
                        irc,
                        channel,
                        "💸 Usage: !crypto <coin> [currency]. Example: !crypto btc eur",
                    )
                    return
                coin = args[0]
                currency = args[1] if len(args) > 1 else "eur"
            else:
                args = text_or_parts.split() if text_or_parts else []
                if len(args) == 0:
                    self._send_response(
                        irc,
                        channel,
                        "💸 Usage: !crypto <coin> [currency]. Example: !crypto btc eur",
                    )
                    return
                coin = args[0]
                currency = args[1] if len(args) > 1 else "eur"

            price = self._get_crypto_price(coin, currency)
            response = f"💸 {coin.capitalize()}: {price} {currency.upper()}"
            self._send_response(irc, channel, response)

        except Exception as e:
            error_msg = f"💸 Error getting crypto price: {str(e)}"
            logger.error(f"Crypto price error: {e}")
            self._send_response(irc, channel, error_msg)

    def _handle_ipfs_command(self, command_text, irc_client=None, target=None):
        """Handle IPFS commands."""
        try:
            from services.ipfs_service import handle_ipfs_command

            admin_password = os.getenv("ADMIN_PASSWORD")
            response = handle_ipfs_command(command_text, admin_password)

            if irc_client and target:
                self._send_response(irc_client, target, response)
            else:
                logger.info(f"IPFS command result: {response}")
                return response

        except Exception as e:
            error_msg = f"❌ IPFS error: {str(e)}"
            logger.error(f"Error handling IPFS command: {e}")
            if irc_client and target:
                self._send_response(irc_client, target, error_msg)
            else:
                return error_msg

    def _format_counts(self, data):
        """Format word counts."""
        if isinstance(data, dict):
            return ", ".join(f"{k}: {v}" for k, v in data.items())
        return str(data)

    def _track_urls(self, context: Dict[str, Any]):
        """Track URLs posted in messages and send duplicate notifications."""
        server = context["server"]
        sender = context["sender"]
        server_name = context["server_name"]
        target = context["target"]
        text = context["text"]

        try:
            from services.url_tracker_service import create_url_tracker_service

            url_tracker = create_url_tracker_service()

            # Find URLs in the text (both http/https and www. prefixed)
            urls = set()  # Use set to avoid duplicates

            # Find http/https URLs - capture full URL including parameters and fragments
            http_urls = re.findall(
                r"https?://[^\s]+",
                text,
            )
            urls.update(http_urls)

            # Find www. URLs (without http/https prefix)
            www_urls = re.findall(
                r"\bwww\.[^\s]+",
                text,
            )
            # Normalize www. URLs by adding https:// prefix
            for www_url in www_urls:
                urls.add(f"https://{www_url}")

            for url in urls:
                # Track the URL (no blacklist for tracking - we track all URLs)
                is_duplicate, first_timestamp = url_tracker.track_url(
                    url, sender, server_name, target
                )

                if is_duplicate and first_timestamp:
                    # Send "Wanha!" message
                    # Get the URL info to populate posters dynamically
                    url_info = url_tracker.get_url_info(url)
                    if url_info and url_info["posters"]:
                        first_nick = url_info["posters"][0]["nick"]
                        duplicate_message = url_tracker.format_duplicate_message(
                            url, first_timestamp, first_nick
                        )
                        self._send_response(server, target, duplicate_message)
                        logger.debug(f"Sent duplicate URL notification for: {url}")

        except Exception as e:
            logger.error(f"Error tracking URLs: {e}")

    def toggle_tamagotchi(self, server, target, sender):
        """Toggle tamagotchi responses on/off with .env file persistence."""
        self.tamagotchi_enabled = not self.tamagotchi_enabled

        # Save the new state to .env file
        import os

        new_value = "true" if self.tamagotchi_enabled else "false"
        success = self._update_env_file("TAMAGOTCHI_ENABLED", new_value)

        status = "enabled" if self.tamagotchi_enabled else "disabled"
        emoji = "🐣" if self.tamagotchi_enabled else "💤"

        if success:
            logger.info(f"Tamagotchi responses toggled to {status} by {sender}")
            response = f"{emoji} Tamagotchi responses are now {status}."
        else:
            logger.info(
                f"Tamagotchi responses toggled to {status} by {sender} (but .env update failed)"
            )
            response = f"{emoji} Tamagotchi responses are now {status} (session only - .env update failed)."

        self._send_response(server, target, response)
        logger.info(f"{sender} toggled tamagotchi to {status}", server.config.name)

        return response

    def _update_env_file(self, key: str, value: str) -> bool:
        """Update a key-value pair in the .env file. Creates the file if it doesn't exist."""
        env_file = ".env"
        try:
            if not os.path.exists(env_file):
                with open(env_file, "w", encoding="utf-8") as f:
                    f.write("")

            with open(env_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            key_found = False
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith(f"{key}=") or stripped.startswith(f"#{key}="):
                    lines[i] = f"{key}={value}\n"
                    key_found = True
                    break

            if not key_found:
                lines.append(f"{key}={value}\n")

            with open(env_file, "w", encoding="utf-8") as f:
                f.writelines(lines)

            os.environ[key] = value

            return True

        except IOError as e:
            logger.error(f"Could not update .env file: {e}")
            return False


def create_message_handler(service_manager, data_manager) -> MessageHandler:
    """
    Factory function to create a message handler instance.

    Args:
        service_manager: ServiceManager instance
        data_manager: DataManager instance

    Returns:
        MessageHandler instance
    """
    return MessageHandler(service_manager, data_manager)
