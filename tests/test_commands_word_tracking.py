"""
Tests for word_tracking commands in cmd_modules/word_tracking.py
"""

import os
import sys
from unittest.mock import Mock, patch

import pytest

# Add src to path before importing project modules
_TEST_ROOT = os.path.dirname(os.path.abspath(__file__))
if _TEST_ROOT not in sys.path:
    sys.path.insert(0, os.path.join(_TEST_ROOT, "..", "src"))

from command_registry import CommandContext  # noqa: E402


@pytest.fixture
def mock_bot_functions():
    """Create mock bot functions for testing commands."""
    return {
        "log": Mock(),
        "notice_message": Mock(),
    }


@pytest.fixture
def console_context():
    """Create a mock CommandContext for console commands."""
    return CommandContext(
        command="",
        args=[],
        raw_message="!test",
        sender=None,
        target=None,
        is_private=False,
        is_console=True,
        server_name="console",
    )


@pytest.fixture
def irc_context():
    """Create a mock CommandContext for IRC commands."""
    return CommandContext(
        command="",
        args=[],
        raw_message="!test",
        sender="TestUser",
        target="#test",
        is_private=False,
        is_console=False,
        server_name="TestServer",
    )


class TestTopwordsCommand:
    """Tests for the !topwords command."""

    def test_topwords_command_exists(self):
        """Test topwords command is registered."""
        from cmd_modules.word_tracking import topwords_command

        assert callable(topwords_command)


class TestLeaderboardCommand:
    """Tests for the !leaderboard command."""

    def test_leaderboard_command_exists(self):
        """Test leaderboard command is registered."""
        from cmd_modules.word_tracking import leaderboard_command

        assert callable(leaderboard_command)


class TestDrinkwordCommand:
    """Tests for the !drinkword command."""

    def test_drinkword_command_exists(self):
        """Test drinkword command is registered."""
        from cmd_modules.word_tracking import drinkword_command

        assert callable(drinkword_command)


class TestDrinkCommand:
    """Tests for the !drink command."""

    def test_drink_command_exists(self):
        """Test drink command is registered."""
        from cmd_modules.word_tracking import drink_command

        assert callable(drink_command)


class TestKraksCommand:
    """Tests for the !kraks command."""

    def test_kraks_command_exists(self):
        """Test kraks command is registered."""
        from cmd_modules.word_tracking import kraks_command

        assert callable(kraks_command)


class TestTamagotchiCommand:
    """Tests for the !tamagotchi command."""

    def test_tamagotchi_command_exists(self):
        """Test tamagotchi command is registered."""
        from cmd_modules.word_tracking import tamagotchi_command

        assert callable(tamagotchi_command)


class TestFeedCommand:
    """Tests for the !feed command."""

    def test_feed_command_exists(self):
        """Test feed command is registered."""
        from cmd_modules.word_tracking import feed_command

        assert callable(feed_command)


class TestPetCommand:
    """Tests for the !pet command."""

    def test_pet_command_exists(self):
        """Test pet command is registered."""
        from cmd_modules.word_tracking import pet_command

        assert callable(pet_command)


class TestKrakCommand:
    """Tests for the !krak command."""

    def test_krak_command_exists(self):
        """Test krak command is registered."""
        from cmd_modules.word_tracking import krak_command

        assert callable(krak_command)


class TestSanaCommand:
    """Tests for the !sana (word) command."""

    def test_sana_command_exists(self):
        """Test sana command is registered."""
        from cmd_modules.word_tracking import sana_command

        assert callable(sana_command)


class TestAssocCommand:
    """Tests for the !assoc (association) command."""

    def test_assoc_command_exists(self):
        """Test assoc command is registered."""
        from cmd_modules.word_tracking import assoc_command

        assert callable(assoc_command)


class TestMuunnosCommand:
    """Tests for the !muunnos (transformation) command."""

    def test_muunnos_command_exists(self):
        """Test muunnos command is registered."""
        from cmd_modules.word_tracking import muunnos_command

        assert callable(muunnos_command)


class TestKrakstatsCommand:
    """Tests for the !krakstats command."""

    def test_krakstats_command_exists(self):
        """Test krakstats command is registered."""
        from cmd_modules.word_tracking import krakstats_command

        assert callable(krakstats_command)


class TestKraksdebugCommand:
    """Tests for the !kraksdebug command."""

    def test_kraksdebug_command_exists(self):
        """Test kraksdebug command is registered."""
        from cmd_modules.word_tracking import kraksdebug_command

        assert callable(kraksdebug_command)
