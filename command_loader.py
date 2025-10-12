"""
Command Loader and Integration Module for LeetIRCPythonBot

This module loads all command modules and provides integration between
the command registry system and the bot infrastructure.
"""

import asyncio
from typing import Any, Dict

import logger

# Defer local imports to function bodies to avoid import-time side effects during
# the full test run, where some tests monkeypatch modules in ways that can break
# imports if they happen too early.


def load_all_commands():
    """Load all command modules to register their commands."""
    try:
        # Import all command modules to trigger registration
        import commands  # unified commands module
        import commands_admin

        # Resolve registry at call time to avoid early imports
        from command_registry import get_command_registry

        registry = get_command_registry()
        command_count = len(registry._commands)
        logger.info(f"Loaded {command_count} commands from command modules")

    except Exception as e:
        logger.warning(f"Warning: Could not load all command modules: {e}")


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
    from command_registry import CommandContext, process_command_message
    from config import get_config

    config = get_config()
    is_private = target.lower() == config.name.lower()
    # For private messages, we should reply to the sender nick instead of the target (bot's nick)
    reply_target = sender if is_private else target

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
                    # Always split by newlines for IRC safety (IRC messages cannot contain newlines)
                    lines = str(response.message).split("\n")
                    split_func = bot_functions.get("split_message_intelligently")
                    for line in lines:
                        line = line.rstrip()
                        if not line:
                            continue
                        if response.split_long_messages and split_func:
                            # Split per line to respect IRC length limits
                            parts = split_func(line, 400)
                            for part in parts:
                                if part:
                                    notice_message(part, irc_connection, reply_target)
                        else:
                            # Fallback: send each line as a separate notice
                            notice_message(line, irc_connection, reply_target)

            return True  # Command was processed

    except Exception as e:
        # Log error but don't crash
        log_func = bot_functions.get("log")
        if log_func:
            log_func(f"Error processing command '{message}': {e}", "ERROR")

        # Send error message to user
        notice_message = bot_functions.get("notice_message")
        if notice_message:
            notice_message(f"Command error: {str(e)}", irc_connection, reply_target)

        return True  # Still consider it processed to avoid fallback

    return False  # No command was processed


async def process_console_command_async(
    command_text: str, bot_functions: Dict[str, Any]
) -> bool:
    """
    Process a console command through the command registry system asynchronously.

    Args:
        command_text: The command text from console
        bot_functions: Dictionary of bot functions and data

    Returns:
        bool: True if a command was processed, False otherwise
    """
    # Create console command context
    from command_registry import CommandContext, process_command_message

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
        logger.error(f"Error processing console command '{command_text}': {e}")
        return True  # Still consider it processed
    return False  # No command was processed


def process_console_command(command_text: str, bot_functions: Dict[str, Any]):
    """
    Process a console command through the command registry system. Uses process_console_command_async.

    Args:
        command_text: The command text from console
        bot_functions: Dictionary of bot functions and data

    Returns:
        bool: True if a command was processed, False otherwise
    """
    log_func = bot_functions.get("log")

    # Ensure commands are loaded before processing
    ensure_commands_loaded()

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
                    process_console_command_async(command_text, bot_functions)
                )
            except Exception as e:
                if log_func:
                    log_func(f"Error in asyncio.run: {e}", "ERROR")
                processed = False
        else:
            # Event loop is already running, use thread pool to avoid conflicts
            import concurrent.futures

            # Create a new thread with its own event loop
            def run_in_new_loop():
                try:
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(
                            process_console_command_async(command_text, bot_functions)
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
                        log_func(
                            f"Command processing timed out: {command_text}", "ERROR"
                        )
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
            logger.error(
                f"ERROR: Console command processing failed for '{command_text}': {e}"
            )

        # Show error to user
        notice_message = bot_functions.get("notice_message")
        if notice_message:
            notice_message(f"Command error: {str(e)}")


def process_irc_message(irc, message, bot_functions):
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

    # Ensure commands are loaded before processing
    ensure_commands_loaded()

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
    from command_registry import CommandType, get_command_registry

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


# Lazy-load commands to avoid import-time side effects during testing
_commands_loaded = False


def ensure_commands_loaded():
    global _commands_loaded
    if _commands_loaded:
        return
    try:
        load_all_commands()
    finally:
        _commands_loaded = True
