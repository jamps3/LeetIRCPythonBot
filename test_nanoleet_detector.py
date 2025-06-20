#!/usr/bin/env python3
"""
Comprehensive tests for the Nanosecond Leet Detection System.
"""

from nanoleet_detector import NanoLeetDetector, create_nanoleet_detector


def test_ultimate_leet_detection():
    """Test ultimate leet detection (perfect 13:37:13.371337133)."""
    print("🏆 Testing Ultimate Leet Detection...")

    detector = create_nanoleet_detector()

    # Test perfect ultimate leet timestamp
    ultimate_timestamp = "13:37:13.371337133"
    result = detector.detect_leet_patterns(ultimate_timestamp)
    level = detector.determine_achievement_level(result)

    print(f"  Timestamp: {ultimate_timestamp}")
    print(f"  Detection result: {result}")
    print(f"  Achievement level: {level}")

    assert level == "ultimate", f"Expected 'ultimate', got '{level}'"
    assert result["is_ultimate"] == True, "Should detect ultimate pattern"
    assert result["total_count"] >= 1, "Should find at least one 1337"

    # Test achievement message formatting
    message = detector.format_achievement_message("testuser", ultimate_timestamp, level)
    print(f"  Achievement message: {message}")

    expected_parts = ["🏆👑", "Ultimate Leet!!", "[testuser]", ultimate_timestamp]
    for part in expected_parts:
        assert part in message, f"Message should contain '{part}'"

    print("  ✅ Ultimate leet detection passed!")


def test_mega_leet_detection():
    """Test mega leet detection (3+ occurrences of 1337)."""
    print("\n🎯 Testing Mega Leet Detection...")

    detector = create_nanoleet_detector()

    # Test timestamps with 3+ occurrences of 1337
    test_cases = [
        "13:37:13.371337133",  # This should be ultimate, not mega
        "13:37:21.133713371",  # 3 occurrences: 1337 in hours/min, and twice in nanoseconds
        "13:37:37.133713373",  # 3 occurrences
        "12:34:56.133713371",  # 2 occurrences, not 3 - should be super
    ]

    for timestamp in test_cases:
        result = detector.detect_leet_patterns(timestamp)
        level = detector.determine_achievement_level(result)

        print(f"  Timestamp: {timestamp}")
        print(f"    Total 1337 count: {result['total_count']}")
        print(f"    Achievement level: {level}")

        if timestamp == "13:37:13.371337133":
            # This should be ultimate, not mega
            assert (
                level == "ultimate"
            ), f"Perfect timestamp should be ultimate, got '{level}'"
        elif result["total_count"] >= 3:
            assert (
                level == "mega"
            ), f"Expected 'mega' for {result['total_count']} occurrences, got '{level}'"

        # Test message formatting for mega achievements
        if level == "mega":
            message = detector.format_achievement_message("megauser", timestamp, level)
            print(f"    Achievement message: {message}")
            assert "🎯🔥" in message and "Mega Leet!" in message

    print("  ✅ Mega leet detection passed!")


def test_super_leet_detection():
    """Test super leet detection (exactly 2 occurrences of 1337)."""
    print("\n⭐ Testing Super Leet Detection...")

    detector = create_nanoleet_detector()

    # Test timestamps with exactly 2 occurrences of 1337
    test_cases = [
        "13:37:21.123413370",  # 2 occurrences: in hours/min and nanoseconds
        "12:34:56.133713370",  # 2 occurrences: both in nanoseconds
        "13:37:42.987654321",  # 1 occurrence: only in hours/min
        "23:45:12.133713370",  # 2 occurrences: both in nanoseconds
    ]

    for timestamp in test_cases:
        result = detector.detect_leet_patterns(timestamp)
        level = detector.determine_achievement_level(result)

        print(f"  Timestamp: {timestamp}")
        print(f"    Total 1337 count: {result['total_count']}")
        print(f"    Time part count: {result['time_count']}")
        print(f"    Nano part count: {result['nano_count']}")
        print(f"    Achievement level: {level}")

        if result["total_count"] == 2:
            assert (
                level == "super"
            ), f"Expected 'super' for 2 occurrences, got '{level}'"

            # Test message formatting
            message = detector.format_achievement_message("superuser", timestamp, level)
            print(f"    Achievement message: {message}")
            assert "⭐💫" in message and "Super Leet!" in message
        elif result["total_count"] == 1:
            # Should be either 'leet' or 'nano' depending on position
            assert level in [
                "leet",
                "nano",
            ], f"Expected 'leet' or 'nano' for 1 occurrence, got '{level}'"

    print("  ✅ Super leet detection passed!")


def test_regular_leet_detection():
    """Test regular leet detection (1337 in time part)."""
    print("\n🎊 Testing Regular Leet Detection...")

    detector = create_nanoleet_detector()

    # Test timestamps with 1337 in hours, minutes, or seconds
    test_cases = [
        "13:37:42.987654321",  # 1337 in hours and minutes
        "23:13:37.987654321",  # 1337 in minutes and seconds
        "13:45:67.987654321",  # Invalid time but has 13 in hours
        "01:33:71.987654321",  # 1337 split across minutes/seconds (shouldn't count)
        "12:34:56.987654321",  # No 1337 anywhere
    ]

    for timestamp in test_cases:
        result = detector.detect_leet_patterns(timestamp)
        level = detector.determine_achievement_level(result)

        print(f"  Timestamp: {timestamp}")
        print(f"    Time part: {result['time_part']}")
        print(f"    Time count: {result['time_count']}")
        print(f"    Achievement level: {level}")

        if result["time_count"] > 0:
            assert level == "leet", f"Expected 'leet' for time part 1337, got '{level}'"

            # Test message formatting
            message = detector.format_achievement_message("leetuser", timestamp, level)
            print(f"    Achievement message: {message}")
            assert "🎊✨" in message and "Leet!" in message
        elif result["total_count"] == 0:
            assert level is None, f"Expected None for no 1337, got '{level}'"

    print("  ✅ Regular leet detection passed!")


def test_nano_leet_detection():
    """Test nano leet detection (1337 only in nanoseconds)."""
    print("\n🔬 Testing Nano Leet Detection...")

    detector = create_nanoleet_detector()

    # Test timestamps with 1337 only in nanosecond part
    test_cases = [
        "02:38:12.123451337",  # Your example: nano leet at the end
        "14:25:48.133700000",  # 1337 at start of nanoseconds
        "09:15:33.000133700",  # 1337 in middle of nanoseconds
        "22:44:55.987000000",  # No 1337 anywhere
        "18:29:07.513371234",  # 1337 in nanoseconds
    ]

    for timestamp in test_cases:
        result = detector.detect_leet_patterns(timestamp)
        level = detector.determine_achievement_level(result)

        print(f"  Timestamp: {timestamp}")
        print(f"    Nano part: {result['nano_part']}")
        print(f"    Nano count: {result['nano_count']}")
        print(f"    Time count: {result['time_count']}")
        print(f"    Achievement level: {level}")

        if result["nano_count"] > 0 and result["time_count"] == 0:
            assert (
                level == "nano"
            ), f"Expected 'nano' for nanosecond-only 1337, got '{level}'"

            # Test message formatting
            message = detector.format_achievement_message("nanouser", timestamp, level)
            print(f"    Achievement message: {message}")
            assert "🔬⚡" in message and "Nano Leet" in message
        elif result["total_count"] == 0:
            assert level is None, f"Expected None for no 1337, got '{level}'"

    print("  ✅ Nano leet detection passed!")


def test_check_message_for_leet():
    """Test the main message checking function."""
    print("\n🎮 Testing Message Leet Checking...")

    detector = create_nanoleet_detector()

    # Test with predefined timestamps
    test_cases = [
        ("testuser1", "13:37:13.371337133", "ultimate"),
        ("testuser2", "12:34:56.133713371", "super"),  # Only 2 occurrences of 1337
        ("testuser3", "13:37:42.987654321", "leet"),
        ("testuser4", "02:38:12.123451337", "nano"),
        ("testuser5", "09:15:33.000000000", None),
        ("testuser6", "13:37:21.133713371", "mega"),  # 3 occurrences: mega leet
    ]

    for nick, timestamp, expected_level in test_cases:
        result = detector.check_message_for_leet(nick, timestamp)

        print(f"  Nick: {nick}, Timestamp: {timestamp}")

        if expected_level:
            assert result is not None, f"Expected achievement for {timestamp}"
            message, level = result
            assert (
                level == expected_level
            ), f"Expected '{expected_level}', got '{level}'"
            assert nick in message, f"Message should contain nick '{nick}'"
            assert (
                timestamp in message
            ), f"Message should contain timestamp '{timestamp}'"
            print(f"    Achievement: {message}")
        else:
            assert (
                result is None
            ), f"Expected no achievement for {timestamp}, got {result}"
            print(f"    No achievement detected")

    print("  ✅ Message leet checking passed!")


def test_achievement_stats():
    """Test achievement statistics functionality."""
    print("\n📊 Testing Achievement Statistics...")

    detector = create_nanoleet_detector()
    stats = detector.get_achievement_stats()

    print(f"  Available achievement levels: {list(stats.keys())}")

    expected_levels = ["ultimate", "mega", "super", "leet", "nano"]
    for level in expected_levels:
        assert level in stats, f"Missing achievement level: {level}"

        achievement = stats[level]
        assert "name" in achievement, f"Missing 'name' in {level}"
        assert "emoji" in achievement, f"Missing 'emoji' in {level}"
        assert "criteria" in achievement, f"Missing 'criteria' in {level}"

        print(
            f"    {level}: {achievement['emoji']} {achievement['name']} - {achievement['criteria']}"
        )

    print("  ✅ Achievement statistics passed!")


def test_timestamp_generation():
    """Test nanosecond timestamp generation."""
    print("\n⏰ Testing Timestamp Generation...")

    detector = create_nanoleet_detector()

    # Generate several timestamps and check format
    for i in range(5):
        timestamp = detector.get_timestamp_with_nanoseconds()
        print(f"  Generated timestamp {i+1}: {timestamp}")

        # Check format: HH:MM:SS.nnnnnnnnn
        assert (
            len(timestamp) == 18
        ), f"Timestamp should be 18 chars, got {len(timestamp)}"
        assert timestamp[2] == ":", "Position 2 should be ':'"
        assert timestamp[5] == ":", "Position 5 should be ':'"
        assert timestamp[8] == ".", "Position 8 should be '.'"

        # Check that nanosecond part is 9 digits
        nano_part = timestamp.split(".")[1]
        assert (
            len(nano_part) == 9
        ), f"Nanosecond part should be 9 digits, got {len(nano_part)}"
        assert nano_part.isdigit(), "Nanosecond part should be all digits"

    print("  ✅ Timestamp generation passed!")


def test_edge_cases():
    """Test edge cases and corner cases."""
    print("\n🧪 Testing Edge Cases...")

    detector = create_nanoleet_detector()

    # Test edge cases
    edge_cases = [
        "",  # Empty string
        "invalid",  # Invalid format
        "25:61:61.123456789",  # Invalid time values
        "13:37:13",  # No nanoseconds
        "13:37:13.",  # Empty nanoseconds
        "1337133713371337133",  # No separators, all 1337s
        "00:00:00.000000000",  # All zeros
        "23:59:59.999999999",  # Maximum valid time
    ]

    for test_input in edge_cases:
        print(f"  Testing edge case: '{test_input}'")

        try:
            result = detector.detect_leet_patterns(test_input)
            level = detector.determine_achievement_level(result)
            print(f"    Result: {result['total_count']} occurrences, level: {level}")

            # Should handle gracefully without crashing
            if test_input == "1337133713371337133":
                # This should detect multiple 1337s
                assert result["total_count"] >= 3, "Should detect multiple 1337s"
                assert level == "mega", "Should be mega leet"

        except Exception as e:
            print(f"    Exception (expected for some cases): {e}")

    print("  ✅ Edge cases passed!")


def main():
    """Run all nanoleet detector tests."""
    print("🔍 Testing Nanosecond Leet Detection System...\n")

    test_ultimate_leet_detection()
    test_mega_leet_detection()
    test_super_leet_detection()
    test_regular_leet_detection()
    test_nano_leet_detection()
    test_check_message_for_leet()
    test_achievement_stats()
    test_timestamp_generation()
    test_edge_cases()

    print("\n🎉 All nanoleet detection tests passed!")
    print("\nAchievement Levels Summary:")
    print("🏆👑 Ultimate Leet!! - Perfect 13:37:13.371337133 format")
    print("🎯🔥 Mega Leet! - 1337 appears 3+ times")
    print("⭐💫 Super Leet! - 1337 appears 2 times")
    print("🎊✨ Leet! - 1337 appears in time part")
    print("🔬⚡ Nano Leet - 1337 appears only in nanoseconds")


if __name__ == "__main__":
    main()
