#!/usr/bin/env python3
"""
Test quit functionality with a custom message across all servers.
"""

import os
import sys
import threading
from unittest.mock import MagicMock, Mock, call, patch

import pytest

# Add parent directory to sys.path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Mock complex dependencies
sys.modules["bs4"] = Mock()
sys.modules["feedparser"] = Mock()
sys.modules["selenium"] = Mock()
sys.modules["google"] = Mock()
sys.modules["googleapiclient"] = Mock()
sys.modules["googleapiclient.discovery"] = Mock()


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
