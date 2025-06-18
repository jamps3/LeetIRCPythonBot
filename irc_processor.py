"""
IRC Message Processing System

This module provides event-driven message processing that integrates
with the command registry and handles various IRC events.
"""

import os
import asyncio
import re
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from irc_client import IRCClient, IRCMessage, IRCMessageType
from command_registry import (
    CommandContext, process_command_message, 
    CommandResponse, get_command_registry
)
from config import get_config


@dataclass
class MessageContext:
    """Enhanced context for message processing."""
    irc_message: IRCMessage
    irc_client: IRCClient
    bot_functions: Dict[str, Any]
    config: Any
    
    @property
    def is_bot_mention(self) -> bool:
        """Check if the message mentions the bot."""
        if not self.irc_message.text:
            return False
        
        bot_name = self.config.name.lower()
        text_lower = self.irc_message.text.lower()
        
        # Check for direct mention at start of message
        return text_lower.startswith(f"{bot_name}:") or text_lower.startswith(f"{bot_name},")
    
    @property
    def is_private_to_bot(self) -> bool:
        """Check if this is a private message to the bot."""
        return (self.irc_message.target and 
                self.irc_message.target.lower() == self.config.name.lower())


class IRCMessageProcessor:
    """
    Processes IRC messages and coordinates various bot functions.
    """
    
    def __init__(self, irc_client: IRCClient, bot_functions: Dict[str, Any]):
        """
        Initialize message processor.
        
        Args:
            irc_client: IRC client instance
            bot_functions: Dictionary of bot functions and data
        """
        self.irc_client = irc_client
        self.bot_functions = bot_functions
        self.config = get_config()
        
        # Load USE_NOTICES setting
        use_notices_setting = os.getenv('USE_NOTICES', 'false').lower()
        self.use_notices = use_notices_setting in ('true', '1', 'yes', 'on')
        
        # Register message handlers
        self.irc_client.add_message_handler(IRCMessageType.PRIVMSG, self._handle_privmsg)
        self.irc_client.add_message_handler(IRCMessageType.JOIN, self._handle_join)
        self.irc_client.add_message_handler(IRCMessageType.PART, self._handle_part)
        self.irc_client.add_message_handler(IRCMessageType.QUIT, self._handle_quit)
        self.irc_client.add_message_handler(IRCMessageType.NICK, self._handle_nick)
        
        # Add raw message handler for legacy compatibility
        self.irc_client.add_raw_handler(self._handle_raw_legacy)
        
        # Message processors (in order of execution)
        self._processors = [
            self._process_ignore_self,
            self._process_word_tracking,
            self._process_drink_tracking,
            self._process_url_titles,
            self._process_commands,
            self._process_ai_chat,
            self._process_leet_tracking,
        ]
    
    def _handle_privmsg(self, message: IRCMessage):
        """Handle PRIVMSG messages."""
        self._process_message(message)
    
    def _handle_join(self, message: IRCMessage):
        """Handle JOIN messages."""
        if message.sender:
            self._log(f"{message.sender} joined {message.target}", "INFO")
    
    def _handle_part(self, message: IRCMessage):
        """Handle PART messages."""
        if message.sender:
            reason = message.text or "No reason"
            self._log(f"{message.sender} left {message.target}: {reason}", "INFO")
    
    def _handle_quit(self, message: IRCMessage):
        """Handle QUIT messages."""
        if message.sender:
            reason = message.text or "No reason"
            self._log(f"{message.sender} quit: {reason}", "INFO")
    
    def _handle_nick(self, message: IRCMessage):
        """Handle NICK changes."""
        if message.sender and message.text:
            self._log(f"{message.sender} changed nick to {message.text}", "INFO")
    
    def _handle_raw_legacy(self, raw_line: str):
        """Handle raw messages for legacy system compatibility."""
        # This allows legacy message handlers to still work
        try:
            process_message = self.bot_functions.get('legacy_process_message')
            if process_message:
                # Convert back to legacy format for compatibility
                legacy_socket = self.irc_client.socket
                process_message(legacy_socket, raw_line, self.bot_functions)
        except Exception as e:
            self._log(f"Legacy message processing error: {e}", "WARNING")
    
    def _process_message(self, irc_message: IRCMessage):
        """Process a PRIVMSG through all processors."""
        context = MessageContext(
            irc_message=irc_message,
            irc_client=self.irc_client,
            bot_functions=self.bot_functions,
            config=self.config
        )
        
        # Run through all processors
        for processor in self._processors:
            try:
                if processor(context):
                    # If processor returns True, stop processing
                    break
            except Exception as e:
                self._log(f"Message processor error in {processor.__name__}: {e}", "ERROR")
    
    def _process_ignore_self(self, context: MessageContext) -> bool:
        """Ignore messages from the bot itself."""
        if context.irc_message.sender and context.irc_message.sender.lower() == self.config.name.lower():
            self._log("Ignoring bot's own message", "DEBUG")
            return True  # Stop processing
        return False
    
    def _process_word_tracking(self, context: MessageContext) -> bool:
        """Process word tracking (legacy system integration)."""
        if not context.irc_message.text or context.irc_message.text.startswith('!'):
            return False
        
        try:
            # Extract words and update tracking
            words = re.findall(r'\b\w+\b', context.irc_message.text.lower())
            if words:
                load_func = self.bot_functions.get('load')
                save_func = self.bot_functions.get('save')
                update_kraks = self.bot_functions.get('update_kraks')
                
                if load_func and save_func and update_kraks:
                    kraks = load_func()
                    update_kraks(kraks, context.irc_message.sender, words)
                    save_func(kraks)
        except Exception as e:
            self._log(f"Word tracking error: {e}", "WARNING")
        
        return False  # Continue processing
    
    def _process_drink_tracking(self, context: MessageContext) -> bool:
        """Process drink word tracking."""
        if not context.irc_message.text or context.irc_message.text.startswith('!'):
            return False
        
        try:
            # Look for drink patterns like "krak (beer)"
            drink_pattern = r'(\w+)\s*\(\s*([\w\s]+)\s*\)'
            match = re.search(drink_pattern, context.irc_message.text)
            
            if match:
                word = match.group(1).lower()
                beverage = match.group(2).lower()
                
                DRINK_WORDS = self.bot_functions.get('DRINK_WORDS', {})
                if word in DRINK_WORDS:
                    count_kraks = self.bot_functions.get('count_kraks')
                    if count_kraks:
                        count_kraks(word, beverage)
        except Exception as e:
            self._log(f"Drink tracking error: {e}", "WARNING")
        
        return False  # Continue processing
    
    def _process_url_titles(self, context: MessageContext) -> bool:
        """Process URL title fetching."""
        if not context.irc_message.text or context.irc_message.is_private_message:
            return False
        
        try:
            fetch_title = self.bot_functions.get('fetch_title')
            if fetch_title:
                fetch_title(
                    context.irc_client.socket,
                    context.irc_message.target,
                    context.irc_message.text
                )
        except Exception as e:
            self._log(f"URL title processing error: {e}", "WARNING")
        
        return False  # Continue processing
    
    async def _process_commands_async(self, context: MessageContext) -> bool:
        """Process bot commands asynchronously."""
        if not context.irc_message.text or not context.irc_message.text.startswith('!'):
            return False
        
        try:
            # Create command context
            cmd_context = CommandContext(
                command="",  # Will be filled by process_command_message
                args=[],     # Will be filled by process_command_message
                raw_message=context.irc_message.text,
                sender=context.irc_message.sender,
                target=context.irc_message.target,
                is_private=context.irc_message.is_private_message,
                is_console=False,
                server_name=context.irc_client.server_config.name
            )
            
            # Add IRC client to bot functions for admin commands
            enhanced_bot_functions = context.bot_functions.copy()
            enhanced_bot_functions['irc'] = context.irc_client.socket
            enhanced_bot_functions['irc_client'] = context.irc_client
            
            # Process command
            response = await process_command_message(
                context.irc_message.text, 
                cmd_context, 
                enhanced_bot_functions
            )
            
            if response and response.should_respond and response.message:
                # Send response
                target = context.irc_message.target
                if context.irc_message.is_private_message:
                    target = context.irc_message.sender
                
                if response.split_long_messages:
                    # Split long messages
                    split_func = context.bot_functions.get('split_message_intelligently')
                    if split_func:
                        parts = split_func(response.message, 400)
                        for part in parts:
                            self._send_response(target, part)
                    else:
                        self._send_response(target, response.message)
                else:
                    self._send_response(target, response.message)
                
                return True  # Command processed, stop further processing
        
        except Exception as e:
            self._log(f"Command processing error: {e}", "ERROR")
        
        return False
    
    def _process_commands(self, context: MessageContext) -> bool:
        """Process bot commands (sync wrapper)."""
        if not context.irc_message.text or not context.irc_message.text.startswith('!'):
            return False
        
        # Run async command processing
        try:
            loop = None
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            return loop.run_until_complete(self._process_commands_async(context))
        except Exception as e:
            self._log(f"Command processing sync error: {e}", "ERROR")
            return False
    
    def _process_ai_chat(self, context: MessageContext) -> bool:
        """Process AI chat requests."""
        if not context.irc_message.text:
            return False
        
        # Only respond to private messages or mentions
        if not (context.is_private_to_bot or context.is_bot_mention):
            return False
        
        try:
            chat_with_gpt = self.bot_functions.get('chat_with_gpt')
            if not chat_with_gpt:
                return False
            
            # Get AI response
            response = chat_with_gpt(context.irc_message.text)
            if response:
                # Determine target
                target = context.irc_message.sender if context.is_private_to_bot else context.irc_message.target
                
                # Split response if needed
                wrap_func = self.bot_functions.get('wrap_irc_message_utf8_bytes')
                if wrap_func:
                    parts = wrap_func(response, reply_target=target, max_lines=5, placeholder="...")
                    for part in parts:
                        self._send_response(target, part)
                else:
                    self._send_response(target, response)
                
                return True  # Handled AI chat
        
        except Exception as e:
            self._log(f"AI chat processing error: {e}", "WARNING")
        
        return False
    
    def _process_leet_tracking(self, context: MessageContext) -> bool:
        """Process leet winner tracking."""
        if not context.irc_message.text:
            return False
        
        try:
            # Check for leet winner patterns
            leet_pattern = r'Ensimmäinen leettaaja oli (\S+) .*?, viimeinen oli (\S+) .*?Lähimpänä multileettiä oli (\S+)'
            match = re.search(leet_pattern, context.irc_message.raw)
            
            if match:
                first, last, multileet = match.groups()
                
                load_leet_winners = self.bot_functions.get('load_leet_winners')
                save_leet_winners = self.bot_functions.get('save_leet_winners')
                
                if load_leet_winners and save_leet_winners:
                    leet_winners = load_leet_winners()
                    
                    for category, winner in zip(['ensimmäinen', 'viimeinen', 'multileet'], [first, last, multileet]):
                        if winner in leet_winners:
                            leet_winners[winner][category] = leet_winners[winner].get(category, 0) + 1
                        else:
                            leet_winners[winner] = {category: 1}
                    
                    save_leet_winners(leet_winners)
                    self._log(f"Updated leet winners: {leet_winners}", "INFO")
            
            # Check for ekavika patterns
            ekavika_pattern = r'𝙫𝙞𝙠𝙖 oli (\w+) kello .*?, ja 𝖊𝖐𝖆 oli (\w+)'
            ekavika_match = re.search(ekavika_pattern, context.irc_message.raw)
            
            if ekavika_match:
                vika, eka = ekavika_match.groups()
                
                # Load and update ekavika data
                import json
                EKAVIKA_FILE = self.bot_functions.get('EKAVIKA_FILE', 'ekavika.json')
                
                try:
                    with open(EKAVIKA_FILE, 'r', encoding='utf-8') as f:
                        ekavika_data = json.load(f)
                except (FileNotFoundError, json.JSONDecodeError):
                    ekavika_data = {'eka': {}, 'vika': {}}
                
                ekavika_data['eka'][eka] = ekavika_data['eka'].get(eka, 0) + 1
                ekavika_data['vika'][vika] = ekavika_data['vika'].get(vika, 0) + 1
                
                with open(EKAVIKA_FILE, 'w', encoding='utf-8') as f:
                    json.dump(ekavika_data, f, indent=4, ensure_ascii=False)
                
                self._log(f"Updated ekavika: eka={eka}, vika={vika}", "INFO")
        
        except Exception as e:
            self._log(f"Leet tracking error: {e}", "WARNING")
        
        return False  # Don't stop processing
    
    def _send_response(self, target: str, message: str):
        """Send a response using NOTICE or PRIVMSG based on USE_NOTICES setting."""
        if self.use_notices:
            self.irc_client.send_notice(target, message)
        else:
            self.irc_client.send_message(target, message)
    
    def _log(self, message: str, level: str = "INFO"):
        """Log a message."""
        log_func = self.bot_functions.get('log')
        if log_func:
            log_func(message, level)
        else:
            print(f"[{level}] {message}")


def create_message_processor(irc_client: IRCClient, bot_functions: Dict[str, Any]) -> IRCMessageProcessor:
    """
    Factory function to create message processor.
    
    Args:
        irc_client: IRC client instance
        bot_functions: Bot functions dictionary
        
    Returns:
        Configured IRCMessageProcessor
    """
    return IRCMessageProcessor(irc_client, bot_functions)

