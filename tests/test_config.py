#!/usr/bin/env python3
"""
Pytest Configuration System tests

Comprehensive tests for the configuration management system.
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

# Ensure clean import
import config as cfg


@pytest.fixture(autouse=True)
def reset_config_manager():
    # Reset global manager across tests
    cfg._config_manager = None
    yield
    cfg._config_manager = None


def test_serverconfig_post_init_channel_prefix_and_keys_padding():
    c = cfg.ServerConfig(
        host="h", port=6667, channels=["chan", "#x"], keys=["k1"], name="n"
    )
    # channels should be prefixed
    assert c.channels == ["#chan", "#x"]
    # keys should be extended to match channels len
    assert c.keys == ["k1", ""]

    # When no keys provided
    c2 = cfg.ServerConfig(host="h", port=6667, channels=["#a"], name="n2")
    assert c2.keys is None


def test_configmanager_loads_env_and_caching(monkeypatch, tmp_path):
    calls = {"n": 0}
    # Fake load_dotenv
    monkeypatch.setattr(
        cfg,
        "load_dotenv",
        lambda *a, **k: (calls.__setitem__("n", calls["n"] + 1) or True),
    )

    m = cfg.ConfigManager(env_file=str(tmp_path / ".env"))
    assert calls["n"] == 1

    # Provide server configs via method stub
    sc = [cfg.ServerConfig(host="h", port=1234, channels=["#c"], name="h")]
    monkeypatch.setattr(
        cfg.ConfigManager, "_load_server_configs", lambda self: sc, raising=True
    )

    # Set envs for other fields
    monkeypatch.setenv("BOT_NAME", "B")
    monkeypatch.setenv("BOT_VERSION", "9.9.9")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("HISTORY_FILE", "hist.json")
    monkeypatch.setenv("EKAVIKA_FILE", "ek.json")
    monkeypatch.setenv("WORDS_FILE", "w.json")
    monkeypatch.setenv("SUBSCRIBERS_FILE", "s.json")
    monkeypatch.setenv("RECONNECT_DELAY", "42")
    monkeypatch.setenv("QUIT_MESSAGE", "bye")
    monkeypatch.setenv("ADMIN_PASSWORD", "pw")
    monkeypatch.setenv("WEATHER_API_KEY", "wa")
    monkeypatch.setenv("ELECTRICITY_API_KEY", "ea")
    monkeypatch.setenv("OPENAI_API_KEY", "oa")
    monkeypatch.setenv("YOUTUBE_API_KEY", "ya")

    c = m.config
    # Cached property
    assert m.config is c
    # Values
    assert (c.name, c.version, c.log_level) == ("B", "9.9.9", "DEBUG")
    assert (c.history_file, c.ekavika_file, c.words_file, c.subscribers_file) == (
        "hist.json",
        "ek.json",
        "w.json",
        "s.json",
    )
    assert (c.reconnect_delay, c.quit_message) == (42, "bye")
    assert (
        c.admin_password,
        c.weather_api_key,
        c.electricity_api_key,
        c.openai_api_key,
        c.youtube_api_key,
    ) == (
        "pw",
        "wa",
        "ea",
        "oa",
        "ya",
    )

    # Reload resets cache and calls load_dotenv again
    m.reload_config()
    assert calls["n"] == 2


def test_get_server_by_name_and_primary(monkeypatch):
    m = cfg.ConfigManager()
    servers = [
        cfg.ServerConfig(host="h1", port=1, channels=["#a"], name="s1"),
        cfg.ServerConfig(host="h2", port=2, channels=["#b"], name="s2"),
    ]
    monkeypatch.setattr(
        cfg.ConfigManager, "_load_server_configs", lambda self: servers, raising=True
    )
    # Force reload
    m.reload_config()
    # Access property
    _ = m.config

    assert m.get_server_by_name("s2").host == "h2"
    assert m.get_server_by_name("zzz") is None
    assert m.get_primary_server().name == "s1"
    # No servers -> None
    monkeypatch.setattr(
        cfg.ConfigManager, "_load_server_configs", lambda self: [], raising=True
    )
    m.reload_config()
    assert m.get_primary_server() is None


def test_validate_config_errors_and_paths(monkeypatch, tmp_path):
    m = cfg.ConfigManager()
    # No servers and no API keys by default
    monkeypatch.setattr(
        cfg.ConfigManager, "_load_server_configs", lambda self: [], raising=True
    )
    m.reload_config()
    # Ensure API keys are absent regardless of developer machine .env
    monkeypatch.delenv("WEATHER_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    errs = m.validate_config()
    joined = ",".join(errs)
    assert "No server configurations found" in joined
    assert "Weather API key not configured" in joined
    assert "OpenAI API key not configured" in joined

    # With server and existing dirs, no file path errors
    servers = [cfg.ServerConfig(host="h", port=1, channels=["#a"], name="s")]
    monkeypatch.setattr(
        cfg.ConfigManager, "_load_server_configs", lambda self: servers, raising=True
    )
    # Set API keys and paths in a real directory
    d = tmp_path / "d"
    d.mkdir()
    monkeypatch.setenv("WEATHER_API_KEY", "x")
    monkeypatch.setenv("OPENAI_API_KEY", "y")
    monkeypatch.setenv("HISTORY_FILE", str(d / "h.json"))
    monkeypatch.setenv("EKAVIKA_FILE", str(d / "e.json"))
    monkeypatch.setenv("WORDS_FILE", str(d / "w.json"))
    monkeypatch.setenv("SUBSCRIBERS_FILE", str(d / "s.json"))
    m.reload_config()
    errs2 = m.validate_config()
    # Should be empty
    assert errs2 == []

    # Non-existent directories trigger errors (set two to ensure branch executes)
    monkeypatch.setenv("HISTORY_FILE", str(tmp_path / "no" / "h.json"))
    monkeypatch.setenv("SUBSCRIBERS_FILE", str(tmp_path / "no2" / "s.json"))
    m.reload_config()
    errs3 = m.validate_config()
    assert any("does not exist" in e for e in errs3)
    assert any("Subscribers file directory does not exist" in e for e in errs3)


def test_save_config_to_json(tmp_path, monkeypatch):
    m = cfg.ConfigManager()
    servers = [cfg.ServerConfig(host="h", port=1, channels=["#a"], name="s")]
    monkeypatch.setattr(
        cfg.ConfigManager, "_load_server_configs", lambda self: servers, raising=True
    )
    m.reload_config()
    p = tmp_path / "out.json"
    m.save_config_to_json(str(p))
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["bot"]["name"] == m.config.name
    assert data["servers"][0]["name"] == "s"
    assert "drink_words" in data


def test_global_getters_and_env_loader(monkeypatch):
    # load_env_file proxies load_dotenv()
    monkeypatch.setattr(cfg, "load_dotenv", lambda *a, **k: True)
    assert cfg.load_env_file() is True

    # config manager singleton
    cm1 = cfg.get_config_manager()
    cm2 = cfg.get_config_manager()
    assert cm1 is cm2

    # get_config returns BotConfig
    botc = cfg.get_config()
    assert isinstance(botc, cfg.BotConfig)


def test_parse_csv_variants():
    assert cfg.parse_comma_separated_values("") == []
    assert cfg.parse_comma_separated_values("a, b ,c") == ["a", "b", "c"]
    # Quoted inputs are de-quoted then split like normal
    assert cfg.parse_comma_separated_values('"a, b ,c"') == ["a", "b", "c"]
    assert cfg.parse_comma_separated_values("'x, y'") == ["x", "y"]


def test_get_server_configs_parsing_and_defaults(monkeypatch, capsys):
    # Clear env of SERVER vars
    for k in list(os.environ.keys()):
        if k.startswith("SERVER"):
            monkeypatch.delenv(k, raising=False)

    # No servers -> default with warning
    servers = cfg.get_server_configs()
    captured = capsys.readouterr()
    assert any("Warning: No server configurations" in captured.out for _ in [0])
    assert servers[0].host == "irc.libera.chat"
    assert servers[0].channels == ["#test"]

    # Add two servers
    monkeypatch.setenv("SERVER1_HOST", "h1")
    monkeypatch.setenv("SERVER1_PORT", "7000")
    monkeypatch.setenv("SERVER1_CHANNELS", "a,b , #c")
    monkeypatch.setenv("SERVER1_KEYS", "k1,k2")
    monkeypatch.setenv("SERVER1_TLS", "yes")
    monkeypatch.setenv("SERVER1_ALLOW_INSECURE_TLS", "1")
    monkeypatch.setenv("SERVER1_HOSTNAME", "srv1")

    monkeypatch.setenv("SERVER2_HOST", "h2")
    monkeypatch.setenv("SERVER2_PORT", "not-int")  # fallback path
    monkeypatch.setenv("SERVER2_CHANNELS", "#z")
    monkeypatch.setenv("SERVER2_TLS", "false")

    # Add a malformed server with empty host to hit 'continue' branch
    monkeypatch.setenv("SERVER9_HOST", "")

    servers2 = cfg.get_server_configs()
    # We don't rely on order, find by host
    by_host = {s.host: s for s in servers2}
    s1 = by_host["h1"]
    s2 = by_host["h2"]

    assert (
        s1.port == 7000
        and s1.tls is True
        and s1.allow_insecure_tls is True
        and s1.name == "srv1"
    )
    assert s1.channels == ["#a", "#b", "#c"]
    # keys padded to channels
    assert s1.keys == ["k1", "k2", ""]

    assert s2.port == 6667 and s2.tls is False and s2.channels == ["#z"]


def test_get_server_config_by_name_and_channel_keys(monkeypatch):
    # Prepare env for a server
    monkeypatch.setenv("SERVER1_HOST", "h")
    monkeypatch.setenv("SERVER1_CHANNELS", "a,b")
    servers = cfg.get_server_configs()
    name = servers[0].name

    found = cfg.get_server_config_by_name(name)
    assert found is not None and found.name == name

    # Not found path
    assert cfg.get_server_config_by_name("unknown-name") is None

    # Channel-key pairs with and without keys
    pairs_no_keys = cfg.get_channel_key_pairs(found)
    assert pairs_no_keys == [("#a", ""), ("#b", "")]

    found.keys = ["k1"]
    # __post_init__ won't be called here; enforce padding like function does when zipping
    pairs_with_keys = cfg.get_channel_key_pairs(found)
    # Since keys shorter, zip truncates, but our function returns zip as-is -> ensure length equals len(found.keys)
    assert pairs_with_keys == [("#a", "k1")]


def test_api_key_and_channel_id_helpers():
    os.environ["X_KEY"] = "val"
    assert cfg.get_api_key("X_KEY") == "val"
    assert cfg.get_api_key("MISSING", default="d") == "d"

    assert cfg.generate_server_channel_id("srv", "chan") == "srv:#chan"
    assert cfg.generate_server_channel_id("srv", "#chan") == "srv:#chan"

    assert cfg.parse_server_channel_id("srv:#c") == ("srv", "#c")
    assert cfg.parse_server_channel_id("invalid") == ("invalid", "")


# Add the parent directory to Python path to ensure imports work in CI
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


def test_config_loading():
    """Test basic configuration loading."""
    from config import get_config, get_config_manager

    config_manager = get_config_manager()
    config = get_config()

    # Basic validation
    assert config.name is not None, "Bot name should be set"
    assert config.version is not None, "Version should be set"
    assert isinstance(config.servers, list), "Servers should be a list"


def test_config_validation():
    """Test configuration validation."""
    from config import get_config_manager

    config_manager = get_config_manager()
    errors = config_manager.validate_config()

    # Should not have critical errors
    critical_errors = [e for e in errors if "not found" in e.lower()]

    assert len(critical_errors) == 0, f"Critical config errors: {critical_errors}"


def test_server_config_parsing():
    """Test server configuration parsing."""
    from config import get_config_manager

    config_manager = get_config_manager()
    config = config_manager.config

    assert config.servers, "Should have servers configured"

    server = config.servers[0]

    # Validate server structure
    assert hasattr(server, "host"), "Server should have host"
    assert hasattr(server, "port"), "Server should have port"
    assert hasattr(server, "channels"), "Server should have channels"
    assert isinstance(server.port, int), "Port should be integer"
    assert isinstance(server.channels, list), "Channels should be list"


def test_environment_variable_handling():
    """Test environment variable handling."""
    import os

    from config import ConfigManager

    # Save current environment state
    original_bot_name = os.environ.get("BOT_NAME")

    # Create temporary .env file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write("BOT_NAME=test_bot\n")
        f.write("TEST_VAR=test_value\n")
        temp_env_path = f.name

    try:
        # Clear any existing BOT_NAME from environment
        if "BOT_NAME" in os.environ:
            del os.environ["BOT_NAME"]

        # Test loading from specific file
        manager = ConfigManager(temp_env_path)

        # Check if bot name was loaded from the temporary file
        config = manager.config
        assert config.name == "test_bot", f"Expected test_bot, got {config.name}"

    finally:
        # Restore original environment
        if original_bot_name is not None:
            os.environ["BOT_NAME"] = original_bot_name
        elif "BOT_NAME" in os.environ:
            del os.environ["BOT_NAME"]

        os.unlink(temp_env_path)


def test_config_json_export():
    """Test configuration JSON export functionality."""
    from config import get_config_manager

    config_manager = get_config_manager()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        temp_json_path = f.name

    try:
        config_manager.save_config_to_json(temp_json_path)

        # Verify file was created and contains valid JSON
        # Use UTF-8 encoding explicitly to handle any Unicode characters
        with open(temp_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Check structure
        assert "bot" in data, "JSON should contain bot section"
        assert "servers" in data, "JSON should contain servers section"
        assert "files" in data, "JSON should contain files section"

        # Verify bot section has required fields
        bot_section = data["bot"]
        assert "name" in bot_section, "Bot section should have name"
        assert "version" in bot_section, "Bot section should have version"

    finally:
        if os.path.exists(temp_json_path):
            os.unlink(temp_json_path)


def test_config_server_lookup():
    """Test server configuration lookup functionality."""
    from config import get_config_manager

    config_manager = get_config_manager()

    # Test primary server lookup
    primary = config_manager.get_primary_server()
    assert primary is not None, "Should have a primary server"

    # Test server lookup by name
    if config_manager.config.servers:
        server_name = config_manager.config.servers[0].name
        found_server = config_manager.get_server_by_name(server_name)
        assert found_server is not None, f"Should find server {server_name}"
        assert found_server.name == server_name, "Should return correct server"

    # Test non-existent server
    non_existent = config_manager.get_server_by_name("NON_EXISTENT")
    assert non_existent is None, "Should return None for non-existent server"
