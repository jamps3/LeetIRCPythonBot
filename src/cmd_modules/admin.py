"""
Admin Commands Module

Contains admin commands: connect, disconnect, exit, countdown
"""

import re
import threading

import logger
from command_registry import (
    CommandContext,
    CommandScope,
    command,
)

# Import reload commands from commands_admin.py for backwards compatibility
# Import scheduled command from commands_admin.py for backwards compatibility
from commands_admin import reload_command, reload_status_command, scheduled_command

# = functions (====================
# Helper (duplicated from commands.py for modularity)
# =====================


def _parse_time_and_message(input_str: str) -> tuple:
    """
    Parse time and message from input string.

    Examples:
    - "1h20min message here" -> ("1h20min", "message here")
    - "30min" -> ("30min", "")
    - "45 message" -> ("45", "message")
    - "message only" -> ("", "message only")  # if no time found
    """
    stripped = input_str.strip()

    # Find all time components with their positions
    time_matches = list(re.finditer(r"(\d+)(h|min|s)", stripped))

    if not time_matches:
        # Check if it starts with just a number (defaults to minutes)
        if stripped and stripped[0].isdigit():
            # Find where digits end (but not if followed by h/min/s)
            match = re.match(r"^(\d+)(?![hmin])", stripped)
            if match:
                time_part = match.group(1)
                message_part = stripped[len(time_part) :].strip()  # noqa: E203
                return time_part, message_part

        # No time found, whole string is message
        return "", stripped

    # Find the end position of all consecutive time components from the start
    time_end_pos = 0
    time_parts = []

    for match in time_matches:
        if match.start() == time_end_pos:
            # This is consecutive with previous time components
            time_parts.append(match.group(0))
            time_end_pos = match.end()
        else:
            # Gap found, stop here
            break

    if time_parts:
        time_str = "".join(time_parts)
        message_str = stripped[time_end_pos:].strip()
        return time_str, message_str

    # Fallback: no valid time components found
    return "", stripped


# =====================
# Connect Command
# =====================


@command(
    "connect",
    description="Connect to IRC servers",
    usage="!connect [server_name host [port] [channels] [tls]]",
    examples=["!connect", "!connect myserver irc.example.com 6667 #general,#random"],
    scope=CommandScope.CONSOLE_ONLY,
)
def connect_command(context: CommandContext, bot_functions):
    """Connect to IRC servers."""
    # Get bot manager from bot_functions
    if not hasattr(bot_functions, "__self__") or not hasattr(
        bot_functions["__self__"], "_console_connect"
    ):
        # Try to get bot manager reference
        bot_manager = bot_functions.get("bot_manager")
        if not bot_manager:
            return "Bot manager not available"
    else:
        bot_manager = bot_functions["__self__"]

    # Use the existing console connect logic
    try:
        result = bot_manager._console_connect(*context.args)
        return result
    except Exception as e:
        return f"Connection error: {e}"


# =====================
# Disconnect Command
# =====================


@command(
    "disconnect",
    description="Disconnect from IRC servers",
    usage="!disconnect [server_names...]",
    examples=["!disconnect", "!disconnect server1 server2"],
    scope=CommandScope.CONSOLE_ONLY,
)
def disconnect_command(context: CommandContext, bot_functions):
    """Disconnect from IRC servers."""
    # Get bot manager from bot_functions
    bot_manager = bot_functions.get("bot_manager")
    if not bot_manager:
        return "Bot manager not available"

    try:
        result = bot_manager._console_disconnect(*context.args)
        return result
    except Exception as e:
        return f"Disconnection error: {e}"


# =====================
# Countdown Command
# =====================


@command(
    "k",
    description="Start a countdown timer with optional message",
    usage="!k [-]<time> [message] (e.g., !k-1h20min30s Done!, !k-30min Meeting time)",
    examples=["!k-1h20min30s Done!", "!k-30min Meeting time", "!k-2h", "!k-45"],
    requires_args=False,  # Allow no args since time can be in command name
)
def countdown_command(context: CommandContext, bot_functions):
    """Start a countdown timer that sends one message when finished."""
    # Handle the case where time is attached to command name (e.g., !k-1s)
    time_str = ""
    message = ""
    if context.command.startswith("k-"):
        # Time is part of command name (e.g., "k-1s Valmis!" -> combine with args)
        time_input = context.command[2:]  # Remove "k-" prefix
        if context.args_text.strip():
            time_input += " " + context.args_text.strip()
        time_str, message = _parse_time_and_message(time_input)
    elif context.args:
        # Split args into time and message parts
        all_args = context.args_text.strip()
        if all_args:
            time_str, message = _parse_time_and_message(all_args)

    if not time_str:
        return "Usage: !k [-]<time> [message] (e.g., !k-1h20min30s Done!, !k-30min Meeting time)"

    # Remove optional leading dash from time
    if time_str.startswith("-"):
        time_str = time_str[1:]

    if not time_str:
        return "Usage: !k [-]<time> [message] (e.g., !k-1h20min30s Done!, !k-30min Meeting time)"

    # Parse time format (e.g., "1h20min30s" -> 1 hour + 20 minutes + 30 seconds)
    # Parse time components using a more flexible approach
    # Support formats like: 1h20min30s, 30min, 2h, 45, 90s
    hours = 0
    minutes = 0
    seconds = 0

    # Extract time components with their units
    time_components = re.findall(r"(\d+)(h|min|s)", time_str)

    if not time_components:
        # No units specified - check if it's just a number (defaults to minutes)
        if time_str.isdigit():
            minutes = int(time_str)
        else:
            return f"Invalid time format: {time_str}. Use formats like: 1h20min30s, 30min, 2h, 45, 90s"
    else:
        # Parse each time component
        for value_str, unit in time_components:
            value = int(value_str)
            if unit == "h":
                hours = value
            elif unit == "min":
                minutes = value
            elif unit == "s":
                seconds = value

        # If there are leftover digits without units, treat as minutes (for backwards compatibility)
        # This handles cases like "1h30" where "30" has no unit
        remaining_digits = re.sub(r"\d+(?:h|min|s)", "", time_str).strip()
        if remaining_digits and remaining_digits.isdigit():
            minutes = int(remaining_digits)

    # Validate ranges
    if (
        hours < 0
        or minutes < 0
        or seconds < 0
        or (hours == 0 and minutes == 0 and seconds == 0)
    ):
        return "Time must be positive"

    if hours > 24 or minutes > 1440 or seconds > 86400:  # Max 24 hours
        return "Maximum countdown time is 24 hours"

    # Convert to total seconds
    total_seconds = (hours * 3600) + (minutes * 60) + seconds

    if total_seconds > 86400:  # 24 hours in seconds
        return "Maximum countdown time is 24 hours"

    # Format the duration for confirmation
    duration_parts = []
    if hours > 0:
        duration_parts.append(f"{hours}h")
    if minutes > 0:
        duration_parts.append(f"{minutes}min")
    if seconds > 0:
        duration_parts.append(f"{seconds}s")
    duration_str = "".join(duration_parts) if duration_parts else f"{total_seconds}s"

    # Start countdown in background
    def countdown_finished():
        """Send completion message when countdown finishes."""
        try:
            # Include custom message if provided
            base_msg = f"⏰ Countdown finished: {duration_str} for {context.sender}"
            completion_msg = f"{base_msg} - {message}" if message else base_msg

            if context.is_console:
                # For console, just log it
                logger.info(completion_msg)
            else:
                # For IRC, send to the channel/user
                notice = bot_functions.get("notice_message")
                irc = bot_functions.get("irc")
                target = context.target or context.sender
                if notice and irc and target:
                    notice(completion_msg, irc, target)
        except Exception as e:
            logger.error(f"Error sending countdown completion: {e}")

    # Start timer in background
    timer = threading.Timer(total_seconds, countdown_finished)
    timer.daemon = True  # Don't prevent program exit
    timer.start()

    # Confirm countdown started
    return f"⏰ Countdown started: {duration_str} ({total_seconds}s)"


# =====================
# Exit Command
# =====================


@command(
    "exit",
    description="Shutdown the bot",
    usage="!exit [quit_message]",
    examples=["!exit", "!exit Custom quit message"],
    scope=CommandScope.CONSOLE_ONLY,
)
def exit_command(context: CommandContext, bot_functions):
    """Shutdown the bot (console/TUI only)."""
    if not context.is_console:
        return  # Exit command only works from console/TUI

    # Get quit message from args if provided
    quit_message = " ".join(context.args) if context.args else ""

    # If quit message provided, set it on servers first
    if quit_message:
        set_quit_message = bot_functions.get("set_quit_message")
        if set_quit_message:
            set_quit_message(quit_message)

    # Try to get bot_manager from bot functions and call its stop method
    # This ensures QUIT is sent to IRC servers before shutdown
    bot_manager = bot_functions.get("bot_manager")
    if bot_manager and hasattr(bot_manager, "stop"):
        logger.info(f"{context.server_name} !{context.command} command received")
        logger.log(
            f"🛑 Shutting down bot with quit message: '{quit_message or 'default'}'",
            "INFO",
            fallback_text=f"[STOP] Shutting down bot with quit message: '{quit_message or 'default'}'",
        )
        # Call bot_manager.stop which properly sends QUIT to servers
        bot_manager.stop(quit_message if quit_message else None)
        return "🛑 Bot shutdown initiated..."

    # Fallback: try to use stop_event directly if bot_manager not available
    stop_event = bot_functions.get("stop_event")
    if stop_event:
        logger.info(f"{context.server_name} !{context.command} command received")
        logger.log(
            f"🛑 Shutting down bot with quit message: '{quit_message or 'default'}'",
            "INFO",
            fallback_text=f"[STOP] Shutting down bot with quit message: '{quit_message or 'default'}'",
        )
        stop_event.set()
        return "🛑 Bot shutdown initiated..."
    else:
        # Fallback - just return a quit message
        return "🛑 Exit command received - bot shutting down"


# Aliases for backwards compatibility
k_command = countdown_command


@command(
    "quit",
    description="Quit IRC and shutdown the bot (alias for !exit)",
    usage="!quit [message]",
    examples=["!quit", "!quit Bye bye!"],
    scope=CommandScope.CONSOLE_ONLY,
)
def quit_command(context: CommandContext, bot_functions):
    """Quit IRC and shutdown the bot (alias for !exit)."""
    # Reuse exit_command logic
    return exit_command(context, bot_functions)
