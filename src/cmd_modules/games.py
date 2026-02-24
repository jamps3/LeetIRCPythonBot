"""
Games Commands Module

Contains game commands: blackjack, sanaketju, noppa, kolikko, ksp
"""

import random
import re

from command_registry import CommandContext, CommandResponse, command
from commands import GameState

# Import needed items from commands.py for shared functionality
# These are lazily initialized to avoid issues
_data_manager = None


def _get_data_manager():
    """Lazy getter for DataManager."""
    global _data_manager
    if _data_manager is None:
        from config import get_config
        from word_tracking import DataManager

        config = get_config()
        _data_manager = DataManager(state_file=config.state_file)
    return _data_manager


# Import BlackjackGame and related items from commands.py
# These are needed by blackjack_command
def _get_blackjack_game():
    """Get the global blackjack game instance from commands.py."""
    from commands import get_blackjack_game as _get_bj_game

    return _get_bj_game()


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
    game = _get_blackjack_game()

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

    # ... Note: The full blackjack implementation is long and depends on BlackjackGame class
    # For now, this is a placeholder that shows the structure
    # The full implementation would need to import BlackjackGame and GameState from commands.py


# Backward compatibility - these are already imported at the top of the file
