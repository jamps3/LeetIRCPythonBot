#!/usr/bin/env python3
"""
Minimal Admin Commands Tests

Tests for the remaining admin commands after moving IRC commands to commands_irc.py
"""

import os
import sys
from unittest.mock import MagicMock, Mock, call, patch

import pytest

from command_registry import CommandContext, CommandResponse
from commands_admin import (
    admin_quit_command,
    openai_command,
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
        "set_quit_message": Mock(),
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


def test_admin_quit_command_console_triggers_shutdown(mock_config, bot_functions):
    """Test that admin_quit command in console triggers shutdown."""
    context = CommandContext(
        command="admin_quit",
        args=["testpass123", "goodbye"],
        raw_message="!admin_quit testpass123 goodbye",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )

    with patch("commands_admin.get_config", return_value=mock_config):
        response = admin_quit_command(context, bot_functions)

    # Verify shutdown was triggered
    bot_functions["stop_event"].set.assert_called_once()
    assert "🛑 Shutting down bot" in response
    assert "goodbye" in response


def test_admin_quit_command_invalid_password(mock_config, bot_functions):
    """Test admin_quit command with invalid password."""
    context = CommandContext(
        command="admin_quit",
        args=["wrongpass"],
        raw_message="!admin_quit wrongpass",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )

    with patch("commands_admin.get_config", return_value=mock_config):
        response = admin_quit_command(context, bot_functions)

    # Verify shutdown was NOT triggered
    bot_functions["stop_event"].set.assert_not_called()
    assert response == "❌ Invalid admin password"


def test_openai_command_valid(mock_config, bot_functions):
    """Test openai command with valid parameters."""
    bot_functions["set_openai_model"] = Mock(return_value="✅ Model set to gpt-4")

    context = CommandContext(
        command="openai",
        args=["testpass123", "gpt-4"],
        raw_message="!openai testpass123 gpt-4",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )

    with patch("commands_admin.get_config", return_value=mock_config):
        response = openai_command(context, bot_functions)

    bot_functions["set_openai_model"].assert_called_once_with("gpt-4")
    assert "Model set to gpt-4" in response


def test_openai_command_invalid_password(mock_config, bot_functions):
    """Test openai command with invalid password."""
    context = CommandContext(
        command="openai",
        args=["wrongpass", "gpt-4"],
        raw_message="!openai wrongpass gpt-4",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )

    with patch("commands_admin.get_config", return_value=mock_config):
        response = openai_command(context, bot_functions)

    assert response == "❌ Invalid admin password"


def test_openai_command_missing_args(mock_config, bot_functions):
    """Test openai command with missing arguments."""
    context = CommandContext(
        command="openai",
        args=["testpass123"],
        raw_message="!openai testpass123",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )

    with patch("commands_admin.get_config", return_value=mock_config):
        response = openai_command(context, bot_functions)

    assert "Usage:" in response
