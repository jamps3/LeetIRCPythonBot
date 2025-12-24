"""
Extended Commands Module

Contains extended user commands for word tracking, statistics, games, and utilities
extracted from commands.py.
"""

import json
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
    description="Näytä krakit (juomasanat) ja niiden jakauma, tai resetoi BAC",
    usage="!kraks [reset]",
    admin_only=False,
)
def command_kraks(context, bot_functions):
    # Check for reset subcommand
    if context.args and context.args[0].lower() == "reset":
        # Get the BAC tracker
        bot_manager = bot_functions.get("bot_manager")
        if not bot_manager or not hasattr(bot_manager, "bac_tracker"):
            return "❌ BAC tracker not available"

        bac_tracker = bot_manager.bac_tracker

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
            bot_manager = bot_functions.get("bot_manager")
            if bot_manager:
                servers = getattr(bot_manager, "servers", {})
                server = server_name or (list(servers.values())[0] if servers else None)
            else:
                server = server_name

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
def kraksdebug_command(context, bot_functions):
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
    "krakstats",
    description="Show personal krak statistics",
    usage="!krakstats",
    examples=["!krakstats"],
)
def krakstats_command(context, bot_functions):
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
    "krak",
    description="Set BAC calculation profile or view current BAC",
    usage="!krak [weight_kg m/f | burn_rate] or !krak (view current BAC)",
    examples=["!krak 75 m", "!krak 0.15", "!krak"],
    admin_only=False,
)
def krak_command(context, bot_functions):
    """Set BAC calculation profile parameters or view current BAC.

    Usage:
    - !krak weight_kg m/f : Set weight and sex for personalized BAC calculation
    - !krak burn_rate : Set custom burn rate in ‰ per hour
    - !krak : View current BAC information
    """
    # Get the BAC tracker
    bot_manager = bot_functions.get("bot_manager")
    if not bot_manager or not hasattr(bot_manager, "bac_tracker"):
        return "❌ BAC tracker not available"

    bac_tracker = bot_manager.bac_tracker

    # Derive server name
    server_name = (
        bot_functions.get("server_name")
        or getattr(context, "server_name", "console")
        or "console"
    )

    nick = context.sender

    if not context.args:
        # No arguments - show current BAC
        bac_info = bac_tracker.get_user_bac(server_name, nick)
        profile = bac_tracker.get_user_profile(server_name, nick)

        # Get last drink grams from stored data
        bac_data = bac_tracker._load_bac_data()
        user_key = f"{server_name}:{nick}"
        user_data = bac_data.get(user_key, {})
        last_drink_grams = user_data.get("last_drink_grams")

        if bac_info["current_bac"] == 0.0 and not any(profile.values()):
            response = "🍺 No BAC data yet. Use !krak <weight_kg> <m/f> to set your profile for accurate calculations."
            # Include last drink alcohol content even when no profile
            if last_drink_grams:
                response += f" | Last: {last_drink_grams:.1f}g"
            return response

        response_parts = []

        # Show current BAC if any
        if bac_info["current_bac"] > 0.0:
            sober_time = bac_info.get("sober_time", "Unknown")
            driving_time = bac_info.get("driving_time")
            response_parts.append(f"🍺 Current BAC: {bac_info['current_bac']:.2f}‰")

            # Include last drink alcohol content if available
            if last_drink_grams:
                response_parts.append(f"Last: {last_drink_grams:.1f}g")

            if sober_time:
                response_parts.append(f"Sober by: ~{sober_time}")

            if driving_time:
                response_parts.append(f"Driving: ~{driving_time}")

        # Show profile info
        profile_info = []
        if (
            profile.get("weight_kg")
            and profile.get("weight_kg") != bac_tracker.DEFAULT_WEIGHT_KG
        ):
            profile_info.append(f"Weight: {profile['weight_kg']}kg")
        if profile.get("sex"):
            profile_info.append(f"Sex: {'Male' if profile['sex'] == 'm' else 'Female'}")
        if profile.get("burn_rate") and profile.get(
            "burn_rate"
        ) != bac_tracker._get_default_burn_rate(profile.get("sex", "m")):
            profile_info.append(f"Burn rate: {profile['burn_rate']}‰/h")

        if profile_info:
            response_parts.append(f"Profile: {', '.join(profile_info)}")
        else:
            response_parts.append(
                "Using default profile (75kg, male, standard burn rate)"
            )

        return " | ".join(response_parts)

    # Parse arguments
    args = context.args

    if len(args) == 2:
        # Check if it's weight + sex format: number + m/f
        try:
            weight = float(args[0])
            sex = args[1].lower()

            if sex not in ["m", "f"]:
                return "❌ Sex must be 'm' (male) or 'f' (female)"

            if weight < 30 or weight > 300:
                return "❌ Weight must be between 30-300 kg"

            # Set weight and sex
            bac_tracker.set_user_profile(server_name, nick, weight_kg=weight, sex=sex)

            # Get the calculated burn rate (now weight-based)
            profile = bac_tracker.get_user_profile(server_name, nick)
            calculated_burn_rate = profile["burn_rate"]

            return f"✅ BAC profile set: {weight}kg, {sex.upper()} (burn rate: {calculated_burn_rate}‰/h)"

        except ValueError:
            return "❌ Invalid weight format. Use: !krak <weight_kg> <m/f>"

    elif len(args) == 1:
        # Check if it's a burn rate: just a number
        try:
            burn_rate = float(args[0])

            if burn_rate < 0.05 or burn_rate > 1.0:
                return "❌ Burn rate must be between 0.05-1.0 ‰ per hour"

            # Set custom burn rate
            bac_tracker.set_user_profile(server_name, nick, burn_rate=burn_rate)

            return f"✅ BAC burn rate set to {burn_rate}‰/h"

        except ValueError:
            return (
                "❌ Invalid number format. Use: !krak <burn_rate> for custom burn rate"
            )

    else:
        return "❌ Usage: !krak [weight_kg m/f | burn_rate] or !krak (view current BAC)"
