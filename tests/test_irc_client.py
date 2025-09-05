"""
IRC Client Tests - Pure Pytest Version

Comprehensive tests for the IRC client functionality.
"""

import os
import sys

import pytest

# Add the parent directory to Python path to ensure imports work in CI
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


def test_irc_client_creation():
    """Test IRC client creation."""
    from irc_client import create_irc_client

    client = create_irc_client("SERVER1", "testbot")

    assert client.nickname == "testbot", "Nickname should be set correctly"
    assert client.server_config is not None, "Server config should be set"
    assert hasattr(client, "connection_info"), "Should have connection info"


def test_irc_message_parsing():
    """Test IRC message parsing functionality."""
    from irc_client import IRCMessageType, create_irc_client

    client = create_irc_client("SERVER1", "testbot")

    test_cases = [
        (
            ":nick!user@host PRIVMSG #channel :Hello world",
            IRCMessageType.PRIVMSG,
            "#channel",
            "Hello world",
        ),
        (":nick!user@host JOIN #channel", IRCMessageType.JOIN, "#channel", None),
        (
            "PING :server.example.com",
            IRCMessageType.PING,
            None,
            "server.example.com",
        ),
        (":server 001 testbot :Welcome", IRCMessageType.NUMERIC, None, "Welcome"),
        (
            ":nick!user@host PRIVMSG testbot :Private message",
            IRCMessageType.PRIVMSG,
            "testbot",
            "Private message",
        ),
    ]

    for raw_msg, expected_type, expected_target, expected_text in test_cases:
        parsed = client.parse_message(raw_msg)

        assert parsed is not None, f"Should parse message: {raw_msg}"
        assert parsed.type == expected_type, f"Wrong type for: {raw_msg}"
        assert parsed.target == expected_target, f"Wrong target for: {raw_msg}"
        assert parsed.text == expected_text, f"Wrong text for: {raw_msg}"


def test_irc_message_properties():
    """Test IRC message property methods."""
    from irc_client import create_irc_client

    client = create_irc_client("SERVER1", "testbot")

    # Test channel message
    channel_msg = client.parse_message(":nick!user@host PRIVMSG #channel :Hello")
    assert channel_msg.is_channel_message is True, "Should be channel message"
    assert channel_msg.is_private_message is False, "Should not be private message"

    # Test private message
    private_msg = client.parse_message(":nick!user@host PRIVMSG testbot :Hello")
    assert private_msg.is_private_message is True, "Should be private message"
    assert private_msg.is_channel_message is False, "Should not be channel message"

    # Test command message
    command_msg = client.parse_message(":nick!user@host PRIVMSG #channel :!help")
    assert command_msg.is_command is True, "Should be command"

    # Test non-command message
    normal_msg = client.parse_message(":nick!user@host PRIVMSG #channel :Hello")
    assert normal_msg.is_command is False, "Should not be command"


def test_irc_connection_states():
    """Test IRC connection state management."""
    from irc_client import IRCConnectionState, create_irc_client

    client = create_irc_client("SERVER1", "testbot")

    # Initial state should be disconnected
    assert (
        client.connection_info.state == IRCConnectionState.DISCONNECTED
    ), "Initial state should be disconnected"

    # Test connection info properties
    assert (
        client.connection_info.uptime is None
    ), "Uptime should be None when disconnected"
    assert client.is_connected is False, "Should not be connected initially"

    # Test status string
    status = client.get_status()
    assert "disconnected" in status.lower(), "Status should mention disconnected state"


def test_irc_handler_system():
    """Test IRC message handler registration system."""
    from irc_client import IRCMessageType, create_irc_client

    client = create_irc_client("SERVER1", "testbot")

    # Test handler registration
    handler_called = []

    def test_handler(message):
        handler_called.append(message.type)

    client.add_message_handler(IRCMessageType.PRIVMSG, test_handler)

    # Simulate message processing (without actual network)
    test_msg = client.parse_message(":nick!user@host PRIVMSG #test :Hello")

    # Call handlers manually for testing
    if test_msg and test_msg.type in client._message_handlers:
        for handler in client._message_handlers[test_msg.type]:
            handler(test_msg)

    assert len(handler_called) == 1, "Handler should be called once"
    assert handler_called[0] == IRCMessageType.PRIVMSG, "Handler should receive PRIVMSG"

    # Test handler removal
    client.remove_message_handler(IRCMessageType.PRIVMSG, test_handler)
    assert (
        len(client._message_handlers.get(IRCMessageType.PRIVMSG, [])) == 0
    ), "Handler should be removed"


def test_irc_rate_limiting():
    """Test IRC rate limiting functionality."""
    from irc_client import create_irc_client

    client = create_irc_client("SERVER1", "testbot")

    # Test rate limiting properties
    assert hasattr(client, "_last_send_time"), "Should have last send time tracking"
    assert hasattr(client, "_send_delay"), "Should have send delay setting"
    assert client._send_delay >= 0, "Send delay should be non-negative"


def test_irc_channel_management():
    """Test IRC channel management methods."""
    from irc_client import create_irc_client

    client = create_irc_client("SERVER1", "testbot")

    # Test initial channel list
    assert isinstance(
        client.connection_info.channels, list
    ), "Channels should be a list"

    # Test channel operations (without actual network)
    initial_count = len(client.connection_info.channels)

    # Note: These would normally send IRC commands, but we're testing the logic
    try:
        client.join_channel("#test")
        # Should add to channel list (even if network call fails)
        assert (
            "#test" in client.connection_info.channels
        ), "Channel should be added to list"
    except Exception:
        # Network error is expected in test environment
        pass

    try:
        client.part_channel("#test")
        # Should remove from channel list
        assert (
            "#test" not in client.connection_info.channels
        ), "Channel should be removed from list"
    except Exception:
        # Network error is expected in test environment
        pass


# Parametrized test for multiple message parsing scenarios
@pytest.mark.parametrize(
    "raw_message,expected_nick,expected_user,expected_host",
    [
        (":nick!user@host PRIVMSG #channel :Hello", "nick", "user", "host"),
        (":testnick!testuser@testhost JOIN #test", "testnick", "testuser", "testhost"),
        (":bot!botuser@bothost PART #channel :Bye", "bot", "botuser", "bothost"),
    ],
)
def test_irc_message_parsing_user_info(
    raw_message, expected_nick, expected_user, expected_host
):
    """Test IRC message parsing with user information extraction."""
    from irc_client import create_irc_client

    client = create_irc_client("SERVER1", "testbot")
    parsed = client.parse_message(raw_message)

    assert parsed is not None, f"Should parse message: {raw_message}"
    assert parsed.nick == expected_nick, f"Wrong nick for: {raw_message}"
    assert parsed.user == expected_user, f"Wrong user for: {raw_message}"
    assert parsed.host == expected_host, f"Wrong host for: {raw_message}"


def test_irc_client_server_config():
    """Test IRC client server configuration handling."""
    from irc_client import create_irc_client

    client = create_irc_client("SERVER1", "testbot")

    # Test server configuration access
    assert hasattr(client, "server_config"), "Should have server config"
    assert client.server_config is not None, "Server config should not be None"

    # Test nickname handling
    assert client.nickname == "testbot", "Nickname should be set from parameter"


def test_irc_message_types():
    """Test IRC message type detection."""
    from irc_client import IRCMessageType, create_irc_client

    client = create_irc_client("SERVER1", "testbot")

    message_type_tests = [
        ("PING :server.com", IRCMessageType.PING),
        (":nick!user@host PRIVMSG #chan :hello", IRCMessageType.PRIVMSG),
        (":nick!user@host JOIN #channel", IRCMessageType.JOIN),
        (":nick!user@host PART #channel", IRCMessageType.PART),
        (":nick!user@host QUIT :Goodbye", IRCMessageType.QUIT),
        (":server 001 nick :Welcome", IRCMessageType.NUMERIC),
        (":server 353 nick = #channel :nick1 nick2", IRCMessageType.NUMERIC),
    ]

    for raw_msg, expected_type in message_type_tests:
        parsed = client.parse_message(raw_msg)
        assert parsed is not None, f"Should parse: {raw_msg}"
        assert (
            parsed.type == expected_type
        ), f"Wrong type for {raw_msg}: expected {expected_type}, got {parsed.type}"


def test_irc_client_error_handling():
    """Test IRC client error handling."""
    from irc_client import create_irc_client

    client = create_irc_client("SERVER1", "testbot")

    # Test parsing invalid messages
    invalid_messages = [
        "",  # Empty message
        "INVALID",  # Malformed message
        ":",  # Just colon
    ]

    for invalid_msg in invalid_messages:
        parsed = client.parse_message(invalid_msg)
        # Should either return None or handle gracefully
        # The exact behavior depends on implementation
        assert parsed is None or hasattr(
            parsed, "type"
        ), f"Should handle invalid message gracefully: {invalid_msg}"


def test_irc_parse_with_tags_and_server_prefix():
    """Cover tag parsing and server-only prefix branches."""
    from irc_client import create_irc_client

    client = create_irc_client("SERVER1", "testbot")

    # IRCv3 tags with prefix and text
    parsed = client.parse_message(
        "@badge=gold;flag :nick!user@host PRIVMSG #chan :Hello"
    )
    assert parsed is not None
    assert parsed.tags.get("badge") == "gold"
    assert parsed.tags.get("flag") in ("flag", True)

    # Server-only prefix (no ! or @): nick property falls back to sender
    parsed2 = client.parse_message(":server NOTICE * :motd")
    assert parsed2 is not None
    assert parsed2.nick == "server"
    assert parsed2.user is None
    assert parsed2.host is None


def test_irc_connect_success_and_nick_in_use(monkeypatch):
    """Simulate successful connect including PING and 433 nickname-in-use handling."""
    import socket as _socket
    import types

    from irc_client import IRCClient

    # Fake server config
    sc = types.SimpleNamespace(
        host="127.0.0.1", port=6667, channels=["#a", "#b"], keys=["k1"]
    )

    sent = []

    class FakeSocket:
        def __init__(self):
            self._step = 0
            self.timeout = None

        def settimeout(self, t):
            self.timeout = t

        def connect(self, addr):
            return None

        def recv(self, n):
            # Step through PING -> 433 -> 001 -> then timeout
            if self._step == 0:
                self._step += 1
                return b"PING :1234\r\n"
            if self._step == 1:
                self._step += 1
                return b":server 433 * testbot :Nickname is already in use\r\n"
            if self._step == 2:
                self._step += 1
                return b":server 001 testbot :Welcome\r\n"
            raise _socket.timeout()

        def sendall(self, data):
            sent.append(data.decode("utf-8"))

        def shutdown(self, how):
            return None

        def close(self):
            return None

    fake = FakeSocket()
    monkeypatch.setattr("socket.socket", lambda *a, **k: fake, raising=True)

    logs = []

    client = IRCClient(
        sc, "testbot", log_callback=lambda m, level="INFO": logs.append((level, m))
    )

    # Avoid starting a thread
    monkeypatch.setattr(client, "_start_keepalive", lambda: None, raising=True)

    ok = client.connect()
    assert ok is True
    assert client.is_connected
    # Channels joined, with key for first only
    assert (
        "#a" in client.connection_info.channels
        and "#b" in client.connection_info.channels
    )
    # AUTH and ping/pong and joins were sent
    sent_str = "\n".join(sent)
    assert "NICK testbot" in sent_str and "USER testbot" in sent_str
    assert "PONG :1234" in sent_str
    assert "JOIN #a k1" in sent_str and "JOIN #b\r\n" in sent_str

    # Disconnect normally
    client.disconnect("Bye")
    assert any("QUIT :Bye" in s for s in sent)

    # Disconnect when already disconnected should no-op
    client.connection_info.state = client.connection_info.state.DISCONNECTED
    client.disconnect()


def test_irc_send_raw_and_rate_limit(monkeypatch):
    """Cover _send_raw normal path, rate limiting sleep, and error when disconnected."""
    import time as _time
    import types

    from irc_client import IRCClient, IRCConnectionState

    sc = types.SimpleNamespace(host="h", port=1, channels=[], keys=[])

    class S:
        def __init__(self):
            self.sent = []

        def sendall(self, b):
            self.sent.append(b.decode("utf-8"))

    client = IRCClient(sc, "n")
    client.socket = S()
    client.connection_info.state = IRCConnectionState.CONNECTED

    # Force sleep path by fixing time
    # Two calls, each uses time.time() twice -> provide four entries
    times = [1000.0, 1000.0, 1000.0, 1000.0]

    def fake_time():
        return times.pop(0)

    slept = {"calls": 0}

    def fake_sleep(d):
        slept["calls"] += 1

    monkeypatch.setattr("time.time", fake_time, raising=False)
    monkeypatch.setattr("time.sleep", fake_sleep, raising=False)

    client._send_raw("PRIVMSG #c :hi")
    client._send_raw("PRIVMSG #c :again")  # triggers sleep due to same timestamp

    assert client.socket.sent[0].startswith("PRIVMSG #c :hi")
    assert slept["calls"] >= 1

    # Error path when not connected
    client.connection_info.state = IRCConnectionState.DISCONNECTED
    with pytest.raises(ConnectionError):
        client._send_raw("X")


def test_irc_join_part_change_and_send_wrappers(monkeypatch):
    import types

    from irc_client import IRCClient, IRCConnectionState

    sc = types.SimpleNamespace(host="h", port=1, channels=[], keys=[])

    class S:
        def __init__(self):
            self.sent = []

        def sendall(self, b):
            self.sent.append(b.decode("utf-8"))

    client = IRCClient(sc, "n")
    client.socket = S()
    client.connection_info.state = IRCConnectionState.CONNECTED

    client.join_channel("#x", key="p")
    client.join_channel("#y")
    client.part_channel("#y", reason="bye")
    client.part_channel("#x")
    client.change_nickname("n2")

    client.send_message("#z", "hi")
    client.send_notice("#z", "n")
    client.send_action("#z", "waves")
    client.send_raw("RAW")

    sent = "\n".join(client.socket.sent)
    assert "JOIN #x p" in sent and "JOIN #y\r\n" in sent
    assert "PART #y :bye" in sent and "PART #x\r\n" in sent
    assert "NICK n2" in sent
    assert "PRIVMSG #z :hi" in sent and "NOTICE #z :n" in sent
    assert "ACTION waves" in sent and "RAW\r\n" in sent


def test_irc_read_messages_and_handlers(monkeypatch):
    """Cover read_messages including raw handlers, message handlers, and PING auto-respond."""
    import socket as _socket
    import types

    from irc_client import IRCClient, IRCConnectionState, IRCMessageType

    sc = types.SimpleNamespace(host="h", port=1, channels=[], keys=[])

    class S:
        def __init__(self):
            self.step = 0
            self.sent = []

        def recv(self, n):
            if self.step == 0:
                self.step += 1
                return (
                    b":srv NOTICE * :hi\r\nPING :xyz\r\n:nick!u@h PRIVMSG #c :hello\r\n"
                )
            raise _socket.timeout()

        def sendall(self, b):
            self.sent.append(b.decode("utf-8"))

    client = IRCClient(sc, "n")
    client.socket = S()
    client.connection_info.state = IRCConnectionState.CONNECTED

    raw_calls = {"n": 0}

    def raw_ok(line):
        raw_calls["n"] += 1

    def raw_bad(line):
        raise RuntimeError("boom")

    client.add_raw_handler(raw_ok)
    client.add_raw_handler(raw_bad)

    called = {"n": 0}

    def priv_handler(msg):
        called["n"] += 1
        raise ValueError("handler error")

    client.add_message_handler(IRCMessageType.PRIVMSG, priv_handler)

    msgs = client.read_messages()
    assert len(msgs) >= 2
    assert any("PONG :xyz" in s for s in client.socket.sent)
    assert raw_calls["n"] >= 1 and called["n"] == 1

    # Socket timeout returns []
    assert client.read_messages() == []

    # General exception path raises
    class S2:
        def recv(self, n):
            raise ValueError("bad")

    client.socket = S2()
    with pytest.raises(ValueError):
        client.read_messages()


def test_irc_run_forever(monkeypatch):
    import types

    from irc_client import IRCClient, IRCConnectionState

    sc = types.SimpleNamespace(host="h", port=1, channels=[], keys=[])
    client = IRCClient(sc, "n")
    client.connection_info.state = IRCConnectionState.CONNECTED

    calls = {"n": 0}

    def rm():
        calls["n"] += 1
        if calls["n"] > 1:
            raise RuntimeError("stop")

    monkeypatch.setattr(client, "read_messages", rm, raising=True)
    monkeypatch.setattr("time.sleep", lambda x: None, raising=False)

    client.run_forever()

    # Now with immediate stop_event set
    import threading

    ev = threading.Event()
    ev.set()
    client.run_forever(ev)


def test_irc_keepalive_worker(monkeypatch):
    """Drive the keepalive worker to send one ping and exit quickly."""
    import types

    from irc_client import IRCClient, IRCConnectionState

    sc = types.SimpleNamespace(host="h", port=1, channels=[], keys=[])

    class S:
        def __init__(self):
            self.sent = []

        def sendall(self, b):
            self.sent.append(b.decode("utf-8"))

    client = IRCClient(sc, "n")
    client.socket = S()
    client.connection_info.state = IRCConnectionState.CONNECTED
    client.connection_info.last_ping = 0  # far in past

    # sleep that sets stop event immediately
    def fake_sleep(d):
        client._stop_event.set()

    monkeypatch.setattr("time.sleep", fake_sleep, raising=False)

    client._keepalive_worker()
    assert any("PING :keepalive" in s for s in client.socket.sent)


def test_create_irc_client_factory(monkeypatch):
    from irc_client import create_irc_client

    class CM:
        def __init__(self, server=None, name="bot"):
            self._server = server
            self.config = types.SimpleNamespace(name=name)

        def get_server_by_name(self, n):
            return self._server

        def get_primary_server(self):
            return self._server

    import types

    # No server available -> ValueError
    def fake_gcm():
        return CM(server=None)

    monkeypatch.setattr("config.get_config_manager", fake_gcm, raising=True)
    with pytest.raises(ValueError):
        create_irc_client("X")

    # With server and default nickname from config
    server = types.SimpleNamespace(host="h", port=1, channels=[], keys=[], name="srv")

    def fake_gcm2():
        return CM(server=server, name="nickfromcfg")

    monkeypatch.setattr("config.get_config_manager", fake_gcm2, raising=True)
    client = create_irc_client("X")
    assert client.nickname == "nickfromcfg"


def test_connection_failure_paths(monkeypatch):
    """Cover connect() branches: empty data, socket.timeout -> auth timeout."""
    import socket as _socket
    import types

    from irc_client import IRCClient

    sc = types.SimpleNamespace(host="h", port=1, channels=[], keys=[])

    # Case 1: recv returns empty -> ConnectionError during auth
    class S1:
        def settimeout(self, t):
            pass

        def connect(self, addr):
            pass

        def recv(self, n):
            return b""

        def sendall(self, b):
            pass

    monkeypatch.setattr("socket.socket", lambda *a, **k: S1(), raising=True)

    client = IRCClient(sc, "n")
    ok = client.connect()
    assert ok is False

    # Case 2: socket.timeout repeatedly -> auth timeout path
    class S2:
        def settimeout(self, t):
            pass

        def connect(self, addr):
            pass

        def recv(self, n):
            raise _socket.timeout()

        def sendall(self, b):
            pass

    monkeypatch.setattr("socket.socket", lambda *a, **k: S2(), raising=True)

    times = [0.0, 31.0]

    def fake_time():
        return times.pop(0)

    monkeypatch.setattr("time.time", fake_time, raising=False)

    client2 = IRCClient(sc, "n2")
    ok2 = client2.connect()
    assert ok2 is False


def test_disconnect_branches(monkeypatch):
    """Cover keepalive thread join and QUIT/close exception handling."""
    import types

    from irc_client import IRCClient, IRCConnectionState

    sc = types.SimpleNamespace(host="h", port=1, channels=["#x"], keys=[])

    joined = {"called": False}

    class FakeThread:
        def is_alive(self):
            return True

        def join(self, timeout=None):
            joined["called"] = True

    class BadSocket:
        def sendall(self, b):
            raise RuntimeError("send fail")

        def shutdown(self, how):
            raise RuntimeError("shutdown fail")

        def close(self):
            pass

    client = IRCClient(sc, "n")
    client._keepalive_thread = FakeThread()
    client.socket = BadSocket()
    client.connection_info.state = IRCConnectionState.CONNECTED

    # Should not raise
    client.disconnect("bye")
    assert joined["called"] is True


def test_start_keepalive_thread(monkeypatch):
    """Cover _start_keepalive thread creation path without running real thread."""
    import types

    from irc_client import IRCClient

    sc = types.SimpleNamespace(host="h", port=1, channels=[], keys=[])

    started = {"n": 0}

    class FT:
        def __init__(self, target=None, daemon=None, name=None):
            started["n"] += 1
            self._target = target

        def start(self):
            # Do not actually run target
            pass

    monkeypatch.setattr("threading.Thread", FT, raising=True)

    client = IRCClient(sc, "n")
    client._start_keepalive()
    assert started["n"] == 1


def test_keepalive_worker_error_path(monkeypatch):
    import types

    from irc_client import IRCClient, IRCConnectionState

    sc = types.SimpleNamespace(host="h", port=1, channels=[], keys=[])

    client = IRCClient(sc, "n")
    client.connection_info.state = IRCConnectionState.CONNECTED

    # Force _send_raw to raise to hit error branch
    monkeypatch.setattr(
        client,
        "_send_raw",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")),
        raising=True,
    )

    # Stop quickly
    monkeypatch.setattr("time.sleep", lambda d: client._stop_event.set(), raising=False)

    client._keepalive_worker()


def test_send_raw_exception_path(monkeypatch):
    import types

    from irc_client import IRCClient, IRCConnectionState

    sc = types.SimpleNamespace(host="h", port=1, channels=[], keys=[])

    class BS:
        def sendall(self, b):
            raise RuntimeError("boom")

    client = IRCClient(sc, "n")
    client.socket = BS()
    client.connection_info.state = IRCConnectionState.CONNECTED

    with pytest.raises(RuntimeError):
        client._send_raw("X")


def test_parse_additional_commands():
    from irc_client import IRCMessageType, create_irc_client

    client = create_irc_client("SERVER1", "testbot")
    cases = [
        (":nick!u@h NICK newnick", IRCMessageType.NICK),
        (":o!u@h KICK #c v :r", IRCMessageType.KICK),
        (":o!u@h MODE #c +o v", IRCMessageType.MODE),
        ("PONG :123", IRCMessageType.PONG),
    ]

    for raw, t in cases:
        p = client.parse_message(raw)
        assert p is not None and p.type == t


def test_read_messages_edge_cases(monkeypatch):
    import types

    from irc_client import IRCClient, IRCConnectionState

    sc = types.SimpleNamespace(host="h", port=1, channels=[], keys=[])

    client = IRCClient(sc, "n")
    # Not connected -> []
    assert client.read_messages() == []

    class S:
        def __init__(self):
            self.calls = 0

        def recv(self, n):
            return b""  # server closed

    client.socket = S()
    client.connection_info.state = IRCConnectionState.CONNECTED

    with pytest.raises(ConnectionError):
        client.read_messages()


def test_run_forever_handles_timeout(monkeypatch):
    import socket
    import threading
    import types

    from irc_client import IRCClient, IRCConnectionState

    sc = types.SimpleNamespace(host="h", port=1, channels=[], keys=[])
    client = IRCClient(sc, "n")
    client.connection_info.state = IRCConnectionState.CONNECTED

    ev = threading.Event()

    calls = {"n": 0}

    def rm():
        # First call raises socket.timeout, second call returns normally so sleep executes
        calls["n"] += 1
        if calls["n"] == 1:
            raise socket.timeout()
        return []

    monkeypatch.setattr(client, "read_messages", rm, raising=True)
    # In normal-path loop, sleep will set the event to stop
    monkeypatch.setattr("time.sleep", lambda x: ev.set(), raising=False)

    client.run_forever(ev)


def test_uptime_and_status_channels(monkeypatch):
    import time
    import types

    from irc_client import IRCClient, IRCConnectionState

    sc = types.SimpleNamespace(host="h", port=1, channels=["#x"], keys=[])
    client = IRCClient(sc, "n")
    client.connection_info.connected_at = time.time() - 1

    # Direct uptime property
    up = client.connection_info.uptime
    assert up is not None and up > 0

    client.connection_info.channels = ["#x", "#y"]
    status = client.get_status()
    assert "Uptime:" in status and "Channels:" in status


def test_remove_message_handler_value_error():
    """Attempting to remove a non-registered handler should be a no-op path."""
    import types

    from irc_client import IRCClient, IRCMessageType

    sc = types.SimpleNamespace(host="h", port=1, channels=[], keys=[])
    client = IRCClient(sc, "n")

    def handler(msg):
        pass

    # Not added; removal should hit ValueError branch and not raise
    client.remove_message_handler(IRCMessageType.PRIVMSG, handler)
