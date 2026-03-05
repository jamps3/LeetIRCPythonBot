"""
IRC Commands Module

Contains IRC-specific commands: join, part, nick, msg, quit, ping, whois, etc.
These commands allow users to control the IRC connection and interact with IRC servers.
"""

from command_registry import CommandContext, CommandResponse, CommandScope, command


def get_irc_connection(bot_functions):
    """Get IRC connection from bot_functions."""
    # Try server_manager first (for console commands)
    server_manager = bot_functions.get("server_manager")
    if server_manager:
        # Get the active server's IRC connection
        if hasattr(server_manager, "servers") and server_manager.servers:
            # Get first active server
            for server in server_manager.servers.values():
                if server and hasattr(server, "irc_client") and server.irc_client:
                    return server.irc_client
    return None


# =====================
# Join Command
# =====================


@command(
    "join",
    description="Join a channel",
    usage="!join #channel [key]",
    examples=["!join #test", "!join #test secretkey"],
    scope=CommandScope.IRC_AND_CONSOLE,
)
def irc_join_command(context: CommandContext, bot_functions):
    """Join a channel on IRC."""
    if not context.args:
        return "Usage: !join #channel [key]"

    channel = context.args[0]
    if not channel.startswith("#"):
        channel = "#" + channel

    key = context.args[1] if len(context.args) > 1 else None

    irc = get_irc_connection(bot_functions)
    if not irc:
        return "Not connected to any IRC server"

    if key:
        irc.send_raw(f"JOIN {channel} {key}")
    else:
        irc.send_raw(f"JOIN {channel}")

    return f"Joining {channel}..."


# =====================
# Part Command
# =====================


@command(
    "part",
    description="Leave a channel",
    usage="!part #channel [message]",
    examples=["!part #test", "!part #test Goodbye!"],
    scope=CommandScope.IRC_AND_CONSOLE,
)
def irc_part_command(context: CommandContext, bot_functions):
    """Leave a channel on IRC."""
    if not context.args:
        return "Usage: !part #channel [message]"

    channel = context.args[0]
    if not channel.startswith("#"):
        channel = "#" + channel

    message = " ".join(context.args[1:]) if len(context.args) > 1 else None

    irc = get_irc_connection(bot_functions)
    if not irc:
        return "Not connected to any IRC server"

    if message:
        irc.send_raw(f"PART {channel} :{message}")
    else:
        irc.send_raw(f"PART {channel}")

    return f"Leaving {channel}..."


# =====================
# Nick Command
# =====================


@command(
    "nick",
    description="Change nickname",
    usage="!nick newnick",
    examples=["!nick NewNick"],
    scope=CommandScope.IRC_AND_CONSOLE,
)
def irc_nick_command(context: CommandContext, bot_functions):
    """Change nickname on IRC."""
    if not context.args:
        return "Usage: !nick newnick"

    new_nick = context.args[0]

    irc = get_irc_connection(bot_functions)
    if not irc:
        return "Not connected to any IRC server"

    irc.send_raw(f"NICK {new_nick}")

    return f"Changing nick to {new_nick}..."


# =====================
# Msg Command
# =====================


@command(
    "msg",
    description="Send a private message",
    usage="!msg nick/channel message",
    examples=["!msg #test Hello!", "!msg UserHello!"],
    scope=CommandScope.IRC_AND_CONSOLE,
)
def irc_msg_command(context: CommandContext, bot_functions):
    """Send a private message on IRC."""
    if len(context.args) < 2:
        return "Usage: !msg nick/channel message"

    target = context.args[0]
    message = " ".join(context.args[1:])

    irc = get_irc_connection(bot_functions)
    if not irc:
        return "Not connected to any IRC server"

    irc.send_message(target, message)

    return f"Sent message to {target}"


# =====================
# Notice Command
# =====================


@command(
    "notice",
    description="Send a notice",
    usage="!notice nick/channel message",
    examples=["!notice #test Hello!", "!notice UserHello!"],
    scope=CommandScope.IRC_AND_CONSOLE,
)
def irc_notice_command(context: CommandContext, bot_functions):
    """Send a notice on IRC."""
    if len(context.args) < 2:
        return "Usage: !notice nick/channel message"

    target = context.args[0]
    message = " ".join(context.args[1:])

    irc = get_irc_connection(bot_functions)
    if not irc:
        return "Not connected to any IRC server"

    irc.send_notice(target, message)

    return f"Sent notice to {target}"


# =====================
# Quit Command - handled by admin.py and console_manager
# =====================


# =====================
# IRC Ping Command - Ping the IRC server
# =====================


@command(
    "ircping",
    description="Send IRC PING to server",
    usage="!ircping [server]",
    examples=["!ircping", "!ircping irc.example.com"],
    scope=CommandScope.IRC_AND_CONSOLE,
)
def irc_ping_command(context: CommandContext, bot_functions):
    """Send IRC PING."""
    target = context.args[0] if context.args else "irc.example.com"

    irc = get_irc_connection(bot_functions)
    if not irc:
        return "Not connected to any IRC server"

    import time

    timestamp = int(time.time())
    irc.send_raw(f"PING :{timestamp}")

    return f"Sent PING to {target}"


# =====================
# WhoIs Command
# =====================


@command(
    "whois",
    description="Query user information",
    usage="!whois nick",
    examples=["!whois TestUser"],
    scope=CommandScope.IRC_AND_CONSOLE,
)
def irc_whois_command(context: CommandContext, bot_functions):
    """Query WHOIS information on IRC."""
    if not context.args:
        return "Usage: !whois nick"

    target = context.args[0]

    irc = get_irc_connection(bot_functions)
    if not irc:
        return "Not connected to any IRC server"

    irc.send_raw(f"WHOIS {target}")

    return f"Querying WHOIS for {target}..."


# =====================
# WhoWas Command
# =====================


@command(
    "whowas",
    description="Query past user information",
    usage="!whowas nick",
    examples=["!whowas TestUser"],
    scope=CommandScope.IRC_AND_CONSOLE,
)
def irc_whowas_command(context: CommandContext, bot_functions):
    """Query WHOWAS information on IRC."""
    if not context.args:
        return "Usage: !whowas nick"

    target = context.args[0]

    irc = get_irc_connection(bot_functions)
    if not irc:
        return "Not connected to any IRC server"

    irc.send_raw(f"WHOWAS {target}")

    return f"Querying WHOWAS for {target}..."


# =====================
# Names Command
# =====================


@command(
    "names",
    description="List users in a channel",
    usage="!names #channel",
    examples=["!names #test"],
    scope=CommandScope.IRC_AND_CONSOLE,
)
def irc_names_command(context: CommandContext, bot_functions):
    """List users in a channel on IRC."""
    if not context.args:
        return "Usage: !names #channel"

    channel = context.args[0]
    if not channel.startswith("#"):
        channel = "#" + channel

    irc = get_irc_connection(bot_functions)
    if not irc:
        return "Not connected to any IRC server"

    irc.send_raw(f"NAMES {channel}")

    return f"Querying NAMES for {channel}..."


# =====================
# List Command
# =====================


@command(
    "list",
    description="List channels on server",
    usage="!list [#channel]",
    examples=["!list", "!list #test"],
    scope=CommandScope.IRC_AND_CONSOLE,
)
def irc_list_command(context: CommandContext, bot_functions):
    """List channels on IRC server."""
    channel = context.args[0] if context.args else None

    irc = get_irc_connection(bot_functions)
    if not irc:
        return "Not connected to any IRC server"

    if channel:
        if not channel.startswith("#"):
            channel = "#" + channel
        irc.send_raw(f"LIST {channel}")
    else:
        irc.send_raw("LIST")

    return "Querying channel list..."


# =====================
# Topic Command
# =====================


@command(
    "topic",
    description="Get/set channel topic",
    usage="!topic #channel [new topic]",
    examples=["!topic #test", "!topic #test New Topic!"],
    scope=CommandScope.IRC_AND_CONSOLE,
)
def irc_topic_command(context: CommandContext, bot_functions):
    """Get or set channel topic on IRC."""
    if not context.args:
        return "Usage: !topic #channel [new topic]"

    channel = context.args[0]
    if not channel.startswith("#"):
        channel = "#" + channel

    irc = get_irc_connection(bot_functions)
    if not irc:
        return "Not connected to any IRC server"

    if len(context.args) > 1:
        # Set topic
        topic = " ".join(context.args[1:])
        irc.send_raw(f"TOPIC {channel} :{topic}")
        return f"Setting topic for {channel}..."
    else:
        # Get topic
        irc.send_raw(f"TOPIC {channel}")
        return f"Querying topic for {channel}..."


# =====================
# Mode Command
# =====================


@command(
    "mode",
    description="Set channel/user mode",
    usage="!mode #channel/nick [modes]",
    examples=["!mode #test +t", "!mode #test +nt", "!mode nick +i"],
    scope=CommandScope.IRC_AND_CONSOLE,
)
def irc_mode_command(context: CommandContext, bot_functions):
    """Set channel or user mode on IRC."""
    if not context.args:
        return "Usage: !mode #channel/nick [modes]"

    target = context.args[0]
    modes = " ".join(context.args[1:]) if len(context.args) > 1 else None

    irc = get_irc_connection(bot_functions)
    if not irc:
        return "Not connected to any IRC server"

    if modes:
        irc.send_raw(f"MODE {target} {modes}")
        return f"Setting mode {modes} on {target}..."
    else:
        irc.send_raw(f"MODE {target}")
        return f"Querying modes for {target}..."


# =====================
# Invite Command
# =====================


@command(
    "invite",
    description="Invite user to channel",
    usage="!invite nick #channel",
    examples=["!invite User #test"],
    scope=CommandScope.IRC_AND_CONSOLE,
)
def irc_invite_command(context: CommandContext, bot_functions):
    """Invite user to channel on IRC."""
    if len(context.args) < 2:
        return "Usage: !invite nick #channel"

    nick = context.args[0]
    channel = context.args[1]
    if not channel.startswith("#"):
        channel = "#" + channel

    irc = get_irc_connection(bot_functions)
    if not irc:
        return "Not connected to any IRC server"

    irc.send_raw(f"INVITE {nick} {channel}")

    return f"Inviting {nick} to {channel}..."


# =====================
# Kick Command
# =====================


@command(
    "kick",
    description="Kick user from channel",
    usage="!kick #channel nick [reason]",
    examples=["!kick #test User", "!kick #test User Bad behavior"],
    scope=CommandScope.IRC_AND_CONSOLE,
)
def irc_kick_command(context: CommandContext, bot_functions):
    """Kick user from channel on IRC."""
    if len(context.args) < 2:
        return "Usage: !kick #channel nick [reason]"

    channel = context.args[0]
    if not channel.startswith("#"):
        channel = "#" + channel

    nick = context.args[1]
    reason = " ".join(context.args[2:]) if len(context.args) > 2 else None

    irc = get_irc_connection(bot_functions)
    if not irc:
        return "Not connected to any IRC server"

    if reason:
        irc.send_raw(f"KICK {channel} {nick} :{reason}")
    else:
        irc.send_raw(f"KICK {channel} {nick}")

    return f"Kicking {nick} from {channel}..."


# =====================
# Away Command
# =====================


@command(
    "away",
    description="Set away status",
    usage="!away [message]",
    examples=["!away", "!away Be right back!"],
    scope=CommandScope.IRC_AND_CONSOLE,
)
def irc_away_command(context: CommandContext, bot_functions):
    """Set away status on IRC."""
    message = " ".join(context.args) if context.args else None

    irc = get_irc_connection(bot_functions)
    if not irc:
        return "Not connected to any IRC server"

    if message:
        irc.send_raw(f"AWAY :{message}")
        return f"Setting away: {message}"
    else:
        irc.send_raw("AWAY")
        return "Marking as back (removing away status)"


# =====================
# MOTD Command
# =====================


@command(
    "motd",
    description="Get server message of the day",
    usage="!motd",
    examples=["!motd"],
    scope=CommandScope.IRC_AND_CONSOLE,
)
def irc_motd_command(context: CommandContext, bot_functions):
    """Get server MOTD on IRC."""
    irc = get_irc_connection(bot_functions)
    if not irc:
        return "Not connected to any IRC server"

    irc.send_raw("MOTD")

    return "Querying MOTD..."


# =====================
# Time Command
# =====================


@command(
    "time",
    description="Get server time",
    usage="!time [server]",
    examples=["!time", "!time irc.example.com"],
    scope=CommandScope.IRC_AND_CONSOLE,
)
def irc_time_command(context: CommandContext, bot_functions):
    """Get server time on IRC."""
    target = context.args[0] if context.args else None

    irc = get_irc_connection(bot_functions)
    if not irc:
        return "Not connected to any IRC server"

    if target:
        irc.send_raw(f"TIME {target}")
    else:
        irc.send_raw("TIME")

    return "Querying server time..."


# =====================
# Version Command (IRC)
# =====================


@command(
    "ircversion",
    description="Get server version",
    usage="!ircversion [server]",
    examples=["!ircversion", "!ircversion irc.example.com"],
    scope=CommandScope.IRC_AND_CONSOLE,
)
def irc_version_command(context: CommandContext, bot_functions):
    """Get server version on IRC."""
    target = context.args[0] if context.args else None

    irc = get_irc_connection(bot_functions)
    if not irc:
        return "Not connected to any IRC server"

    if target:
        irc.send_raw(f"VERSION {target}")
    else:
        irc.send_raw("VERSION")

    return "Querying server version..."


# =====================
# Admin Command
# =====================


@command(
    "ircadmin",
    description="Get server admin info",
    usage="!ircadmin [server]",
    examples=["!ircadmin", "!ircadmin irc.example.com"],
    scope=CommandScope.IRC_AND_CONSOLE,
)
def irc_admin_command(context: CommandContext, bot_functions):
    """Get server admin info on IRC."""
    target = context.args[0] if context.args else None

    irc = get_irc_connection(bot_functions)
    if not irc:
        return "Not connected to any IRC server"

    if target:
        irc.send_raw(f"ADMIN {target}")
    else:
        irc.send_raw("ADMIN")

    return "Querying admin info..."


# =====================
# Raw Command
# =====================


@command(
    "raw",
    description="Send raw IRC command",
    usage="!raw <command>",
    examples=["!raw PRIVMSG #test :Hello!"],
    scope=CommandScope.IRC_ONLY,
)
def irc_raw_command(context: CommandContext, bot_functions):
    """Send raw IRC command."""
    if not context.args:
        return "Usage: !raw <command>"

    raw_command = context.args_text

    irc = get_irc_connection(bot_functions)
    if not irc:
        return "Not connected to any IRC server"

    irc.send_raw(raw_command)

    return f"Sent raw command: {raw_command}"


# =====================
# Lag Command - measure network lag
# =====================


@command(
    "lag",
    description="Measure network lag to a user (sends timestamped ping)",
    usage="!lag <nick>",
    examples=["!lag TestUser"],
    scope=CommandScope.IRC_AND_CONSOLE,
)
def lag_command(context: CommandContext, bot_functions):
    """Measure network lag to a user by sending a timestamped ping."""
    if not context.args:
        return "Usage: !lag <nick>"

    target_nick = context.args[0]

    # Get server_manager for lag tracking
    server_manager = bot_functions.get("server_manager")
    if not server_manager:
        return "Server manager not available"

    # Get the latency tracker
    latency_tracker = bot_functions.get("latency_tracker")
    if not latency_tracker:
        return "Latency tracker not available"

    # Get server name
    server_name = bot_functions.get("server_name", "unknown")

    # Send a CTCP PING to measure lag
    irc = get_irc_connection(bot_functions)
    if not irc:
        return "Not connected to any IRC server"

    import time

    timestamp = int(time.time() * 1000)  # milliseconds

    # Send CTCP PING
    irc.send_raw(f"PRIVMSG {target_nick} :\x01PING {timestamp}\x01")

    # Store the pending ping for later response matching
    latency_tracker._store_lag(server_name, target_nick, timestamp)

    return f"Pinging {target_nick} to measure lag..."


# =====================
# Sexact Command - send timestamped message for exact timing
# =====================


@command(
    "sexact",
    description="Send a timestamped message for exact timing measurement",
    usage="!sexact <nick> <time> <message>",
    examples=["!sexact TestUser 1234567890 Hello"],
    scope=CommandScope.IRC_AND_CONSOLE,
)
def sexact_command(context: CommandContext, bot_functions):
    """Send a timestamped message for exact timing measurement."""
    if len(context.args) < 3:
        return "Usage: !sexact <nick> <time> <message>"

    target_nick = context.args[0]
    timestamp = context.args[1]
    message = " ".join(context.args[2:])

    irc = get_irc_connection(bot_functions)
    if not irc:
        return "Not connected to any IRC server"

    # Send the message with timestamp in a way that can be correlated
    irc.send_raw(f"PRIVMSG {target_nick} :[{timestamp}] {message}")

    return f"Sent timed message to {target_nick}"
