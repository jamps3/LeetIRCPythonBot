#!/usr/bin/env python3
"""
Test script for new features: Scheduled Messages, IPFS, and Eurojackpot
"""

import unittest
import time
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock


class TestScheduledMessages(unittest.TestCase):
    """Test scheduled message functionality."""

    def setUp(self):
        # Reset global service instance
        import services.scheduled_message_service

        services.scheduled_message_service._scheduled_message_service = None

    def test_schedule_message(self):
        """Test scheduling a message."""
        from services.scheduled_message_service import get_scheduled_message_service

        service = get_scheduled_message_service()
        mock_irc = Mock()

        # Schedule message for 1 second in the future
        now = datetime.now()
        target_time = now.replace(
            hour=now.hour,
            minute=now.minute,
            second=(now.second + 2) % 60,
            microsecond=0,
        )

        message_id = service.schedule_message(
            mock_irc,
            "#test",
            "Test message",
            target_time.hour,
            target_time.minute,
            target_time.second,
            0,
        )

        self.assertIsInstance(message_id, str)
        self.assertIn("scheduled_", message_id)

        # Verify message is in the scheduled list
        scheduled = service.list_scheduled_messages()
        self.assertIn(message_id, scheduled)
        self.assertEqual(scheduled[message_id]["message"], "Test message")
        self.assertEqual(scheduled[message_id]["channel"], "#test")

    def test_cancel_message(self):
        """Test cancelling a scheduled message."""
        from services.scheduled_message_service import get_scheduled_message_service

        service = get_scheduled_message_service()
        mock_irc = Mock()

        # Schedule a message far in the future
        message_id = service.schedule_message(
            mock_irc, "#test", "Test message", 23, 59, 59, 0
        )

        # Verify it exists
        scheduled = service.list_scheduled_messages()
        self.assertIn(message_id, scheduled)

        # Cancel it
        result = service.cancel_message(message_id)
        self.assertTrue(result)

        # Verify it's gone
        scheduled = service.list_scheduled_messages()
        self.assertNotIn(message_id, scheduled)

    def test_convenience_function(self):
        """Test the convenience function for scheduling."""
        from services.scheduled_message_service import send_scheduled_message

        mock_irc = Mock()

        message_id = send_scheduled_message(
            mock_irc, "#test", "Convenience test", 23, 59, 58, 123456
        )

        self.assertIsInstance(message_id, str)


class TestIPFSService(unittest.TestCase):
    """Test IPFS functionality."""

    def setUp(self):
        # Reset global service instance
        import services.ipfs_service

        services.ipfs_service._ipfs_service = None

    @patch("subprocess.run")
    def test_ipfs_availability_check(self, mock_run):
        """Test IPFS availability checking."""
        from services.ipfs_service import IPFSService

        # Test when IPFS is available
        mock_run.return_value.returncode = 0
        service = IPFSService()
        self.assertTrue(service.ipfs_available)

        # Test when IPFS is not available
        mock_run.side_effect = FileNotFoundError()
        service2 = IPFSService()
        self.assertFalse(service2.ipfs_available)

    @patch("requests.head")
    @patch("requests.get")
    def test_download_file_size_check(self, mock_get, mock_head):
        """Test file size checking during download."""
        from services.ipfs_service import IPFSService

        service = IPFSService()
        service.ipfs_available = True  # Mock as available

        # Test file too large
        mock_head.return_value.headers = {"content-length": "200000000"}  # 200MB

        temp_file, error, size = service._download_file(
            "http://example.com/large.file", 100000000
        )  # 100MB limit

        self.assertIsNone(temp_file)
        self.assertIn("too large", error)
        self.assertEqual(size, 200000000)

    def test_handle_ipfs_command(self):
        """Test IPFS command handling."""
        from services.ipfs_service import handle_ipfs_command

        # Test invalid command format
        result = handle_ipfs_command("!ipfs")
        self.assertIn("Usage", result)

        # Test add command without URL
        result = handle_ipfs_command("!ipfs add")
        self.assertIn("Usage", result)


class TestEurojackpotService(unittest.TestCase):
    """Test Eurojackpot functionality."""

    def setUp(self):
        # Reset global service instance
        import services.eurojackpot_service

        services.eurojackpot_service._eurojackpot_service = None

    @patch("requests.get")
    def test_next_draw_info(self, mock_get):
        """Test getting next draw information."""
        from services.eurojackpot_service import EurojackpotService

        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "drawTime": "2024-03-15T19:00:00Z",
            "jackpot": {"amount": 15000000, "currency": "EUR"},
        }
        mock_get.return_value = mock_response

        service = EurojackpotService()
        result = service.get_next_draw_info()

        self.assertTrue(result["success"])
        self.assertIn("Seuraava Eurojackpot", result["message"])
        self.assertIn("15.0 miljoonaa EUR", result["message"])

    @patch("requests.get")
    def test_last_results(self, mock_get):
        """Test getting last draw results."""
        from services.eurojackpot_service import EurojackpotService

        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "drawTime": "2024-03-12T19:00:00Z",
            "results": {"primary": [7, 14, 21, 28, 35], "secondary": [3, 8]},
            "prizeBreakdown": [{"prizeRank": 1, "winners": 2}],
        }
        mock_get.return_value = mock_response

        service = EurojackpotService()
        result = service.get_last_results()

        self.assertTrue(result["success"])
        self.assertIn("Viimeisin Eurojackpot", result["message"])
        self.assertIn("07 - 14 - 21 - 28 - 35 + 03 - 08", result["message"])
        self.assertIn("2 jackpot-voittajaa", result["message"])

    def test_convenience_functions(self):
        """Test convenience functions for Eurojackpot."""
        from services.eurojackpot_service import (
            get_eurojackpot_numbers,
            get_eurojackpot_results,
        )

        # These should not crash even without API responses
        try:
            numbers_result = get_eurojackpot_numbers()
            self.assertIsInstance(numbers_result, str)

            results_result = get_eurojackpot_results()
            self.assertIsInstance(results_result, str)
        except Exception as e:
            # Expected if no network or API issues
            self.assertIn("Error", str(e))


class TestExtendedCommands(unittest.TestCase):
    """Test the extended command implementations."""

    def test_command_registration(self):
        """Test that extended commands are registered."""
        from command_registry import get_command_registry

        # Import extended commands to register them
        import commands_extended

        registry = get_command_registry()

        # Check that our new commands are registered
        self.assertIn("schedule", registry._commands)
        self.assertIn("ipfs", registry._commands)
        self.assertIn("eurojackpot", registry._commands)
        self.assertIn("scheduled", registry._commands)

    def test_schedule_command_parsing(self):
        """Test schedule command argument parsing."""
        from commands_extended import command_schedule

        # Test invalid format
        context = {"server": Mock()}
        result = command_schedule(context, [])
        self.assertIn("Usage", result)

        # Test invalid format 2
        result = command_schedule(context, ["invalid", "format"])
        self.assertIn("Invalid format", result)

    def test_eurojackpot_command(self):
        """Test Eurojackpot command."""
        from commands_extended import command_eurojackpot

        context = {}

        # Test default (next draw)
        try:
            result = command_eurojackpot(context, [])
            self.assertIsInstance(result, str)
        except Exception as e:
            # Expected if no network access
            self.assertIn("Error", str(e))

        # Test results request
        try:
            result = command_eurojackpot(context, ["tulokset"])
            self.assertIsInstance(result, str)
        except Exception as e:
            # Expected if no network access
            self.assertIn("Error", str(e))


class TestIntegration(unittest.TestCase):
    """Test integration between services and commands."""

    def test_command_loader_import(self):
        """Test that command_loader can import extended commands."""
        try:
            from command_loader import load_all_commands

            result = load_all_commands()
            # Should not crash
        except ImportError as e:
            self.fail(f"Failed to import extended commands: {e}")

    def test_bot_manager_integration(self):
        """Test bot manager can access new service methods."""
        from bot_manager import BotManager

        # Create mock bot manager instance
        bot = BotManager("TestBot")

        # Test that new methods exist
        self.assertTrue(hasattr(bot, "_send_scheduled_message"))
        self.assertTrue(hasattr(bot, "_get_eurojackpot_numbers"))
        self.assertTrue(hasattr(bot, "_get_eurojackpot_results"))
        self.assertTrue(hasattr(bot, "_handle_ipfs_command"))


def run_tests():
    """Run all tests with detailed output."""
    import sys

    # Create test suite
    test_classes = [
        TestScheduledMessages,
        TestIPFSService,
        TestEurojackpotService,
        TestExtendedCommands,
        TestIntegration,
    ]

    suite = unittest.TestSuite()
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)

    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)

    # Print summary
    print("\n" + "=" * 60)
    print("🧪 NEW FEATURES TEST SUMMARY")
    print("=" * 60)

    if result.wasSuccessful():
        print(f"✅ All {result.testsRun} tests passed!")
        print("\n🎉 NEW FEATURES READY:")
        print("  1. ⏰ Scheduled Messages - Microsecond precision message scheduling")
        print(
            "  2. 📁 IPFS Integration - File sharing with size limits and admin override"
        )
        print("  3. 🎰 Eurojackpot Info - Next draw and last results")
        print("  4. 🛠️  Extended Commands - New command registry integration")
    else:
        print(
            f"❌ {len(result.failures)} failures, {len(result.errors)} errors out of {result.testsRun} tests"
        )

        if result.failures:
            print("\nFailures:")
            for test, traceback in result.failures:
                print(
                    f"  - {test}: {traceback.split('AssertionError: ')[-1].split('\\n')[0]}"
                )

        if result.errors:
            print("\nErrors:")
            for test, traceback in result.errors:
                print(f"  - {test}: {traceback.split('\\n')[-2]}")

    print("=" * 60)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
