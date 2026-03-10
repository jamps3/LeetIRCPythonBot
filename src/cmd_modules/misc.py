"""
Miscellaneous Commands Module

Contains misc commands: 420, kaiku, muunnos, matka, np, quote, leets, etc.

Note: Some commands depend on shared helpers in commands.py - they are imported as needed.
"""

import os
import random
import re
import urllib.request
from datetime import datetime

import requests

import bot_manager  # noqa: F401 - needed for schedule command
from command_registry import (
    CommandContext,
    CommandType,
    command,
    process_command_message,
)
from config import DATA_DIR, get_config

# =====================
# 420 Command
# =====================


_420_RESPONSES = [
    # Classic 420 responses
    "🌿 420! Stay chill! 🌿",
    "🔥 Blaze it! 🔥",
    "🍃 High five! 🍃",
    "😎 420, man! 😎",
    "🌱 It's 420 somewhere! 🌱",
    "🎉 4/20 forever! 🎉",
    "💨 Cloud nine calling! 💨",
    # Finnish/Estonian vibes
    "🌿 Hyvä meininki! 🌿",
    "🔥 Saundaa! 🔥",
    "😎 420 vaan! 😎",
    # Fun responses
    "🍪 Time for cookies! 🍪",
    "🎰 Lucky number 420! 🎰",
    "🌟 Legendary number! 🌟",
    "💚 Green vibes only! 💚",
    "☮️ Peace and love! ☮️",
    "🎶 Bobbing along! 🎶",
    "🦋 Floating on clouds! 🦋",
    # Emoji combinations
    "🌿☀️🌿",
    "🔥💨🔥",
    "🍃🎵🍃",
    "😎✨😎",
    # Inspirational
    "Stay elevated! 💫",
    "Keep it mellow! 🌊",
    "Good vibes only! ✌️",
    "Stay positive! 🌞",
    # Random fun
    "Puff puff pass! 🎋",
    "Herb is the word! 🌾",
    "Nature's gift! 🌻",
    "Pure relaxation! 🧘",
    "Live and let live! 🕊️",
]


def _get_420_countdown() -> str:
    """Calculate days until next April 20th."""
    now = datetime.now()
    current_year = now.year
    # April 20th of current year
    april_20 = datetime(current_year, 4, 20)

    if now > april_20:
        # Already passed this year, next year's April 20th
        april_20 = datetime(current_year + 1, 4, 20)

    days_until = (april_20 - now).days
    return days_until


def _get_1620_countdown() -> str:
    """Calculate time until next 16:20 (4:20 PM) today."""
    now = datetime.now()
    current_hour = now.hour
    current_minute = now.minute

    # Target: 16:20 (4:20 PM)
    target_hour = 16
    target_minute = 20

    # Calculate minutes until 16:20
    current_minutes = current_hour * 60 + current_minute
    target_minutes = target_hour * 60 + target_minute

    if current_minutes >= target_minutes:
        # Already passed today, tomorrow's 16:20
        minutes_until = (24 * 60 - current_minutes) + target_minutes
    else:
        minutes_until = target_minutes - current_minutes

    hours = minutes_until // 60
    mins = minutes_until % 60

    if hours > 0:
        return f"{hours}h {mins}min"
    else:
        return f"{mins}min"


@command(
    "420",
    description="420 countdown and toggle responses",
    usage="!420 [on|off|toggle]",
)
def four_twenty_command(context: CommandContext, bot_functions):
    """Show 420 countdown and respond with 420 vibes! Use !420 on/off to toggle."""
    # Check for on/off/toggle argument
    args = context.args if hasattr(context, "args") and context.args else []

    if args:
        # Handle toggle command
        action = args[0].lower() if args else ""
        data_manager = bot_functions.get("data_manager")

        if action in ("on", "off", "toggle") and data_manager:
            try:
                state = data_manager.load_state()
                current_enabled = state.get("420_enabled", True)

                if action == "on":
                    new_enabled = True
                elif action == "off":
                    new_enabled = False
                else:  # toggle
                    new_enabled = not current_enabled

                # Update the setting
                state["420_enabled"] = new_enabled
                data_manager.save_state(state)

                status = "päällä" if new_enabled else "pois päältä"
                return f"🌿 420 responses: {status} 🌿"
            except Exception as e:
                return f"🌿 Error updating 420 setting: {e}"

    # Default: show countdown
    days = _get_420_countdown()
    time_to_1620 = _get_1620_countdown()
    response = random.choice(_420_RESPONSES)

    # Check if today is 4/20
    now = datetime.now()
    is_420_today = now.month == 4 and now.day == 20

    if is_420_today:
        return f"🎉 IT'S 4/20 TODAY! 🎉 | {response}"
    else:
        return f"⏰ {days} päivää 4/20:een | ⌚ {time_to_1620} 16:20:een | {response}"


# =====================
# Kaiku/Echo Command
# =====================


@command(
    "kaiku",
    aliases=["echo"],
    description="Echo back the message or send to channel",
    usage="!kaiku [#channel] [command] [command_parameters]",
    examples=[
        "!kaiku Hello world!",
        "!kaiku #general Hello",
        "!kaiku #general !weather Helsinki",
    ],
    requires_args=True,
)
async def echo_command(context: CommandContext, bot_functions):
    """Echo back the message or send to channel."""
    if not context.args:
        return "Usage: !kaiku <message> or !kaiku #channel <message>"

    first_arg = context.args[0]

    # Check if first argument is a channel
    if first_arg.startswith("#"):
        # Send to specified channel
        if len(context.args) < 2:
            return "Usage: !kaiku #channel <message>"

        # Get the server from bot_functions
        server = bot_functions.get("server")
        if not server:
            return "Server not available"

        # Simple echo to channel
        message = " ".join(context.args[1:])

        # Check if message starts with ! - treat as command to execute
        if message.startswith("!"):
            # Create a new context for the subcommand
            sub_context = CommandContext(
                command="",
                args=[],
                raw_message=message,
                sender=context.sender,
                target=first_arg,  # Send result to the specified channel
                server_name=context.server_name,
                is_console=False,
            )
            # Execute the subcommand
            result = await process_command_message(message, sub_context, bot_functions)
            if result:
                # Send command result to channel - handle CommandResponse or string
                if hasattr(result, "message"):
                    # It's a CommandResponse object
                    response_text = result.message
                else:
                    # It's already a string
                    response_text = str(result)
                if response_text:
                    # Check if we should use notices (like the original command would)
                    use_notices = get_config().use_notices
                    if use_notices and hasattr(server, "send_notice"):
                        server.send_notice(first_arg, response_text)
                    else:
                        server.send_message(first_arg, response_text)
            return None  # Command executed, don't echo the raw message
        else:
            # Regular echo - just send the message as-is
            server.send_message(first_arg, message)
            return None  # type: ignore
    else:
        # Regular echo mode
        if context.is_console:
            return f"Console: {context.args_text}"
        else:
            return f"{context.sender}: {context.args_text}"


# =====================
# NP (Name Day) Command
# =====================


@command("np", description="Show name day", usage="!np [päivä|nimi]")
def np_command(context: CommandContext, bot_functions):
    """Show name day for today, a given date, or search by name using nimipaivat.json data file."""
    import json
    import os

    # Try to load nimipaivat.json
    np_file = os.path.join("data", "nimipaivat.json")
    if not os.path.exists(np_file):
        return "Name day data file not found"

    try:
        with open(np_file, "r", encoding="utf-8") as f:
            nimipaivat = json.load(f)
    except Exception:
        return "Error loading name day data"

    # Get today's date info
    now = datetime.now()
    today_month = now.month
    today_day = now.day

    # Load additional name day data (Swedish, Sami, Orthodox)
    others_data = {}
    others_file = os.path.join("data", "nimipaivat_others.json")
    if os.path.exists(others_file):
        try:
            with open(others_file, "r", encoding="utf-8") as f:
                others_data = json.load(f)
        except Exception:
            pass  # Silently skip if file can't be loaded

    # Handle new dict format: {"2025-01-01": {"official": [...], ...}}
    if isinstance(nimipaivat, dict):
        # Build date key for today (search by month-day ignoring year)
        month_day_key = f"-{today_month:02d}-{today_day:02d}"

        if not context.args:
            # Show today's name days - search by month-day
            for date_str, entry in nimipaivat.items():
                if date_str.endswith(month_day_key):
                    # Build detailed response with all name categories
                    official = entry.get("official", [])
                    unofficial = entry.get("unofficial", [])
                    dogs = entry.get("dogs", [])
                    cats = entry.get("cats", [])

                    parts = []
                    if official:
                        parts.append(f"Viralliset: {', '.join(official)}")
                    if unofficial:
                        parts.append(f"Epäviralliset: {', '.join(unofficial)}")
                    if dogs and dogs != [": -"]:
                        parts.append(f"Koirat: {', '.join(dogs)}")
                    if cats and cats != [": -"]:
                        parts.append(f"Kissat: {', '.join(cats)}")

                    # Add other name days (Swedish, Sami, Orthodox, Hevonen, Historiallinen)
                    # Data structure: {"ruotsi": {"2026-01-02": ["Gerhard"]}, "saame": {...}, ...}
                    month_day_date = f"{today_month:02d}-{today_day:02d}"

                    # Map category keys to display names
                    category_map = {
                        "ruotsi": "Ruotsiksi",
                        "saame": "Saameksi",
                        "ortodoksi": "Ortodoksit",
                        "hevonen": "Hevoset",
                        "historiallinen": "Historialliset",
                    }

                    for category, display_name in category_map.items():
                        if category in others_data:
                            category_dates = others_data[category]
                            # Find matching date (ignore year)
                            for other_date_str, names in category_dates.items():
                                if other_date_str.endswith(f"-{month_day_date}"):
                                    if names and names != [": -"]:
                                        parts.append(
                                            f"{display_name}: {', '.join(names)}"
                                        )
                                    break

                    if parts:
                        # Use single line format, but add newlines if too long for IRC
                        single_line = f"Nimipäivät tänään {today_day}.{today_month}.{now.year}: | {' | '.join(parts)}"
                        # IRC message limit is typically ~400 chars, add newlines if needed
                        if len(single_line) > 400:
                            return (
                                f"Nimipäivät tänään {today_day}.{today_month}.{now.year}:\n"
                                + "\n".join(parts)
                            )
                        return single_line
                    else:
                        return f"Tänään ({today_day}.{today_month}) on nimipäivä: {', '.join(official)}"
            return "No name day found for today"

        arg = context.args[0].lower()

        # Check if it's a number (date)
        if arg.isdigit():
            day = int(arg)
            # Show all name days for that day number (any month)
            results = []
            for date_str, entry in nimipaivat.items():
                try:
                    _, m, d = date_str.split("-")
                    if int(d) == day:
                        names = entry.get("official", [])
                        if names:
                            results.append(f"{day}.{int(m)}: {', '.join(names)}")
                except (ValueError, IndexError):
                    continue
            if results:
                return " | ".join(results)
            return f"No name day found for day {day}"

        # Search by name
        search_name = arg
        results = []
        for date_str, entry in nimipaivat.items():
            names = entry.get("official", [])
            for name in names:
                if search_name in name.lower():
                    try:
                        _, month, day = date_str.split("-")
                        results.append(f"{int(day)}.{int(month)}: {name}")
                    except (ValueError, IndexError):
                        pass
        if results:
            return " | ".join(results[:10])  # Limit results
        return f"No name found: {search_name}"

    # Handle old list format (legacy support)
    # [{"month": 1, "day": 1, "names": ["..."]}]
    if not context.args:
        # Show today's name days
        for entry in nimipaivat:
            if entry.get("month") == today_month and entry.get("day") == today_day:
                names = entry.get("names", [])
                return f"Tänään ({today_day}.{today_month}) on nimipäivä: {', '.join(names)}"
        return "No name day found for today"

    arg = context.args[0].lower()

    # Check if it's a number (date)
    if arg.isdigit():
        day = int(arg)
        month = None

        # Check if second arg is month
        if len(context.args) > 1 and context.args[1].isdigit():
            month = int(context.args[1])

        if month:
            # Search by exact date
            for entry in nimipaivat:
                if entry.get("month") == month and entry.get("day") == day:
                    names = entry.get("names", [])
                    return f"{day}.{month} on nimipäivä: {', '.join(names)}"
            return f"No name day found for {day}.{month}"
        else:
            # Show all name days for that day number (any month)
            results = []
            for entry in nimipaivat:
                if entry.get("day") == day:
                    m = entry.get("month")
                    names = entry.get("names", [])
                    results.append(f"{day}.{m}: {', '.join(names)}")
            if results:
                return " | ".join(results)
            return f"No name day found for day {day}"

    # Search by name
    search_name = arg
    results = []
    for entry in nimipaivat:
        names = entry.get("names", [])
        for name in names:
            if search_name in name.lower():
                day = entry.get("day")
                month = entry.get("month")
                results.append(f"{name} ({day}.{month})")

    if results:
        return " | ".join(results[:10])  # Limit to 10 results
    else:
        return f"No name found: {search_name}"


# =====================
# Leets Command
# =====================


@command(
    name="leets",
    command_type=CommandType.PUBLIC,
    description="Show recent leet detection history",
    usage="!leets <limit>",
    admin_only=False,
)
def command_leets(context, bot_functions):
    """Show recent leet detection history."""
    from datetime import datetime

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


# =====================
# Quote Command
# =====================


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
    quotes_source = getattr(
        config_obj, "quotes_source", os.path.join(DATA_DIR, "quotes.txt")
    )

    # Make sure we have an absolute path for file operations
    if not os.path.isabs(quotes_source):
        # Make relative paths resolve from project root
        quotes_source = os.path.join(DATA_DIR, quotes_source)

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


# =====================
# Matka Command
# =====================


@command(
    "matka", description="Show travel time and distance", usage="!matka <from> | <to>"
)
def driving_distance_osrm(context: CommandContext, bot_functions):
    """
    Laskee ajomatkan pituuden ja keston OSRM:n avulla kahden kaupungin valilla.
    """

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
            raise Exception(f"Koordinaatteja ei loytynyt kaupungille: {city_name}")

    text = context.args_text.strip()

    # Jos lainausmerkit kaytossa → poimitaan niiden sisalto
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
        # Muuten pilkotaan valilyonneilla
        args = text.split()

    if len(args) != 2:
        return "Anna kaupungit muodossa: !matka <kaupunki1> <kaupunki2> tai lainausmerkissa jos nimi sisaltaa valilyonnteja"

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
        distance_km = route["distance"] / 1000  # metreista kilometreiksi
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
        raise Exception(f"Virhe haettaessa reitteja: {response.status_code}")


# =====================
# Schedule Command
# =====================


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
        # In console, the server name is optional - use active server if not provided
        # Try with server name first, then without, then just time (use active channel)
        match = re.match(
            r"(\S+)\s+(#\S+)\s+(\d{1,2}):(\d{1,2}):(\d{1,2})(?:\.(\d{1,9}))?\s+(.+)",
            text,
        )
        if not match:
            # Try without server name (use active channel from console)
            match = re.match(
                r"(#\S+)\s+(\d{1,2}):(\d{1,2}):(\d{1,2})(?:\.(\d{1,9}))?\s+(.+)",
                text,
            )
        if not match:
            # Try just time and message (use active channel)
            match = re.match(
                r"(\d{1,2}):(\d{1,2}):(\d{1,2})(?:\.(\d{1,9}))?\s+(.+)",
                text,
            )
    else:
        match = re.match(
            r"(#\S+)\s+(\d{1,2}):(\d{1,2}):(\d{1,2})(?:\.(\d{1,9}))?\s+(.+)", text
        )

    if not match:
        return "Invalid format! Use: !schedule [server] [#channel] HH:MM:SS<.ns> message\nIn console, both server and channel are optional - uses active ones."

    # Determine if server name was provided based on number of groups
    # Format with server: 7 groups, Format without: 6 groups, Format just time: 5 groups
    num_groups = len(match.groups())

    if context.is_console:
        if num_groups == 7:
            # Format: server #channel HH:MM:SS message
            server_name = match.group(1)
            channel = match.group(2)
            hour = int(match.group(3))
            minute = int(match.group(4))
            second = int(match.group(5))
            frac_str = match.group(
                6
            )  # up to 9 digits (nanoseconds resolution in input)
            message = match.group(7)
        elif num_groups == 6:
            # Format: #channel HH:MM:SS message (no server name)
            # Use active server from console
            server_name = None
            channel = match.group(1)
            hour = int(match.group(2))
            minute = int(match.group(3))
            second = int(match.group(4))
            frac_str = match.group(
                5
            )  # up to 9 digits (nanoseconds resolution in input)
            message = match.group(6)
        else:
            # Format: HH:MM:SS message (no channel - use active channel)
            server_name = None
            channel = None  # Will be resolved from active channel
            hour = int(match.group(1))
            minute = int(match.group(2))
            second = int(match.group(3))
            frac_str = match.group(
                4
            )  # up to 9 digits (nanoseconds resolution in input)
            message = match.group(5)
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

        # If called from console, use the provided server name or get active server
        if not server:
            # Check if bot_manager is a proper instance with servers attribute
            if not hasattr(bot_manager, "servers") or not isinstance(
                getattr(bot_manager, "servers", None), dict
            ):
                # bot_manager is not a proper instance, can't determine server
                return "❌ Server context not available for scheduling"

            if server_name:
                # Use the provided server name
                server = bot_manager.servers.get(server_name)
            else:
                # Try to get active server from console_manager
                if (
                    hasattr(bot_manager, "console_manager")
                    and bot_manager.console_manager
                ):
                    active_server = bot_manager.console_manager.active_server
                    if active_server:
                        server = bot_manager.servers.get(active_server)
                # Fallback to first available server
                if not server and bot_manager.servers:
                    server = next(iter(bot_manager.servers.values()))

        if not server:
            return "❌ Server context not available for scheduling"

        # If no channel provided, get from active channel
        if not channel:
            if hasattr(bot_manager, "console_manager") and bot_manager.console_manager:
                channel = bot_manager.console_manager.active_channel
            if not channel:
                return "❌ No active channel. Use #channel to select one, or specify channel in command."

        # Schedule
        message_id = send_scheduled_message(
            server, channel, message, hour, minute, second, ns_str
        )

        # Show the requested time with 9-digit fractional part (as in logs)
        # Try to get server name from server object if possible
        server_name_str = None
        if server:
            server_name_str = (
                getattr(server, "name", None)
                or getattr(server, "server_name", None)
                or getattr(getattr(server, "config", None), "name", None)
                or getattr(server, "host", None)
            )
        if not server_name_str:
            server_name_str = str(server) if server else "unknown"
        return f"✅ Message scheduled with ID: {message_id} for {hour:02d}:{minute:02d}:{second:02d}.{ns_str} in {server_name_str} {channel}"

    except Exception as e:
        return f"❌ Error scheduling message: {str(e)}"


# =====================
# Placeholder commands - these need more work to extract
# =====================

# muunnos_command - depends on Finnish word transformation helpers

# =====================
# IPFS Command
# =====================


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


# For now, these will be imported from commands.py via the fallback mechanism

# =====================
# Dream Command
# =====================


@command(
    "dream",
    description="Generate surreal dream narrative or toggle automatic midnight dreams",
    usage="!dream [narrative|report|toggle] [surrealist|cyberpunk]",
    examples=["!dream", "!dream toggle", "!dream narrative cyberpunk", "!dream report"],
)
def dream_command(context: CommandContext, bot_functions):
    """Generate a dream narrative from daily conversation or toggle automatic midnight dreams."""
    # Get the dream service
    dream_service = bot_functions.get("dream_service")
    if not dream_service:
        return "Dream service is not available."

    # Get server name
    server_name = (
        bot_functions.get("server_name")
        or getattr(context, "server_name", "console")
        or "console"
    )

    # Get current channel
    channel = context.target if context.target else context.sender

    # Parse arguments
    args = context.args or []

    # Check for toggle command
    if args and args[0].lower() == "toggle":
        # Toggle automatic midnight dreams for current channel
        enabled = dream_service.toggle_dream_channel(channel)
        status = "enabled" if enabled else "disabled"
        return f"🌙 Automatic midnight dreams {status} for {channel}"

    # Determine output type and genre
    output_type = "narrative"  # default
    genre = "surrealist"  # default

    if args:
        if args[0].lower() in ["narrative", "report"]:
            output_type = args[0].lower()
            if len(args) > 1:
                genre = args[1].lower()
        elif args[0].lower() in ["surrealist", "cyberpunk"]:
            genre = args[0].lower()
            if len(args) > 1 and args[1].lower() in ["narrative", "report"]:
                output_type = args[1].lower()

    # Validate genre
    if genre not in ["surrealist", "cyberpunk"]:
        genre = "surrealist"

    # Generate dream
    try:
        dream_content = dream_service.generate_dream(
            server_name, channel, genre, output_type
        )

        # Send to channel if in IRC, otherwise return for console
        if not context.is_console:
            notice = bot_functions.get("notice_message")
            irc = bot_functions.get("irc")
            if notice and irc:
                # Split long messages for IRC
                lines = dream_content.split("\n")
                for line in lines:
                    if line.strip():
                        notice(line, irc, channel)
                return None  # Don't send additional response
            else:
                return dream_content
        else:
            return dream_content

    except Exception as e:
        return f"Dream generation failed: {str(e)}"


# Aliases for backwards compatibility with existing tests
matka_command = driving_distance_osrm
leets_command = command_leets
schedule_command = command_schedule
ipfs_command = command_ipfs
scheduled_command = command_schedule
