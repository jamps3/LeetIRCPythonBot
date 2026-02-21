"""
IRC Commands Module for LeetIRCPythonBot

This module contains IRC-specific commands that use the / prefix instead of !.
These commands provide direct IRC functionality like joining channels, changing
nicks, sending messages, etc.
"""

from command_registry import CommandContext, CommandScope, command

# Import admin password verification
from commands_admin import verify_admin_password


def get_irc_connection(context: CommandContext, bot_functions):
    """Get IRC connection for the current context."""
    if context.is_console:
        # In console mode, we need to get the active server
        # Try bot_manager first, then fall back to server_manager
        bot_manager = bot_functions.get("bot_manager")
        server_manager = bot_functions.get("server_manager")

        # Try bot_manager.servers first
        if bot_manager and hasattr(bot_manager, "servers") and bot_manager.servers:
            # Use the first connected server as default
            for server in bot_manager.servers.values():
                if hasattr(server, "connected") and server.connected:
                    return server
            # If no connected servers, use the first one
            return next(iter(bot_manager.servers.values()))

        # Fall back to server_manager
        if (
            server_manager
            and hasattr(server_manager, "servers")
            and server_manager.servers
        ):
            # Use the first connected server as default
            for server in server_manager.servers.values():
                if hasattr(server, "connected") and server.connected:
                    return server
            # If no connected servers, use the first one
            return next(iter(server_manager.servers.values()))
    else:
        # In IRC mode, use the current IRC connection
        return bot_functions.get("irc")
    return None


@command(
    "join",
    description="Join an IRC channel",
    usage="/join <#channel> [key] or /join <server> <#channel> [key]",
    examples=["/join #general", "/join #private secretkey", "/join ircnet #channel"],
    requires_args=True,
    scope=CommandScope.BOTH,
)
def irc_join_command(context: CommandContext, bot_functions):
    """Join an IRC channel."""
    # Parse args.
    # NOTE: /join is not an admin-only command, so don't require a password.
    # We still allow an *optional* password as the first argument for
    # convenience/consistency with other admin-gated commands.
    args = list(context.args or [])
    if not context.is_console and verify_admin_password(args):
        args = args[1:]

    if len(args) < 1:
        return "Usage: /join <#channel> [key] or /join <server> <#channel> [key]"

    # Parse arguments: [server] <#channel> [key]
    # - /join #chan [key]
    # - /join server #chan [key]
    server_name = None
    if len(args) >= 2 and (not args[0].startswith("#")) and args[1].startswith("#"):
        # server + channel (+ optional key)
        server_name = args[0]
        channel = args[1]
        key = args[2] if len(args) > 2 else ""
    else:
        # channel (+ optional key)
        channel = args[0]
        key = args[1] if len(args) > 1 else ""

    # Ensure channel starts with #
    if not channel.startswith("#"):
        channel = "#" + channel

    # Get IRC connection
    if server_name:
        # Specific server requested
        bot_manager = bot_functions.get("bot_manager")
        if bot_manager and server_name in bot_manager.servers:
            irc = bot_manager.servers[server_name]
        else:
            return f"❌ Server '{server_name}' not found"
    else:
        # Use current or default connection
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
    scope=CommandScope.CONSOLE_ONLY,
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
    "ircquit",
    aliases=["quit"],
    description="Disconnect from IRC server",
    usage="/quit [message]",
    examples=["/quit", "/quit Goodbye everyone!"],
    scope=CommandScope.CONSOLE_ONLY,
)
def irc_quit_command(context: CommandContext, bot_functions):
    """Disconnect from IRC server."""
    message = " ".join(context.args) if context.args else "Quit"

    # Set the quit message globally for all servers before quitting
    set_quit_message = bot_functions.get("set_quit_message")
    if set_quit_message:
        set_quit_message(message)

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
    scope=CommandScope.CONSOLE_ONLY,
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
    scope=CommandScope.CONSOLE_ONLY,
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
    scope=CommandScope.CONSOLE_ONLY,
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
    scope=CommandScope.CONSOLE_ONLY,
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
    scope=CommandScope.CONSOLE_ONLY,
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
    scope=CommandScope.CONSOLE_ONLY,
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
    scope=CommandScope.CONSOLE_ONLY,
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
    scope=CommandScope.CONSOLE_ONLY,
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
    scope=CommandScope.CONSOLE_ONLY,
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
    scope=CommandScope.CONSOLE_ONLY,
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
    scope=CommandScope.CONSOLE_ONLY,
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
    scope=CommandScope.CONSOLE_ONLY,
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
    scope=CommandScope.CONSOLE_ONLY,
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
    scope=CommandScope.CONSOLE_ONLY,
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
    "latency",
    aliases=["lag"],
    description="Measure latency, show stored lags, or clear lag storage",
    usage="!lag <nick> [show|clear] | !lag list | !lag clear [nick]",
    examples=[
        "!lag Beiki - measure latency to Beiki",
        "!lag Beiki show - show stored lag for Beiki",
        "!lag list - list all stored lags",
        "!lag clear Beiki - clear lag for Beiki",
        "!lag clear - clear all lags",
    ],
    requires_args=False,
    scope=CommandScope.CONSOLE_ONLY,
)
def latency_command(context: CommandContext, bot_functions):
    """
    Measure latency to another bot by sending !ping and reading the response time,
    or manage stored lag values.

    The target bot should respond with a NOTICE containing "Kello on HH.MM.SS,NNNNNNNNN"
    """
    # Get the message handler
    bot_manager = bot_functions.get("bot_manager")
    if not bot_manager:
        message_handler = bot_functions.get("message_handler")
        if message_handler:
            class BotManagerStub:
                def __init__(self, mh):
                    self.message_handler = mh

            bot_manager = BotManagerStub(message_handler)
        else:
            return "❌ Bot manager not available (not in bot_functions)"
    elif not hasattr(bot_manager, "message_handler"):
        return f"❌ Bot manager available but has no message_handler attribute (type: {type(bot_manager)})"

    message_handler = bot_manager.message_handler

    # Get the server connection
    irc = get_irc_connection(context, bot_functions)
    if not irc:
        return "❌ No IRC connection available"

    # Handle subcommands
    if context.args:
        first_arg = context.args[0].lower()

        # !lag list - show all stored lags
        if first_arg == "list":
            lags = message_handler._list_lags()
            if not lags:
                return "📊 No stored lags"
            server_name = irc.config.name
            lines = [f"📊 Stored lags for {server_name}:"]
            for (srv, nick), lag_ms in sorted(lags.items(), key=lambda x: x[1]):
                if srv == server_name.lower():
                    lines.append(f"  {nick}: {lag_ms:.2f} ms")
            return "\n".join(lines) if len(lines) > 1 else "📊 No stored lags for this server"

        # !lag clear [nick] - clear lag(s)
        if first_arg == "clear":
            if len(context.args) > 1:
                nick = context.args[1]
                server_name = irc.config.name
                result = message_handler._clear_lag(server_name, nick)
                if result:
                    return f"✅ Cleared lag for {nick}"
                return f"❌ No lag found for {nick}"
            else:
                # Clear all lags for this server
                server_name = irc.config.name
                lags = message_handler._list_lags(server_name)
                count = len(lags)
                for (srv, nick) in lags.keys():
                    message_handler._clear_lag(srv, nick)
                return f"✅ Cleared {count} lag(s) for {server_name}"

        # !lag <nick> [show|clear] - show or clear specific nick
        target = first_arg
        if len(context.args) > 1:
            second_arg = context.args[1].lower()
            if second_arg == "show":
                server_name = irc.config.name
                lag = message_handler._get_lag(server_name, target)
                if lag is not None:
                    return f"📡 Stored lag for {target}: {lag:.2f} ms"
                return f"❌ No stored lag for {target}. Run !lag {target} first."
            if second_arg == "clear":
                server_name = irc.config.name
                result = message_handler._clear_lag(server_name, target)
                if result:
                    return f"✅ Cleared lag for {target}"
                return f"❌ No lag found for {target}"

        # No subcommand - measure latency
        try:
            result = message_handler._send_latency_ping(irc, target)
            return result
        except Exception as e:
            return f"❌ Failed to send latency ping: {str(e)}"

    # No args - show usage
    return "Usage: !lag <nick> (measure) | !lag <nick> show | !lag list | !lag clear [nick]"


@command(
    "sexact",
    description="Send a message at exact time using stored lag compensation",
    usage="!sexact <nick|#channel> <HH:MM:SS> <message>",
    examples=[
        "!sexact Beiki 12:00:00 Hello Beiki!",
        "!sexact Beiki #channel 14:30:00 Hello everyone!",
    ],
    requires_args=False,
    scope=CommandScope.CONSOLE_ONLY,
)
def sexact_command(context: CommandContext, bot_functions):
    """
    Send a message at exact time using stored lag compensation.
    
    Usage:
        !sexact <nick> <HH:MM:SS> <message>       - Send to nick (uses nick's lag)
        !sexact <nick> #channel <HH:MM:SS> <msg>  - Send to channel using nick's lag
    """
    import re
    from services.scheduled_message_service import send_scheduled_message

    # Get the message handler and server connection
    bot_manager = bot_functions.get("bot_manager")
    if not bot_manager:
        message_handler = bot_functions.get("message_handler")
        if message_handler:
            class BotManagerStub:
                def __init__(self, mh):
                    self.message_handler = mh
            bot_manager = BotManagerStub(message_handler)
        else:
            return "❌ Bot manager not available"
    elif not hasattr(bot_manager, "message_handler"):
        return "❌ Bot manager has no message_handler"

    message_handler = bot_manager.message_handler
    irc = get_irc_connection(context, bot_functions)
    if not irc:
        return "❌ No IRC connection available"

    # Parse arguments
    if len(context.args) < 3:
        return "Usage: !sexact <nick> <HH:MM:SS> <message> or !sexact <nick> #channel <HH:MM:SS> <message>"

    # Check if format is: !sexact <nick> #channel <time> <message>
    # Pattern: nick starts with letter (not #), and has #channel as second arg
    if len(context.args) >= 4 and context.args[1].startswith("#"):
        # Format: !sexact <nick> #channel <time> <message>
        nick = context.args[0]
        channel = context.args[1]
        time_str = context.args[2]
        message = " ".join(context.args[3:])
    else:
        # Format: !sexact <nick|channel> <time> <message>
        target = context.args[0]
        time_str = context.args[1]
        message = " ".join(context.args[2:])
        
        # Determine if target is a nick or channel
        if target.startswith("#"):
            # It's a channel - need a nick to get lag from
            return "❌ For channels, use format: !sexact <nick> #channel <time> <message>"
        else:
            # It's a nick - send to the nick directly
            nick = target
            channel = nick

    # Parse time (HH:MM:SS)
    time_pattern = r"(\d{1,2}):(\d{2}):(\d{2})"
    match = re.match(time_pattern, time_str)
    if not match:
        return "❌ Invalid time format. Use HH:MM:SS"
    
    hour = int(match.group(1))
    minute = int(match.group(2))
    second = int(match.group(3))
    
    if hour > 23 or minute > 59 or second > 59:
        return "❌ Invalid time values"

    # Get stored lag for the nick
    server_name = irc.config.name
    lag_ms = message_handler._get_lag(server_name, nick)
    
    if lag_ms is None:
        return f"❌ No lag measured for {nick}. Run !lag {nick} first."

    # Schedule the message with lag compensation
    try:
        msg_id = send_scheduled_message(
            irc_client=irc,
            channel=channel,
            message=message,
            hour=hour,
            minute=minute,
            second=second,
            nanosecond=0,
            lag_ms=lag_ms,
        )
        target_time = f"{hour:02d}:{minute:02d}:{second:02d}"
        return f"✅ Message scheduled to arrive at {target_time} (sending at {target_time} - {lag_ms/2:.1f}ms early, lag: {lag_ms:.1f}ms)"
    except Exception as e:
        return f"❌ Failed to schedule message: {str(e)}"


@command(
    "ircadmin",
    description="Get server administrator info",
    usage="/ircadmin [server]",
    examples=["/ircadmin", "/ircadmin irc.example.com"],
    scope=CommandScope.CONSOLE_ONLY,
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
    scope=CommandScope.CONSOLE_ONLY,
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
    scope=CommandScope.CONSOLE_ONLY,
)
def irc_raw_command(context: CommandContext, bot_functions):
    """Send raw IRC command."""
    # Check connection first
    irc = get_irc_connection(context, bot_functions)
    if not irc:
        return "❌ No IRC connection available"

    # Determine how to handle password based on context
    args = list(context.args or [])
    if context.is_console:
        # Console: allow optional password. If the first arg matches the password, strip it
        if verify_admin_password(args):
            args = args[1:]
    else:
        # IRC: require password as first argument
        if not verify_admin_password(args):
            return "❌ Invalid admin password"
        args = args[1:]

    if not args:
        return "Usage: /raw <command>"

    raw_command = " ".join(args)

    try:
        if hasattr(irc, "send_raw"):
            irc.send_raw(raw_command)
        else:
            irc.send(raw_command)

        return f"✅ Raw command sent: {raw_command}"

    except Exception as e:
        return f"❌ Failed to send raw command: {str(e)}"
