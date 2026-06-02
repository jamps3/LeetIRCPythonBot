"""Coverage for the standalone latency tracking mixin."""

import threading
from types import SimpleNamespace
from unittest.mock import Mock

from handlers import latency_tracker
from handlers.latency_tracker import LatencyTrackerMixin
from handlers.message_handler import MessageHandler


def test_measure_send_and_check_latency_response(monkeypatch):
    tracker = LatencyTrackerMixin()
    tracker._store_lag = Mock()
    server = SimpleNamespace(name="srv", send_raw=Mock())
    monkeypatch.setattr(latency_tracker.time, "time", lambda: 10.25)

    assert tracker._measure_latency() == 10.25
    assert tracker._send_latency_ping(server, "#chan") == "lag_10250"
    server.send_raw.assert_called_once_with("PING :lag_10250")
    assert tracker._check_latency_response(server, "alice", "hello") is None
    assert tracker._check_latency_response(server, "alice", "PONG") is None
    assert tracker._check_latency_response(server, "alice", "PONG :other") is None
    assert tracker._check_latency_response(server, "alice", "PONG :lag_bad") is None
    assert (
        tracker._check_latency_response(server, "alice", "PONG :lag_10000") == "250.0ms"
    )
    tracker._store_lag.assert_called_once_with("srv", "alice", 250.0)


def test_load_and_save_lag_storage(monkeypatch):
    tracker = LatencyTrackerMixin()
    monkeypatch.setattr(
        latency_tracker,
        "load_json_file",
        lambda *_args, **_kwargs: {"srv|alice": 12.5, "invalid": 8},
    )
    assert tracker._load_lag_storage() == {("srv", "alice"): 12.5}

    monkeypatch.setattr(latency_tracker, "load_json_file", lambda *_a, **_k: [])
    assert tracker._load_lag_storage() == {}
    monkeypatch.setattr(
        latency_tracker, "load_json_file", Mock(side_effect=KeyError("bad"))
    )
    assert tracker._load_lag_storage() == {}

    save = Mock()
    monkeypatch.setattr(latency_tracker, "save_json_atomic", save)
    tracker._lag_storage = {("srv", "alice"): 5}
    tracker._save_lag_storage()
    assert save.call_args.args[1] == {"srv|alice": 5}
    save.side_effect = OSError("disk")
    tracker._save_lag_storage()


def test_store_get_list_and_clear_lags(monkeypatch):
    tracker = LatencyTrackerMixin()
    monkeypatch.setattr(tracker, "_load_lag_storage", lambda: {("a", "n"): 1})
    tracker._save_lag_storage = Mock()
    assert tracker._get_lag("a", "n") == 1
    tracker._store_lag("b", "m", 2)
    assert tracker._list_lags() == {("a", "n"): 1, ("b", "m"): 2}
    assert tracker._list_lags("b") == {("b", "m"): 2}
    assert tracker._clear_lag("b", "m")
    assert not tracker._clear_lag("missing", "m")


def test_lazy_storage_initialization_for_store_list_and_clear(monkeypatch):
    tracker = LatencyTrackerMixin()
    monkeypatch.setattr(tracker, "_load_lag_storage", lambda: {})
    tracker._save_lag_storage = Mock()
    tracker._store_lag("srv", "alice", 1)
    del tracker._lag_storage
    assert tracker._list_lags() == {}
    del tracker._lag_storage
    assert not tracker._clear_lag("srv", "alice")


def test_message_handler_latency_targets_and_network_pong(monkeypatch):
    tracker = object.__new__(MessageHandler)
    tracker.data_manager = Mock()
    tracker.data_manager.load_state.return_value = {
        "config": {"latency_nicks": [" Beiki ", "Beici", "Beiki", ""]}
    }
    tracker._store_lag = Mock()
    server = SimpleNamespace(config=SimpleNamespace(name="srv"), send_raw=Mock())
    monkeypatch.setattr("handlers.message_handler.time.time", lambda: 12.345)

    assert tracker._get_latency_nicks() == ["Beiki", "Beici"]
    assert tracker._send_network_latency_ping(server) == "latency_12345"
    server.send_raw.assert_called_once_with("PING :latency_12345")
    assert tracker._handle_pong(server, "keepalive") is None
    assert tracker._handle_pong(server, "latency_bad") is None
    assert tracker._handle_pong(server, "latency_12000") == (
        "IRC network latency on srv: 345ms"
    )
    tracker._store_lag.assert_called_once_with("srv", "__network__", 345)

    tracker.data_manager.load_state.return_value = {"config": {"latency_nicks": "x"}}
    assert tracker._get_latency_nicks() == []
    tracker.data_manager.load_state.side_effect = RuntimeError("bad")
    assert tracker._get_latency_nicks() == []


def test_message_handler_sends_ctcp_latency_ping(monkeypatch):
    tracker = object.__new__(MessageHandler)
    tracker._store_pending_ctcp_ping = Mock()
    server = SimpleNamespace(config=SimpleNamespace(name="srv"), send_raw=Mock())
    monkeypatch.setattr("handlers.message_handler.time.time", lambda: 1.5)
    tracker._send_ctcp_latency_ping(server, "Beiki", "#chan")
    server.send_raw.assert_called_once_with("PRIVMSG Beiki :\x01PING 1500\x01")
    tracker._store_pending_ctcp_ping.assert_called_once_with(
        "srv", "Beiki", 1500, "#chan"
    )


def test_passive_notice_latency_tracking(monkeypatch):
    tracker = object.__new__(MessageHandler)
    tracker.data_manager = Mock()
    tracker.data_manager.load_state.return_value = {
        "config": {
            "latency_nicks": ["Beiki", "Beici"],
            "latency_source_channel": "#joensuu",
            "latency_observer_channel": "!placeholder",
        }
    }
    tracker._pending_notice_latency = {}
    tracker._pending_notice_latency_lock = threading.Lock()
    tracker._store_lag = Mock()
    server = SimpleNamespace(config=SimpleNamespace(name="srv"))
    monkeypatch.setattr("handlers.message_handler.time.time_ns", lambda: 25_100_000_000)

    tracker._record_passive_latency_start(server, "#other", "hello")
    assert tracker._pending_notice_latency == {}
    tracker._record_passive_latency_start(server, "#JOENSUU", "hello")
    assert tracker._check_passive_latency_receipt(
        server,
        "Beiki",
        "!placeholder",
        "ke@vko22_00:00:25 -Beiki:!Beiki- grond 0.00.25,179052653: hello",
    )
    tracker._store_lag.assert_called_once_with("srv", "Beiki", 79.052653)
    assert tracker._check_passive_latency_receipt(
        server, "stranger", "!placeholder", "x"
    )
    assert not tracker._check_passive_latency_receipt(
        server, "Beiki", "#other", "hello"
    )


def test_passive_latency_announcement_parser_and_midnight_resolution():
    parse = MessageHandler._parse_passive_latency_announcement
    assert parse("invalid") is None
    assert parse(
        "ke@vko22_00:41:17 -Beibi:!Beiki- jamps 0.41.17,037949452: good gay."
    ) == ("good gay.", 2_477_037_949_452, "Beibi")
    assert parse("0.00.25,179052653: eka") == ("eka", 25_179_052_653, None)
    day_ns = 24 * 60 * 60 * 1_000_000_000
    assert (
        MessageHandler._nearest_receipt_time_ns(day_ns - 50_000_000, 25_000_000)
        == day_ns + 25_000_000
    )


def test_passive_latency_config_defaults_on_error():
    tracker = object.__new__(MessageHandler)
    tracker.data_manager = Mock()
    tracker.data_manager.load_state.side_effect = RuntimeError("bad")
    assert tracker._get_passive_latency_channels() == ("", "")
