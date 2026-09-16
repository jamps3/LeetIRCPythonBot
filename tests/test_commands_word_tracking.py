"""
Tests for word_tracking commands in cmd_modules/word_tracking.py
"""

import json
import os
import sys
from unittest.mock import ANY, Mock, patch

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


def _context(*args, sender="alice", server_name="discord:1"):
    return CommandContext(
        command="test",
        args=list(args),
        raw_message="!test " + " ".join(args),
        sender=sender,
        target="#10",
        server_name=server_name,
        platform="discord",
        channel_id="10",
    )


def test_topwords_uses_explicit_scope_and_aggregates_unscoped_servers():
    from cmd_modules.word_tracking import command_topwords

    words = Mock()
    words.get_server_stats.side_effect = lambda server: {
        "top_words": [("sauna", 2), ("beer", 1)] if server == "one" else [("sauna", 3)]
    }
    data_manager = Mock()
    data_manager.get_all_servers.return_value = ["one", "two"]

    assert (
        command_topwords(
            _context("2", server_name="console"),
            {"general_words": words, "data_manager": data_manager},
        )
        == "Top 2 sanat: sauna: 5, beer: 1"
    )

    words.get_user_stats.side_effect = lambda server, nick: {
        "total_words": 2 if server == "two" and nick == "Alice" else 0
    }
    words.get_user_top_words.return_value = [{"word": "sauna", "count": 2}]
    assert (
        command_topwords(
            _context("Alice", "5", server_name="console"),
            {"general_words": words, "data_manager": data_manager},
        )
        == "Alice@two: sauna: 2"
    )


def test_leaderboards_select_word_or_drink_tracker():
    from cmd_modules.word_tracking import command_leaderboard

    words = Mock()
    words.get_leaderboard.return_value = [{"nick": "alice", "total_words": 7}]
    drink = Mock()
    drink.get_server_stats.return_value = {"top_users": [("bob", 4)]}

    assert (
        command_leaderboard(
            _context("words"), {"general_words": words, "drink_tracker": drink}
        )
        == "Sanatilasto: alice:7"
    )
    assert (
        command_leaderboard(
            _context(), {"general_words": words, "drink_tracker": drink}
        )
        == "Juomaleaderi: bob:4"
    )


def test_drinkword_and_drink_commands_validate_and_format_results():
    from cmd_modules.word_tracking import command_drink, command_drinkword

    tracker = Mock()
    assert command_drinkword(_context(), {"drink_tracker": tracker}) == (
        "Käyttö: !drinkword <word> [drink_name]"
    )
    assert command_drinkword(_context("krak"), {"drink_tracker": tracker}) == (
        "Käyttö: !drinkword <word> <drink_name>"
    )
    tracker.add_drink_word_mapping.return_value = True
    assert (
        command_drinkword(_context("krak", "Karhu"), {"drink_tracker": tracker})
        == "✅ Lisätty: krak -> Karhu"
    )
    tracker.add_drink_word_mapping.assert_called_once_with("krak", "Karhu", "discord:1")

    tracker.search_specific_drink.return_value = {
        "total_occurrences": 3,
        "drink_words": {"krak": 3},
        "users": [{"nick": "alice", "total": 3}],
    }
    assert command_drink(_context("Karhu"), {"drink_tracker": tracker}) == (
        ", krak:3, top: alice:3"
    )
    tracker.search_specific_drink.return_value = {"total_occurrences": 0}
    assert command_drink(_context("missing"), {"drink_tracker": tracker}) == (
        "Ei osumia juomalle 'missing'."
    )


def test_kraks_resets_bac_or_formats_breakdown(monkeypatch):
    import cmd_modules.word_tracking as commands

    tracker = Mock()
    tracker.get_server_stats.return_value = {"total_drink_words": 3}
    tracker.get_drink_word_breakdown.return_value = [("krak", 3, "alice")]
    monkeypatch.setattr(commands, "_get_statistics_start_date", lambda: "01.01.2026")
    bac_tracker = Mock()

    assert (
        commands.command_kraks(_context("reset"), {"bac_tracker": bac_tracker})
        == "✅ BAC resetoitu käyttäjälle alice"
    )
    bac_tracker.reset_user_bac.assert_called_once_with("discord:1", "alice")
    assert commands.command_kraks(_context(), {"drink_tracker": tracker}) == (
        "Krakit yhteensä: 3, krak: 3 [alice] (since 01.01.2026)"
    )


def test_tamagotchi_commands_delegate_status_feed_and_pet():
    import cmd_modules.word_tracking as commands

    pet = Mock()
    pet.get_status.return_value = "happy"
    pet.feed.return_value = "fed"
    pet.pet.return_value = "purr"

    assert commands.command_tamagotchi(_context(), {"tamagotchi": pet}) == "happy"
    assert (
        commands.command_tamagotchi(_context("feed", "berry"), {"tamagotchi": pet})
        == "fed"
    )
    assert commands.command_tamagotchi(_context("play"), {"tamagotchi": pet}) == "purr"
    assert commands.command_tamagotchi(_context("unknown"), {"tamagotchi": pet}) == (
        "Käyttö: !tamagotchi [status|feed|play|stats]"
    )
    assert commands.command_feed(_context("cake"), {"tamagotchi": pet}) == "fed"
    assert commands.command_pet(_context(), {"tamagotchi": pet}) == "purr"
    pet.feed.assert_any_call("discord:1", "berry")
    pet.feed.assert_any_call("discord:1", "cake")


def test_krak_validates_profiles_and_formats_bac_information():
    from cmd_modules.word_tracking import command_krak

    tracker = Mock()
    tracker.get_user_bac.return_value = {
        "current_bac": 0.42,
        "sober_time": "2h",
        "driving_time": "1h",
    }
    tracker.get_user_profile.return_value = {"burn_rate": 0.15}
    tracker._load_bac_data.return_value = {
        "discord:1:alice": {"last_drink_grams": 12.5}
    }

    response = command_krak(_context("70", "m"), {"bac_tracker": tracker})

    tracker.set_user_profile.assert_called_once_with(
        "discord:1", "alice", weight_kg=70.0, sex="m"
    )
    assert "✅ Set profile: 70.0kg, M" in response
    assert "Promilles: 0.42‰" in response
    assert "Last: 12.5g" in response
    assert "Burn rate: 0.15‰/h" in response
    assert command_krak(_context("70", "x"), {"bac_tracker": tracker}) == (
        "❌ Invalid sex. Use 'm' or 'f'"
    )
    assert command_krak(_context("1.5"), {"bac_tracker": tracker}) == (
        "❌ Burn rate must be between 0.05 and 1.0 ‰/h"
    )


def test_assoc_handles_lookup_search_add_and_delete():
    from cmd_modules.word_tracking import command_assoc

    associations = Mock()
    functions = {"word_associations": associations}

    assert (
        command_assoc(_context(), functions)
        == "Käyttö: !assoc <sana> [-sana | -add | -del | -list]"
    )
    associations.get_association.return_value = ["löyly"]
    assert command_assoc(_context("Sauna"), functions) == "sauna: löyly"
    assert command_assoc(_context("sauna", "-list"), functions) == "Assosiaatiot: löyly"

    associations.get_association.return_value = []
    associations.search_associations.return_value = {"saunailta": ["kalja"]}
    assert command_assoc(_context("sauna"), functions) == "saunailta: kalja"
    associations.search_associations.return_value = {}
    assert (
        command_assoc(_context("sauna"), functions)
        == "Assosiaatioita sanalle 'sauna' ei löytynyt."
    )

    associations.add_association.return_value = True
    assert (
        command_assoc(_context("sauna", "-add", "löyly"), functions)
        == "Assosiaatio 'sauna' -> '-add löyly' lisätty."
    )
    associations.delete_association.return_value = True
    assert (
        command_assoc(_context("sauna", "-del"), functions)
        == "Assosiaatiot sanalle 'sauna' poistettu."
    )


def test_transform_phrase_covers_syllables_and_phrase_shapes(monkeypatch):
    import lemmatizer
    from cmd_modules.word_tracking import _find_first_syllable, transform_phrase

    assert _find_first_syllable("") == ("", "")
    assert _find_first_syllable("aamu") == ("a", "amu")
    assert _find_first_syllable("sauna") == ("sa", "una")
    assert _find_first_syllable("kello") == ("ke", "llo")
    assert _find_first_syllable("rhythm") == ("ry", "ythm")
    assert transform_phrase("kala maja") == "mala kaja"
    assert transform_phrase("kala ja maja") == "mala ja kaja"
    assert transform_phrase("kala kassa maja") == "mala kassa kaja"
    assert transform_phrase("kala testi sana") == "tela kasti sana"
    assert transform_phrase("kala sana testi koti") == "kola sana testi kati"
    assert transform_phrase("a") == "a"

    monkeypatch.setattr(
        lemmatizer, "analyze_word", lambda word: word in {"talo", "kala"}
    )
    assert transform_phrase("talokala") == "kalotala"
    monkeypatch.setattr(lemmatizer, "analyze_word", lambda word: False)
    assert transform_phrase("talokala") == "talokala"


def test_muunnos_command_reads_searches_adds_and_sends_notices(monkeypatch, tmp_path):
    import cmd_modules.word_tracking as commands

    data_file = tmp_path / "muunnokset.json"
    data_file.write_text('{"kala": "mala", "sauna": "nausa"}', encoding="utf-8")
    monkeypatch.setattr(commands, "SANANMUUNNOKSET_FILE", data_file)
    monkeypatch.setattr(commands.secure_random, "choice", lambda values: "kala")

    assert commands.muunnos_command(_context(), {}) == "kala - mala"
    assert commands.muunnos_command(_context("kala"), {}) == "kala - mala"
    assert (
        commands.muunnos_command(_context("ab"), {}) == "Liian lyhyt sana muunnokseen."
    )
    assert 'Hakutulokset termillä "a" (2/2):' in commands.muunnos_command(
        _context("search", "a"), {}
    )
    assert commands.muunnos_command(_context("search"), {}) == (
        "Usage: !muunnos search [-s] <term> - searches for transformations containing the term"
    )
    assert (
        commands.muunnos_command(_context("search", "zzz"), {})
        == 'Ei löydy muunnoksia termillä: "zzz"'
    )
    assert commands.muunnos_command(_context("s", "a"), {}).startswith("(2/2):")
    assert commands.muunnos_command(_context("add", "only"), {}) == (
        'Usage: !muunnos add "original phrase" "transformed phrase"'
    )

    add_context = _context("add", '"uusi sana"', '"sana uusi"')
    assert (
        commands.muunnos_command(add_context, {})
        == '✅ Added transformation: "uusi sana" → "sana uusi"'
    )
    assert '"uusi sana": "sana uusi"' in data_file.read_text(encoding="utf-8")

    notices = Mock()
    irc_context = _context("kala")
    irc_context.platform = "irc"
    irc_context.is_console = False
    result = commands.muunnos_command(
        irc_context, {"notice_message": notices, "irc": object()}
    )
    assert result.should_respond is False
    notices.assert_called_once_with("kala - mala", ANY, "#10")


def test_krakstats_formats_recent_statistics_and_private_notice():
    from datetime import datetime

    from cmd_modules.word_tracking import krakstats_command

    now = datetime.now().isoformat()
    tracker = Mock()
    tracker.get_user_stats.return_value = {
        "total_drink_words": 2,
        "drink_words": {
            "krak": {
                "timestamps": [
                    {"time": now, "specific_drink": "Karhu"},
                    {"time": "not-a-date", "specific_drink": "Karhu"},
                ]
            }
        },
    }
    context = _context(sender="alice")
    context.is_console = True
    response = krakstats_command(context, {"drink_tracker": tracker})
    assert "Total kraks: 2 | Last 30 days: 1" in response
    assert "Drink types: Karhu: 1" in response

    notices = Mock()
    context.is_console = False
    result = krakstats_command(
        context, {"drink_tracker": tracker, "notice_message": notices, "irc": object()}
    )
    assert result.should_respond is False
    assert notices.call_count == 5


def test_word_tracking_empty_data_service_failures_and_fallbacks(monkeypatch):
    import cmd_modules.word_tracking as commands

    default = Mock(return_value="fallback")
    assert (
        commands._get_from_bot_functions({"value": "injected"}, "value", default)
        == "injected"
    )
    monkeypatch.setattr(commands, "general_words", "singleton")
    assert commands._get_from_bot_functions({}, "general_words", default) == "singleton"
    monkeypatch.setattr(commands, "general_words", None)
    assert commands._get_from_bot_functions({}, "unknown", default) == "fallback"

    words = Mock()
    words.get_server_stats.return_value = {"top_words": []}
    assert (
        commands.command_topwords(
            _context(), {"general_words": words, "data_manager": Mock()}
        )
        == "Ei vielä tilastoja saatavilla."
    )
    words.get_user_stats.return_value = {"total_words": 0}
    assert (
        commands.command_topwords(
            _context("nobody"), {"general_words": words, "data_manager": Mock()}
        )
        == "Käyttäjää 'nobody' ei löydy."
    )
    words.get_leaderboard.return_value = []
    assert (
        commands.command_leaderboard(_context("words"), {"general_words": words})
        == "Ei vielä sanatilastoja saatavilla."
    )
    drink = Mock()
    drink.get_server_stats.return_value = {"top_users": []}
    assert (
        commands.command_leaderboard(_context(), {"drink_tracker": drink})
        == "Ei vielä juomatilastoja saatavilla."
    )

    monkeypatch.setattr(commands, "_get_drink_tracker", lambda: None)
    assert (
        commands.command_drink(_context("beer"), {})
        == "Drink tracker ei ole käytettävissä."
    )
    assert (
        commands.command_drinkword(_context("beer", "Beer"), {})
        == "Drink tracker ei ole käytettävissä."
    )
    monkeypatch.setattr(commands, "_get_tamagotchi_bot", lambda: None)
    assert (
        commands.command_tamagotchi(_context(), {})
        == "Tamagotchi service is not available."
    )
    assert (
        commands.command_feed(_context(), {}) == "Tamagotchi service is not available."
    )
    assert (
        commands.command_pet(_context(), {}) == "Tamagotchi service is not available."
    )


def test_sana_kraks_krakstats_and_debug_edge_cases(monkeypatch):
    import cmd_modules.word_tracking as commands

    words = Mock()
    assert (
        commands.command_sana(_context(), {"general_words": words})
        == "Käyttö: !sana <sana>"
    )
    words.get_word_stats.side_effect = TypeError()
    words.search_word.return_value = {
        "total_occurrences": 1,
        "users": [{"nick": "alice"}],
    }
    assert (
        commands.command_sana(_context("Sauna"), {"general_words": words})
        == "'sauna': 1 kertaa (top: alice)"
    )

    tracker = Mock()
    tracker.get_server_stats.return_value = {"total_drink_words": 0}
    monkeypatch.setattr(commands, "_get_statistics_start_date", lambda: None)
    assert (
        commands.command_kraks(_context(), {"drink_tracker": tracker})
        == "Ei vielä krakkauksia tallennettuna."
    )
    assert (
        commands.command_kraks(_context("reset"), {}) == "❌ BAC tracker not available"
    )
    tracker.get_server_stats.return_value = {
        "total_drink_words": 2,
        "top_users": [("alice", 2)],
    }
    tracker.get_drink_word_breakdown.return_value = []
    assert "Top 5: alice:2" in commands.command_kraks(
        _context(), {"drink_tracker": tracker}
    )

    no_data = Mock()
    no_data.get_user_stats.return_value = {"total_drink_words": 0}
    assert (
        commands.krakstats_command(_context(), {"drink_tracker": no_data})
        == "Ei krakkauksia vielä tallennettuna käyttäjälle alice."
    )

    bac = Mock()
    bac.get_user_bac.return_value = {"current_bac": 0.0}
    bac.get_user_profile.return_value = {"burn_rate": 0}
    bac._load_bac_data.return_value = {"discord:1:bob": {"last_drink_grams": 4.0}}
    assert "bob's No BAC data yet. | Last: 4.0g" in commands.command_krak(
        _context("bob"), {"bac_tracker": bac}
    )
    assert commands.command_krak(
        _context("1", "m", "extra"), {"bac_tracker": bac}
    ).startswith("❌ Too many")

    manager = Mock()
    manager.load_kraksdebug_state.return_value = {"channels": [], "nicks": []}
    assert "#new added to" in commands.kraksdebug_command(
        _context("new"), {"data_manager": manager}
    )
    private = _context(sender="alice")
    private.target = "alice"
    assert "alice' added to" in commands.kraksdebug_command(
        private, {"data_manager": manager}
    )
    channel = _context()
    assert "now enabled" in commands.kraksdebug_command(
        channel, {"data_manager": manager}
    )


def test_statistics_dates_bac_variants_and_debug_removals(monkeypatch):
    import cmd_modules.word_tracking as commands

    data_manager = Mock()
    data_manager.load_drink_data.return_value = {
        "servers": {
            "discord:1": {
                "nicks": {
                    "alice": {
                        "drink_words": {
                            "krak": {
                                "timestamps": [
                                    {"time": "2026-02-03T12:00:00"},
                                    {"time": "2026-01-02T12:00:00"},
                                ]
                            }
                        }
                    }
                }
            }
        }
    }
    monkeypatch.setattr(commands, "_get_data_manager", lambda: data_manager)
    assert commands._get_statistics_start_date() == "02.01.2026"
    data_manager.load_drink_data.return_value = {"servers": {}}
    assert commands._get_statistics_start_date() is None

    bac = Mock()
    bac.get_user_bac.return_value = {"current_bac": 0.0}
    bac.get_user_profile.return_value = {"burn_rate": 0.2}
    bac._load_bac_data.return_value = {}
    assert (
        commands.command_krak(_context("0.2"), {"bac_tracker": bac})
        == "✅ Set burn rate: 0.2‰/h | Burn rate: 0.2‰/h"
    )
    assert (
        commands.command_krak(_context("heavy", "m"), {"bac_tracker": bac})
        == "❌ Invalid weight. Use a number for weight in kg"
    )
    assert commands.command_krak(_context(), {}) == "❌ BAC tracker not available"

    manager = Mock()
    manager.load_kraksdebug_state.return_value = {
        "channels": ["#test"],
        "nicks": ["alice"],
        "nick_notices": True,
    }
    assert "#test removed from" in commands.kraksdebug_command(
        _context("#test"), {"data_manager": manager}
    )
    private = _context(sender="alice")
    private.target = "alice"
    assert "alice' removed from" in commands.kraksdebug_command(
        private, {"data_manager": manager}
    )
    channel = _context()
    assert "now disabled" in commands.kraksdebug_command(
        channel, {"data_manager": manager}
    )


def test_muunnos_error_long_search_and_algorithmic_fallbacks(monkeypatch, tmp_path):
    import cmd_modules.word_tracking as commands

    missing = tmp_path / "missing.json"
    monkeypatch.setattr(commands, "SANANMUUNNOKSET_FILE", missing)
    assert "Virhe ladattaessa sananmuunnoksia" in commands.muunnos_command(
        _context(), {}
    )

    data_file = tmp_path / "muunnokset.json"
    transformations = {f"word{i:02d}{'x' * 50}": f"result{i}" for i in range(12)}
    data_file.write_text(json.dumps(transformations), encoding="utf-8")
    monkeypatch.setattr(commands, "SANANMUUNNOKSET_FILE", data_file)
    long_search = commands.muunnos_command(_context("s", "word"), {})
    assert long_search.endswith("[7]")
    full_search = commands.muunnos_command(_context("search", "word"), {})
    assert "... ja 2 lisää" in full_search
    assert commands.muunnos_command(_context("abcdef"), {}).startswith("abcdef - ")
    assert commands.muunnos_command(_context("kala", "maja"), {}).startswith(
        "kala maja - "
    )

    data_file.write_text("{}", encoding="utf-8")
    assert commands.muunnos_command(_context(), {}) == "Ei sananmuunnoksia saatavilla."
