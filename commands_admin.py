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
        return CommandResponse.error_msg("Invalid admin password")

    if len(context.args) < 2:
        return CommandResponse.error_msg("Usage: !join <password> #channel [key]")

    channel = context.args[1]
    key = context.args[2] if len(context.args) > 2 else ""

    if context.is_console:
        return f"Admin command: JOIN {channel} {key if key else '(no key)'}"
    else:
        # Send IRC command
        irc = bot_functions.get("irc")
        if irc:
            if key:
                irc.sendall(f"JOIN {channel} {key}\r\n".encode("utf-8"))
            else:
                irc.sendall(f"JOIN {channel}\r\n".encode("utf-8"))

            log_func = bot_functions.get("log")
            if log_func:
                log_func(f"Admin joined channel {channel}", "INFO")

            return f"Joined {channel}"
        else:
            return CommandResponse.error_msg("IRC connection not available")


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
        return CommandResponse.error_msg("Invalid admin password")

    if len(context.args) < 2:
        return CommandResponse.error_msg("Usage: !part <password> #channel")

    channel = context.args[1]

    if context.is_console:
        return f"Admin command: PART {channel}"
    else:
        # Send IRC command
        irc = bot_functions.get("irc")
        if irc:
            irc.sendall(f"PART {channel}\r\n".encode("utf-8"))

            log_func = bot_functions.get("log")
            if log_func:
                log_func(f"Admin left channel {channel}", "INFO")

            return f"Left {channel}"
        else:
            return CommandResponse.error_msg("IRC connection not available")


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
        return CommandResponse.error_msg("Invalid admin password")

    if len(context.args) < 2:
        return CommandResponse.error_msg("Usage: !nick <password> <new_nickname>")

    new_nick = context.args[1]

    if context.is_console:
        return f"Admin command: NICK {new_nick}"
    else:
        # Send IRC command
        irc = bot_functions.get("irc")
        if irc:
            irc.sendall(f"NICK {new_nick}\r\n".encode("utf-8"))

            log_func = bot_functions.get("log")
            if log_func:
                log_func(f"Admin changed nick to {new_nick}", "INFO")

            return f"Changed nick to {new_nick}"
        else:
            return CommandResponse.error_msg("IRC connection not available")


@command(
    "quit",
    description="Quit IRC with message (admin only)",
    usage="!quit <password> [message]",
    examples=["!quit mypass", "!quit mypass Goodbye everyone!"],
    admin_only=True,
    requires_args=True,
    scope=CommandScope.IRC_ONLY,
)
def quit_command(context: CommandContext, bot_functions):
    """Quit IRC with an optional message."""
    if not verify_admin_password(context.args):
        return CommandResponse.error_msg("Invalid admin password")

    quit_message = " ".join(context.args[1:]) if len(context.args) > 1 else "Admin quit"

    # Send IRC command
    irc = bot_functions.get("irc")
    if irc:
        irc.sendall(f"QUIT :{quit_message}\r\n".encode("utf-8"))

        log_func = bot_functions.get("log")
        if log_func:
            log_func(f"Admin quit with message: {quit_message}", "INFO")

        return (
            CommandResponse.no_response()
        )  # Don't send a response since we're quitting
    else:
        return CommandResponse.error_msg("IRC connection not available")


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
        return CommandResponse.error_msg("Invalid admin password")

    if len(context.args) < 2:
        return CommandResponse.error_msg("Usage: !raw <password> <IRC_COMMAND>")

    raw_command = " ".join(context.args[1:])

    # Send IRC command
    irc = bot_functions.get("irc")
    if irc:
        irc.sendall(f"{raw_command}\r\n".encode("utf-8"))

        log_func = bot_functions.get("log")
        if log_func:
            log_func(f"Admin sent raw command: {raw_command}", "INFO")

        return f"Sent: {raw_command}"
    else:
        return CommandResponse.error_msg("IRC connection not available")


# Import this module to register the commands
def register_admin_commands():
    """Register all admin commands. Called automatically when module is imported."""
    pass


# Auto-register when imported
register_admin_commands()
