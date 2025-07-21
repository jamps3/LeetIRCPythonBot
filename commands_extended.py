#!/usr/bin/env python3
"""
Extended Commands for LeetIRC Bot

Additional commands including scheduled messages, IPFS, and Eurojackpot functionality.
"""

import os
import re
from datetime import datetime

from command_registry import CommandType, command


@command(
    name="leets",
    command_type=CommandType.PUBLIC,
    description="Show recent leet detections",
    usage="!leets [limit]",
    admin_only=False,
)
def command_leets(context, args):
    """Show recent leet detection history."""
    from leet_detector import create_leet_detector

    limit = int(args[0]) if args and args[0].isdigit() else 5
    detector = create_leet_detector()
    history = detector.get_leet_history(limit=limit)

    if not history:
        return "No leet detections found."

    response_lines = ["🎉 Recent Leet Detections:"]
    for detection in history:
        date_str = datetime.fromisoformat(detection["datetime"]).strftime(
            "%d.%m %H:%M:%S"
        )
        user_msg_part = (
            f' "{detection["user_message"]}"' if detection["user_message"] else ""
        )
        response_lines.append(
            f"{detection['emoji']} {detection['achievement_name']} [{detection['nick']}] {detection['timestamp']}{user_msg_part} ({date_str})"
        )

    return "\n".join(response_lines)


from command_registry import CommandType, command


@command(
    name="schedule",
    command_type=CommandType.ADMIN,
    aliases=["leet"],
    description="Schedule a message to be sent at a specific time",
    usage="!schedule #channel HH:MM:SS[.microseconds] message",
    admin_only=True,
)
def command_schedule(context, args):
    """Schedule a message for later delivery."""
    if not args:
        return "Usage: !schedule #channel HH:MM:SS[.microseconds] message"

    # Parse the command format: !schedule #channel HH:MM:SS message
    # or !schedule #channel HH:MM:SS.microseconds message
    text = " ".join(args)
    match = re.match(
        r"(#\S+)\s+(\d{1,2}):(\d{1,2}):(\d{1,2})(?:\.(\d{1,6}))?\s+(.+)", text
    )

    if not match:
        return "Invalid format! Use: !schedule #channel HH:MM:SS[.microseconds] message"

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
def command_ipfs(context, args):
    """Handle IPFS file operations."""
    if not args:
        return "Usage: !ipfs add <url> or !ipfs <password> <url>"

    try:
        from services.ipfs_service import handle_ipfs_command

        # Reconstruct the full command
        command_text = "!ipfs " + " ".join(args)
        admin_password = os.getenv("ADMIN_PASSWORD")

        response = handle_ipfs_command(command_text, admin_password)
        return response

    except Exception as e:
        return f"❌ IPFS error: {str(e)}"


@command(
    name="eurojackpot",
    command_type=CommandType.PUBLIC,
    description="Get Eurojackpot information",
    usage="!eurojackpot [tulokset]",
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
    usage="!scheduled [list|cancel <id>]",
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
            return "Usage: !scheduled [list|cancel <id>]"

    except Exception as e:
        return f"❌ Scheduled messages error: {str(e)}"
