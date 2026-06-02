"""Focused behavioral coverage for ConsoleManager."""

import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import console_manager
from console_manager import ConsoleManager


@pytest.fixture
def manager():
    instance = object.__new__(ConsoleManager)
    instance.service_manager = Mock()
    instance.message_handler = Mock()
    instance.server_manager = Mock()
    instance.server_manager.servers = {}
    instance.server_manager.server_threads = {}
    instance.server_manager.bot_name = "Bot"
    instance.stop_event = threading.Event()
    instance.bot_manager = None
    instance.console_mode = True
    instance.readline_available = False
    instance.readline = None
    instance._history_file = None
    instance._input_active = False
    instance.active_channel = None
    instance.active_server = None
    return instance


def test_init_setters_terminal_and_factory(monkeypatch):
    monkeypatch.setattr(ConsoleManager, "_setup_readline", Mock())
    monkeypatch.setattr(ConsoleManager, "_setup_console_output_protection", Mock())
    instance = ConsoleManager()
    values = [Mock(), Mock(), Mock(), Mock(), threading.Event()]
    instance.set_message_handler(values[0])
    instance.set_server_manager(values[1])
    instance.set_service_manager(values[2])
    instance.set_bot_manager(values[3])
    instance.set_stop_event(values[4])
    assert instance.message_handler is values[0]
    monkeypatch.setattr(console_manager.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(console_manager.sys.stdout, "isatty", lambda: True)
    assert instance._is_interactive_terminal()
    monkeypatch.setattr(console_manager.sys.stdin, "isatty", Mock(side_effect=OSError))
    assert not instance._is_interactive_terminal()
    monkeypatch.setattr(console_manager, "ConsoleManager", Mock(return_value="console"))
    assert console_manager.create_console_manager(1, 2, 3, values[4]) == "console"


def test_readline_history_and_shutdown(manager):
    readline = Mock()
    readline.read_history_file.side_effect = FileNotFoundError
    manager.readline = readline
    manager.readline_available = True
    manager._setup_readline_history()
    assert manager._history_file == "data\\leetbot_history"
    assert readline.parse_and_bind.call_count == 9
    manager._save_command_history()
    readline.write_history_file.assert_called_once()
    manager.shutdown()


def test_process_console_input_routes(manager):
    manager._handle_console_quit = Mock()
    manager._handle_console_command = Mock()
    manager._handle_channel_command = Mock()
    manager._handle_ai_chat_command = Mock()
    manager._handle_channel_message = Mock()
    for text in ["quit", "!status", "#chan", "-hello", "chat"]:
        manager._process_console_input(text)
    manager._handle_console_quit.assert_called_once()
    manager._handle_console_command.assert_called_once_with("!status")
    manager._handle_channel_command.assert_called_once_with("#chan")
    manager._handle_ai_chat_command.assert_called_once_with("-hello")
    manager._handle_channel_message.assert_called_once_with("chat")


def test_console_command_dispatch(manager, monkeypatch):
    methods = {
        "connect": "_console_connect",
        "disconnect": "_console_disconnect",
        "status": "_console_status",
        "channels": "_get_channel_status",
        "reload": "_console_reload",
        "rl": "_console_reload",
    }
    for name in set(methods.values()):
        setattr(manager, name, Mock(return_value=name))
    for command, method in methods.items():
        manager._handle_console_command(f"!{command} arg")
        getattr(manager, method).assert_called()

    process = Mock()
    monkeypatch.setattr("command_loader.process_console_command", process)
    manager._create_console_bot_functions = Mock(return_value={"x": 1})
    manager._handle_console_command("!ping")
    process.assert_called_once_with("!ping", {"x": 1})


def test_server_connect_disconnect_and_status(manager):
    thread = Mock(is_alive=lambda: True)
    server = SimpleNamespace(
        connected=True, config=SimpleNamespace(host="host", port=6667)
    )
    manager.server_manager.servers = {"srv": server}
    manager.server_manager.server_threads = {"srv": thread}
    assert "Connected to 1 servers" in manager._console_connect()
    assert "Added and connected" in manager._console_connect(
        "new", "host", "6697", "#a,#b", "tls"
    )
    assert manager.server_manager.add_server_and_connect.call_args.args == (
        "new",
        "host",
        6697,
        ["#a", "#b"],
    )
    assert manager.server_manager.add_server_and_connect.call_args.kwargs == {
        "use_tls": True
    }
    assert manager._console_connect("only") == (
        "Usage: !connect [server_name host [port] [channels] [tls]]"
    )
    assert manager._console_disconnect() == "Disconnected from all servers"
    assert manager._console_disconnect("srv") == "Disconnected from: srv"
    assert "✅ Connected" in manager._console_status()
    server.connected = False
    assert "🔄 Connecting" in manager._console_status()


def test_join_part_send_and_channel_status(manager):
    server = Mock(connected=True)
    manager.server_manager.servers = {"srv": server}
    manager.server_manager.server_threads = {"srv": Mock(is_alive=lambda: True)}
    manager.server_manager.get_server.return_value = server
    manager.bot_manager = SimpleNamespace(
        joined_channels={}, active_channel=None, active_server=None
    )
    manager.message_handler._record_passive_latency_start = Mock()
    assert manager._console_join_or_part_channel("chat") == (
        "Joined #chat on srv (now active)"
    )
    assert manager._console_send_to_channel("hello") == "[srv:#chat] <Bot> hello"
    manager.message_handler._record_passive_latency_start.assert_called_once_with(
        server, "#chat", "hello"
    )
    status = manager._get_channel_status()
    assert "[#chat]" in status and "srv (active)" in status
    assert manager._console_join_or_part_channel("#chat") == "Parted #chat on srv"
    assert manager.active_channel is None
    assert manager._normalize_channel("chat") == "#chat"


def test_ai_weather_electricity_and_models(manager, tmp_path, monkeypatch):
    gpt = SimpleNamespace(model="old", chat=Mock(return_value="answer"))
    weather = Mock()
    weather.get_weather.return_value = {"temp": 1}
    weather.format_weather_message.return_value = "sunny"
    electricity = Mock()
    electricity.get_electricity_price.return_value = {"price": 1}
    electricity.format_price_message.return_value = "cheap"
    services = {"gpt": gpt, "weather": weather, "electricity": electricity}
    manager.service_manager.get_service.side_effect = services.get
    manager.service_manager.is_service_available.return_value = True
    manager._process_ai_request("hi", "Console")
    manager._console_weather("Helsinki")
    manager._console_electricity([])
    monkeypatch.chdir(tmp_path)
    assert manager._set_openai_model("new") == "OpenAI model set to 'new' (persisted)"
    assert manager._get_openai_model() == "new"
    assert "OPENAI_MODEL=new" in (tmp_path / ".env").read_text(encoding="utf-8")


def test_send_electricity_price_branches(manager, monkeypatch):
    messages = []
    monkeypatch.setattr(console_manager.logger, "msg", messages.append)
    service = Mock()
    manager.service_manager.get_service.return_value = service
    service.parse_command_args.return_value = {
        "date": "today",
        "hour": 1,
        "quarter": None,
    }
    service.get_electricity_price.return_value = {"price": 1}
    service.format_price_message.return_value = "price"
    manager._send_electricity_price(None, None, "1")
    assert messages[-1] == "price"
    service.parse_command_args.return_value = {"error": "bad"}
    manager._send_electricity_price(None, None, [])
    assert messages[-1] == "⚡ bad"


def test_version_and_env_update(manager, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert manager._get_current_version() == "2.2.0"
    (tmp_path / "VERSION").write_text("1.2.3", encoding="utf-8")
    assert manager._get_current_version() == "1.2.3"
    assert manager._update_env_file("A", "1")
    assert manager._update_env_file("A", "2")
    assert (tmp_path / ".env").read_text(encoding="utf-8") == "A=2\n"


def test_setup_readline_noninteractive_and_listener_exit(manager, monkeypatch):
    manager._is_interactive_terminal = Mock(return_value=False)
    manager._setup_readline()
    assert manager._history_file is None
    manager.stop_event.set()
    manager._save_command_history = Mock()
    manager._listen_for_console_commands()
    manager._save_command_history.assert_called_once()


def test_listener_reads_input_and_handles_eof(manager, monkeypatch):
    manager._is_interactive_terminal = Mock(return_value=True)
    manager._process_console_input = Mock()
    values = iter([" hello ", EOFError()])

    def fake_input(_prompt):
        value = next(values)
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr("builtins.input", fake_input)
    manager._save_command_history = Mock()
    manager._listen_for_console_commands()
    manager._process_console_input.assert_called_once_with("hello")
    assert manager.stop_event.is_set()


def test_reload_outcomes(manager, monkeypatch):
    monkeypatch.setattr("reload_manager.reload_all_commands", lambda: (True, "done"))
    monkeypatch.setattr("reload_manager.verify_critical_commands", lambda: [])
    assert manager._console_reload() == "✅ done"
    monkeypatch.setattr("reload_manager.verify_critical_commands", lambda: ["help"])
    assert "critical commands missing: help" in manager._console_reload()
    monkeypatch.setattr("reload_manager.reload_all_commands", lambda: (False, "bad"))
    assert manager._console_reload() == "❌ bad"


def test_join_send_and_connect_failures(manager):
    manager.server_manager.servers = {}
    assert (
        manager._console_connect()
        == "No servers configured. Load configurations first."
    )
    assert manager._console_join_or_part_channel("chat") == (
        "No connected servers available. Use !connect first."
    )
    manager.active_channel = "#chat"
    manager.active_server = "srv"
    manager.server_manager.get_server.return_value = None
    assert manager._console_send_to_channel("x") == "Server srv is not connected."

    server = Mock(connected=True)
    server.send_message.side_effect = RuntimeError("send")
    manager.server_manager.get_server.return_value = server
    assert manager._console_send_to_channel("x") == "Error sending message: send"


def test_create_console_bot_functions(manager):
    server = Mock()
    manager.server_manager.servers = {"srv": server}
    manager.server_manager.get_server.return_value = server
    manager.server_manager.get_all_servers.return_value = {"srv": server}
    manager.service_manager.get_service.return_value = None
    manager.message_handler.data_manager = "dm"
    manager.message_handler.drink_tracker = "drink"
    manager.message_handler.bac_tracker = "bac"
    manager.message_handler.general_words = "words"
    manager.message_handler.tamagotchi = "pet"
    manager.message_handler.lemmatizer = "lemmatizer"
    manager._get_current_version = Mock(return_value="1.2.3")
    functions = manager._create_console_bot_functions()
    assert functions["server"] is server
    assert functions["BOT_VERSION"] == "1.2.3"
    assert functions["data_manager"] == "dm"
    functions["set_quit_message"]("bye")
    assert server.quit_message == "bye"


def test_model_and_service_unavailable_paths(manager, monkeypatch):
    messages = []
    monkeypatch.setattr(console_manager.logger, "msg", messages.append)
    manager.service_manager.get_service.return_value = None
    assert "not available" in manager._set_openai_model("x")
    assert "not available" in manager._get_openai_model()
    manager._console_weather("Helsinki")
    manager._console_electricity([])
    manager._send_electricity_price(None, None, "")
    assert "not available" in messages[-1]


def test_electricity_stats_longbar_and_daily(manager, monkeypatch):
    messages = []
    monkeypatch.setattr(console_manager.logger, "msg", messages.append)
    service = Mock()
    manager.service_manager.get_service.return_value = service
    service.parse_command_args.return_value = {
        "date": "today",
        "show_stats": True,
        "palette": 2,
    }
    service.format_statistics_message.return_value = "stats"
    manager._send_electricity_price(None, None, "stats")
    assert messages[-1] == "stats"

    service.parse_command_args.return_value = {
        "date": "today",
        "show_longbar": True,
        "palette": 1,
    }
    service.get_daily_prices.return_value = {"interval_prices": []}
    service._create_long_price_bar_graph.return_value = "bar"
    manager._send_electricity_price(None, None, "bar")
    assert messages[-1] == "bar"

    service.parse_command_args.return_value = {
        "date": "today",
        "show_all_hours": True,
        "is_tomorrow": False,
    }
    service.get_electricity_price.return_value = {"price": 1}
    service.format_daily_prices_message.return_value = "daily"
    manager._send_electricity_price(None, None, "all")
    assert messages[-1] == "daily"


def test_channel_and_ai_handler_paths(manager, monkeypatch):
    manager._console_join_or_part_channel = Mock(return_value="joined")
    manager._get_channel_status = Mock(return_value="status")
    manager._handle_channel_command("#chat")
    manager._handle_channel_command("#")
    manager._console_join_or_part_channel.assert_called_once_with("chat")
    manager._get_channel_status.assert_called_once()

    manager.service_manager.is_service_available.return_value = False
    manager._handle_ai_chat_command("-hello")
    manager._handle_ai_chat_command("-")
    manager._console_send_to_channel = Mock(return_value="sent")
    manager._handle_channel_message("hello")
    manager._console_send_to_channel.assert_called_once_with("hello")


def test_empty_disconnect_status_and_join_error_paths(manager):
    manager.server_manager.server_threads = {}
    assert manager._console_disconnect() == "No servers currently connected"
    manager.server_manager.servers = {}
    assert manager._console_status() == "No servers configured"

    server = Mock(connected=True)
    manager.server_manager.servers = {"srv": server}
    manager.server_manager.server_threads = {"srv": Mock(is_alive=lambda: True)}
    server.join_channel.side_effect = RuntimeError("join")
    assert manager._console_join_or_part_channel("chat") == "Error joining #chat: join"


def test_version_invalid_and_env_commented_key(manager, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "VERSION").write_text("invalid", encoding="utf-8")
    assert manager._get_current_version() == "2.2.0"
    (tmp_path / ".env").write_text("#A=old\n", encoding="utf-8")
    assert manager._update_env_file("A", "new")
    assert (tmp_path / ".env").read_text(encoding="utf-8") == "A=new\n"


def test_console_output_protection_and_listener_start(manager, monkeypatch):
    manager._input_active = True
    manager._setup_console_output_protection()
    assert manager._input_active is False
    thread = Mock()
    monkeypatch.setattr(console_manager.threading, "Thread", Mock(return_value=thread))
    manager.start_console_listener()
    thread.start.assert_called_once()
