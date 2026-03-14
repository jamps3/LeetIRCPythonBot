"""
Word Tracking Commands Module

Contains word tracking commands: drink, kraks, drinkword, krakstats, tamagotchi, muunnos, etc.
"""

import json
import os
import random

from command_registry import CommandContext, CommandResponse, CommandType, command
from config import SANANMUUNNOKSET_FILE
from tamagotchi import TamagotchiBot

# Import lazy getters from word_tracking module directly
from word_tracking import DataManager, DrinkTracker, GeneralWords


# Get the shared singletons via lazy getters
def _get_data_manager():
    """Get or create the shared DataManager instance."""
    from config import get_config

    config = get_config()
    return DataManager(state_file=config.state_file)


def _get_drink_tracker():
    """Get or create the shared DrinkTracker instance."""
    return DrinkTracker(_get_data_manager())


def _get_general_words():
    """Get or create the shared GeneralWords instance."""
    return GeneralWords(_get_data_manager())


def _get_tamagotchi_bot():
    """Get or create the shared TamagotchiBot instance."""
    return TamagotchiBot(_get_data_manager())


# Module-level storage for lazy singleton instances
# These are set on first access via getters, not at import time
data_manager = None
general_words = None


# =====================
# Helper functions
# =====================


def _get_from_bot_functions(bot_functions, key, default_getter):
    """Get value from bot_functions dict, or use module-level singleton, or use default getter."""
    # First try bot_functions
    if bot_functions is not None:
        value = bot_functions.get(key)
        if value is not None:
            return value

    # Then try module-level singletons (for test compatibility)
    if key == "general_words" and general_words is not None:
        return general_words
    if key == "data_manager" and data_manager is not None:
        return data_manager
    if key == "drink_tracker" and data_manager is not None:
        return _get_drink_tracker()
    if key == "tamagotchi" and data_manager is not None:
        return _get_tamagotchi_bot()

    # Fall back to getter
    return default_getter()


# =====================
# topwords Command
# =====================


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

    # Get general_words and data_manager from bot_functions or use lazy getter
    words = _get_from_bot_functions(bot_functions, "general_words", _get_general_words)
    dm = _get_from_bot_functions(bot_functions, "data_manager", _get_data_manager)

    if args:  # User-specific top words
        nick = " ".join(args).strip()
        for server_name in dm.get_all_servers():
            user_stats = words.get_user_stats(server_name, nick)
            if user_stats.get("total_words", 0) > 0:
                top_words = words.get_user_top_words(server_name, nick, limit)
                word_list = ", ".join(
                    f"{word['word']}: {word['count']}" for word in top_words
                )
                return f"{nick}@{server_name}: {word_list}"
        return f"Käyttäjää '{nick}' ei löydy."
    else:  # Global top words across servers
        global_word_counts = {}
        for server_name in dm.get_all_servers():
            server_stats = words.get_server_stats(server_name)
            for word, count in server_stats.get("top_words", []):
                global_word_counts[word] = global_word_counts.get(word, 0) + count

        if global_word_counts:
            top_words = sorted(
                global_word_counts.items(), key=lambda x: x[1], reverse=True
            )[:limit]
            word_list = ", ".join(f"{word}: {count}" for word, count in top_words)
            return f"Top {limit} sanat: {word_list}"
        else:
            return "Ei vielä tilastoja saatavilla."


# =====================
# leaderboard Command
# =====================


@command(
    name="leaderboard",
    command_type=CommandType.PUBLIC,
    description="Show leaderboard of top users",
    usage="!leaderboard [drink|words]",
    admin_only=False,
)
def command_leaderboard(context, bot_functions):
    args = context.args or []
    board_type = args[0].lower() if args else "drink"

    # Get trackers from bot_functions or use lazy getters
    if board_type == "words":
        words = _get_from_bot_functions(
            bot_functions, "general_words", _get_general_words
        )
        dm = _get_from_bot_functions(bot_functions, "data_manager", _get_data_manager)
    else:
        # Default to drink tracker
        drink = _get_from_bot_functions(
            bot_functions, "drink_tracker", _get_drink_tracker
        )
        dm = _get_from_bot_functions(bot_functions, "data_manager", _get_data_manager)

    # Get all servers
    servers = dm.get_all_servers()

    if board_type == "words":
        # Word leaderboard
        all_users = []
        for server_name in servers:
            server_stats = words.get_server_stats(server_name)
            for user, stats in server_stats.get("users", {}).items():
                all_users.append(
                    {
                        "nick": user,
                        "server": server_name,
                        "total": stats.get("total_words", 0),
                    }
                )

        if not all_users:
            return "Ei vielä sanatilastoja saatavilla."

        all_users.sort(key=lambda x: x["total"], reverse=True)
        top_10 = all_users[:10]
        result = "Sanatilasto: " + ", ".join(
            f"{u['nick']}:{u['total']}" for u in top_10
        )
        return result

    else:
        # Drink leaderboard
        all_users = []
        for server_name in servers:
            server_stats = drink.get_server_stats(server_name)
            for user, stats in server_stats.get("top_users", []):
                all_users.append(
                    {
                        "nick": user,
                        "server": server_name,
                        "total": stats.get("total", 0),
                    }
                )

        if not all_users:
            return "Ei vielä juomatilastoja saatavilla."

        all_users.sort(key=lambda x: x["total"], reverse=True)
        top_10 = all_users[:10]
        result = "Juomaleaderi: " + ", ".join(
            f"{u['nick']}:{u['total']}" for u in top_10
        )
        return result


# =====================
# drinkword Command
# =====================


@command(
    name="drinkword",
    command_type=CommandType.PUBLIC,
    description="Add a custom drink word",
    usage="!drinkword <word> [drink_name]",
    admin_only=False,
)
def command_drinkword(context, bot_functions):
    drink = bot_functions.get("drink_tracker") or _get_drink_tracker()
    if not drink:
        return "Drink tracker ei ole käytettävissä."

    if not context.args:
        return "Käyttö: !drinkword <word> [drink_name]"

    # Parse arguments
    args = context.args
    word = args[0].lower()
    drink_name = " ".join(args[1:]) if len(args) > 1 else None

    if not drink_name:
        return "Käyttö: !drinkword <word> <drink_name>"

    # Derive server name
    server_name = (
        bot_functions.get("server_name")
        or getattr(context, "server_name", "console")
        or "console"
    )

    # Add the drink word mapping
    success = drink.add_drink_word_mapping(word, drink_name, server_name)

    if success:
        return f"✅ Lisätty: {word} -> {drink_name}"
    else:
        return f"Virhe lisättäessä: {word} -> {drink_name}"


# =====================
# drink Command
# =====================


@command(
    name="drink",
    command_type=CommandType.PUBLIC,
    description="Hae juomia nimen perusteella (tukee *-jokeria)",
    usage="!drink <juoman nimi>",
    admin_only=False,
)
def command_drink(context, bot_functions):
    drink = bot_functions.get("drink_tracker") or _get_drink_tracker()
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


# =====================
# kraks Command
# =====================


def _get_statistics_start_date():
    """Get the earliest timestamp from drink tracking data and format as dd.mm.yyyy."""
    data = _get_data_manager().load_drink_data()
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
    drink = bot_functions.get("drink_tracker") or _get_drink_tracker()
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


# =====================
# tamagotchi Command
# =====================


@command(
    name="tamagotchi",
    command_type=CommandType.PUBLIC,
    description="Tamagotchi virtual pet",
    usage="!tamagotchi [status|feed|play|stats]",
    admin_only=False,
)
def command_tamagotchi(context, bot_functions):
    """Show tamagotchi status or interact with it."""
    tamagotchi = bot_functions.get("tamagotchi") or _get_tamagotchi_bot()
    if not tamagotchi:
        return "Tamagotchi service is not available."

    # Get server name
    server_name = (
        bot_functions.get("server_name")
        or getattr(context, "server_name", "console")
        or "console"
    )
    nick = context.sender

    # Load state
    tamagotchi._load_state(data_manager)

    subcommand = context.args[0].lower() if context.args else "status"

    if subcommand == "status":
        return tamagotchi.get_status(nick, server_name)
    elif subcommand == "feed":
        return tamagotchi.feed(nick, server_name)
    elif subcommand == "play":
        return tamagotchi.play(nick, server_name)
    elif subcommand == "stats":
        return tamagotchi.get_detailed_stats(nick, server_name)
    else:
        return "Käyttö: !tamagotchi [status|feed|play|stats]"


# =====================
# feed Command
# =====================


@command(
    name="feed",
    command_type=CommandType.PUBLIC,
    description="Feed your tamagotchi",
    usage="!feed",
    admin_only=False,
)
def command_feed(context, bot_functions):
    """Feed your tamagotchi."""
    tamagotchi = bot_functions.get("tamagotchi") or _get_tamagotchi_bot()
    if not tamagotchi:
        return "Tamagotchi service is not available."

    # Get server name
    server_name = (
        bot_functions.get("server_name")
        or getattr(context, "server_name", "console")
        or "console"
    )
    nick = context.sender

    # Load state and feed
    tamagotchi._load_state(data_manager)
    return tamagotchi.feed(nick, server_name)


# =====================
# pet Command
# =====================


@command(
    name="pet",
    command_type=CommandType.PUBLIC,
    description="Pet your tamagotchi",
    usage="!pet",
    admin_only=False,
)
def command_pet(context, bot_functions):
    """Pet your tamagotchi."""
    tamagotchi = bot_functions.get("tamagotchi") or _get_tamagotchi_bot()
    if not tamagotchi:
        return "Tamagotchi service is not available."

    # Get server name
    server_name = (
        bot_functions.get("server_name")
        or getattr(context, "server_name", "console")
        or "console"
    )
    nick = context.sender

    # Load state and play/pet
    tamagotchi._load_state(data_manager)
    return tamagotchi.play(nick, server_name)


# =====================
# krak Command (alias for kraks)
# =====================


@command(
    name="krak",
    command_type=CommandType.PUBLIC,
    description="Set BAC calculation profile parameters or view current BAC",
    usage="!krak [weight_kg m/f] or !krak [burn_rate] or !krak [nickname] or !krak",
    admin_only=False,
)
def command_krak(context, bot_functions):
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

    # Check if arguments are provided for setting profile
    setting_message = None
    if context.args:
        # Try to parse profile settings
        if len(context.args) == 2:
            # Two args: weight_kg sex
            try:
                weight_kg = float(context.args[0])
                sex = context.args[1].lower()
                if sex in ["m", "f"]:
                    bac_tracker.set_user_profile(
                        server_name, context.sender, weight_kg=weight_kg, sex=sex
                    )
                    setting_message = f"✅ Set profile: {weight_kg}kg, {sex.upper()}"
                else:
                    return "❌ Invalid sex. Use 'm' or 'f'"
            except ValueError:
                return "❌ Invalid weight. Use a number for weight in kg"
        elif len(context.args) == 1:
            # One arg: could be burn_rate or nickname
            try:
                burn_rate = float(context.args[0])
                # Validate burn rate range
                if 0.05 <= burn_rate <= 1.0:
                    bac_tracker.set_user_profile(
                        server_name, context.sender, burn_rate=burn_rate
                    )
                    setting_message = f"✅ Set burn rate: {burn_rate}‰/h"
                else:
                    return "❌ Burn rate must be between 0.05 and 1.0 ‰/h"
            except ValueError:
                # Not a number, treat as nickname
                pass  # Will be handled below
        else:
            return "❌ Too many arguments. Use: !krak [weight_kg sex] or !krak [burn_rate] or !krak [nickname]"

    # Determine the target user (default to sender)
    target_nick = context.sender

    # Check if we have a nickname argument (single non-numeric argument)
    if context.args and len(context.args) == 1:
        potential_nick = context.args[0]
        try:
            float(potential_nick)
            # It's a number, already handled above
        except ValueError:
            if potential_nick.lower() not in ["m", "f"]:
                # Not a number and not sex, treat as nickname
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
        if setting_message:
            response = f"{setting_message}\n{response}"
        return response

    response_parts = []

    # Add setting confirmation if we set something
    if setting_message:
        response_parts.append(setting_message)

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
# sana Command
# =====================


@command(
    name="sana",
    command_type=CommandType.PUBLIC,
    description="Track a word",
    usage="!sana <word>",
    admin_only=False,
)
def command_sana(context, bot_functions):
    """Track a word usage."""
    words = bot_functions.get("general_words") or _get_general_words()
    if not words:
        return "General words tracker ei ole käytettävissä."

    if not context.args_text:
        return "Käyttö: !sana <sana>"

    # Get server name
    server_name = (
        bot_functions.get("server_name")
        or getattr(context, "server_name", "console")
        or "console"
    )

    word = context.args_text.strip().lower()
    nick = context.sender

    # Record word
    words.record_word(word, nick, server_name)

    # Get stats for the word
    stats = words.get_word_stats(server_name, word)
    if stats:
        return f"'{word}': {stats['count']} kertaa (top: {stats['top_user']})"
    else:
        return f"'{word}' tallennettu."


@command(
    name="assoc",
    command_type=CommandType.PUBLIC,
    description="Look up or manage word associations (format: word (thing))",
    usage="!assoc <word> [-sana | -add | -del | -list]",
    examples=[
        "!assoc sauna",
        "!assoc suklaa",
        "!assoc kahvi -list",
    ],
    admin_only=False,
)
def command_assoc(context, bot_functions):
    """Look up or manage word associations."""
    word_assoc = bot_functions.get("word_associations")
    if not word_assoc:
        return "Word associations ei ole käytettävissä."

    if not context.args_text:
        return "Käyttö: !assoc <sana> [-sana | -add | -del | -list]"

    args = context.args_text.strip().split()
    word = args[0].lower()

    # Check for flags
    has_list = "-list" in args or "-lista" in args
    has_add = "-add" in args or "-lisaa" in args
    has_del = "-del" in args or "-poista" in args

    if has_del:
        # Delete all associations for this word
        if word_assoc.delete_association(word):
            return f"Assosiaatiot sanalle '{word}' poistettu."
        else:
            return f"Assosiaatioita sanalle '{word}' ei löytynyt."

    if has_add:
        # Add a new association
        if len(args) < 2:
            return "Käyttö: !assoc <sana> -add <assoc>"
        association = " ".join(args[1:])
        if word_assoc.add_association(word, association):
            return f"Assosiaatio '{word}' -> '{association}' lisätty."
        return "Virhe lisättäessä assosiaatiota."

    # Default: look up associations
    associations = word_assoc.get_association(word)

    if has_list or not associations:
        # Show all associations for word or search
        if associations:
            return f"Assosiaatiot: {', '.join(associations)}"
        else:
            # Search for partial matches
            results = word_assoc.search_associations(word)
            if results:
                response_parts = []
                for w, assocs in list(results.items())[:5]:
                    response_parts.append(f"{w}: {', '.join(assocs)}")
                return " | ".join(response_parts)
            return f"Assosiaatioita sanalle '{word}' ei löytynyt."

    return f"{word}: {', '.join(associations)}"


# =====================
# Muunnos (Word Transformation) Helper Functions
# =====================


def _find_first_syllable(word):
    """Find the first syllable of a Finnish word."""
    vowels = "aeiouyäöåAEIOUYÄÖÅ"

    if not word:
        return "", ""

    if word[0] in vowels:
        # For vowel-starting words, the first syllable is the first vowel
        return word[0], word[1:]

    # For consonant-starting words
    for i, char in enumerate(word):
        if char in vowels:
            prefix = word[0] + word[i]
            if i + 1 < len(word) and word[i + 1] == char:
                prefix += char
            rest = word[len(prefix) :]  # noqa: E203
            return prefix, rest

    # No vowel found, return whole word as prefix
    return word, ""


def transform_phrase(input_text):
    """Apply transformation logic to input text."""
    from lemmatizer import analyze_word

    words = input_text.split()

    if len(words) == 1:
        # Single word: try to split into two Finnish words and transform
        word = words[0]
        if len(word) < 5:  # Need at least 5 chars for two words
            return word

        # Try to split into two valid Finnish words
        for i in range(2, len(word) - 2):
            part1 = word[:i]
            part2 = word[i:]
            if analyze_word(part1) and analyze_word(part2):
                # Found valid split, transform as phrase
                first_prefix, first_rest = _find_first_syllable(part1)
                last_prefix, last_rest = _find_first_syllable(part2)
                new_first = last_prefix + first_rest
                new_last = first_prefix + last_rest
                return new_first + new_last  # Combine without space

        # No valid split found
        return word

    elif len(words) >= 2:
        # Multiple words: apply the sananmuunnos transformation
        if len(words) == 2:
            # Swap between first and last words
            first_word = words[0]
            last_word = words[1]

            first_prefix, first_rest = _find_first_syllable(first_word)
            last_prefix, last_rest = _find_first_syllable(last_word)

            # Handle double vowels
            had_double = (
                first_prefix
                and len(first_prefix) > 1
                and first_prefix[-1] == first_prefix[-2]
            )
            had_double_last = (
                last_prefix
                and len(last_prefix) > 1
                and last_prefix[-1] == last_prefix[-2]
            )

            if had_double:
                first_prefix = first_prefix[:-1]
                if last_prefix and len(last_prefix) > 1 and not had_double_last:
                    last_prefix += last_prefix[-1]

            if had_double_last and not had_double:
                if (
                    first_prefix
                    and len(first_prefix) > 1
                    and not (first_prefix[-1] == first_prefix[-2])
                ):
                    first_prefix += first_prefix[-1]

            if had_double_last:
                last_prefix = last_prefix[:-1]

            new_first = last_prefix + first_rest
            new_last = first_prefix + last_rest

            new_words = [new_first, new_last]
        elif len(words) == 3:
            first_word = words[0]
            second_word = words[1]
            third_word = words[2]

            # Special case: if middle word is 'ja', swap first and third syllables
            if second_word.lower() == "ja":
                first_prefix, first_rest = _find_first_syllable(first_word)
                third_prefix, third_rest = _find_first_syllable(third_word)

                # Reduce first prefix if it ends with double vowel
                if (
                    first_prefix
                    and len(first_prefix) > 1
                    and first_prefix[-1] == first_prefix[-2]
                ):
                    first_prefix = first_prefix[:-1]

                new_first = third_prefix + first_rest
                new_third = first_prefix + third_rest

                new_words = [new_first, words[1], new_third]
            # Check if first and second words share the same beginning
            elif (
                len(first_word) >= 2
                and len(second_word) >= 2
                and first_word[:2] == second_word[:2]
            ):
                # Swap first and third words
                first_prefix, first_rest = _find_first_syllable(first_word)
                third_prefix, third_rest = _find_first_syllable(third_word)

                # Reduce first prefix if it ends with double vowel
                if (
                    first_prefix
                    and len(first_prefix) > 1
                    and first_prefix[-1] == first_prefix[-2]
                ):
                    first_prefix = first_prefix[:-1]

                new_first = third_prefix + first_rest
                new_third = first_prefix + third_rest

                new_words = [new_first, words[1], new_third]
            else:
                # Swap between first and second words only
                first_prefix, first_rest = _find_first_syllable(first_word)
                second_prefix, second_rest = _find_first_syllable(second_word)

                # Reduce first prefix if it ends with double vowel
                if (
                    first_prefix
                    and len(first_prefix) > 1
                    and first_prefix[-1] == first_prefix[-2]
                ):
                    first_prefix = first_prefix[:-1]

                new_first = second_prefix + first_rest
                new_second = first_prefix + second_rest

                new_words = [new_first, new_second, words[2]]
        else:
            # For more than 3 words, swap between first and last (original behavior)
            first_word = words[0]
            last_word = words[-1]

            first_prefix, first_rest = _find_first_syllable(first_word)
            last_prefix, last_rest = _find_first_syllable(last_word)

            # Reduce first prefix if it ends with double vowel
            if (
                first_prefix
                and len(first_prefix) > 1
                and first_prefix[-1] == first_prefix[-2]
            ):
                first_prefix = first_prefix[:-1]

            new_first = last_prefix + first_rest
            new_last = first_prefix + last_rest

            new_words = words[:]
            new_words[0] = new_first
            new_words[-1] = new_last

        result_phrase = " ".join(new_words)
        return result_phrase

    # Fallback: return original
    return input_text


def _send_muunnos_response(context: CommandContext, bot_functions, result: str):
    """Send muunnos response via notices (IRC) or return directly (console)."""
    if context.is_console:
        return result
    else:
        # IRC: send as notice to the channel where requested
        notice = bot_functions.get("notice_message")
        irc = bot_functions.get("irc")
        if notice and irc:
            # Send to the target (channel) where the command was issued
            target = context.target if context.target else context.sender
            notice(result, irc, target)
            return CommandResponse.no_response()
        return result


# =====================
# muunnos Command
# =====================


@command(
    "muunnos",
    description="Finnish word transformation (sananmuunnos)",
    usage='!muunnos [phrase|search <term>|add "original" "transformed"]',
    examples=[
        "!muunnos",
        "!muunnos hillittömästi mätti",
        "!muunnos search kalja",
        '!muunnos add "lokki kivellä" "kikki lovella"',
    ],
)
def muunnos_command(context: CommandContext, bot_functions):
    """Finnish word transformation using lookup table and algorithmic fallback."""
    # Load the transformation data
    data_file = SANANMUUNNOKSET_FILE
    try:
        with open(data_file, "r", encoding="utf-8") as f:
            transformations = json.load(f)
    except (FileNotFoundError, IOError) as e:
        result = f"Virhe ladattaessa sananmuunnoksia: {e}"
        return _send_muunnos_response(context, bot_functions, result)

    # Check for 'search' or 's' command
    if context.args and context.args[0].lower() in ("search", "s"):
        # 's' is shorthand for short mode search
        short_mode = context.args[0].lower() == "s"
        search_args = context.args[1:]

        if not search_args:
            result = "Usage: !muunnos search [-s] <term> - searches for transformations containing the term"
            return _send_muunnos_response(context, bot_functions, result)

        search_term = search_args[0].lower()
        matches = []
        for original, transformed in transformations.items():
            if search_term in original.lower() or search_term in transformed.lower():
                matches.append((original, transformed))

        if not matches:
            result = f'Ei löydy muunnoksia termillä: "{search_term}"'
            return _send_muunnos_response(context, bot_functions, result)

        if short_mode:
            # Short mode: one line, IRC-friendly
            # IRC message limit ~400 chars, format: "(24/6207): a→b, c→d, ..."
            total = len(transformations)
            found = len(matches)
            header = f"({found}/{total}):"

            # Build single line output
            remaining = 400 - len(header) - 4  # 4 for " ..." suffix
            result_parts = []
            for original, transformed in matches:
                entry = f"{original}→{transformed}"
                if (
                    len(header) + sum(len(p) + 2 for p in result_parts) + len(entry) + 4
                    <= remaining
                ):
                    result_parts.append(entry)
                else:
                    break

            result = header + " " + ", ".join(result_parts)
            if found > len(result_parts):
                result += f" ... [{found - len(result_parts)}]"

            return _send_muunnos_response(context, bot_functions, result)
        else:
            # Full mode: multi-line output
            # Limit to 10 results
            limited_matches = matches[:10]
            result_lines = [
                f'Hakutulokset termillä "{search_term}" ({len(matches)}/{len(transformations)}):'
            ]
            for original, transformed in limited_matches:
                result_lines.append(f"  {original} → {transformed}")

            if len(matches) > 10:
                result_lines.append(f"  ... ja {len(matches) - 10} lisää")

            result = "\n".join(result_lines)
            return _send_muunnos_response(context, bot_functions, result)

    # Check for 'add' command
    if context.args and context.args[0].lower() == "add":
        if len(context.args) < 3:
            result = 'Usage: !muunnos add "original phrase" "transformed phrase"'
            return _send_muunnos_response(context, bot_functions, result)

        # Parse quoted strings
        args_text = context.args_text
        if args_text.startswith('add "') and args_text.count('"') >= 4:
            # Extract the two quoted strings
            parts = args_text.split('"')
            if len(parts) >= 5:
                original = parts[1].strip()
                transformed = parts[3].strip()

                if original and transformed:
                    transformations[original] = transformed
                    # Save back to file
                    try:
                        with open(data_file, "w", encoding="utf-8") as f:
                            json.dump(transformations, f, ensure_ascii=False, indent=4)
                        result = (
                            f'✅ Added transformation: "{original}" → "{transformed}"'
                        )
                        return _send_muunnos_response(context, bot_functions, result)
                    except Exception as e:
                        result = f"Virhe tallennettaessa: {e}"
                        return _send_muunnos_response(context, bot_functions, result)
                else:
                    result = "Both original and transformed phrases must be non-empty."
                    return _send_muunnos_response(context, bot_functions, result)
        result = 'Usage: !muunnos add "original phrase" "transformed phrase"'
        return _send_muunnos_response(context, bot_functions, result)

    # If no arguments, return a random transformation
    if not context.args_text.strip():
        if not transformations:
            result = "Ei sananmuunnoksia saatavilla."
            return _send_muunnos_response(context, bot_functions, result)

        original = random.choice(list(transformations.keys()))
        transformed = transformations[original]
        result = f"{original} - {transformed}"
        return _send_muunnos_response(context, bot_functions, result)

    # If arguments provided, try to find exact match first
    input_text = context.args_text.strip()
    if input_text in transformations:
        transformed = transformations[input_text]
        result = f"{input_text} - {transformed}"
        return _send_muunnos_response(context, bot_functions, result)

    # Try algorithmic transformation for unknown inputs
    words = input_text.split()
    if len(words) == 1:
        # Single word: split into parts and try to transform
        word = words[0]
        if len(word) < 3:
            result = "Liian lyhyt sana muunnokseen."
            return _send_muunnos_response(context, bot_functions, result)

        # Split word into two parts (roughly half)
        mid = len(word) // 2
        part1 = word[:mid]
        part2 = word[mid:]

        # Try to find transformations for each part
        transformed_part1 = transformations.get(part1, part1)
        transformed_part2 = transformations.get(part2, part2)

        # Combine without space for single word transformation
        result_str = transformed_part1 + transformed_part2
        result = f"{word} - {result_str}"
        return _send_muunnos_response(context, bot_functions, result)

    elif len(words) >= 2:
        # Use the algorithmic transformation
        result_str = transform_phrase(input_text)
        if result_str != input_text:
            result = f"{input_text} - {result_str}"
            return _send_muunnos_response(context, bot_functions, result)

    # Fallback: try random transformations until one works
    max_attempts = 10
    for _ in range(max_attempts):
        random_original = random.choice(list(transformations.keys()))
        random_transformed = transformations[random_original]
        # Try to apply this transformation somehow - for now just return it
        result = f"{random_original} - {random_transformed}"
        return _send_muunnos_response(context, bot_functions, result)

    result = f"Ei löydy muunnosta: {input_text}"
    return _send_muunnos_response(context, bot_functions, result)


# =====================
# Krakstats Command
# =====================


@command(
    "krakstats",
    description="Show personal krak statistics",
    usage="!krakstats",
    examples=["!krakstats"],
)
def krakstats_command(context: CommandContext, bot_functions):
    """Show personal krak statistics for the user."""
    # Use injected drink tracker to ensure shared persistence
    drink = bot_functions.get("drink_tracker") or _get_drink_tracker()
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


# =====================
# Kraksdebug Command
# =====================


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


# Aliases for backwards compatibility with existing tests
topwords_command = command_topwords
leaderboard_command = command_leaderboard
drinkword_command = command_drinkword
drink_command = command_drink
kraks_command = command_kraks
tamagotchi_command = command_tamagotchi
feed_command = command_feed
pet_command = command_pet
krak_command = command_krak
sana_command = command_sana
assoc_command = command_assoc
