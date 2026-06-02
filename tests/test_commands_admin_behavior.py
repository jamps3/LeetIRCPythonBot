"""Behavioral tests for modular admin commands."""

from unittest.mock import Mock, patch

from cmd_modules import admin
from command_registry import CommandContext


def make_context(command, *args, is_console=True):
    return CommandContext(
        command=command,
        args=list(args),
        raw_message=" ".join((f"!{command}", *args)),
        sender="TestUser",
        target="#test",
        is_console=is_console,
        server_name="console" if is_console else "TestServer",
    )


def test_connect_and_disconnect_use_bot_manager():
    manager = Mock()
    manager._console_connect.return_value = "connected"
    manager._console_disconnect.return_value = "disconnected"
    bot_functions = {"bot_manager": manager}

    assert (
        admin.connect_command(make_context("connect", "test"), bot_functions)
        == "connected"
    )
    assert (
        admin.disconnect_command(make_context("disconnect", "test"), bot_functions)
        == "disconnected"
    )
    manager._console_connect.assert_called_once_with("test")
    manager._console_disconnect.assert_called_once_with("test")


def test_connect_and_disconnect_report_missing_manager():
    assert (
        admin.connect_command(make_context("connect"), {})
        == "Bot manager not available"
    )
    assert (
        admin.disconnect_command(make_context("disconnect"), {})
        == "Bot manager not available"
    )


def test_countdown_starts_timer_and_sends_completion_notice():
    timer = Mock()
    notice = Mock()
    irc = Mock()
    with patch("cmd_modules.admin.threading.Timer", return_value=timer) as timer_class:
        result = admin.countdown_command(
            make_context("k-1s", "Done", is_console=False),
            {"notice_message": notice, "irc": irc},
        )

    timer_class.assert_called_once()
    assert timer_class.call_args.args[0] == 1
    timer.daemon = True
    timer.start.assert_called_once()
    timer_class.call_args.args[1]()
    notice.assert_called_once()
    assert "Done" in notice.call_args.args[0]
    assert result.endswith("(1s)")


def test_countdown_validates_duration():
    assert admin.countdown_command(make_context("k"), {}).startswith("Usage:")
    assert (
        admin.countdown_command(make_context("k", "0"), {}) == "Time must be positive"
    )
    assert (
        admin.countdown_command(make_context("k", "25h"), {})
        == "Maximum countdown time is 24 hours"
    )


def test_exit_stops_manager_with_custom_message():
    manager = Mock()
    set_quit_message = Mock()
    result = admin.exit_command(
        make_context("exit", "Goodbye", "now"),
        {"bot_manager": manager, "set_quit_message": set_quit_message},
    )

    set_quit_message.assert_called_once_with("Goodbye now")
    manager.stop.assert_called_once_with("Goodbye now")
    assert "shutdown initiated" in result.lower()


def test_exit_uses_stop_event_fallback_and_ignores_irc():
    stop_event = Mock()
    assert admin.exit_command(make_context("exit", is_console=False), {}) is None
    result = admin.exit_command(make_context("exit"), {"stop_event": stop_event})
    stop_event.set.assert_called_once()
    assert "shutdown initiated" in result.lower()


def test_quit_delegates_to_exit():
    with patch("cmd_modules.admin.exit_command", return_value="done") as exit_command:
        context = make_context("quit")
        assert admin.quit_command(context, {}) == "done"
        exit_command.assert_called_once_with(context, {})
