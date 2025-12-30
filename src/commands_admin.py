"""
Admin Commands for LeetIRCPythonBot

This module contains administrative commands that require password authentication.
"""

from command_registry import CommandContext, CommandScope, command
from config import get_config


def verify_admin_password(args):
    """Check if the first argument is the correct admin password."""
    if not args:
        return False

    config = get_config()
    return args[0] == config.admin_password


@command(
    "admin_quit",
    description="Quit IRC with message and shutdown bot (admin only)",
    usage="!admin_quit <password> [message]",
    examples=["!admin_quit mypass", "!admin_quit mypass Goodbye everyone!"],
    admin_only=True,
    requires_args=True,
    scope=CommandScope.CONSOLE_ONLY,
)
def admin_quit_command(context: CommandContext, bot_functions):
    """Quit IRC with an optional message and shutdown the bot."""
    if not verify_admin_password(context.args):
        return "❌ Invalid admin password"

    quit_message = " ".join(context.args[1:]) if len(context.args) > 1 else "Admin quit"

    # Set the custom quit message first for all servers
    set_quit_message_func = bot_functions.get("set_quit_message")
    if set_quit_message_func:
        set_quit_message_func(quit_message)

    # For admin quit, always trigger bot shutdown
    stop_event = bot_functions.get("stop_event")
    if stop_event:
        stop_event.set()

    if context.is_console:
        return f"🛑 Shutting down bot: {quit_message}"
    else:
        # Send IRC command
        irc = bot_functions.get("irc")
        if irc:
            # Use modern client interface
            if hasattr(irc, "send_raw") and callable(getattr(irc, "send_raw")):
                irc.send_raw(f"QUIT :{quit_message}")
            else:
                # Fallback: log intent if raw not available
                notice = bot_functions.get("notice_message")
                if notice:
                    notice(f"Sending QUIT: {quit_message}")

            log_func = bot_functions.get("log")
            if log_func:
                log_func(f"Admin quit with message: {quit_message}", "INFO")

            return ""  # Don't send a response since we're quitting
        else:
            return "❌ IRC connection not available"


@command(
    "openai",
    description="Set the OpenAI model (admin only)",
    usage="!openai <password> <model>",
    examples=["!openai mypass gpt-5-mini", "!openai mypass gpt-5"],
    admin_only=True,
    requires_args=True,
)
def openai_command(context: CommandContext, bot_functions):
    """Change the OpenAI model used by the GPT service.

    Requires admin password as the first argument and model name as the second.
    """
    if not verify_admin_password(context.args):
        return "❌ Invalid admin password"

    if len(context.args) < 2:
        return "❌ Usage: !openai <password> <model>"

    model = context.args[1]

    # Use bot function to set the model so it updates runtime and persists
    setter = bot_functions.get("set_openai_model")
    if not setter:
        return "❌ Cannot change model: setter not available"

    result = setter(model)

    # In IRC, prefer sending a NOTICE to the caller; in console, return string
    if context.is_console:
        return result
    else:
        # Send private notice to the sender if available
        notice = bot_functions.get("notice_message")
        irc = bot_functions.get("irc")
        to_target = context.sender or context.target
        if notice and irc and to_target:
            notice(result, irc, to_target)
            return ""
        return result


@command(
    "scheduled",
    description="List or cancel scheduled messages (admin only)",
    usage="!scheduled <password> <list|cancel> [message_id]",
    examples=[
        "!scheduled mypass list",
        "!scheduled mypass cancel scheduled_1712345678_0",
    ],
    admin_only=True,
    requires_args=True,
)
def scheduled_command(context: CommandContext, bot_functions):
    """Manage scheduled messages (admin password required on IRC; optional on console)."""
    try:
        # Determine how to handle password based on context
        args = list(context.args or [])
        if context.is_console:
            # Console: allow optional password. If the first arg matches the password, strip it
            if verify_admin_password(args):
                args = args[1:]
        else:
            # IRC: require password as first argument
            if not verify_admin_password(args):
                return "❌ Invalid admin password"
            args = args[1:]

        from services.scheduled_message_service import get_scheduled_message_service

        service = get_scheduled_message_service()

        # Process sub-commands using args
        if not args or args[0].lower() == "list":
            # List scheduled messages
            messages = service.list_scheduled_messages()
            if not messages:
                return "📅 No messages currently scheduled"

            result = "📅 Scheduled messages:\n"
            for msg_id, info in messages.items():
                chan = info.get("channel", "?") if isinstance(info, dict) else "?"
                msg = info.get("message", "") if isinstance(info, dict) else str(info)
                t = None
                if isinstance(info, dict):
                    t = info.get("target_time") or info.get("target_display")
                result += f"• {msg_id}: '{msg}' to {chan} at {t or '?'}\n"

            return result.strip()

        if args[0].lower() == "cancel" and len(args) > 1:
            # Cancel a scheduled message
            message_id = args[1]
            if service.cancel_message(message_id):
                return f"✅ Cancelled scheduled message: {message_id}"
            else:
                return f"❌ Message not found: {message_id}"

        return "Usage: !scheduled <password> list|cancel <id>"

    except Exception as e:
        return f"❌ Scheduled messages error: {str(e)}"


@command(
    "ops",
    description="Give operator status (+o) to all users in channel",
    usage="!ops",
    examples=["!ops"],
    admin_only=False,
    requires_args=False,
)
def ops_command(context: CommandContext, bot_functions):
    """Give operator status (+o) to all users in the current channel."""
    # This command must be used in a channel
    if not context.target or not context.target.startswith("#"):
        return "❌ This command must be used in a channel"

    # Check if command is allowed in this channel
    config = get_config()
    allowed_channels = getattr(config, "ops_allowed_channels", [])
    if allowed_channels and context.target.lower() not in [
        ch.lower() for ch in allowed_channels
    ]:
        return f"❌ !ops command not allowed in this channel. Allowed channels: {', '.join(allowed_channels)}"

    # Get bot manager to set up pending ops
    bot_manager = bot_functions.get("bot_manager")
    if not bot_manager:
        return "❌ Bot manager not available"

    # Get IRC connection
    irc = bot_functions.get("irc")
    if not irc:
        return "❌ IRC connection not available"

    try:
        channel = context.target
        server_name = context.server_name

        # Initialize pending ops data structure for this server/channel
        if not hasattr(bot_manager, "_pending_ops"):
            bot_manager._pending_ops = {}
        if server_name not in bot_manager._pending_ops:
            bot_manager._pending_ops[server_name] = {}
        if channel not in bot_manager._pending_ops[server_name]:
            bot_manager._pending_ops[server_name][channel] = {"users": []}

        # Send NAMES command to get user list, response will be handled asynchronously
        if hasattr(irc, "send_raw"):
            irc.send_raw(f"NAMES {channel}")
        else:
            irc.send(f"NAMES {channel}")

    except Exception as e:
        return f"❌ Error requesting operator status: {str(e)}"


@command(
    "leetwinnersreset",
    description="Reset leetwinners statistics (admin only)",
    usage="!leetwinnersreset <password>",
    examples=["!leetwinnersreset mypass"],
    admin_only=True,
    requires_args=True,
)
def leetwinners_reset_command(context: CommandContext, bot_functions):
    """Reset leetwinners statistics and set new start date."""
    if not verify_admin_password(context.args):
        return "❌ Invalid admin password"

    if len(context.args) < 1:
        return "❌ Usage: !leetwinnersreset <password>"

    try:
        from datetime import datetime

        # Get save function from bot_functions
        save_leet_winners = bot_functions.get("save_leet_winners")
        if not save_leet_winners:
            return "❌ Leet winners service not available"

        # Create empty data with start date
        current_date = datetime.now().strftime("%d.%m.%Y")
        reset_data = {
            "_metadata": {
                "statistics_started": current_date,
                "last_reset": current_date,
            }
        }

        # Save the reset data
        save_leet_winners(reset_data)

        return f"✅ Leetwinners statistics reset successfully. New tracking period started: {current_date}"

    except Exception as e:
        return f"❌ Error resetting leetwinners: {str(e)}"


# Import this module to register the commands
def register_admin_commands():
    """Register all admin commands. Called automatically when module is imported."""
    pass


# Auto-register when imported
register_admin_commands()
