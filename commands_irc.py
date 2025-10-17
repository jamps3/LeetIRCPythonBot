"""
IRC Commands Module for LeetIRCPythonBot

This module contains IRC-specific commands that use the / prefix instead of !.
These commands provide direct IRC functionality like joining channels, changing
nicks, sending messages, etc.
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


def get_irc_connection(context: CommandContext, bot_functions):
    """Get IRC connection for the current context."""
    if context.is_console:
        # In console mode, we need to get the active server
        bot_manager = bot_functions.get("bot_manager")
        if bot_manager and bot_manager.servers:
            # Use the first connected server as default
            for server in bot_manager.servers.values():
                if hasattr(server, "connected") and server.connected:
                    return server
            # If no connected servers, use the first one
            return next(iter(bot_manager.servers.values()))
    else:
        # In IRC mode, use the current IRC connection
        return bot_functions.get("irc")
    return None


@command(
    "join",
    description="Join an IRC channel",
    usage="/join <#channel> [key]",
    examples=["/join #general", "/join #private secretkey"],
    requires_args=True,
)
def irc_join_command(context: CommandContext, bot_functions):
    """Join an IRC channel."""
    if len(context.args) < 1:
        return "Usage: /join <#channel> [key]"

    channel = context.args[0]
    key = context.args[1] if len(context.args) > 1 else ""

    # Ensure channel starts with #
    if not channel.startswith("#"):
        channel = "#" + channel

    irc = get_irc_connection(context, bot_functions)
    if not irc:
        return "❌ No IRC connection available"

    try:
        if hasattr(irc, "send_raw"):
            if key:
                irc.send_raw(f"JOIN {channel} {key}")
            else:
                irc.send_raw(f"JOIN {channel}")
        else:
            # Fallback for different IRC client interfaces
            if key:
                irc.send(f"JOIN {channel} {key}")
            else:
                irc.send(f"JOIN {channel}")

        # Log the action
        log_func = bot_functions.get("log")
        if log_func:
            log_func(f"Joined channel {channel}", "INFO")

        return f"✅ Joining {channel}"

    except Exception as e:
        return f"❌ Failed to join {channel}: {str(e)}"


@command(
    "part",
    description="Leave an IRC channel",
    usage="/part <#channel> [message]",
    examples=["/part #general", "/part #random Goodbye!"],
    requires_args=True,
)
def irc_part_command(context: CommandContext, bot_functions):
    """Leave an IRC channel."""
    if len(context.args) < 1:
        return "Usage: /part <#channel> [message]"

    channel = context.args[0]
    message = " ".join(context.args[1:]) if len(context.args) > 1 else ""

    # Ensure channel starts with #
    if not channel.startswith("#"):
        channel = "#" + channel

    irc = get_irc_connection(context, bot_functions)
    if not irc:
        return "❌ No IRC connection available"

    try:
        if hasattr(irc, "send_raw"):
            if message:
                irc.send_raw(f"PART {channel} :{message}")
            else:
                irc.send_raw(f"PART {channel}")
        else:
            # Fallback for different IRC client interfaces
            if message:
                irc.send(f"PART {channel} :{message}")
            else:
                irc.send(f"PART {channel}")

        # Log the action
        log_func = bot_functions.get("log")
        if log_func:
            log_func(f"Left channel {channel}", "INFO")

        return f"✅ Left {channel}"

    except Exception as e:
        return f"❌ Failed to leave {channel}: {str(e)}"


@command(
    "quit",
    description="Disconnect from IRC server",
    usage="/quit [message]",
    examples=["/quit", "/quit Goodbye everyone!"],
)
def irc_quit_command(context: CommandContext, bot_functions):
    """Disconnect from IRC server."""
    message = " ".join(context.args) if context.args else "Quit"

    irc = get_irc_connection(context, bot_functions)
    if not irc:
        return "❌ No IRC connection available"

    try:
        if hasattr(irc, "send_raw"):
            irc.send_raw(f"QUIT :{message}")
        else:
            irc.send(f"QUIT :{message}")

        # Log the action
        log_func = bot_functions.get("log")
        if log_func:
            log_func(f"Quit IRC with message: {message}", "INFO")

        # Also trigger bot shutdown if requested
        stop_event = bot_functions.get("stop_event")
        if stop_event and context.is_console:
            stop_event.set()

        return f"✅ Disconnecting: {message}"

    except Exception as e:
        return f"❌ Failed to quit: {str(e)}"


@command(
    "nick",
    description="Change your nickname",
    usage="/nick <new_nickname>",
    examples=["/nick NewNick"],
    requires_args=True,
)
def irc_nick_command(context: CommandContext, bot_functions):
    """Change your nickname."""
    if len(context.args) < 1:
        return "Usage: /nick <new_nickname>"

    new_nick = context.args[0]

    irc = get_irc_connection(context, bot_functions)
    if not irc:
        return "❌ No IRC connection available"

    try:
        if hasattr(irc, "send_raw"):
            irc.send_raw(f"NICK {new_nick}")
        else:
            irc.send(f"NICK {new_nick}")

        # Log the action
        log_func = bot_functions.get("log")
        if log_func:
            log_func(f"Changed nick to {new_nick}", "INFO")

        return f"✅ Changing nick to {new_nick}"

    except Exception as e:
        return f"❌ Failed to change nick: {str(e)}"


@command(
    "msg",
    description="Send a private message to a user",
    usage="/msg <nick> <message>",
    examples=["/msg Alice Hello there!"],
    requires_args=True,
)
def irc_msg_command(context: CommandContext, bot_functions):
    """Send a private message to a user."""
    if len(context.args) < 2:
        return "Usage: /msg <nick> <message>"

    target = context.args[0]
    message = " ".join(context.args[1:])

    irc = get_irc_connection(context, bot_functions)
    if not irc:
        return "❌ No IRC connection available"

    try:
        if hasattr(irc, "send_raw"):
            irc.send_raw(f"PRIVMSG {target} :{message}")
        elif hasattr(irc, "send_message"):
            irc.send_message(target, message)
        else:
            irc.send(f"PRIVMSG {target} :{message}")

        return f"✅ Message sent to {target}"

    except Exception as e:
        return f"❌ Failed to send message: {str(e)}"


@command(
    "notice",
    description="Send a notice to a user (less intrusive than /msg)",
    usage="/notice <nick> <message>",
    examples=["/notice Bob Important info here"],
    requires_args=True,
)
def irc_notice_command(context: CommandContext, bot_functions):
    """Send a notice to a user."""
    if len(context.args) < 2:
        return "Usage: /notice <nick> <message>"

    target = context.args[0]
    message = " ".join(context.args[1:])

    irc = get_irc_connection(context, bot_functions)
    if not irc:
        return "❌ No IRC connection available"

    try:
        if hasattr(irc, "send_raw"):
            irc.send_raw(f"NOTICE {target} :{message}")
        elif hasattr(irc, "send_notice"):
            irc.send_notice(target, message)
        else:
            irc.send(f"NOTICE {target} :{message}")

        return f"✅ Notice sent to {target}"

    except Exception as e:
        return f"❌ Failed to send notice: {str(e)}"


@command(
    "away",
    description="Set or remove away status",
    usage="/away [message]",
    examples=["/away", "/away Gone for lunch"],
)
def irc_away_command(context: CommandContext, bot_functions):
    """Set or remove away status."""
    message = " ".join(context.args) if context.args else ""

    irc = get_irc_connection(context, bot_functions)
    if not irc:
        return "❌ No IRC connection available"

    try:
        if hasattr(irc, "send_raw"):
            if message:
                irc.send_raw(f"AWAY :{message}")
            else:
                irc.send_raw("AWAY")
        else:
            if message:
                irc.send(f"AWAY :{message}")
            else:
                irc.send("AWAY")

        if message:
            return f"✅ Set away: {message}"
        else:
            return "✅ Removed away status"

    except Exception as e:
        return f"❌ Failed to set away status: {str(e)}"


@command(
    "whois",
    description="Get information about a user",
    usage="/whois <nick>",
    examples=["/whois Alice"],
    requires_args=True,
)
def irc_whois_command(context: CommandContext, bot_functions):
    """Get information about a user."""
    if len(context.args) < 1:
        return "Usage: /whois <nick>"

    nick = context.args[0]

    irc = get_irc_connection(context, bot_functions)
    if not irc:
        return "❌ No IRC connection available"

    try:
        if hasattr(irc, "send_raw"):
            irc.send_raw(f"WHOIS {nick}")
        else:
            irc.send(f"WHOIS {nick}")

        return f"✅ WHOIS request sent for {nick}"

    except Exception as e:
        return f"❌ Failed to send WHOIS: {str(e)}"


@command(
    "whowas",
    description="Get information about a user who was recently online",
    usage="/whowas <nick>",
    examples=["/whowas Alice"],
    requires_args=True,
)
def irc_whowas_command(context: CommandContext, bot_functions):
    """Get information about a user who was recently online."""
    if len(context.args) < 1:
        return "Usage: /whowas <nick>"

    nick = context.args[0]

    irc = get_irc_connection(context, bot_functions)
    if not irc:
        return "❌ No IRC connection available"

    try:
        if hasattr(irc, "send_raw"):
            irc.send_raw(f"WHOWAS {nick}")
        else:
            irc.send(f"WHOWAS {nick}")

        return f"✅ WHOWAS request sent for {nick}"

    except Exception as e:
        return f"❌ Failed to send WHOWAS: {str(e)}"


@command(
    "list",
    description="List available channels",
    usage="/list [#channel]",
    examples=["/list", "/list #general"],
)
def irc_list_command(context: CommandContext, bot_functions):
    """List available channels."""
    channel = context.args[0] if context.args else ""

    irc = get_irc_connection(context, bot_functions)
    if not irc:
        return "❌ No IRC connection available"

    try:
        if hasattr(irc, "send_raw"):
            if channel:
                irc.send_raw(f"LIST {channel}")
            else:
                irc.send_raw("LIST")
        else:
            if channel:
                irc.send(f"LIST {channel}")
            else:
                irc.send("LIST")

        if channel:
            return f"✅ Listing channel info for {channel}"
        else:
            return "✅ Listing all channels"

    except Exception as e:
        return f"❌ Failed to list channels: {str(e)}"


@command(
    "invite",
    description="Invite a user to a channel",
    usage="/invite <nick> <#channel>",
    examples=["/invite Alice #general"],
    requires_args=True,
)
def irc_invite_command(context: CommandContext, bot_functions):
    """Invite a user to a channel."""
    if len(context.args) < 2:
        return "Usage: /invite <nick> <#channel>"

    nick = context.args[0]
    channel = context.args[1]

    # Ensure channel starts with #
    if not channel.startswith("#"):
        channel = "#" + channel

    irc = get_irc_connection(context, bot_functions)
    if not irc:
        return "❌ No IRC connection available"

    try:
        if hasattr(irc, "send_raw"):
            irc.send_raw(f"INVITE {nick} {channel}")
        else:
            irc.send(f"INVITE {nick} {channel}")

        return f"✅ Invited {nick} to {channel}"

    except Exception as e:
        return f"❌ Failed to invite user: {str(e)}"


@command(
    "kick",
    description="Kick a user from a channel (requires privileges)",
    usage="/kick <nick> [reason]",
    examples=["/kick BadUser", "/kick BadUser Spam"],
    requires_args=True,
)
def irc_kick_command(context: CommandContext, bot_functions):
    """Kick a user from a channel."""
    if len(context.args) < 1:
        return "Usage: /kick <nick> [reason]"

    nick = context.args[0]
    reason = " ".join(context.args[1:]) if len(context.args) > 1 else ""

    # For console mode, we need to determine the target channel
    channel = context.target if not context.is_console else None
    if not channel or not channel.startswith("#"):
        return "❌ This command must be used in a channel or specify a channel"

    irc = get_irc_connection(context, bot_functions)
    if not irc:
        return "❌ No IRC connection available"

    try:
        if hasattr(irc, "send_raw"):
            if reason:
                irc.send_raw(f"KICK {channel} {nick} :{reason}")
            else:
                irc.send_raw(f"KICK {channel} {nick}")
        else:
            if reason:
                irc.send(f"KICK {channel} {nick} :{reason}")
            else:
                irc.send(f"KICK {channel} {nick}")

        return f"✅ Kicked {nick} from {channel}"

    except Exception as e:
        return f"❌ Failed to kick user: {str(e)}"


@command(
    "topic",
    description="Set the channel topic",
    usage="/topic <#channel> <new_topic>",
    examples=["/topic #general Welcome to our channel!"],
    requires_args=True,
)
def irc_topic_command(context: CommandContext, bot_functions):
    """Set the channel topic."""
    if len(context.args) < 2:
        return "Usage: /topic <#channel> <new_topic>"

    channel = context.args[0]
    topic = " ".join(context.args[1:])

    # Ensure channel starts with #
    if not channel.startswith("#"):
        channel = "#" + channel

    irc = get_irc_connection(context, bot_functions)
    if not irc:
        return "❌ No IRC connection available"

    try:
        if hasattr(irc, "send_raw"):
            irc.send_raw(f"TOPIC {channel} :{topic}")
        else:
            irc.send(f"TOPIC {channel} :{topic}")

        return f"✅ Set topic for {channel}: {topic}"

    except Exception as e:
        return f"❌ Failed to set topic: {str(e)}"


@command(
    "mode",
    description="Change user or channel modes",
    usage="/mode <target> <modes>",
    examples=["/mode #channel +t", "/mode Alice +v"],
    requires_args=True,
)
def irc_mode_command(context: CommandContext, bot_functions):
    """Change user or channel modes."""
    if len(context.args) < 2:
        return "Usage: /mode <target> <modes>"

    target = context.args[0]
    modes = " ".join(context.args[1:])

    irc = get_irc_connection(context, bot_functions)
    if not irc:
        return "❌ No IRC connection available"

    try:
        if hasattr(irc, "send_raw"):
            irc.send_raw(f"MODE {target} {modes}")
        else:
            irc.send(f"MODE {target} {modes}")

        return f"✅ Set mode {modes} on {target}"

    except Exception as e:
        return f"❌ Failed to set mode: {str(e)}"


@command(
    "names",
    description="List users in a channel",
    usage="/names <#channel>",
    examples=["/names #general"],
    requires_args=True,
)
def irc_names_command(context: CommandContext, bot_functions):
    """List users in a channel."""
    if len(context.args) < 1:
        return "Usage: /names <#channel>"

    channel = context.args[0]

    # Ensure channel starts with #
    if not channel.startswith("#"):
        channel = "#" + channel

    irc = get_irc_connection(context, bot_functions)
    if not irc:
        return "❌ No IRC connection available"

    try:
        if hasattr(irc, "send_raw"):
            irc.send_raw(f"NAMES {channel}")
        else:
            irc.send(f"NAMES {channel}")

        return f"✅ Requesting user list for {channel}"

    except Exception as e:
        return f"❌ Failed to get names: {str(e)}"


@command(
    "ircping",
    description="Check server response",
    usage="/ircping <server>",
    examples=["/ircping irc.example.com"],
    requires_args=True,
)
def irc_ping_command(context: CommandContext, bot_functions):
    """Check server response."""
    if len(context.args) < 1:
        return "Usage: /ping <server>"

    server = context.args[0]

    irc = get_irc_connection(context, bot_functions)
    if not irc:
        return "❌ No IRC connection available"

    try:
        if hasattr(irc, "send_raw"):
            irc.send_raw(f"PING {server}")
        else:
            irc.send(f"PING {server}")

        return f"✅ Ping sent to {server}"

    except Exception as e:
        return f"❌ Failed to ping: {str(e)}"


@command(
    "irctime",
    description="Get server time",
    usage="/irctime",
    examples=["/irctime"],
)
def irc_time_command(context: CommandContext, bot_functions):
    """Get server time."""
    irc = get_irc_connection(context, bot_functions)
    if not irc:
        return "❌ No IRC connection available"

    try:
        if hasattr(irc, "send_raw"):
            irc.send_raw("TIME")
        else:
            irc.send("TIME")

        return "✅ Time request sent to server"

    except Exception as e:
        return f"❌ Failed to get time: {str(e)}"


@command(
    "ircversion",
    description="Get server software version",
    usage="/ircversion",
    examples=["/ircversion"],
)
def irc_version_command(context: CommandContext, bot_functions):
    """Get server software version."""
    irc = get_irc_connection(context, bot_functions)
    if not irc:
        return "❌ No IRC connection available"

    try:
        if hasattr(irc, "send_raw"):
            irc.send_raw("VERSION")
        else:
            irc.send("VERSION")

        return "✅ Version request sent to server"

    except Exception as e:
        return f"❌ Failed to get version: {str(e)}"


@command(
    "ircadmin",
    description="Get server administrator info",
    usage="/ircadmin [server]",
    examples=["/ircadmin", "/ircadmin irc.example.com"],
)
def irc_admin_command(context: CommandContext, bot_functions):
    """Get server administrator info."""
    server = context.args[0] if context.args else ""

    irc = get_irc_connection(context, bot_functions)
    if not irc:
        return "❌ No IRC connection available"

    try:
        if hasattr(irc, "send_raw"):
            if server:
                irc.send_raw(f"ADMIN {server}")
            else:
                irc.send_raw("ADMIN")
        else:
            if server:
                irc.send(f"ADMIN {server}")
            else:
                irc.send("ADMIN")

        return "✅ Admin info request sent"

    except Exception as e:
        return f"❌ Failed to get admin info: {str(e)}"


@command(
    "motd",
    description="Show the Message of the Day",
    usage="/motd",
    examples=["/motd"],
)
def irc_motd_command(context: CommandContext, bot_functions):
    """Show the Message of the Day."""
    irc = get_irc_connection(context, bot_functions)
    if not irc:
        return "❌ No IRC connection available"

    try:
        if hasattr(irc, "send_raw"):
            irc.send_raw("MOTD")
        else:
            irc.send("MOTD")

        return "✅ MOTD request sent"

    except Exception as e:
        return f"❌ Failed to get MOTD: {str(e)}"


@command(
    "raw",
    description="Send raw IRC command",
    usage="/raw <command>",
    examples=["/raw MODE #channel +t"],
    requires_args=True,
)
def irc_raw_command(context: CommandContext, bot_functions):
    """Send raw IRC command."""
    raw_command = " ".join(context.args)

    irc = get_irc_connection(context, bot_functions)
    if not irc:
        return "❌ No IRC connection available"

    try:
        if hasattr(irc, "send_raw"):
            irc.send_raw(raw_command)
        else:
            irc.send(raw_command)

        return f"✅ Raw command sent: {raw_command}"

    except Exception as e:
        return f"❌ Failed to send raw command: {str(e)}"
