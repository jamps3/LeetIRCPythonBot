#!/usr/bin/env python3
"""
Pytest tests for main.py
"""

import os
import sys
from argparse import Namespace

import pytest

import main as main_mod

# Add the parent directory to Python path to ensure imports work in CI
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


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
    _install_fake_args(monkeypatch, nickname="NickX", console=True)
    monkeypatch.setattr(main_mod, "setup_environment", lambda: "Bot", raising=True)
    monkeypatch.setattr(main_mod, "BotManager", _FakeBotManager, raising=True)
    assert main_mod.main() == 0


essential_vars = ["SERVER1_HOST"]


def test_main_env_missing_returns_1(monkeypatch):
    _install_fake_args(monkeypatch)
    monkeypatch.setattr(main_mod, "setup_environment", lambda: None, raising=True)
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
        def __init__(self, name, console_mode=False):
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
    def __init__(self, name, console_mode=False):
        self.name = name
        self.console_mode = console_mode
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True
        return True

    def wait_for_shutdown(self):
        return None

    def stop(self):
        self.stopped = True

    def run(self):
        self.start()
        self.wait_for_shutdown()
        self.stop()


def _install_fake_args(monkeypatch, **kwargs):
    defaults = {
        "loglevel": "INFO",
        "nickname": None,
        "show_api_keys": False,
        "console": False,
    }
    defaults.update(kwargs)
    monkeypatch.setattr(
        main_mod, "parse_arguments", lambda: Namespace(**defaults), raising=True
    )


def test_main_success_flow(monkeypatch):
    _install_fake_args(monkeypatch, console=True)
    monkeypatch.setattr(main_mod, "setup_environment", lambda: "Bot", raising=True)
    monkeypatch.setattr(main_mod, "BotManager", _FakeBotManager, raising=True)
    assert main_mod.main() == 0


def test_main_start_failure(monkeypatch):
    class BM(_FakeBotManager):
        def start(self):
            return False

    _install_fake_args(monkeypatch)
    monkeypatch.setattr(main_mod, "setup_environment", lambda: "Bot", raising=True)
    monkeypatch.setattr(main_mod, "BotManager", BM, raising=True)
    assert main_mod.main() == 1


def test_main_keyboard_interrupt(monkeypatch):
    class BM(_FakeBotManager):
        def wait_for_shutdown(self):
            raise KeyboardInterrupt

    _install_fake_args(monkeypatch, console=True)
    monkeypatch.setattr(main_mod, "setup_environment", lambda: "Bot", raising=True)
    monkeypatch.setattr(main_mod, "BotManager", BM, raising=True)
    assert main_mod.main() == 0


def test_main_unexpected_exception(monkeypatch):
    class BM(_FakeBotManager):
        def wait_for_shutdown(self):
            raise ValueError("boom")

    _install_fake_args(monkeypatch)
    monkeypatch.setattr(main_mod, "setup_environment", lambda: "Bot", raising=True)
    monkeypatch.setattr(main_mod, "BotManager", BM, raising=True)
    assert main_mod.main() == 1
