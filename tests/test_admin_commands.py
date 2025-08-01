"""
Tests for Admin Commands - Unified Version

This module contains comprehensive tests for all admin commands including:
- quit command (console and IRC)
- join command
- part command
- nick command
- raw command
"""

import os
import sys
import threading
import time
import unittest
from unittest.mock import MagicMock, Mock, call, patch

import pytest

# Add parent directory to sys.path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from command_registry import CommandContext, CommandResponse
from commands_admin import (
    join_command,
    nick_command,
    part_command,
    quit_command,
    raw_command,
    verify_admin_password,
)


@pytest.fixture
def mock_config():
    """Create a mock configuration."""
    config = Mock()
    config.admin_password = "testpass123"
    return config


@pytest.fixture
def mock_irc():
    """Create a mock IRC connection."""
    irc = Mock()
    irc.send_raw = Mock()
    return irc


@pytest.fixture
def mock_stop_event():
    """Create a mock stop event."""
    return Mock()


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    return Mock()


@pytest.fixture
def bot_functions(mock_irc, mock_stop_event, mock_logger):
    """Create bot functions dictionary."""
    return {
        "irc": mock_irc,
        "stop_event": mock_stop_event,
        "log": mock_logger,
    }


def test_verify_admin_password_valid(mock_config):
    """Test admin password verification with valid password."""
    with patch("commands_admin.get_config", return_value=mock_config):
        assert verify_admin_password(["testpass123"]) is True


def test_verify_admin_password_invalid(mock_config):
    """Test admin password verification with invalid password."""
    with patch("commands_admin.get_config", return_value=mock_config):
        assert verify_admin_password(["wrongpass"]) is False


def test_verify_admin_password_no_args(mock_config):
    """Test admin password verification with no arguments."""
    with patch("commands_admin.get_config", return_value=mock_config):
        assert verify_admin_password([]) is False


def test_quit_command_console_triggers_shutdown(mock_config, bot_functions):
    """Test that quit command in console actually triggers shutdown."""
    context = CommandContext(
        command="quit",
        args=["testpass123", "goodbye"],
        raw_message="!quit testpass123 goodbye",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )

    with patch("commands_admin.get_config", return_value=mock_config):
        response = quit_command(context, bot_functions)

    # Verify shutdown was triggered
    bot_functions["stop_event"].set.assert_called_once()
    assert "🛑 Shutting down bot" in response
    assert "goodbye" in response


class TestAdminCommands(unittest.TestCase):
    """Test class for admin commands."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_config = Mock()
        self.mock_config.admin_password = "testpass123"
        
        self.mock_irc = Mock()
        self.mock_irc.send_raw = Mock()
        
        self.mock_stop_event = Mock()
        self.mock_logger = Mock()
        
        self.bot_functions = {
            "irc": self.mock_irc,
            "stop_event": self.mock_stop_event,
            "log": self.mock_logger,
        }

    def test_quit_command_console_no_message(self):
        """Test quit command in console without message."""
        context = CommandContext(
            command="quit",
            args=["testpass123"],
            raw_message="!quit testpass123",
            sender=None,
            target=None,
            is_private=False,
            is_console=True,
            server_name="console",
        )

        with patch("commands_admin.get_config", return_value=self.mock_config):
            response = quit_command(context, self.bot_functions)

        self.mock_stop_event.set.assert_called_once()
        self.assertIn("🛑 Shutting down bot", response)
        self.assertIn("Admin quit", response)

    def test_quit_command_console_invalid_password(self):
        """Test quit command with invalid password."""
        context = CommandContext(
            command="quit",
            args=["wrongpass"],
            raw_message="!quit wrongpass",
            sender=None,
            target=None,
            is_private=False,
            is_console=True,
            server_name="console",
        )

        with patch("commands_admin.get_config", return_value=self.mock_config):
            response = quit_command(context, self.bot_functions)

        # Verify shutdown was NOT triggered
        self.mock_stop_event.set.assert_not_called()
        self.assertEqual(response, "❌ Invalid admin password")

    def test_quit_command_console_no_stop_event(self):
        """Test quit command when stop_event is not available."""
        bot_functions_no_stop = {
            "irc": self.mock_irc,
            "log": self.mock_logger,
        }

        context = CommandContext(
            command="quit",
            args=["testpass123"],
            raw_message="!quit testpass123",
            sender=None,
            target=None,
            is_private=False,
            is_console=True,
            server_name="console",
        )

        with patch("commands_admin.get_config", return_value=self.mock_config):
            response = quit_command(context, bot_functions_no_stop)

        self.assertEqual(response, "❌ Cannot access shutdown mechanism")

    def test_quit_command_irc_sends_quit_and_triggers_shutdown(self):
        """Test quit command over IRC sends QUIT and triggers shutdown."""
        context = CommandContext(
            command="quit",
            args=["testpass123", "bye", "everyone"],
            raw_message="!quit testpass123 bye everyone",
            sender="admin",
            target="#test",
            is_private=False,
            is_console=False,
            server_name="testserver",
        )

        with patch("commands_admin.get_config", return_value=self.mock_config):
            response = quit_command(context, self.bot_functions)

        # Verify IRC QUIT was sent
        self.mock_irc.send_raw.assert_called_once_with("QUIT :bye everyone")

        # Verify shutdown was triggered
        self.mock_stop_event.set.assert_called_once()

        # Verify logging
        self.mock_logger.assert_called_once_with(
            "Admin quit with message: bye everyone", "INFO"
        )

        # Should return no response for IRC quit
        self.assertEqual(response, "")

    def test_quit_command_irc_no_connection(self):
        """Test quit command when IRC connection is not available."""
        bot_functions_no_irc = {
            "stop_event": self.mock_stop_event,
            "log": self.mock_logger,
        }

        context = CommandContext(
            command="quit",
            args=["testpass123"],
            raw_message="!quit testpass123",
            sender="admin",
            target="#test",
            is_private=False,
            is_console=False,
            server_name="testserver",
        )

        with patch("commands_admin.get_config", return_value=self.mock_config):
            response = quit_command(context, bot_functions_no_irc)

        self.assertEqual(response, "❌ IRC connection not available")

    def test_join_command_console(self):
        """Test join command in console."""
        context = CommandContext(
            command="join",
            args=["testpass123", "#newchannel"],
            raw_message="!join testpass123 #newchannel",
            sender=None,
            target=None,
            is_private=False,
            is_console=True,
            server_name="console",
        )

        with patch("commands_admin.get_config", return_value=self.mock_config):
            response = join_command(context, self.bot_functions)

        self.assertEqual(response, "Admin command: JOIN #newchannel (no key)")

    def test_join_command_console_with_key(self):
        """Test join command in console with channel key."""
        context = CommandContext(
            command="join",
            args=["testpass123", "#private", "secretkey"],
            raw_message="!join testpass123 #private secretkey",
            sender=None,
            target=None,
            is_private=False,
            is_console=True,
            server_name="console",
        )

        with patch("commands_admin.get_config", return_value=self.mock_config):
            response = join_command(context, self.bot_functions)

        self.assertEqual(response, "Admin command: JOIN #private secretkey")

    def test_join_command_irc(self):
        """Test join command over IRC."""
        context = CommandContext(
            command="join",
            args=["testpass123", "#newchannel"],
            raw_message="!join testpass123 #newchannel",
            sender="admin",
            target="#test",
            is_private=False,
            is_console=False,
            server_name="testserver",
        )

        with patch("commands_admin.get_config", return_value=self.mock_config):
            response = join_command(context, self.bot_functions)

        self.mock_irc.send_raw.assert_called_once_with("JOIN #newchannel")
        self.mock_logger.assert_called_once_with(
            "Admin joined channel #newchannel", "INFO"
        )
        self.assertEqual(response, "Joined #newchannel")

    def test_join_command_irc_with_key(self):
        """Test join command over IRC with channel key."""
        context = CommandContext(
            command="join",
            args=["testpass123", "#private", "secretkey"],
            raw_message="!join testpass123 #private secretkey",
            sender="admin",
            target="#test",
            is_private=False,
            is_console=False,
            server_name="testserver",
        )

        with patch("commands_admin.get_config", return_value=self.mock_config):
            response = join_command(context, self.bot_functions)

        self.mock_irc.send_raw.assert_called_once_with("JOIN #private secretkey")
        self.mock_logger.assert_called_once_with(
            "Admin joined channel #private", "INFO"
        )
        self.assertEqual(response, "Joined #private")

    def test_part_command_console(self):
        """Test part command in console."""
        context = CommandContext(
            command="part",
            args=["testpass123", "#channel"],
            raw_message="!part testpass123 #channel",
            sender=None,
            target=None,
            is_private=False,
            is_console=True,
            server_name="console",
        )

        with patch("commands_admin.get_config", return_value=self.mock_config):
            response = part_command(context, self.bot_functions)

        self.assertEqual(response, "Admin command: PART #channel")

    def test_part_command_irc(self):
        """Test part command over IRC."""
        context = CommandContext(
            command="part",
            args=["testpass123", "#channel"],
            raw_message="!part testpass123 #channel",
            sender="admin",
            target="#test",
            is_private=False,
            is_console=False,
            server_name="testserver",
        )

        with patch("commands_admin.get_config", return_value=self.mock_config):
            response = part_command(context, self.bot_functions)

        self.mock_irc.send_raw.assert_called_once_with("PART #channel")
        self.mock_logger.assert_called_once_with("Admin left channel #channel", "INFO")
        self.assertEqual(response, "Left #channel")

    def test_nick_command_console(self):
        """Test nick command in console."""
        context = CommandContext(
            command="nick",
            args=["testpass123", "newbot"],
            raw_message="!nick testpass123 newbot",
            sender=None,
            target=None,
            is_private=False,
            is_console=True,
            server_name="console",
        )

        with patch("commands_admin.get_config", return_value=self.mock_config):
            response = nick_command(context, self.bot_functions)

        self.assertEqual(response, "Admin command: NICK newbot")

    def test_nick_command_irc(self):
        """Test nick command over IRC."""
        context = CommandContext(
            command="nick",
            args=["testpass123", "newbot"],
            raw_message="!nick testpass123 newbot",
            sender="admin",
            target="#test",
            is_private=False,
            is_console=False,
            server_name="testserver",
        )

        with patch("commands_admin.get_config", return_value=self.mock_config):
            response = nick_command(context, self.bot_functions)

        self.mock_irc.send_raw.assert_called_once_with("NICK newbot")
        self.mock_logger.assert_called_once_with("Admin changed nick to newbot", "INFO")
        self.assertEqual(response, "Changed nick to newbot")

    def test_raw_command_irc(self):
        """Test raw command over IRC."""
        context = CommandContext(
            command="raw",
            args=["testpass123", "MODE", "#channel", "+o", "user"],
            raw_message="!raw testpass123 MODE #channel +o user",
            sender="admin",
            target="#test",
            is_private=False,
            is_console=False,
            server_name="testserver",
        )

        with patch("commands_admin.get_config", return_value=self.mock_config):
            response = raw_command(context, self.bot_functions)

        self.mock_irc.send_raw.assert_called_once_with("MODE #channel +o user")
        self.mock_logger.assert_called_once_with(
            "Admin sent raw command: MODE #channel +o user", "INFO"
        )
        self.assertEqual(response, "Sent: MODE #channel +o user")

    def test_commands_require_args(self):
        """Test that commands properly validate required arguments."""
        contexts = [
            ("join", ["testpass123"]),
            ("part", ["testpass123"]),
            ("nick", ["testpass123"]),
            ("raw", ["testpass123"]),
        ]

        commands = [join_command, part_command, nick_command, raw_command]

        for (cmd_name, args), cmd_func in zip(contexts, commands):
            with self.subTest(command=cmd_name):
                context = CommandContext(
                    command=cmd_name,
                    args=args,
                    raw_message=f"!{cmd_name} {' '.join(args)}",
                    sender="admin",
                    target="#test",
                    is_private=False,
                    is_console=False,
                    server_name="testserver",
                )

                with patch("commands_admin.get_config", return_value=self.mock_config):
                    response = cmd_func(context, self.bot_functions)

                self.assertIsInstance(response, str)
                self.assertTrue(response.startswith("❌ Usage:"))

    def test_admin_commands_use_server_send_raw(self):
        """Test that admin commands correctly use Server.send_raw() method."""
        # Mock Server instance with send_raw method
        mock_server = Mock()
        mock_server.send_raw = Mock()

        bot_functions = {
            "irc": mock_server,
            "log": Mock(),
        }

        test_cases = [
            (join_command, "join", ["testpass123", "#test"], "JOIN #test"),
            (part_command, "part", ["testpass123", "#test"], "PART #test"),
            (nick_command, "nick", ["testpass123", "newbot"], "NICK newbot"),
            (
                raw_command,
                "raw",
                ["testpass123", "MODE", "#test", "+o", "user"],
                "MODE #test +o user",
            ),
        ]

        for cmd_func, cmd_name, args, expected_raw in test_cases:
            with self.subTest(command=cmd_name):
                mock_server.send_raw.reset_mock()

                context = CommandContext(
                    command=cmd_name,
                    args=args,
                    raw_message=f"!{cmd_name} {' '.join(args)}",
                    sender="admin",
                    target="#test",
                    is_private=False,
                    is_console=False,
                    server_name="testserver",
                )

                with patch("commands_admin.get_config", return_value=self.mock_config):
                    response = cmd_func(context, bot_functions)

                # Verify that send_raw was called with the correct command
                mock_server.send_raw.assert_called_once_with(expected_raw)

                # Verify that the response indicates success
                self.assertNotIn("❌", response)


class TestQuitCommandIntegration(unittest.TestCase):
    """Integration tests for quit command with threading."""

    def test_quit_command_actually_stops_thread(self):
        """Test that quit command actually stops a running thread."""
        # Create a real threading.Event
        stop_event = threading.Event()

        # Create a simple worker thread that runs until stop_event is set
        def worker():
            while not stop_event.is_set():
                time.sleep(0.1)

        # Start the worker thread
        thread = threading.Thread(target=worker)
        thread.start()

        # Verify thread is running
        self.assertTrue(thread.is_alive())

        # Set up quit command
        mock_config = Mock()
        mock_config.admin_password = "testpass123"

        bot_functions = {
            "stop_event": stop_event,
            "log": Mock(),
        }

        context = CommandContext(
            command="quit",
            args=["testpass123", "test shutdown"],
            raw_message="!quit testpass123 test shutdown",
            sender=None,
            target=None,
            is_private=False,
            is_console=True,
            server_name="console",
        )

        # Execute quit command
        with patch("commands_admin.get_config", return_value=mock_config):
            response = quit_command(context, bot_functions)

        # Verify response
        self.assertIn("🛑 Shutting down bot", response)
        self.assertIn("test shutdown", response)

        # Wait for thread to stop
        thread.join(timeout=2.0)

        # Verify thread has stopped
        self.assertFalse(thread.is_alive())
        self.assertTrue(stop_event.is_set())


if __name__ == "__main__":
    unittest.main()
