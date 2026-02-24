"""
Miscellaneous Commands Module

Contains misc commands: 420, kaiku, muunnos, matka, np, quote, leets, etc.

Note: Some commands depend on shared helpers in commands.py - they are imported as needed.
"""

import random
from datetime import datetime

from command_registry import CommandContext, command

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

    # Handle different argument patterns
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
# Placeholder commands - these need more work to extract
# =====================

# muunnos_command - depends on Finnish word transformation helpers
# quote_command - depends on quote file loading
# leets_command - depends on leet detector
# matka_command - depends on OSRM API
# schedule command - depends on scheduled_message_service
# ipfs command - depends on IPFS service

# For now, these will be imported from commands.py via the fallback mechanism
