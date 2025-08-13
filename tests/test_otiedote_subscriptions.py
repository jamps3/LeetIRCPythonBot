#!/usr/bin/env python3
"""
Tests for Otiedote delivery ensuring it uses subscriptions (onnettomuustiedotteet)
rather than broadcasting to all configured channels.
"""

import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from bot_manager import BotManager


class TestOtiedoteSubscriptions(unittest.TestCase):
    def setUp(self):
        # Minimal env to avoid external service initialization side effects
        os.environ.setdefault("USE_NOTICES", "false")

        # Create BotManager with one server configured via environment
        # Simulate one server in config by patching get_server_configs
        self.server_name = "test_server"

        server_config_mock = Mock()
        server_config_mock.name = self.server_name
        server_config_mock.host = "localhost"
        server_config_mock.port = 6667
        server_config_mock.channels = ["#general", "#random"]

        # Create a fake Server with send_message/notice capturing
        self.fake_server = Mock()
        self.fake_server.config.name = self.server_name
        self.sent_messages = []

        def capture_send_message(target, message):
            self.sent_messages.append((target, message))

        def capture_send_notice(target, message):
            self.sent_messages.append((target, message))

        self.fake_server.send_message.side_effect = capture_send_message
        self.fake_server.send_notice.side_effect = capture_send_notice

        # Patch BotManager dependencies to control environment
        patches = [
            patch("config.get_server_configs", return_value=[server_config_mock]),
            patch(
                "services.electricity_service.create_electricity_service",
                side_effect=ImportError("skip"),
            ),
            patch("services.gpt_service.GPTService", side_effect=ImportError("skip")),
            patch(
                "services.youtube_service.create_youtube_service",
                side_effect=ImportError("skip"),
            ),
            patch(
                "services.fmi_warning_service.create_fmi_warning_service",
                side_effect=ImportError("skip"),
            ),
            patch(
                "services.crypto_service.create_crypto_service",
                side_effect=ImportError("skip"),
            ),
        ]
        self._patchers = [p.start() for p in patches]
        self.addCleanup(lambda: [p.stop() for p in patches])

        # Build BotManager and inject our server
        self.manager = BotManager("TestBot")
        self.manager.servers = {self.server_name: self.fake_server}

    def test_otiedote_sends_only_to_subscribers(self):
        # Mock subscriptions to return explicit onnettomuustiedotteet subscribers
        mock_subscriptions = Mock()
        mock_subscriptions.get_subscribers.return_value = [
            ("#general", self.server_name),
            ("user1", self.server_name),
        ]

        with patch.object(
            self.manager, "_get_subscriptions_module", return_value=mock_subscriptions
        ):
            # Trigger Otiedote release
            self.manager._handle_otiedote_release("Test Title", "https://example.com")

        # Verify messages sent only to listed subscribers
        targets = [t for (t, _msg) in self.sent_messages]
        assert "#general" in targets
        assert "user1" in targets
        # Should NOT send to other configured channels like #random by broadcast
        assert "#random" not in targets

    def test_otiedote_no_subscribers_sends_nothing(self):
        mock_subscriptions = Mock()
        mock_subscriptions.get_subscribers.return_value = []

        with patch.object(
            self.manager, "_get_subscriptions_module", return_value=mock_subscriptions
        ):
            # Trigger Otiedote release
            self.manager._handle_otiedote_release("Test Title", "https://example.com")

        # Nothing should be sent
        assert self.sent_messages == []


if __name__ == "__main__":
    unittest.main()
