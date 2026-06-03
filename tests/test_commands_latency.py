"""Behavioral coverage for the privacy-safe latency command."""

from types import SimpleNamespace
from unittest.mock import Mock

from cmd_modules.basic import latency_command
from command_registry import CommandContext


def _context(*args):
    return CommandContext(
        command="latency",
        args=list(args),
        raw_message="!latency",
        target="#chan",
    )


def test_latency_requires_connection_and_tracker():
    assert latency_command(_context(), {}) == "Not connected to any IRC server"
    server = SimpleNamespace(send_raw=Mock())
    assert (
        latency_command(_context(), {"server": server})
        == "Latency tracker is unavailable"
    )
    disconnected = SimpleNamespace(send_raw=Mock(), connected=False)
    assert (
        latency_command(_context(), {"server": disconnected})
        == "Not connected to any IRC server"
    )


def test_latency_resolves_console_server_name():
    server = SimpleNamespace(
        config=SimpleNamespace(name="srv"),
        connected=True,
        send_raw=Mock(),
    )
    server_manager = Mock()
    server_manager.get_server.return_value = server
    tracker = Mock()
    tracker._get_latency_nicks.return_value = []

    assert (
        latency_command(
            _context("network"),
            {
                "server": "srv",
                "server_manager": server_manager,
                "latency_tracker": tracker,
            },
        )
        == "Measuring IRC network latency on srv"
    )
    server_manager.get_server.assert_called_once_with("srv")
    tracker._send_network_latency_ping.assert_called_once_with(server)


def test_latency_network_and_nicks():
    server = SimpleNamespace(config=SimpleNamespace(name="srv"), send_raw=Mock())
    tracker = Mock()
    tracker._get_latency_nicks.return_value = ["Beiki", "Beici"]
    functions = {"server": server, "latency_tracker": tracker}

    assert latency_command(_context("network"), functions) == (
        "Measuring IRC network latency on srv"
    )
    tracker._send_network_latency_ping.assert_called_once_with(server)

    assert latency_command(_context("nicks"), functions) == (
        "Measuring latency for: Beiki, Beici"
    )
    assert tracker._send_ctcp_latency_ping.call_args_list[0].args == (
        server,
        "Beiki",
        "#chan",
    )


def test_latency_list_empty_list_and_usage():
    server = SimpleNamespace(config=SimpleNamespace(name="srv"), send_raw=Mock())
    tracker = Mock()
    functions = {"server": server, "latency_tracker": tracker}
    tracker._get_latency_nicks.return_value = []
    assert latency_command(_context("nicks"), functions) == (
        "No latency nicks configured in config.latency_nicks"
    )
    assert latency_command(_context(), functions) == (
        "No latency nicks configured in config.latency_nicks"
    )

    tracker._get_latency_nicks.return_value = ["Beiki", "Beici"]
    tracker._get_lag.side_effect = [12.4, None, 8.6]
    assert latency_command(_context("list"), functions) == (
        "IRC network: 9ms | Beiki: 12ms, Beici: n/a"
    )
    assert latency_command(_context("wat"), functions) == (
        "Usage: !latency [network|nicks|list]"
    )
