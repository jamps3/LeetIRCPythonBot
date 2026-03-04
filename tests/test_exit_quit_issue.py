#!/usr/bin/env python3
"""
Test for !exit command sends QUIT to IRC servers.

Issue fixed: When !exit is issued from console, bot_manager.stop() is now called
which properly sends QUIT to IRC servers before shutting down.
"""

import os
import sys
from unittest.mock import MagicMock, Mock, patch

import pytest
from dotenv import load_dotenv

# Ensure src/ is in sys.path for test imports
_SRC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _SRC_PATH not in sys.path:
    sys.path.insert(0, _SRC_PATH)

# Import process_console_command for flake8 compliance (will be reloaded in fixture)
from command_loader import process_console_command  # noqa: E402

# Load environment variables for testing
load_dotenv()


@pytest.fixture(autouse=True)
def ensure_commands():
    """Ensure command registry is properly initialized before each test."""
    # CRITICAL: Ensure src/ is first in path - cmd_modules must be imported from src/
    src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    # Also ensure sys.path[0] is not the tests folder (pytest may set it there)
    if sys.path and "tests" in sys.path[0]:
        sys.path.pop(0)

    # Import fresh to ensure we get the right module from src/
    import importlib

    importlib.invalidate_caches()

    # Force reload from source: remove any cached cmd_modules
    # but keep command_loader reference for this test
    mods_to_remove = [
        k
        for k in list(sys.modules.keys())
        if (k.startswith("cmd_modules") or k.startswith("command_"))
        and k != "command_loader"
    ]
    for mod in mods_to_remove:
        del sys.modules[mod]

    from command_loader import (
        load_all_commands,
        process_console_command,
        reset_commands_loaded_flag,
    )
    from command_registry import get_command_registry

    # Force reload: reset flag and clear registry
    reset_commands_loaded_flag()
    registry = get_command_registry()
    registry._commands.clear()  # Clear any stale commands
    registry._aliases.clear()

    # Reload all commands
    load_all_commands()

    # Make process_console_command available globally for tests
    globals()["process_console_command"] = process_console_command


class TestExitCommandQUIT:
    """Test that !exit sends QUIT to IRC servers."""

    def test_exit_command_calls_bot_manager_stop_with_quit_message(self):
        """
        Test that !exit from console calls bot_manager.stop() with the quit message.

        This verifies the fix: bot_manager.stop() is called which internally
        calls server_manager.shutdown(quit_message) which sends QUIT to servers.
        """
        # Create mock bot_manager
        mock_bot_manager = Mock()

        # Create mock stop_event (for fallback)
        mock_stop_event = Mock()

        # Create mock notice_message to capture the response
        mock_notice = Mock()

        # Create bot_functions like console_manager does
        bot_functions = {
            "notice_message": mock_notice,
            "stop_event": mock_stop_event,
            "bot_manager": mock_bot_manager,
            "server_manager": Mock(),  # Shouldn't be needed when bot_manager is available
            "set_quit_message": Mock(),
        }

        # Call !exit command with custom quit message
        process_console_command("!exit Bye bye IRC!", bot_functions)

        # Verify bot_manager.stop was called with the quit message
        mock_bot_manager.stop.assert_called_once_with("Bye bye IRC!")

        # Verify notice was called with shutdown message
        mock_notice.assert_called()
        call_args = str(mock_notice.call_args)
        assert "shutdown" in call_args.lower() or "Bye bye IRC!" in call_args

    def test_exit_command_calls_bot_manager_stop_without_message(self):
        """
        Test that !exit without message calls bot_manager.stop() with None.
        """
        # Create mock bot_manager
        mock_bot_manager = Mock()

        # Create mock notice_message
        mock_notice = Mock()

        # Create bot_functions
        bot_functions = {
            "notice_message": mock_notice,
            "stop_event": Mock(),
            "bot_manager": mock_bot_manager,
            "set_quit_message": Mock(),
        }

        # Call !exit command without message
        process_console_command("!exit", bot_functions)

        # Verify bot_manager.stop was called with None
        mock_bot_manager.stop.assert_called_once_with(None)

    def test_exit_command_fallback_to_stop_event(self):
        """
        Test that !exit falls back to stop_event if bot_manager not available.
        """
        # Create mock stop_event (no bot_manager)
        mock_stop_event = Mock()

        # Create mock notice_message
        mock_notice = Mock()

        # Create bot_functions without bot_manager
        bot_functions = {
            "notice_message": mock_notice,
            "stop_event": mock_stop_event,
            "bot_manager": None,
            "set_quit_message": Mock(),
        }

        # Call !exit command
        process_console_command("!exit Bye bye!", bot_functions)

        # Verify stop_event.set was called (fallback behavior)
        mock_stop_event.set.assert_called_once()

        # Verify notice was called
        mock_notice.assert_called()


class TestQuitCommand:
    """Test the !quit command (alias for !exit)."""

    def test_quit_command_calls_bot_manager_stop_with_message(self):
        """
        Test that !quit from console calls bot_manager.stop() with the quit message.
        """
        # Create mock bot_manager
        mock_bot_manager = Mock()

        # Create mock notice_message to capture the response
        mock_notice = Mock()

        # Create bot_functions like console_manager does
        bot_functions = {
            "notice_message": mock_notice,
            "stop_event": Mock(),
            "bot_manager": mock_bot_manager,
            "set_quit_message": Mock(),
        }

        # Call !quit command with custom quit message
        process_console_command("!quit Bye bye IRC!", bot_functions)

        # Verify bot_manager.stop was called with the quit message
        mock_bot_manager.stop.assert_called_once_with("Bye bye IRC!")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
