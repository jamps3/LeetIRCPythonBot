"""
Unified Commands Module for LeetIRC Bot

This module merges the functionality of commands_basic.py and commands_extended.py
into a single source of truth (commands.py). The legacy modules are converted to
thin shims that re-export from here to preserve backwards compatibility.
"""

import os
import re
import time
from datetime import datetime

from command_registry import (
    CommandContext,
    CommandResponse,
    CommandScope,
    CommandType,
    command,
)
from config import get_config

# Utilities (some commands/services may rely on these via bot_functions)
# Kept aligned with legacy modules to avoid lint/config churn.
from utils import fetch_title_improved, split_message_intelligently  # noqa: F401

# Word tracking system (extended features)
from word_tracking import DataManager, DrinkTracker, GeneralWords, TamagotchiBot

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
    description="Show global leaderboard",
    usage="!leaderboard",
    admin_only=False,
)
def command_leaderboard(context, bot_functions):
    global_user_counts = {}

    for server_name in data_manager.get_all_servers():
        leaderboard = general_words.get_leaderboard(server_name, 100)
        for user in leaderboard:
            user_key = f"{user['nick']}@{server_name}"
            global_user_counts[user_key] = (
                global_user_counts.get(user_key, 0) + user["total_words"]
            )

    if global_user_counts:
        top_users = sorted(
            global_user_counts.items(), key=lambda x: x[1], reverse=True
        )[:5]
        leaderboard_msg = ", ".join(f"{nick}: {count}" for nick, count in top_users)
        return f"Aktiivisimmat käyttäjät (globaali): {leaderboard_msg}"
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
    return f"{query}: {total}{(', ' + details_text) if details_text else ''}"


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
        return "Usage: !schedule #channel HH:MM:SS<.microsecs> message"

    # Parse the command format: !schedule #channel HH:MM:SS message
    # or !schedule #channel HH:MM:SS.<1..9 digits> message
    text = " ".join(args)
    match = re.match(
        r"(#\S+)\s+(\d{1,2}):(\d{1,2}):(\d{1,2})(?:\.(\d{1,9}))?\s+(.+)", text
    )

    if not match:
        return "Invalid format! Use: !schedule #channel HH:MM:SS<.microsecs> message"

    channel = match.group(1)
    hour = int(match.group(2))
    minute = int(match.group(3))
    second = int(match.group(4))
    frac_str = match.group(5)  # up to 9 digits (nanoseconds resolution in input)
    message = match.group(6)

    # Convert fractional seconds (up to 9 digits) to microseconds for scheduling
    if frac_str:
        ns_str = frac_str.ljust(9, "0")[:9]  # normalize to exactly 9 digits for display
        # Convert nanoseconds to microseconds (floor) for datetime compatibility
        microsecond = min(999999, int(ns_str[:6]))
    else:
        ns_str = "000000000"
        microsecond = 0

    # Validate time values
    if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
        return "Invalid time! Hour: 0-23, Minute: 0-59, Second: 0-59"

    try:
        # Get the scheduled message service
        from services.scheduled_message_service import send_scheduled_message_ns

        # Retrieve the IRC/server object from bot_functions
        server = bot_functions.get("server")

        if not server:
            return "❌ Server context not available for scheduling"

        # Convert 9-digit fraction to nanoseconds and schedule
        nanosecond = int(ns_str)
        message_id = send_scheduled_message_ns(
            server, channel, message, hour, minute, second, nanosecond
        )

        # Show the requested time with 9-digit fractional part (as in logs)
        return f"✅ Message scheduled with ID: {message_id} for {hour:02d}:{minute:02d}:{second:02d}.{ns_str}"

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


@command(
    name="scheduled",
    command_type=CommandType.ADMIN,
    description="List or cancel scheduled messages",
    usage="!scheduled <password> list|cancel <id>",
    admin_only=True,
)
def command_scheduled(context, bot_functions):
    """Manage scheduled messages (admin password required)."""
    try:
        # Verify admin password as first argument, but allow console usage without it
        from commands_admin import verify_admin_password

        require_password = not getattr(context, "is_console", False)
        if require_password and not verify_admin_password(context.args or []):
            return "❌ Invalid admin password"

        from services.scheduled_message_service import get_scheduled_message_service

        service = get_scheduled_message_service()

        # Determine sub-arguments (skip password only when required)
        full_args = context.args or []
        sub_args = full_args[1:] if require_password else full_args
        if not sub_args or sub_args[0].lower() == "list":
            # List scheduled messages
            messages = service.list_scheduled_messages()
            if not messages:
                return "📅 No messages currently scheduled"

            result = "📅 Scheduled messages:\n"
            for msg_id, info in messages.items():
                result += f"• {msg_id}: '{info['message']}' to {info['channel']} at {info['target_time']}\n"

            return result.strip()

        elif sub_args[0].lower() == "cancel" and len(sub_args) > 1:
            # Cancel a scheduled message
            message_id = sub_args[1]
            if service.cancel_message(message_id):
                return f"✅ Cancelled scheduled message: {message_id}"
            else:
                return f"❌ Message not found: {message_id}"

        else:
            return "Usage: !scheduled <password> list|cancel <id>"

    except Exception as e:
        return f"❌ Scheduled messages error: {str(e)}"


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
        # Call the weather service
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


# EOF
