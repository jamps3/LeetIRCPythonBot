"""
Unified Commands Module for LeetIRCPythonBot
Admin commands in commands_admin.py
"""

import json
import os
import random
import re
import time
import urllib.request
from datetime import datetime

import bot_manager
import config
from command_registry import (
    CommandContext,
    CommandResponse,
    CommandScope,
    CommandType,
    command,
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
    config_obj = get_config()
    # Prefer a BOT_VERSION provided by the caller's context (e.g., console tests),
    # falling back to configured version.
    version = (
        bot_functions.get("BOT_VERSION", config_obj.version)
        if isinstance(bot_functions, dict)
        else config_obj.version
    )
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
            return "Nimipäivät tänään: " + format_entry(key, data[key])
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
    description="Display a random quote or search for a specific quote",
    usage="!quote [search_text]",
    examples=["!quote", "!quote tunnuslauseemme on"],
)
def quote_command(context: CommandContext, bot_functions):
    """Display a random quote from configured source (file or URL), or search for a specific quote if text is provided."""
    config_obj = get_config()

    # Get quotes source from environment, default to data/quotes.txt
    quotes_source = getattr(config_obj, "quotes_source", "data/quotes.txt")

    try:
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
            if not os.path.isabs(quotes_source):
                # Make relative paths resolve from project root
                project_root = os.path.abspath(
                    os.path.join(os.path.dirname(__file__), "..")
                )
                quotes_source = os.path.join(project_root, quotes_source)

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
        return f"Error getting quote: {e}"


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


@command(
    "sahko",
    aliases=["sähkö"],
    description="Get electricity price information",
    usage="!sahko [tänään|huomenna|longbar|tilastot|stats] [tunti]",
    examples=[
        "!sahko",
        "!sahko huomenna",
        "!sahko tänään 15",
        "!sahko longbar",
        "!sahko tilastot",
        "!sahko stats",
    ],
)
def electricity_command(context: CommandContext, bot_functions):
    """Get electricity price information."""
    # Get electricity service directly for better control in TUI mode
    bot_manager = bot_functions.get("bot_manager")
    if not bot_manager or not bot_manager.electricity_service:
        return "Electricity price service not available. Please configure ELECTRICITY_API_KEY."

    try:
        # Parse arguments using the service
        parsed_args = bot_manager.electricity_service.parse_command_args(context.args)

        if parsed_args.get("error"):
            return f"⚡ {parsed_args['error']}"

        if parsed_args.get("show_longbar"):
            # Show long bar graph for today's 15-minute intervals
            daily_data = bot_manager.electricity_service.get_daily_prices(
                parsed_args["date"]
            )
            if daily_data.get("error"):
                response = (
                    f"⚡ {daily_data.get('message', 'Hintatietoja ei saatavilla.')}"
                )
            else:
                long_bar = bot_manager.electricity_service._create_long_price_bar_graph(
                    daily_data["interval_prices"]
                )
                # Split into bars: each bar is either 4 chars (colored: \x03 + color + symbol + \x0f) or 1 char (space)
                # We need to find the 48th bar boundary, not character boundary
                bars = []
                i = 0
                while i < len(long_bar):
                    # Check if this is a colored bar (4 chars: \x03 + color_num + symbol + \x0f)
                    if (
                        i + 3 < len(long_bar)
                        and long_bar[i] == "\x03"
                        and long_bar[i + 3] == "\x0f"
                    ):
                        # Colored bar: \x03 + color + symbol + \x0f
                        bars.append(long_bar[i : i + 4])  # noqa: E203
                        i += 4
                    else:
                        # Space for missing data
                        bars.append(long_bar[i])
                        i += 1

                # Now split into first 48 bars and remaining 48 bars
                first_half = "".join(bars[:48])
                second_half = "".join(bars[48:])
                response = f"⚡ {first_half}\n{second_half}"
                # Return CommandResponse with split_long_messages=False to preserve newlines
                return CommandResponse(
                    success=True, message=response, split_long_messages=False
                )
        elif parsed_args.get("show_stats"):
            # Show daily statistics
            stats_data = bot_manager.electricity_service.get_price_statistics(
                parsed_args["date"]
            )
            response = bot_manager.electricity_service.format_statistics_message(
                stats_data
            )
        elif parsed_args.get("show_all_hours"):
            # Show all hours for the day
            # First, check if data is available for the requested date
            daily_data = bot_manager.electricity_service.get_daily_prices(
                parsed_args["date"]
            )
            if daily_data.get("error"):
                # Data not available - return error message immediately
                if parsed_args["is_tomorrow"]:
                    return f"⚡ Huomisen hintatietoja ei vielä saatavilla. {daily_data.get('message', 'Data may not be published yet.')}"
                else:
                    return (
                        f"⚡ {daily_data.get('message', 'Hintatietoja ei saatavilla.')}"
                    )

            # Data is available, get prices for all hours
            all_prices = []
            for h in range(24):
                price_data = bot_manager.electricity_service.get_electricity_price(
                    hour=h, date=parsed_args["date"]
                )
                if price_data.get("error"):
                    all_prices.append({"hour": h, "error": price_data["message"]})
                else:
                    all_prices.append(price_data)
            response = bot_manager.electricity_service.format_daily_prices_message(
                all_prices, is_tomorrow=parsed_args["is_tomorrow"]
            )
        else:
            # Handle specific hour or 15-minute interval
            price_data = bot_manager.electricity_service.get_electricity_price(
                hour=parsed_args.get("hour"),
                quarter=parsed_args.get("quarter"),
                date=parsed_args["date"],
            )
            response = bot_manager.electricity_service.format_price_message(price_data)

        return response

    except Exception as e:
        return f"⚡ Error getting electricity price: {str(e)}"


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
    from datetime import datetime as _dt

    import requests

    try:
        # XML data URL from Suomen Pankki
        url = (
            "https://reports.suomenpankki.fi/WebForms/ReportViewerPage.aspx?report="
            "/tilastot/markkina-_ja_hallinnolliset_korot/euribor_korot_today_xml_en&output=xml"
        )
        response = requests.get(url)
        if response.status_code == 200:
            root = ElementTree.fromstring(response.content)
            ns = {"ns": "euribor_korot_today_xml_en"}
            period = root.find(".//ns:period", namespaces=ns)
            if period is not None:
                date_str = period.attrib.get("value")
                date_obj = _dt.strptime(date_str, "%Y-%m-%d")
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
    "junat",
    description="Näytä seuraavat junat asemalta (Digitraffic)",
    usage="!junat [asema] | !junat saapuvat [asema]",
    examples=[
        "!junat",
        "!junat Joensuu",
        "!junat JNS",
        "!junat saapuvat",
        "!junat saapuvat HKI",
    ],
)
def trains_command(context: CommandContext, bot_functions):
    """Show upcoming trains for a station using Digitraffic API.

    Defaults to Joensuu (JNS) when no station is given.
    """
    try:
        from services.digitraffic_service import (
            get_arrivals_for_station,
            get_trains_for_station,
        )

        # Parse subcommand 'saapuvat'
        if context.args and context.args[0].lower() == "saapuvat":
            station = (
                " ".join(context.args[1:]).strip() if len(context.args) > 1 else None
            )
            result = get_arrivals_for_station(station)
        else:
            station = context.args_text.strip() if context.args_text else None
            result = get_trains_for_station(station)
        # Let the command framework split by newlines for IRC notices
        return CommandResponse.success_msg(result)
    except Exception as e:
        return f"❌ Digitraffic virhe: {str(e)}"


@command(
    "youtube",
    description="Search YouTube videos or get video info",
    usage="!youtube <search query>",
    examples=["!youtube python tutorial", "!youtube cat videos"],
    requires_args=True,
)
def youtube_command(context: CommandContext, bot_functions):
    """Search YouTube for videos."""
    search_youtube = bot_functions.get("search_youtube")
    if not search_youtube:
        return "YouTube service not available. Please configure YOUTUBE_API_KEY."

    query = context.args_text.strip()
    if not query:
        return "Usage: !youtube <search query>"

    try:
        response = search_youtube(query)
        return response
    except Exception as e:
        return f"❌ YouTube search error: {str(e)}"


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
    """Show top-3 leet winners by category (first, last, multileet)."""
    load_leet_winners = bot_functions.get("load_leet_winners")
    if not load_leet_winners:
        return "Leet winners service not available"

    # Expected structure: { winner: {category: count, ...}, ... }
    data = load_leet_winners() or {}

    # Extract metadata if present
    metadata = data.get("_metadata", {})
    start_date = metadata.get("statistics_started")

    # Aggregate counts per category -> list of (winner, count)
    per_category = {}
    for winner, categories in data.items():
        # Skip metadata entries
        if winner.startswith("_"):
            continue

        for cat, count in categories.items():
            if cat not in per_category:
                per_category[cat] = []
            per_category[cat].append((winner, count))

    # Sort each category desc by count, then by winner name for stability
    lines = []
    for cat, entries in per_category.items():
        top = sorted(entries, key=lambda x: (-x[1], x[0]))[:5]
        if top:
            formatted = ", ".join(f"{w} [{c}]" for w, c in top)
            lines.append(f"{cat}: {formatted}")

    _cat_map = {"first": "𝓮𝓴𝓪", "last": "𝓿𝓲𝓴𝓪", "multileet": "𝓶𝓾𝓵𝓽𝓲𝓵𝓮𝓮𝓽"}
    transformed = []
    for ln in lines:
        if ":" in ln:
            cat, rest = ln.split(":", 1)
            mapped = _cat_map.get(cat.strip().lower(), cat.strip())
            transformed.append(f"{mapped}: {rest.strip()}")
        else:
            transformed.append(ln)
    winners_text = "; ".join(transformed)

    # Build response with optional start date
    if winners_text:
        response = f"𝓛𝓮𝓮𝓽𝔀𝓲𝓷𝓷𝓮𝓻𝓼: {winners_text}"
        if start_date:
            response += f" (since {start_date})"
        return response
    else:
        if start_date:
            return f"No 𝓛𝓮𝓮𝓽𝔀𝓲𝓷𝓷𝓮𝓻𝓼 recorded yet (tracking since {start_date})."
        else:
            return "No 𝓛𝓮𝓮𝓽𝔀𝓲𝓷𝓷𝓮𝓻𝓼 recorded yet."


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
        logger.log(
            "🛑 Shutting down bot...",
            "INFO",
            fallback_text="[STOP] Shutting down bot...",
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


@command(
    name="kraks",
    command_type=CommandType.PUBLIC,
    description="Näytä krakit (juomasanat) ja niiden jakauma",
    usage="!kraks",
    admin_only=False,
)
def command_kraks(context, bot_functions):
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
    if stats.get("total_drink_words", 0) <= 0:
        # Find the earliest timestamp from drink tracking data
        data = _data_manager.load_drink_data()
        earliest_timestamp = None

        # Look through all servers and users for the earliest timestamp
        if "servers" in data:
            for server_data in data["servers"].values():
                if "nicks" in server_data:
                    for user_data in server_data["nicks"].values():
                        if "drink_words" in user_data:
                            for drink_data in user_data["drink_words"].values():
                                if (
                                    "timestamps" in drink_data
                                    and drink_data["timestamps"]
                                ):
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
                formatted_date = started_dt.strftime("%d.%m.%Y %H:%M")
                return f"Ei vielä krakkauksia tallennettuna. Tilastot aloitettu {formatted_date}."
            except (ValueError, KeyError):
                return "Ei vielä krakkauksia tallennettuna."
        else:
            return "Ei vielä krakkauksia tallennettuna."

    breakdown = drink.get_drink_word_breakdown(server_name)
    if breakdown:
        details = ", ".join(
            f"{word}: {count} [{top_user}]" for word, count, top_user in breakdown[:10]
        )
        return f"Krakit yhteensä: {stats['total_drink_words']}, {details}"
    else:
        top5 = ", ".join(
            [f"{nick}:{count}" for nick, count in stats.get("top_users", [])[:5]]
        )
        return f"Krakit yhteensä: {stats['total_drink_words']}. Top 5: {top5}"


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
    name="eurojackpot",
    command_type=CommandType.PUBLIC,
    description="Get Eurojackpot information",
    usage=(
        "!eurojackpot [next|tulokset|last|date <DD.MM.YY|DD.MM.YYYY|YYYY-MM-DD>|"
        "freq [--extended|--ext] [--limit N]|stats|hot|cold|pairs|trends|streaks|help]"
    ),
    admin_only=False,
)
def command_eurojackpot(context, bot_functions):
    """Get Eurojackpot lottery information."""
    try:
        args = [a.lower() for a in (context.args or [])]

        # Backwards-compatible branches
        if not args:
            from services.eurojackpot_service import get_eurojackpot_numbers

            # Default: next draw info (backwards-compatible)
            return get_eurojackpot_numbers()

        if args[0] in ["tulokset", "results", "viimeisin", "last"]:
            from services.eurojackpot_service import get_eurojackpot_results

            return get_eurojackpot_results()

        # Explicit next
        if args[0] in ["next", "seuraava"]:
            from services.eurojackpot_service import get_eurojackpot_numbers

            return get_eurojackpot_numbers()

        # Draw by date
        if args[0] in ["date", "päivä", "pvm"]:
            if len(context.args) < 2:
                return "Usage: !eurojackpot date <DD.MM.YY|DD.MM.YYYY|YYYY-MM-DD>"
            from services.eurojackpot_service import get_eurojackpot_service

            service = get_eurojackpot_service()
            res = service.get_draw_by_date(context.args[1])
            return res.get("message", "Eurojackpot: Virhe haussa")

        # Frequent numbers with flags
        if args[0] in ["freq", "frequency", "yleisimmat", "yleisimmät"]:
            from services.eurojackpot_service import get_eurojackpot_service

            service = get_eurojackpot_service()
            extended = any(a in ["--extended", "--ext"] for a in args[1:])
            # parse --limit N
            limit = None
            if "--limit" in args:
                try:
                    li = args.index("--limit")
                    limit = (
                        int(context.args[li + 1])
                        if li + 1 < len(context.args)
                        else None
                    )
                except Exception:
                    limit = None
            res = service.get_frequent_numbers(limit=limit or 10, extended=extended)
            return res.get("message", "📊 Virhe yleisimpien numeroiden haussa")

        # Database stats
        if args[0] in ["stats", "tietokanta"]:
            from services.eurojackpot_service import get_eurojackpot_service

            service = get_eurojackpot_service()
            res = service.get_database_stats()
            return res.get("message", "📊 Virhe tietokannan tilastoissa")

        # Analytics: hot/cold/pairs/trends/streaks
        if args[0] in ["hot", "cold", "pairs", "trends", "streaks", "analytics"]:
            from services.eurojackpot_service import get_eurojackpot_service

            service = get_eurojackpot_service()
            sub = args[0]
            # If 'analytics' used, expect a subtype
            if sub == "analytics":
                if len(args) < 2:
                    return (
                        "Usage: !eurojackpot analytics <hot|cold|pairs|trends|streaks>"
                    )
                sub = args[1]

            if sub == "hot":
                res = service.get_hot_cold_numbers(mode="hot")
                return res.get("message", "📊 Virhe hot-numeroissa")
            if sub == "cold":
                res = service.get_hot_cold_numbers(mode="cold")
                return res.get("message", "📊 Virhe cold-numeroissa")
            if sub == "pairs":
                res = service.get_common_pairs()
                return res.get("message", "📊 Virhe paritilastoissa")
            if sub == "trends":
                res = service.get_trends()
                return res.get("message", "📊 Virhe trendeissä")
            if sub == "streaks":
                res = service.get_streaks()
                return res.get("message", "📊 Virhe putkitilastoissa")

        if args[0] in ["scrape"]:
            from services.eurojackpot_service import get_eurojackpot_service

            service = get_eurojackpot_service()
            res = service.scrape_all_draws()
            return res.get("message", "Eurojackpot: Virhe haussa")

        if args[0] == "help":
            return (
                "Usage: !eurojackpot [next|tulokset|last|date <date>|freq [--extended] [--limit N]|"
                "stats|hot|cold|pairs|trends|streaks|help]"
            )

        # Fallback: treat as date
        from services.eurojackpot_service import get_eurojackpot_service

        service = get_eurojackpot_service()
        res = service.get_draw_by_date(context.args[0])
        return res.get("message", "Eurojackpot: Virhe haussa")

    except Exception as e:
        return f"❌ Eurojackpot error: {str(e)}"


# Moved from basic: weather and solar wind commands
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
        # Call the weather service - pass the location as the third parameter
        send_weather(irc_ctx, context.target, location)
        return CommandResponse.no_response()  # Weather service handles the output
    else:
        return "Weather service not available"


@command(
    "se",
    aliases=["sääennuste"],
    description="Short forecast (single line)",
    usage="!se [city] [hours]",
    examples=["!se", "!se Joensuu", "!se Joensuu 12"],
)
def short_forecast_command(context: CommandContext, bot_functions):
    """Return a single-line forecast using Meteosource free API."""
    try:
        from services.weather_forecast_service import format_single_line
    except Exception as e:
        return f"Forecast service not available: {e}"

    # Parse args: allow city with spaces and optional trailing integer hours
    text = context.args_text.strip() if context.args_text else ""
    city = None
    hours = None
    if text:
        parts = text.split()
        # If last token is an int, treat as hours
        try:
            cand = int(parts[-1])
            hours = cand if cand > 0 else None
            parts = parts[:-1]
        except Exception:
            pass
        city = " ".join(parts).strip() if parts else None

    try:
        line = format_single_line(city, hours)
    except Exception as e:
        return f"❌ Ennustevirhe: {e}"
    return line


@command(
    "sel",
    aliases=["sääennustelista"],
    description="Short forecast (multiple lines)",
    usage="!sel [city] [hours]",
    examples=["!sel", "!sel Joensuu 12"],
)
def short_forecast_list_command(context: CommandContext, bot_functions):
    """Return a multi-line forecast using Meteosource free API."""
    try:
        from services.weather_forecast_service import format_multi_line
    except Exception as e:
        return f"Forecast service not available: {e}"

    text = context.args_text.strip() if context.args_text else ""
    city = None
    hours = None
    if text:
        parts = text.split()
        try:
            cand = int(parts[-1])
            hours = cand if cand > 0 else None
            parts = parts[:-1]
        except Exception:
            pass
        city = " ".join(parts).strip() if parts else None

    try:
        lines = format_multi_line(city, hours)
    except Exception as e:
        return f"❌ Ennustevirhe: {e}"

    if context.is_console:
        return "\n".join(lines)
    # On IRC, send each line as separate notice if available
    notice = bot_functions.get("notice_message")
    irc = bot_functions.get("irc")
    target = context.target or context.sender
    if notice and irc:
        for ln in lines:
            notice(ln, irc, target)
        return CommandResponse.no_response()
    return "\n".join(lines)


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


@command(
    "otiedote",
    description="Get accident reports (Onnettomuustiedotteet) from local JSON",
    usage="!otiedote [N | #N | filter #channel *filter* *field*]",
    examples=[
        "!otiedote",
        "!otiedote 2",
        "!otiedote #2610",
        "!otiedote filter #joensuu Pohjois-Karjalan pelastuslaitos organization",
        "Fields: id, title, date, location, organization, content, units, url or * for all",
    ],
)
def otiedote_command(context: CommandContext, bot_functions):
    """Handle otiedote commands from local JSON."""
    otiedote_list = load_otiedote_json()
    if not otiedote_list:
        return "❌ No otiedote data available."

    # Latest release number (highest ID)
    latest_id = max(item["id"] for item in otiedote_list)

    # Handle filter subcommand
    if context.args and context.args[0].lower() == "filter":
        if len(context.args) < 3:
            return "❌ Usage: !otiedote filter #channel organization [field]"

        channel = context.args[1]
        if not channel.startswith("#"):
            return "❌ Channel must start with #"

        organization = context.args[2]
        field = context.args[3] if len(context.args) > 3 else "organization"

        # Load state.json
        config_obj = get_config()
        state_file = config_obj.state_file
        if os.path.exists(state_file):
            try:
                with open(state_file, "r", encoding="utf8") as f:
                    state = json.load(f)
            except Exception:
                state = {}
        else:
            state = {}

        # Ensure otiedote section exists
        if "otiedote" not in state:
            state["otiedote"] = {"latest_release": 0}

        if "filters" not in state["otiedote"]:
            state["otiedote"]["filters"] = {}

        # Add filter for channel
        if channel not in state["otiedote"]["filters"]:
            state["otiedote"]["filters"][channel] = []

        filter_entry = f"{organization}:{field}"
        if filter_entry not in state["otiedote"]["filters"][channel]:
            state["otiedote"]["filters"][channel].append(filter_entry)

        # Save state
        try:
            with open(state_file, "w", encoding="utf8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            return f"✅ Added filter for {channel}: {organization} (field: {field})"
        except Exception as e:
            return f"❌ Failed to save filter: {e}"

    # Current number (#) simply returns latest ID
    if context.args_text and context.args_text.strip() == "#":
        return f"Current otiedote release number: #{latest_id}"

    args_text = context.args_text.strip() if context.args_text else ""

    # !otiedote → show latest full description
    if not args_text:
        latest = max(otiedote_list, key=lambda x: x["id"])
        if latest["content"]:
            return f"📄 {latest['title']} | {latest['content']} URL: {latest['url']}"
        else:
            return f"📄 {latest['title']} URL: {latest['url']}"

    # !otiedote #<number> → show short description for specific release number
    if args_text.startswith("#"):
        try:
            number = int(args_text[1:])
            item = next((x for x in otiedote_list if x["id"] == number), None)
            if not item:
                return f"❌ Otiedote #{number} not found in local JSON."
            trimmed_content = trim_with_dots(item["content"])
            return f"📄 {item['title']} {trimmed_content} {item.get('location', '')} {item.get('date', '')} URL: {item['url']}"
        except ValueError:
            return "❌ Invalid number format. Usage: !otiedote #<number>"

    # !otiedote <N> → show Nth latest (1=latest)
    try:
        offset = int(args_text)
        if offset < 1 or offset > len(otiedote_list):
            return f"❌ Invalid number. Must be between 1 and {len(otiedote_list)}."
        sorted_list = sorted(otiedote_list, key=lambda x: x["id"], reverse=True)
        item = sorted_list[offset - 1]
        trimmed_content = trim_with_dots(item["content"])
        return f"📄 {item['title']} {trimmed_content} {item.get('location', '')} {item.get('date', '')} URL: {item['url']}"
    except ValueError:
        return "❌ Invalid argument. Usage: !otiedote [N | # | #N | filter #channel *filter* organization]"


@command(
    "wrap",
    description="Toggle text wrapping mode in TUI",
    usage="!wrap",
    examples=["!wrap"],
    scope=CommandScope.CONSOLE_ONLY,
)
def wrap_command(context: CommandContext, bot_functions):
    """Toggle text wrapping mode in TUI."""
    # Access the global TUI instance
    from tui import _current_tui

    if _current_tui is None:
        return "TUI not available"

    # Toggle the wrap mode
    _current_tui.toggle_wrap()
    return ""  # Return empty string since toggle_wrap already logs the change


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


# EOF
