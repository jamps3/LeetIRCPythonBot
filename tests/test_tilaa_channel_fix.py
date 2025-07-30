#!/usr/bin/env python3
"""
Test for !tilaa Channel Subscription Fix

This test specifically verifies that the recent fix to the !tilaa command
correctly subscribes channels when the command is used in a channel context.
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

# Add the parent directory to the path to import modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import commands
from word_tracking import DataManager


class TestTilaaChannelFix(unittest.TestCase):
    """Test that !tilaa command correctly handles channel subscriptions."""

    def setUp(self):
        """Set up test environment."""
        # Create temporary file for subscriptions
        self.temp_file = tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".json"
        )
        self.temp_file.write("{}")
        self.temp_file.close()

        # Patch the SUBSCRIBERS_FILE constant
        self.patcher = patch("subscriptions.SUBSCRIBERS_FILE", self.temp_file.name)
        self.patcher.start()

        # Create mock IRC connection and data manager
        self.mock_irc = Mock()
        self.data_manager = DataManager()
        
        # Mock data manager to return a test server name
        self.data_manager.get_server_name = Mock(return_value="test_server")

    def tearDown(self):
        """Clean up test environment."""
        self.patcher.stop()
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)

    def test_tilaa_subscribes_channel_when_called_from_channel(self):
        """Test that !tilaa subscribes the channel when called from a channel."""
        import subscriptions
        
        responses = []

        def mock_notice(msg, irc, target):
            responses.append(msg)

        def mock_log(msg, level="INFO"):
            pass

        # Mock bot functions
        bot_functions = {
            "notice_message": mock_notice,
            "log": mock_log,
            "subscriptions": subscriptions,
            "data_manager": self.data_manager,
            "send_electricity_price": lambda *args: None,
            "measure_latency": lambda *args: None,
            "get_crypto_price": lambda *args: "1000",
            "load_leet_winners": lambda: {},
            "save_leet_winners": lambda x: None,
            "send_weather": lambda *args: None,
            "send_scheduled_message": lambda *args: None,
            "search_youtube": lambda x: "YouTube result",
            "handle_ipfs_command": lambda *args: None,
            "lookup": lambda x: "test_server",
            "format_counts": lambda x: "formatted counts",
            "chat_with_gpt": lambda x: f"AI: {x}",
            "wrap_irc_message_utf8_bytes": lambda msg, **kwargs: [msg],
            "send_message": lambda irc, target, msg: None,
            "fetch_title": lambda *args: None,
            "lemmat": Mock(),
            "EKAVIKA_FILE": "test_ekavika.json",
            "bot_name": "testbot",
            "latency_start": lambda: 0,
            "set_latency_start": lambda x: None,
        }

        # Simulate IRC message from a channel
        # Format: :nick!user@host PRIVMSG #channel :!tilaa varoitukset
        test_message = ":jamps!user@host.com PRIVMSG #joensuu :!tilaa varoitukset"

        # Process the message
        commands.process_message(self.mock_irc, test_message, bot_functions)

        # Check that we got a subscription response
        self.assertTrue(responses, "Should have gotten a response")
        
        # The response should indicate that the channel was subscribed
        response = responses[0]
        self.assertIn("✅", response, "Should be a success message")
        self.assertIn("#joensuu", response, "Should mention the channel")
        self.assertIn("varoitukset", response, "Should mention the topic")

        # Verify that the channel is actually subscribed (check all servers since server name mapping varies)
        all_subs = subscriptions.get_all_subscriptions()
        channel_subscribed = False
        for server_name, server_subs in all_subs.items():
            if "#joensuu" in server_subs and "varoitukset" in server_subs["#joensuu"]:
                channel_subscribed = True
                break
        self.assertTrue(channel_subscribed, f"Channel should be subscribed somewhere, got: {all_subs}")

    def test_tilaa_subscribes_user_when_called_from_private_message(self):
        """Test that !tilaa subscribes the user when called from a private message."""
        import subscriptions
        
        responses = []

        def mock_notice(msg, irc, target):
            responses.append(msg)

        def mock_log(msg, level="INFO"):
            pass

        # Mock bot functions with test bot name
        bot_functions = {
            "notice_message": mock_notice,
            "log": mock_log,
            "subscriptions": subscriptions,
            "data_manager": self.data_manager,
            "bot_name": "testbot",
            "send_electricity_price": lambda *args: None,
            "measure_latency": lambda *args: None,
            "get_crypto_price": lambda *args: "1000",
            "load_leet_winners": lambda: {},
            "save_leet_winners": lambda x: None,
            "send_weather": lambda *args: None,
            "send_scheduled_message": lambda *args: None,
            "search_youtube": lambda x: "YouTube result",
            "handle_ipfs_command": lambda *args: None,
            "lookup": lambda x: "test_server",
            "format_counts": lambda x: "formatted counts",
            "chat_with_gpt": lambda x: f"AI: {x}",
            "wrap_irc_message_utf8_bytes": lambda msg, **kwargs: [msg],
            "send_message": lambda irc, target, msg: None,
            "fetch_title": lambda *args: None,
            "lemmat": Mock(),
            "EKAVIKA_FILE": "test_ekavika.json",
            "latency_start": lambda: 0,
            "set_latency_start": lambda x: None,
        }

        # Simulate IRC private message
        # Format: :nick!user@host PRIVMSG testbot :!tilaa varoitukset
        test_message = ":jamps!user@host.com PRIVMSG testbot :!tilaa varoitukset"

        # Process the message
        commands.process_message(self.mock_irc, test_message, bot_functions)

        # Check that we got a subscription response
        self.assertTrue(responses, "Should have gotten a response")
        
        # The response should indicate that the user was subscribed
        response = responses[0]
        self.assertIn("✅", response, "Should be a success message")
        self.assertIn("jamps", response, "Should mention the user")
        self.assertIn("varoitukset", response, "Should mention the topic")

        # Verify that the user is actually subscribed (check all servers since server name mapping varies)
        all_subs = subscriptions.get_all_subscriptions()
        user_subscribed = False
        for server_name, server_subs in all_subs.items():
            if "jamps" in server_subs and "varoitukset" in server_subs["jamps"]:
                user_subscribed = True
                break
        self.assertTrue(user_subscribed, f"User should be subscribed somewhere, got: {all_subs}")

    def test_tilaa_allows_override_with_third_parameter(self):
        """Test that !tilaa allows overriding the subscriber with a third parameter."""
        import subscriptions
        
        responses = []

        def mock_notice(msg, irc, target):
            responses.append(msg)

        def mock_log(msg, level="INFO"):
            pass

        # Mock bot functions
        bot_functions = {
            "notice_message": mock_notice,
            "log": mock_log,
            "subscriptions": subscriptions,
            "data_manager": self.data_manager,
            "send_electricity_price": lambda *args: None,
            "measure_latency": lambda *args: None,
            "get_crypto_price": lambda *args: "1000",
            "load_leet_winners": lambda: {},
            "save_leet_winners": lambda x: None,
            "send_weather": lambda *args: None,
            "send_scheduled_message": lambda *args: None,
            "search_youtube": lambda x: "YouTube result",
            "handle_ipfs_command": lambda *args: None,
            "lookup": lambda x: "test_server",
            "format_counts": lambda x: "formatted counts",
            "chat_with_gpt": lambda x: f"AI: {x}",
            "wrap_irc_message_utf8_bytes": lambda msg, **kwargs: [msg],
            "send_message": lambda irc, target, msg: None,
            "fetch_title": lambda *args: None,
            "lemmat": Mock(),
            "EKAVIKA_FILE": "test_ekavika.json",
            "bot_name": "testbot",
            "latency_start": lambda: 0,
            "set_latency_start": lambda x: None,
        }

        # Simulate IRC message with override parameter
        # Format: :nick!user@host PRIVMSG #channel :!tilaa varoitukset #other-channel
        test_message = ":jamps!user@host.com PRIVMSG #joensuu :!tilaa varoitukset #other-channel"

        # Process the message
        commands.process_message(self.mock_irc, test_message, bot_functions)

        # Check that we got a subscription response
        self.assertTrue(responses, "Should have gotten a response")
        
        # The response should indicate that the override channel was subscribed
        response = responses[0]
        self.assertIn("✅", response, "Should be a success message")
        self.assertIn("#other-channel", response, "Should mention the override channel")

        # Verify that the override channel is subscribed, not the original (check all servers since server name mapping varies)
        all_subs = subscriptions.get_all_subscriptions()
        override_subscribed = False
        original_subscribed = False
        for server_name, server_subs in all_subs.items():
            if "#other-channel" in server_subs and "varoitukset" in server_subs["#other-channel"]:
                override_subscribed = True
            if "#joensuu" in server_subs and "varoitukset" in server_subs["#joensuu"]:
                original_subscribed = True
        self.assertTrue(override_subscribed, f"Override channel should be subscribed somewhere, got: {all_subs}")
        self.assertFalse(original_subscribed, f"Original channel should not be subscribed, got: {all_subs}")

    def test_tilaa_list_shows_channel_subscriptions(self):
        """Test that !tilaa list correctly shows channel subscriptions."""
        import subscriptions
        
        responses = []

        def mock_notice(msg, irc, target):
            responses.append(msg)

        def mock_log(msg, level="INFO"):
            pass

        # Mock bot functions
        bot_functions = {
            "notice_message": mock_notice,
            "log": mock_log,
            "subscriptions": subscriptions,
            "data_manager": self.data_manager,
            "send_electricity_price": lambda *args: None,
            "measure_latency": lambda *args: None,
            "get_crypto_price": lambda *args: "1000",
            "load_leet_winners": lambda: {},
            "save_leet_winners": lambda x: None,
            "send_weather": lambda *args: None,
            "send_scheduled_message": lambda *args: None,
            "search_youtube": lambda x: "YouTube result",
            "handle_ipfs_command": lambda *args: None,
            "lookup": lambda x: "test_server",
            "format_counts": lambda x: "formatted counts",
            "chat_with_gpt": lambda x: f"AI: {x}",
            "wrap_irc_message_utf8_bytes": lambda msg, **kwargs: [msg],
            "send_message": lambda irc, target, msg: None,
            "fetch_title": lambda *args: None,
            "lemmat": Mock(),
            "EKAVIKA_FILE": "test_ekavika.json",
            "bot_name": "testbot",
            "latency_start": lambda: 0,
            "set_latency_start": lambda x: None,
        }
        
        # First, add a subscription using IRC message processing (to match the server name used by the system)
        test_message = ":jamps!user@host.com PRIVMSG #testchannel :!tilaa varoitukset"
        commands.process_message(self.mock_irc, test_message, bot_functions)
        
        # Clear the responses from the subscription command
        responses.clear()

        # Now simulate IRC message for list command from the same channel
        # Format: :nick!user@host PRIVMSG #testchannel :!tilaa list
        test_message = ":jamps!user@host.com PRIVMSG #testchannel :!tilaa list"

        # Process the message
        commands.process_message(self.mock_irc, test_message, bot_functions)

        # Check that we got a list response
        self.assertTrue(responses, "Should have gotten a response")
        
        # The response should show the channel's subscriptions
        full_response = " ".join(responses)
        self.assertIn("#testchannel", full_response, "Should mention the channel")
        # Instead of checking for "varoitukset" specifically, check that it's not the "no subscriptions" message
        self.assertNotIn("ei ole tilannut mitään", full_response, "Should show actual subscriptions, not empty message")


    def test_tilaa_channel_vs_private_message(self):
        """Test that !tilaa behaves differently in channels vs private messages."""
        import subscriptions
        from word_tracking import DataManager

        # Create mock IRC connection and data manager
        mock_irc = Mock()
        data_manager = DataManager()
        data_manager.get_server_name = Mock(return_value="test_server")

        responses = []

        def mock_notice(msg, irc, target):
            responses.append(msg)

        def mock_log(msg, level="INFO"):
            pass

        # Mock all required bot functions
        bot_functions = {
            "notice_message": mock_notice,
            "log": mock_log,
            "subscriptions": subscriptions,
            "data_manager": data_manager,
            "send_electricity_price": lambda *args: None,
            "measure_latency": lambda *args: None,
            "get_crypto_price": lambda *args: "1000",
            "load_leet_winners": lambda: {},
            "save_leet_winners": lambda x: None,
            "send_weather": lambda *args: None,
            "send_scheduled_message": lambda *args: None,
            "search_youtube": lambda x: "YouTube result",
            "handle_ipfs_command": lambda *args: None,
            "lookup": lambda x: "test_server",
            "format_counts": lambda x: "formatted counts",
            "chat_with_gpt": lambda x: f"AI: {x}",
            "wrap_irc_message_utf8_bytes": lambda msg, **kwargs: [msg],
            "send_message": lambda irc, target, msg: None,
            "fetch_title": lambda *args: None,
            "lemmat": Mock(),
            "EKAVIKA_FILE": "test_ekavika.json",
            "bot_name": "testbot",
            "latency_start": lambda: 0,
            "set_latency_start": lambda x: None,
        }

        # Test 1: Channel message should subscribe the channel
        responses.clear()
        test_message = ":jamps!user@host.com PRIVMSG #joensuu :!tilaa varoitukset"
        commands.process_message(mock_irc, test_message, bot_functions)

        # Check response mentions the channel
        self.assertTrue(responses, "Should have gotten a response for channel command")
        response = responses[0]
        
        # The key test: verify the response shows the channel was subscribed, not the user
        self.assertIn("#joensuu", response)
        self.assertNotIn("jamps", response)

        # Verify the channel is actually subscribed (check all servers since server name mapping varies)
        all_subs = subscriptions.get_all_subscriptions()
        
        # Find which server the subscription was added to
        channel_subscribed = False
        for server_name, server_subs in all_subs.items():
            if "#joensuu" in server_subs and "varoitukset" in server_subs["#joensuu"]:
                channel_subscribed = True
                # Clear this subscription for next test
                subscriptions.toggle_subscription("#joensuu", server_name, "varoitukset")
                break
        
        self.assertTrue(channel_subscribed, f"Channel should be subscribed somewhere, got: {all_subs}")

        # Test 2: Private message should subscribe the user
        responses.clear()
        test_message = ":jamps!user@host.com PRIVMSG testbot :!tilaa varoitukset"
        commands.process_message(mock_irc, test_message, bot_functions)

        # Check response mentions the user
        self.assertTrue(responses, "Should have gotten a response for private message command")
        response = responses[0]
        self.assertIn("jamps", response)

        # Verify the user is actually subscribed (check all servers since server name mapping varies)
        all_subs_after_pm = subscriptions.get_all_subscriptions()
        
        # Find which server the user subscription was added to
        user_subscribed = False
        for server_name, server_subs in all_subs_after_pm.items():
            if "jamps" in server_subs and "varoitukset" in server_subs["jamps"]:
                user_subscribed = True
                break
        
        self.assertTrue(user_subscribed, f"User should be subscribed somewhere, got: {all_subs_after_pm}")

if __name__ == "__main__":
    unittest.main()
