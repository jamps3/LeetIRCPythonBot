import os

import pytest

from leet_detector import LeetDetector


def test_ignore_trivial_1337_at_13_37_only():
    d = LeetDetector()
    # Time is 23:37 with seconds that don't contain 1337 and no nano 1337
    ts = "23:37:42.987654321"
    result = d.detect_leet_patterns(ts)
    level = d.determine_achievement_level(result)
    assert level is None, "Should ignore trivial 13:37-only occurrence"


def test_detect_leet_when_additional_occurrence_present_in_seconds():
    d = LeetDetector()
    # Time part contains extra 1337 in seconds -> should be at least 'leet'
    ts = "23:13:37.987654321"
    result = d.detect_leet_patterns(ts)
    level = d.determine_achievement_level(result)
    assert level in {"leet", "super", "mega", "ultimate"}


def test_detect_nano_leet_when_only_nano_contains_1337():
    d = LeetDetector()
    # Time is 23:37 but seconds do not contain 1337; nano has 1337
    ts = "23:37:42.000133700"
    result = d.detect_leet_patterns(ts)
    level = d.determine_achievement_level(result)
    assert level in {"nano", "super", "mega", "ultimate"}


def test_nanoleet_detector_ultimate():
    """Test ultimate leet detection (perfect 13:37:13.371337133)."""
    from leet_detector import create_nanoleet_detector

    detector = create_nanoleet_detector()

    # Test perfect ultimate leet timestamp
    ultimate_timestamp = "13:37:13.371337133"
    result = detector.detect_leet_patterns(ultimate_timestamp)
    level = detector.determine_achievement_level(result)

    assert level == "ultimate", f"Expected 'ultimate' level, got '{level}'"
    assert result["is_ultimate"], "Result should be marked as ultimate"
    assert result["total_count"] >= 1, "Total count should be at least 1"

    # Test achievement message formatting
    message = detector.format_achievement_message("testuser", ultimate_timestamp, level)
    expected_parts = ["🏆👑", "Ultimate Leet!!", "[testuser]", ultimate_timestamp]

    for part in expected_parts:
        assert part in message, f"Expected '{part}' in message: {message}"


def test_nanoleet_detector_mega():
    """Test mega leet detection (3+ occurrences of 1337)."""
    from leet_detector import create_nanoleet_detector

    detector = create_nanoleet_detector()

    # Test timestamps with 3+ occurrences of 1337
    test_cases = [
        ("13:37:21.133713371", "mega"),  # 3 occurrences
        ("12:34:56.133713371", "super"),  # 2 occurrences, should be super
    ]

    for timestamp, expected_level in test_cases:
        result = detector.detect_leet_patterns(timestamp)
        level = detector.determine_achievement_level(result)

        if timestamp == "13:37:13.371337133":
            # This should be ultimate, not mega
            assert (
                level == "ultimate"
            ), f"Ultimate timestamp should be 'ultimate', got '{level}'"
        elif result["total_count"] >= 3 and expected_level == "mega":
            assert (
                level == "mega"
            ), f"Expected 'mega' level for {timestamp}, got '{level}'"
        elif result["total_count"] == 2 and expected_level == "super":
            assert (
                level == "super"
            ), f"Expected 'super' level for {timestamp}, got '{level}'"


def test_nanoleet_detector_nano():
    """Test nano leet detection (1337 only in nanoseconds)."""
    from leet_detector import create_nanoleet_detector

    detector = create_nanoleet_detector()

    # Test timestamps with 1337 only in nanosecond part
    test_cases = [
        "02:38:12.123451337",  # nano leet at the end
        "14:25:48.133700000",  # 1337 at start of nanoseconds
        "09:15:33.000133700",  # 1337 in middle of nanoseconds
    ]

    for timestamp in test_cases:
        result = detector.detect_leet_patterns(timestamp)
        level = detector.determine_achievement_level(result)

        if result["nano_count"] > 0 and result["time_count"] == 0:
            assert (
                level == "nano"
            ), f"Expected 'nano' level for {timestamp}, got '{level}'"

            # Test message formatting
            message = detector.format_achievement_message("nanouser", timestamp, level)
            assert "🔬⚡" in message, f"Expected nano emoji in message: {message}"
            assert "Nano Leet" in message, f"Expected 'Nano Leet' in message: {message}"


def test_nanoleet_message_for_leet():
    """Test nanoleet message processing for regular leet detection."""
    from leet_detector import create_nanoleet_detector

    detector = create_nanoleet_detector()

    # Test check_message_for_leet function
    test_timestamp = "23:13:37.987654321"  # Regular leet (1337 appears in timestamp but not in hours+minutes)
    result = detector.check_message_for_leet("testuser", test_timestamp)

    assert result is not None, "Should detect leet in timestamp"

    message, level = result

    assert level == "leet", f"Expected 'leet' level, got '{level}'"
    assert "testuser" in message, "Message should contain username"
    assert test_timestamp in message, "Message should contain timestamp"
    assert "🎊✨" in message, "Message should contain leet emoji"


def test_leet_detector_json_storage():
    """Test that leet detections are properly stored in JSON format."""
    import json
    import tempfile

    from leet_detector import create_leet_detector

    # Create temporary file for testing
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        test_file = f.name

    try:
        # Create detector with test file
        detector = create_leet_detector()
        detector.leet_history_file = test_file

        # Test that no history exists initially
        history = detector.get_leet_history()
        assert len(history) == 0, "History should be empty initially"

        # Create a leet detection
        result = detector.check_message_for_leet(
            "testuser", "23:13:37.987654321", "Test message"
        )
        assert result is not None, "Should detect leet"

        # Check that it was saved to JSON
        history = detector.get_leet_history()
        assert len(history) == 1, "Should have one detection in history"

        detection = history[0]
        assert detection["nick"] == "testuser", "Nick should be saved correctly"
        assert (
            detection["timestamp"] == "23:13:37.987654321"
        ), "Timestamp should be saved correctly"
        assert (
            detection["user_message"] == "Test message"
        ), "User message should be saved correctly"
        assert (
            detection["achievement_level"] == "leet"
        ), "Achievement level should be correct"
        assert "datetime" in detection, "Detection should have datetime"
        assert "achievement_name" in detection, "Detection should have achievement name"
        assert "emoji" in detection, "Detection should have emoji"

        # Test that JSON file is valid
        with open(test_file, "r", encoding="utf-8") as f:
            json_data = json.load(f)
        assert isinstance(json_data, list), "JSON should contain a list"
        assert len(json_data) == 1, "JSON should have one detection"

    finally:
        # Clean up
        if os.path.exists(test_file):
            os.unlink(test_file)


def test_leet_detector_history_limit():
    """Test that leet history limit works correctly."""
    import tempfile
    import time

    from leet_detector import create_leet_detector

    # Create temporary file for testing
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        test_file = f.name

    try:
        # Create detector with test file
        detector = create_leet_detector()
        detector.leet_history_file = test_file

        # Create multiple leet detections
        test_scenarios = [
            ("alice", "13:37:13.371337133", "Ultimate leet!"),
            ("bob", "13:37:21.133713371", "Mega leet!"),
            ("charlie", "12:34:56.133713370", "Super leet!"),
            ("dave", "23:13:37.987654321", "Regular leet"),
            ("eve", "02:38:12.123451337", "Nano leet"),
        ]

        for nick, timestamp, message in test_scenarios:
            detector.check_message_for_leet(nick, timestamp, message)
            time.sleep(0.01)  # Small delay to ensure different timestamps

        # Test unlimited history
        all_history = detector.get_leet_history()
        assert (
            len(all_history) == 5
        ), f"Should have 5 detections, got {len(all_history)}"

        # Test limited history
        limited_history = detector.get_leet_history(limit=3)
        assert (
            len(limited_history) == 3
        ), f"Should have 3 detections with limit, got {len(limited_history)}"

        # Test that history is sorted by most recent first
        # The last detection (eve) should be first in the history
        assert (
            limited_history[0]["nick"] == "eve"
        ), "Most recent detection should be first"
        assert (
            limited_history[1]["nick"] == "dave"
        ), "Second most recent should be second"
        assert (
            limited_history[2]["nick"] == "charlie"
        ), "Third most recent should be third"

    finally:
        # Clean up
        if os.path.exists(test_file):
            os.unlink(test_file)


def test_leet_detector_message_inclusion():
    """Test that user messages are properly included in leet detections."""
    import tempfile

    from leet_detector import create_leet_detector

    # Create temporary file for testing
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        test_file = f.name

    try:
        # Create detector with test file
        detector = create_leet_detector()
        detector.leet_history_file = test_file

        # Test with user message
        test_message = "This is my test message with leet!"
        result = detector.check_message_for_leet(
            "testuser", "23:13:37.987654321", test_message
        )

        assert result is not None, "Should detect leet"
        achievement_msg, level = result

        # Check that the user message is included in the achievement message
        assert (
            test_message in achievement_msg
        ), f"User message should be in achievement message: {achievement_msg}"
        assert (
            '"' in achievement_msg
        ), "User message should be quoted in achievement message"

        # Check that it's stored in history
        history = detector.get_leet_history()
        assert len(history) == 1, "Should have one detection in history"
        assert (
            history[0]["user_message"] == test_message
        ), "User message should be stored in history"

        # Test without user message
        result2 = detector.check_message_for_leet("testuser2", "12:34:56.133713370")
        assert result2 is not None, "Should detect leet even without user message"

        history2 = detector.get_leet_history()
        assert len(history2) == 2, "Should have two detections in history"

        # Find the detection without user message
        no_msg_detection = next(d for d in history2 if d["nick"] == "testuser2")
        assert (
            no_msg_detection["user_message"] is None
        ), "Detection without message should have None for user_message"

    finally:
        # Clean up
        if os.path.exists(test_file):
            os.unlink(test_file)


def test_leets_command_formatting():
    """Test the formatting of the !leets command output."""
    import tempfile
    from datetime import datetime

    from leet_detector import create_leet_detector

    # Create temporary file for testing
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        test_file = f.name

    try:
        # Create detector with test file
        detector = create_leet_detector()
        detector.leet_history_file = test_file

        # Create a test detection
        test_message = "Amazing leet timing!"
        result = detector.check_message_for_leet(
            "testuser", "13:37:42.133713370", test_message
        )
        assert result is not None, "Should detect leet"

        # Get history
        history = detector.get_leet_history()
        assert len(history) == 1, "Should have one detection"

        detection = history[0]

        # Test datetime parsing (simulate what the !leets command does)
        try:
            dt = datetime.fromisoformat(detection["datetime"].replace("Z", "+00:00"))
            date_str = dt.strftime("%d.%m %H:%M:%S")
        except (ValueError, KeyError, AttributeError):
            date_str = detection.get("datetime", "Unknown")

        # Format message (simulate what the !leets command does)
        user_msg_part = (
            f' "{detection["user_message"]}"' if detection.get("user_message") else ""
        )
        formatted_msg = f"{detection['emoji']} {detection['achievement_name']} [{detection['nick']}] {detection['timestamp']}{user_msg_part} ({date_str})"

        # Check that all components are present
        assert (
            detection["emoji"] in formatted_msg
        ), "Emoji should be in formatted message"
        assert (
            detection["achievement_name"] in formatted_msg
        ), "Achievement name should be in formatted message"
        assert (
            f"[{detection['nick']}]" in formatted_msg
        ), "Nick should be bracketed in formatted message"
        assert (
            detection["timestamp"] in formatted_msg
        ), "Timestamp should be in formatted message"
        assert (
            f'"{test_message}"' in formatted_msg
        ), "User message should be quoted in formatted message"
        assert (
            date_str in formatted_msg
        ), "Date should be in parentheses in formatted message"

        # Test message without user content
        result2 = detector.check_message_for_leet("testuser2", "12:34:56.133713370")
        history2 = detector.get_leet_history()

        no_msg_detection = next(d for d in history2 if d["nick"] == "testuser2")
        user_msg_part2 = (
            f' "{no_msg_detection["user_message"]}"'
            if no_msg_detection.get("user_message")
            else ""
        )
        formatted_msg2 = f"{no_msg_detection['emoji']} {no_msg_detection['achievement_name']} [{no_msg_detection['nick']}] {no_msg_detection['timestamp']}{user_msg_part2} ({date_str})"

        # Should not have quotes when no user message
        assert '"' not in user_msg_part2, "Should not have quotes when no user message"

    finally:
        # Clean up
        if os.path.exists(test_file):
            os.unlink(test_file)
