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
