"""
Basic Commands Module

Contains core/basic commands extracted from commands.py.
"""

import os
import random
import re
import time
import urllib.request
from datetime import datetime

from command_registry import (
    CommandContext,
    CommandResponse,
    CommandScope,
    command,
)
from config import get_config

# =====================
# Basic commands section
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


@command("ping", description="Check if bot is responsive", usage="!ping")
def ping_command(context: CommandContext, bot_functions):
    """Simple ping command to check bot responsiveness."""
    return "Pong! 🏓"


@command(
    "matka", description="Show travel time and distance", usage="!matka <from> | <to>"
)
def driving_distance_osrm(context: CommandContext, bot_functions):
    """
    Laskee ajomatkan pituuden ja keston OSRM:n avulla kahden kaupungin välillä.
    """
    import requests

    def get_coordinates(city_name):
        """Hakee kaupungin koordinaatit (lon, lat) Nominatim-palvelusta."""
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": city_name, "format": "json", "limit": 1}
        response = requests.get(
            url, params=params, headers={"User-Agent": "matkalaskuri"}
        )
        if response.status_code == 200 and response.json():
            result = response.json()[0]
            lon, lat = float(result["lon"]), float(result["lat"])
            # Ota viimeinen osa display_name:sta → "Suomi / Finland"
            display_name = result.get("display_name", "")
            parts = [p.strip() for p in display_name.split(",")]
            country = parts[-1] if parts else "Tuntematon maa"
            return lon, lat, country
        else:
            raise Exception(f"Koordinaatteja ei löytynyt kaupungille: {city_name}")

    text = context.args_text.strip()

    # Jos lainausmerkit käytössä → poimitaan niiden sisältö
    if '"' in text:
        parts = []
        buf = ""
        in_quotes = False
        for ch in text:
            if ch == '"':
                if in_quotes:
                    parts.append(buf.strip())
                    buf = ""
                    in_quotes = False
                else:
                    in_quotes = True
            else:
                if in_quotes:
                    buf += ch
        args = parts
    else:
        # Muuten pilkotaan välilyönneillä
        args = text.split()

    if len(args) != 2:
        return "Anna kaupungit muodossa: !matka <kaupunki1> <kaupunki2> tai lainausmerkeissä jos nimi sisältää välilyöntejä"

    origin_city, destination_city = args

    origin_lon, origin_lat, origin_country = get_coordinates(origin_city)
    dest_lon, dest_lat, dest_country = get_coordinates(destination_city)

    # OSRM-kutsu
    url = (
        f"http://router.project-osrm.org/route/v1/driving/"
        f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}?overview=false"
    )
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        route = data["routes"][0]
        distance_km = route["distance"] / 1000  # metreistä kilometreiksi
        duration_min = route["duration"] / 60  # sekunneista minuuteiksi
        origin_city = origin_city.title()
        destination_city = destination_city.title()
        origin_country = origin_country.title()
        dest_country = dest_country.title()
        return (
            f"{origin_city}, {origin_country} → {destination_city}, {dest_country} : "
            f"Matka: {distance_km:.1f} km, "
            f"Ajoaika: {duration_min/60:.1f} h"
        )
    else:
        raise Exception(f"Virhe haettaessa reittiä: {response.status_code}")


@command("np", description="Show name day", usage="!np [päivä|nimi]")
def np_command(context: CommandContext, bot_functions):
    """Show name day for today, a given date, or search by name using nimipaivat.json data file."""
    import json
    import os
    import re
    from datetime import date, datetime

    base_dir = os.path.dirname(os.path.dirname(__file__))  # projektin juuri
    json_path = os.path.join(base_dir, "data", "nimipaivat.json")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    args = getattr(context, "args", [])
    query = " ".join(args).strip() if args else ""

    def format_entry(key, entry):
        dt = datetime.strptime(key, "%Y-%m-%d")
        msg_parts = [f"{dt.day}.{dt.month}.{dt.year}:"]
        if entry.get("official"):
            msg_parts.append("Viralliset: " + ", ".join(entry["official"]))
        if entry.get("unofficial"):
            msg_parts.append("Epäviralliset: " + ", ".join(entry["unofficial"]))
        if entry.get("dogs"):
            msg_parts.append("Koirat: " + ", ".join(entry["dogs"]))
        if entry.get("cats"):
            msg_parts.append("Kissat: " + ", ".join(entry["cats"]))
        return " | ".join(msg_parts)

    # 1) Ei parametreja → näytä tänään
    if not query:
        today = date.today()
        key_suffix = f"-{today.month:02d}-{today.day:02d}"
        key = next((k for k in data.keys() if k.endswith(key_suffix)), None)
        if key:
            return "Nimipäivät tänään " + format_entry(key, data[key])
        else:
            return (
                f"Tälle päivälle ({today.day}.{today.month}.) ei löytynyt nimipäiviä."
            )

    # 2) Päiväparametri tukee: 1.2, 1.2., 01.02, 01.02., 1.2.25, 01.02.2025
    date_match = re.fullmatch(r"(\d{1,2})\.(\d{1,2})(?:\.(\d{2}|\d{4}))?\.?$", query)
    if date_match:
        d, m, _ = date_match.groups()
        day = int(d)
        month = int(m)
        key_suffix = f"-{month:02d}-{day:02d}"
        matches = [k for k in data.keys() if k.endswith(key_suffix)]
        if matches:
            return f"Nimipäivät {day}.{month}: " + " || ".join(
                format_entry(k, data[k]) for k in matches
            )
        else:
            return f"Päivälle {day}.{month}. ei löytynyt nimipäiviä."

    # Apufunktio rivinvaihtojen lisäämiseen
    def wrap_message(msg, limit=459):
        result = []
        current = 0
        while current < len(msg):
            # Jos jäljellä oleva pituus on pienempi kuin limit, lisää loppu
            if len(msg) - current <= limit:
                result.append(msg[current:])
                break
            # Etsi seuraava välilyönti tai pilkku limitin jälkeen
            cut = msg.rfind(" ", current, current + limit)
            cut_comma = msg.rfind(",", current, current + limit)
            cut = max(cut, cut_comma)
            if cut == -1 or cut <= current:
                # fallback: katkaise suoraan limitin kohdalla
                cut = current + limit
            result.append(msg[current : cut + 1].strip())  # noqa: E203
            current = cut + 1
        return "\n".join(result)

    # 3) Nimihaku → palautetaan kaikki päivät joissa nimi esiintyy
    name = query.lower()
    results = []

    for k, v in data.items():
        all_names = (
            v.get("official", [])
            + v.get("unofficial", [])
            + v.get("dogs", [])
            + v.get("cats", [])
        )
        if any(name == n.lower() for n in all_names):
            results.append(format_entry(k, v))

    if results:
        msg = f"Nimi '{query.title()}' löytyy seuraavilta päiviltä: " + " || ".join(
            results
        )
        return wrap_message(msg, 445)
    else:
        return f"Nimelle '{query.title()}' ei löytynyt nimipäiviä."


@command(
    "quote",
    description="Display a random quote, search for quotes, or add new quotes",
    usage="!quote [search_text] or !quote add <quote_text>",
    examples=["!quote", "!quote tunnuslauseemme on", "!quote add This is a new quote"],
)
def quote_command(context: CommandContext, bot_functions):
    """Display a random quote from configured source (file or URL), search for a specific quote, or add a new quote."""
    config_obj = get_config()

    # Get quotes source from environment, default to data/quotes.txt
    quotes_source = getattr(config_obj, "quotes_source", "data/quotes.txt")

    # Make sure we have an absolute path for file operations
    if not os.path.isabs(quotes_source):
        # Make relative paths resolve from project root
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        quotes_source = os.path.join(project_root, quotes_source)

    try:
        # Check if this is an "add" command
        if context.args and context.args[0].lower() == "add":
            # Add a new quote
            if len(context.args) < 2:
                return "Usage: !quote add <quote_text>"

            quote_text = " ".join(context.args[1:]).strip()
            if not quote_text:
                return "Quote text cannot be empty"

            try:
                # Ensure the directory exists
                os.makedirs(os.path.dirname(quotes_source), exist_ok=True)

                # Append the quote to the file
                with open(quotes_source, "a", encoding="utf-8") as f:
                    f.write(quote_text + "\n")

                return f'✅ Quote added: "{quote_text}"'
            except Exception as e:
                return f"Error adding quote: {e}"

        # Handle reading/displaying quotes
        lines = []

        if quotes_source.startswith("http://") or quotes_source.startswith("https://"):
            # Handle URL source
            try:
                with urllib.request.urlopen(quotes_source) as response:
                    content = response.read().decode("utf-8")
                    lines = [
                        line.strip() for line in content.splitlines() if line.strip()
                    ]
            except Exception as e:
                return f"Error fetching quotes from URL: {e}"
        else:
            # Handle file source
            if not os.path.exists(quotes_source):
                return "Quotes file not found."

            try:
                with open(quotes_source, "r", encoding="utf-8") as f:
                    lines = [line.strip() for line in f if line.strip()]
            except Exception as e:
                return f"Error reading quotes file: {e}"

        if not lines:
            return "No quotes available"

        # Check if search text is provided
        search_text = context.args_text.strip() if context.args_text else ""

        if search_text:
            # Search for quotes containing the search text (case-insensitive)
            matching_quotes = [
                line for line in lines if search_text.lower() in line.lower()
            ]

            if not matching_quotes:
                return f"No quotes found containing '{search_text}'"

            # Return the first matching quote
            quote = matching_quotes[0]
        else:
            # Select random quote
            quote = random.choice(lines)

        # Remove line numbers if present (format: "123|quote text")
        if "|" in quote and quote.split("|")[0].isdigit():
            quote = "|".join(quote.split("|")[1:])

        return quote

    except Exception as e:
        return f"Error with quote command: {e}"


@command(
    "connect",
    description="Connect to IRC servers",
    usage="!connect [server_name host [port] [channels] [tls]]",
    examples=["!connect", "!connect myserver irc.example.com 6667 #general,#random"],
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


@command(
    "disconnect",
    description="Disconnect from IRC servers",
    usage="!disconnect [server_names...]",
    examples=["!disconnect", "!disconnect server1 server2"],
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


@command(
    "status",
    description="Show server connection status",
    usage="!status",
    examples=["!status"],
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


@command(
    "channels",
    description="Show channel status and list",
    usage="!channels",
    examples=["!channels"],
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


@command("about", description="Show information about the bot", usage="!about")
def about_command(context: CommandContext, bot_functions):
    """Show information about the bot."""
    config_obj = get_config()
    return (
        f"LeetIRCPythonBot v{config_obj.version} - A Leet IRC bot with word tracking, "
        f"weather, drink statistics, and more! Type !help for commands."
    )


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

    # If quit message provided, set it
    if context.args:
        quit_message = " ".join(context.args)
        set_quit_message = bot_functions.get("set_quit_message")
        if set_quit_message:
            set_quit_message(quit_message)

    # Try to get the stop event from bot functions and trigger it
    stop_event = bot_functions.get("stop_event")
    if stop_event:
        import logger

        logger.info(f"{context.server_name} !{context.command} command received")
        quit_message = (
            " ".join(context.args) if context.args else "default quit message"
        )
        logger.log(
            f"🛑 Shutting down bot with quit message: '{quit_message}'",
            "INFO",
            fallback_text=f"[STOP] Shutting down bot with quit message: '{quit_message}'",
        )
        stop_event.set()
        return "🛑 Bot shutdown initiated..."
    else:
        # Fallback - just return a quit message
        return "🛑 Exit command received - bot shutting down"
