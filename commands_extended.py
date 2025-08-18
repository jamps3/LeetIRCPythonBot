#!/usr/bin/env python3
"""
Extended Commands for LeetIRC Bot

This module contains more complex commands including word tracking, drink statistics,
scheduled messages, IPFS, and Eurojackpot functionality.
"""

import os
import re
from datetime import datetime

from command_registry import CommandContext, CommandResponse, CommandType, command
from utils import fetch_title_improved, split_message_intelligently

# Import word tracking system
from word_tracking import DataManager, DrinkTracker, GeneralWords, TamagotchiBot

# Initialize word tracking system
data_manager = DataManager()
drink_tracker = DrinkTracker(data_manager)
general_words = GeneralWords(data_manager)
tamagotchi_bot = TamagotchiBot(data_manager)


@command(
    name="sana",
    command_type=CommandType.PUBLIC,
    description="Search word statistics",
    usage="!sana <sana>",
    admin_only=False,
)
def command_sana(context, args):
    if context.args:
        search_word = " ".join(context.args).strip().lower()
        results = general_words.search_word(search_word)

        if results["total_occurrences"] > 0:
            all_users = []
            for server_name, server_data in results["servers"].items():
                for user in server_data["users"]:
                    all_users.append(f"{user['nick']}@{server_name}: {user['count']}")

            if all_users:
                users_text = ", ".join(all_users)
                return f"Sana '{search_word}' on sanottu: {users_text}"
            else:
                return f"Kukaan ei ole sanonut sanaa '{search_word}' vielä."
        else:
            return f"Kukaan ei ole sanonut sanaa '{search_word}' vielä."
    else:
        return "Käytä komentoa: !sana <sana>"


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
    command_type=CommandType.PRIVATE,
    description="Show top words used",
    usage="!topwords <nick>",
    admin_only=False,
)
def command_topwords(context, bot_functions):
    if context.args:
        nick = " ".join(context.args).strip()
        found_user = False
        for server_name in data_manager.get_all_servers():
            user_stats = general_words.get_user_stats(server_name, nick)
            if user_stats["total_words"] > 0:
                top_words = general_words.get_user_top_words(server_name, nick, 5)
                word_list = ", ".join(
                    f"{word['word']}: {word['count']}" for word in top_words
                )
                return f"{nick}@{server_name}: {word_list}"
                found_user = True

        if not found_user:
            return f"Käyttäjää '{nick}' ei löydy."
    else:
        global_word_counts = {}
        for server_name in data_manager.get_all_servers():
            server_stats = general_words.get_server_stats(server_name)
            for word, count in server_stats["top_words"]:
                global_word_counts[word] = global_word_counts.get(word, 0) + count

        if global_word_counts:
            top_words = sorted(
                global_word_counts.items(), key=lambda x: x[1], reverse=True
            )[:5]
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
def command_leaderboard(context, args):
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
    drink = bot_functions.get("drink_tracker")
    if not drink:
        return "Drink tracker ei ole käytettävissä."

    if not context.args:
        return "Käyttö: !drinkword <juomasana>"

    server_name = bot_functions.get("server_name") or getattr(context, "server_name", "console") or "console"
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
    drink = bot_functions.get("drink_tracker")
    if not drink:
        return "Drink tracker ei ole käytettävissä."

    if not context.args_text:
        return "Käyttö: !drink <juoman nimi>"

    server_name = bot_functions.get("server_name") or getattr(context, "server_name", "console") or "console"
    query = context.args_text.strip()

    results = drink.search_specific_drink(query, server_filter=server_name)
    total = results.get("total_occurrences", 0)
    if total <= 0:
        return f"Ei osumia juomalle '{query}'."

    # Summarize by drink word and top users
    drink_words = results.get("drink_words", {})
    words_part = ", ".join([f"{w}:{c}" for w, c in sorted(drink_words.items(), key=lambda x: x[1], reverse=True)[:5]])
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
    drink = bot_functions.get("drink_tracker")
    if not drink:
        return "Drink tracker ei ole käytettävissä."

    # Derive server name (works for both IRC and console)
    server_name = bot_functions.get("server_name") or getattr(context, "server_name", "console") or "console"

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
        top5 = ", ".join([f"{nick}:{count}" for nick, count in stats.get("top_users", [])[:5]])
        return f"Krakit yhteensä: {stats['total_drink_words']}. Top 5: {top5}"


@command(
    name="tamagotchi",
    command_type=CommandType.PUBLIC,
    description="Shows tamagotchi status",
    usage="!tamagotchi",
    admin_only=False,
)
def command_tamagotchi(context, args):
    console_server = "console"
    status = tamagotchi_bot.get_status(console_server)
    return status


@command(
    name="feed",
    command_type=CommandType.PUBLIC,
    description="Feed your Tamagotchi",
    usage="!feed <food>",
    admin_only=False,
)
def command_feed(context, args):
    food = context.args_text.strip() if context.args_text else None
    console_server = "console"
    response = tamagotchi_bot.feed(console_server, food)
    return response


@command(
    name="pet",
    command_type=CommandType.PUBLIC,
    description="Pet your Tamagotchi",
    usage="!pet",
    admin_only=False,
)
def command_pet(context, args):
    console_server = "console"
    response = tamagotchi_bot.pet(console_server)
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
    usage="!schedule #channel HH:MM:SS<.microseconds> message",
    admin_only=True,
)
def command_schedule(context, args):
    """Schedule a message for later delivery."""
    if not args:
        return "Usage: !schedule #channel HH:MM:SS<.microseconds> message"

    # Parse the command format: !schedule #channel HH:MM:SS message
    # or !schedule #channel HH:MM:SS.microseconds message
    text = " ".join(args)
    match = re.match(
        r"(#\S+)\s+(\d{1,2}):(\d{1,2}):(\d{1,2})(?:\.(\d{1,6}))?\s+(.+)", text
    )

    if not match:
        return "Invalid format! Use: !schedule #channel HH:MM:SS<.microseconds> message"

    channel = match.group(1)
    hour = int(match.group(2))
    minute = int(match.group(3))
    second = int(match.group(4))
    microsecond_str = match.group(5)
    message = match.group(6)

    # Convert microseconds
    if microsecond_str:
        # Pad or truncate to 6 digits
        microsecond = int(microsecond_str.ljust(6, "0")[:6])
    else:
        microsecond = 0

    # Validate time values
    if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
        return "Invalid time! Hour: 0-23, Minute: 0-59, Second: 0-59"

    try:
        # Get the scheduled message service
        from services.scheduled_message_service import send_scheduled_message

        server = context.get("server")

        if not server:
            return "❌ Server context not available for scheduling"

        # Schedule the message
        message_id = send_scheduled_message(
            server, channel, message, hour, minute, second, microsecond
        )

        return f"✅ Message scheduled with ID: {message_id} for {hour:02d}:{minute:02d}:{second:02d}.{microsecond:06d}"

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
    usage="!eurojackpot <tulokset>",
    admin_only=False,
)
def command_eurojackpot(context, args):
    """Get Eurojackpot lottery information."""
    try:
        # Check if user wants results or next draw info
        if args and args[0].lower() in ["tulokset", "results", "viimeisin"]:
            from services.eurojackpot_service import get_eurojackpot_results

            return get_eurojackpot_results()
        else:
            from services.eurojackpot_service import get_eurojackpot_numbers

            return get_eurojackpot_numbers()

    except Exception as e:
        return f"❌ Eurojackpot error: {str(e)}"


@command(
    name="scheduled",
    command_type=CommandType.ADMIN,
    description="List or cancel scheduled messages",
    usage="!scheduled list|cancel <id>",
    admin_only=True,
)
def command_scheduled(context, args):
    """Manage scheduled messages."""
    try:
        from services.scheduled_message_service import get_scheduled_message_service

        service = get_scheduled_message_service()

        if not args or args[0].lower() == "list":
            # List scheduled messages
            messages = service.list_scheduled_messages()
            if not messages:
                return "📅 No messages currently scheduled"

            result = "📅 Scheduled messages:\n"
            for msg_id, info in messages.items():
                result += f"• {msg_id}: '{info['message']}' to {info['channel']} at {info['target_time']}\n"

            return result.strip()

        elif args[0].lower() == "cancel" and len(args) > 1:
            # Cancel a scheduled message
            message_id = args[1]
            if service.cancel_message(message_id):
                return f"✅ Cancelled scheduled message: {message_id}"
            else:
                return f"❌ Message not found: {message_id}"

        else:
            return "Usage: !scheduled list|cancel <id>"

    except Exception as e:
        return f"❌ Scheduled messages error: {str(e)}"
