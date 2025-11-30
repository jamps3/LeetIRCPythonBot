#!/usr/bin/env python3
"""
Pytest tests for IRC server connectivity.
"""

import socket
import ssl
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import server as server_mod
from config import ServerConfig
from server import Server


@pytest.fixture
def server_config():
    return ServerConfig(
        name="TestServer",
        host="irc.example.com",
        port=6667,
        channels=["#c1", "#c2"],
        keys=["k1", ""],
        tls=False,
        allow_insecure_tls=False,
    )


@pytest.fixture
def srv(monkeypatch, server_config):
    # Use a dummy logger for deterministic behavior
    dummy_logger = Mock()
    monkeypatch.setattr("logger.get_logger", lambda name: dummy_logger, raising=True)
    stop = threading.Event()
    s = Server(server_config, "Bot", stop)
    return s


# --- register_callback and simple delegators ---


def test_register_callback_valid_and_invalid(srv):
    called = []
    srv.register_callback("message", lambda *a, **k: called.append("m"))
    assert len(srv.callbacks["message"]) == 1
    # Invalid event logs warning path
    srv.register_callback("nope", lambda: None)


def test_connect_and_run_calls_start(monkeypatch, srv):
    flag = {"started": False}
    monkeypatch.setattr(
        srv, "start", lambda: flag.__setitem__("started", True), raising=True
    )
    srv.connect_and_run()
    assert flag["started"] is True


# --- connect() variants ---


def test_connect_non_tls_success(monkeypatch, srv):
    # Fake raw socket
    class RawSock:
        def __init__(self, *a, **k):
            self.timeouts = []
            self.connected_to = None

        def settimeout(self, t):
            self.timeouts.append(t)

        def connect(self, addr):
            self.connected_to = addr

        def close(self):
            pass

    monkeypatch.setattr(server_mod.socket, "socket", lambda *a, **k: RawSock())
    srv.config.tls = False
    ok = srv.connect()
    assert ok is True
    assert srv.connected is True
    # Should not be SSL socket
    assert srv.is_tls() is False


def test_connect_tls_success_insecure_ctx(monkeypatch, srv):
    # Prepare raw
    class RawSock:
        def __init__(self, *a, **k):
            pass

        def settimeout(self, t):
            pass

        def connect(self, addr):
            pass

    # Fake SSL socket type within server module
    class MySSLSock:
        def __init__(self, *a, **k):
            pass

        def connect(self, addr):
            pass

        def getpeercert(self):
            return {"subject": ((("commonName", "example.com"),),)}

        def version(self):
            return "TLSv1.3"

        def settimeout(self, t):
            pass

    monkeypatch.setattr(server_mod.socket, "socket", lambda *a, **k: RawSock())
    monkeypatch.setattr(server_mod.ssl, "SSLSocket", MySSLSock)

    # Fake SSL context with desired attributes and methods
    class Ctx:
        def __init__(self):
            self.check_hostname = True
            self.verify_mode = ssl.CERT_REQUIRED
            self.minimum_version = ssl.TLSVersion.TLSv1_2
            self.options = 0

        def set_ciphers(self, s):
            pass

        def wrap_socket(self, raw_socket, server_hostname=None):
            return MySSLSock()

    monkeypatch.setattr(server_mod.ssl, "create_default_context", lambda: Ctx())

    srv.config.tls = True
    srv.config.allow_insecure_tls = True
    ok = srv.connect()
    assert ok is True
    assert srv.is_tls() is True


def test_connect_tls_secure_ctx(monkeypatch, srv):
    # Like previous TLS test but with allow_insecure_tls=False to hit secure branch
    class RawSock:
        def __init__(self, *a, **k):
            pass

        def settimeout(self, t):
            pass

        def connect(self, addr):
            pass

    class MySSLSock:
        def __init__(self, *a, **k):
            pass

        def connect(self, addr):
            pass

        def getpeercert(self):
            return {"subject": ((("commonName", "example.com"),),)}

        def version(self):
            return "TLSv1.3"

        def settimeout(self, t):
            pass

    class Ctx:
        def __init__(self):
            self.check_hostname = True
            self.verify_mode = ssl.CERT_REQUIRED
            self.minimum_version = ssl.TLSVersion.TLSv1_2
            self.options = 0

        def set_ciphers(self, s):
            pass

        def wrap_socket(self, raw_socket, server_hostname=None):
            return MySSLSock()

    monkeypatch.setattr(server_mod.socket, "socket", lambda *a, **k: RawSock())
    monkeypatch.setattr(server_mod.ssl, "SSLSocket", MySSLSock)
    monkeypatch.setattr(server_mod.ssl, "create_default_context", lambda: Ctx())
    srv.config.tls = True
    srv.config.allow_insecure_tls = False
    assert srv.connect() is True


def test_connect_tls_context_creation_failure(monkeypatch, srv):
    class RawSock:
        def __init__(self, *a, **k):
            pass

        def settimeout(self, t):
            pass

    monkeypatch.setattr(server_mod.socket, "socket", lambda *a, **k: RawSock())
    monkeypatch.setattr(
        server_mod.ssl,
        "create_default_context",
        lambda: (_ for _ in ()).throw(Exception("ctx fail")),
    )
    srv.config.tls = True
    assert srv.connect() is False


def test_connect_socket_error(monkeypatch, srv):
    class RawSock:
        def __init__(self, *a, **k):
            pass

        def settimeout(self, t):
            pass

        def connect(self, addr):
            raise socket.error("boom")

    monkeypatch.setattr(server_mod.socket, "socket", lambda *a, **k: RawSock())
    srv.config.tls = False
    assert srv.connect() is False


def test_connect_ssl_cert_verification_error(monkeypatch, srv):
    class RawSock:
        def __init__(self, *a, **k):
            pass

        def settimeout(self, t):
            pass

    class BadSSLSock:
        def __init__(self, *a, **k):
            pass

        def connect(self, addr):
            raise ssl.SSLCertVerificationError("cert bad")

    class Ctx:
        def __init__(self):
            self.check_hostname = True
            self.verify_mode = ssl.CERT_REQUIRED
            self.minimum_version = ssl.TLSVersion.TLSv1_2
            self.options = 0

        def set_ciphers(self, s):
            pass

        def wrap_socket(self, raw_socket, server_hostname=None):
            return BadSSLSock()

    monkeypatch.setattr(server_mod.socket, "socket", lambda *a, **k: RawSock())
    monkeypatch.setattr(server_mod.ssl, "SSLSocket", BadSSLSock)
    monkeypatch.setattr(server_mod.ssl, "create_default_context", lambda: Ctx())
    srv.config.tls = True
    assert srv.connect() is False


def test_connect_ssl_error(monkeypatch, srv):
    class RawSock:
        def __init__(self, *a, **k):
            pass

        def settimeout(self, t):
            pass

    class BadSSLSock:
        def __init__(self, *a, **k):
            pass

        def connect(self, addr):
            raise ssl.SSLError("tls err")

    class Ctx:
        def __init__(self):
            self.check_hostname = True
            self.verify_mode = ssl.CERT_REQUIRED
            self.minimum_version = ssl.TLSVersion.TLSv1_2
            self.options = 0

        def set_ciphers(self, s):
            pass

        def wrap_socket(self, raw_socket, server_hostname=None):
            return BadSSLSock()

    monkeypatch.setattr(server_mod.socket, "socket", lambda *a, **k: RawSock())
    monkeypatch.setattr(server_mod.ssl, "SSLSocket", BadSSLSock)
    monkeypatch.setattr(server_mod.ssl, "create_default_context", lambda: Ctx())
    srv.config.tls = True
    assert srv.connect() is False


def test_connect_unexpected_exception(monkeypatch, srv):
    class RawSock:
        def __init__(self, *a, **k):
            pass

        def settimeout(self, t):
            raise RuntimeError("settimeout fail")

    monkeypatch.setattr(server_mod.socket, "socket", lambda *a, **k: RawSock())
    srv.config.tls = False
    assert srv.connect() is False


# --- login() variants ---


def test_login_success_with_wait_and_welcome(monkeypatch, srv):
    sent = []
    monkeypatch.setattr(srv, "send_raw", lambda m: sent.append(m), raising=True)

    # Fake recv sequence: first a processing notice with 020, then welcome 001
    msgs = [
        b":server.example 020 * :Please wait while we process your connection\r\n",
        b":server.example 001 Bot :welcome\r\n",
    ]

    class Sock:
        def recv(self, n):
            return msgs.pop(0) if msgs else b""

        def settimeout(self, t):
            pass

    srv.socket = Sock()
    srv.connected = True

    assert srv.login() is True
    # Ensure NICK/USER were attempted
    assert any(m.startswith("NICK ") for m in sent)
    assert any(m.startswith("USER ") for m in sent)


def test_login_stop_event_set_returns_false(srv):
    srv.stop_event.set()
    assert srv.login() is False


def test_login_outer_exception_from_send_raw(monkeypatch, srv):
    def boom(m):
        raise BrokenPipeError("x")

    monkeypatch.setattr(srv, "send_raw", boom, raising=True)
    # Minimal socket to satisfy attribute access
    srv.socket = SimpleNamespace(recv=lambda n: b"", settimeout=lambda t: None)
    srv.connected = True
    assert srv.login() is False


def test_login_timeout_then_exit(monkeypatch, srv):
    # Ensure loop hits the timeout path then exits on subsequent error
    # Freeze time to simulate 31 seconds elapsed
    base = [0]

    def fake_time():
        # First call inside login uses last_response_time set; later difference >30
        base[0] += 31
        return base[0]

    monkeypatch.setattr(server_mod.time, "time", fake_time)

    class Sock:
        def settimeout(self, t):
            pass

        def recv(self, n):
            # Return empty to avoid updating last_response_time
            return b""

    srv.socket = Sock()
    srv.connected = True
    assert srv.login() is False


def test_login_generic_exception(monkeypatch, srv):
    class Sock:
        def settimeout(self, t):
            pass

        def recv(self, n):
            raise Exception("boom")

    srv.socket = Sock()
    srv.connected = True
    assert srv.login() is False


def test_login_timeout_branch_precise(monkeypatch, srv):
    # Force precise time progression: 0 at last_response_time, then 1000 to trigger timeout
    calls = {"n": 0}

    def seq_time():
        calls["n"] += 1
        return 0 if calls["n"] == 1 else 1000

    monkeypatch.setattr(server_mod.time, "time", seq_time)
    # Send raw does nothing
    monkeypatch.setattr(srv, "send_raw", lambda m: None, raising=True)

    class Sock:
        def __init__(self):
            self.calls = 0

        def settimeout(self, t):
            pass

        def recv(self, n):
            self.calls += 1
            if self.calls == 1:
                return b""  # triggers timeout check
            raise BrokenPipeError("stop")

    srv.socket = Sock()
    srv.connected = True
    assert srv.login() is False


# --- channel joins ---


def test_join_channels_with_and_without_keys(monkeypatch, srv):
    calls = []
    monkeypatch.setattr(srv, "send_raw", lambda m: calls.append(m), raising=True)
    srv.join_channels()
    assert "JOIN #c1 k1" in calls[0]
    assert "JOIN #c2" in calls[1]


# --- send_raw variants and delegators ---


def test_send_raw_not_connected_returns(srv):
    srv.connected = False
    srv.socket = None
    srv.send_raw("PRIVMSG #x :hi")


def test_send_raw_rate_limited_drop(monkeypatch, srv):
    srv.connected = True
    srv.socket = SimpleNamespace(
        sendall=lambda b: (_ for _ in ()).throw(AssertionError("should not send"))
    )
    monkeypatch.setattr(
        srv, "_wait_for_rate_limit", lambda timeout: False, raising=True
    )
    srv.send_raw("PRIVMSG #x :hello")


def test_send_raw_exception_sets_disconnected(srv):
    srv.connected = True

    def sendall(_):
        raise BrokenPipeError("nope")

    srv.socket = SimpleNamespace(sendall=sendall)
    srv.send_raw("PING :x", bypass_rate_limit=True)
    assert srv.connected is False


def test_send_message_and_notice_delegate(monkeypatch, srv):
    calls = []
    monkeypatch.setattr(srv, "send_raw", lambda m: calls.append(m), raising=True)
    srv.send_message("#a", "hi")
    srv.send_notice("#a", "hi")
    assert any(m.startswith("PRIVMSG ") for m in calls)
    assert any(m.startswith("NOTICE ") for m in calls)


# --- keepalive ping ---


def test_keepalive_ping_sends_when_due(monkeypatch, srv):
    monkeypatch.setattr(server_mod.time, "sleep", lambda s: None)
    srv.connected = True
    srv.last_ping = 0  # long ago

    def send_raw(m):
        # On first ping, drop connection to exit loop
        srv.connected = False

    srv.send_raw = send_raw
    srv._keepalive_ping()


def test_keepalive_ping_exception_sets_disconnected(monkeypatch, srv):
    monkeypatch.setattr(server_mod.time, "sleep", lambda s: None)
    srv.connected = True
    srv.last_ping = 0

    def send_raw(_):
        raise RuntimeError("boom")

    srv.send_raw = send_raw
    srv._keepalive_ping()
    assert srv.connected is False


def test_keepalive_returns_when_stop_set_during_sleep(monkeypatch, srv):
    # First loop sees not set, sleep sets it, next iteration returns at line 385
    def sleeper(_):
        srv.stop_event.set()

    monkeypatch.setattr(server_mod.time, "sleep", sleeper)
    srv.connected = True
    srv.stop_event.clear()
    srv._keepalive_ping()


# --- read messages ---


def test_read_messages_ping_and_close(monkeypatch, srv):
    monkeypatch.setattr(server_mod.time, "sleep", lambda s: None)
    pongs = []
    srv.send_raw = lambda m, **k: pongs.append(m)
    messages = [b"PING :abc\r\n", b""]

    class Sock:
        def settimeout(self, t):
            pass

        def recv(self, n):
            return messages.pop(0)

    srv.socket = Sock()
    srv.connected = True
    srv.stop_event.clear()
    # Spy on _process_message
    seen = []
    monkeypatch.setattr(
        srv, "_process_message", lambda line: seen.append(line), raising=True
    )
    srv._read_messages()
    assert any(m.startswith("PONG :abc") for m in pongs)


def test_read_messages_timeout_and_errors(monkeypatch, srv):
    # Timeout then empty -> close path
    class Sock1:
        def __init__(self):
            self.calls = 0

        def settimeout(self, t):
            pass

        def recv(self, n):
            self.calls += 1
            if self.calls == 1:
                raise socket.timeout
            return b""

    srv.socket = Sock1()
    srv.connected = True
    srv._read_messages()

    # Connection error path
    class Sock2:
        def settimeout(self, t):
            pass

        def recv(self, n):
            raise ConnectionResetError("x")

    srv.socket = Sock2()
    srv.connected = True
    srv._read_messages()

    # Unexpected error via _process_message raising
    class Sock3:
        def settimeout(self, t):
            pass

        def recv(self, n):
            return b"PRIVMSG #c :hi\r\n"

    srv.socket = Sock3()
    srv.connected = True
    monkeypatch.setattr(
        srv,
        "_process_message",
        lambda m: (_ for _ in ()).throw(RuntimeError("boom")),
        raising=True,
    )
    srv._read_messages()


# --- process_message ---


def test_process_message_callbacks_and_errors(srv):
    seen = {"m": 0, "j": 0, "p": 0, "q": 0}

    def cbm(_s, sender, hostmask, target, text):
        seen["m"] += 1
        raise RuntimeError("cb err")

    def cbj(_s, sender, hostmask, channel):
        seen["j"] += 1
        raise RuntimeError("cb err")

    def cbp(_s, sender, hostmask, channel):
        seen["p"] += 1
        raise RuntimeError("cb err")

    def cbq(_s, sender, hostmask):
        seen["q"] += 1
        raise RuntimeError("cb err")

    srv.register_callback("message", cbm)
    srv.register_callback("join", cbj)
    srv.register_callback("part", cbp)
    srv.register_callback("quit", cbq)

    import time

    srv._process_message(":nick!u PRIVMSG #c :hello")
    srv._process_message(":nick!u JOIN #c")
    srv._process_message(":nick!u PART #c")
    srv._process_message(":nick!u QUIT :bye")

    # Give async callbacks time to execute (if any were async)
    # But since these are sync callbacks, they execute immediately
    # Just give a tiny delay to be safe
    time.sleep(0.05)

    # Debug: print what was seen
    if not all(v == 1 for v in seen.values()):
        print(f"DEBUG: seen values: {seen}")

    assert all(v == 1 for v in seen.values())


# --- start() variants ---


def test_start_exits_when_stop_set_initially(srv):
    srv.stop_event.set()
    srv.start()


def test_start_top_of_loop_detects_stop(monkeypatch, srv):
    # Manipulate is_set to return False at while condition, then True at inner check
    seq = {"n": 0}

    def is_set_seq():
        seq["n"] += 1
        return seq["n"] >= 2

    monkeypatch.setattr(srv.stop_event, "is_set", is_set_seq, raising=True)
    srv.start()


def test_start_after_connection_then_stop_triggers_quit(monkeypatch, srv):
    monkeypatch.setattr(server_mod.time, "sleep", lambda s: None)
    calls = {"quit": 0}
    monkeypatch.setattr(srv, "connect", lambda: True, raising=True)

    def fake_login():
        # Set stop during login to trigger the immediate-stop branch
        srv.stop_event.set()
        return True

    monkeypatch.setattr(srv, "login", fake_login, raising=True)
    monkeypatch.setattr(
        srv,
        "quit",
        lambda msg: calls.__setitem__("quit", calls["quit"] + 1),
        raising=True,
    )
    srv.start()
    assert calls["quit"] == 1


def test_start_connect_failure_then_not_reconnect_when_stop_set(monkeypatch, srv):
    monkeypatch.setattr(server_mod.time, "sleep", lambda s: None)

    def connect_and_stop():
        srv.stop_event.set()
        return False

    monkeypatch.setattr(srv, "connect", connect_and_stop, raising=True)
    srv.start()


def test_start_reconnect_wait_loop_runs_then_stop(monkeypatch, srv):
    # Speed up
    monkeypatch.setattr(server_mod.time, "sleep", lambda s: None)
    # Keep track of calls and set stop after first retry message
    calls = {"n": 0}

    def fake_connect():
        calls["n"] += 1
        # Do not set stop on first call so it goes through reconnect wait
        if calls["n"] == 1:
            return False
        # After first iteration, request stop
        srv.stop_event.set()
        return False

    monkeypatch.setattr(srv, "connect", fake_connect, raising=True)
    srv.start()


def test_start_threads_then_quit_on_stop(monkeypatch, srv):
    # Cover thread creation paths and quit when stop is set during while loop
    monkeypatch.setattr(server_mod.time, "sleep", lambda s: srv.stop_event.set())
    monkeypatch.setattr(srv, "connect", lambda: True, raising=True)
    monkeypatch.setattr(srv, "login", lambda: True, raising=True)
    calls = {"quit": 0}
    monkeypatch.setattr(
        srv,
        "quit",
        lambda msg: calls.__setitem__("quit", calls["quit"] + 1),
        raising=True,
    )

    # Replace threading.Thread to avoid real threads
    class FakeThread:
        def __init__(self, target=None, daemon=None, name=None):
            self.name = name

        def start(self):
            pass

    monkeypatch.setattr(server_mod.threading, "Thread", FakeThread)
    srv.connected = True
    srv.start()
    assert calls["quit"] == 1


def test_start_fail_then_stop_before_reconnect(monkeypatch, srv):
    # Cover final check 559-560
    monkeypatch.setattr(server_mod.time, "sleep", lambda s: None)
    seq = {"n": 0}

    def is_set_seq():
        # Calls: while-cond(False), top-if(False), fail-if(False), final-check(True)
        seq["n"] += 1
        return seq["n"] >= 4

    monkeypatch.setattr(srv.stop_event, "is_set", is_set_seq, raising=True)
    monkeypatch.setattr(srv, "connect", lambda: False, raising=True)
    srv.start()


def test_start_reconnect_wait_stop(monkeypatch, srv):
    # Reach reconnect wait loop and set stop during the wait to hit 566-569 and 574
    calls = {"sleep": 0}

    def sleeper(_):
        calls["sleep"] += 1
        if calls["sleep"] == 1:
            srv.stop_event.set()

    monkeypatch.setattr(server_mod.time, "sleep", sleeper)
    monkeypatch.setattr(srv, "connect", lambda: False, raising=True)
    # Ensure initial stop checks are false
    seq = {"n": 0}

    def is_set_seq():
        seq["n"] += 1
        # false for while, top-if, fail-if, final check; then true inside wait
        return False

    # Use normal is_set and just rely on sleeper to set the event
    srv.start()


# --- quit and close ---


def test_quit_success(monkeypatch, srv):
    srv.connected = True
    sent = []
    monkeypatch.setattr(srv, "send_raw", lambda m: sent.append(m), raising=True)

    class Sock:
        def shutdown(self, how):
            pass

        def close(self):
            pass

    srv.socket = Sock()
    srv.quit("Bye")
    assert any(m.startswith("QUIT :Bye") for m in sent)


def test_quit_send_error_still_closes(monkeypatch, srv):
    srv.connected = True

    def boom(_):
        raise RuntimeError("x")

    srv.send_raw = boom

    class Sock:
        def shutdown(self, how):
            pass

        def close(self):
            pass

    srv.socket = Sock()
    srv.quit("Bye")
    assert srv.connected is False


def test_close_socket_error_branches(srv):
    class Sock:
        def shutdown(self, how):
            raise OSError("bad")

        def close(self):
            raise OSError("bad close")

    srv.socket = Sock()
    srv._close_socket()
    assert srv.socket is None


def test_stop_quit_message_and_thread_join(monkeypatch, srv):
    # Fake thread that remains alive
    class FakeThread:
        def __init__(self, name):
            self.name = name

        def join(self, timeout=None):
            pass

        def is_alive(self):
            return True

    srv.threads = [FakeThread("t1"), FakeThread("t2")]

    srv.connected = True

    class Sock:
        def shutdown(self, how):
            pass

        def close(self):
            pass

    srv.socket = Sock()

    # Force send QUIT to raise to exercise warning path
    def boom(_):
        raise RuntimeError("boom")

    monkeypatch.setattr(srv, "send_raw", boom, raising=True)

    srv.stop(quit_message="Custom bye")
    assert srv.quit_message == "Custom bye"
    assert srv.connected is False
    assert srv.socket is None
    assert srv.threads == []


def test_stop_success_sleep_and_error_path(monkeypatch, srv):
    # Cover lines 648-650 (sleep after QUIT) and 667-668 (error path)
    # First: successful QUIT path with sleep
    import time as real_time

    monkeypatch.setattr(real_time, "sleep", lambda s: None)

    srv.connected = True
    sent = []
    monkeypatch.setattr(srv, "send_raw", lambda m: sent.append(m), raising=True)

    class Sock:
        def shutdown(self, how):
            pass

        def close(self):
            pass

    srv.socket = Sock()
    srv.stop(quit_message="Bye2")
    assert any(m.startswith("QUIT :Bye2") for m in sent)

    # Now: force error inside stop() to hit exception handler
    dummy_logger = Mock()
    calls = {"n": 0}

    def boom(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("log boom")
        # subsequent calls succeed
        return None

    dummy_logger.info = boom
    monkeypatch.setattr("logger.get_logger", lambda name: dummy_logger, raising=True)
    # Rebuild server to pick up new logger
    stop = threading.Event()
    srv2 = Server(srv.config, "Bot", stop)
    srv2.connected = True
    srv2.socket = Sock()
    # send_raw OK so error is from logger.info
    monkeypatch.setattr(srv2, "send_raw", lambda m: None, raising=True)
    srv2.stop(quit_message="Ok")


# --- quit command functionality ---


def test_quit_command_console_triggers_shutdown():
    """Test that exit command in console mode sets stop event."""
    import importlib

    from command_loader import process_console_command
    from command_registry import reset_command_registry

    # Reset and load commands
    reset_command_registry()
    try:
        from command_loader import reset_commands_loaded_flag

        reset_commands_loaded_flag()
    except (ImportError, AttributeError):
        pass

    # Load command modules
    try:
        import commands
        import commands_admin
        import commands_irc

        importlib.reload(commands)
        importlib.reload(commands_admin)
        importlib.reload(commands_irc)
    except Exception:
        pass

    # Create a mock stop event
    stop_event = Mock()

    # Create bot functions with stop_event
    bot_functions = {
        "stop_event": stop_event,
        "notice_message": Mock(),
        "log": Mock(),
        "send_electricity_price": Mock(),
        "load_leet_winners": Mock(return_value={}),
        "send_weather": Mock(),
        "load": Mock(return_value={}),
        "fetch_title": Mock(),
        "handle_ipfs_command": Mock(),
    }

    # Process the exit command (no admin password needed)
    process_console_command("!exit", bot_functions)

    # Verify stop event was set
    stop_event.set.assert_called_once()


def test_quit_with_stop_event_integration():
    """Test quit command with actual threading event to verify it stops a thread."""
    # Create a real stop event
    stop_event = threading.Event()

    # Worker function that runs until stop event is set
    def worker():
        while not stop_event.is_set():
            # Simulate work with a short sleep
            stop_event.wait(0.01)

    # Start worker thread
    thread = threading.Thread(target=worker)
    thread.start()

    # Verify thread is running
    assert thread.is_alive()

    # Set the stop event (simulating the quit command effect)
    stop_event.set()

    # Wait for thread to finish
    thread.join(timeout=1.0)

    # Verify thread stopped
    assert not thread.is_alive()
    assert stop_event.is_set()
