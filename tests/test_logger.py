#!/usr/bin/env python3
"""
Pytest tests for logger module.
"""

import builtins
import importlib
import os
import re
from unittest.mock import Mock

import logger as lg


def test_config_reload_uses_active_tui_logger_hook():
    """Config reloads must continue to route logs through the active TUI."""
    import config

    received = []

    def tui_hook(*args):
        received.append(args)

    lg.set_tui_hook(tui_hook)
    try:
        importlib.reload(config)
        config.logger.info("config reload log")
    finally:
        lg.clear_tui_hook()

    assert config.get_logger is lg.get_logger
    assert any(entry[3] == "config reload log" for entry in received)


def test_logger_buffers_hook_failures_without_writing_over_tui(capsys):
    def broken_hook(*_args):
        raise RuntimeError("render failed")

    lg.set_tui_hook(broken_hook)
    try:
        lg.info("DrinkTracker event")
        buffered = lg.get_and_clear_log_buffer()
    finally:
        lg.clear_tui_hook()

    assert capsys.readouterr().out == ""
    assert any(
        isinstance(entry[3], str) and "TUI hook failed: render failed" in entry[3]
        for entry in buffered
    )


def test_logger_buffers_file_hook_failures_without_writing_over_tui(capsys):
    received = []

    def broken_file_hook(*_args):
        raise OSError("disk unavailable")

    lg.set_tui_hook(lambda *args: received.append(args))
    lg.set_file_hook(broken_file_hook)
    try:
        lg.info("DrinkTracker event")
        buffered = lg.get_and_clear_log_buffer()
    finally:
        lg.clear_file_hook()
        lg.clear_tui_hook()

    assert capsys.readouterr().out == ""
    assert any(
        isinstance(entry[3], str) and "File hook failed: disk unavailable" in entry[3]
        for entry in buffered
    )
    assert any(entry[3] == "DrinkTracker event" for entry in received)


def test_drink_tracker_logs_through_active_tui_hook():
    from word_tracking.drink_tracker import DrinkTracker

    received = []
    data_manager = Mock()
    data_manager.load_drink_data.return_value = {"servers": {}}
    lg.set_tui_hook(lambda *args: received.append(args))
    try:
        DrinkTracker(data_manager).logger.info("tracked drink")
    finally:
        lg.clear_tui_hook()

    assert any(
        entry[1] == "DrinkTracker" and entry[3] == "tracked drink" for entry in received
    )


def test_logger_basic_levels_and_timestamp(capsys):
    # Instance with context
    pl = lg.PrecisionLogger("ModuleCtx")
    pl.info("info message")
    pl.error("error message")
    pl.warning("warn message")
    pl.debug("debug message")
    pl.msg("msg event")
    pl.server("server event")

    # Module-level convenience API (with and without context)
    lg.info("i1")
    lg.error("e1")
    lg.warning("w1")
    lg.debug("d1")
    lg.msg("m1")
    lg.server("s1")

    lg.log("with extra", level="INFO", context="CtxA")
    lg.log("no ctx", level="WARNING")

    out = capsys.readouterr().out.strip().splitlines()
    assert out, "Expected some output from logger"

    # First line should contain a high-precision timestamp like [YYYY-mm-dd HH:MM:SS.NNNNNNNNN]
    assert re.match(r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{9}\] ", out[0])

    # Check that various levels and contexts appear
    joined = "\n".join(out)
    assert "[INFO   ]" in joined
    assert "[ERROR  ]" in joined
    assert "[WARNING]" in joined
    assert "[DEBUG  ]" in joined
    assert "[MSG    ]" in joined
    assert "[SERVER ]" in joined
    assert "[ModuleCtx]" in joined
    assert "[CtxA]" in joined


def test_safe_print_fallback_and_sanitize(monkeypatch, capsys):
    calls = {"n": 0}
    captured_texts = []

    # Store original print function
    original_print = builtins.print

    def fake_print(text):
        calls["n"] += 1
        captured_texts.append(text)
        if calls["n"] == 1:
            raise UnicodeEncodeError("utf-8", "x", 0, 1, "test")
        # second call succeeds - use original print to output to capsys
        original_print(text)
        return None

    monkeypatch.setattr(builtins, "print", fake_print)

    # With explicit fallback
    lg.log("🤖 hi", fallback_text="[BOT] hi")
    out = capsys.readouterr().out
    assert "[BOT] hi" in out

    # Without fallback (sanitizes)
    calls["n"] = 0
    captured_texts.clear()
    lg.log("🤖 hi")
    out2 = capsys.readouterr().out
    # Should print a sanitized version with [BOT] replacing the emoji
    assert "[BOT] hi" in out2


def test_get_log_files_ignores_files_removed_during_rotation(monkeypatch):
    monkeypatch.setattr(lg.os, "listdir", lambda _: ["leet.log", "leet.log.2"])

    def getmtime(path):
        if path.endswith(".2"):
            raise FileNotFoundError(path)
        return 1

    monkeypatch.setattr(lg.os.path, "getmtime", getmtime)

    assert lg.get_log_files("data/leet.log") == [os.path.join("data", "leet.log")]
