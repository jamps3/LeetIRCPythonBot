"""
Basic IRC Bot Commands

This module contains basic utility commands like help, time, echo, etc.
"""

import time
from datetime import datetime

from command_registry import (
    CommandContext,
    CommandResponse,
    CommandScope,
    CommandType,
    command,
)
from config import get_config


@command(
    "help",
    description="Show available commands",
    usage="!help [command]",
    examples=["!help", "!help weather"],
)
def help_command(context: CommandContext, bot_functions):
    """Show help for commands."""
    from command_registry import get_command_registry

    registry = get_command_registry()

    # If specific command requested
    if context.args:
        command_name = context.args[0]
        help_text = registry.generate_help(specific_command=command_name)
        return CommandResponse.success_msg(help_text)

    # General help - show all applicable commands
    if context.is_console:
        # For console, show console and both-scope commands
        help_text = registry.generate_help(scope=CommandScope.CONSOLE_ONLY)
        both_help = registry.generate_help(scope=CommandScope.BOTH)
        if both_help and "No commands available" not in both_help:
            help_text += "\n\n" + both_help
    else:
        # For IRC, show IRC and both-scope commands
        help_text = registry.generate_help(scope=CommandScope.IRC_ONLY)
        both_help = registry.generate_help(scope=CommandScope.BOTH)
        if both_help and "No commands available" not in both_help:
            help_text += "\n\n" + both_help
    return CommandResponse.success_msg(help_text)


@command("aika", aliases=["time"], description="Show current time", usage="!aika")
def time_command(context: CommandContext, bot_functions):
    """Show current time with nanosecond precision."""
    now_ns = time.time_ns()
    dt = datetime.fromtimestamp(now_ns // 1_000_000_000)
    nanoseconds = now_ns % 1_000_000_000
    formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S") + f".{nanoseconds:09d}"
    return f"Nykyinen aika: {formatted_time}"


@command(
    "kaiku",
    aliases=["echo"],
    description="Echo back the message",
    usage="!kaiku <message>",
    examples=["!kaiku Hello world!"],
    requires_args=True,
)
def echo_command(context: CommandContext, bot_functions):
    """Echo back the provided message."""
    if context.is_console:
        return f"Console: {context.args_text}"
    else:
        return f"{context.sender}: {context.args_text}"


@command("version", description="Show bot version", usage="!version")
def version_command(context: CommandContext, bot_functions):
    """Show the bot version."""
    config = get_config()
    return f"Bot version: {config.version}"


@command("ping", description="Check if bot is responsive", usage="!ping")
def ping_command(context: CommandContext, bot_functions):
    """Simple ping command to check bot responsiveness."""
    return "Pong! 🏓"


@command(
    "s",
    aliases=["sää", "weather"],
    description="Get weather information",
    usage="!s [location]",
    examples=["!s", "!s Helsinki", "!s Joensuu"],
)
def weather_command(context: CommandContext, bot_functions):
    """Get weather information for a location."""
    location = context.args_text.strip() if context.args_text else "Joensuu"

    # Call the weather function from bot_functions
    send_weather = bot_functions.get("send_weather")
    if send_weather:
        # For console, we need to handle the response differently
        if context.is_console:
            # Import logging to track console calls
            import logging

            logger = logging.getLogger(__name__)
            logger.info(f"Getting weather for {location} from console")

        # Call the weather service
        send_weather(None, context.target, location)
        return CommandResponse.no_response()  # Weather service handles the output
    else:
        return "Weather service not available"


@command("about", description="Show information about the bot", usage="!about")
def about_command(context: CommandContext, bot_functions):
    """Show information about the bot."""
    config = get_config()
    return (
        f"LeetIRC Bot v{config.version} - A Finnish IRC bot with word tracking, "
        f"weather, drink statistics, and more! Type !help for commands."
    )


@command(
    "exit",
    description="Exit the bot from console",
    usage="!exit",
    examples=["!exit"],
    scope=CommandScope.CONSOLE_ONLY,
)
def exit_command(context: CommandContext, bot_functions):
    """Exit the bot when used from console."""
    if context.is_console:
        # Try to get the stop event from bot functions and trigger it
        stop_event = bot_functions.get("stop_event")
        if stop_event:
            stop_event.set()
            return "🛑 Shutting down bot..."
        else:
            # Fallback - just return a quit message
            return "🛑 Exit command received - bot shutting down"
    else:
        return "This command only works from console"


# Import this module to register the commands
def register_basic_commands():
    """Register all basic commands. Called automatically when module is imported."""
    pass


# Auto-register when imported
register_basic_commands()
