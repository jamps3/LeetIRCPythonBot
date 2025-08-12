"""
Basic IRC Bot Commands

This module contains basic utility commands like help, time, echo, etc.
"""

import time

# Note: utils imports are not needed for basic commands
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

    # If specific command requested, return its detailed help (private on IRC)
    if context.args:
        command_name = context.args[0]
        help_text = registry.generate_help(specific_command=command_name)
        if context.is_console:
            return CommandResponse.success_msg(help_text)
        # IRC: send privately to the caller (nick)
        notice = bot_functions.get("notice_message")
        irc = bot_functions.get("irc")
        to_target = context.sender or context.target
        if notice and irc:
            for line in str(help_text).split("\n"):
                if line.strip():
                    notice(line, irc, to_target)
            return CommandResponse.no_response()
        return CommandResponse.success_msg(help_text)

    # Build command list depending on context. From IRC, show only IRC_ONLY.
    if context.is_console:
        infos = registry.get_commands_info(
            scope=_CS.CONSOLE_ONLY
        ) + registry.get_commands_info(scope=_CS.BOTH)
    else:
        infos = registry.get_commands_info(scope=_CS.IRC_ONLY)

    by_name = {}
    for info in infos:
        if info.name == "help":
            continue  # exclude help itself
        by_name[info.name] = info

    # Partition into groups
    tama_names = {"tamagotchi", "feed", "pet"}
    regular = [
        i for i in by_name.values() if not i.admin_only and i.name not in tama_names
    ]
    tamas = [i for i in by_name.values() if not i.admin_only and i.name in tama_names]
    admins = [i for i in by_name.values() if i.admin_only]

    # Sort alphabetically within groups
    regular.sort(key=lambda x: x.name)
    tamas.sort(key=lambda x: x.name)
    admins.sort(key=lambda x: x.name)

    # Format lines
    lines = ["Available commands:"]

    def fmt(info):
        line = info.name
        if info.admin_only:
            line += "*"
        if info.description:
            line += f" - {info.description}"
        return line

    lines.extend(fmt(i) for i in regular)
    if tamas:
        lines.extend(fmt(i) for i in tamas)
    if admins:
        lines.extend(fmt(i) for i in admins)
        lines.append("")
        lines.append("* Admin command (requires password)")

    help_text = "\n".join(lines)

    if context.is_console:
        return CommandResponse.success_msg(help_text)
    else:
        # IRC: send privately to the caller (nick)
        notice = bot_functions.get("notice_message")
        irc = bot_functions.get("irc")
        to_target = context.sender or context.target
        if notice and irc:
            for line in lines:
                if line.strip():
                    notice(line, irc, to_target)
            return CommandResponse.no_response()
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
    # Prefer a BOT_VERSION provided by the caller's context (e.g., console tests),
    # falling back to configured version.
    version = (
        bot_functions.get("BOT_VERSION", config.version)
        if isinstance(bot_functions, dict)
        else config.version
    )
    return f"Bot version: {version}"


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

        # Determine IRC/server context if available (for IRC responses)
        irc_ctx = bot_functions.get("irc") if not context.is_console else None
        # Call the weather service
        send_weather(irc_ctx, context.target, location)
        return CommandResponse.no_response()  # Weather service handles the output
    else:
        return "Weather service not available"


@command(
    "solarwind",
    description="Get solar wind information from NOAA SWPC",
    usage="!solarwind",
    examples=["!solarwind"],
)
def solarwind_command(context: CommandContext, bot_functions):
    """Get current solar wind information."""
    try:
        from services.solarwind_service import get_solar_wind_info

        return get_solar_wind_info()
    except Exception as e:
        return f"❌ Solar wind error: {str(e)}"


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


@command(
    "sahko",
    aliases=["sähkö"],
    description="Get electricity price information",
    usage="!sahko [tänään|huomenna] [tunti]",
    examples=["!sahko", "!sahko huomenna", "!sahko tänään 15"],
)
def electricity_command(context: CommandContext, bot_functions):
    """Get electricity price information."""
    send_electricity_price = bot_functions.get("send_electricity_price")
    if send_electricity_price:
        # Reconstruct the command parts from context
        command_parts = [context.command]
        if context.args_text:
            command_parts.extend(context.args_text.split())

        # Determine IRC/server context if available (for IRC responses)
        irc_ctx = bot_functions.get("irc") if not context.is_console else None
        send_electricity_price(irc_ctx, context.target, command_parts)
        return CommandResponse.no_response()  # Service handles the output
    else:
        return "Electricity price service not available"


@command(
    "euribor",
    description="Get current 12-month Euribor rate",
    usage="!euribor",
    examples=["!euribor"],
)
def euribor_command(context: CommandContext, bot_functions):
    """Get current 12-month Euribor rate from Suomen Pankki."""
    import platform
    import xml.etree.ElementTree as ElementTree
    from datetime import datetime

    import requests

    try:
        # XML data URL from Suomen Pankki
        url = "https://reports.suomenpankki.fi/WebForms/ReportViewerPage.aspx?report=/tilastot/markkina-_ja_hallinnolliset_korot/euribor_korot_today_xml_en&output=xml"
        response = requests.get(url)
        if response.status_code == 200:
            root = ElementTree.fromstring(response.content)
            ns = {"ns": "euribor_korot_today_xml_en"}
            period = root.find(".//ns:period", namespaces=ns)
            if period is not None:
                date_str = period.attrib.get("value")
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                if platform.system() == "Windows":
                    formatted_date = date_obj.strftime("%#d.%#m.%y")
                else:
                    formatted_date = date_obj.strftime("%-d.%-m.%y")
                rates = period.findall(".//ns:rate", namespaces=ns)
                for rate in rates:
                    if rate.attrib.get("name") == "12 month (act/360)":
                        euribor_12m = rate.find("./ns:intr", namespaces=ns)
                        if euribor_12m is not None:
                            return f"{formatted_date} 12kk Euribor: {euribor_12m.attrib['value']}%"
                        else:
                            return "Interest rate value not found."
                else:
                    return "12-month Euribor rate not found."
            else:
                return "No period data found in XML."
        else:
            return (
                f"Failed to retrieve XML data. HTTP Status Code: {response.status_code}"
            )
    except Exception as e:
        return f"Error fetching Euribor rate: {str(e)}"


@command(
    "crypto",
    description="Get cryptocurrency prices",
    usage="!crypto [coin] [currency]",
    examples=["!crypto", "!crypto btc", "!crypto eth eur"],
)
def crypto_command(context: CommandContext, bot_functions):
    """Get cryptocurrency price information."""
    get_crypto_price = bot_functions.get("get_crypto_price")
    if not get_crypto_price:
        return "Crypto price service not available"

    if len(context.args) >= 1:
        coin = context.args[0].lower()
        currency = context.args[1] if len(context.args) > 1 else "eur"
        price = get_crypto_price(coin, currency)
        return f"💸 {coin.capitalize()}: {price} {currency.upper()}"
    else:
        # Show top 3 coins by default
        top_coins = ["bitcoin", "ethereum", "tether"]
        prices = {coin: get_crypto_price(coin, "eur") for coin in top_coins}
        return " | ".join(
            [f"{coin.capitalize()}: {prices[coin]} €" for coin in top_coins]
        )


@command(
    "url",
    description="Fetch and display title from URL",
    usage="!url <url>",
    examples=["!url https://example.com"],
    requires_args=True,
)
def url_command(context: CommandContext, bot_functions):
    """Fetch title from a URL."""
    fetch_title = bot_functions.get("fetch_title")
    if fetch_title:
        # Extract URL from arguments
        url = context.args_text.strip()
        fetch_title(None, context.target, url)
        return CommandResponse.no_response()  # Service handles the output
    else:
        return "URL title fetching service not available"


@command(
    "leetwinners",
    description="Show top leet winners by category",
    usage="!leetwinners",
    examples=["!leetwinners"],
)
def leetwinners_command(context: CommandContext, bot_functions):
    """Show top-3 leet winners by category (ensimmäinen, multileet, viimeinen)."""
    load_leet_winners = bot_functions.get("load_leet_winners")
    if not load_leet_winners:
        return "Leet winners service not available"

    # Expected structure: { winner: {category: count, ...}, ... }
    data = load_leet_winners() or {}

    # Aggregate counts per category -> list of (winner, count)
    per_category = {}
    for winner, categories in data.items():
        for cat, count in categories.items():
            if cat not in per_category:
                per_category[cat] = []
            per_category[cat].append((winner, count))

    # Sort each category desc by count, then by winner name for stability
    lines = []
    for cat, entries in per_category.items():
        top = sorted(entries, key=lambda x: (-x[1], x[0]))[:3]
        if top:
            formatted = ", ".join(f"{w} [{c}]" for w, c in top)
            lines.append(f"{cat}: {formatted}")

    winners_text = "; ".join(lines)
    return (
        f"𝓛𝓮𝓮𝓽𝔀𝓲𝓷𝓷𝓮𝓻𝓼: {winners_text}"
        if winners_text
        else "No 𝓛𝓮𝓮𝓽𝔀𝓲𝓷𝓷𝓮𝓻𝓼 recorded yet."
    )


# Auto-register when imported
register_basic_commands()
