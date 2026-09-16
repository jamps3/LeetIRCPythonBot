"""Behavioral tests for channel-scoped community commands."""

from unittest.mock import Mock

from cmd_modules.community import (
    feature_command,
    history_command,
    metrics_command,
    poll_command,
    seen_command,
)
from command_registry import CommandContext


def _context(*args, sender="alice", platform="discord", target="123"):
    return CommandContext(
        command="community",
        args=list(args),
        raw_message="!community " + " ".join(args),
        sender=sender,
        target=target,
        server_name="discord:42",
        platform=platform,
        channel_id=target,
    )


def test_feature_and_metrics_validate_channel_scopes_and_values():
    service = Mock()
    service.get_channel_features.return_value = {"ai": True, "youtube": False}
    service.get_metrics.return_value = {"messages": 4, "last_event_at": "now"}
    functions = {"community_state": service}

    assert "This command must be used" in feature_command(
        _context(target=None), functions
    )
    assert feature_command(_context(), functions) == "Features: ai=on, youtube=off"
    assert feature_command(_context("ai"), functions) == "Usage: !feature [name on|off]"
    assert "Known features" in feature_command(_context("madeup", "on"), functions)
    assert feature_command(_context("ai", "maybe"), functions) == "Use on or off."
    assert feature_command(_context("ai", "off"), functions) == "ai is now off for 123."
    service.set_feature.assert_called_once_with("discord:42", "123", "ai", False)
    assert metrics_command(_context(), functions) == "Metrics: messages: 4 | last: now"
    service.get_metrics.return_value = {}
    assert (
        metrics_command(_context(), functions)
        == "No metrics recorded for this channel yet."
    )


def test_history_seen_and_poll_delegate_to_channel_service():
    service = Mock()
    service.get_seen.return_value = {
        "nick": "Bob",
        "last_seen": "not-a-date",
        "message": "hello",
    }
    service.create_poll.return_value = "p1"
    service.vote_poll.return_value = "vote saved"
    service.poll_results.return_value = "results"
    service.close_poll.return_value = "closed"
    gpt = Mock()
    gpt.get_conversation_stats.return_value = {
        "total_messages": 3,
        "user_messages": 2,
        "assistant_messages": 1,
    }
    functions = {"community_state": service, "gpt_service": gpt}

    assert (
        history_command(_context(), functions)
        == "GPT history for 123: 3 messages (2 user, 1 assistant)."
    )
    gpt.reset_conversation.return_value = "reset"
    assert history_command(_context("reset"), functions) == "reset"
    assert seen_command(_context("alice"), functions) == "alice: you are right here."
    assert (
        seen_command(_context("Bob"), functions)
        == "Bob was last seen not-a-date: hello"
    )
    service.get_seen.return_value = None
    assert seen_command(_context("Bob"), functions) == "I have not seen Bob in 123."

    assert "Usage" in poll_command(_context(), functions)
    assert (
        poll_command(
            _context("create", "Lunch?", "|", "pizza", "|", "sushi"), functions
        )
        == "Poll p1: Lunch? | 1. pizza | 2. sushi"
    )
    assert (
        poll_command(_context("vote", "p1", "two"), functions)
        == "Vote must be a number."
    )
    assert poll_command(_context("vote", "p1", "2"), functions) == "vote saved"
    assert poll_command(_context("results", "p1"), functions) == "results"
    assert poll_command(_context("close", "p1"), functions) == "closed results"
    assert "Usage" in poll_command(_context("unexpected"), functions)
