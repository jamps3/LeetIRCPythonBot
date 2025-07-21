from unittest.mock import MagicMock

import pytest

from commands_extended import command_leets
from leet_detector import create_leet_detector


@pytest.fixture
def mock_leet_detector(monkeypatch):
    """Fixture to mock the LeetDetector and its history."""
    mock_detector = MagicMock()
    mock_detector.get_leet_history.return_value = [
        {
            "datetime": "2025-07-21T01:44:07.388625",
            "nick": "testuser",
            "timestamp": "13:37:42.987654321",
            "achievement_level": "leet",
            "user_message": "First leet message",
            "achievement_name": "Leet!",
            "emoji": "🎊✨",
        },
        {
            "datetime": "2025-07-21T01:46:18.259017",
            "nick": "anotheruser",
            "timestamp": "13:37:42.987654321",
            "achievement_level": "leet",
            "user_message": "Another leet",
            "achievement_name": "Leet!",
            "emoji": "🎊✨",
        },
    ]
    monkeypatch.setattr("leet_detector.create_leet_detector", lambda: mock_detector)
    return mock_detector


def test_leets_command_with_mocked_data(mock_leet_detector):
    """Test the !leets command with mocked leet detection history."""
    context = MagicMock()
    args = []
    response = command_leets(context, args)

    expected_output = "🎉 Recent Leet Detections:\n"
    expected_output += '🎊✨ Leet! [testuser] 13:37:42.987654321 "First leet message" (21.07 01:44:07)\n'
    expected_output += (
        '🎊✨ Leet! [anotheruser] 13:37:42.987654321 "Another leet" (21.07 01:46:18)'
    )

    assert response == expected_output


def test_leets_command_empty_history(monkeypatch):
    """Test the !leets command when no detections are available."""
    mock_detector = MagicMock()
    mock_detector.get_leet_history.return_value = []
    monkeypatch.setattr("leet_detector.create_leet_detector", lambda: mock_detector)

    context = MagicMock()
    args = []
    response = command_leets(context, args)

    assert response == "No leet detections found."
