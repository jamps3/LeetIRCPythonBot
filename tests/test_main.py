#!/usr/bin/env python3
"""
Pytest tests for main.py
"""

import io
import os
import sys
import types
from argparse import Namespace

import pytest

import main as main_mod


def test_setup_environment_warns_when_env_file_missing(monkeypatch):
    # load_env_file returns False -> warning path
    monkeypatch.setattr(main_mod, "load_env_file", lambda: False, raising=True)
    # Provide minimum server config to get past server check
    os.environ["SERVER1_HOST"] = "irc.example.com"
    try:
        assert main_mod.setup_environment() == os.getenv("BOT_NAME", "LeetIRCBot")
    finally:
        os.environ.pop("SERVER1_HOST", None)


def test_main_nickname_override(monkeypatch):
    _install_fake_args(monkeypatch, nickname="NickX")
    monkeypatch.setattr(main_mod, "setup_environment", lambda: "Bot", raising=True)
    monkeypatch.setattr(main_mod, "BotManager", _FakeBotManager, raising=True)
    monkeypatch.setattr(main_mod, "setup_console_encoding", lambda: None, raising=True)
    assert main_mod.main() == 0


essential_vars = ["SERVER1_HOST"]


def test_main_env_missing_returns_1(monkeypatch):
    _install_fake_args(monkeypatch)
    monkeypatch.setattr(main_mod, "setup_environment", lambda: None, raising=True)
    monkeypatch.setattr(main_mod, "setup_console_encoding", lambda: None, raising=True)
    # BotManager won't be constructed on early return
    assert main_mod.main() == 1


def test_dunder_main_guard_execution(monkeypatch):
    # Prepare environment and sys for execution
    import runpy

    import bot_manager as bm

    # Avoid Windows-specific encoding changes
    monkeypatch.setattr(sys, "platform", "linux")

    # Minimal server config so setup_environment passes
    os.environ["SERVER1_HOST"] = "irc.example.com"
    os.environ["BOT_NAME"] = "Bot"

    # Replace BotManager with a fast fake in the real module since run_module will import it
    class BMFast:
        def __init__(self, name):
            pass

        def start(self):
            return True

        def wait_for_shutdown(self):
            return None

        def stop(self):
            pass

    monkeypatch.setattr(bm, "BotManager", BMFast, raising=True)

    # Ensure argv minimal
    monkeypatch.setattr(sys, "argv", ["prog"])

    # Execute as __main__ and catch SystemExit
    with pytest.raises(SystemExit) as se:
        runpy.run_module("main", run_name="__main__")
    # exit code should be int
    assert isinstance(se.value.code, int)


def test_setup_console_encoding_runs(monkeypatch):
    # Force non-Windows path to avoid altering pytest's captured stdout
    monkeypatch.setattr(main_mod, "sys", types.SimpleNamespace(platform="linux"))
    main_mod.setup_console_encoding()


def test_setup_console_encoding_windows_branch(monkeypatch):
    # Simulate Windows platform and valid buffered stdout/stderr so wrapping succeeds
    bin_out = io.BytesIO()
    bin_err = io.BytesIO()

    fake_sys = types.SimpleNamespace(
        platform="win32",
        stdout=types.SimpleNamespace(buffer=bin_out),
        stderr=types.SimpleNamespace(buffer=bin_err),
    )

    # Patch the module's sys so we don't affect pytest's real sys
    monkeypatch.setattr(main_mod, "sys", fake_sys, raising=True)

    # Execute: should wrap stdout/stderr with TextIOWrapper using utf-8
    main_mod.setup_console_encoding()

    # Validate the wrappers work and write UTF-8 to underlying buffers
    main_mod.sys.stdout.write("ok✓")
    main_mod.sys.stdout.flush()
    assert bin_out.getvalue() != b""  # data written

    main_mod.sys.stderr.write("err✓")
    main_mod.sys.stderr.flush()
    assert bin_err.getvalue() != b""


def test_setup_console_encoding_windows_exception_path(monkeypatch):
    # Simulate Windows platform but provide missing .buffer to trigger exception path
    fake_sys = types.SimpleNamespace(
        platform="win32",
        stdout=types.SimpleNamespace(),  # no buffer attribute
        stderr=types.SimpleNamespace(),  # no buffer attribute
    )

    monkeypatch.setattr(main_mod, "sys", fake_sys, raising=True)

    # Should not raise; except block swallows the error
    main_mod.setup_console_encoding()

    # stdout/stderr should remain as our simple objects without write
    assert not hasattr(main_mod.sys.stdout, "write")
    assert not hasattr(main_mod.sys.stderr, "write")


def test_safe_print_fallback_and_sanitize(monkeypatch, capsys):
    calls = {"n": 0}

    def fake_print(text):
        calls["n"] += 1
        if calls["n"] == 1:
            raise UnicodeEncodeError("utf-8", "x", 0, 1, "test")
        # second call succeeds; capture via capsys
        return None

    import builtins

    monkeypatch.setattr(builtins, "print", fake_print)
    # With explicit fallback
    main_mod.safe_print("🤖 hi", fallback_text="[BOT] hi")
    # Without fallback (sanitizes)
    calls["n"] = 0
    main_mod.safe_print("🤖 hi")


def test_setup_environment_no_server_config(monkeypatch):
    # Ensure load_env_file returns True
    monkeypatch.setattr(main_mod, "load_env_file", lambda: True, raising=True)

    # Clear SERVER*_HOST
    for i in range(1, 10):
        os.environ.pop(f"SERVER{i}_HOST", None)
    assert main_mod.setup_environment() is None


def test_setup_environment_with_server(monkeypatch):
    monkeypatch.setattr(main_mod, "load_env_file", lambda: True, raising=True)
    os.environ["SERVER1_HOST"] = "irc.example.com"
    os.environ["BOT_NAME"] = "TestBot"
    assert main_mod.setup_environment() == "TestBot"
    # cleanup
    os.environ.pop("SERVER1_HOST", None)
    os.environ.pop("BOT_NAME", None)


def test_setup_logging_sets_env_and_option_output(capsys):
    os.environ.pop("LOG_LEVEL", None)
    # Provide fake keys to exercise masking/printing code paths
    os.environ["OPENAI_API_KEY"] = "A" * 16
    os.environ["WEATHER_API_KEY"] = ""
    os.environ["ELECTRICITY_API_KEY"] = "Not set"
    os.environ["YOUTUBE_API_KEY"] = "short"

    main_mod.setup_logging("DEBUG", show_api_keys=True)
    assert os.environ["LOG_LEVEL"] == "DEBUG"


def test_parse_arguments_variants(monkeypatch):
    argv = ["prog", "-l", "DEBUG", "-nick", "Alice", "-api"]
    monkeypatch.setattr(sys, "argv", argv)
    args = main_mod.parse_arguments()
    assert (
        args.loglevel == "DEBUG"
        and args.nickname == "Alice"
        and args.show_api_keys is True
    )


class _FakeBotManager:
    def __init__(self, name):
        self.name = name
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True
        return True

    def wait_for_shutdown(self):
        return None

    def stop(self):
        self.stopped = True


def _install_fake_args(monkeypatch, **kwargs):
    defaults = {"loglevel": "INFO", "nickname": None, "show_api_keys": False}
    defaults.update(kwargs)
    monkeypatch.setattr(
        main_mod, "parse_arguments", lambda: Namespace(**defaults), raising=True
    )


def test_main_success_flow(monkeypatch):
    _install_fake_args(monkeypatch)
    monkeypatch.setattr(main_mod, "setup_environment", lambda: "Bot", raising=True)
    monkeypatch.setattr(main_mod, "BotManager", _FakeBotManager, raising=True)
    monkeypatch.setattr(main_mod, "setup_console_encoding", lambda: None, raising=True)
    assert main_mod.main() == 0


def test_main_start_failure(monkeypatch):
    class BM(_FakeBotManager):
        def start(self):
            return False

    _install_fake_args(monkeypatch)
    monkeypatch.setattr(main_mod, "setup_environment", lambda: "Bot", raising=True)
    monkeypatch.setattr(main_mod, "BotManager", BM, raising=True)
    monkeypatch.setattr(main_mod, "setup_console_encoding", lambda: None, raising=True)
    assert main_mod.main() == 1


def test_main_keyboard_interrupt(monkeypatch):
    class BM(_FakeBotManager):
        def wait_for_shutdown(self):
            raise KeyboardInterrupt

    _install_fake_args(monkeypatch)
    monkeypatch.setattr(main_mod, "setup_environment", lambda: "Bot", raising=True)
    monkeypatch.setattr(main_mod, "BotManager", BM, raising=True)
    monkeypatch.setattr(main_mod, "setup_console_encoding", lambda: None, raising=True)
    assert main_mod.main() == 0


def test_main_unexpected_exception(monkeypatch):
    class BM(_FakeBotManager):
        def wait_for_shutdown(self):
            raise ValueError("boom")

    _install_fake_args(monkeypatch)
    monkeypatch.setattr(main_mod, "setup_environment", lambda: "Bot", raising=True)
    monkeypatch.setattr(main_mod, "BotManager", BM, raising=True)
    monkeypatch.setattr(main_mod, "setup_console_encoding", lambda: None, raising=True)
    assert main_mod.main() == 1


def test_main_stop_raises_returns_1(monkeypatch):
    class BM(_FakeBotManager):
        def stop(self):
            raise RuntimeError("stop fail")

    _install_fake_args(monkeypatch)
    monkeypatch.setattr(main_mod, "setup_environment", lambda: "Bot", raising=True)
    monkeypatch.setattr(main_mod, "BotManager", BM, raising=True)
    monkeypatch.setattr(main_mod, "setup_console_encoding", lambda: None, raising=True)
    assert main_mod.main() == 1
