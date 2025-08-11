#!/usr/bin/env python3
"""
IRC command integration tests for basic commands.

These tests ensure that IRC context (irc connection and channel) is properly
propagated to service functions for commands like !s (weather) and !sahko (electricity).
"""

from types import SimpleNamespace


class DummyIrc:
    """Minimal dummy IRC object to pass through the pipeline."""
    def __init__(self):
        self.sent = []

    # Provide methods that may be used by _send_response if ever invoked
    def send_message(self, target, msg):
        self.sent.append(("PRIVMSG", target, msg))

    def send_notice(self, target, msg):
        self.sent.append(("NOTICE", target, msg))


def _run_irc(enhanced_process_irc_message, raw_text, bot_functions):
    mock_irc = DummyIrc()
    enhanced_process_irc_message(mock_irc, raw_text, bot_functions)
    return mock_irc


def test_irc_weather_command_passes_irc_context():
    """!s should call send_weather with the IRC connection and channel target."""
    from command_loader import enhanced_process_irc_message

    calls = SimpleNamespace(args=None)

    def mock_send_weather(irc, target, location):
        calls.args = (irc, target, location)

    responses = []

    def mock_notice(msg, irc=None, target=None):
        responses.append(msg)

    bot_functions = {
        "notice_message": mock_notice,
        "send_weather": mock_send_weather,
        # These are optional for this path but provided to match interface
        "log": lambda msg, level="INFO": None,
    }

    # Simulate IRC channel command: :nick!u@h PRIVMSG #chan :!s Joensuu
    raw_text = ":tester!user@host PRIVMSG #test :!s Joensuu"

    mock_irc = _run_irc(enhanced_process_irc_message, raw_text, bot_functions)

    # Ensure our mock was called and IRC context was provided
    assert calls.args is not None, "send_weather was not called"
    irc_arg, target_arg, location_arg = calls.args
    assert irc_arg is not None, "IRC context was not provided to send_weather"
    assert target_arg == "#test", "Channel target not passed correctly"
    assert location_arg.lower() == "joensuu"


def test_irc_electricity_command_passes_irc_context():
    """!sahko should call send_electricity_price with the IRC connection and channel."""
    from command_loader import enhanced_process_irc_message

    calls = SimpleNamespace(args=None)

    def mock_send_electricity_price(irc, target, parts):
        calls.args = (irc, target, parts)

    responses = []

    def mock_notice(msg, irc=None, target=None):
        responses.append(msg)

    bot_functions = {
        "notice_message": mock_notice,
        "send_electricity_price": mock_send_electricity_price,
        "log": lambda msg, level="INFO": None,
    }

    # Simulate IRC channel command: :nick!u@h PRIVMSG #chan :!sahko
    raw_text = ":tester!user@host PRIVMSG #test :!sahko"

    mock_irc = _run_irc(enhanced_process_irc_message, raw_text, bot_functions)

    assert calls.args is not None, "send_electricity_price was not called"
    irc_arg, target_arg, parts_arg = calls.args
    assert irc_arg is not None, "IRC context was not provided to send_electricity_price"
    assert target_arg == "#test", "Channel target not passed correctly"
    assert isinstance(parts_arg, list) and parts_arg and parts_arg[0] in ("sahko", "sähkö"), "Command parts not passed correctly"
