"""
Games Commands Module

Contains game commands: blackjack, sanaketju, noppa, kolikko, ksp
"""

import random
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from command_registry import CommandContext, CommandResponse, command
from logger import get_logger

# Import needed items from commands.py for shared functionality
# These are lazily initialized to avoid issues
_data_manager = None

logger = get_logger(__name__)


# =====================
# Blackjack Game Classes
# =====================


class CardSuit(Enum):
    SPADES = "♠"
    CLUBS = "♣"
    HEARTS = "♥"
    DIAMONDS = "♦"


class CardRank(Enum):
    ACE = "A"
    TWO = "2"
    THREE = "3"
    FOUR = "4"
    FIVE = "5"
    SIX = "6"
    SEVEN = "7"
    EIGHT = "8"
    NINE = "9"
    TEN = "10"
    JACK = "J"
    QUEEN = "Q"
    KING = "K"


@dataclass
class Card:
    """A playing card with suit and rank."""

    suit: CardSuit
    rank: CardRank

    @property
    def value(self) -> int:
        """Get the numeric value of the card for blackjack."""
        if self.rank == CardRank.ACE:
            return 11  # Aces are 11 by default, can be reduced to 1
        elif self.rank in [CardRank.JACK, CardRank.QUEEN, CardRank.KING]:
            return 10
        else:
            return int(self.rank.value)

    def __str__(self) -> str:
        return f"{self.rank.value}{self.suit.value}"


@dataclass
class Hand:
    """A blackjack hand containing cards."""

    cards: List[Card] = field(default_factory=list)
    is_stand: bool = False
    is_bust: bool = False

    @property
    def value(self) -> int:
        """Calculate the total value of the hand, handling aces optimally."""
        total = 0
        aces = 0

        for card in self.cards:
            if card.rank == CardRank.ACE:
                aces += 1
                total += 11
            else:
                total += card.value

        # Convert aces from 11 to 1 if needed
        while total > 21 and aces > 0:
            total -= 10
            aces -= 1

        return total

    @property
    def is_blackjack(self) -> bool:
        """Check if this is a blackjack (21 with 2 cards)."""
        return len(self.cards) == 2 and self.value == 21

    def add_card(self, card: Card):
        """Add a card to the hand and check for bust."""
        self.cards.append(card)
        if self.value > 21:
            self.is_bust = True

    def __str__(self) -> str:
        card_strs = [str(card) for card in self.cards]
        return f"[{', '.join(card_strs)}] ({self.value})"


class Deck:
    """A standard 52-card deck."""

    def __init__(self):
        self.cards: List[Card] = []
        self.reset()

    def reset(self):
        """Reset and shuffle the deck."""
        self.cards = []
        for suit in CardSuit:
            for rank in CardRank:
                self.cards.append(Card(suit, rank))
        random.shuffle(self.cards)

    def draw(self) -> Card:
        """Draw a card from the deck."""
        if not self.cards:
            raise ValueError("Deck is empty")
        return self.cards.pop()


class GameState(Enum):
    """Blackjack game states."""

    IDLE = "idle"
    JOINING = "joining"
    PLAYING = "playing"
    DEALER_TURN = "dealer_turn"
    ENDED = "ended"


@dataclass
class BlackjackGame:
    """A blackjack game instance."""

    channel: str = ""
    server: Optional[Any] = None
    state: GameState = GameState.IDLE
    players: OrderedDict = field(default_factory=OrderedDict)
    dealer_hand: Hand = field(default_factory=Hand)
    deck: Deck = field(default_factory=Deck)
    current_turn_index: int = 0
    started_at: Optional[datetime] = None
    last_action_at: Optional[datetime] = None
    join_timer: Optional[threading.Timer] = None

    def start_game(self, starter: str, channel: str, server=None):
        """Start a new game in joining state."""
        self.channel = channel
        self.server = server
        self.state = GameState.JOINING
        self.players = OrderedDict()
        self.dealer_hand = Hand()
        self.deck.reset()
        self.current_turn_index = 0
        self.started_at = datetime.now()
        self.last_action_at = datetime.now()

        # Add the starter as first player
        self.players[starter] = Hand()

        # Start 5-minute join timer
        self.join_timer = threading.Timer(300.0, self._auto_deal)
        self.join_timer.start()

    def join_player(self, nick: str) -> bool:
        """Add a player to the game. Returns True if successful."""
        if self.state != GameState.JOINING:
            return False
        if nick in self.players:
            return False  # Already joined

        self.players[nick] = Hand()
        self.last_action_at = datetime.now()
        return True

    def leave_player(self, nick: str) -> bool:
        """Remove a player from the game. Returns True if successful."""
        if self.state != GameState.JOINING:
            return False
        if nick not in self.players:
            return False

        del self.players[nick]
        self.last_action_at = datetime.now()

        # If no players left, cancel the game
        if not self.players:
            self._cleanup()

        return True

    def deal_cards(self, dealer: str) -> bool:
        """Deal initial cards and start playing. Returns True if successful."""
        if self.state != GameState.JOINING:
            return False
        if dealer not in self.players:
            return False  # Only joined players can deal
        if len(self.players) < 1:
            return False

        # Cancel join timer
        if self.join_timer:
            self.join_timer.cancel()
            self.join_timer = None

        self.state = GameState.PLAYING
        self.last_action_at = datetime.now()

        # Deal 2 cards to each player
        for _ in range(2):
            for player_hand in self.players.values():
                player_hand.add_card(self.deck.draw())

        # Deal 2 cards to dealer (one face up, one face down)
        self.dealer_hand.add_card(self.deck.draw())
        self.dealer_hand.add_card(self.deck.draw())

        return True

    def player_hit(self, nick: str) -> Optional[Card]:
        """Player draws a card. Returns the card if successful."""
        if self.state != GameState.PLAYING:
            return None
        if nick not in self.players:
            return None

        player_names = list(self.players.keys())
        if player_names[self.current_turn_index] != nick:
            return None  # Not player's turn

        player_hand = self.players[nick]
        if player_hand.is_stand or player_hand.is_bust:
            return None  # Can't hit if stood or bust

        card = self.deck.draw()
        player_hand.add_card(card)
        self.last_action_at = datetime.now()

        # If bust or blackjack, auto-stand
        if player_hand.is_bust or player_hand.is_blackjack:
            player_hand.is_stand = True
            self._next_turn()

        return card

    def player_stand(self, nick: str) -> bool:
        """Player stands. Returns True if successful."""
        if self.state != GameState.PLAYING:
            return False
        if nick not in self.players:
            return False

        player_names = list(self.players.keys())
        if player_names[self.current_turn_index] != nick:
            return False  # Not player's turn

        player_hand = self.players[nick]
        if player_hand.is_stand or player_hand.is_bust:
            return False  # Already stood or bust

        player_hand.is_stand = True
        self.last_action_at = datetime.now()
        self._next_turn()
        return True

    def get_status(self, nick: str = None) -> str:
        """Get current game status."""
        if self.state == GameState.IDLE:
            return "No active blackjack game."

        if self.state == GameState.JOINING:
            players_list = ", ".join(self.players.keys())
            time_left = 300 - (datetime.now() - self.started_at).seconds
            return f"Joining phase. Players: {players_list}. Time left: {time_left}s"

        if self.state == GameState.PLAYING:
            player_names = list(self.players.keys())
            current_player = (
                player_names[self.current_turn_index]
                if self.current_turn_index < len(player_names)
                else "Unknown"
            )

            status_lines = []
            status_lines.append(f"Current turn: {current_player}")

            # Show dealer's visible card
            if self.dealer_hand.cards:
                dealer_visible = str(self.dealer_hand.cards[0])
                status_lines.append(f"Dealer: [{dealer_visible}, ?]")

            # Show all players' hands
            for player_nick, hand in self.players.items():
                status_lines.append(f"{player_nick}: {hand}")

            return "\n".join(status_lines)

        if self.state == GameState.DEALER_TURN:
            return "Dealer is playing..."

        if self.state == GameState.ENDED:
            return "Game has ended."

        return "Unknown game state."

    def get_player_hand(self, nick: str) -> Optional[str]:
        """Get a player's private hand information."""
        if nick not in self.players:
            return None

        hand = self.players[nick]

        if self.state == GameState.PLAYING:
            player_names = list(self.players.keys())
            is_current_turn = player_names[self.current_turn_index] == nick
            turn_status = " (Your turn)" if is_current_turn else ""
            return f"Your hand: {hand}{turn_status}"
        elif self.state == GameState.DEALER_TURN or self.state == GameState.ENDED:
            return f"Your final hand: {hand}"
        else:
            return f"Your hand: {hand}"

    def end_game(self) -> Dict[str, str]:
        """End the game and calculate results. Returns results dict."""
        if self.state not in [GameState.PLAYING, GameState.DEALER_TURN]:
            return {}

        self.state = GameState.ENDED

        # Dealer plays
        while self.dealer_hand.value < 17:
            self.dealer_hand.add_card(self.deck.draw())

        # Calculate results with hand information
        results = {}
        dealer_value = self.dealer_hand.value
        dealer_bust = self.dealer_hand.is_bust

        # Format dealer hand
        dealer_cards = [str(card) for card in self.dealer_hand.cards]
        dealer_hand_str = f"[{', '.join(dealer_cards)}] ({dealer_value})"

        for nick, hand in self.players.items():
            # Format player hand
            player_cards = [str(card) for card in hand.cards]
            player_hand_str = f"[{', '.join(player_cards)}] ({hand.value})"

            if hand.is_bust:
                results[nick] = f"BUST {player_hand_str} vs {dealer_hand_str}"
            elif hand.is_blackjack and not self.dealer_hand.is_blackjack:
                results[nick] = f"BLACKJACK {player_hand_str} vs {dealer_hand_str}"
            elif dealer_bust:
                results[nick] = f"VOITTO {player_hand_str} vs {dealer_hand_str}"
            elif hand.value > dealer_value:
                results[nick] = f"VOITTO {player_hand_str} vs {dealer_hand_str}"
            elif hand.value < dealer_value:
                results[nick] = f"HÄVIÖ {player_hand_str} vs {dealer_hand_str}"
            else:
                results[nick] = f"TASAPELI {player_hand_str} vs {dealer_hand_str}"

        self._cleanup()
        return results

    def _next_turn(self):
        """Advance to the next player's turn."""
        self.current_turn_index += 1
        player_names = list(self.players.keys())

        # Check if all players have finished
        active_players = [
            p for p in self.players.values() if not p.is_stand and not p.is_bust
        ]
        if not active_players:
            self.state = GameState.DEALER_TURN
            # Auto-end game after a short delay
            threading.Timer(2.0, self.end_game).start()

    def _auto_deal(self):
        """Automatically deal cards when join timer expires."""
        if self.state == GameState.JOINING and len(self.players) >= 1:
            self.deal_cards(list(self.players.keys())[0])

    def _cleanup(self):
        """Clean up the game."""
        self.state = GameState.IDLE
        if self.join_timer:
            self.join_timer.cancel()
            self.join_timer = None


# Global blackjack game instance
_blackjack_game = BlackjackGame()


def get_blackjack_game() -> BlackjackGame:
    """Get the global blackjack game instance."""
    return _blackjack_game


# =====================
# Lazy DataManager Getter
# =====================


def _get_data_manager():
    """Lazy getter for DataManager."""
    global _data_manager
    if _data_manager is None:
        from config import get_config
        from word_tracking import DataManager

        config = get_config()
        _data_manager = DataManager(state_file=config.state_file)
    return _data_manager


# =====================
# Kolikko (Coin flip) Command
# =====================


@command(
    "kolikko",
    description="Flip a coin",
    usage="!kolikko [kruuna|klaava]",
    examples=["!kolikko", "!kolikko kruuna"],
)
def kolikko_command(context: CommandContext, bot_functions):
    """Flip a coin and optionally check if user guessed correctly."""
    result = random.choice(["Kruuna", "Klaava"])

    if context.args:
        guess = context.args[0].lower()
        if guess in ["kruuna", "klaava"]:
            # Capitalize first letter for comparison
            normalized_result = result.lower()
            if guess == normalized_result:
                return f"{result}. Voitit!"
            else:
                return f"{result}. Hävisit."
        else:
            return "Virheellinen valinta. Käytä: kruuna tai klaava"
    else:
        return result


# =====================
# Noppa (Dice) Command
# =====================


@command(
    "noppa",
    description="Roll dice",
    usage="!noppa <NdS>",
    examples=["!noppa 2d6", "!noppa 1d20"],
    requires_args=True,
)
def noppa_command(context: CommandContext, bot_functions):
    """Roll dice in NdS format (e.g., 2d6 for two six-sided dice)."""
    if not context.args:
        return "Käyttö: !noppa <NdS> (esim. 2d6)"

    dice_spec = context.args[0].lower()

    match = re.match(r"^(\d+)d(\d+)$", dice_spec)
    if not match:
        return "Virheellinen noppaformaatti. Käytä: NdS (esim. 2d6)"

    num_dice = int(match.group(1))
    sides = int(match.group(2))

    if num_dice < 1 or num_dice > 20:
        return "Noppien määrä pitää olla 1-20 välillä."
    if sides < 2 or sides > 100:
        return "Sivujen määrä pitää olla 2-100 välillä."

    rolls = [random.randint(1, sides) for _ in range(num_dice)]
    total = sum(rolls)

    if num_dice == 1:
        return f"{context.sender} heitti: {rolls[0]}"
    else:
        roll_str = " + ".join(str(r) for r in rolls)
        return f"{context.sender} heitti: {roll_str} = {total}"


# =====================
# KSP (Rock-Paper-Scissors) Command
# =====================


@command(
    "ksp",
    description="Play rock-paper-scissors (kivi-sakset-paperi)",
    usage="!ksp <kivi|sakset|paperi>",
    examples=["!ksp kivi", "!ksp sakset", "!ksp paperi"],
    requires_args=True,
)
def ksp_command(context: CommandContext, bot_functions):
    """Play rock-paper-scissors game."""
    choice = context.args[0].lower()
    valid_choices = ["kivi", "sakset", "paperi"]
    if choice not in valid_choices:
        return f"Virheellinen valinta. Käytä: {', '.join(valid_choices)}"

    # Load current game state
    current_game = _get_data_manager().load_ksp_state()

    def determine_winner(c1, c2):
        if c1 == c2:
            return "tasapeli"
        wins = {"kivi": "sakset", "paperi": "kivi", "sakset": "paperi"}
        if wins[c1] == c2:
            return "player1"
        return "player2"

    if current_game is None:
        # Start new game
        game_state = {"choice": choice, "sender": context.sender}
        _get_data_manager().save_ksp_state(game_state)
        return f"Peli aloitettu: {choice} pelaajalta {context.sender}"
    else:
        player1_sender = current_game["sender"]
        player1_choice = current_game["choice"]
        player2_sender = context.sender
        player2_choice = choice

        if player1_sender == player2_sender:
            # Same player changing choice
            game_state = {"choice": choice, "sender": context.sender}
            _get_data_manager().save_ksp_state(game_state)
            return f"Valinta vaihdettu: {choice} (aiempi: {player1_choice})"

        # Different player, play the game
        winner = determine_winner(player1_choice, player2_choice)
        if winner == "tasapeli":
            result = f"Tasapeli: {player1_choice} vs {player2_choice}"
        elif winner == "player1":
            result = f"{player1_sender} voitti {player2_sender}: {player1_choice} vs {player2_choice}"
        else:
            result = f"{player2_sender} voitti {player1_sender}: {player2_choice} vs {player1_choice}"

        # Reset game
        _get_data_manager().save_ksp_state(None)
        return result


# =====================
# Blackjack Command
# =====================


@command(
    "blackjack",
    description="Play blackjack (subcommands: start, join, leave, deal, hit, stand, status)",
    usage="!blackjack <start|join|leave|deal|hit|stand|status>",
    examples=[
        "!blackjack start",
        "!blackjack join",
        "!blackjack hit",
        "!blackjack status",
    ],
)
def blackjack_command(context: CommandContext, bot_functions):
    """Main blackjack command with subcommands."""
    game = get_blackjack_game()

    if not context.args:
        return "Usage: !blackjack <start|join|leave|deal|hit|stand|status>"

    subcommand = context.args[0].lower()

    # Helper functions
    def send_private(msg: str, target: str = None):
        """Send a private message to a user."""
        if not target:
            target = context.sender
        notice = bot_functions.get("notice_message")
        irc = bot_functions.get("irc")
        if notice and irc:
            notice(msg, irc, target)

    def send_channel(msg: str):
        """Send a message to the game channel."""
        if game.channel and game.server:
            game.server.send_message(game.channel, msg)

    # Handle subcommands
    if subcommand == "start":
        if game.state != GameState.IDLE:
            return "A blackjack game is already active."

        game.start_game(
            context.sender,
            context.target or context.sender,
            bot_functions.get("server"),
        )

        # Announce in channel
        send_channel(
            f"Blackjack game started by {context.sender}! Join with !blackjack join (5min)"
        )

        # Confirm to starter privately
        send_private(
            "You started a blackjack game! Others can join with !blackjack join"
        )

        return CommandResponse.no_response()

    elif subcommand == "join":
        if game.state != GameState.JOINING:
            return "No blackjack game is currently accepting joins."

        if game.join_player(context.sender):
            send_private(
                f"You joined the blackjack game! Players: {', '.join(game.players.keys())}"
            )
            return CommandResponse.no_response()
        else:
            return "You are already in the game or joining is not allowed."

    elif subcommand == "leave":
        if game.state != GameState.JOINING:
            return "You can only leave during the joining phase."

        if game.leave_player(context.sender):
            send_private("You left the blackjack game.")
            return CommandResponse.no_response()
        else:
            return "You are not in the game."

    elif subcommand == "deal":
        if game.state != GameState.JOINING:
            return "Cards can only be dealt during the joining phase."

        if game.deal_cards(context.sender):
            # Send initial hands privately to all players
            dealer_visible = (
                str(game.dealer_hand.cards[0]) if game.dealer_hand.cards else "?"
            )
            for nick in game.players.keys():
                hand_str = game.get_player_hand(nick)
                send_private(f"{hand_str} | Dealer: {dealer_visible}", nick)

            return CommandResponse.no_response()
        else:
            return "Cannot deal cards right now."

    elif subcommand == "hit":
        if game.state != GameState.PLAYING:
            return "No active blackjack game."

        card = game.player_hit(context.sender)
        if card:
            player_hand = game.players[context.sender]
            # Create hand display without value for hit messages
            hand_cards = [str(c) for c in player_hand.cards]
            hand_display = f"[{', '.join(hand_cards)}]"

            hand_value = player_hand.value
            hand_with_count = f"{hand_display} ({hand_value})"

            if game.players[context.sender].is_bust:
                send_private(
                    f"You drew: {card} Hand: {hand_with_count}\n💥 You went bust!"
                )
                # Check if game should end
                active_players = [
                    p for p in game.players.values() if not p.is_stand and not p.is_bust
                ]
                if not active_players:
                    results = game.end_game()
                    if results:
                        result_str = " | ".join(
                            f"{nick} {result}" for nick, result in results.items()
                        )
                        send_channel(f"Blackjack results: {result_str}")
            else:
                send_private(f"You drew: {card} Hand: {hand_with_count}")

            return CommandResponse.no_response()
        else:
            return "It's not your turn or you cannot hit."

    elif subcommand == "stand":
        if game.state != GameState.PLAYING:
            return "No active blackjack game."

        if game.player_stand(context.sender):
            hand_str = game.get_player_hand(context.sender)
            send_private(f"You stand with: {hand_str}")

            # Check if game should end
            active_players = [
                p for p in game.players.values() if not p.is_stand and not p.is_bust
            ]
            if not active_players:
                results = game.end_game()
                if results:
                    result_str = " | ".join(
                        f"{nick} {result}" for nick, result in results.items()
                    )
                    send_channel(f"Blackjack results: {result_str}")

            return CommandResponse.no_response()
        else:
            return "It's not your turn or you cannot stand."

    elif subcommand == "status":
        status = game.get_status(context.sender)
        if context.is_console:
            return status
        else:
            send_private(status)
            return CommandResponse.no_response()

    else:
        return f"Unknown subcommand: {subcommand}. Use: start, join, leave, deal, hit, stand, status"


# =====================
# Sanaketju Game Class
# =====================


@dataclass
class SanaketjuGame:
    """A sanaketju (word chain) game instance."""

    active: bool = False
    channel: str = ""
    current_word: str = ""
    chain_length: int = 0
    participants: Dict[str, int] = field(default_factory=dict)  # nick -> total_score
    used_words: set = field(default_factory=set)
    start_time: Optional[datetime] = None
    notice_whitelist: set = field(default_factory=set)

    def start_game(self, channel: str, data_manager) -> Optional[str]:
        """Start a new game. Returns starting word or None if failed."""
        if self.active:
            return None

        # Get random starting word from collected words
        starting_word = self._get_random_starting_word(data_manager)
        if not starting_word:
            return None

        self.active = True
        self.channel = channel
        self.current_word = starting_word
        self.chain_length = 1
        self.participants = {}
        self.used_words = {starting_word.lower()}
        self.start_time = datetime.now()

        # Save state
        self._save_state(data_manager)
        return starting_word

    def _get_random_starting_word(self, data_manager) -> Optional[str]:
        """Get a random word from collected words for starting the game."""
        try:
            # Get all words from general words data
            general_data = data_manager.load_general_words_data()
            all_words = set()

            for server_data in general_data.get("servers", {}).values():
                for nick_data in server_data.get("nicks", {}).values():
                    all_words.update(nick_data.get("general_words", {}).keys())

            # Filter words: no special characters, max 30 chars
            valid_words = [
                word
                for word in all_words
                if len(word) <= 30 and word.isalpha() and len(word) >= 3
            ]

            if not valid_words:
                return None

            return random.choice(valid_words)

        except Exception as e:
            logger.error(f"Error getting random starting word: {e}")
            return None

    def process_word(
        self, word: str, nick: str, data_manager
    ) -> Optional[Dict[str, Any]]:
        """
        Process a potential word continuation.
        Returns dict with 'valid', 'score', 'total_score' if valid, None if invalid.
        """
        if not self.active:
            return None

        word = word.lower().strip()
        if not word or len(word) > 30 or not word.isalpha():
            return None

        # Check if word starts with last letter of current word
        if not self.current_word or word[0] != self.current_word[-1].lower():
            return None

        # Check if word has been used
        if word in self.used_words:
            return None

        # Valid word! Update game state
        self.current_word = word
        self.chain_length += 1
        self.used_words.add(word)

        # Update participant score
        score = len(word)
        if nick not in self.participants:
            self.participants[nick] = 0
        self.participants[nick] += score

        # Save state
        self._save_state(data_manager)

        return {
            "valid": True,
            "word": word,
            "score": score,
            "total_score": self.participants[nick],
            "chain_length": self.chain_length,
        }

    def toggle_add(self, nick: str, target_nick: Optional[str] = None) -> bool:
        """
        Toggle notice whitelist for a user.
        Returns True if now added, False if now removed.
        """
        if target_nick:
            # Admin toggling another user
            nick_to_toggle = target_nick.lower()
        else:
            # User toggling themselves
            nick_to_toggle = nick.lower()

        if nick_to_toggle in self.notice_whitelist:
            self.notice_whitelist.remove(nick_to_toggle)
            return False  # Now removed
        else:
            self.notice_whitelist.add(nick_to_toggle)
            return True  # Now added

    def get_status(self) -> str:
        """Get current game status."""
        if not self.active:
            return "Ei aktiivista sanaketjua."

        participants_str = (
            ", ".join(
                f"{nick}: {score} pistettä"
                for nick, score in sorted(
                    self.participants.items(), key=lambda x: x[1], reverse=True
                )
            )
            or "Ei osallistujia vielä"
        )

        start_time_str = (
            self.start_time.strftime("%d.%m.%Y %H:%M")
            if self.start_time
            else "Tuntematon"
        )

        return (
            f"Sanaketju aktiivinen! "
            f"Nykyinen sana: {self.current_word} | "
            f"Ketjun pituus: {self.chain_length} | "
            f"Aloitusaika: {start_time_str} | "
            f"Osallistujat: {participants_str}"
        )

    def end_game(self, data_manager) -> Optional[str]:
        """End the current game. Returns final results or None if no active game."""
        if not self.active:
            return None

        # Calculate results
        if not self.participants:
            result = "Sanaketju päättyi. Ei osallistujia."
        else:
            winner = max(self.participants.items(), key=lambda x: x[1])
            end_time = datetime.now()
            duration = end_time - (self.start_time or end_time)

            participants_str = ", ".join(
                f"{nick}: {score}"
                for nick, score in sorted(
                    self.participants.items(), key=lambda x: x[1], reverse=True
                )
            )

            result = (
                f"Sanaketju päättyi! "
                f"Voittanut: {winner[0]} ({winner[1]} pistettä) | "
                f"Ketjun pituus: {self.chain_length} | "
                f"Kesto: {str(duration).split('.')[0]} | "
                f"Osallistujat: {participants_str}"
            )

        # Reset game
        self.active = False
        self.channel = ""
        self.current_word = ""
        self.chain_length = 0
        self.participants = {}
        self.used_words = set()
        self.start_time = None

        # Save state
        self._save_state(data_manager)
        return result

    def _save_state(self, data_manager):
        """Save current game state."""
        state = {
            "active": self.active,
            "channel": self.channel,
            "current_word": self.current_word,
            "chain_length": self.chain_length,
            "participants": self.participants,
            "used_words": list(self.used_words),
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "notice_whitelist": list(self.notice_whitelist),
        }
        data_manager.save_sanaketju_state(state)

    def _load_state(self, data_manager):
        """Load game state from data manager."""
        state = data_manager.load_sanaketju_state()
        if state:
            self.active = state.get("active", False)
            self.channel = state.get("channel", "")
            self.current_word = state.get("current_word", "")
            self.chain_length = state.get("chain_length", 0)
            self.participants = state.get("participants", {})
            self.used_words = set(state.get("used_words", []))
            start_time_str = state.get("start_time")
            if start_time_str:
                try:
                    self.start_time = datetime.fromisoformat(start_time_str)
                except Exception:
                    self.start_time = None
            self.notice_whitelist = set(state.get("notice_whitelist", []))


# Global sanaketju game instance
_sanaketju_game = SanaketjuGame()


def get_sanaketju_game() -> SanaketjuGame:
    """Get the global sanaketju game instance."""
    return _sanaketju_game


# =====================
# Sanaketju Command
# =====================


@command(
    "sanaketju",
    description="Play sanaketju word chain game (start, status, stop, add)",
    usage="!sanaketju [start|stop|add [nick]]",
    examples=[
        "!sanaketju",
        "!sanaketju start",
        "!sanaketju stop",
        "!sanaketju add",
        "!sanaketju add othernick",
    ],
)
def sanaketju_command(context: CommandContext, bot_functions):
    """Main sanaketju command with subcommands."""
    data_manager = bot_functions.get("data_manager")
    if not data_manager:
        return "❌ Data manager not available"

    game = get_sanaketju_game()
    game._load_state(data_manager)  # Load latest state

    if not context.args:
        # Show current status
        return game.get_status()

    subcommand = context.args[0].lower()

    if subcommand == "start":
        if game.active:
            return "Sanaketju on jo käynnissä!"

        starting_word = game.start_game(context.target, data_manager)
        if starting_word:
            return f"🎯 Sanaketju aloitettu! Aloitussana: {starting_word}"
        else:
            return "❌ Ei voitu aloittaa sanaketjua - ei sanoja saatavilla."

    elif subcommand == "stop":
        result = game.end_game(data_manager)
        if result:
            return result
        else:
            return "Ei aktiivista sanaketjua lopetettavaksi."

    elif subcommand == "add":
        target_nick = context.args[1] if len(context.args) > 1 else None

        # Check if user has permission to add others (simple check: if they specify a nick)
        if target_nick and target_nick != context.sender:
            # For now, allow anyone to toggle anyone's add status
            # Could add admin check here if needed
            pass

        added = game.toggle_add(context.sender, target_nick)
        nick_display = target_nick or context.sender

        if added:
            return f"✅ {nick_display} lisätty sanaketjuun."
        else:
            return f"✅ {nick_display} poistettu sanaketjusta."

    else:
        return "Tuntematon komento. Käytä: start, stop, add [nick] tai ilman parametreja tilan näyttämiseen."


# Backward compatibility - these are already imported at the top of the file
