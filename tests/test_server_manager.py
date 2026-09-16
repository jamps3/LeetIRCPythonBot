"""Tests for critical IRC server lifecycle orchestration."""

import threading
from types import SimpleNamespace
from unittest.mock import Mock

import server_manager as server_manager_module
from server_manager import ServerManager


class FakeThread:
    """Small deterministic replacement for a server worker thread."""

    instances = []

    def __init__(self, target=None, name=None, daemon=None):
        self.target = target
        self.name = name
        self.daemon = daemon
        self.started = False
        self.joined_with = None
        self.alive = False
        self.instances.append(self)

    def start(self):
        self.started = True
        self.alive = True

    def is_alive(self):
        return self.alive

    def join(self, timeout=None):
        self.joined_with = timeout
        self.alive = False


def make_manager():
    """Build a manager without constructing real network clients."""
    manager = object.__new__(ServerManager)
    manager.bot_name = "LeetBot"
    manager.stop_event = threading.Event()
    manager.bot_config = SimpleNamespace(latency_observer_channel="")
    manager.auto_connect = False
    manager.quit_message = "Bye"
    manager.servers = {}
    manager.server_threads = {}
    manager.joined_channels = {}
    manager.midnight_scheduler_thread = None
    manager._scheduler_running = False
    return manager


def make_server(name="network", *, connected=True):
    server = Mock()
    server.config = SimpleNamespace(
        name=name, host="irc.example.test", port=6697, quit_message=""
    )
    server.connected = connected
    return server


def test_load_server_configurations_builds_servers_and_adds_observer(monkeypatch):
    config = SimpleNamespace(
        name="network",
        host="irc.example.test",
        port=6697,
        channels=["#chat"],
        quit_message="Configured bye",
    )
    bot_config = SimpleNamespace(
        auto_connect=True,
        quit_message="Fallback bye",
        latency_observer_channel="#latency",
    )
    created = []

    class FakeServer:
        def __init__(self, server_config, bot_name, stop_event, manager_config):
            self.config = server_config
            self.bot_name = bot_name
            self.stop_event = stop_event
            self.manager_config = manager_config
            self.quit_message = ""
            created.append(self)

    monkeypatch.setattr(
        server_manager_module, "get_config", lambda: SimpleNamespace(servers=[config])
    )
    monkeypatch.setattr(server_manager_module, "Server", FakeServer)

    manager = ServerManager("LeetBot", threading.Event(), bot_config)

    assert config.channels == ["#chat", "#latency"]
    assert manager.auto_connect is True
    assert manager.servers == {"network": created[0]}
    assert manager.joined_channels == {"network": []}
    assert created[0].quit_message == "Configured bye"


def test_register_callbacks_registers_all_message_events():
    manager = make_manager()
    server = make_server()
    manager.servers = {"network": server}
    handler = Mock()

    manager.register_message_callbacks(handler)

    assert [call.args[0] for call in server.register_callback.call_args_list] == [
        "message",
        "notice",
        "join",
        "part",
        "quit",
        "numeric",
        "pong",
    ]


def test_start_servers_handles_missing_manual_and_auto_connect():
    manager = make_manager()
    manager._start_midnight_scheduler = Mock()

    assert manager.start_servers() is False

    manager.servers = {"network": make_server()}
    assert manager.start_servers() is True
    manager._start_midnight_scheduler.assert_called_once()

    manager.auto_connect = True
    manager.connect_to_servers = Mock(return_value=True)
    assert manager.start_servers() is True
    manager.connect_to_servers.assert_called_once_with()


def test_connect_and_disconnect_manage_worker_threads(monkeypatch):
    FakeThread.instances.clear()
    monkeypatch.setattr(server_manager_module.threading, "Thread", FakeThread)
    manager = make_manager()
    server = make_server()
    manager.servers = {"network": server}

    assert manager.connect_to_servers(["missing"]) is False
    assert manager.connect_to_servers() is True
    thread = manager.server_threads["network"]
    assert thread.started is True
    assert thread.target is server.start
    assert manager.connect_to_servers() is False

    assert manager.disconnect_from_servers(quit_message="Closing") is True
    server.quit.assert_called_once_with("Closing")
    assert thread.joined_with == 5.0
    assert manager.server_threads == {}


def test_channel_status_broadcast_and_shutdown_paths():
    manager = make_manager()
    first = make_server("first")
    second = make_server("second")
    second.send_message.side_effect = RuntimeError("unavailable")
    second.send_notice.side_effect = RuntimeError("unavailable")
    manager.servers = {"first": first, "second": second}
    manager.joined_channels = {"first": [], "second": []}

    manager.send_to_all_servers("#chat", "hello")
    manager.send_notice_to_all_servers("#chat", "notice")
    first.send_message.assert_called_once_with("#chat", "hello")
    first.send_notice.assert_called_once_with("#chat", "notice")

    assert manager.join_channel("first", "chat", "key") is True
    first.join_channel.assert_called_once_with("#chat", "key")
    assert manager.get_joined_channels("first") == {"first": ["#chat"]}
    assert manager.part_channel("first", "chat", "later") is True
    first.part_channel.assert_called_once_with("#chat", "later")
    assert manager.join_channel("missing", "chat") is False
    assert manager.part_channel("missing", "chat") is False

    manager.disconnect_from_servers = Mock()
    scheduler = FakeThread()
    scheduler.alive = True
    manager.midnight_scheduler_thread = scheduler
    manager._scheduler_running = True
    manager.shutdown("Stopping")

    manager.disconnect_from_servers.assert_called_once_with(quit_message="Stopping")
    assert scheduler.joined_with == 1.0
    assert manager.servers == {}
    assert manager.joined_channels == {}


def test_server_status_reports_connected_thread_and_unknown_server():
    manager = make_manager()
    server = make_server(connected=True)
    thread = FakeThread()
    thread.alive = True
    manager.servers = {"network": server}
    manager.server_threads = {"network": thread}
    manager.joined_channels = {"network": ["#chat"]}

    assert manager.is_server_connected("network") is True
    assert manager.is_server_connected("missing") is False
    assert manager.get_server_status("missing") == {
        "error": "Server 'missing' not found"
    }
    assert manager.get_server_status("network") == {
        "name": "network",
        "host": "irc.example.test",
        "port": 6697,
        "connected": True,
        "thread_alive": True,
        "channels": ["#chat"],
    }


def test_server_manager_reports_all_status_and_connected_servers():
    manager = make_manager()
    connected = make_server("connected", connected=True)
    disconnected = make_server("disconnected", connected=False)
    thread = FakeThread()
    thread.alive = True
    manager.servers = {"connected": connected, "disconnected": disconnected}
    manager.server_threads = {"connected": thread}
    manager.joined_channels = {"connected": ["#chat"], "disconnected": []}

    assert manager.get_server("connected") is connected
    assert manager.get_server("missing") is None
    assert manager.get_all_servers() == manager.servers
    assert manager.get_connected_servers() == {"connected": connected}
    assert manager.get_server_status() == {
        "connected": {
            "host": "irc.example.test",
            "port": 6697,
            "connected": True,
            "thread_alive": True,
            "channels": ["#chat"],
        },
        "disconnected": {
            "host": "irc.example.test",
            "port": 6697,
            "connected": False,
            "thread_alive": False,
            "channels": [],
        },
    }
    assert manager.get_joined_channels() == manager.joined_channels


def test_channel_operations_and_disconnect_failures_leave_state_consistent():
    manager = make_manager()
    server = make_server(connected=True)
    server.join_channel.side_effect = RuntimeError("banned")
    server.part_channel.side_effect = RuntimeError("not joined")
    server.quit.side_effect = RuntimeError("socket closed")
    thread = FakeThread()
    thread.alive = True
    manager.servers = {"network": server}
    manager.server_threads = {"network": thread}
    manager.joined_channels = {"network": ["#chat"]}

    assert manager.join_channel("network", "new") is False
    assert manager.joined_channels["network"] == ["#chat"]
    assert manager.part_channel("network", "chat") is False
    assert manager.joined_channels["network"] == ["#chat"]
    assert manager.disconnect_from_servers() is False
    assert manager.server_threads == {}


def test_add_server_and_connect_builds_config_and_starts_connection(monkeypatch):
    manager = make_manager()
    created = []

    class FakeServer:
        def __init__(self, config, bot_name, stop_event, bot_config):
            self.config = config
            self.quit_message = ""
            created.append(self)

    monkeypatch.setattr(server_manager_module, "Server", FakeServer)
    manager.connect_to_servers = Mock(return_value=True)

    assert (
        manager.add_server_and_connect(
            "new", "irc.new.test", 6697, ["#chat"], ["secret"], use_tls=True
        )
        is True
    )

    assert created[0].config.host == "irc.new.test"
    assert created[0].config.port == 6697
    assert created[0].config.channels == ["#chat"]
    assert created[0].config.keys == ["secret"]
    assert created[0].config.tls is True
    assert manager.joined_channels == {"new": []}
    manager.connect_to_servers.assert_called_once_with(["new"])
