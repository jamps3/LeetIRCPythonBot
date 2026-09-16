"""Tests for user input routing before it reaches command handlers."""

import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import command_loader


class ImmediateThread:
    """Execute routed background work synchronously in unit tests."""

    def __init__(self, target=None, args=(), **_kwargs):
        self.target = target
        self.args = args
        self.started = False

    def start(self):
        self.started = True
        self.target(*self.args)


def make_bot(*, gpt_service=None):
    console = Mock()
    console._create_console_bot_functions.return_value = {"notice_message": Mock()}
    return SimpleNamespace(
        stop_event=Mock(), console_manager=console, gpt_service=gpt_service
    )


def test_process_user_input_stops_cleanly_for_plain_and_bot_quit(monkeypatch):
    bot = make_bot()
    processed = []
    monkeypatch.setattr(
        command_loader, "process_console_command", lambda *args: processed.append(args)
    )

    assert command_loader.process_user_input("quit", bot) is False
    bot.stop_event.set.assert_called_once()

    assert command_loader.process_user_input("!exit", bot) is False
    assert processed == [
        ("!exit", bot.console_manager._create_console_bot_functions.return_value)
    ]


def test_process_user_input_routes_commands_channels_and_messages(monkeypatch):
    bot = make_bot()
    processed = []
    monkeypatch.setattr(threading, "Thread", ImmediateThread)
    monkeypatch.setattr(
        command_loader, "process_console_command", lambda *args: processed.append(args)
    )

    assert command_loader.process_user_input("!help", bot) is True
    assert processed == [
        ("!help", bot.console_manager._create_console_bot_functions.return_value)
    ]

    assert command_loader.process_user_input("#chat", bot) is True
    bot.console_manager._console_join_or_part_channel.assert_called_once_with("chat")
    assert command_loader.process_user_input("#", bot) is True
    bot.console_manager._get_channel_status.assert_called_once()

    assert command_loader.process_user_input("hello", bot) is True
    bot.console_manager._console_send_to_channel.assert_called_once_with("hello")


def test_process_user_input_routes_ai_and_handles_empty_input(monkeypatch):
    gpt = Mock()
    gpt.chat.return_value = "response"
    bot = make_bot(gpt_service=gpt)
    monkeypatch.setattr(threading, "Thread", ImmediateThread)

    assert (
        command_loader.process_user_input("- explain this", bot, source="TUI") is True
    )
    gpt.chat.assert_called_once_with("explain this", "TUI", "console", "console")
    assert command_loader.process_user_input("   ", bot) is True


@pytest.mark.asyncio
async def test_process_irc_command_uses_channel_target_and_splits_response(monkeypatch):
    response = SimpleNamespace(
        should_respond=True,
        message="first\nsecond",
        split_long_messages=True,
    )
    process = AsyncMock(return_value=response)
    notices = Mock()
    wrapped = Mock(side_effect=lambda text, *_args, **_kwargs: [text])
    captured_contexts = []

    async def capture_context(message, context, bot_functions):
        captured_contexts.append((message, context, bot_functions))
        return await process(message, context, bot_functions)

    monkeypatch.setattr(command_loader, "ensure_commands_loaded", Mock())
    monkeypatch.setattr("command_registry.process_command_message", capture_context)
    monkeypatch.setattr("config.get_config", lambda: SimpleNamespace(name="LeetBot"))
    irc = SimpleNamespace(bot_name="LeetBot")

    assert await command_loader.process_irc_command(
        "!weather Helsinki",
        "alice",
        "#weather",
        irc,
        "ident@host",
        {
            "server_name": "network",
            "notice_message": notices,
            "wrap_irc_message_utf8_bytes": wrapped,
        },
    )

    _, context, bot_functions = captured_contexts[0]
    assert context.target == "#weather"
    assert context.is_private is False
    assert bot_functions["irc"] is irc
    assert notices.call_args_list == [
        (("first", irc, "#weather"), {}),
        (("second", irc, "#weather"), {}),
    ]


@pytest.mark.asyncio
async def test_process_console_command_async_sends_split_response(monkeypatch):
    response = SimpleNamespace(
        should_respond=True,
        message="one\n\ntwo",
        split_long_messages=True,
    )
    notices = Mock()
    monkeypatch.setattr(
        "command_registry.process_command_message", AsyncMock(return_value=response)
    )

    assert await command_loader.process_console_command_async(
        "!help", {"notice_message": notices}
    )
    assert [call.args for call in notices.call_args_list] == [("one",), ("two",)]


def test_process_console_command_reports_unknown_and_success(monkeypatch):
    notices = Mock()
    log = Mock()

    async def not_processed(*_args):
        return False

    monkeypatch.setattr(command_loader, "ensure_commands_loaded", Mock())
    monkeypatch.setattr(command_loader, "process_console_command_async", not_processed)
    command_loader.process_console_command(
        "/unknown", {"notice_message": notices, "log": log}
    )
    notices.assert_called_once_with(
        "Command not recognized: /unknown. Type /help for available commands."
    )

    async def processed(*_args):
        return True

    monkeypatch.setattr(command_loader, "process_console_command_async", processed)
    command_loader.process_console_command("!help", {"log": log})
    assert any("processed successfully" in call.args[0] for call in log.call_args_list)
