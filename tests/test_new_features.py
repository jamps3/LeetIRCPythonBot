#!/usr/bin/env python3
"""
New Features Test Suite

Tests for new bot features including scheduled messages, IPFS integration,
and enhanced Eurojackpot functionality.
"""

import os
import sys
from unittest.mock import MagicMock, Mock, patch

# Add the parent directory to sys.path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

# Load environment variables for testing
load_dotenv()


def test_scheduled_message_creation():
    """Test scheduled message service creation and basic functionality."""
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
    assert isinstance(message_id, str)
    assert "scheduled_" in message_id

    # Verify message is in the scheduled list
    scheduled = service.list_scheduled_messages()
    assert message_id in scheduled
    assert scheduled[message_id]["message"] == "Test message"
    assert scheduled[message_id]["channel"] == "#test"


def test_scheduled_message_cancellation():
    """Test scheduled message cancellation."""
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
    assert message_id in scheduled

    # Cancel it
    result = service.cancel_message(message_id)
    assert result is True

    # Verify it's gone
    scheduled = service.list_scheduled_messages()
    assert message_id not in scheduled


def test_scheduled_message_convenience_function():
    """Test the convenience function for scheduling messages."""
    # Reset global service instance
    import services.scheduled_message_service
    from services.scheduled_message_service import send_scheduled_message

    services.scheduled_message_service._scheduled_message_service = None

    mock_irc = Mock()

    message_id = send_scheduled_message(
        mock_irc, "#test", "Convenience test", 23, 59, 57, 123456
    )

    assert isinstance(message_id, str)


@patch("subprocess.run")
def test_ipfs_availability_check(mock_run):
    """Test IPFS availability checking."""
    # Reset global service instance
    import services.ipfs_service
    from services.ipfs_service import IPFSService

    services.ipfs_service._ipfs_service = None

    # Test when IPFS is available
    mock_run.return_value.returncode = 0
    service = IPFSService()
    assert service.ipfs_available is True

    # Test when IPFS is not available
    mock_run.side_effect = FileNotFoundError()
    service2 = IPFSService()
    assert service2.ipfs_available is False


@patch("requests.head")
@patch("requests.get")
def test_ipfs_file_size_check(mock_get, mock_head):
    """Test IPFS file size checking during download."""
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

    assert temp_file is None
    assert "too large" in error
    assert size == 200000000


def test_ipfs_command_handling():
    """Test IPFS command handling."""
    # Reset global service instance
    import services.ipfs_service
    from services.ipfs_service import handle_ipfs_command

    services.ipfs_service._ipfs_service = None

    # Test invalid command format
    result = handle_ipfs_command("!ipfs")
    assert "Usage" in result

    # Test add command without URL
    result = handle_ipfs_command("!ipfs add")
    assert "Usage" in result


def test_eurojackpot_service_creation():
    """Test Eurojackpot service creation and basic functionality."""
    # Reset global service instance
    import services.eurojackpot_service
    from services.eurojackpot_service import EurojackpotService

    services.eurojackpot_service._eurojackpot_service = None

    service = EurojackpotService()

    # Test week number calculation
    week_num = service.get_week_number("2023-12-15")
    assert isinstance(week_num, int)
    assert 1 <= week_num <= 53

    # Test frequent numbers
    result = service.get_frequent_numbers()
    assert result["success"] is True
    assert len(result["primary_numbers"]) == 5
    assert len(result["secondary_numbers"]) == 2


def test_eurojackpot_manual_add():
    """Test manual addition of Eurojackpot draws."""
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

        assert result["success"] is True
        assert result["action"] in ["lisätty", "päivitetty"]

        # Test invalid date (not Friday or Tuesday)
        result = service.add_draw_manually(
            "21.12.2023", "1,5,12,25,35,3,8", "15000000"  # This is a Thursday
        )

        assert result["success"] is False
        assert "tiistaisin ja perjantaisin" in result["message"]

        # Test invalid numbers (wrong count)
        result = service.add_draw_manually(
            "22.12.2023", "1,5,12", "15000000"  # Friday  # Too few numbers
        )

        assert result["success"] is False
        assert "7 numeroa" in result["message"]

    finally:
        # Clean up temporary file
        if os.path.exists(temp_db_file):
            os.unlink(temp_db_file)


def test_eurojackpot_database_operations():
    """Test Eurojackpot database operations."""
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
        assert isinstance(db, dict)
        assert "draws" in db
        assert "last_updated" in db
        assert len(db["draws"]) == 0
        assert db["last_updated"] is None

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
        assert loaded_draw is not None
        assert loaded_draw["date"] == "15.12.2023"
        assert loaded_draw["main_numbers"] == "01 12 23 34 45"
        assert loaded_draw["euro_numbers"] == "06 07"

    finally:
        # Clean up temporary file
        if os.path.exists(temp_db_file):
            os.unlink(temp_db_file)


def test_eurojackpot_tuesday_friday_validation():
    """Test that Eurojackpot now accepts both Tuesday and Friday draws."""
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

        assert result["success"] is True

        # Test Friday (should work)
        result = service.add_draw_manually(
            "22.12.2023", "2,6,13,26,36,4,9", "20000000"  # This is a Friday
        )

        assert result["success"] is True

        # Test Wednesday (should fail)
        result = service.add_draw_manually(
            "20.12.2023", "3,7,14,27,37,5,10", "25000000"  # This is a Wednesday
        )

        assert result["success"] is False
        assert "tiistaisin ja perjantaisin" in result["message"]

    finally:
        # Clean up temporary file
        if os.path.exists(temp_db_file):
            os.unlink(temp_db_file)
