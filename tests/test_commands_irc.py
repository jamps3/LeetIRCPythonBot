#!/usr/bin/env python3
"""
Pytest tests for IRC commands.

These tests ensure that IRC context (irc connection and channel) is properly
propagated to service functions for commands like !s (weather) and !sahko (electricity).
"""

import os
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import pytest

# Common imports used by various merged tests
from command_registry import CommandContext
from commands import command_leets, solarwind_command
from word_tracking import DataManager, DrinkTracker


@pytest.fixture(autouse=True, scope="function")
def reset_command_registry():
    """Reset command registry before each test to avoid conflicts."""
    from command_registry import reset_command_registry

    reset_command_registry()

    # Reset command loader flag so commands get reloaded
    try:
        from command_loader import reset_commands_loaded_flag

        reset_commands_loaded_flag()
    except ImportError:
        pass

    # Load all command modules to register commands properly
    try:
        from command_loader import load_all_commands

        load_all_commands()
    except Exception:
        # Fallback: try individual imports
        try:
            import commands
            import commands_admin
            import commands_irc
        except Exception:
            pass

    yield

    # Clean up after test
    reset_command_registry()


# Optional dotenv loading (graceful no-op if not available)
try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover - fallback for environments without dotenv

    def load_dotenv():  # type: ignore
        return None


load_dotenv()


class DummyIrc:
    """Minimal dummy IRC object to pass through the pipeline."""

    def __init__(self):
        self.sent = []

    # Provide methods that may be used by _send_response if ever invoked
    def send_message(self, target, msg):
        self.sent.append(("PRIVMSG", target, msg))

    def send_notice(self, target, msg):
        self.sent.append(("NOTICE", target, msg))


def _run_irc(process_irc_message, raw_text, bot_functions):
    mock_irc = DummyIrc()
    process_irc_message(mock_irc, raw_text, bot_functions)
    return mock_irc


def test_irc_weather_command_passes_irc_context():
    """!s should call send_weather with the IRC connection and channel target."""
    from command_loader import process_irc_message

    calls = SimpleNamespace(args=None)

    def mock_send_weather(irc, target, location):
        calls.args = (irc, target, location)

    responses = []

    def mock_notice(msg, irc=None, target=None):
        responses.append(msg)

    bot_functions = {
        "notice_message": mock_notice,
        "send_weather": mock_send_weather,
        # These are optional for this path but provided to match interface
        "log": lambda msg, level="INFO": None,
    }

    # Simulate IRC channel command: :nick!u@h PRIVMSG #chan :!s Joensuu
    raw_text = ":tester!user@host PRIVMSG #test :!s Joensuu"

    mock_irc = _run_irc(process_irc_message, raw_text, bot_functions)

    # Ensure our mock was called and IRC context was provided
    assert calls.args is not None, "send_weather was not called"
    irc_arg, target_arg, location_arg = calls.args
    assert irc_arg is not None, "IRC context was not provided to send_weather"
    assert target_arg == "#test", "Channel target not passed correctly"
    assert location_arg.lower() == "joensuu"


def test_irc_electricity_command_passes_irc_context():
    """!sahko should call send_electricity_price with the IRC connection and channel."""
    from command_loader import process_irc_message

    calls = SimpleNamespace(args=None)

    def mock_send_electricity_price(irc, target, parts):
        calls.args = (irc, target, parts)

    responses = []

    def mock_notice(msg, irc=None, target=None):
        responses.append(msg)

    bot_functions = {
        "notice_message": mock_notice,
        "send_electricity_price": mock_send_electricity_price,
        "log": lambda msg, level="INFO": None,
    }

    # Simulate IRC channel command: :nick!u@h PRIVMSG #chan :!sahko
    raw_text = ":tester!user@host PRIVMSG #test :!sahko"

    mock_irc = _run_irc(process_irc_message, raw_text, bot_functions)

    assert calls.args is not None, "send_electricity_price was not called"
    irc_arg, target_arg, parts_arg = calls.args
    assert irc_arg is not None, "IRC context was not provided to send_electricity_price"
    assert target_arg == "#test", "Channel target not passed correctly"
    assert (
        isinstance(parts_arg, list) and parts_arg and parts_arg[0] in ("sahko", "sähkö")
    ), "Command parts not passed correctly"


# =========================
# Kraks command (drink tracking) tests (merged from test_commands.py)
# =========================


@pytest.fixture
def temp_dir():
    """Create and clean up a temporary directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir

    # Cleanup
    import shutil

    shutil.rmtree(temp_dir)


@pytest.fixture
def data_manager(temp_dir):
    """Create a DataManager instance for testing."""
    # Clear the opt-out environment variable to ensure clean test environment
    os.environ["DRINK_TRACKING_OPT_OUT"] = ""
    return DataManager(temp_dir)


@pytest.fixture
def drink_tracker(data_manager):
    """Create a DrinkTracker instance for testing."""
    return DrinkTracker(data_manager)


def test_kraks_command_empty_stats(drink_tracker):
    """Test !kraks command with no drink words recorded."""
    server_name = "test_server"
    stats = drink_tracker.get_server_stats(server_name)

    # Should return empty stats
    assert stats["total_drink_words"] == 0, "Should have no drink words initially"
    assert stats["top_users"] == [], "Should have no top users initially"


def test_kraks_command_with_data(drink_tracker):
    """Test !kraks command with recorded drink words."""
    server_name = "test_server"

    # Add some test data
    alice_matches = drink_tracker.process_message(
        server_name, "alice", "krak krak krak"
    )
    bob_matches = drink_tracker.process_message(server_name, "bob", "narsk narsk")
    charlie_matches = drink_tracker.process_message(server_name, "charlie", "parsk")

    # Verify matches were found
    assert len(alice_matches) == 3, "Alice should have 3 kraks"
    assert len(bob_matches) == 2, "Bob should have 2 narsks"
    assert len(charlie_matches) == 1, "Charlie should have 1 parsk"

    # Get stats
    stats = drink_tracker.get_server_stats(server_name)

    # Should have recorded drink words
    assert stats["total_drink_words"] == 6, "Should have 6 total drink words"
    assert len(stats["top_users"]) == 3, "Should have 3 users"
    assert stats["top_users"][0] == ("alice", 3), "Alice should have most drinks"
    assert stats["top_users"][1] == ("bob", 2), "Bob should have second most drinks"
    assert stats["top_users"][2] == ("charlie", 1), "Charlie should have least drinks"


def test_kraks_command_drink_word_breakdown(drink_tracker):
    """Test !kraks command breakdown by drink word."""
    server_name = "test_server"

    # Add some test data
    drink_tracker.process_message(server_name, "alice", "krak krak krak")
    drink_tracker.process_message(server_name, "bob", "narsk narsk")
    drink_tracker.process_message(server_name, "charlie", "krak")

    # Get breakdown
    breakdown = drink_tracker.get_drink_word_breakdown(server_name)

    # Should have correct breakdown
    assert len(breakdown) == 2, "Should have 2 different drink words"
    assert breakdown[0] == (
        "krak",
        4,
        "alice",
    ), "Krak should have 4 total with alice as top user"
    assert breakdown[1] == (
        "narsk",
        2,
        "bob",
    ), "Narsk should have 2 total with bob as top user"


def test_kraks_command_response_format(drink_tracker):
    """Test !kraks command response formatting."""
    server_name = "test_server"

    # Add some test data
    drink_tracker.process_message(server_name, "alice", "krak krak")
    drink_tracker.process_message(server_name, "bob", "narsk")

    # Get stats and breakdown
    stats = drink_tracker.get_server_stats(server_name)
    breakdown = drink_tracker.get_drink_word_breakdown(server_name)

    # Test response construction
    if stats["total_drink_words"] > 0:
        if breakdown:
            details = ", ".join(
                f"{word}: {count} [{top_user}]"
                for word, count, top_user in breakdown[:10]
            )
            response = f"Krakit yhteensä: {stats['total_drink_words']}, {details}"
        else:
            response = (
                f"Krakit yhteensä: {stats['total_drink_words']}. Top 5: "
                + ", ".join(
                    [f"{nick}:{count}" for nick, count in stats["top_users"][:5]]
                )
            )
    else:
        response = "Ei vielä krakkauksia tallennettuna."

    expected_response = "Krakit yhteensä: 3, krak: 2 [alice], narsk: 1 [bob]"
    assert response == expected_response, "Response format should match expected format"


def test_kraks_command_empty_response(drink_tracker):
    """Test !kraks command response when no data exists."""
    server_name = "test_server"

    # Get stats (should be empty)
    stats = drink_tracker.get_server_stats(server_name)

    # Test response construction
    if stats["total_drink_words"] > 0:
        response = f"Krakit yhteensä: {stats['total_drink_words']}"
    else:
        response = "Ei vielä krakkauksia tallennettuna."

    assert (
        response == "Ei vielä krakkauksia tallennettuna."
    ), "Should show no drinks message"


def test_kraks_command_with_specific_drinks(drink_tracker):
    """Test !kraks command with specific drink information."""
    server_name = "test_server"

    # Add some test data with specific drinks
    drink_tracker.process_message(server_name, "alice", "krak (Karhu 5,5%)")
    drink_tracker.process_message(server_name, "bob", "narsk (Olvi III)")
    drink_tracker.process_message(server_name, "alice", "krak (Karhu 5,5%)")

    # Get user stats to verify specific drinks are tracked
    alice_stats = drink_tracker.get_user_stats(server_name, "alice")
    bob_stats = drink_tracker.get_user_stats(server_name, "bob")

    # Verify specific drinks are recorded
    assert (
        alice_stats["total_drink_words"] == 2
    ), "Alice should have 2 total drink words"
    assert (
        alice_stats["drink_words"]["krak"]["drinks"]["Karhu 5,5%"] == 2
    ), "Alice should have 2 Karhu 5,5%"

    assert bob_stats["total_drink_words"] == 1, "Bob should have 1 total drink word"
    assert (
        bob_stats["drink_words"]["narsk"]["drinks"]["Olvi III"] == 1
    ), "Bob should have 1 Olvi III"


def test_kraks_command_user_privacy(drink_tracker, data_manager):
    """Test !kraks command respects user privacy settings."""
    server_name = "test_server"

    # Add some test data
    drink_tracker.process_message(server_name, "alice", "krak krak")

    # Opt alice out
    data_manager.set_user_opt_out(server_name, "alice", True)

    # Try to add more data - should be ignored
    drink_tracker.process_message(server_name, "alice", "krak krak")

    # Get stats - should only have the original data
    stats = drink_tracker.get_server_stats(server_name)
    alice_stats = drink_tracker.get_user_stats(server_name, "alice")

    assert stats["total_drink_words"] == 2, "Should only have original data"
    assert (
        alice_stats["total_drink_words"] == 2
    ), "No new data should be added for opted-out user"


def test_kraks_command_multiple_servers(drink_tracker):
    """Test !kraks command with multiple servers."""
    server1 = "server1"
    server2 = "server2"

    # Add data to both servers
    drink_tracker.process_message(server1, "alice", "krak krak")
    drink_tracker.process_message(server2, "bob", "narsk")

    # Get stats for each server
    stats1 = drink_tracker.get_server_stats(server1)
    stats2 = drink_tracker.get_server_stats(server2)

    # Should be separate
    assert stats1["total_drink_words"] == 2, "Server1 should have 2 drink words"
    assert stats2["total_drink_words"] == 1, "Server2 should have 1 drink word"

    # Global stats should show both
    global_stats = drink_tracker.get_global_stats()
    assert (
        global_stats["total_drink_words"] == 3
    ), "Global stats should show all drink words"


@pytest.mark.parametrize(
    "drink_word",
    [
        "krak",
        "kr1k",
        "kr0k",
        "narsk",
        "parsk",
        "tlup",
        "marsk",
        "tsup",
        "plop",
        "tsirp",
    ],
)
def test_kraks_command_drink_word_patterns(drink_tracker, drink_word):
    """Test !kraks command recognizes all drink word patterns."""
    server_name = "test_server"

    # Test individual drink word
    matches = drink_tracker.process_message(server_name, "testuser", drink_word)

    # Should recognize the drink word
    assert len(matches) == 1, f"Should recognize {drink_word} as a drink word"


def test_kraks_command_all_drink_word_patterns(drink_tracker):
    """Test !kraks command recognizes all drink word patterns together."""
    server_name = "test_server"

    # Test various drink words
    drink_words = [
        "krak",
        "kr1k",
        "kr0k",
        "narsk",
        "parsk",
        "tlup",
        "marsk",
        "tsup",
        "plop",
        "tsirp",
    ]

    for word in drink_words:
        drink_tracker.process_message(server_name, "testuser", word)

    # Get stats
    stats = drink_tracker.get_server_stats(server_name)
    breakdown = drink_tracker.get_drink_word_breakdown(server_name)

    # Should have recorded all drink words
    assert stats["total_drink_words"] == len(
        drink_words
    ), f"Should have recorded {len(drink_words)} drink words"
    assert len(breakdown) == len(
        drink_words
    ), f"Breakdown should have {len(drink_words)} different words"


def test_help_specific_irc_sends_lines_to_nick():
    from command_loader import process_irc_message

    notices = []

    def mock_notice(msg, irc=None, target=None):
        notices.append((target, msg))

    botf = {"notice_message": mock_notice}
    raw = ":tester!user@host PRIVMSG #test :!help ping"
    _run_help(process_irc_message, raw, botf)

    assert notices and all(t == "tester" for t, _ in notices)
    assert any("ping" in m.lower() for _, m in notices)


@pytest.mark.parametrize(
    "word,expected_normalized",
    [
        ("KRAK", "krak"),
        ("krak", "krak"),
        ("Krak", "krak"),
        ("KrAk", "krak"),
    ],
)
def test_kraks_command_case_insensitive(drink_tracker, word, expected_normalized):
    """Test !kraks command is case insensitive."""
    server_name = "test_server"

    # Add data with different cases
    drink_tracker.process_message(server_name, "alice", "KRAK")
    drink_tracker.process_message(server_name, "bob", "krak")
    drink_tracker.process_message(server_name, "charlie", "Krak")

    # Get breakdown
    breakdown = drink_tracker.get_drink_word_breakdown(server_name)

    # Should all be counted as the same word
    assert len(breakdown) == 1, "All case variations should be counted as one word"
    assert breakdown[0][0] == "krak", "Should be normalized to lowercase"
    assert breakdown[0][1] == 3, "Total count should be 3"


def test_kraks_command_mixed_messages(drink_tracker):
    """Test !kraks command with mixed drink and non-drink content."""
    server_name = "test_server"

    # Add messages with mixed content
    drink_tracker.process_message(
        server_name, "alice", "Hello everyone, krak! How are you?"
    )
    drink_tracker.process_message(server_name, "bob", "Just had a beer, narsk narsk!")
    drink_tracker.process_message(
        server_name, "charlie", "No drinks here, just chatting"
    )

    # Get stats
    stats = drink_tracker.get_server_stats(server_name)
    breakdown = drink_tracker.get_drink_word_breakdown(server_name)

    # Should only count the drink words
    assert (
        stats["total_drink_words"] == 3
    ), "Should count only drink words from mixed messages"
    assert len(breakdown) == 2, "Should have krak and narsk"


def test_kraks_command_user_stats_detail(drink_tracker):
    """Test detailed user statistics for !kraks command."""
    server_name = "test_server"

    # Add varied data for one user
    drink_tracker.process_message(server_name, "alice", "krak krak")
    drink_tracker.process_message(server_name, "alice", "narsk")
    drink_tracker.process_message(server_name, "alice", "krak (Karhu)")

    # Get detailed user stats
    alice_stats = drink_tracker.get_user_stats(server_name, "alice")

    # Verify detailed breakdown
    assert (
        alice_stats["total_drink_words"] == 4
    ), "Alice should have 4 total drink words"
    assert "krak" in alice_stats["drink_words"], "Alice should have krak words"
    assert "narsk" in alice_stats["drink_words"], "Alice should have narsk words"


# =========================
# Leets command tests
# =========================


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


# =========================
# Solarwind command tests
# =========================


class TestSolarWindCommand:
    """Test cases for the solarwind command."""

    def test_solarwind_command_irc_context(self):
        """Test solarwind command in IRC context."""
        # Create IRC context
        context = CommandContext(
            command="solarwind",
            args=[],
            raw_message="!solarwind",
            sender="testuser",
            target="#testchannel",
            is_console=False,
            is_private=False,
        )

        bot_functions = {}

        # Execute command
        result = solarwind_command(context, bot_functions)

        # Verify result
        assert isinstance(result, str)
        if "❌" not in result:
            assert "Solar Wind" in result
            assert "Density:" in result
            assert "Speed:" in result
            assert "Temperature:" in result
            assert "Magnetic Field:" in result
            assert "🌌" in result
        else:
            # Accept graceful error in offline or API-failure environments
            assert "Solar" in result or "solar" in result

    def test_solarwind_command_console_context(self):
        """Test solarwind command in console context."""
        # Create console context
        context = CommandContext(
            command="solarwind",
            args=[],
            raw_message="!solarwind",
            sender=None,
            target=None,
            is_console=True,
            is_private=False,
        )

        bot_functions = {}

        # Execute command
        result = solarwind_command(context, bot_functions)

        # Verify result
        assert isinstance(result, str)
        if "❌" not in result:
            assert "Solar Wind" in result
            assert "Density:" in result
            assert "Speed:" in result
            assert "Temperature:" in result
            assert "Magnetic Field:" in result
            assert "🌌" in result
        else:
            # Accept graceful error in offline or API-failure environments
            assert "Solar" in result or "solar" in result

    @patch("services.solarwind_service.requests.get")
    def test_solarwind_command_api_error(self, mock_get):
        """Test solarwind command when API fails."""
        # Mock API failure
        mock_get.side_effect = Exception("API connection failed")

        context = CommandContext(
            command="solarwind",
            args=[],
            raw_message="!solarwind",
            sender="testuser",
            target="#testchannel",
            is_console=False,
            is_private=False,
        )

        bot_functions = {}

        # Execute command
        result = solarwind_command(context, bot_functions)

        # Verify error handling
        assert isinstance(result, str)
        assert "❌" in result
        assert "Solar wind error" in result or "Solar Wind Error" in result

    def test_solarwind_service_directly(self):
        """Test the solar wind service directly."""
        from services.solarwind_service import get_solar_wind_info

        result = get_solar_wind_info()

        # Verify result format
        assert isinstance(result, str)
        if "❌" not in result:  # If no error
            assert "Solar Wind" in result
            assert "Density:" in result
            assert "Speed:" in result
            assert "Temperature:" in result
            assert "Magnetic Field:" in result
            assert "🌌" in result


# =========================
# IRC !help command tests
# =========================


def _run_help(process_irc_message, raw_text, bot_functions):
    irc = DummyIrc()
    process_irc_message(irc, raw_text, bot_functions)
    return irc


def test_help_sends_private_to_nick_and_has_no_duplicates():
    from command_loader import process_irc_message

    notices = []

    def mock_notice(msg, irc=None, target=None):
        notices.append((target, msg))

    # Minimal bot_functions for routing
    bot_functions = {
        "notice_message": mock_notice,
        "log": lambda msg, level="INFO": None,
    }

    # Simulate IRC channel command invoking !help
    # :nick!user@host PRIVMSG #chan :!help
    raw = ":tester!user@host PRIVMSG #test :!help"

    irc = _run_help(process_irc_message, raw, bot_functions)

    # Ensure we sent something
    assert notices, "!help should produce NOTICE lines"

    # All targets should be the caller nick (private), not the channel
    targets = {t for t, _ in notices}
    assert targets == {"tester"} or (
        len(targets) == 1 and next(iter(targets)) == "tester"
    ), f"Expected notices to be sent to the nick 'tester', got targets: {targets}"

    # Extract message lines and check no duplicates (excluding footer blank lines)
    lines = [msg.strip() for _, msg in notices if msg and msg.strip()]
    # The header line must appear exactly once
    assert lines[0].startswith("Available commands:"), "First line should be the header"
    # help itself must not be present
    assert not any(
        line.startswith("help") for line in lines
    ), "!help should not list itself"

    # Check duplicates ignoring the header
    body = lines[1:]
    assert len(body) == len(set(body)), "Duplicate command lines found in !help output"


# =========================
# Scheduled message service tests
# =========================


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


# =========================
# IPFS service tests
# =========================


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
