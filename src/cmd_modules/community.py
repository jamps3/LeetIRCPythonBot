"""Community and channel management commands."""

from __future__ import annotations

from datetime import datetime, timezone

from command_registry import CommandContext, CommandType, command
from services.community_state_service import DEFAULT_FEATURES, parse_poll_create


def _service(bot_functions):
    service = bot_functions.get("community_state")
    if not service:
        raise RuntimeError("Community state service is not available")
    return service


def _server_channel(context: CommandContext) -> tuple[str, str] | str:
    if context.is_console or not context.target or not context.target.startswith("#"):
        return "This command must be used in a channel."
    return context.server_name, context.target


@command(
    "feature",
    aliases=["features"],
    description="Show or toggle per-channel bot features",
    usage="!feature [name on|off]",
    examples=["!feature", "!feature youtube off", "!feature gpt_history on"],
    command_type=CommandType.PUBLIC,
)
def feature_command(context: CommandContext, bot_functions):
    scope = _server_channel(context)
    if isinstance(scope, str):
        return scope
    server_name, channel = scope
    service = _service(bot_functions)

    if not context.args:
        features = service.get_channel_features(server_name, channel)
        return "Features: " + ", ".join(
            f"{name}={'on' if enabled else 'off'}"
            for name, enabled in sorted(features.items())
        )

    if len(context.args) != 2:
        return "Usage: !feature [name on|off]"

    feature = context.args[0].lower()
    value = context.args[1].lower()
    if feature not in DEFAULT_FEATURES:
        return "Known features: " + ", ".join(sorted(DEFAULT_FEATURES))
    if value not in ("on", "off", "true", "false", "1", "0", "yes", "no"):
        return "Use on or off."

    enabled = value in ("on", "true", "1", "yes")
    service.set_feature(server_name, channel, feature, enabled)
    return f"{feature} is now {'on' if enabled else 'off'} for {channel}."


@command(
    "metrics",
    description="Show channel observability counters",
    usage="!metrics",
    command_type=CommandType.PUBLIC,
)
def metrics_command(context: CommandContext, bot_functions):
    scope = _server_channel(context)
    if isinstance(scope, str):
        return scope
    server_name, channel = scope
    metrics = _service(bot_functions).get_metrics(server_name, channel)
    if not metrics:
        return "No metrics recorded for this channel yet."
    parts = [
        f"{key}: {value}"
        for key, value in sorted(metrics.items())
        if key != "last_event_at"
    ]
    if metrics.get("last_event_at"):
        parts.append(f"last: {metrics['last_event_at']}")
    return "Metrics: " + " | ".join(parts)


@command(
    "history",
    aliases=["gpthistory"],
    description="Show or reset GPT history for this channel",
    usage="!history [reset]",
    command_type=CommandType.PUBLIC,
)
def history_command(context: CommandContext, bot_functions):
    scope = _server_channel(context)
    if isinstance(scope, str):
        return scope
    server_name, channel = scope
    gpt = bot_functions.get("gpt_service")
    if not gpt:
        return "GPT service is not available."
    if context.args and context.args[0].lower() == "reset":
        return gpt.reset_conversation(server_name, channel)
    stats = gpt.get_conversation_stats(server_name, channel)
    return (
        f"GPT history for {channel}: {stats['total_messages']} messages "
        f"({stats['user_messages']} user, {stats['assistant_messages']} assistant)."
    )


@command(
    "seen",
    description="Show when a nick was last active in this channel",
    usage="!seen <nick>",
    examples=["!seen nick"],
    requires_args=True,
    command_type=CommandType.PUBLIC,
)
def seen_command(context: CommandContext, bot_functions):
    scope = _server_channel(context)
    if isinstance(scope, str):
        return scope
    server_name, channel = scope
    nick = context.args[0]
    if context.sender and nick.lower() == context.sender.lower():
        return f"{nick}: you are right here."
    entry = _service(bot_functions).get_seen(server_name, channel, nick)
    if not entry:
        return f"I have not seen {nick} in {channel}."
    when = entry.get("last_seen", "unknown time")
    try:
        dt = datetime.fromisoformat(when)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        when = dt.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    except ValueError:
        pass
    message = entry.get("message", "")
    return f"{entry.get('nick', nick)} was last seen {when}: {message}"


@command(
    "poll",
    description="Create, vote, close, or show poll results",
    usage="!poll create question | option | option OR !poll vote <id> <number>",
    examples=[
        "!poll create Lunch? | pizza | sushi",
        "!poll vote 1234 2",
        "!poll results 1234",
        "!poll close 1234",
    ],
    command_type=CommandType.PUBLIC,
)
def poll_command(context: CommandContext, bot_functions):
    scope = _server_channel(context)
    if isinstance(scope, str):
        return scope
    server_name, channel = scope
    service = _service(bot_functions)

    if not context.args:
        return (
            "Usage: !poll create question | option | option OR !poll vote <id> <number>"
        )

    action = context.args[0].lower()
    if action == "create":
        parsed = parse_poll_create(" ".join(context.args[1:]))
        if not parsed:
            return "Usage: !poll create question | option | option"
        question, options = parsed
        poll_id = service.create_poll(
            server_name, channel, context.sender or "unknown", question, options[:10]
        )
        listed = " | ".join(
            f"{i + 1}. {option}" for i, option in enumerate(options[:10])
        )
        return f"Poll {poll_id}: {question} | {listed}"

    if action == "vote" and len(context.args) >= 3:
        try:
            option_number = int(context.args[2])
        except ValueError:
            return "Vote must be a number."
        return service.vote_poll(
            server_name,
            channel,
            context.args[1],
            context.sender or "unknown",
            option_number,
        )

    if action == "results" and len(context.args) >= 2:
        return service.poll_results(server_name, channel, context.args[1])

    if action == "close" and len(context.args) >= 2:
        close_msg = service.close_poll(server_name, channel, context.args[1])
        return (
            close_msg
            + " "
            + service.poll_results(server_name, channel, context.args[1])
        )

    return "Usage: !poll create|vote|results|close ..."
