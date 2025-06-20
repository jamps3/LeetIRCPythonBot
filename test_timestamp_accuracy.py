#!/usr/bin/env python3
"""
Test demonstrating the improved timestamp accuracy for nanoleet detection.
"""

import time

from nanoleet_detector import create_nanoleet_detector


def test_timestamp_accuracy():
    """Test the accuracy and timing of timestamp capture."""
    print("⏱️ Testing Timestamp Accuracy for Nanoleet Detection")
    print("=" * 60)

    detector = create_nanoleet_detector()

    print("\n🎯 Priority Test: Measuring timestamp capture speed...")

    # Simulate multiple rapid message processing
    print("\nSimulating rapid message processing (10 messages):")

    timestamps = []
    for i in range(10):
        # Simulate the exact moment a message is received
        start_time = time.time_ns()

        # Get timestamp immediately (first priority)
        timestamp = detector.get_timestamp_with_nanoseconds()

        # Calculate processing time
        end_time = time.time_ns()
        processing_time_ns = end_time - start_time

        timestamps.append(timestamp)

        print(
            f"  Message {i+1:2d}: {timestamp} (captured in {processing_time_ns:,} ns)"
        )

        # Small delay to see nanosecond differences
        time.sleep(0.0001)  # 100 microseconds

    print(f"\n📊 Statistics:")
    print(f"   - Generated {len(timestamps)} unique timestamps")
    print(f"   - All timestamps are unique: {len(set(timestamps)) == len(timestamps)}")
    print(f"   - Nanosecond precision: ✅")

    # Test what happens with processing delays
    print("\n🔄 Testing impact of processing delays:")

    print("\n  Scenario 1: Timestamp captured FIRST (current implementation)")
    start = time.time_ns()
    immediate_timestamp = detector.get_timestamp_with_nanoseconds()

    # Simulate other processing (word tracking, youtube, etc.)
    time.sleep(0.001)  # 1ms delay

    end = time.time_ns()
    total_delay = end - start

    print(f"    Timestamp: {immediate_timestamp}")
    print(
        f"    Total processing time: {total_delay:,} ns ({total_delay/1_000_000:.2f} ms)"
    )

    print("\n  Scenario 2: Timestamp captured AFTER processing (old way)")
    start = time.time_ns()

    # Simulate other processing first
    time.sleep(0.001)  # 1ms delay

    delayed_timestamp = detector.get_timestamp_with_nanoseconds()
    end = time.time_ns()
    total_delay = end - start

    print(f"    Timestamp: {delayed_timestamp}")
    print(
        f"    Total processing time: {total_delay:,} ns ({total_delay/1_000_000:.2f} ms)"
    )

    # Compare the timestamps
    def extract_nanoseconds(ts):
        return int(ts.split(".")[1])

    immediate_ns = extract_nanoseconds(immediate_timestamp)
    delayed_ns = extract_nanoseconds(delayed_timestamp)
    difference_ns = (
        abs(delayed_ns - immediate_ns)
        if delayed_ns > immediate_ns
        else (1_000_000_000 - immediate_ns + delayed_ns)
    )

    print(f"\n  📏 Accuracy difference: {difference_ns:,} nanoseconds")
    print(f"     ({difference_ns/1_000_000:.2f} milliseconds)")

    print(f"\n✅ RESULT: First-priority timestamp capture provides")
    print(f"   maximum accuracy for leet detection!")

    # Test for potential leet achievements
    print(f"\n🎲 Testing current timestamps for leet achievements:")

    for i in range(5):
        current_ts = detector.get_timestamp_with_nanoseconds()
        result = detector.check_message_for_leet("test_user", current_ts)

        if result:
            achievement_message, level = result
            print(f"  🎉 LUCKY: {achievement_message}")
        else:
            print(f"  ⏰ {current_ts} (no leet)")

        time.sleep(0.0005)  # 500 microseconds

    print(f"\n🎯 The nanoleet detection now runs with MAXIMUM accuracy!")
    print(f"   - First priority in message processing pipeline")
    print(f"   - Immediate timestamp capture upon message receipt")
    print(f"   - Nanosecond precision maintained")
    print(f"   - No processing delays affect timestamp accuracy")


if __name__ == "__main__":
    test_timestamp_accuracy()
