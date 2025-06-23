#!/usr/bin/env python3
"""
New Features Test Suite

Tests for new bot features including scheduled messages, IPFS integration,
and enhanced Eurojackpot functionality.
"""

import os
import sys
import time
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

# Add the parent directory to sys.path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

from test_framework import TestCase, TestSuite

# Load environment variables for testing
load_dotenv()


def test_scheduled_message_creation():
    """Test scheduled message service creation and basic functionality."""
    try:
        # Reset global service instance
        import services.scheduled_message_service
        from services.scheduled_message_service import get_scheduled_message_service

        services.scheduled_message_service._scheduled_message_service = None

        service = get_scheduled_message_service()
        mock_irc = Mock()

        # Schedule message for far future
        message_id = service.schedule_message(
            mock_irc, "#test", "Test message", 23, 59, 59, 0
        )

        # Should return valid message ID
        if not isinstance(message_id, str) or "scheduled_" not in message_id:
            return False

        # Verify message is in the scheduled list
        scheduled = service.list_scheduled_messages()
        if message_id not in scheduled:
            return False

        if scheduled[message_id]["message"] != "Test message":
            return False

        if scheduled[message_id]["channel"] != "#test":
            return False

        return True

    except Exception as e:
        print(f"Scheduled message creation test failed: {e}")
        return False


def test_scheduled_message_cancellation():
    """Test scheduled message cancellation."""
    try:
        # Reset global service instance
        import services.scheduled_message_service
        from services.scheduled_message_service import get_scheduled_message_service

        services.scheduled_message_service._scheduled_message_service = None

        service = get_scheduled_message_service()
        mock_irc = Mock()

        # Schedule a message far in the future
        message_id = service.schedule_message(
            mock_irc, "#test", "Test message", 23, 59, 58, 0
        )

        # Verify it exists
        scheduled = service.list_scheduled_messages()
        if message_id not in scheduled:
            return False

        # Cancel it
        result = service.cancel_message(message_id)
        if not result:
            return False

        # Verify it's gone
        scheduled = service.list_scheduled_messages()
        if message_id in scheduled:
            return False

        return True

    except Exception as e:
        print(f"Scheduled message cancellation test failed: {e}")
        return False


def test_scheduled_message_convenience_function():
    """Test the convenience function for scheduling messages."""
    try:
        # Reset global service instance
        import services.scheduled_message_service
        from services.scheduled_message_service import send_scheduled_message

        services.scheduled_message_service._scheduled_message_service = None

        mock_irc = Mock()

        message_id = send_scheduled_message(
            mock_irc, "#test", "Convenience test", 23, 59, 57, 123456
        )

        if not isinstance(message_id, str):
            return False

        return True

    except Exception as e:
        print(f"Scheduled message convenience function test failed: {e}")
        return False


@patch("subprocess.run")
def test_ipfs_availability_check(mock_run):
    """Test IPFS availability checking."""
    try:
        # Reset global service instance
        import services.ipfs_service
        from services.ipfs_service import IPFSService

        services.ipfs_service._ipfs_service = None

        # Test when IPFS is available
        mock_run.return_value.returncode = 0
        service = IPFSService()
        if not service.ipfs_available:
            return False

        # Test when IPFS is not available
        mock_run.side_effect = FileNotFoundError()
        service2 = IPFSService()
        if service2.ipfs_available:
            return False

        return True

    except Exception as e:
        print(f"IPFS availability check test failed: {e}")
        return False


@patch("requests.head")
@patch("requests.get")
def test_ipfs_file_size_check(mock_get, mock_head):
    """Test IPFS file size checking during download."""
    try:
        # Reset global service instance
        import services.ipfs_service
        from services.ipfs_service import IPFSService

        services.ipfs_service._ipfs_service = None

        service = IPFSService()
        service.ipfs_available = True  # Mock as available

        # Test file too large
        mock_head.return_value.headers = {"content-length": "200000000"}  # 200MB

        temp_file, error, size = service._download_file(
            "http://example.com/large.file", 100000000
        )  # 100MB limit

        if temp_file is not None:
            return False

        if "too large" not in error:
            return False

        if size != 200000000:
            return False

        return True

    except Exception as e:
        print(f"IPFS file size check test failed: {e}")
        return False


def test_ipfs_command_handling():
    """Test IPFS command handling."""
    try:
        # Reset global service instance
        import services.ipfs_service
        from services.ipfs_service import handle_ipfs_command

        services.ipfs_service._ipfs_service = None

        # Test invalid command format
        result = handle_ipfs_command("!ipfs")
        if "Usage" not in result:
            return False

        # Test add command without URL
        result = handle_ipfs_command("!ipfs add")
        if "Usage" not in result:
            return False

        return True

    except Exception as e:
        print(f"IPFS command handling test failed: {e}")
        return False


def test_eurojackpot_service_creation():
    """Test Eurojackpot service creation and basic functionality."""
    try:
        # Reset global service instance
        import services.eurojackpot_service
        from services.eurojackpot_service import EurojackpotService

        services.eurojackpot_service._eurojackpot_service = None

        service = EurojackpotService()

        # Test week number calculation
        week_num = service.get_week_number("2023-12-15")
        if not isinstance(week_num, int) or week_num < 1 or week_num > 53:
            return False

        # Test frequent numbers
        result = service.get_frequent_numbers()
        if not result["success"]:
            return False

        if len(result["primary_numbers"]) != 5:
            return False

        if len(result["secondary_numbers"]) != 2:
            return False

        return True

    except Exception as e:
        print(f"Eurojackpot service creation test failed: {e}")
        return False


def test_eurojackpot_manual_add():
    """Test manual addition of Eurojackpot draws."""
    try:
        import os
        import tempfile

        from services.eurojackpot_service import EurojackpotService

        # Create service with temporary database file
        service = EurojackpotService()
        temp_db_file = tempfile.mktemp(suffix=".json")
        service.db_file = temp_db_file

        try:
            # Test adding a valid draw (Friday)
            result = service.add_draw_manually(
                "22.12.2023", "1,5,12,25,35,3,8", "15000000"  # This is a Friday
            )

            if not result["success"]:
                return False

            if result["action"] not in ["lisätty", "päivitetty"]:
                return False

            # Test invalid date (not Friday or Tuesday)
            result = service.add_draw_manually(
                "21.12.2023", "1,5,12,25,35,3,8", "15000000"  # This is a Thursday
            )

            if result["success"]:  # Should fail
                return False

            if "tiistaisin ja perjantaisin" not in result["message"]:
                return False

            # Test invalid numbers (wrong count)
            result = service.add_draw_manually(
                "22.12.2023", "1,5,12", "15000000"  # Friday  # Too few numbers
            )

            if result["success"]:  # Should fail
                return False

            if "7 numeroa" not in result["message"]:
                return False

            return True

        finally:
            # Clean up temporary file
            if os.path.exists(temp_db_file):
                os.unlink(temp_db_file)

    except Exception as e:
        print(f"Eurojackpot manual add test failed: {e}")
        return False


def test_eurojackpot_database_operations():
    """Test Eurojackpot database operations."""
    try:
        import os
        import tempfile
        from datetime import datetime

        from services.eurojackpot_service import EurojackpotService

        # Create service with temporary database file
        service = EurojackpotService()
        temp_db_file = tempfile.mktemp(suffix=".json")
        service.db_file = temp_db_file

        try:
            # Test database initialization
            db = service._load_database()
            if not isinstance(db, dict):
                return False

            if "draws" not in db or "last_updated" not in db:
                return False

            if len(db["draws"]) != 0:
                return False

            if db["last_updated"] is not None:
                return False

            # Test saving and loading draw data
            test_draw = {
                "date_iso": "2023-12-15",
                "date": "15.12.2023",
                "week_number": 50,
                "numbers": ["01", "12", "23", "34", "45", "06", "07"],
                "main_numbers": "01 12 23 34 45",
                "euro_numbers": "06 07",
                "jackpot": "15000000",
                "currency": "EUR",
                "type": "test",
                "saved_at": datetime.now().isoformat(),
            }

            # Save draw
            service._save_draw_to_database(test_draw)

            # Load and verify
            loaded_draw = service._get_draw_by_date_from_database("2023-12-15")
            if loaded_draw is None:
                return False

            if loaded_draw["date"] != "15.12.2023":
                return False

            if loaded_draw["main_numbers"] != "01 12 23 34 45":
                return False

            if loaded_draw["euro_numbers"] != "06 07":
                return False

            return True

        finally:
            # Clean up temporary file
            if os.path.exists(temp_db_file):
                os.unlink(temp_db_file)

    except Exception as e:
        print(f"Eurojackpot database operations test failed: {e}")
        return False


def test_eurojackpot_tuesday_friday_validation():
    """Test that Eurojackpot now accepts both Tuesday and Friday draws."""
    try:
        import os
        import tempfile

        from services.eurojackpot_service import EurojackpotService

        service = EurojackpotService()
        temp_db_file = tempfile.mktemp(suffix=".json")
        service.db_file = temp_db_file

        try:
            # Test Tuesday (should work)
            result = service.add_draw_manually(
                "19.12.2023", "1,5,12,25,35,3,8", "15000000"  # This is a Tuesday
            )

            if not result["success"]:
                return False

            # Test Friday (should work)
            result = service.add_draw_manually(
                "22.12.2023", "2,6,13,26,36,4,9", "20000000"  # This is a Friday
            )

            if not result["success"]:
                return False

            # Test Wednesday (should fail)
            result = service.add_draw_manually(
                "20.12.2023", "3,7,14,27,37,5,10", "25000000"  # This is a Wednesday
            )

            if result["success"]:  # Should fail
                return False

            if "tiistaisin ja perjantaisin" not in result["message"]:
                return False

            return True

        finally:
            # Clean up temporary file
            if os.path.exists(temp_db_file):
                os.unlink(temp_db_file)

    except Exception as e:
        print(f"Eurojackpot Tuesday/Friday validation test failed: {e}")
        return False


def register_new_features_tests(runner):
    """Register new features tests with the test framework."""
    tests = [
        TestCase(
            name="scheduled_message_creation",
            description="Test scheduled message service creation and basic functionality",
            test_func=test_scheduled_message_creation,
            category="new_features",
        ),
        TestCase(
            name="scheduled_message_cancellation",
            description="Test scheduled message cancellation",
            test_func=test_scheduled_message_cancellation,
            category="new_features",
        ),
        TestCase(
            name="scheduled_message_convenience_function",
            description="Test convenience function for scheduling messages",
            test_func=test_scheduled_message_convenience_function,
            category="new_features",
        ),
        TestCase(
            name="ipfs_availability_check",
            description="Test IPFS availability checking",
            test_func=test_ipfs_availability_check,
            category="new_features",
        ),
        TestCase(
            name="ipfs_file_size_check",
            description="Test IPFS file size checking during download",
            test_func=test_ipfs_file_size_check,
            category="new_features",
        ),
        TestCase(
            name="ipfs_command_handling",
            description="Test IPFS command handling",
            test_func=test_ipfs_command_handling,
            category="new_features",
        ),
        TestCase(
            name="eurojackpot_service_creation",
            description="Test Eurojackpot service creation and basic functionality",
            test_func=test_eurojackpot_service_creation,
            category="new_features",
        ),
        TestCase(
            name="eurojackpot_manual_add",
            description="Test manual addition of Eurojackpot draws",
            test_func=test_eurojackpot_manual_add,
            category="new_features",
        ),
        TestCase(
            name="eurojackpot_database_operations",
            description="Test Eurojackpot database operations",
            test_func=test_eurojackpot_database_operations,
            category="new_features",
        ),
        TestCase(
            name="eurojackpot_tuesday_friday_validation",
            description="Test Tuesday and Friday draw validation for Eurojackpot",
            test_func=test_eurojackpot_tuesday_friday_validation,
            category="new_features",
        ),
    ]

    suite = TestSuite(
        name="New_Features",
        description="Tests for new bot features (scheduled messages, IPFS, enhanced Eurojackpot)",
        tests=tests,
    )

    runner.add_suite(suite)


# For standalone testing
if __name__ == "__main__":
    from test_framework import TestRunner

    runner = TestRunner(verbose=True)
    register_new_features_tests(runner)
    success = runner.run_all()

    print(f"\nNew features tests: {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1)
