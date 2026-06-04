"""Focused behavioral coverage for MessageHandler helpers."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from handlers import message_handler
from handlers.message_handler import MessageHandler


@pytest.fixture
def handler(tmp_path):
    instance = object.__new__(MessageHandler)
    instance.service_manager = Mock()
    instance.service_manager.get_service.return_value = None
    instance.data_manager = Mock()
    instance.data_manager.state_file = tmp_path / "state.json"
    instance.data_manager.load_state.return_value = {}
    instance.data_manager.load_kraksdebug_state.return_value = {}
    instance.drink_tracker = Mock()
    instance.bac_tracker = Mock()
    instance.general_words = Mock()
    instance.word_associations = Mock()
    instance.tamagotchi = Mock()
    instance.lemmatizer = None
    instance.use_notices = True
    instance.tamagotchi_enabled = False
    instance.four_twenty_enabled = True
    instance._sanaketju_game = Mock(active=False)
    instance.x_api_queue = []
    instance.x_api_queue_lock = Mock()
    instance.x_api_queue_lock.__enter__ = Mock()
    instance.x_api_queue_lock.__exit__ = Mock(return_value=False)
    instance.x_api_last_request_time = 0
    instance.x_api_rate_limit_seconds = 300
    return instance


@pytest.fixture
def server():
    return SimpleNamespace(
        config=SimpleNamespace(name="srv", channels=["#chan"]),
        bot_name="Bot",
        connected=True,
        send_notice=Mock(),
        send_message=Mock(),
        send_raw=Mock(),
    )


def test_settings_and_x_cache_initialization(handler):
    handler.data_manager.load_state.side_effect = [
        {},
        RuntimeError("bad"),
        {},
        {"x_cache_settings": {}},
        RuntimeError("bad"),
    ]
    assert handler._load_420_enabled_setting() is True
    assert handler._load_420_enabled_setting() is True
    handler._save_420_enabled_setting(False)
    handler._initialize_x_cache_settings()
    handler._initialize_x_cache_settings()


def test_send_response_modes_and_connected_server(handler, server, monkeypatch):
    logged = []
    monkeypatch.setattr(
        message_handler.logger, "msg", lambda msg, *_: logged.append(msg)
    )
    handler._send_response(None, None, "console")
    handler._send_response(server, None, "missing target")
    handler._send_response(server, "console", "console target")
    server.connected = False
    handler._send_response(server, "#chan", "offline")
    server.connected = True
    handler._send_response(server, "#chan", "hello")
    server.send_notice.assert_called_once_with("#chan", "hello")
    handler.use_notices = False
    handler._send_response(server, "nick", "hi")
    server.send_message.assert_called_once_with("nick", "hi")
    assert logged[:3] == ["console", "missing target", "console target"]


def test_send_response_records_notice_latency(handler, server):
    handler._record_passive_latency_start = Mock()
    handler._send_response(server, "#chan", "hello")
    handler._record_passive_latency_start.assert_called_once_with(
        server, "#chan", "hello"
    )


def test_wrap_irc_message_utf8_bytes(handler):
    assert handler._wrap_irc_message_utf8_bytes(None) == []
    assert handler._wrap_irc_message_utf8_bytes("one\n\ntwo") == ["one", "", "two"]
    long_word = "ä" * 500
    lines = handler._wrap_irc_message_utf8_bytes(long_word, max_lines=2)
    assert len(lines) == 2
    assert lines[-1].endswith("...")
    assert all(len(line.encode("utf-8")) <= 425 for line in lines)


def test_url_classification_and_title_bans(handler, monkeypatch):
    assert handler._is_youtube_url("https://youtu.be/abc")
    assert handler._is_x_url("https://x.com/user/status/123")
    monkeypatch.setenv("TITLE_BLACKLIST_DOMAINS", "blocked.example")
    monkeypatch.setenv("TITLE_BLACKLIST_EXTENSIONS", ".pdf")
    assert handler._is_url_blacklisted("https://blocked.example/a")
    assert handler._is_url_blacklisted("https://example.com/a.pdf")
    assert not handler._is_url_blacklisted("https://example.com/a")
    monkeypatch.setenv("TITLE_BANNED_TEXTS", "Forbidden;Nope")
    assert handler._is_title_banned("403 Forbidden")
    assert not handler._is_title_banned("Useful title")


def test_fetch_title_html_x_and_blacklist(handler, server, monkeypatch):
    handler._send_response = Mock()
    handler._fetch_x_post_content = Mock()
    monkeypatch.setenv("TITLE_BLACKLIST_DOMAINS", "skip.example")
    response = SimpleNamespace(
        status_code=200,
        headers={"Content-Type": "text/html"},
        content=b"<html><title>  Useful \xc2\xad title </title></html>",
    )
    monkeypatch.setattr(message_handler.requests, "get", Mock(return_value=response))
    handler._fetch_title(
        server,
        "#chan",
        "https://x.com/u/status/1 https://skip.example/a https://ok.example/a",
    )
    handler._fetch_x_post_content.assert_called_once()
    sent_title = handler._send_response.call_args.args[-1]
    assert sent_title.startswith("📄 Useful ")
    assert sent_title.endswith(" title")


def test_x_cache_hit_expiry_and_size_management(handler, monkeypatch):
    monkeypatch.setattr(message_handler.time, "time", lambda: 5000)
    handler.data_manager.load_state.return_value = {
        "x_cache": {"u": {"response": "cached", "timestamp": 4999}},
        "x_cache_settings": {"expiration_hours": 1, "max_entries": 10},
    }
    assert handler._get_cached_x_response("u") == "cached"
    handler.data_manager.load_state.return_value["x_cache"]["u"]["timestamp"] = 0
    assert handler._get_cached_x_response("u") is None
    handler.data_manager.load_state.return_value = {
        "x_cache_settings": {"max_entries": 10}
    }
    cache = {str(i): {"timestamp": i} for i in range(12)}
    handler._manage_x_cache_size(cache)
    assert len(cache) == 10
    handler.data_manager.load_state.return_value = {}
    handler._cache_x_response("new", "text")
    assert handler.data_manager.save_state.called


def test_fetch_x_post_content_cached_and_immediate(handler, server, monkeypatch):
    handler._send_response = Mock()
    handler._get_cached_x_response = Mock(return_value="cached")
    handler._fetch_x_post_content(server, "#chan", "https://x.com/u/status/123")
    handler._send_response.assert_called_once_with(server, "#chan", "🐦 cached")
    handler._send_response.reset_mock()
    handler._get_cached_x_response.return_value = None
    handler._process_x_api_request = Mock()
    monkeypatch.setattr(message_handler.time, "time", lambda: 1000)
    handler._fetch_x_post_content(server, "#chan", "https://x.com/u/status/456")
    handler._process_x_api_request.assert_called_once_with(
        server, "#chan", "https://x.com/u/status/456", "456"
    )


def test_nanoleet_and_420_paths(handler, server, monkeypatch):
    handler._send_response = Mock()
    detector = Mock()
    detector.get_timestamp_with_nanoseconds.return_value = "time"
    detector.check_message_for_leet.return_value = ("nano", "nanoleet")
    detector.check_420_leet.return_value = None
    handler.service_manager.get_service.return_value = detector
    context = {"server": server, "target": "#chan", "sender": "alice", "text": "420"}
    handler._check_nanoleet_achievement(context)
    monkeypatch.setattr(message_handler.secure_random, "choice", lambda _: "regular")
    handler._handle_420_response(context)
    assert handler._send_response.call_args_list[0].args[-1] == "nano"
    assert handler._send_response.call_args_list[1].args[-1] == "regular"
    detector.check_420_leet.return_value = ("special", "420")
    handler._handle_420_response(context)
    assert handler._send_response.call_args.args[-1] == "special"


def test_handle_youtube_urls_and_ai_chat(handler, server):
    handler._send_response = Mock()
    youtube = Mock()
    youtube.extract_video_id.return_value = "id"
    youtube.get_video_info.return_value = {"title": "video"}
    youtube.format_video_info_message.return_value = "video info"
    handler.service_manager.get_service.side_effect = lambda name: (
        youtube if name == "youtube" else Mock()
    )
    handler._handle_youtube_urls({"server": server, "target": "#chan", "text": "url"})
    handler.drink_tracker.process_message.return_value = []
    handler._chat_with_gpt = Mock(return_value="line one\nline two")
    asyncio.run(handler._handle_ai_chat("Bot: hello", "alice", "#chan", server))
    assert handler._send_response.call_count == 3


def test_service_proxies(handler, server, monkeypatch):
    handler._send_response = Mock()
    crypto = Mock()
    crypto.get_crypto_price.return_value = {"price": 12.5}
    alko = Mock()
    alko.get_product_info.return_value = {"name": "Beer"}
    alko.format_product_info.return_value = "Beer info"
    youtube = Mock()
    youtube.search_videos.return_value = []
    youtube.format_search_results_message.return_value = "results"
    services = {"crypto": crypto, "alko": alko, "youtube": youtube}
    handler.service_manager.get_service.side_effect = services.get
    assert handler._get_crypto_price("btc") == "12.50 EUR"
    assert handler._get_alko_product("beer") == "Beer info"
    assert handler._search_youtube("cats") == "results"
    handler._send_crypto_price(server, "#chan", "btc usd")
    handler._send_youtube_info(server, "#chan", "cats")
    assert handler._send_response.call_count == 2
    assert handler._format_counts({"a": 1}) == "a: 1"
    assert handler._format_counts("x") == "x"


def test_weather_prescription_and_drug_helpers(handler, server):
    handler._send_response = Mock()
    weather = Mock()
    weather.get_weather.return_value = {"temp": 1}
    weather.format_weather_message.return_value = "weather"
    rx = Mock(drugs={"a": {}})
    rx.format_profile.return_value = "profile"
    rx.check_interactions.return_value = "interaction"
    drug = Mock()
    drug.check_interactions.return_value = {
        "warnings": ["warn"],
        "unknown_drugs": ["mystery"],
        "interactions": [],
    }
    services = {"weather": weather, "prescription_interaction": rx, "drug": drug}
    handler.service_manager.get_service.side_effect = services.get
    handler._send_weather(server, "#chan", "Helsinki")
    assert handler._check_prescription_interactions("a") == "profile"
    assert handler._check_prescription_interactions("a, b") == "interaction"
    assert handler._check_drug_interactions("a b") == "warn | 💊 Unknown drugs: mystery"


def test_update_state_and_env_files(handler, tmp_path, monkeypatch):
    handler.data_manager.state_file.write_text("{}", encoding="utf-8")
    assert handler._update_state_file("TAMAGOTCHI_ENABLED", "true")
    state = json.loads(handler.data_manager.state_file.read_text(encoding="utf-8"))
    assert state["tamagotchi_enabled"] is True
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("A=1", encoding="utf-8")
    assert handler._update_env_file("A", "2")
    assert handler._update_env_file("B", "3")
    assert (tmp_path / ".env").read_text(encoding="utf-8") == "A=2\nB=3\n"


def test_numeric_ops_join_and_subscription_helpers(handler, server):
    manager = SimpleNamespace(
        joined_channels={},
        active_channel=None,
        active_server=None,
        console_manager=SimpleNamespace(active_channel=None, active_server=None),
        _servers={"srv": server},
    )
    handler.bot_manager = manager
    handler._handle_join(server, "Bot", "ident", "#chan")
    assert manager.active_channel == "#chan"
    server._pending_ops = {"srv": {"#chan": {"users": []}}}
    handler._handle_numeric(server, 353, "Bot", "= #chan :@alice +bob Bot")
    handler._handle_numeric(server, 366, "Bot", "#chan :End")
    assert server.send_raw.call_count == 2
    assert handler._get_subscription_server("srv") is server
    assert handler._can_send_subscription_target("srv", server, "#chan")


def test_toggle_tamagotchi_and_factory(handler, server, monkeypatch):
    handler._send_response = Mock()
    handler._update_state_file = Mock(return_value=True)
    result = handler.toggle_tamagotchi(server, "#chan", "alice")
    assert "enabled" in result
    monkeypatch.setattr(message_handler, "MessageHandler", Mock(return_value="handler"))
    assert message_handler.create_message_handler("services", "data") == "handler"


def test_track_urls_skips_service_construction_without_urls(handler, monkeypatch):
    create_tracker = Mock()
    monkeypatch.setattr(
        "services.url_tracker_service.create_url_tracker_service", create_tracker
    )
    handler._track_urls(
        {
            "server": Mock(),
            "sender": "alice",
            "server_name": "srv",
            "target": "#chan",
            "text": "ordinary chat without links",
        }
    )
    create_tracker.assert_not_called()
