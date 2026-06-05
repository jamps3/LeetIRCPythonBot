#!/usr/bin/env python3
"""
Tests for the !otiedote command.
"""

import os
import sys
from unittest.mock import Mock, patch

import pytest

# Add src to path before importing project modules
_TEST_ROOT = os.path.dirname(os.path.abspath(__file__))
if _TEST_ROOT not in sys.path:
    sys.path.insert(0, os.path.join(_TEST_ROOT, "..", "src"))

from command_registry import CommandContext


@pytest.fixture
def mock_bot_functions():
    """Create mock bot functions for testing commands."""
    return {
        "log": Mock(),
        "notice_message": Mock(),
        "send_weather": Mock(),
        "send_electricity_price": Mock(),
        "send_youtube_info": Mock(),
        "send_imdb_info": Mock(),
        "get_crypto_price": Mock(),
        "load_leet_winners": Mock(),
        "get_alko_product": Mock(),
        "check_drug_interactions": Mock(),
        "server": Mock(),
        "bot_manager": Mock(),
    }


@pytest.fixture
def console_context():
    """Create a mock CommandContext for console commands."""
    return CommandContext(
        command="test",
        args=[],
        raw_message="!test",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )


class TestOtiedoteCommand:
    """Tests for the !otiedote command."""

    def test_otiedote_command_latest(self, console_context, mock_bot_functions):
        """Test otiedote command to show latest release."""
        from cmd_modules.services import otiedote_command

        # Mock the otiedote service
        with (
            patch("cmd_modules.services.create_otiedote_service") as mock_service_class,
            patch("cmd_modules.services.get_config") as mock_get_config,
        ):
            mock_config = Mock()
            mock_get_config.return_value = mock_config

            mock_service = Mock()
            mock_service_class.return_value = mock_service

            # Mock load_otiedote_data to return test data
            mock_service.load_otiedote_data.return_value = [
                {
                    "id": 1,
                    "title": "Test Otiedote",
                    "content": "This is a test otiedote content",
                    "url": "https://example.com/otiedote/1",
                }
            ]

            result = otiedote_command(console_context, mock_bot_functions)

            assert "Test Otiedote" in result
            assert "This is a test otiedote content" in result
            assert "https://example.com/otiedote/1" in result

    def test_otiedote_command_specific_number(
        self, console_context, mock_bot_functions
    ):
        """Test otiedote command with specific release number."""
        from cmd_modules.services import otiedote_command

        # Create context with arguments
        console_context.args_text = "#5"
        console_context.args = ["#5"]

        # Mock the otiedote service
        with (
            patch("cmd_modules.services.create_otiedote_service") as mock_service_class,
            patch("cmd_modules.services.get_config") as mock_get_config,
        ):
            mock_config = Mock()
            mock_get_config.return_value = mock_config

            mock_service = Mock()
            mock_service_class.return_value = mock_service

            # Mock load_otiedote_data to return test data
            mock_service.load_otiedote_data.return_value = [
                {
                    "id": 5,
                    "title": "Test Otiedote #5",
                    "content": "This is test otiedote content for release 5",
                    "url": "https://example.com/otiedote/5",
                }
            ]

            result = otiedote_command(console_context, mock_bot_functions)

            assert "Test Otiedote #5" in result
            assert "This is test otiedote content for release 5" in result
            assert "https://example.com/otiedote/5" in result

    def test_otiedote_command_no_data(self, console_context, mock_bot_functions):
        """Test otiedote command when no data is available."""
        from cmd_modules.services import otiedote_command

        # Mock the otiedote service
        with (
            patch("cmd_modules.services.create_otiedote_service") as mock_service_class,
            patch("cmd_modules.services.get_config") as mock_get_config,
        ):
            mock_config = Mock()
            mock_get_config.return_value = mock_config

            mock_service = Mock()
            mock_service_class.return_value = mock_service

            # Mock load_otiedote_data to return empty list
            mock_service.load_otiedote_data.return_value = []

            result = otiedote_command(console_context, mock_bot_functions)

            assert "No otiedote data available" in result

    def test_otiedote_attempts_shows_current_value(
        self, console_context, mock_bot_functions
    ):
        """Test showing configured not-found attempts."""
        from cmd_modules.services import otiedote_command

        console_context.args_text = "attempts"
        console_context.args = ["attempts"]

        with (
            patch("cmd_modules.services.create_otiedote_service") as mock_service_class,
            patch("cmd_modules.services.get_config") as mock_get_config,
        ):
            mock_get_config.return_value = Mock(state_file="state.json")
            mock_service = Mock()
            mock_service.load_otiedote_data.return_value = []
            mock_service.get_not_found_attempts.return_value = 2
            mock_service_class.return_value = mock_service

            result = otiedote_command(console_context, mock_bot_functions)

        assert result == "📋 Otiedote not-found attempts: 2"
        mock_service.fetch_next_release.assert_not_called()

    def test_otiedote_attempts_sets_value(self, console_context, mock_bot_functions):
        """Test setting configured not-found attempts."""
        from cmd_modules.services import otiedote_command

        console_context.args_text = "attempts 4"
        console_context.args = ["attempts", "4"]

        with (
            patch("cmd_modules.services.create_otiedote_service") as mock_service_class,
            patch("cmd_modules.services.get_config") as mock_get_config,
        ):
            mock_get_config.return_value = Mock(state_file="state.json")
            mock_service = Mock()
            mock_service.load_otiedote_data.return_value = []
            mock_service.get_not_found_attempts.return_value = 2
            mock_service_class.return_value = mock_service

            result = otiedote_command(console_context, mock_bot_functions)

        assert result == "✅ Otiedote not-found attempts set to 4 (was 2)"
        mock_service.set_not_found_attempts.assert_called_once_with(4)
        mock_service.fetch_next_release.assert_not_called()

    def test_otiedote_attempts_rejects_invalid_value(
        self, console_context, mock_bot_functions
    ):
        """Test invalid not-found attempt values."""
        from cmd_modules.services import otiedote_command

        console_context.args_text = "attempts 0"
        console_context.args = ["attempts", "0"]

        with (
            patch("cmd_modules.services.create_otiedote_service") as mock_service_class,
            patch("cmd_modules.services.get_config") as mock_get_config,
        ):
            mock_get_config.return_value = Mock(state_file="state.json")
            mock_service = Mock()
            mock_service.load_otiedote_data.return_value = []
            mock_service_class.return_value = mock_service

            result = otiedote_command(console_context, mock_bot_functions)

        assert result == "❌ Attempts must be at least 1"
        mock_service.set_not_found_attempts.assert_not_called()
        mock_service.fetch_next_release.assert_not_called()
