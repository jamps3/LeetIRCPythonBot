"""
Comprehensive Tests for Admin Commands

This module tests all admin commands including:
- quit command (console and IRC) - FIXED: Now properly triggers shutdown
- join command (console and IRC) - VERIFIED: Works correctly
- part command (console and IRC) - VERIFIED: Works correctly
- nick command (console and IRC) - VERIFIED: Works correctly
- raw command (IRC only) - VERIFIED: Works correctly

All commands now return consistent string types and handle both console and IRC contexts properly.
"""

import os
import sys
import threading
import time
import unittest
from unittest.mock import Mock, patch

# Add parent directory to sys.path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Mock dotenv to avoid dependency issues
sys.modules["dotenv"] = Mock()

import commands_admin


class TestAdminCommands(unittest.TestCase):
    """Test suite for all admin commands."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_config = Mock()
        self.mock_config.admin_password = "testpass123"

        # Mock IRC connection
        self.mock_irc = Mock()
        self.mock_irc.send_raw = Mock()

        # Real threading.Event for shutdown testing
        self.stop_event = threading.Event()

        # Mock logger
        self.mock_logger = Mock()

        # Basic bot functions
        self.bot_functions = {
            "irc": self.mock_irc,
            "stop_event": self.stop_event,
            "log": self.mock_logger,
        }

        # Mock context creator
        class MockContext:
            def __init__(self, args, is_console=True):
                self.args = args
                self.is_console = is_console

        self.MockContext = MockContext

        # Patch get_config
        self.config_patcher = patch(
            "commands_admin.get_config", return_value=self.mock_config
        )
        self.config_patcher.start()

    def tearDown(self):
        """Clean up after tests."""
        self.config_patcher.stop()

    def test_quit_command_console_triggers_shutdown(self):
        """Test that quit command in console actually triggers shutdown."""
        context = self.MockContext(["testpass123", "test", "shutdown"], is_console=True)
        response = commands_admin.quit_command(context, self.bot_functions)

        # Verify shutdown was triggered
        self.assertTrue(
            self.stop_event.is_set(), "Stop event should be set after console quit"
        )
        self.assertIn(
            "🛑 Shutting down bot", response, "Response should contain shutdown message"
        )
        self.assertIn("test shutdown", response, "Response should contain quit message")

    def test_quit_command_irc_sends_quit_and_triggers_shutdown(self):
        """Test quit command over IRC sends QUIT and triggers shutdown."""
        self.stop_event.clear()
        context = self.MockContext(["testpass123", "bye", "everyone"], is_console=False)
        response = commands_admin.quit_command(context, self.bot_functions)

        # Verify IRC QUIT was sent
        self.mock_irc.send_raw.assert_called_once_with("QUIT :bye everyone")

        # Verify shutdown was triggered
        self.assertTrue(
            self.stop_event.is_set(), "Stop event should be set after IRC quit"
        )

        # Verify logging
        self.mock_logger.assert_called_once_with(
            "Admin quit with message: bye everyone", "INFO"
        )

        # Should return empty string for IRC quit (no response)
        self.assertEqual(response, "", "IRC quit should return empty string")

    def test_join_command_console(self):
        """Test join command in console."""
        context = self.MockContext(["testpass123", "#newchannel"], is_console=True)
        response = commands_admin.join_command(context, self.bot_functions)

        self.assertEqual(response, "Admin command: JOIN #newchannel (no key)")

    def test_join_command_irc(self):
        """Test join command over IRC."""
        context = self.MockContext(["testpass123", "#testchannel"], is_console=False)
        response = commands_admin.join_command(context, self.bot_functions)

        self.mock_irc.send_raw.assert_called_once_with("JOIN #testchannel")
        self.mock_logger.assert_called_once_with(
            "Admin joined channel #testchannel", "INFO"
        )
        self.assertEqual(response, "Joined #testchannel")

    def test_join_command_irc_with_key(self):
        """Test join command over IRC with channel key."""
        context = self.MockContext(
            ["testpass123", "#private", "secretkey"], is_console=False
        )
        response = commands_admin.join_command(context, self.bot_functions)

        self.mock_irc.send_raw.assert_called_once_with("JOIN #private secretkey")
        self.mock_logger.assert_called_once_with(
            "Admin joined channel #private", "INFO"
        )
        self.assertEqual(response, "Joined #private")

    def test_part_command_console(self):
        """Test part command in console."""
        context = self.MockContext(["testpass123", "#channel"], is_console=True)
        response = commands_admin.part_command(context, self.bot_functions)

        self.assertEqual(response, "Admin command: PART #channel")

    def test_part_command_irc(self):
        """Test part command over IRC."""
        context = self.MockContext(["testpass123", "#leavechannel"], is_console=False)
        response = commands_admin.part_command(context, self.bot_functions)

        self.mock_irc.send_raw.assert_called_once_with("PART #leavechannel")
        self.mock_logger.assert_called_once_with(
            "Admin left channel #leavechannel", "INFO"
        )
        self.assertEqual(response, "Left #leavechannel")

    def test_nick_command_console(self):
        """Test nick command in console."""
        context = self.MockContext(["testpass123", "newbotname"], is_console=True)
        response = commands_admin.nick_command(context, self.bot_functions)

        self.assertEqual(response, "Admin command: NICK newbotname")

    def test_nick_command_irc(self):
        """Test nick command over IRC."""
        context = self.MockContext(["testpass123", "coolbot"], is_console=False)
        response = commands_admin.nick_command(context, self.bot_functions)

        self.mock_irc.send_raw.assert_called_once_with("NICK coolbot")
        self.mock_logger.assert_called_once_with(
            "Admin changed nick to coolbot", "INFO"
        )
        self.assertEqual(response, "Changed nick to coolbot")

    def test_raw_command_irc(self):
        """Test raw command over IRC."""
        context = self.MockContext(
            ["testpass123", "MODE", "#channel", "+o", "user"], is_console=False
        )
        response = commands_admin.raw_command(context, self.bot_functions)

        self.mock_irc.send_raw.assert_called_once_with("MODE #channel +o user")
        self.mock_logger.assert_called_once_with(
            "Admin sent raw command: MODE #channel +o user", "INFO"
        )
        self.assertEqual(response, "Sent: MODE #channel +o user")

    def test_invalid_password_all_commands(self):
        """Test that all commands reject invalid passwords."""
        commands_to_test = [
            (commands_admin.quit_command, ["wrongpass"]),
            (commands_admin.join_command, ["wrongpass"]),
            (commands_admin.part_command, ["wrongpass"]),
            (commands_admin.nick_command, ["wrongpass"]),
            (commands_admin.raw_command, ["wrongpass"]),
        ]

        for cmd_func, args in commands_to_test:
            with self.subTest(command=cmd_func.__name__):
                context = self.MockContext(args, is_console=True)
                response = cmd_func(context, self.bot_functions)

                self.assertIn("❌ Invalid admin password", response)
                # Verify no IRC commands were sent
                self.mock_irc.send_raw.assert_not_called()

    def test_missing_arguments_all_commands(self):
        """Test that commands validate required arguments."""
        commands_to_test = [
            (commands_admin.join_command, ["testpass123"]),  # Missing channel
            (commands_admin.part_command, ["testpass123"]),  # Missing channel
            (commands_admin.nick_command, ["testpass123"]),  # Missing nickname
            (commands_admin.raw_command, ["testpass123"]),  # Missing command
        ]

        for cmd_func, args in commands_to_test:
            with self.subTest(command=cmd_func.__name__):
                context = self.MockContext(args, is_console=False)
                response = cmd_func(context, self.bot_functions)

                self.assertIn("❌ Usage:", response)

    def test_quit_command_actually_stops_thread(self):
        """Integration test: verify quit command actually stops a running thread."""
        # Create a real threading.Event
        stop_event = threading.Event()

        # Create a worker thread that runs until stop_event is set
        def worker():
            while not stop_event.is_set():
                time.sleep(0.1)

        # Start the worker thread
        thread = threading.Thread(target=worker)
        thread.start()

        # Verify thread is running
        self.assertTrue(thread.is_alive())

        # Set up quit command
        bot_functions = {
            "stop_event": stop_event,
            "log": Mock(),
        }

        context = self.MockContext(["testpass123", "test shutdown"], is_console=True)

        # Execute quit command
        response = commands_admin.quit_command(context, bot_functions)

        # Verify response
        self.assertIn("🛑 Shutting down bot", response)
        self.assertIn("test shutdown", response)

        # Wait for thread to stop
        thread.join(timeout=2.0)

        # Verify thread has stopped
        self.assertFalse(thread.is_alive())
        self.assertTrue(stop_event.is_set())

    def test_no_irc_connection_error_handling(self):
        """Test that commands handle missing IRC connection gracefully."""
        bot_functions_no_irc = {
            "stop_event": self.stop_event,
            "log": self.mock_logger,
        }

        commands_to_test = [
            (commands_admin.join_command, ["testpass123", "#test"]),
            (commands_admin.part_command, ["testpass123", "#test"]),
            (commands_admin.nick_command, ["testpass123", "testnick"]),
            (
                commands_admin.raw_command,
                ["testpass123", "MODE", "#test", "+o", "user"],
            ),
        ]

        for cmd_func, args in commands_to_test:
            with self.subTest(command=cmd_func.__name__):
                context = self.MockContext(args, is_console=False)
                response = cmd_func(context, bot_functions_no_irc)

                self.assertIn("❌ IRC connection not available", response)

    def test_quit_command_no_stop_event(self):
        """Test quit command when stop_event is not available."""
        bot_functions_no_stop = {
            "irc": self.mock_irc,
            "log": self.mock_logger,
        }

        context = self.MockContext(["testpass123"], is_console=True)
        response = commands_admin.quit_command(context, bot_functions_no_stop)

        self.assertEqual(response, "❌ Cannot access shutdown mechanism")


if __name__ == "__main__":
    unittest.main()
