"""
Command Loader and Integration Module

This module loads all command modules and provides integration between
the command registry system and the bot infrastructure.
"""

import asyncio
from typing import Any, Dict, Optional

from command_registry import (
    CommandContext,
    CommandResponse,
    CommandScope,
    CommandType,
    get_command_registry,
    process_command_message,
)
from config import get_config


def load_all_commands():
    """Load all command modules to register their commands."""
    try:
        # Import all command modules to trigger registration
        import commands_admin
        import commands_basic
        import commands_extended  # Add new extended commands

        # Additional command modules can be imported here
        # import commands_weather
        # import commands_crypto
        # etc.

        registry = get_command_registry()
        command_count = len(registry._commands)
        print(f"Loaded {command_count} commands from command modules")

    except ImportError as e:
        print(f"Warning: Could not load all command modules: {e}")


async def process_irc_command(
    message: str,
    sender: str,
    target: str,
    irc_connection,
    bot_functions: Dict[str, Any],
) -> bool:
    """
    Process an IRC command message through the command registry system.

    Args:
        message: The IRC message text
        sender: Nickname of the message sender
        target: Channel or target of the message
        irc_connection: IRC socket connection
        bot_functions: Dictionary of bot functions and data

    Returns:
        bool: True if a command was processed, False otherwise
    """
    # Create command context
    config = get_config()
    is_private = target.lower() == config.name.lower()

    context = CommandContext(
        command="",  # Will be filled by process_command_message
        args=[],  # Will be filled by process_command_message
        raw_message=message,
        sender=sender,
        target=target,
        is_private=is_private,
        is_console=False,
        server_name=bot_functions.get("server_name", "unknown"),
    )

    # Add IRC connection to bot_functions for admin commands
    bot_functions_with_irc = bot_functions.copy()
    bot_functions_with_irc["irc"] = irc_connection

    # Process the command
    try:
        response = await process_command_message(
            message, context, bot_functions_with_irc
        )

        if response is not None:
            # Send response if needed
            if response.should_respond and response.message:
                notice_message = bot_functions.get("notice_message")
                if notice_message:
                    if response.split_long_messages:
                        # Split long messages intelligently
                        split_func = bot_functions.get("split_message_intelligently")
                        if split_func:
                            parts = split_func(
                                response.message, 400
                            )  # IRC message limit
                            for part in parts:
                                notice_message(part, irc_connection, target)
                        else:
                            notice_message(response.message, irc_connection, target)
                    else:
                        notice_message(response.message, irc_connection, target)

            return True  # Command was processed

    except Exception as e:
        # Log error but don't crash
        log_func = bot_functions.get("log")
        if log_func:
            log_func(f"Error processing command '{message}': {e}", "ERROR")

        # Send error message to user
        notice_message = bot_functions.get("notice_message")
        if notice_message:
            notice_message(f"Command error: {str(e)}", irc_connection, target)

        return True  # Still consider it processed to avoid fallback

    return False  # No command was processed


async def process_console_command_new(
    command_text: str, bot_functions: Dict[str, Any]
) -> bool:
    """
    Process a console command through the command registry system.

    Args:
        command_text: The command text from console
        bot_functions: Dictionary of bot functions and data

    Returns:
        bool: True if a command was processed, False otherwise
    """
    # Create console command context
    context = CommandContext(
        command="",  # Will be filled by process_command_message
        args=[],  # Will be filled by process_command_message
        raw_message=command_text,
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )

    # Process the command
    try:
        response = await process_command_message(command_text, context, bot_functions)

        if response is not None:
            # Send response to console if needed
            if response.should_respond and response.message:
                notice_message = bot_functions.get("notice_message")
                if notice_message:
                    if response.split_long_messages:
                        # Split long messages for console output
                        lines = response.message.split("\n")
                        for line in lines:
                            if line.strip():
                                notice_message(line)
                    else:
                        notice_message(response.message)

            return True  # Command was processed

    except Exception as e:
        # Log error but don't crash
        log_func = bot_functions.get("log")
        if log_func:
            log_func(f"Error processing console command '{command_text}': {e}", "ERROR")
        else:
            print(f"Error processing console command '{command_text}': {e}")

        return True  # Still consider it processed

    return False  # No command was processed


def enhanced_process_console_command(command_text: str, bot_functions: Dict[str, Any]):
    """
    Process console commands using the command registry system.
    """
    log_func = bot_functions.get("log")

    # Process command through command registry
    try:
        # Handle async processing more robustly
        processed = False
        
        # Try to detect if we're in an event loop already
        loop = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop
            loop = None
        
        if loop is None:
            # No event loop running, safe to use asyncio.run
            try:
                processed = asyncio.run(
                    process_console_command_new(command_text, bot_functions)
                )
            except Exception as e:
                if log_func:
                    log_func(f"Error in asyncio.run: {e}", "ERROR")
                processed = False
        else:
            # Event loop is already running, use thread pool to avoid conflicts
            import concurrent.futures
            import threading
            
            # Create a new thread with its own event loop
            def run_in_new_loop():
                try:
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(
                            process_console_command_new(command_text, bot_functions)
                        )
                    finally:
                        new_loop.close()
                        asyncio.set_event_loop(None)
                except Exception as e:
                    if log_func:
                        log_func(f"Error in new loop: {e}", "ERROR")
                    return False
            
            # Run in thread pool with timeout
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                try:
                    future = executor.submit(run_in_new_loop)
                    processed = future.result(timeout=10.0)
                except concurrent.futures.TimeoutError:
                    if log_func:
                        log_func(f"Command processing timed out: {command_text}", "ERROR")
                    processed = False
                except Exception as e:
                    if log_func:
                        log_func(f"Error in thread pool: {e}", "ERROR")
                    processed = False

        if processed:
            if log_func:
                log_func(f"Command '{command_text}' processed successfully", "DEBUG")
            return  # Command was handled
        else:
            # Command not recognized
            notice_message = bot_functions.get("notice_message")
            if notice_message:
                notice_message(
                    f"Command not recognized: {command_text}. Type !help for available commands."
                )

    except Exception as e:
        if log_func:
            log_func(f"Error processing console command '{command_text}': {e}", "ERROR")
        else:
            print(f"ERROR: Console command processing failed for '{command_text}': {e}")

        # Show error to user
        notice_message = bot_functions.get("notice_message")
        if notice_message:
            notice_message(f"Command error: {str(e)}")


def enhanced_process_irc_message(irc, message, bot_functions):
    """
    Process IRC messages and route commands to the command registry system.
    
    Handles both command messages (starting with !) and routes them to the 
    appropriate command handlers through the command registry.
    """
    import re

    # Extract message components
    match = re.search(r":(\S+)!(\S+) PRIVMSG (\S+) :(.+)", message)
    if not match:
        # Not a PRIVMSG, ignore
        return

    sender, _, target, text = match.groups()

    # Only process commands (starting with !)
    if not text.startswith("!"):
        # Non-command messages are handled by bot_manager's word tracking system
        return

    # Process command through command registry
    try:
        # Run async command processing in a compatible way
        try:
            # Get or create an event loop
            loop = asyncio.get_running_loop()
        except RuntimeError:  # No running loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        processed = loop.run_until_complete(
            process_irc_command(text, sender, target, irc, bot_functions)
        )

        if processed:
            return  # Command was handled

    except Exception as e:
        log_func = bot_functions.get("log")
        if log_func:
            log_func(
                f"Command processing failed for IRC command '{text}': {e}", "WARNING"
            )


def get_command_help_text() -> str:
    """
    Generate help text for all registered commands.

    Returns:
        str: Formatted help text
    """
    registry = get_command_registry()

    # Get commands by category
    public_commands = registry.get_commands_info(
        command_type=CommandType.PUBLIC, include_hidden=False
    )

    admin_commands = registry.get_commands_info(
        command_type=CommandType.ADMIN, include_hidden=False
    )

    help_lines = ["📋 Available commands:"]

    # Public commands
    for cmd in public_commands:
        line = f"• !{cmd.name}"
        if cmd.aliases:
            line += f" (aliases: {', '.join(cmd.aliases)})"
        if cmd.description:
            line += f" - {cmd.description}"
        help_lines.append(line)

    # Admin commands
    if admin_commands:
        help_lines.append("")
        help_lines.append("🔒 Admin commands:")
        for cmd in admin_commands:
            line = f"• !{cmd.name}*"
            if cmd.aliases:
                line += f" (aliases: {', '.join(cmd.aliases)})"
            if cmd.description:
                line += f" - {cmd.description}"
            help_lines.append(line)

        help_lines.append("")
        help_lines.append("* = Requires admin password")

    return "\n".join(help_lines)


# Initialize commands when module is imported
load_all_commands()
