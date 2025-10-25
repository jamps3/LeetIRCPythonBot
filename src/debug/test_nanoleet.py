#!/usr/bin/env python3
"""
Demo script showing the nanosecond leet detection system in action.
"""

import sys
import time
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from leet_detector import create_nanoleet_detector


def demo_nanoleet_detection():
    """Demonstrate the nanoleet detection system."""
    print("Nanosecond Leet Detection System Demo")
    print("=" * 50)

    detector = create_nanoleet_detector()

    print("\nSimulating channel messages with leet detection...\n")

    # Test various timestamp scenarios
    test_scenarios = [
        ("jampsix", "13:37:13.371337133", "The ultimate leet timestamp!"),
        ("testuser", "13:37:21.133713371", "Multiple 1337s in one timestamp"),
        ("alice", "02:38:12.123451337", "Your example - nano leet at the end"),
        ("bob", "23:13:37.987654321", "Regular leet in time part"),
        ("charlie", "14:25:30.000000000", "No leet here"),
        ("dave", "12:34:56.133713370", "Super leet with 2 occurrences"),
        ("eve", "19:45:33.133713371", "Another mega leet scenario"),
    ]

    for nick, timestamp, description in test_scenarios:
        print(f"[{timestamp}] <{nick}> {description}")

        # Check for leet achievement
        result = detector.check_message_for_leet(nick, timestamp)

        if result:
            achievement_message, achievement_level = result
            print(f"    {achievement_message}")
        else:
            print("    No leet achievement detected")

        print()

    print("Achievement System Summary:")
    print("-" * 30)

    stats = detector.get_achievement_stats()
    for level, info in stats.items():
        print(f"{info['emoji']} {info['name']}: {info['criteria']}")

    print("\nReal-time demonstration:")
    print("Generating 10 random timestamps to see if we get lucky...")

    lucky_count = 0
    for i in range(10):
        timestamp = detector.get_timestamp_with_nanoseconds()
        result = detector.check_message_for_leet("demo_user", timestamp)

        if result:
            achievement_message, achievement_level = result
            print(f"  LUCKY #{i+1}: {achievement_message}")
            lucky_count += 1
        else:
            print(f"  #{i+1}: {timestamp} (no leet)")

        # Small delay to get different nanoseconds
        time.sleep(0.001)

    print(f"\nFound {lucky_count} leet achievements in 10 random timestamps!")
    print("The system is now integrated into the bot and will detect")
    print("   leet achievements automatically on every channel message!")


if __name__ == "__main__":
    demo_nanoleet_detection()
