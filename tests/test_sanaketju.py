#!/usr/bin/env python3
"""
Sanaketju Game Tests

Tests for the sanaketju word chain game functionality.
"""

from unittest.mock import Mock, patch

import pytest

from command_registry import CommandContext
from commands import get_sanaketju_game, sanaketju_command
from word_tracking.data_manager import DataManager


@pytest.fixture
def mock_data_manager():
    """Create a mock data manager."""
    dm = Mock(spec=DataManager)
    dm.load_sanaketju_state.return_value = {}
    dm.save_sanaketju_state = Mock()
    return dm


@pytest.fixture
def mock_bot_functions(mock_data_manager):
    """Create bot functions dictionary."""
    return {
        "data_manager": mock_data_manager,
    }


def test_sanaketju_start_command(mock_bot_functions, mock_data_manager):
    """Test starting a sanaketju game."""
    context = CommandContext(
        command="sanaketju",
        args=["start"],
        raw_message="!sanaketju start",
        sender="testuser",
        target="#testchannel",
        is_private=False,
        is_console=False,
        server_name="testserver",
    )

    with patch("commands.get_sanaketju_game") as mock_get_game:
        mock_game = Mock()
        mock_game._load_state = Mock()  # Mock the _load_state method
        mock_game.active = False  # Mock game not active
        mock_game.start_game.return_value = "testword"
        mock_get_game.return_value = mock_game

        response = sanaketju_command(context, mock_bot_functions)

        mock_game.start_game.assert_called_once_with("#testchannel", mock_data_manager)
        assert "testword" in response


def test_sanaketju_status_command(mock_bot_functions):
    """Test getting sanaketju game status."""
    context = CommandContext(
        command="sanaketju",
        args=[],  # No args means show status
        raw_message="!sanaketju",
        sender="testuser",
        target="#testchannel",
        is_private=False,
        is_console=False,
        server_name="testserver",
    )

    with patch("commands.get_sanaketju_game") as mock_get_game:
        mock_game = Mock()
        mock_game.get_status.return_value = "Game status"
        mock_get_game.return_value = mock_game

        response = sanaketju_command(context, mock_bot_functions)

        mock_game.get_status.assert_called_once()
        assert response == "Game status"


def test_sanaketju_stop_command(mock_bot_functions, mock_data_manager):
    """Test stopping a sanaketju game."""
    context = CommandContext(
        command="sanaketju",
        args=["stop"],
        raw_message="!sanaketju stop",
        sender="testuser",
        target="#testchannel",
        is_private=False,
        is_console=False,
        server_name="testserver",
    )

    with patch("commands.get_sanaketju_game") as mock_get_game:
        mock_game = Mock()
        mock_game.end_game.return_value = "Game ended"
        mock_get_game.return_value = mock_game

        response = sanaketju_command(context, mock_bot_functions)

        mock_game.end_game.assert_called_once_with(mock_data_manager)
        assert response == "Game ended"


def test_sanaketju_ignore_command(mock_bot_functions):
    """Test ignoring sanaketju notices."""
    context = CommandContext(
        command="sanaketju",
        args=["ignore"],
        raw_message="!sanaketju ignore",
        sender="testuser",
        target="#testchannel",
        is_private=False,
        is_console=False,
        server_name="testserver",
    )

    with patch("commands.get_sanaketju_game") as mock_get_game:
        mock_game = Mock()
        mock_game.toggle_ignore.return_value = True  # Now ignored
        mock_get_game.return_value = mock_game

        response = sanaketju_command(context, mock_bot_functions)

        mock_game.toggle_ignore.assert_called_once_with("testuser", None)
        assert "ei enää saa sanaketju-ilmoituksia" in response


def test_sanaketju_ignore_other_command(mock_bot_functions):
    """Test ignoring another user from sanaketju notices."""
    context = CommandContext(
        command="sanaketju",
        args=["ignore", "otheruser"],
        raw_message="!sanaketju ignore otheruser",
        sender="testuser",
        target="#testchannel",
        is_private=False,
        is_console=False,
        server_name="testserver",
    )

    with patch("commands.get_sanaketju_game") as mock_get_game:
        mock_game = Mock()
        mock_game.toggle_ignore.return_value = True  # Now ignored
        mock_get_game.return_value = mock_game

        response = sanaketju_command(context, mock_bot_functions)

        mock_game.toggle_ignore.assert_called_once_with("testuser", "otheruser")
        assert "ei enää saa sanaketju-ilmoituksia" in response


def test_sanaketju_invalid_command(mock_bot_functions):
    """Test invalid sanaketju command."""
    context = CommandContext(
        command="sanaketju",
        args=["invalid"],
        raw_message="!sanaketju invalid",
        sender="testuser",
        target="#testchannel",
        is_private=False,
        is_console=False,
        server_name="testserver",
    )

    response = sanaketju_command(context, mock_bot_functions)

    assert "Tuntematon komento" in response
