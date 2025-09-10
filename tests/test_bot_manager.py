#!/usr/bin/env python3
"""
Pytest tests for bot_manager module.
"""

import json
import os
import sys
import time
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

import bot_manager as bm

# Ensure project root on path
"""parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
"""


class DummyLogger:
    def __init__(self):
        self.records = []

    def info(self, *args, **kwargs):
        self.records.append(("info", args))

    def warning(self, *args, **kwargs):
        self.records.append(("warning", args))

    def error(self, *args, **kwargs):
        self.records.append(("error", args))

    def debug(self, *args, **kwargs):
        self.records.append(("debug", args))

    def log(self, *args, **kwargs):
        self.records.append(("log", args))


class DummyDetector:
    def get_timestamp_with_nanoseconds(self):
        return "2025-09-04T00:00:00.123456789Z"

    def check_message_for_leet(self, sender, ts, msg):
        return None


@pytest.fixture
def manager(monkeypatch):
    # Patch logger
    monkeypatch.setattr(bm, "get_logger", lambda name: DummyLogger(), raising=True)
    # Avoid external services
    monkeypatch.setattr(bm, "get_api_key", lambda k: "", raising=True)
    monkeypatch.setattr(bm, "WeatherService", None, raising=True)
    monkeypatch.setattr(bm, "GPTService", None, raising=True)
    monkeypatch.setattr(bm, "create_electricity_service", None, raising=True)
    monkeypatch.setattr(bm, "create_youtube_service", None, raising=True)
    monkeypatch.setattr(bm, "create_crypto_service", None, raising=True)
    monkeypatch.setattr(bm, "create_fmi_warning_service", None, raising=True)
    monkeypatch.setattr(bm, "create_otiedote_service", None, raising=True)
    # Lightweight components
    monkeypatch.setattr(
        bm,
        "DataManager",
        lambda: SimpleNamespace(migrate_from_pickle=lambda: True),
        raising=True,
    )
    monkeypatch.setattr(
        bm,
        "DrinkTracker",
        lambda dm: SimpleNamespace(process_message=lambda **k: None),
        raising=True,
    )
    monkeypatch.setattr(
        bm,
        "GeneralWords",
        lambda dm: SimpleNamespace(process_message=lambda **k: None),
        raising=True,
    )
    monkeypatch.setattr(
        bm,
        "TamagotchiBot",
        lambda dm: SimpleNamespace(process_message=lambda **k: (False, None)),
        raising=True,
    )
    monkeypatch.setattr(bm, "Lemmatizer", lambda: object(), raising=True)
    monkeypatch.setattr(
        bm, "create_nanoleet_detector", lambda: DummyDetector(), raising=True
    )

    # Construct
    m = bm.BotManager("MyBot")
    return m


def test_bot_manager_initialization_with_services():
    """Test that BotManager initializes properly with all services."""
    # Mock all dependencies but ensure they return proper values
    with patch("bot_manager.DataManager") as mock_dm:
        with patch("bot_manager.get_api_key") as mock_api:
            with patch("bot_manager.create_crypto_service") as mock_crypto:
                with patch("bot_manager.create_nanoleet_detector") as mock_nano:
                    with patch("bot_manager.create_fmi_warning_service") as mock_fmi:
                        with patch(
                            "bot_manager.create_otiedote_service"
                        ) as mock_otiedote:
                            with patch("bot_manager.Lemmatizer") as mock_lemma:
                                # Set up proper mock returns
                                mock_api.return_value = "fake_key"
                                mock_crypto.return_value = Mock()
                                mock_nano.return_value = Mock()
                                mock_fmi.return_value = Mock()
                                mock_otiedote.return_value = Mock()
                                mock_lemma.return_value = Mock()

                                # Mock data manager
                                mock_dm_instance = Mock()
                                mock_dm.return_value = mock_dm_instance
                                mock_dm_instance.load_tamagotchi_state.return_value = {
                                    "servers": {}
                                }
                                mock_dm_instance.save_tamagotchi_state.return_value = (
                                    None
                                )
                                mock_dm_instance.load_general_words_data.return_value = {
                                    "servers": {}
                                }
                                mock_dm_instance.save_general_words_data.return_value = (
                                    None
                                )
                                mock_dm_instance.load_drink_data.return_value = {
                                    "servers": {}
                                }
                                mock_dm_instance.save_drink_data.return_value = None

                                from bot_manager import BotManager

                                bot_manager = BotManager("TestBot")

                                # Check that essential attributes exist
                                required_attrs = [
                                    "bot_name",
                                    "servers",
                                    "stop_event",
                                    "data_manager",
                                    "drink_tracker",
                                    "general_words",
                                    "tamagotchi",
                                    "crypto_service",
                                    "nanoleet_detector",
                                ]

                                for attr in required_attrs:
                                    assert hasattr(
                                        bot_manager, attr
                                    ), f"Missing required attribute: {attr}"

                                # Check that essential methods exist
                                required_methods = [
                                    "_handle_message",
                                    "_track_words",
                                    "_process_commands",
                                    "start",
                                    "stop",
                                    "wait_for_shutdown",
                                    "_listen_for_console_commands",
                                    "_create_console_bot_functions",
                                ]

                                for method in required_methods:
                                    assert hasattr(
                                        bot_manager, method
                                    ), f"Missing required method: {method}"
                                    assert callable(
                                        getattr(bot_manager, method)
                                    ), f"Attribute {method} is not callable"


def test_safe_print_no_error(capsys):
    bm.safe_print("hello 🤖")
    out = capsys.readouterr().out
    assert "hello" in out


def test_url_blacklist_functionality():
    """Test URL blacklisting for title fetching."""
    # Mock all dependencies
    with patch("bot_manager.DataManager"):
        with patch("bot_manager.get_api_key", return_value=None):
            with patch("bot_manager.create_crypto_service", return_value=Mock()):
                with patch("bot_manager.create_nanoleet_detector", return_value=Mock()):
                    with patch(
                        "bot_manager.create_fmi_warning_service", return_value=Mock()
                    ):
                        with patch(
                            "bot_manager.create_otiedote_service", return_value=Mock()
                        ):
                            with patch(
                                "bot_manager.Lemmatizer",
                                side_effect=Exception("Mock error"),
                            ):
                                from bot_manager import BotManager

                                bot_manager = BotManager("TestBot")

                                # Test blacklisted URLs
                                blacklisted_urls = [
                                    "https://www.youtube.com/watch?v=5nM6T3KCVfM",
                                    "https://facebook.com/somepost",
                                    "https://x.com/sometweet",
                                    "https://example.com/photo.jpg",
                                    "https://example.com/document.pdf",
                                ]

                                for url in blacklisted_urls:
                                    result = bot_manager._is_url_blacklisted(url)
                                    assert (
                                        result
                                    ), f"URL should be blacklisted but wasn't: {url}"

                                # Test allowed URLs
                                allowed_urls = [
                                    "https://example.com",
                                    "https://news.example.com/article",
                                    "https://github.com/user/repo",
                                ]

                                for url in allowed_urls:
                                    result = bot_manager._is_url_blacklisted(url)
                                    assert (
                                        not result
                                    ), f"URL should be allowed but was blacklisted: {url}"


def test_wrap_irc_message_utf8_bytes_basic(manager):
    # within limit
    lines = manager._wrap_irc_message_utf8_bytes("short message")
    assert lines == ["short message"]
    # very long word forces byte split and placeholder when hitting max_lines
    long_word = "ä" * 1000  # multi-byte
    lines2 = manager._wrap_irc_message_utf8_bytes(long_word, max_lines=2)
    assert len(lines2) == 2
    assert lines2[-1].endswith("...")


def test_is_youtube_url_variants():
    urls = [
        "https://www.youtube.com/watch?v=abc123",
        "https://youtu.be/abc123",
        "https://youtube.com/embed/abc123",
        "https://m.youtube.com/watch?v=",
        "https://music.youtube.com/watch?v=",
        "https://www.youtube.com/shorts/abc123",
    ]
    for u in urls:
        assert bm.BotManager._is_youtube_url(bm.BotManager, u) is True
    assert bm.BotManager._is_youtube_url(bm.BotManager, "https://example.com") is False


def test_youtube_url_detection():
    """Test YouTube URL detection functionality."""
    # Mock all dependencies
    with patch("bot_manager.DataManager"):
        with patch("bot_manager.get_api_key", return_value=None):
            with patch("bot_manager.create_crypto_service", return_value=Mock()):
                with patch("bot_manager.create_nanoleet_detector", return_value=Mock()):
                    with patch(
                        "bot_manager.create_fmi_warning_service", return_value=Mock()
                    ):
                        with patch(
                            "bot_manager.create_otiedote_service", return_value=Mock()
                        ):
                            with patch(
                                "bot_manager.Lemmatizer",
                                side_effect=Exception("Mock error"),
                            ):
                                from bot_manager import BotManager

                                bot_manager = BotManager("TestBot")

                                # Test various YouTube URL formats
                                test_urls = [
                                    # Standard YouTube URLs
                                    (
                                        "https://www.youtube.com/watch?v=5nM6T3KCVfM",
                                        True,
                                    ),
                                    (
                                        "http://www.youtube.com/watch?v=5nM6T3KCVfM",
                                        True,
                                    ),
                                    ("https://youtube.com/watch?v=5nM6T3KCVfM", True),
                                    # Short YouTube URLs
                                    ("https://youtu.be/5nM6T3KCVfM", True),
                                    ("http://youtu.be/5nM6T3KCVfM", True),
                                    # YouTube Shorts URLs
                                    (
                                        "https://www.youtube.com/shorts/5nM6T3KCVfM",
                                        True,
                                    ),
                                    # Mobile YouTube URLs
                                    ("https://m.youtube.com/watch?v=5nM6T3KCVfM", True),
                                    # YouTube Music URLs
                                    (
                                        "https://music.youtube.com/watch?v=5nM6T3KCVfM",
                                        True,
                                    ),
                                    # Embed URLs
                                    ("https://www.youtube.com/embed/5nM6T3KCVfM", True),
                                    ("https://www.youtube.com/v/5nM6T3KCVfM", True),
                                    # Non-YouTube URLs (should return False)
                                    ("https://www.google.com", False),
                                    ("https://example.com/watch?v=notYouTube", False),
                                    ("https://vimeo.com/123456", False),
                                    ("https://twitch.tv/streamername", False),
                                    ("", False),
                                    ("not a url at all", False),
                                ]

                                for url, should_be_youtube in test_urls:
                                    result = bot_manager._is_youtube_url(url)
                                    assert (
                                        result == should_be_youtube
                                    ), f"Failed for URL: {url}, expected {should_be_youtube}, got {result}"


def test_update_env_file_add_and_update(tmp_path, monkeypatch, manager):
    env = tmp_path / ".env"
    env.write_text("OPENAI_MODEL=gpt-old\nOTHER=1\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    # Update existing
    assert manager._update_env_file("OPENAI_MODEL", "gpt-new") is True
    content = env.read_text(encoding="utf-8")
    assert "OPENAI_MODEL=gpt-new" in content

    # Add new key
    assert manager._update_env_file("NEWKEY", "val") is True
    content = env.read_text(encoding="utf-8")
    assert "NEWKEY=val" in content

    # Missing file
    sub = tmp_path / "sub"
    os.makedirs(sub, exist_ok=True)
    monkeypatch.chdir(sub)
    assert manager._update_env_file("X", "Y") is False


def test_toggle_tamagotchi_and_set_quit_message(monkeypatch, manager):
    # Stub _update_env_file to True
    monkeypatch.setattr(manager, "_update_env_file", lambda k, v: True, raising=True)
    # Capture responses sent
    sent = []
    monkeypatch.setattr(
        manager, "_send_response", lambda s, t, m: sent.append((t, m)), raising=True
    )

    # Toggle
    resp = manager.toggle_tamagotchi(
        SimpleNamespace(config=SimpleNamespace(name="s")), "#c", "nick"
    )
    assert "Tamagotchi responses are now" in resp
    assert len(sent) == 1

    # set quit message updates servers
    dummy_server = SimpleNamespace(quit_message=None)
    manager.servers = {"A": dummy_server}
    manager.set_quit_message("Bye")
    assert manager.quit_message == "Bye"
    assert dummy_server.quit_message == "Bye"


def test_send_response_use_notice_and_message(manager):
    out = []

    class S:
        def send_notice(self, t, m):
            out.append(("notice", t, m))

        def send_message(self, t, m):
            out.append(("message", t, m))

    server = S()

    manager.use_notices = True
    manager._send_response(server, "#c", "hi")
    manager.use_notices = False
    manager._send_response(server, "#c", "hi")
    # Console path
    manager._send_response(None, "#c", "console")

    kinds = [k for k, *_ in out]
    assert kinds == ["notice", "message"]


def test_process_leet_winner_summary(monkeypatch, manager):
    winners = {}
    monkeypatch.setattr(manager, "_load_leet_winners", lambda: winners, raising=True)
    saved = {}

    def save(d):
        saved.update(d)

    monkeypatch.setattr(manager, "_save_leet_winners", save, raising=True)

    text = "Ensimmäinen leettaaja oli Alice kello 13.37.00,218154740 (”leet”), viimeinen oli Bob kello 13.37.56,267236192 (”leet”). Lähimpänä multileettiä oli Carol kello 13.37.13,242345678 (”leet”)."
    sender = "Beici"
    manager._process_leet_winner_summary(text, sender)
    assert saved.get("Alice", {}).get("ensimmäinen") == 1
    assert saved.get("Bob", {}).get("viimeinen") == 1
    assert saved.get("Carol", {}).get("multileet") == 1
    sender = "Beiki"
    manager._process_leet_winner_summary(text, sender)
    assert saved.get("Alice", {}).get("ensimmäinen") == 2
    assert saved.get("Bob", {}).get("viimeinen") == 2
    assert saved.get("Carol", {}).get("multileet") == 2
    sender = "Beibi"
    manager._process_leet_winner_summary(text, sender)
    assert saved.get("Alice", {}).get("ensimmäinen") == 3
    assert saved.get("Bob", {}).get("viimeinen") == 3
    assert saved.get("Carol", {}).get("multileet") == 3


def test_chat_with_gpt_paths(monkeypatch, manager):
    # Without gpt_service
    assert "not available" in manager._chat_with_gpt("hello").lower()

    # With gpt_service and error path
    class GS:
        def __init__(self):
            self.model = "m"

        def chat(self, msg, sender):
            raise RuntimeError("boom")

    manager.gpt_service = GS()
    assert "trouble" in manager._chat_with_gpt("hello").lower()

    # With gpt_service success and mention cleanup
    class GS2:
        def __init__(self):
            self.model = "m"

        def chat(self, msg, sender):
            return f"ok:{msg}:{sender}"

    manager.gpt_service = GS2()
    out = manager._chat_with_gpt("MyBot: hey", "nick")
    assert out.startswith("ok:")


def test_set_openai_model_statuses(monkeypatch, manager, tmp_path):
    # No gpt_service -> error text
    manager.gpt_service = None
    assert "not available" in manager.set_openai_model("gpt-5").lower()

    # With gpt_service but no .env -> session only
    class GS:
        def __init__(self):
            self.model = "old"

    manager.gpt_service = GS()
    monkeypatch.chdir(tmp_path)
    msg = manager.set_openai_model("new-model")
    assert "session only" in msg

    # With .env -> persisted
    (tmp_path / ".env").write_text("OPENAI_MODEL=old\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    msg2 = manager.set_openai_model("new2")
    assert "persisted" in msg2


def test_measure_latency(manager):
    t1 = manager._measure_latency()
    assert isinstance(t1, float)


def test_send_crypto_price_and_electricity(monkeypatch, manager):
    # Crypto service
    class Crypto:
        def get_crypto_price(self, coin, cur):
            return {"price": 123.45}

        def format_price_message(self, data):
            return f"{data['price']} EUR"

    manager.crypto_service = Crypto()

    sent = []
    monkeypatch.setattr(
        manager, "_send_response", lambda i, c, m: sent.append(m), raising=True
    )

    manager._send_crypto_price(None, "#c", "btc eur")
    manager._send_crypto_price(None, "#c", ["!crypto", "btc", "eur"])  # list variant
    assert len(sent) == 2 and "EUR" in sent[0]

    # Electricity service
    class Elec:
        def parse_command_args(self, args):
            return {"hour": 10, "date": None, "is_tomorrow": False}

        def get_electricity_price(self, hour=None, date=None, include_tomorrow=True):
            return {"price": 1.23}

        def format_price_message(self, data):
            return "price-ok"

        def get_price_statistics(self, date):
            return {"stats": True}

        def format_statistics_message(self, data):
            return "stats-ok"

        def get_daily_prices(self, date):
            return [1, 2, 3]

        def format_daily_prices_message(self, daily, is_tomorrow=False):
            return "daily-ok"

    manager.electricity_service = Elec()

    sent.clear()
    manager._send_electricity_price(None, "#c", "")
    manager._send_electricity_price(None, "#c", ["!price"])  # list variant
    assert sent[-1] in ("price-ok", "daily-ok", "stats-ok")


def test_ipfs_command_paths(monkeypatch, manager):
    # Success path without irc/target returns value
    import sys as _sys
    import types

    _sys.modules["services.ipfs_service"] = types.SimpleNamespace(
        handle_ipfs_command=lambda cmd, pw: "resp"
    )
    assert manager._handle_ipfs_command("cmd") == "resp"
    # Success path with irc/target sends via _send_response
    sent = []
    manager._send_response = lambda s, t, m: sent.append(m)
    manager._handle_ipfs_command("cmd", irc_client=SimpleNamespace(), target="#c")
    assert sent[-1] == "resp"
    # Error path
    _sys.modules["services.ipfs_service"] = types.SimpleNamespace(
        handle_ipfs_command=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("e"))
    )
    assert "❌" in manager._handle_ipfs_command("cmd")


def test_wrap_message_edge_cases(manager):
    # None -> []
    assert manager._wrap_irc_message_utf8_bytes(None) == []
    # Preserve blank lines
    lines = manager._wrap_irc_message_utf8_bytes("a\n\n b")
    assert "" in lines
    # Placeholder trimming branch: line exactly at safe limit and max_lines=1
    msg = "a" * 425
    out = manager._wrap_irc_message_utf8_bytes(msg, max_lines=1)
    assert out[0].endswith("...")


def test_update_env_file_ioerror(monkeypatch, manager, tmp_path):
    env = tmp_path / ".env"
    env.write_text("X=Y\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    # Force IOError on write
    import builtins as _bi

    real_open = open

    def fake_open(*a, **k):
        if a and a[0].endswith(".env") and (len(a) > 1 and a[1] == "w"):
            raise OSError("fail")
        return real_open(*a, **k)

    monkeypatch.setattr(_bi, "open", fake_open)
    assert manager._update_env_file("A", "B") is False


def test_optional_service_import_errors_cover_except_blocks(monkeypatch):
    # Load bot_manager anew under an alias and force ImportError for optional services
    import builtins as _bi
    import importlib.util
    import sys as _sys
    import types

    path = bm.__file__
    orig_import = _bi.__import__

    def fake_import(name, *a, **k):
        blocked = {
            "services.crypto_service",
            "services.electricity_service",
            "services.fmi_warning_service",
            "services.gpt_service",
            "services.otiedote_service",
            "services.weather_service",
            "services.youtube_service",
        }
        if name in blocked:
            raise ImportError("blocked")
        return orig_import(name, *a, **k)

    _bi.__import__ = fake_import
    try:
        spec = importlib.util.spec_from_file_location("bot_manager_alt", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        # All optional factories should be None
        assert getattr(mod, "create_crypto_service") is None
        assert getattr(mod, "create_electricity_service") is None
        assert getattr(mod, "create_fmi_warning_service") is None
        assert getattr(mod, "GPTService") is None
        assert getattr(mod, "create_otiedote_service") is None
        assert getattr(mod, "WeatherService") is None
        assert getattr(mod, "create_youtube_service") is None
    finally:
        _bi.__import__ = orig_import
        _sys.modules.pop("bot_manager_alt", None)


def test_load_configurations_and_register_callbacks(monkeypatch, manager):
    class Conf(SimpleNamespace):
        pass

    confs = [
        Conf(name="srv1", host="h", port=6667),
        Conf(name="srv2", host="h2", port=6667),
    ]
    monkeypatch.setattr(bm, "load_env_file", lambda: True, raising=True)
    monkeypatch.setattr(bm, "get_server_configs", lambda: confs, raising=True)

    callbacks = {}

    class Srv:
        def __init__(self, cfg, bot, ev):
            self.config = cfg
            self.quit_message = None

        def register_callback(self, ev, fn):
            callbacks.setdefault(ev, 0)
            callbacks[ev] += 1

    monkeypatch.setattr(bm, "Server", Srv, raising=True)

    ok = manager.load_configurations()
    assert ok is True and set(manager.servers.keys()) == {"srv1", "srv2"}

    manager.register_callbacks()
    # message/join/part/quit expected across both servers
    assert callbacks.get("message") == 2
    assert callbacks.get("join") == 2
    assert callbacks.get("part") == 2
    assert callbacks.get("quit") == 2


def test_handle_message_core_paths(monkeypatch, manager):
    # Prepare server stub that collects responses
    sent = []

    class Srv:
        def __init__(self):
            self.config = SimpleNamespace(name="srv")

        def send_message(self, t, m):
            sent.append(("msg", t, m))

        def send_notice(self, t, m):
            sent.append(("not", t, m))

    server = Srv()

    # Stub youtube service and GPT service
    class YT:
        def extract_video_id(self, text):
            return "vid" if "youtube" in text else None

        def get_video_info(self, vid):
            return {"ok": True}

        def format_video_info_message(self, data):
            return "ytinfo"

    manager.youtube_service = YT()

    class GPT:
        def __init__(self):
            self.model = "m"

        def chat(self, msg, sender):
            return "line1\nline2"

    manager.gpt_service = GPT()

    # Wrap to identity to keep lines
    monkeypatch.setattr(
        manager,
        "_wrap_irc_message_utf8_bytes",
        lambda m, reply_target=None, **k: str(m).split("\n"),
        raising=True,
    )
    # No-op processor
    monkeypatch.setenv("USE_NOTICES", "false")
    monkeypatch.setenv("TAMAGOTCHI_ENABLED", "true")
    monkeypatch.setattr(
        bm,
        "command_loader",
        SimpleNamespace(enhanced_process_irc_message=lambda *a, **k: None),
        raising=False,
    )

    manager._handle_message(
        server, "someone", "#chan", "check youtube https://youtube.com/watch?v=x"
    )
    manager._handle_message(server, "nick", "MyBot", "MyBot: hello there")

    # At least ytinfo and two GPT lines should be sent
    texts = [m for _, _, m in sent]
    assert any("ytinfo" in m for m in texts)
    assert any("line1" in m for m in texts)


def test_send_to_all_servers_and_notices(monkeypatch, manager):
    out = []

    class S:
        def __init__(self, name):
            self.config = SimpleNamespace(name=name)

        def send_message(self, t, m):
            out.append(("msg", t, m))

        def send_notice(self, t, m):
            raise RuntimeError("boom")

        def stop(self, **k):
            pass

    manager.servers = {"a": S("a"), "b": S("b")}
    manager.send_to_all_servers("#c", "hi")
    manager.send_notice_to_all_servers("#c", "hi")
    assert len(out) == 2


def test_fetch_title_variants(monkeypatch, manager):
    # Skip blacklisted domain
    assert (
        manager._fetch_title(
            SimpleNamespace(send_message=lambda t, m: None),
            "#c",
            "https://youtube.com/watch?v=x",
        )
        is None
    )

    # Non-HTML content -> skip
    class Resp:
        status_code = 200
        headers = {"Content-Type": "application/json"}
        content = b"{}"

    # Patch requests module used by function's local import via sys.modules
    import sys as _sys
    import types

    dummy_requests = types.SimpleNamespace(get=lambda url, **k: Resp())
    _sys.modules["requests"] = dummy_requests
    manager._fetch_title(
        SimpleNamespace(send_message=lambda t, m: None), "#c", "http://example.com"
    )

    # HTML with title
    html = b"<html><head><title> My   Page  </title></head><body></body></html>"

    class Resp2:
        status_code = 200
        headers = {"Content-Type": "text/html"}
        content = html

    _sys.modules["requests"] = types.SimpleNamespace(get=lambda url, **k: Resp2())
    sent = []
    manager._send_response = lambda irc, tgt, msg: sent.append(msg)
    manager._fetch_title(
        SimpleNamespace(send_message=lambda t, m: None), "#c", "http://site.com"
    )
    assert any("My Page" in m for m in sent)

    # Error during fetch
    import sys as _sys
    import types

    _sys.modules["requests"] = types.SimpleNamespace(
        get=lambda url, **k: (_ for _ in ()).throw(RuntimeError("e"))
    )
    manager._fetch_title(
        SimpleNamespace(send_message=lambda t, m: None), "#c", "http://err.com"
    )


def test_get_subscriptions_module_import_error(monkeypatch, manager):
    import builtins as _bi

    real_import = _bi.__import__

    def fake_import(name, *args, **kwargs):
        if name == "subscriptions":
            raise ImportError("nope")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(_bi, "__import__", fake_import)
    mod = manager._get_subscriptions_module()
    subs = mod.get_subscribers("varoitukset")
    assert subs == []


def test_handle_fmi_and_otiedote_release(monkeypatch, manager):
    # Subscribers flow
    subs = SimpleNamespace(
        get_subscribers=lambda topic: (
            [("#c", "srv")] if topic in ("varoitukset", "onnettomuustiedotteet") else []
        )
    )
    monkeypatch.setattr(
        manager, "_get_subscriptions_module", lambda: subs, raising=True
    )
    sent = []
    manager.servers = {
        "srv": SimpleNamespace(
            send_message=lambda t, m: sent.append((t, m)),
            send_notice=lambda t, m: sent.append((t, m)),
        )
    }

    manager._handle_fmi_warnings(["w1", "w2"])
    manager._handle_otiedote_release("Title", "http://url", "Desc")
    assert any("w1" in m for _, m in sent)
    assert manager.latest_otiedote and manager.latest_otiedote["title"] == "Title"

    # No subscribers
    subs2 = SimpleNamespace(get_subscribers=lambda topic: [])
    monkeypatch.setattr(
        manager, "_get_subscriptions_module", lambda: subs2, raising=True
    )
    manager._handle_fmi_warnings(["w1"])  # should do nothing
    manager._handle_otiedote_release("T", "U")  # not broadcast

    # Error path in get_subscribers
    def boom(topic):
        raise RuntimeError("err")

    subs_err = SimpleNamespace(get_subscribers=boom)
    monkeypatch.setattr(
        manager, "_get_subscriptions_module", lambda: subs_err, raising=True
    )
    manager._handle_otiedote_release("T", "U")


def test_stop_and_wait_for_shutdown(monkeypatch, manager):
    # Prepare services
    manager.fmi_warning_service = SimpleNamespace(start=lambda: None, stop=lambda: None)
    manager.otiedote_service = SimpleNamespace(start=lambda: None, stop=lambda: None)

    # Prepare servers and threads
    class Thr:
        def __init__(self, alive):
            self._alive = alive

        def join(self, timeout=None):
            self._alive = False

        def is_alive(self):
            return self._alive

    s1 = SimpleNamespace(stop=lambda **k: None)
    s2 = SimpleNamespace(stop=lambda **k: None)
    manager.servers = {"a": s1, "b": s2}
    manager.server_threads = {"a": Thr(True), "b": Thr(False)}

    # Avoid sleep
    monkeypatch.setattr(bm.time, "sleep", lambda *a, **k: None, raising=False)

    manager.stop("bye")
    # wait_for_shutdown without KeyboardInterrupt
    manager.wait_for_shutdown()


def test_wait_for_shutdown_keyboard_interrupt(monkeypatch, manager):
    class T:
        def __init__(self):
            self._alive = True

        def join(self, timeout=None):
            self._alive = False

        def is_alive(self):
            return self._alive

    manager.server_threads = {"x": T()}
    # Force KeyboardInterrupt during loop
    calls = {"n": 0}

    def fake_sleep(_):
        calls["n"] += 1
        raise KeyboardInterrupt

    monkeypatch.setattr(bm.time, "sleep", fake_sleep, raising=False)
    with pytest.raises(KeyboardInterrupt):
        manager.wait_for_shutdown()


def test_send_latest_otiedote_and_weather_and_scheduled(monkeypatch, manager, tmp_path):
    # send latest without info
    sent = []
    manager._send_response = lambda s, t, m: sent.append(m)
    manager._send_latest_otiedote(SimpleNamespace(), "#c")
    assert any("Ei tallennettua" in m for m in sent)

    # send with description and wrapper lines
    sent.clear()
    manager.latest_otiedote = {"description": "desc", "url": "u"}
    monkeypatch.setattr(
        manager,
        "_wrap_irc_message_utf8_bytes",
        lambda m, reply_target=None, **k: ["L1", "", None],
        raising=True,
    )
    manager._send_latest_otiedote(SimpleNamespace(), "#c")
    assert sent == ["L1"]

    # console weather: no service then with service error
    manager.weather_service = None
    manager._console_weather(None, None, "X")

    class WS:
        def get_weather(self, loc):
            raise RuntimeError("err")

        def format_weather_message(self, d):
            return "msg"

    manager.weather_service = WS()
    manager._console_weather(None, None, "X")

    # scheduled message ok and error
    with patch(
        "services.scheduled_message_service.send_scheduled_message", return_value=123
    ):
        res = manager._send_scheduled_message(SimpleNamespace(), "#c", "m", 1, 2, 3)
        assert "✅" in res
    with patch(
        "services.scheduled_message_service.send_scheduled_message",
        side_effect=RuntimeError("e"),
    ):
        res2 = manager._send_scheduled_message(SimpleNamespace(), "#c", "m", 1, 2, 3)
        assert "❌" in res2

    # eurojackpot numbers/results success and error
    with patch(
        "services.eurojackpot_service.get_eurojackpot_numbers",
        return_value={"ok": True},
    ):
        assert manager._get_eurojackpot_numbers() == {"ok": True}
    with patch(
        "services.eurojackpot_service.get_eurojackpot_numbers",
        side_effect=RuntimeError("e"),
    ):
        assert "❌" in manager._get_eurojackpot_numbers()

    with patch(
        "services.eurojackpot_service.get_eurojackpot_results",
        return_value={"ok": True},
    ):
        assert manager._get_eurojackpot_results() == {"ok": True}
    with patch(
        "services.eurojackpot_service.get_eurojackpot_results",
        side_effect=RuntimeError("e"),
    ):
        assert "❌" in manager._get_eurojackpot_results()


def test_search_and_youtube_handlers(monkeypatch, manager):
    # _search_youtube success and error
    class Y:
        def search_videos(self, q, max_results=3):
            return {"list": []}

        def format_search_results_message(self, d):
            return "ok"

        def extract_video_id(self, t):
            return "id" if "watch" in t else None

        def get_video_info(self, vid):
            return {"id": vid}

        def format_video_info_message(self, d):
            return "info"

    manager.youtube_service = Y()

    assert manager._search_youtube("q") == "ok"
    with patch.object(
        manager.youtube_service, "search_videos", side_effect=RuntimeError("e")
    ):
        assert "Error" in manager._search_youtube("q")

    # _send_youtube_info URL and query paths and error
    sent = []
    manager._send_response = lambda i, c, m: sent.append(m)
    manager._send_youtube_info(
        SimpleNamespace(), "#c", "https://youtube.com/watch?v=abc"
    )
    manager._send_youtube_info(SimpleNamespace(), "#c", "query")
    with patch.object(
        manager.youtube_service, "extract_video_id", side_effect=RuntimeError("e")
    ):
        manager._send_youtube_info(SimpleNamespace(), "#c", "query")

    # _handle_youtube_urls
    sent.clear()
    ctx = {
        "server": SimpleNamespace(),
        "target": "#c",
        "text": "https://youtube.com/watch?v=x",
    }
    manager._send_response = lambda s, t, m: sent.append(m)
    manager._handle_youtube_urls(ctx)
    assert sent and sent[0] == "info"


def test_readline_setup_and_protected_output(monkeypatch, manager, tmp_path):
    # Non-interactive path
    monkeypatch.setattr(
        manager, "_is_interactive_terminal", lambda: False, raising=True
    )
    manager._setup_readline_history()

    # Interactive with stub readline
    class RL:
        def set_history_length(self, n):
            pass

        def read_history_file(self, p):
            raise FileNotFoundError

        def parse_and_bind(self, s):
            pass

        def write_history_file(self, p):
            pass

        def redisplay(self):
            pass

    monkeypatch.setattr(bm, "READLINE_AVAILABLE", True, raising=False)
    monkeypatch.setattr(bm, "readline", RL(), raising=False)
    monkeypatch.setattr(manager, "_is_interactive_terminal", lambda: True, raising=True)
    manager._setup_readline_history()
    manager._save_command_history()

    # Protected print/std writes
    manager._input_active = True
    manager._history_file = str(tmp_path / "hist")
    # Replace original stdout/stderr writers to avoid escape sequences clutter
    manager._original_stdout_write = lambda t: None
    manager._original_stderr_write = lambda t: None
    # Calls should not raise
    manager._protected_print("x")
    manager._protected_stdout_write("x")
    manager._protected_stderr_write("x")


def test_console_listener_commands_and_chat(monkeypatch, manager):
    # Interactive terminal
    monkeypatch.setattr(manager, "_is_interactive_terminal", lambda: True, raising=True)

    # Provide GPT chat
    class G:
        def __init__(self):
            self.model = "m"

        def chat(self, msg, sender):
            return "ok"

    manager.gpt_service = G()
    # Command loader that raises to exercise error path
    import sys as _sys
    import types

    _sys.modules["command_loader"] = types.SimpleNamespace(
        enhanced_process_console_command=lambda *a, **k: (_ for _ in ()).throw(
            RuntimeError("boom")
        )
    )
    # Inputs: chat -> command -> quit
    inputs = iter(["hello", "!cmd", "quit"])
    import builtins as _bi

    monkeypatch.setattr(_bi, "input", lambda prompt="": next(inputs))
    manager.stop_event.clear()
    manager._listen_for_console_commands()


def test_console_listener_non_interactive_immediate_exit(monkeypatch, manager):
    # Non-interactive: should not block if stop_event is set
    manager.stop_event.set()
    monkeypatch.setattr(
        manager, "_is_interactive_terminal", lambda: False, raising=True
    )
    manager._listen_for_console_commands()


def test_console_listener_quit(monkeypatch, manager):
    # Make interactive and feed inputs including quit
    monkeypatch.setattr(manager, "_is_interactive_terminal", lambda: True, raising=True)
    inputs = iter([" ", "quit"])  # blank then quit
    import builtins as _bi

    monkeypatch.setattr(_bi, "input", lambda prompt="": next(inputs))
    # Ensure stop_event not set initially
    manager.stop_event.clear()
    manager._listen_for_console_commands()
    assert manager.stop_event.is_set()


def test_start_flow(monkeypatch, manager):
    # Mock configuration load and services start
    monkeypatch.setattr(manager, "load_configurations", lambda: True, raising=True)
    manager.fmi_warning_service = SimpleNamespace(start=lambda: None)
    manager.otiedote_service = SimpleNamespace(start=lambda: None)

    # Provide one server
    class S:
        def __init__(self):
            self.config = SimpleNamespace(name="srv")

        def start(self):
            pass

        def register_callback(self, ev, fn):
            pass

    manager.servers = {"srv": S()}

    # Patch threading.Thread to no-op thread
    class T:
        def __init__(self, target=None, name=None, daemon=None):
            self._target = target

        def start(self):
            pass

    monkeypatch.setattr(bm.threading, "Thread", T)
    ok = manager.start()
    assert ok is True


def test_setup_protected_output_direct(manager):
    # Directly call but restore global state afterwards to avoid test runner side-effects
    import builtins as _bi
    import sys as _sys

    orig_print = _bi.print
    orig_out = _sys.stdout.write
    orig_err = _sys.stderr.write
    try:
        manager._setup_protected_output()
    finally:
        # Restore globals
        _bi.print = orig_print
        _sys.stdout.write = orig_out
        _sys.stderr.write = orig_err


def test_nanoleet_achievement_send(monkeypatch, manager):
    # Detector returns non-'leet' level to trigger send
    class D:
        def get_timestamp_with_nanoseconds(self):
            return "ts"

        def check_message_for_leet(self, sender, ts, msg):
            return ("ach", "super")

    manager.nanoleet_detector = D()
    sent = []
    manager._send_response = lambda s, t, m: sent.append(m)
    server = SimpleNamespace(config=SimpleNamespace(name="srv"))
    manager._handle_message(server, "u", "#c", "hello")
    assert "ach" in sent


def test_process_commands_paths(monkeypatch, manager):
    server = SimpleNamespace(config=SimpleNamespace(name="srv"))
    # !otiedote should call send_latest and return early
    called = {"n": 0}

    def fake_send_latest(s, t):
        called["n"] += 1

    monkeypatch.setattr(
        manager, "_send_latest_otiedote", fake_send_latest, raising=True
    )
    ctx = {
        "server": server,
        "server_name": "srv",
        "sender": "nick",
        "target": "#c",
        "text": "!otiedote",
    }
    manager._process_commands(ctx)
    assert called["n"] == 1

    # enhanced_process_irc_message gets called for normal text
    import sys as _sys
    import types

    called2 = {"args": None}
    _sys.modules["command_loader"] = types.SimpleNamespace(
        enhanced_process_irc_message=lambda *a, **k: called2.update({"args": a})
    )
    ctx2 = {
        "server": server,
        "server_name": "srv",
        "sender": "nick",
        "target": "#c",
        "text": "hello",
    }
    manager._process_commands(ctx2)
    assert called2["args"] is not None
