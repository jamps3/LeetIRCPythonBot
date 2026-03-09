"""
Tests for service commands in cmd_modules/services.py
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


class TestWeatherCommand:
    """Tests for the !s (weather) command."""

    def test_s_command_exists(self):
        """Test s (weather) command is registered."""
        from cmd_modules.services import weather_command

        assert callable(weather_command)


class TestShortForecastCommand:
    """Tests for the !se (short forecast) command."""

    def test_se_command_exists(self):
        """Test se (short forecast) command is registered."""
        from cmd_modules.services import short_forecast_command

        assert callable(short_forecast_command)


class TestShortForecastListCommand:
    """Tests for the !sel (short forecast list) command."""

    def test_sel_command_exists(self):
        """Test sel (short forecast list) command is registered."""
        from cmd_modules.services import short_forecast_list_command

        assert callable(short_forecast_list_command)


class TestSolarwindCommand:
    """Tests for the !solarwind command."""

    def test_solarwind_command_exists(self):
        """Test solarwind command is registered."""
        from cmd_modules.services import solarwind_command

        assert callable(solarwind_command)


class TestOtiedoteCommand:
    """Tests for the !otiedote command."""

    def test_otiedote_command_exists(self):
        """Test otiedote command is registered."""
        from cmd_modules.services import otiedote_command

        assert callable(otiedote_command)


class TestElectricityCommand:
    """Tests for the !sahko (electricity) command."""

    def test_sahko_command_exists(self):
        """Test sahko command is registered."""
        from cmd_modules.services import electricity_command

        assert callable(electricity_command)


class TestEuriborCommand:
    """Tests for the !euribor command."""

    def test_euribor_command_exists(self):
        """Test euribor command is registered."""
        from cmd_modules.services import euribor_command

        assert callable(euribor_command)


class TestTrainsCommand:
    """Tests for the !junat (trains) command."""

    def test_junat_command_exists(self):
        """Test junat command is registered."""
        from cmd_modules.services import trains_command

        assert callable(trains_command)


class TestYoutubeCommand:
    """Tests for the !youtube command."""

    def test_youtube_command_exists(self):
        """Test youtube command is registered."""
        from cmd_modules.services import youtube_command

        assert callable(youtube_command)


class TestImdbCommand:
    """Tests for the !imdb command."""

    def test_imdb_command_exists(self):
        """Test imdb command is registered."""
        from cmd_modules.services import imdb_command

        assert callable(imdb_command)


class TestCryptoCommand:
    """Tests for the !crypto command."""

    def test_crypto_command_exists(self):
        """Test crypto command is registered."""
        from cmd_modules.services import crypto_command

        assert callable(crypto_command)


class TestLeetwinnersCommand:
    """Tests for the !leetwinners command."""

    def test_leetwinners_command_exists(self):
        """Test leetwinners command is registered."""
        from cmd_modules.services import leetwinners_command

        assert callable(leetwinners_command)


class TestEurojackpotCommand:
    """Tests for the !eurojackpot command."""

    def test_eurojackpot_command_exists(self):
        """Test eurojackpot command is registered."""
        from cmd_modules.services import command_eurojackpot

        assert callable(command_eurojackpot)


class TestAlkoCommand:
    """Tests for the !alko command."""

    def test_alko_command_exists(self):
        """Test alko command is registered."""
        from cmd_modules.services import alko_command

        assert callable(alko_command)


class TestDrugsCommand:
    """Tests for the !drugs command."""

    def test_drugs_command_exists(self):
        """Test drugs command is registered."""
        from cmd_modules.services import drugs_command

        assert callable(drugs_command)


class TestUrlCommand:
    """Tests for the !url command."""

    def test_url_command_exists(self):
        """Test url command is registered."""
        from cmd_modules.services import url_command

        assert callable(url_command)


class TestWrapCommand:
    """Tests for the !wrap command."""

    def test_wrap_command_exists(self):
        """Test wrap command is registered."""
        from cmd_modules.services import wrap_command

        assert callable(wrap_command)


class TestTilaaCommand:
    """Tests for the !tilaa (subscribe) command."""

    def test_tilaa_command_exists(self):
        """Test tilaa command is registered."""
        from cmd_modules.services import tilaa_command

        assert callable(tilaa_command)


class TestEcodeCommand:
    """Tests for the !ecode (E-codes) command."""

    def test_ecode_command_exists(self):
        """Test ecode command is registered."""
        from commands_services import ecode_command

        assert callable(ecode_command)
