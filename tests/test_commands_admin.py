"""
Tests for admin commands in cmd_modules/admin.py
"""

import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

# Add src to path before importing project modules
_TEST_ROOT = os.path.dirname(os.path.abspath(__file__))
if _TEST_ROOT not in sys.path:
    sys.path.insert(0, os.path.join(_TEST_ROOT, "..", "src"))

from command_registry import CommandContext  # noqa: E402
from config import ServerConfig  # noqa: E402


@pytest.fixture
def mock_bot_functions():
    """Create mock bot functions for testing commands."""
    return {
        "log": Mock(),
        "notice_message": Mock(),
    }


@pytest.fixture
def console_context():
    """Create a mock CommandContext for console commands."""
    return CommandContext(
        command="",
        args=[],
        raw_message="!test",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )


@pytest.fixture
def irc_context():
    """Create a mock CommandContext for IRC commands."""
    return CommandContext(
        command="",
        args=[],
        raw_message="!test",
        sender="TestUser",
        target="#test",
        is_private=False,
        is_console=False,
        server_name="TestServer",
    )


class TestConnectCommand:
    """Tests for the !connect command."""

    def test_connect_command_exists(self):
        """Test connect command is registered."""
        from cmd_modules.admin import connect_command

        assert callable(connect_command)


class TestDisconnectCommand:
    """Tests for the !disconnect command."""

    def test_disconnect_command_exists(self):
        """Test disconnect command is registered."""
        from cmd_modules.admin import disconnect_command

        assert callable(disconnect_command)


class TestExitCommand:
    """Tests for the !exit command."""

    def test_exit_command_exists(self):
        """Test exit command is registered."""
        from cmd_modules.admin import exit_command

        assert callable(exit_command)


class TestCountdownCommand:
    """Tests for the !k (countdown) command."""

    def test_k_command_exists(self):
        """Test k (countdown) command is registered."""
        from cmd_modules.admin import countdown_command

        assert callable(countdown_command)


class TestIgnoreCommand:
    """Tests for the !ignorecommand privileged admin command."""

    def test_ignorecommand_adds_command_and_updates_live_server(
        self, tmp_path, monkeypatch
    ):
        from cmd_modules import admin_privileged

        state_file = tmp_path / "state.json"
        state_file.write_text(
            """
{
  "config": {
    "servers": [
      {
        "name": "Libera",
        "host": "irc.example",
        "port": 6697,
        "channels": ["#test"],
        "banned_commands": []
      }
    ]
  }
}
""".strip(),
            encoding="utf-8",
        )
        server_config = ServerConfig(
            name="Libera",
            host="irc.example",
            port=6697,
            channels=["#test"],
            banned_commands=[],
        )
        monkeypatch.setattr(
            admin_privileged,
            "get_config",
            lambda: SimpleNamespace(
                admin_password="secret",
                state_file=str(state_file),
                servers=[server_config],
            ),
        )
        monkeypatch.setattr(
            admin_privileged,
            "get_config_manager",
            lambda: SimpleNamespace(reload_config=Mock()),
        )
        live_server = SimpleNamespace(config=server_config)
        context = CommandContext(
            command="ignorecommand",
            args=["secret", "Libera", "!weather"],
            raw_message="!ignorecommand secret Libera !weather",
            is_console=False,
            server_name="Libera",
        )

        result = admin_privileged.ignore_command_command(
            context,
            {"server_manager": SimpleNamespace(servers={"Libera": live_server})},
        )

        assert result == "✅ Ignoring !weather on Libera"
        assert live_server.config.banned_commands == ["weather"]
        saved_state = json.loads(state_file.read_text(encoding="utf-8"))
        assert saved_state["config"]["servers"][0]["banned_commands"] == ["weather"]

    def test_ignorecommand_lists_all_and_single_server(self, monkeypatch):
        from cmd_modules import admin_privileged

        servers = [
            ServerConfig(
                name="Libera",
                host="irc.example",
                port=6697,
                channels=["#test"],
                banned_commands=["weather", "ping"],
            ),
            ServerConfig(
                name="Other",
                host="irc2.example",
                port=6667,
                channels=["#other"],
                banned_commands=[],
            ),
        ]
        monkeypatch.setattr(
            admin_privileged,
            "get_config",
            lambda: SimpleNamespace(
                admin_password="secret",
                state_file="unused",
                servers=servers,
            ),
        )
        context = CommandContext(
            command="ignorecommand",
            args=["secret", "list"],
            raw_message="!ignorecommand secret list",
            is_console=False,
        )

        result = admin_privileged.ignore_command_command(context, {})

        assert "Libera: ping, weather" in result
        assert "Other: (none)" in result

        context.args = ["secret", "list", "Libera"]
        result = admin_privileged.ignore_command_command(context, {})

        assert result == "Ignored commands:\nLibera: ping, weather"

    @pytest.mark.parametrize("server_arg", ["irc.nerv.fi", "irc.nerv.fi:6697"])
    def test_ignorecommand_accepts_host_for_derived_server_name(
        self, tmp_path, monkeypatch, server_arg
    ):
        from cmd_modules import admin_privileged

        state_file = tmp_path / "state.json"
        state_file.write_text(
            """
{
  "config": {
    "servers": [
      {
        "host": "irc.nerv.fi",
        "port": 6697,
        "channels": ["#test"],
        "banned_commands": []
      }
    ]
  }
}
""".strip(),
            encoding="utf-8",
        )
        server_config = ServerConfig(
            name="irc.nerv.fi:6697",
            host="irc.nerv.fi",
            port=6697,
            channels=["#test"],
            banned_commands=[],
        )
        monkeypatch.setattr(
            admin_privileged,
            "get_config",
            lambda: SimpleNamespace(
                admin_password="secret",
                state_file=str(state_file),
                servers=[server_config],
            ),
        )
        monkeypatch.setattr(
            admin_privileged,
            "get_config_manager",
            lambda: SimpleNamespace(reload_config=Mock()),
        )
        live_server = SimpleNamespace(config=server_config)
        context = CommandContext(
            command="ignorecommand",
            args=["secret", server_arg, "!about"],
            raw_message=f"!ignorecommand secret {server_arg} !about",
            is_console=False,
        )

        result = admin_privileged.ignore_command_command(
            context,
            {
                "server_manager": SimpleNamespace(
                    servers={"irc.nerv.fi:6697": live_server}
                )
            },
        )

        assert result == "✅ Ignoring !about on irc.nerv.fi:6697"
        assert live_server.config.banned_commands == ["about"]
        saved_state = json.loads(state_file.read_text(encoding="utf-8"))
        assert saved_state["config"]["servers"][0]["banned_commands"] == ["about"]

        context.args = ["secret", "list", "irc.nerv.fi"]
        result = admin_privileged.ignore_command_command(context, {})

        assert result == "Ignored commands:\nirc.nerv.fi:6697: about"

    def test_ignorecommand_rejects_bad_password(self):
        from cmd_modules import admin_privileged

        context = CommandContext(
            command="ignorecommand",
            args=["wrong", "list"],
            raw_message="!ignorecommand wrong list",
            is_console=False,
        )

        assert (
            admin_privileged.ignore_command_command(context, {})
            == "❌ Invalid admin password"
        )
