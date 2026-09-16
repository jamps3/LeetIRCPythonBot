"""
Tests for games commands in cmd_modules/games.py
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


class TestKolikkoCommand:
    """Tests for the !kolikko (coin) command."""

    def test_kolikko_command_exists(self):
        """Test kolikko command is registered."""
        from cmd_modules.games import kolikko_command

        assert callable(kolikko_command)


class TestNoppaCommand:
    """Tests for the !noppa (dice) command."""

    def test_noppa_command_exists(self):
        """Test noppa command is registered."""
        from cmd_modules.games import noppa_command

        assert callable(noppa_command)

    def test_noppa_console(self, console_context, mock_bot_functions):
        """Test noppa command from console."""
        from cmd_modules.games import noppa_command

        console_context.command = "noppa"
        result = noppa_command(console_context, mock_bot_functions)
        assert result is not None
        # Should contain a number between 1-6
        assert any(str(i) in result for i in range(1, 7))


class TestKspCommand:
    """Tests for the !ksp (rock paper scissors) command."""

    def test_ksp_command_exists(self):
        """Test ksp command is registered."""
        from cmd_modules.games import ksp_command

        assert callable(ksp_command)


class TestBlackjackCommand:
    """Tests for the !blackjack command."""

    def test_blackjack_command_exists(self):
        """Test blackjack command is registered."""
        from cmd_modules.games import blackjack_command

        assert callable(blackjack_command)


class TestSanaketjuCommand:
    """Tests for the !sanaketju (word chain) command."""

    def test_sanaketju_command_exists(self):
        """Test sanaketju command is registered."""
        from cmd_modules.games import sanaketju_command

        assert callable(sanaketju_command)


def _context(*args, sender="alice", server_name="discord:1"):
    return CommandContext(
        command="game",
        args=list(args),
        raw_message="!game " + " ".join(args),
        sender=sender,
        target="#games",
        server_name=server_name,
        platform="discord",
        channel_id="games",
    )


def test_card_hand_deck_and_game_scope_helpers():
    from cmd_modules.games import (
        Card,
        CardRank,
        CardSuit,
        Deck,
        Hand,
        _game_key,
        get_blackjack_game,
    )

    assert Card(CardSuit.HEARTS, CardRank.ACE).value == 11
    assert Card(CardSuit.CLUBS, CardRank.KING).value == 10
    hand = Hand(
        [Card(CardSuit.SPADES, CardRank.ACE), Card(CardSuit.CLUBS, CardRank.NINE)]
    )
    assert hand.value == 20
    hand.add_card(Card(CardSuit.HEARTS, CardRank.FIVE))
    assert hand.value == 15
    hand.add_card(Card(CardSuit.DIAMONDS, CardRank.KING))
    assert hand.is_bust is True
    assert Hand(
        [Card(CardSuit.SPADES, CardRank.ACE), Card(CardSuit.CLUBS, CardRank.KING)]
    ).is_blackjack
    deck = Deck()
    assert len(deck.cards) == 52
    assert isinstance(deck.draw(), Card)
    deck.cards = []
    with pytest.raises(ValueError):
        deck.draw()
    assert _game_key(_context(), {}) == "discord:1:#games"
    assert get_blackjack_game("discord:1:#games") is get_blackjack_game(
        "discord:1:#games"
    )


def test_simple_game_commands_cover_validation_and_outcomes(monkeypatch):
    import cmd_modules.games as games

    monkeypatch.setattr(games.secure_random, "choice", lambda values: values[0])
    monkeypatch.setattr(games.secure_random, "randint", lambda start, end: end)
    assert games.kolikko_command(_context(), {}) == "Kruuna"
    assert games.kolikko_command(_context("kruuna"), {}) == "Kruuna. Voitit!"
    assert (
        games.kolikko_command(_context("nope"), {})
        == "Virheellinen valinta. Käytä: kruuna tai klaava"
    )
    assert games.noppa_command(_context(), {}) == "Käyttö: !noppa <NdS> (esim. 2d6)"
    assert (
        games.noppa_command(_context("bad"), {})
        == "Virheellinen noppaformaatti. Käytä: NdS (esim. 2d6)"
    )
    assert (
        games.noppa_command(_context("0d6"), {})
        == "Noppien määrä pitää olla 1-20 välillä."
    )
    assert (
        games.noppa_command(_context("1d101"), {})
        == "Sivujen määrä pitää olla 2-100 välillä."
    )
    assert games.noppa_command(_context("2d6"), {}) == "alice heitti: 6 + 6 = 12"

    data = Mock()
    monkeypatch.setattr(games, "_get_data_manager", lambda: data)
    data.load_ksp_state.return_value = None
    assert (
        games.ksp_command(_context("kivi"), {})
        == "Peli aloitettu: kivi pelaajalta alice"
    )
    data.load_ksp_state.return_value = {"sender": "alice", "choice": "kivi"}
    assert (
        games.ksp_command(_context("paperi"), {})
        == "Valinta vaihdettu: paperi (aiempi: kivi)"
    )
    data.load_ksp_state.return_value = {"sender": "bob", "choice": "kivi"}
    assert (
        games.ksp_command(_context("paperi"), {}) == "alice voitti bob: paperi vs kivi"
    )
    assert "Virheellinen valinta" in games.ksp_command(_context("bad"), {})


def test_sanaketju_game_persists_state_and_scores_words(monkeypatch):
    from cmd_modules.games import SanaketjuGame

    data = Mock()
    data.load_general_words_data.return_value = {
        "servers": {"discord": {"nicks": {"alice": {"general_words": {"sauna": 2}}}}}
    }
    game = SanaketjuGame()
    monkeypatch.setattr("cmd_modules.games.secure_random.choice", lambda words: "sauna")
    assert game.start_game("#games", data, "discord:#games") == "sauna"
    assert game.process_word("auto", "bob", data, "discord:#games") == {
        "valid": True,
        "word": "auto",
        "score": 4,
        "total_score": 4,
        "chain_length": 2,
    }
    assert game.process_word("auto", "bob", data, "discord:#games") is None
    assert game.process_word("bad!", "bob", data, "discord:#games") is None
    assert "Nykyinen sana: auto" in game.get_status()
    assert game.toggle_add("Bob") is True
    assert game.toggle_add("Bob") is False
    assert "Voittanut: bob (4 pistettä)" in game.end_game(data, "discord:#games")
    assert game.end_game(data, "discord:#games") is None


def test_blackjack_game_turns_status_and_results_without_timers(monkeypatch):
    import cmd_modules.games as games

    class Timer:
        def __init__(self, *_args):
            self.daemon = False

        def start(self):
            pass

        def cancel(self):
            pass

    monkeypatch.setattr(games.threading, "Timer", Timer)
    game = games.BlackjackGame()
    game.start_game("alice", "#games")
    assert game.state == games.GameState.JOINING
    assert "Joining phase. Players: alice" in game.get_status()
    assert game.join_player("bob") is True
    assert game.join_player("bob") is False
    assert game.leave_player("nobody") is False
    assert game.deal_cards("nobody") is False
    assert game.deal_cards("alice") is True
    assert game.state == games.GameState.PLAYING
    assert "Current turn: alice" in game.get_status()
    assert "Your turn" in game.get_player_hand("alice")
    assert game.player_hit("bob") is None
    assert game.player_stand("alice") is True
    assert game.player_stand("alice") is False
    assert game.player_stand("bob") is True
    assert game.state == games.GameState.DEALER_TURN
    results = game.end_game()
    assert set(results) == {"alice", "bob"}
    assert game.state == games.GameState.IDLE
    assert game.get_status() == "No active blackjack game."


def test_blackjack_result_outcomes_and_command_basics(monkeypatch):
    import cmd_modules.games as games

    game = games.BlackjackGame()
    game.state = games.GameState.PLAYING
    game.players["bust"] = games.Hand(
        [games.Card(games.CardSuit.SPADES, games.CardRank.KING)] * 3
    )
    game.players["bust"].is_bust = True
    game.players["winner"] = games.Hand(
        [
            games.Card(games.CardSuit.SPADES, games.CardRank.TEN),
            games.Card(games.CardSuit.HEARTS, games.CardRank.NINE),
        ]
    )
    game.players["tie"] = games.Hand(
        [
            games.Card(games.CardSuit.SPADES, games.CardRank.TEN),
            games.Card(games.CardSuit.HEARTS, games.CardRank.SEVEN),
        ]
    )
    game.dealer_hand = games.Hand(
        [
            games.Card(games.CardSuit.CLUBS, games.CardRank.TEN),
            games.Card(games.CardSuit.DIAMONDS, games.CardRank.SEVEN),
        ]
    )
    results = game.end_game()
    assert results["bust"].startswith("BUST")
    assert results["winner"].startswith("VOITTO")
    assert results["tie"].startswith("TASAPELI")

    key = games._game_key(_context(), {})
    games._blackjack_games.pop(key, None)
    assert (
        games.blackjack_command(_context(), {})
        == "Usage: !blackjack <start|join|leave|deal|hit|stand|status>"
    )
    assert "Unknown subcommand" in games.blackjack_command(_context("nope"), {})
    assert (
        games.blackjack_command(_context("join"), {})
        == "No blackjack game is currently accepting joins."
    )
