"""
Admin IRC Bot Commands

This module contains administrative commands that require password authentication.
"""

import os

from command_registry import (
    CommandContext,
    CommandResponse,
    CommandScope,
    CommandType,
    command,
)
from config import get_config


def verify_admin_password(args):
    """Check if the first argument is the correct admin password."""
    if not args:
        return False

    config = get_config()
    return args[0] == config.admin_password


@command(
    "join",
    description="Join a channel (admin only)",
    usage="!join <password> #channel [key]",
    examples=["!join mypass #newchannel", "!join mypass #private secretkey"],
    admin_only=True,
    requires_args=True,
)
def join_command(context: CommandContext, bot_functions):
    """Join an IRC channel."""
    if not verify_admin_password(context.args):
        return "❌ Invalid admin password"

    if len(context.args) < 2:
        return "❌ Usage: !join <password> #channel [key]"

    channel = context.args[1]
    key = context.args[2] if len(context.args) > 2 else ""

    if context.is_console:
        return f"Admin command: JOIN {channel} {key if key else '(no key)'}"
    else:
        # Send IRC command
        irc = bot_functions.get("irc")
        if irc:
            if key:
                irc.send_raw(f"JOIN {channel} {key}")
            else:
                irc.send_raw(f"JOIN {channel}")

            log_func = bot_functions.get("log")
            if log_func:
                log_func(f"Admin joined channel {channel}", "INFO")

            return f"Joined {channel}"
        else:
            return "❌ IRC connection not available"


@command(
    "part",
    description="Leave a channel (admin only)",
    usage="!part <password> #channel",
    examples=["!part mypass #channel"],
    admin_only=True,
    requires_args=True,
)
def part_command(context: CommandContext, bot_functions):
    """Leave an IRC channel."""
    if not verify_admin_password(context.args):
        return "❌ Invalid admin password"

    if len(context.args) < 2:
        return "❌ Usage: !part <password> #channel"

    channel = context.args[1]

    if context.is_console:
        return f"Admin command: PART {channel}"
    else:
        # Send IRC command
        irc = bot_functions.get("irc")
        if irc:
            irc.send_raw(f"PART {channel}")

            log_func = bot_functions.get("log")
            if log_func:
                log_func(f"Admin left channel {channel}", "INFO")

            return f"Left {channel}"
        else:
            return "❌ IRC connection not available"


@command(
    "nick",
    description="Change bot nickname (admin only)",
    usage="!nick <password> <new_nickname>",
    examples=["!nick mypass newbot"],
    admin_only=True,
    requires_args=True,
)
def nick_command(context: CommandContext, bot_functions):
    """Change the bot's nickname."""
    if not verify_admin_password(context.args):
        return "❌ Invalid admin password"

    if len(context.args) < 2:
        return "❌ Usage: !nick <password> <new_nickname>"

    new_nick = context.args[1]

    if context.is_console:
        return f"Admin command: NICK {new_nick}"
    else:
        # Send IRC command
        irc = bot_functions.get("irc")
        if irc:
            irc.send_raw(f"NICK {new_nick}")

            log_func = bot_functions.get("log")
            if log_func:
                log_func(f"Admin changed nick to {new_nick}", "INFO")

            return f"Changed nick to {new_nick}"
        else:
            return "❌ IRC connection not available"


@command(
    "quit",
    description="Quit IRC with message (admin only)",
    usage="!quit <password> [message]",
    examples=["!quit mypass", "!quit mypass Goodbye everyone!"],
    admin_only=True,
    requires_args=True,
)
def quit_command(context: CommandContext, bot_functions):
    """Quit IRC with an optional message."""
    if not verify_admin_password(context.args):
        return "❌ Invalid admin password"

    quit_message = " ".join(context.args[1:]) if len(context.args) > 1 else "Admin quit"

    # Set the custom quit message first for all servers
    set_quit_message_func = bot_functions.get("set_quit_message")
    if set_quit_message_func:
        set_quit_message_func(quit_message)

    if context.is_console:
        # For console, trigger bot shutdown
        stop_event = bot_functions.get("stop_event")
        if stop_event:
            stop_event.set()
            return f"🛑 Shutting down bot: {quit_message}"
        else:
            return "❌ Cannot access shutdown mechanism"
    else:
        # Send IRC command
        irc = bot_functions.get("irc")
        if irc:
            irc.send_raw(f"QUIT :{quit_message}")

            log_func = bot_functions.get("log")
            if log_func:
                log_func(f"Admin quit with message: {quit_message}", "INFO")

            # Also trigger shutdown for IRC quit
            stop_event = bot_functions.get("stop_event")
            if stop_event:
                stop_event.set()

            return ""  # Don't send a response since we're quitting
        else:
            return "❌ IRC connection not available"


@command(
    "raw",
    description="Send raw IRC command (admin only)",
    usage="!raw <password> <IRC_COMMAND>",
    examples=["!raw mypass MODE #channel +o user"],
    admin_only=True,
    requires_args=True,
    scope=CommandScope.IRC_ONLY,
)
def raw_command(context: CommandContext, bot_functions):
    """Send a raw IRC command."""
    if not verify_admin_password(context.args):
        return "❌ Invalid admin password"

    if len(context.args) < 2:
        return "❌ Usage: !raw <password> <IRC_COMMAND>"

    raw_command = " ".join(context.args[1:])

    # Send IRC command
    irc = bot_functions.get("irc")
    if irc:
        irc.send_raw(raw_command)

        log_func = bot_functions.get("log")
        if log_func:
            log_func(f"Admin sent raw command: {raw_command}", "INFO")

        return f"Sent: {raw_command}"
    else:
        return "❌ IRC connection not available"


# Import this module to register the commands
def register_admin_commands():
    """Register all admin commands. Called automatically when module is imported."""
    pass


# Auto-register when imported
register_admin_commands()
