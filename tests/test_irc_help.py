#!/usr/bin/env python3
"""
IRC help command tests.

Validates that:
- !help sends responses to the caller (nick) via NOTICE, not to the channel
- !help output contains no duplicate command lines
- !help does not list the help command itself
"""

from types import SimpleNamespace


class DummyIrc:
    def __init__(self):
        self.sent = []  # list of tuples: (type, target, message)

    def send_message(self, target, msg):
        self.sent.append(("PRIVMSG", target, msg))

    def send_notice(self, target, msg):
        self.sent.append(("NOTICE", target, msg))


def _run_help(enhanced_process_irc_message, raw_text, bot_functions):
    irc = DummyIrc()
    enhanced_process_irc_message(irc, raw_text, bot_functions)
    return irc


def test_help_sends_private_to_nick_and_has_no_duplicates():
    from command_loader import enhanced_process_irc_message

    notices = []

    def mock_notice(msg, irc=None, target=None):
        notices.append((target, msg))

    # Minimal bot_functions for routing
    bot_functions = {
        "notice_message": mock_notice,
        "log": lambda msg, level="INFO": None,
    }

    # Simulate IRC channel command invoking !help
    # :nick!user@host PRIVMSG #chan :!help
    raw = ":tester!user@host PRIVMSG #test :!help"

    irc = _run_help(enhanced_process_irc_message, raw, bot_functions)

    # Ensure we sent something
    assert notices, "!help should produce NOTICE lines"

    # All targets should be the caller nick (private), not the channel
    targets = {t for t, _ in notices}
    assert targets == {"tester"} or (
        len(targets) == 1 and next(iter(targets)) == "tester"
    ), f"Expected notices to be sent to the nick 'tester', got targets: {targets}"

    # Extract message lines and check no duplicates (excluding footer blank lines)
    lines = [msg.strip() for _, msg in notices if msg and msg.strip()]
    # The header line must appear exactly once
    assert lines[0].startswith("Available commands:"), "First line should be the header"
    # help itself must not be present
    assert not any(
        line.startswith("help") for line in lines
    ), "!help should not list itself"

    # Check duplicates ignoring the header
    body = lines[1:]
    assert len(body) == len(set(body)), "Duplicate command lines found in !help output"
