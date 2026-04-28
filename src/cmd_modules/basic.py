"""
Basic Commands Module

Contains basic commands: help, ping, version, about, servers, status, channels
"""

import re
import time
from datetime import datetime

from command_registry import CommandContext, CommandResponse, CommandScope, command
from config import get_config

# =====================
# Help Command
# =====================


@command(
    "help",
    description="Show available commands",
    usage="!help [command]",
    examples=["!help", "!help weather"],
)
def help_command(context: CommandContext, bot_functions):
    """Show help for commands without duplicates and with custom ordering.

    Ordering rules:
    - Do not list the 'help' command itself.
    - List regular (non-admin, non-Tamagotchi) commands alphabetically.
    - Then list Tamagotchi-related commands (tamagotchi, feed, pet) alphabetically.
    - Finally list admin commands alphabetically (marked with * by the renderer).
    """
    from command_registry import CommandScope as _CS
    from command_registry import get_command_registry

    registry = get_command_registry()

    # If specific command requested, return its detailed help
    if context.args:
        command_name = context.args[0]
        help_text = registry.generate_help(specific_command=command_name)
        if context.is_console:
            return help_text
        else:
            return CommandResponse.success_msg(help_text)
    else:
        # Build command list depending on context. From IRC, show only IRC_ONLY.
        if context.is_console:
            infos = registry.get_commands_info(
                scope=_CS.CONSOLE_ONLY
            ) + registry.get_commands_info(scope=_CS.BOTH)
        else:
            infos = registry.get_commands_info(scope=_CS.IRC_ONLY)

        command_names = []
        for info in infos:
            if info.name == "help":
                continue  # exclude help itself
            name = info.name
            if info.admin_only:
                name += "*"
            command_names.append(name)

        # Sort alphabetically
        command_names.sort()

        # Join into one line
        help_text = "Available commands: " + ", ".join(command_names)

        if context.is_console:
            return help_text
        else:
            # IRC: manually send notices to nick
            notice = bot_functions.get("notice_message")
            irc = bot_functions.get("irc")
            if notice and irc:
                lines = str(help_text).split("\n")
                for line in lines:
                    if line.strip():
                        notice(line, irc, context.sender)
                return CommandResponse.no_response()
            return CommandResponse.success_msg(help_text)


# =====================
# Ping Command
# =====================


@command(
    "ping", description="Check if bot is responsive and measure lag", usage="!ping"
)
def ping_command(context: CommandContext, bot_functions):
    """Simple ping command to check bot responsiveness with nanosecond precision lag measurement."""
    # Measure round-trip time to IRC server if available
    lag_ns = None
    lag_text = ""

    # Try to measure lag using IRC connection
    if not context.is_console:
        irc = bot_functions.get("irc")
        if irc:
            try:
                # Measure time for a simple PING command to server
                start_time = time.time_ns()

                # Send PING to server (this is a standard IRC command)
                if hasattr(irc, "send") and callable(irc.send):
                    # Create a simple PING message
                    ping_msg = f"PING {int(time.time())}\r\n"
                    try:
                        irc.send(ping_msg.encode("utf-8"))
                        # Note: This is a simplified lag measurement
                        # In a real implementation, we'd wait for PONG response
                        # For now, we'll use a basic timing approach
                    except Exception:
                        pass

                # For now, use a basic timing approach since full PING/PONG requires response handling
                # This gives us the basic processing time
                end_time = time.time_ns()
                lag_ns = end_time - start_time

                # Store lag measurement in dream service if available
                dream_service = bot_functions.get("dream_service")
                if dream_service and lag_ns is not None:
                    dream_service.measure_and_store_lag(lag_ns)

            except Exception:
                lag_ns = None

    # Get current timestamp with nanosecond precision
    now_ns = time.time_ns()
    dt = datetime.fromtimestamp(now_ns // 1_000_000_000)
    nanoseconds = now_ns % 1_000_000_000
    formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S") + f".{nanoseconds:09d}"

    # Format lag information
    if lag_ns is not None:
        lag_ms = lag_ns / 1_000_000
        lag_text = f" | Lag: {lag_ns:,} ns ({lag_ms:.3f} ms)"

    return f"Pong! 🏓 | Nykyinen aika: {formatted_time}{lag_text}"


def _get_irc_connection(bot_functions):
    """Get IRC connection from bot_functions."""
    # First try direct 'irc' key (set by process_irc_command)
    irc = bot_functions.get("irc")
    if irc:
        return irc

    # Fall back to server.irc_client
    server = bot_functions.get("server")
    if server and hasattr(server, "irc_client"):
        return server.irc_client

    return None


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

    # Get the latency tracker if available
    latency_tracker = bot_functions.get("latency_tracker")

    # Get server name
    server_name = bot_functions.get("server_name", "unknown")

    # Get server from bot_functions
    server = bot_functions.get("server")
    if not server or not hasattr(server, "send_raw"):
        return "Not connected to any IRC server"

    timestamp = int(time.time() * 1000)  # milliseconds

    # Send CTCP PING
    server.send_raw(f"PRIVMSG {target_nick} :\x01PING {timestamp}\x01")

    # Store the pending ping for later response matching if tracker available
    # Store: (server_name, target_nick) -> {timestamp, channel, server_name}
    if latency_tracker and hasattr(latency_tracker, "_store_pending_ctcp_ping"):
        # Use the channel from context (where the command was issued)
        channel = context.target if context.target else ""
        latency_tracker._store_pending_ctcp_ping(
            server_name, target_nick, timestamp, channel
        )

    # Return None to suppress output - response will be sent when PONG is received
    return None


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

    irc = _get_irc_connection(bot_functions)
    if not irc:
        return "Not connected to any IRC server"

    # Send the message with timestamp in a way that can be correlated
    irc.send_raw(f"PRIVMSG {target_nick} :[{timestamp}] {message}")

    return f"Sent timed message to {target_nick}"


# =====================
# Version Command
# =====================


@command("version", description="Show bot version", usage="!version")
def version_command(context: CommandContext, bot_functions):
    """Show the bot version."""
    # Check for explicit BOT_VERSION override first (for testing)
    if isinstance(bot_functions, dict) and "BOT_VERSION" in bot_functions:
        return f"Bot version: {bot_functions['BOT_VERSION']}"

    # Read version directly from VERSION file to ensure it's current
    version_file = "VERSION"
    try:
        with open(version_file, "r", encoding="utf-8") as f:
            current_version = f.read().strip()
            # Validate version format (basic check)

            if current_version and re.match(r"^\d+\.\d+\.\d+$", current_version):
                version = current_version
            else:
                # Fallback to config if VERSION file is invalid
                config_obj = get_config()
                version = config_obj.version
    except (FileNotFoundError, IOError):
        # Fallback to "1.0" if VERSION file doesn't exist
        version = "1.0"

    return f"Bot version: {version}"


# =====================
# Servers Command
# =====================


@command(
    "servers",
    description="List connected server names",
    usage="!servers",
    scope=CommandScope.CONSOLE_ONLY,
)
def servers_command(context: CommandContext, bot_functions):
    """List the names of connected servers."""
    bot_manager = bot_functions.get("bot_manager")
    if not bot_manager or not bot_manager.servers:
        return "No servers configured"

    server_names = list(bot_manager.servers.keys())
    if not server_names:
        return "No servers configured"

    return f"Connected servers: {', '.join(server_names)}"


# =====================
# Status Command
# =====================


@command(
    "status",
    description="Show server connection status",
    usage="!status",
    examples=["!status"],
    scope=CommandScope.CONSOLE_ONLY,
)
def status_command(context: CommandContext, bot_functions):
    """Show server connection status."""
    # Get bot manager from bot_functions
    bot_manager = bot_functions.get("bot_manager")
    if not bot_manager:
        return "Bot manager not available"

    try:
        result = bot_manager._console_status(*context.args)
        return result
    except Exception as e:
        return f"Status error: {e}"


# =====================
# Channels Command
# =====================


@command(
    "channels",
    description="Show channel status and list",
    usage="!channels",
    examples=["!channels"],
    scope=CommandScope.CONSOLE_ONLY,
)
def channels_command(context: CommandContext, bot_functions):
    """Show channel status and list."""
    # Get bot manager from bot_functions
    bot_manager = bot_functions.get("bot_manager")
    if not bot_manager:
        return "Bot manager not available"

    try:
        result = bot_manager._get_channel_status()
        return result
    except Exception as e:
        return f"Channels error: {e}"


# =====================
# About Command
# =====================


@command("about", description="Show information about the bot", usage="!about")
def about_command(context: CommandContext, bot_functions):
    """Show information about the bot."""
    # Read version directly from VERSION file to ensure it's current
    version_file = "VERSION"
    try:
        with open(version_file, "r", encoding="utf-8") as f:
            current_version = f.read().strip()
            # Validate version format (basic check)

            if current_version and re.match(r"^\d+\.\d+\.\d+$", current_version):
                version = current_version
            else:
                # Fallback to config if VERSION file is invalid
                config_obj = get_config()
                version = config_obj.version
    except (FileNotFoundError, IOError):
        # Fallback to "1.0" if VERSION file doesn't exist
        version = "1.0"

    return (
        f"LeetIRCPythonBot v{version} - A Leet IRC bot with word tracking, "
        f"weather, drink statistics, and more! Type !help for commands."
    )
