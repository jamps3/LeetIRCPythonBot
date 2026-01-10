"""
Unified Commands Module for LeetIRCPythonBot
Admin commands in commands_admin.py
"""

import json
import os
import random
import re
import threading
import time
import urllib.request
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import bot_manager

# Import service commands module
import commands_services  # noqa: F401
import logger
from command_registry import (
    CommandContext,
    CommandResponse,
    CommandScope,
    CommandType,
    command,
)

# Re-export service commands for backward compatibility with tests
from commands_services import (
    alko_command,
    crypto_command,
    electricity_command,
    euribor_command,
    leetwinners_command,
    trains_command,
    weather_command,
)
from config import get_config

# Word tracking system (extended features)
from tamagotchi import TamagotchiBot
from word_tracking import DataManager, DrinkTracker, GeneralWords

# Initialize word tracking system (shared singletons)
_data_manager = DataManager()
_drink_tracker = DrinkTracker(_data_manager)
_general_words = GeneralWords(_data_manager)
_tamagotchi_bot = TamagotchiBot(_data_manager)

# Backwards-compatibility aliases for tests and external modules that monkeypatch
# These names match those previously exposed by commands_extended.py
data_manager = _data_manager
drink_tracker = _drink_tracker
general_words = _general_words
tamagotchi_bot = _tamagotchi_bot


# =====================
# Helper functions
# =====================


def load_otiedote_json():
    JSON_FILE = os.path.join("data", os.getenv("OTIEDOTE_FILE", "otiedote.json"))
    if not os.path.exists(JSON_FILE):
        print(f"Otiedote JSON file not found: {JSON_FILE}")
        return []
    with open(JSON_FILE, "r", encoding="utf8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def trim_with_dots(text: str, limit: int = 400) -> str:
    return text if len(text) <= 400 else text[:400].rsplit(" ", 1)[0] + "..."


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
            import re

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
    now_ns = time.time_ns()
    dt = datetime.fromtimestamp(now_ns // 1_000_000_000)
    nanoseconds = now_ns % 1_000_000_000
    formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S") + f".{nanoseconds:09d}"
    return f"Pong! 🏓 | Nykyinen aika: {formatted_time}"


@command(
    "kolikko",
    description="Flip a coin",
    usage="!kolikko [kruuna|klaava]",
    examples=["!kolikko", "!kolikko kruuna"],
)
def kolikko_command(context: CommandContext, bot_functions):
    """Flip a coin and optionally check if user guessed correctly."""
    result = random.choice(["Kruuna", "Klaava"])

    if context.args:
        guess = context.args[0].lower()
        if guess in ["kruuna", "klaava"]:
            # Capitalize first letter for comparison
            normalized_result = result.lower()
            if guess == normalized_result:
                return f"{result}. Voitit!"
            else:
                return f"{result}. Hävisit."
        else:
            return "Virheellinen valinta. Käytä: kruuna tai klaava"
    else:
        return result


@command(
    "noppa",
    description="Roll dice",
    usage="!noppa <NdS>",
    examples=["!noppa 2d6", "!noppa 1d20"],
    requires_args=True,
)
def noppa_command(context: CommandContext, bot_functions):
    """Roll dice in NdS format (e.g., 2d6 for two six-sided dice)."""
    if not context.args:
        return "Käyttö: !noppa <NdS> (esim. 2d6)"

    dice_spec = context.args[0].lower()
    import re

    match = re.match(r"^(\d+)d(\d+)$", dice_spec)
    if not match:
        return "Virheellinen noppaformaatti. Käytä: NdS (esim. 2d6)"

    num_dice = int(match.group(1))
    sides = int(match.group(2))

    if num_dice < 1 or num_dice > 20:
        return "Noppien määrä pitää olla 1-20 välillä."
    if sides < 2 or sides > 100:
        return "Sivujen määrä pitää olla 2-100 välillä."

    rolls = [random.randint(1, sides) for _ in range(num_dice)]
    total = sum(rolls)

    if num_dice == 1:
        return f"{context.sender} heitti: {rolls[0]}"
    else:
        roll_str = " + ".join(str(r) for r in rolls)
        return f"{context.sender} heitti: {roll_str} = {total}"


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


@command("about", description="Show information about the bot", usage="!about")
def about_command(context: CommandContext, bot_functions):
    """Show information about the bot."""
    # Read version directly from VERSION file to ensure it's current
    version_file = "VERSION"
    try:
        with open(version_file, "r", encoding="utf-8") as f:
            current_version = f.read().strip()
            # Validate version format (basic check)
            import re

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


# ========================
# Extended commands section
# ========================


@command(
    name="sana",
    command_type=CommandType.PUBLIC,
    description="Search word statistics",
    usage="!sana <sana> [limit]",
    admin_only=False,
)
def command_sana(context, bot_functions):
    if context.args:
        # Parse optional limit as last numeric arg
        args = context.args[:]
        limit = 10
        if args and isinstance(args[-1], str) and args[-1].isdigit():
            try:
                limit = max(1, min(50, int(args[-1])))
            except Exception:
                limit = 10
            args = args[:-1]

        search_word = " ".join(args).strip().lower()
        if not search_word:
            return "Käytä komentoa: !sana <sana> [limit]"

        results = _general_words.search_word(search_word)

        # Determine current server (fallback to 'console' if missing)
        current_server = getattr(context, "server_name", "") or "console"

        if results["total_occurrences"] > 0:
            # Prefer users for the current server; if none, aggregate across all servers
            server_data = results.get("servers", {}).get(current_server, {})
            users = server_data.get("users", [])

            if not users:
                # Fallback: combine users from all servers
                all_users = []
                for sdata in results.get("servers", {}).values():
                    all_users.extend(sdata.get("users", []))
                # Aggregate counts by nick
                agg = {}
                for u in all_users:
                    nick = u.get("nick")
                    if not nick:
                        continue
                    agg[nick] = agg.get(nick, 0) + int(u.get("count", 0))
                users = [{"nick": n, "count": c} for n, c in agg.items()]

            if users:
                # Sort by count desc and apply limit
                users_sorted = sorted(
                    users, key=lambda u: u.get("count", 0), reverse=True
                )
                users_sorted = users_sorted[:limit]
                users_text = ", ".join(
                    f"{u['nick']}: {u['count']}" for u in users_sorted
                )
                return f"Sana '{search_word}' on sanottu: {users_text}"
            else:
                return f"Kukaan ei ole sanonut sanaa '{search_word}' vielä."
        else:
            return f"Kukaan ei ole sanonut sanaa '{search_word}' vielä."
    else:
        return "Käytä komentoa: !sana <sana> [limit]"


@command(
    name="tilaa",
    command_type=CommandType.PUBLIC,
    description="Handle subscription commands",
    usage="!tilaa varoitukset|onnettomuustiedotteet|list <kanava>",
    admin_only=False,
)
def command_tilaa(context, bot_functions):
    topic = context.args[0].lower() if context.args else None
    if not topic:
        return "⚠ Käyttö: !tilaa varoitukset|onnettomuustiedotteet|list <kanava>"

    if not bot_functions or "subscriptions" not in bot_functions:
        return "Subscription service is not available."

    subscriptions = bot_functions["subscriptions"]

    if topic == "list":
        result = subscriptions.format_all_subscriptions()
        return CommandResponse.success_msg(result)

    elif topic in ["varoitukset", "onnettomuustiedotteet"]:
        # Determine subscriber (channel/user)
        if len(context.args) >= 2:
            subscriber = context.args[1]  # Explicit override
        elif context.target and context.target.startswith("#"):
            subscriber = context.target
        elif context.sender:
            subscriber = context.sender
        else:
            subscriber = "console"

        # Use server_name from context (fallback to 'console')
        server_name = getattr(context, "server_name", "") or "console"
        result = subscriptions.toggle_subscription(subscriber, server_name, topic)
        return result
    else:
        return "⚠ Tuntematon tilaustyyppi. Käytä: varoitukset, onnettomuustiedotteet tai list"


@command(
    name="topwords",
    command_type=CommandType.PUBLIC,
    description="Show top words used",
    usage="!topwords [nick] [limit]",
    admin_only=False,
)
def command_topwords(context, bot_functions):
    # Default limit
    limit = 10

    args = context.args or []

    # If last argument is an integer, treat it as limit
    if args and isinstance(args[-1], str) and args[-1].isdigit():
        try:
            limit = max(1, min(50, int(args[-1])))
        except Exception:
            limit = 10
        args = args[:-1]  # remove limit token from args

    if args:  # User-specific top words
        nick = " ".join(args).strip()
        for server_name in data_manager.get_all_servers():
            user_stats = general_words.get_user_stats(server_name, nick)
            if user_stats.get("total_words", 0) > 0:
                top_words = general_words.get_user_top_words(server_name, nick, limit)
                word_list = ", ".join(
                    f"{word['word']}: {word['count']}" for word in top_words
                )
                return f"{nick}@{server_name}: {word_list}"
        return f"Käyttäjää '{nick}' ei löydy."
    else:  # Global top words across servers
        global_word_counts = {}
        for server_name in data_manager.get_all_servers():
            server_stats = general_words.get_server_stats(server_name)
            for word, count in server_stats.get("top_words", []):
                global_word_counts[word] = global_word_counts.get(word, 0) + count

        if global_word_counts:
            top_words = sorted(
                global_word_counts.items(), key=lambda x: x[1], reverse=True
            )[:limit]
            word_list = ", ".join(f"{word}: {count}" for word, count in top_words)
            return f"Käytetyimmät sanat (globaali): {word_list}"
        else:
            return "Ei vielä tarpeeksi dataa sanatilastoille."


@command(
    name="leaderboard",
    command_type=CommandType.PUBLIC,
    description="Show server-specific leaderboard",
    usage="!leaderboard [limit]",
    admin_only=False,
)
def command_leaderboard(context, bot_functions):
    # Default limit
    limit = 10

    args = context.args or []
    if args and isinstance(args[-1], str) and args[-1].isdigit():
        try:
            limit = max(1, min(50, int(args[-1])))
        except Exception:
            limit = 10
        args = args[:-1]  # remove limit token from args

    # Determine current server (works for console and IRC)
    server_name = (
        bot_functions.get("server_name")
        or getattr(context, "server_name", "console")
        or "console"
    )

    # Fetch leaderboard only for the current server
    entries = general_words.get_leaderboard(server_name, 100) or []

    if entries:
        # Sort by total_words desc, take top N based on limit, and hide server from output
        top_users = sorted(
            entries, key=lambda u: u.get("total_words", 0), reverse=True
        )[:limit]
        leaderboard_msg = ", ".join(
            f"{u['nick']}: {u['total_words']}" for u in top_users
        )
        return f"Aktiivisimmat käyttäjät: {leaderboard_msg}"
    else:
        return "Ei vielä tarpeeksi dataa leaderboardille."


@command(
    name="drinkword",
    command_type=CommandType.PUBLIC,
    description="Näytä tilastot tietylle juomasanalle (esim. krak)",
    usage="!drinkword <juomasana>",
    admin_only=False,
)
def command_drinkword(context, bot_functions):
    drink = bot_functions.get("drink_tracker") or _drink_tracker
    if not drink:
        return "Drink tracker ei ole käytettävissä."

    if not context.args:
        return "Käyttö: !drinkword <juomasana>"

    server_name = (
        bot_functions.get("server_name")
        or getattr(context, "server_name", "console")
        or "console"
    )
    drink_word = context.args[0].strip().lower()

    results = drink.search_drink_word(drink_word, server_filter=server_name)
    total = results.get("total_occurrences", 0)
    if total <= 0:
        return f"Ei osumia sanalle '{drink_word}'."

    users = results.get("users", [])
    top = ", ".join([f"{u['nick']}:{u['total']}" for u in users[:10]]) if users else ""
    return f"{drink_word}: {total} (top: {top})" if top else f"{drink_word}: {total}"


@command(
    name="drink",
    command_type=CommandType.PUBLIC,
    description="Hae juomia nimen perusteella (tukee *-jokeria)",
    usage="!drink <juoman nimi>",
    admin_only=False,
)
def command_drink(context, bot_functions):
    drink = bot_functions.get("drink_tracker") or _drink_tracker
    if not drink:
        return "Drink tracker ei ole käytettävissä."

    if not context.args_text:
        return "Käyttö: !drink <juoman nimi>"

    server_name = (
        bot_functions.get("server_name")
        or getattr(context, "server_name", "console")
        or "console"
    )
    query = context.args_text.strip()

    results = drink.search_specific_drink(query, server_filter=server_name)
    total = results.get("total_occurrences", 0)
    if total <= 0:
        return f"Ei osumia juomalle '{query}'."

    # Summarize by drink word and top users
    drink_words = results.get("drink_words", {})
    words_part = ", ".join(
        [
            f"{w}:{c}"
            for w, c in sorted(drink_words.items(), key=lambda x: x[1], reverse=True)[
                :5
            ]
        ]
    )
    users = results.get("users", [])
    top_users = ", ".join([f"{u['nick']}:{u['total']}" for u in users[:5]])

    details = []
    if words_part:
        details.append(words_part)
    if top_users:
        details.append(f"top: {top_users}")

    details_text = ", ".join(details)
    return f"{(', ' + details_text) if details_text else ''}"


def _get_statistics_start_date():
    """Get the earliest timestamp from drink tracking data and format as dd.mm.yyyy."""
    data = _data_manager.load_drink_data()
    earliest_timestamp = None

    # Look through all servers and users for the earliest timestamp
    if "servers" in data:
        for server_data in data["servers"].values():
            if "nicks" in server_data:
                for user_data in server_data["nicks"].values():
                    if "drink_words" in user_data:
                        for drink_data in user_data["drink_words"].values():
                            if "timestamps" in drink_data and drink_data["timestamps"]:
                                for timestamp_entry in drink_data["timestamps"]:
                                    if "time" in timestamp_entry:
                                        current_time = timestamp_entry["time"]
                                        if (
                                            earliest_timestamp is None
                                            or current_time < earliest_timestamp
                                        ):
                                            earliest_timestamp = current_time

    if earliest_timestamp:
        try:
            from datetime import datetime

            started_dt = datetime.fromisoformat(earliest_timestamp)
            return started_dt.strftime("%d.%m.%Y")
        except (ValueError, KeyError):
            return None
    return None


@command(
    name="kraks",
    command_type=CommandType.PUBLIC,
    description="Näytä krakit (juomasanat) ja niiden jakauma, tai resetoi BAC",
    usage="!kraks [reset]",
    admin_only=False,
)
def command_kraks(context, bot_functions):
    # Check for reset subcommand
    if context.args and context.args[0].lower() == "reset":
        # Get the BAC tracker
        bac_tracker = bot_functions.get("bac_tracker")
        if not bac_tracker:
            return "❌ BAC tracker not available"

        # Derive server name
        server_name = (
            bot_functions.get("server_name")
            or getattr(context, "server_name", "console")
            or "console"
        )

        nick = context.sender

        # Reset the user's BAC
        bac_tracker.reset_user_bac(server_name, nick)

        return f"✅ BAC resetoitu käyttäjälle {nick}"

    # Original kraks functionality
    # Use injected drink tracker to ensure shared persistence
    drink = bot_functions.get("drink_tracker") or _drink_tracker
    if not drink:
        return "Drink tracker ei ole käytettävissä."

    # Derive server name (works for both IRC and console)
    server_name = (
        bot_functions.get("server_name")
        or getattr(context, "server_name", "console")
        or "console"
    )

    stats = drink.get_server_stats(server_name)
    start_date = _get_statistics_start_date()

    if stats.get("total_drink_words", 0) <= 0:
        if start_date:
            return f"Ei vielä krakkauksia tallennettuna. Since {start_date}."
        else:
            return "Ei vielä krakkauksia tallennettuna."

    breakdown = drink.get_drink_word_breakdown(server_name)
    if breakdown:
        details = ", ".join(
            f"{word}: {count} [{top_user}]" for word, count, top_user in breakdown[:10]
        )
        response = f"Krakit yhteensä: {stats['total_drink_words']}, {details}"
        if start_date:
            response += f" (since {start_date})"
        return response
    else:
        top5 = ", ".join(
            [f"{nick}:{count}" for nick, count in stats.get("top_users", [])[:5]]
        )
        response = f"Krakit yhteensä: {stats['total_drink_words']}. Top 5: {top5}"
        if start_date:
            response += f" (since {start_date})"
        return response


@command(
    name="tamagotchi",
    command_type=CommandType.PUBLIC,
    description="Shows tamagotchi status",
    usage="!tamagotchi",
    admin_only=False,
)
def command_tamagotchi(context, bot_functions):
    console_server = "console"
    status = _tamagotchi_bot.get_status(console_server)
    return status


@command(
    name="feed",
    command_type=CommandType.PUBLIC,
    description="Feed your Tamagotchi",
    usage="!feed <food>",
    admin_only=False,
)
def command_feed(context, bot_functions):
    food = context.args_text.strip() if context.args_text else None
    console_server = "console"
    response = _tamagotchi_bot.feed(console_server, food)
    return response


@command(
    name="pet",
    command_type=CommandType.PUBLIC,
    description="Pet your Tamagotchi",
    usage="!pet",
    admin_only=False,
)
def command_pet(context, bot_functions):
    console_server = "console"
    response = _tamagotchi_bot.pet(console_server)
    return response


@command(
    name="leets",
    command_type=CommandType.PUBLIC,
    description="Show recent leet detection history",
    usage="!leets <limit>",
    admin_only=False,
)
def command_leets(context, bot_functions):
    """Show recent leet detection history."""
    from leet_detector import create_leet_detector

    # Parse optional numeric limit from context.args
    limit = 5
    if context.args and isinstance(context.args[0], str) and context.args[0].isdigit():
        try:
            limit = max(1, int(context.args[0]))
        except Exception:
            limit = 5

    detector = create_leet_detector()
    history = detector.get_leet_history(limit=limit)

    if not history:
        return "No leet detections found."

    response_lines = ["🎉 Recent Leet Detections:"]
    for detection in history:
        try:
            date_str = datetime.fromisoformat(detection.get("datetime", "")).strftime(
                "%d.%m %H:%M:%S"
            )
        except Exception:
            date_str = ""
        user_msg = detection.get("user_message")
        user_msg_part = f' "{user_msg}"' if user_msg else ""
        response_lines.append(
            f"{detection.get('emoji', '')} {detection.get('achievement_name', '')} [{detection.get('nick', '')}] "
            f"{detection.get('timestamp', '')}{user_msg_part} ({date_str})"
        )

    return "\n".join(response_lines)


@command(
    name="schedule",
    command_type=CommandType.ADMIN,
    aliases=["leet"],
    description="Schedule a message to be sent at a specific time",
    usage="!schedule #channel HH:MM:SS<.microsecs> message",
    admin_only=True,
)
def command_schedule(context, bot_functions):
    """Schedule a message for later delivery."""
    # Use parsed args from context (as provided by the command registry)
    args = context.args
    if not args:
        return "Usage: !schedule #channel HH:MM:SS<.ns> message"

    # Parse the command format: !schedule #channel HH:MM:SS message
    # or !schedule #channel HH:MM:SS.<1..9 digits> message
    text = " ".join(args)
    if context.is_console:
        # In console, the first parameter is the server name
        match = re.match(
            r"(\S+)\s+(#\S+)\s+(\d{1,2}):(\d{1,2}):(\d{1,2})(?:\.(\d{1,9}))?\s+(.+)",
            text,
        )
    else:
        match = re.match(
            r"(#\S+)\s+(\d{1,2}):(\d{1,2}):(\d{1,2})(?:\.(\d{1,9}))?\s+(.+)", text
        )

    if not match:
        return "Invalid format! Use: !schedule #channel HH:MM:SS<.microsecs> message"

    if context.is_console:
        server_name = match.group(1)
        channel = match.group(2)
        hour = int(match.group(3))
        minute = int(match.group(4))
        second = int(match.group(5))
        frac_str = match.group(6)  # up to 9 digits (nanoseconds resolution in input)
        message = match.group(7)
    else:
        channel = match.group(1)
        hour = int(match.group(2))
        minute = int(match.group(3))
        second = int(match.group(4))
        frac_str = match.group(5)  # up to 9 digits (nanoseconds resolution in input)
        message = match.group(6)

    # Convert fractional seconds (up to 9 digits) for scheduling
    if frac_str:
        ns_str = frac_str.ljust(9, "0")[:9]  # normalize to exactly 9 digits for display
    else:
        ns_str = "000000000"

    # Validate time values
    if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
        return "Invalid time! Hour: 0-23, Minute: 0-59, Second: 0-59"

    try:
        # Get the scheduled message service
        from services.scheduled_message_service import send_scheduled_message

        # Retrieve the IRC/server object from bot_functions
        server = bot_functions.get("server")

        # If called from console, use the first parameter or if omitted get the first server
        if not server:
            server = server_name or (
                bot_manager.servers[0] if bot_manager.servers else None
            )

        if not server:
            return "❌ Server context not available for scheduling"

        # Schedule
        message_id = send_scheduled_message(
            server, channel, message, hour, minute, second, ns_str
        )

        # Show the requested time with 9-digit fractional part (as in logs)
        # Try to get server name from server object if possible
        server_name_str = (
            getattr(server, "name", None)
            or getattr(server, "server_name", None)
            or str(server)
        )
        return f"✅ Message scheduled with ID: {message_id} for {hour:02d}:{minute:02d}:{second:02d}.{ns_str} in {server_name_str} {channel}"

    except Exception as e:
        return f"❌ Error scheduling message: {str(e)}"


@command(
    name="ipfs",
    command_type=CommandType.PUBLIC,
    description="Add files to IPFS from URLs",
    usage="!ipfs add <url> or !ipfs <password> <url>",
    admin_only=False,
)
def command_ipfs(context, bot_functions):
    """Handle IPFS file operations."""
    # Use parsed args from context to avoid accidental contamination
    if not context.args:
        return "Usage: !ipfs add <url> or !ipfs <password> <url>"

    try:
        from services.ipfs_service import handle_ipfs_command

        # Reconstruct the full command exactly as user intended (post-!ipfs)
        command_text = "!ipfs " + " ".join(context.args)
        admin_password = os.getenv("ADMIN_PASSWORD")

        response = handle_ipfs_command(command_text, admin_password)
        return response

    except Exception as e:
        return f"❌ IPFS error: {str(e)}"


@command(
    "krakstats",
    description="Show personal krak statistics",
    usage="!krakstats",
    examples=["!krakstats"],
)
def krakstats_command(context: CommandContext, bot_functions):
    """Show personal krak statistics for the user."""
    # Use injected drink tracker to ensure shared persistence
    drink = bot_functions.get("drink_tracker") or _drink_tracker
    if not drink:
        return "Drink tracker ei ole käytettävissä."

    # Derive server name (works for both IRC and console)
    server_name = (
        bot_functions.get("server_name")
        or getattr(context, "server_name", "console")
        or "console"
    )

    nick = context.sender

    # Get user stats
    user_stats = drink.get_user_stats(server_name, nick)

    if user_stats.get("total_drink_words", 0) == 0:
        return f"Ei krakkauksia vielä tallennettuna käyttäjälle {nick}."

    total_kraks = user_stats["total_drink_words"]

    # Calculate recent counts
    from datetime import datetime, timedelta

    now = datetime.now()
    last_30_days = now - timedelta(days=30)
    last_week = now - timedelta(days=7)
    last_24h = now - timedelta(hours=24)

    count_30d = 0
    count_week = 0
    count_24h = 0

    # Count by drink type and time periods
    drink_type_counts = {}
    drink_type_recent = {"30d": {}, "week": {}, "24h": {}}

    for drink_word, drink_data in user_stats.get("drink_words", {}).items():
        for timestamp_entry in drink_data.get("timestamps", []):
            timestamp_str = timestamp_entry.get("time", "")
            try:
                timestamp = datetime.fromisoformat(timestamp_str)
                specific_drink = timestamp_entry.get("specific_drink", "unspecified")

                # Count by time period
                if timestamp >= last_30_days:
                    count_30d += 1
                    drink_type_recent["30d"][specific_drink] = (
                        drink_type_recent["30d"].get(specific_drink, 0) + 1
                    )
                if timestamp >= last_week:
                    count_week += 1
                    drink_type_recent["week"][specific_drink] = (
                        drink_type_recent["week"].get(specific_drink, 0) + 1
                    )
                if timestamp >= last_24h:
                    count_24h += 1
                    drink_type_recent["24h"][specific_drink] = (
                        drink_type_recent["24h"].get(specific_drink, 0) + 1
                    )

                # Count by drink type
                drink_type_counts[specific_drink] = (
                    drink_type_counts.get(specific_drink, 0) + 1
                )

            except (ValueError, KeyError):
                continue

    # Format response in compact multi-line format
    response_parts = []

    # First line: Summary stats
    response_parts.append(
        f"🐧 {nick} krak statistics: Total kraks: {total_kraks} | Last 30 days: {count_30d} | Last week: {count_week} | Last 24h: {count_24h}"
    )

    # Second line: All-time drink types
    if drink_type_counts:
        sorted_types = sorted(
            drink_type_counts.items(), key=lambda x: x[1], reverse=True
        )
        drink_type_str = " | ".join(
            f"{drink_type}: {count}" for drink_type, count in sorted_types[:5]
        )
        response_parts.append(f"Drink types: {drink_type_str}")

    # Third line: Last 24h drink types
    if drink_type_recent["24h"]:
        sorted_24h = sorted(
            drink_type_recent["24h"].items(), key=lambda x: x[1], reverse=True
        )
        drink_24h_str = " | ".join(
            f"{drink_type}: {count}" for drink_type, count in sorted_24h[:3]
        )
        response_parts.append(f"Last 24h drink types: {drink_24h_str}")

    # Fourth line: Last week drink types
    if drink_type_recent["week"]:
        sorted_week = sorted(
            drink_type_recent["week"].items(), key=lambda x: x[1], reverse=True
        )
        drink_week_str = " | ".join(
            f"{drink_type}: {count}" for drink_type, count in sorted_week[:3]
        )
        response_parts.append(f"Last week drink types: {drink_week_str}")

    # Fifth line: Last 30 days drink types
    if drink_type_recent["30d"]:
        sorted_30d = sorted(
            drink_type_recent["30d"].items(), key=lambda x: x[1], reverse=True
        )
        drink_30d_str = " | ".join(
            f"{drink_type}: {count}" for drink_type, count in sorted_30d[:3]
        )
        response_parts.append(f"Last 30 days drink types: {drink_30d_str}")

    # Send response privately to the user (not to channel)
    if context.is_console:
        return "\n".join(response_parts)
    else:
        # IRC: send as notices to the nick who asked
        notice = bot_functions.get("notice_message")
        irc = bot_functions.get("irc")
        if notice and irc:
            for line in response_parts:
                if line.strip():
                    notice(line, irc, context.sender)
            return CommandResponse.no_response()
        return CommandResponse.success_msg("\n".join(response_parts))


@command(
    "ksp",
    description="Play rock-paper-scissors (kivi-sakset-paperi)",
    usage="!ksp <kivi|sakset|paperi>",
    examples=["!ksp kivi", "!ksp sakset", "!ksp paperi"],
    requires_args=True,
)
def ksp_command(context: CommandContext, bot_functions):
    """Play rock-paper-scissors game."""
    choice = context.args[0].lower()
    valid_choices = ["kivi", "sakset", "paperi"]
    if choice not in valid_choices:
        return f"Virheellinen valinta. Käytä: {', '.join(valid_choices)}"

    # Load current game state
    current_game = _data_manager.load_ksp_state()

    def determine_winner(c1, c2):
        if c1 == c2:
            return "tasapeli"
        wins = {"kivi": "sakset", "paperi": "kivi", "sakset": "paperi"}
        if wins[c1] == c2:
            return "player1"
        return "player2"

    if current_game is None:
        # Start new game
        game_state = {"choice": choice, "sender": context.sender}
        _data_manager.save_ksp_state(game_state)
        return f"Peli aloitettu: {choice} pelaajalta {context.sender}"
    else:
        player1_sender = current_game["sender"]
        player1_choice = current_game["choice"]
        player2_sender = context.sender
        player2_choice = choice

        if player1_sender == player2_sender:
            # Same player changing choice
            game_state = {"choice": choice, "sender": context.sender}
            _data_manager.save_ksp_state(game_state)
            return f"Valinta vaihdettu: {choice} (aiempi: {player1_choice})"

        # Different player, play the game
        winner = determine_winner(player1_choice, player2_choice)
        if winner == "tasapeli":
            result = f"Tasapeli: {player1_choice} vs {player2_choice}"
        elif winner == "player1":
            result = f"{player1_sender} voitti {player2_sender}: {player1_choice} vs {player2_choice}"
        else:
            result = f"{player2_sender} voitti {player1_sender}: {player2_choice} vs {player1_choice}"

        # Reset game
        _data_manager.save_ksp_state(None)
        return result


@command(
    "kraksdebug",
    description="Configure drink word detection debugging",
    usage="!kraksdebug [#channel] or !kraksdebug (in private: toggle nick whitelist)",
    examples=["!kraksdebug #test", "!kraksdebug"],
    admin_only=False,
)
def kraksdebug_command(context: CommandContext, bot_functions):
    """Configure drink word detection debugging notifications.

    In a channel: toggles sending drink word detections to that channel.
    In private message: adds/removes your nick from the whitelist for nick notices.
    """
    # Get the data manager
    data_manager = bot_functions.get("data_manager")
    if not data_manager:
        return "❌ Data manager not available"

    # Load current kraksdebug state
    kraksdebug_config = data_manager.load_kraksdebug_state()

    if context.args:
        # Channel parameter provided (channel usage)
        channel = context.args[0]

        # Ensure channel starts with #
        if not channel.startswith("#"):
            channel = "#" + channel

        # Toggle channel in list
        if channel in kraksdebug_config["channels"]:
            kraksdebug_config["channels"].remove(channel)
            action = "removed from"
        else:
            kraksdebug_config["channels"].append(channel)
            action = "added to"

        # Save state
        data_manager.save_kraksdebug_state(kraksdebug_config)

        return f"✅ Channel {channel} {action} drink word detection notifications"
    else:
        # No parameter - different behavior based on context
        is_private = not context.target.startswith("#")

        if is_private:
            # Private message: toggle nick in whitelist
            nick = context.sender
            nicks_list = kraksdebug_config.get("nicks", [])

            if nick in nicks_list:
                nicks_list.remove(nick)
                action = "removed from"
            else:
                nicks_list.append(nick)
                action = "added to"

            kraksdebug_config["nicks"] = nicks_list
            data_manager.save_kraksdebug_state(kraksdebug_config)

            return (
                f"✅ Your nick '{nick}' {action} drink word detection notice whitelist"
            )
        else:
            # Channel message: toggle nick notices (legacy behavior)
            kraksdebug_config["nick_notices"] = not kraksdebug_config.get(
                "nick_notices", False
            )

            # Save state
            data_manager.save_kraksdebug_state(kraksdebug_config)

            status = "enabled" if kraksdebug_config["nick_notices"] else "disabled"
            return f"✅ Drink word detection notices to nicks are now {status}"


@command(
    "krak",
    description="Set BAC calculation profile or view current BAC",
    usage="!krak [weight_kg m/f | burn_rate | nickname] or !krak (view current BAC)",
    examples=["!krak 75 m", "!krak 0.15", "!krak", "!krak otheruser"],
    admin_only=False,
)
def krak_command(context: CommandContext, bot_functions):
    """Set BAC calculation profile parameters or view current BAC.

    Usage:
    - !krak weight_kg m/f : Set weight and sex for personalized BAC calculation
    - !krak burn_rate : Set custom burn rate in ‰ per hour
    - !krak nickname : View another user's BAC information
    - !krak : View current BAC information
    """
    # Get the BAC tracker
    bac_tracker = bot_functions.get("bac_tracker")
    if not bac_tracker:
        return "❌ BAC tracker not available"

    # Derive server name
    server_name = (
        bot_functions.get("server_name")
        or getattr(context, "server_name", "console")
        or "console"
    )

    # Determine the target user (default to sender)
    target_nick = context.sender

    # Check if this looks like a nickname request (single non-numeric argument)
    if context.args and len(context.args) == 1:
        potential_nick = context.args[0]
        # Check if it's not a number (would be burn rate) and not a sex indicator
        try:
            float(potential_nick)
            # It's a number, so it's burn rate - don't treat as nickname
        except ValueError:
            if potential_nick.lower() not in ["m", "f"]:
                # Not a number and not sex, so treat as nickname
                target_nick = potential_nick

    # Show BAC information
    bac_info = bac_tracker.get_user_bac(server_name, target_nick)
    profile = bac_tracker.get_user_profile(server_name, target_nick)

    # Get last drink grams from stored data
    bac_data = bac_tracker._load_bac_data()
    user_key = f"{server_name}:{target_nick}"
    user_data = bac_data.get(user_key, {})
    last_drink_grams = user_data.get("last_drink_grams")

    # Show whose BAC we're displaying if it's not the sender
    display_name = f"{target_nick}'s" if target_nick != context.sender else ""

    if bac_info["current_bac"] == 0.0 and not any(profile.values()):
        response = f"🍺 {display_name} No BAC data yet."
        # Include last drink alcohol content even when no profile
        if last_drink_grams:
            response += f" | Last: {last_drink_grams:.1f}g"
        return response

    response_parts = []

    # Show current BAC if any
    if bac_info["current_bac"] > 0.0:
        sober_time = bac_info.get("sober_time", "Unknown")
        driving_time = bac_info.get("driving_time")
        response_parts.append(
            f"🍺 {display_name} Promilles: {bac_info['current_bac']:.2f}‰"
        )

        # Include last drink alcohol content if available
        if last_drink_grams:
            response_parts.append(f"Last: {last_drink_grams:.1f}g")

        if sober_time:
            response_parts.append(f"Sober: ~{sober_time}")

        if driving_time:
            response_parts.append(f"Driving: ~{driving_time}")

    # Show burn rate only
    response_parts.append(f"Burn rate: {profile['burn_rate']}‰/h")

    return " | ".join(response_parts)


# =====================
# Blackjack game classes
# =====================


class CardSuit(Enum):
    SPADES = "♠"
    CLUBS = "♣"
    HEARTS = "♥"
    DIAMONDS = "♦"


class CardRank(Enum):
    ACE = "A"
    TWO = "2"
    THREE = "3"
    FOUR = "4"
    FIVE = "5"
    SIX = "6"
    SEVEN = "7"
    EIGHT = "8"
    NINE = "9"
    TEN = "10"
    JACK = "J"
    QUEEN = "Q"
    KING = "K"


@dataclass
class Card:
    """A playing card with suit and rank."""

    suit: CardSuit
    rank: CardRank

    @property
    def value(self) -> int:
        """Get the numeric value of the card for blackjack."""
        if self.rank == CardRank.ACE:
            return 11  # Aces are 11 by default, can be reduced to 1
        elif self.rank in [CardRank.JACK, CardRank.QUEEN, CardRank.KING]:
            return 10
        else:
            return int(self.rank.value)

    def __str__(self) -> str:
        return f"{self.rank.value}{self.suit.value}"


@dataclass
class Hand:
    """A blackjack hand containing cards."""

    cards: List[Card] = field(default_factory=list)
    is_stand: bool = False
    is_bust: bool = False

    @property
    def value(self) -> int:
        """Calculate the total value of the hand, handling aces optimally."""
        total = 0
        aces = 0

        for card in self.cards:
            if card.rank == CardRank.ACE:
                aces += 1
                total += 11
            else:
                total += card.value

        # Convert aces from 11 to 1 if needed
        while total > 21 and aces > 0:
            total -= 10
            aces -= 1

        return total

    @property
    def is_blackjack(self) -> bool:
        """Check if this is a blackjack (21 with 2 cards)."""
        return len(self.cards) == 2 and self.value == 21

    def add_card(self, card: Card):
        """Add a card to the hand and check for bust."""
        self.cards.append(card)
        if self.value > 21:
            self.is_bust = True

    def __str__(self) -> str:
        card_strs = [str(card) for card in self.cards]
        return f"[{', '.join(card_strs)}] ({self.value})"


class Deck:
    """A standard 52-card deck."""

    def __init__(self):
        self.cards: List[Card] = []
        self.reset()

    def reset(self):
        """Reset and shuffle the deck."""
        self.cards = []
        for suit in CardSuit:
            for rank in CardRank:
                self.cards.append(Card(suit, rank))
        random.shuffle(self.cards)

    def draw(self) -> Card:
        """Draw a card from the deck."""
        if not self.cards:
            raise ValueError("Deck is empty")
        return self.cards.pop()


class GameState(Enum):
    """Blackjack game states."""

    IDLE = "idle"
    JOINING = "joining"
    PLAYING = "playing"
    DEALER_TURN = "dealer_turn"
    ENDED = "ended"


@dataclass
class BlackjackGame:
    """A blackjack game instance."""

    channel: str = ""  # Channel where game was started
    state: GameState = GameState.IDLE
    players: OrderedDict[str, Hand] = field(default_factory=OrderedDict)
    dealer_hand: Hand = field(default_factory=Hand)
    deck: Deck = field(default_factory=Deck)
    current_turn_index: int = 0
    started_at: Optional[datetime] = None
    last_action_at: Optional[datetime] = None
    join_timer: Optional[threading.Timer] = None

    def start_game(self, starter: str, channel: str):
        """Start a new game in joining state."""
        self.channel = channel
        self.state = GameState.JOINING
        self.players = OrderedDict()
        self.dealer_hand = Hand()
        self.deck.reset()
        self.current_turn_index = 0
        self.started_at = datetime.now()
        self.last_action_at = datetime.now()

        # Add the starter as first player
        self.players[starter] = Hand()

        # Start 5-minute join timer
        self.join_timer = threading.Timer(300.0, self._auto_deal)
        self.join_timer.start()

    def join_player(self, nick: str) -> bool:
        """Add a player to the game. Returns True if successful."""
        if self.state != GameState.JOINING:
            return False
        if nick in self.players:
            return False  # Already joined

        self.players[nick] = Hand()
        self.last_action_at = datetime.now()
        return True

    def leave_player(self, nick: str) -> bool:
        """Remove a player from the game. Returns True if successful."""
        if self.state != GameState.JOINING:
            return False
        if nick not in self.players:
            return False

        del self.players[nick]
        self.last_action_at = datetime.now()

        # If no players left, cancel the game
        if not self.players:
            self._cleanup()

        return True

    def deal_cards(self, dealer: str) -> bool:
        """Deal initial cards and start playing. Returns True if successful."""
        if self.state != GameState.JOINING:
            return False
        if dealer not in self.players:
            return False  # Only joined players can deal
        if len(self.players) < 1:
            return False

        # Cancel join timer
        if self.join_timer:
            self.join_timer.cancel()
            self.join_timer = None

        self.state = GameState.PLAYING
        self.last_action_at = datetime.now()

        # Deal 2 cards to each player
        for _ in range(2):
            for player_hand in self.players.values():
                player_hand.add_card(self.deck.draw())

        # Deal 2 cards to dealer (one face up, one face down)
        self.dealer_hand.add_card(self.deck.draw())
        self.dealer_hand.add_card(self.deck.draw())

        return True

    def player_hit(self, nick: str) -> Optional[Card]:
        """Player draws a card. Returns the card if successful."""
        if self.state != GameState.PLAYING:
            return None
        if nick not in self.players:
            return None

        player_names = list(self.players.keys())
        if player_names[self.current_turn_index] != nick:
            return None  # Not player's turn

        player_hand = self.players[nick]
        if player_hand.is_stand or player_hand.is_bust:
            return None  # Can't hit if stood or bust

        card = self.deck.draw()
        player_hand.add_card(card)
        self.last_action_at = datetime.now()

        # If bust or blackjack, auto-stand
        if player_hand.is_bust or player_hand.is_blackjack:
            player_hand.is_stand = True
            self._next_turn()

        return card

    def player_stand(self, nick: str) -> bool:
        """Player stands. Returns True if successful."""
        if self.state != GameState.PLAYING:
            return False
        if nick not in self.players:
            return False

        player_names = list(self.players.keys())
        if player_names[self.current_turn_index] != nick:
            return False  # Not player's turn

        player_hand = self.players[nick]
        if player_hand.is_stand or player_hand.is_bust:
            return False  # Already stood or bust

        player_hand.is_stand = True
        self.last_action_at = datetime.now()
        self._next_turn()
        return True

    def get_status(self, nick: str = None) -> str:
        """Get current game status."""
        if self.state == GameState.IDLE:
            return "No active blackjack game."

        if self.state == GameState.JOINING:
            players_list = ", ".join(self.players.keys())
            time_left = 300 - (datetime.now() - self.started_at).seconds
            return f"Joining phase. Players: {players_list}. Time left: {time_left}s"

        if self.state == GameState.PLAYING:
            player_names = list(self.players.keys())
            current_player = (
                player_names[self.current_turn_index]
                if self.current_turn_index < len(player_names)
                else "Unknown"
            )

            status_lines = []
            status_lines.append(f"Current turn: {current_player}")

            # Show dealer's visible card
            if self.dealer_hand.cards:
                dealer_visible = str(self.dealer_hand.cards[0])
                status_lines.append(f"Dealer: [{dealer_visible}, ?]")

            # Show all players' hands
            for player_nick, hand in self.players.items():
                status_lines.append(f"{player_nick}: {hand}")

            return "\n".join(status_lines)

        if self.state == GameState.DEALER_TURN:
            return "Dealer is playing..."

        if self.state == GameState.ENDED:
            return "Game has ended."

        return "Unknown game state."

    def get_player_hand(self, nick: str) -> Optional[str]:
        """Get a player's private hand information."""
        if nick not in self.players:
            return None

        hand = self.players[nick]

        if self.state == GameState.PLAYING:
            player_names = list(self.players.keys())
            is_current_turn = player_names[self.current_turn_index] == nick
            turn_status = " (Your turn)" if is_current_turn else ""
            return f"Your hand: {hand}{turn_status}"
        elif self.state == GameState.DEALER_TURN or self.state == GameState.ENDED:
            return f"Your final hand: {hand}"
        else:
            return f"Your hand: {hand}"

    def end_game(self) -> Dict[str, str]:
        """End the game and calculate results. Returns results dict."""
        if self.state not in [GameState.PLAYING, GameState.DEALER_TURN]:
            return {}

        self.state = GameState.ENDED

        # Dealer plays
        while self.dealer_hand.value < 17:
            self.dealer_hand.add_card(self.deck.draw())

        # Calculate results with hand information
        results = {}
        dealer_value = self.dealer_hand.value
        dealer_bust = self.dealer_hand.is_bust

        # Format dealer hand
        dealer_cards = [str(card) for card in self.dealer_hand.cards]
        dealer_hand_str = f"[{', '.join(dealer_cards)}] ({dealer_value})"

        for nick, hand in self.players.items():
            # Format player hand
            player_cards = [str(card) for card in hand.cards]
            player_hand_str = f"[{', '.join(player_cards)}] ({hand.value})"

            if hand.is_bust:
                results[nick] = f"BUST {player_hand_str} vs {dealer_hand_str}"
            elif hand.is_blackjack and not self.dealer_hand.is_blackjack:
                results[nick] = f"BLACKJACK {player_hand_str} vs {dealer_hand_str}"
            elif dealer_bust:
                results[nick] = f"VOITTO {player_hand_str} vs {dealer_hand_str}"
            elif hand.value > dealer_value:
                results[nick] = f"VOITTO {player_hand_str} vs {dealer_hand_str}"
            elif hand.value < dealer_value:
                results[nick] = f"HÄVIÖ {player_hand_str} vs {dealer_hand_str}"
            else:
                results[nick] = f"TASAPELI {player_hand_str} vs {dealer_hand_str}"

        self._cleanup()
        return results

    def _next_turn(self):
        """Advance to the next player's turn."""
        self.current_turn_index += 1
        player_names = list(self.players.keys())

        # Check if all players have finished
        active_players = [
            p for p in self.players.values() if not p.is_stand and not p.is_bust
        ]
        if not active_players:
            self.state = GameState.DEALER_TURN
            # Auto-end game after a short delay
            threading.Timer(2.0, self.end_game).start()

    def _auto_deal(self):
        """Automatically deal cards when join timer expires."""
        if self.state == GameState.JOINING and len(self.players) >= 1:
            self.deal_cards(list(self.players.keys())[0])

    def _cleanup(self):
        """Clean up the game."""
        self.state = GameState.IDLE
        if self.join_timer:
            self.join_timer.cancel()
            self.join_timer = None


# Global blackjack game instance
_blackjack_game = BlackjackGame()


def get_blackjack_game() -> BlackjackGame:
    """Get the global blackjack game instance."""
    return _blackjack_game


# =====================
# Sanaketju game classes
# =====================


@dataclass
class SanaketjuGame:
    """A sanaketju (word chain) game instance."""

    active: bool = False
    channel: str = ""
    current_word: str = ""
    chain_length: int = 0
    participants: Dict[str, int] = field(default_factory=dict)  # nick -> total_score
    used_words: set = field(default_factory=set)
    start_time: Optional[datetime] = None
    notice_blacklist: set = field(default_factory=set)  # nicks who don't want notices

    def start_game(self, channel: str, data_manager: DataManager) -> Optional[str]:
        """Start a new game. Returns starting word or None if failed."""
        if self.active:
            return None

        # Get random starting word from collected words
        starting_word = self._get_random_starting_word(data_manager)
        if not starting_word:
            return None

        self.active = True
        self.channel = channel
        self.current_word = starting_word
        self.chain_length = 1
        self.participants = {}
        self.used_words = {starting_word.lower()}
        self.start_time = datetime.now()
        self.notice_blacklist = set()

        # Save state
        self._save_state(data_manager)
        return starting_word

    def _get_random_starting_word(self, data_manager: DataManager) -> Optional[str]:
        """Get a random word from collected words for starting the game."""
        try:
            # Get all words from general words data
            general_data = data_manager.load_general_words_data()
            all_words = set()

            for server_data in general_data.get("servers", {}).values():
                for nick_data in server_data.get("nicks", {}).values():
                    all_words.update(nick_data.get("general_words", {}).keys())

            # Filter words: no special characters, max 30 chars
            valid_words = [
                word
                for word in all_words
                if len(word) <= 30 and word.isalpha() and len(word) >= 3
            ]

            if not valid_words:
                return None

            return random.choice(valid_words)

        except Exception as e:
            logger.error(f"Error getting random starting word: {e}")
            return None

    def process_word(
        self, word: str, nick: str, data_manager: DataManager
    ) -> Optional[Dict[str, Any]]:
        """
        Process a potential word continuation.
        Returns dict with 'valid', 'score', 'total_score' if valid, None if invalid.
        """
        if not self.active:
            return None

        word = word.lower().strip()
        if not word or len(word) > 30 or not word.isalpha():
            return None

        # Check if word starts with last letter of current word
        if not self.current_word or word[0] != self.current_word[-1].lower():
            return None

        # Check if word has been used
        if word in self.used_words:
            return None

        # Valid word! Update game state
        self.current_word = word
        self.chain_length += 1
        self.used_words.add(word)

        # Update participant score
        score = len(word)
        if nick not in self.participants:
            self.participants[nick] = 0
        self.participants[nick] += score

        # Save state
        self._save_state(data_manager)

        return {
            "valid": True,
            "word": word,
            "score": score,
            "total_score": self.participants[nick],
            "chain_length": self.chain_length,
        }

    def toggle_ignore(self, nick: str, target_nick: Optional[str] = None) -> bool:
        """
        Toggle notice blacklist for a user.
        Returns True if now ignored, False if now receiving notices.
        """
        if target_nick:
            # Admin toggling another user
            nick_to_toggle = target_nick.lower()
        else:
            # User toggling themselves
            nick_to_toggle = nick.lower()

        if nick_to_toggle in self.notice_blacklist:
            self.notice_blacklist.remove(nick_to_toggle)
            return False  # Now receiving notices
        else:
            self.notice_blacklist.add(nick_to_toggle)
            return True  # Now ignored

    def get_status(self) -> str:
        """Get current game status."""
        if not self.active:
            return "Ei aktiivista sanaketjua."

        participants_str = (
            ", ".join(
                f"{nick}: {score} pistettä"
                for nick, score in sorted(
                    self.participants.items(), key=lambda x: x[1], reverse=True
                )
            )
            or "Ei osallistujia vielä"
        )

        start_time_str = (
            self.start_time.strftime("%d.%m.%Y %H:%M")
            if self.start_time
            else "Tuntematon"
        )

        return (
            f"Sanaketju aktiivinen! "
            f"Nykyinen sana: {self.current_word} | "
            f"Ketjun pituus: {self.chain_length} | "
            f"Aloitusaika: {start_time_str} | "
            f"Osallistujat: {participants_str}"
        )

    def end_game(self, data_manager: DataManager) -> Optional[str]:
        """End the current game. Returns final results or None if no active game."""
        if not self.active:
            return None

        # Calculate results
        if not self.participants:
            result = "Sanaketju päättyi. Ei osallistujia."
        else:
            winner = max(self.participants.items(), key=lambda x: x[1])
            end_time = datetime.now()
            duration = end_time - (self.start_time or end_time)

            participants_str = ", ".join(
                f"{nick}: {score}"
                for nick, score in sorted(
                    self.participants.items(), key=lambda x: x[1], reverse=True
                )
            )

            result = (
                f"Sanaketju päättyi! "
                f"Voittanut: {winner[0]} ({winner[1]} pistettä) | "
                f"Ketjun pituus: {self.chain_length} | "
                f"Kesto: {str(duration).split('.')[0]} | "
                f"Osallistujat: {participants_str}"
            )

        # Reset game
        self.active = False
        self.channel = ""
        self.current_word = ""
        self.chain_length = 0
        self.participants = {}
        self.used_words = set()
        self.start_time = None
        self.notice_blacklist = set()

        # Save state
        self._save_state(data_manager)
        return result

    def _save_state(self, data_manager: DataManager):
        """Save current game state."""
        state = {
            "active": self.active,
            "channel": self.channel,
            "current_word": self.current_word,
            "chain_length": self.chain_length,
            "participants": self.participants,
            "used_words": list(self.used_words),
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "notice_blacklist": list(self.notice_blacklist),
        }
        data_manager.save_sanaketju_state(state)

    def _load_state(self, data_manager: DataManager):
        """Load game state from data manager."""
        state = data_manager.load_sanaketju_state()
        if state:
            self.active = state.get("active", False)
            self.channel = state.get("channel", "")
            self.current_word = state.get("current_word", "")
            self.chain_length = state.get("chain_length", 0)
            self.participants = state.get("participants", {})
            self.used_words = set(state.get("used_words", []))
            start_time_str = state.get("start_time")
            if start_time_str:
                try:
                    self.start_time = datetime.fromisoformat(start_time_str)
                except Exception:
                    self.start_time = None
            self.notice_blacklist = set(state.get("notice_blacklist", []))


# Global sanaketju game instance
_sanaketju_game = SanaketjuGame()


def get_sanaketju_game() -> SanaketjuGame:
    """Get the global sanaketju game instance."""
    return _sanaketju_game


# =====================
# Blackjack command
# =====================


@command(
    "blackjack",
    description="Play blackjack (subcommands: start, join, leave, deal, hit, stand, status)",
    usage="!blackjack <start|join|leave|deal|hit|stand|status>",
    examples=[
        "!blackjack start",
        "!blackjack join",
        "!blackjack hit",
        "!blackjack status",
    ],
)
def blackjack_command(context: CommandContext, bot_functions):
    """Main blackjack command with subcommands."""
    game = get_blackjack_game()

    if not context.args:
        return "Usage: !blackjack <start|join|leave|deal|hit|stand|status>"

    subcommand = context.args[0].lower()

    # Helper functions
    def send_private(msg: str, target: str = None):
        """Send a private message to a user."""
        if not target:
            target = context.sender
        notice = bot_functions.get("notice_message")
        irc = bot_functions.get("irc")
        if notice and irc:
            notice(msg, irc, target)

    def send_channel(msg: str):
        """Send a message to the game channel."""
        if game.channel:
            send_message = bot_functions.get("send_message")
            if send_message:
                # send_message lambda expects (irc, target, msg)
                send_message(bot_functions.get("server"), game.channel, msg)

    # Handle subcommands
    if subcommand == "start":
        if game.state != GameState.IDLE:
            return "A blackjack game is already active."

        game.start_game(context.sender, context.target or context.sender)

        # Announce in channel
        send_channel(
            f"Blackjack game started by {context.sender}! Join with !blackjack join (5min)"
        )

        # Confirm to starter privately
        send_private(
            "You started a blackjack game! Others can join with !blackjack join"
        )

        return CommandResponse.no_response()

    elif subcommand == "join":
        if game.state != GameState.JOINING:
            return "No blackjack game is currently accepting joins."

        if game.join_player(context.sender):
            send_private(
                f"You joined the blackjack game! Players: {', '.join(game.players.keys())}"
            )
            return CommandResponse.no_response()
        else:
            return "You are already in the game or joining is not allowed."

    elif subcommand == "leave":
        if game.state != GameState.JOINING:
            return "You can only leave during the joining phase."

        if game.leave_player(context.sender):
            send_private("You left the blackjack game.")
            return CommandResponse.no_response()
        else:
            return "You are not in the game."

    elif subcommand == "deal":
        if game.state != GameState.JOINING:
            return "Cards can only be dealt during the joining phase."

        if game.deal_cards(context.sender):
            # Send initial hands privately to all players
            dealer_visible = (
                str(game.dealer_hand.cards[0]) if game.dealer_hand.cards else "?"
            )
            for nick in game.players.keys():
                hand_str = game.get_player_hand(nick)
                send_private(f"{hand_str} | Dealer: {dealer_visible}", nick)

            return CommandResponse.no_response()
        else:
            return "Cannot deal cards right now."

    elif subcommand == "hit":
        if game.state != GameState.PLAYING:
            return "No active blackjack game."

        card = game.player_hit(context.sender)
        if card:
            player_hand = game.players[context.sender]
            # Create hand display without value for hit messages
            hand_cards = [str(c) for c in player_hand.cards]
            hand_display = f"[{', '.join(hand_cards)}]"

            hand_value = player_hand.value
            hand_with_count = f"{hand_display} ({hand_value})"

            if game.players[context.sender].is_bust:
                send_private(
                    f"You drew: {card} Hand: {hand_with_count}\n💥 You went bust!"
                )
                # Check if game should end
                active_players = [
                    p for p in game.players.values() if not p.is_stand and not p.is_bust
                ]
                if not active_players:
                    results = game.end_game()
                    if results:
                        result_str = " | ".join(
                            f"{nick} {result}" for nick, result in results.items()
                        )
                        send_channel(f"Blackjack results: {result_str}")
            else:
                send_private(f"You drew: {card} Hand: {hand_with_count}")

            return CommandResponse.no_response()
        else:
            return "It's not your turn or you cannot hit."

    elif subcommand == "stand":
        if game.state != GameState.PLAYING:
            return "No active blackjack game."

        if game.player_stand(context.sender):
            hand_str = game.get_player_hand(context.sender)
            send_private(f"You stand with: {hand_str}")

            # Check if game should end
            active_players = [
                p for p in game.players.values() if not p.is_stand and not p.is_bust
            ]
            if not active_players:
                results = game.end_game()
                if results:
                    result_str = " | ".join(
                        f"{nick} {result}" for nick, result in results.items()
                    )
                    send_channel(f"Blackjack results: {result_str}")

            return CommandResponse.no_response()
        else:
            return "It's not your turn or you cannot stand."

    elif subcommand == "status":
        status = game.get_status(context.sender)
        send_private(status)
        return CommandResponse.no_response()

    else:
        return f"Unknown subcommand: {subcommand}. Use: start, join, leave, deal, hit, stand, status"


# =====================
# Sanaketju command
# =====================


@command(
    "sanaketju",
    description="Play sanaketju word chain game (start, status, stop, ignore)",
    usage="!sanaketju [start|stop|ignore [nick]]",
    examples=[
        "!sanaketju",
        "!sanaketju start",
        "!sanaketju stop",
        "!sanaketju ignore",
        "!sanaketju ignore othernick",
    ],
)
def sanaketju_command(context: CommandContext, bot_functions):
    """Main sanaketju command with subcommands."""
    data_manager = bot_functions.get("data_manager")
    if not data_manager:
        return "❌ Data manager not available"

    game = get_sanaketju_game()
    game._load_state(data_manager)  # Load latest state

    if not context.args:
        # Show current status
        return game.get_status()

    subcommand = context.args[0].lower()

    if subcommand == "start":
        if game.active:
            return "Sanaketju on jo käynnissä!"

        starting_word = game.start_game(context.target, data_manager)
        if starting_word:
            return f"🎯 Sanaketju aloitettu! Aloitussana: {starting_word}"
        else:
            return "❌ Ei voitu aloittaa sanaketjua - ei sanoja saatavilla."

    elif subcommand == "stop":
        result = game.end_game(data_manager)
        if result:
            return result
        else:
            return "Ei aktiivista sanaketjua lopetettavaksi."

    elif subcommand == "ignore":
        target_nick = context.args[1] if len(context.args) > 1 else None

        # Check if user has permission to ignore others (simple check: if they specify a nick)
        if target_nick and target_nick != context.sender:
            # For now, allow anyone to toggle anyone's ignore status
            # Could add admin check here if needed
            pass

        ignored = game.toggle_ignore(context.sender, target_nick)
        nick_display = target_nick or context.sender

        if ignored:
            return f"✅ {nick_display} ei enää saa sanaketju-ilmoituksia."
        else:
            return f"✅ {nick_display} saa taas sanaketju-ilmoituksia."

    else:
        return "Tuntematon komento. Käytä: start, stop, ignore [nick] tai ilman parametreja tilan näyttämiseen."


# EOF
