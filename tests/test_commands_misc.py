"""
Tests for misc commands in cmd_modules/misc.py
"""

import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add src to path before importing project modules - must be at very top
_TEST_ROOT = os.path.dirname(os.path.abspath(__file__))
if _TEST_ROOT not in sys.path:
    sys.path.insert(0, os.path.join(_TEST_ROOT, "..", "src"))

from command_registry import CommandContext  # noqa: E402


@pytest.fixture(autouse=True)
def ensure_commands_loaded():
    """Ensure command modules are loaded before tests run."""
    import importlib

    from command_registry import reset_command_registry

    # Reset registry first
    reset_command_registry()

    # Import and reload cmd_modules.misc to register commands
    import cmd_modules.misc

    try:
        importlib.reload(cmd_modules.misc)
    except Exception:
        pass

    yield

    # Cleanup
    reset_command_registry()


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


class TestNPCommand:
    """Tests for the !np (name day) command."""

    def test_np_command_today(self, console_context, mock_bot_functions):
        """Test np command shows today's name days."""
        from cmd_modules.misc import np_command

        # Set up context with no args (should show today)
        console_context.args = []
        console_context.args_text = ""
        console_context.command = "np"

        result = np_command(console_context, mock_bot_functions)

        # Should return a string with name day info
        assert result is not None
        assert isinstance(result, str)
        # Should contain "Nimipäivät" or "nimipäivä" (case insensitive)
        assert "nimipäiv" in result.lower()
        # Should contain today's date (use pattern matching for any day)
        # Check for the date format like "DD.M" or "DD.MM.YYYY"
        import re

        # Match pattern like "4.3" or "04.3" or "4.03" etc at end of "tänään"
        assert re.search(
            r"\d+\.\d+", result
        ), f"Expected date pattern in result: {result}"

    def test_np_command_search_name(self, console_context, mock_bot_functions):
        """Test np command can search by name."""
        from cmd_modules.misc import np_command

        console_context.args = ["Kauko"]
        console_context.args_text = "Kauko"
        console_context.command = "np"

        result = np_command(console_context, mock_bot_functions)

        # Should return search results
        assert result is not None
        assert isinstance(result, str)
        # Should find Kauko
        assert "Kauko" in result or "3.3" in result

    def test_np_command_file_not_found(self, console_context, mock_bot_functions):
        """Test np command handles missing data file."""
        from cmd_modules.misc import np_command

        console_context.args = []
        console_context.args_text = ""
        console_context.command = "np"

        with patch("os.path.exists", return_value=False):
            result = np_command(console_context, mock_bot_functions)
            assert "not found" in result.lower()


class TestKaikuCommand:
    """Tests for the !kaiku (echo) command."""

    @pytest.mark.anyio
    async def test_kaiku_console_echo(self, console_context, mock_bot_functions):
        """Test kaiku command echoes message on console."""
        from cmd_modules.misc import echo_command

        console_context.args = ["Hello", "World"]
        console_context.args_text = "Hello World"
        console_context.command = "kaiku"

        result = await echo_command(console_context, mock_bot_functions)

        # Console should return prefixed message
        assert "Console: Hello World" in result

    @pytest.mark.anyio
    async def test_kaiku_irc_echo(self, irc_context, mock_bot_functions):
        """Test kaiku command echoes message on IRC."""
        from cmd_modules.misc import echo_command

        irc_context.args = ["Hello", "World"]
        irc_context.args_text = "Hello World"
        irc_context.command = "kaiku"

        result = await echo_command(irc_context, mock_bot_functions)

        # IRC should return sender prefixed message
        assert "TestUser: Hello World" in result

    @pytest.mark.anyio
    async def test_kaiku_no_args(self, console_context, mock_bot_functions):
        """Test kaiku command with no args returns usage."""
        from cmd_modules.misc import echo_command

        console_context.args = []
        console_context.args_text = ""
        console_context.command = "kaiku"

        result = await echo_command(console_context, mock_bot_functions)

        assert "Usage" in result


class Test420Command:
    """Tests for the !420 command."""

    def test_420_command_exists(self):
        """Test 420 command is registered."""
        from cmd_modules.misc import four_twenty_command

        assert callable(four_twenty_command)


class TestQuoteCommand:
    """Tests for the !quote command."""

    def test_quote_command_exists(self):
        """Test quote command is registered."""
        from cmd_modules.misc import quote_command

        assert callable(quote_command)


class TestMatkaCommand:
    """Tests for the !matka (travel) command."""

    def test_matka_command_exists(self):
        """Test matka command is registered."""
        from cmd_modules.misc import matka_command

        assert callable(matka_command)


class TestLeetsCommand:
    """Tests for the !leets command."""

    def test_leets_command_exists(self):
        """Test leets command is registered."""
        from cmd_modules.misc import leets_command

        assert callable(leets_command)


class TestScheduleCommand:
    """Tests for the !schedule command."""

    def test_schedule_command_exists(self):
        """Test schedule command is registered."""
        from cmd_modules.misc import schedule_command

        assert callable(schedule_command)


class TestIPFSCommand:
    """Tests for the !ipfs command."""

    def test_ipfs_command_exists(self):
        """Test ipfs command is registered."""
        from cmd_modules.misc import ipfs_command

        assert callable(ipfs_command)


class TestDreamCommand:
    """Tests for the !dream command."""

    def test_dream_command_exists(self):
        """Test dream command is registered."""
        from command_registry import get_command_registry

        registry = get_command_registry()
        commands = registry.get_commands_info()
        command_names = [cmd.name for cmd in commands]
        assert "dream" in command_names

    def test_dream_command_toggle(self):
        """Test dream command toggles channel state."""
        from unittest.mock import Mock

        from cmd_modules.misc import dream_command

        # Create mock bot functions
        mock_bot_functions = {
            "data_manager": Mock(),
            "dream_service": Mock(),
        }

        # Mock data manager
        mock_bot_functions["data_manager"].load_state.return_value = {
            "dream_channels": []
        }
        mock_bot_functions["data_manager"].save_state = Mock()

        # Mock dream service
        mock_bot_functions["dream_service"].toggle_dream_channel.return_value = True
        mock_bot_functions["dream_service"].is_dream_channel_enabled.return_value = True

        # Create context
        context = CommandContext(
            command="dream",
            args=["toggle"],
            raw_message="!dream toggle",
            sender="testuser",
            target="#test",
            is_console=False,
        )

        # Test toggle command
        result = dream_command(context, mock_bot_functions)

        # The function returns a string (not CommandResponse in this case)
        assert isinstance(result, str)
        assert "enabled" in result.lower()
        assert "#test" in result

    def test_dream_command_status(self):
        """Test dream command shows status."""
        from unittest.mock import Mock

        from cmd_modules.misc import dream_command

        # Create mock bot functions
        mock_bot_functions = {
            "data_manager": Mock(),
            "dream_service": Mock(),
        }

        # Mock data manager
        mock_bot_functions["data_manager"].load_state.return_value = {
            "dream_channels": ["#test", "#other"]
        }

        # Mock dream service
        mock_bot_functions["dream_service"].generate_dream.return_value = (
            "Test dream content"
        )

        # Create context
        context = CommandContext(
            command="dream",
            args=["report"],
            raw_message="!dream report",
            sender="testuser",
            target="#test",
            is_console=False,
        )

        # Test status command
        result = dream_command(context, mock_bot_functions)

        # The function returns a string (not CommandResponse)
        assert isinstance(result, str)
