#!/usr/bin/env python3
"""
Tamagotchi-related tests.
"""

import os
import tempfile
from unittest.mock import Mock, patch

from dotenv import load_dotenv

# Ensure env vars are loaded for tests that depend on them
load_dotenv()


def test_tamagotchi_toggle_functionality():
    """Test tamagotchi toggle functionality with mock environment."""
    # Create temporary .env file for testing
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write("BOT_NAME=TestBot\nTAMAGOTCHI_ENABLED=true\nUSE_NOTICES=false\n")
        env_file = f.name

    try:
        # Mock all dependencies
        with patch("bot_manager.DataManager") as mock_dm:
            with patch("bot_manager.get_api_key", return_value=None):
                with patch("bot_manager.create_crypto_service", return_value=Mock()):
                    with patch("bot_manager.create_leet_detector", return_value=Mock()):
                        with patch(
                            "bot_manager.create_fmi_warning_service",
                            return_value=Mock(),
                        ):
                            with patch(
                                "bot_manager.create_otiedote_service",
                                return_value=Mock(),
                            ):
                                with patch(
                                    "bot_manager.Lemmatizer",
                                    side_effect=Exception("Mock error"),
                                ):
                                    from bot_manager import BotManager

                                    # Mock data manager methods
                                    mock_dm.return_value.load_tamagotchi_state.return_value = {
                                        "servers": {}
                                    }
                                    mock_dm.return_value.save_tamagotchi_state.return_value = (
                                        None
                                    )
                                    mock_dm.return_value.load_general_words_data.return_value = {
                                        "servers": {}
                                    }
                                    mock_dm.return_value.save_general_words_data.return_value = (
                                        None
                                    )
                                    mock_dm.return_value.load_drink_data.return_value = {
                                        "servers": {}
                                    }
                                    mock_dm.return_value.save_drink_data.return_value = (
                                        None
                                    )

                                    bot_manager = BotManager("TestBot")

                                    # Test initial state
                                    assert hasattr(
                                        bot_manager, "tamagotchi_enabled"
                                    ), "Bot should have tamagotchi_enabled attribute"
                                    assert hasattr(
                                        bot_manager, "toggle_tamagotchi"
                                    ), "Bot should have toggle_tamagotchi method"

                                    # Mock server and response tracking
                                    mock_server = Mock()
                                    mock_server.config.name = "test_server"

                                    responses = []

                                    def mock_send_response(server, target, message):
                                        responses.append(message)

                                    # Mock the message handler's _send_response method
                                    bot_manager.message_handler._send_response = (
                                        mock_send_response
                                    )

                                    # Test toggle command
                                    original_state = bot_manager.tamagotchi_enabled
                                    bot_manager.toggle_tamagotchi(
                                        mock_server, "#test", "testuser"
                                    )

                                    # Should have changed state
                                    assert (
                                        bot_manager.tamagotchi_enabled != original_state
                                    ), "Tamagotchi state should have changed"
                                    assert (
                                        len(responses) > 0
                                    ), "Should have sent a response"
                                    assert (
                                        "Tamagotchi" in responses[0]
                                    ), "Response should mention Tamagotchi"
    finally:
        # Clean up temp file
        if os.path.exists(env_file):
            os.unlink(env_file)
