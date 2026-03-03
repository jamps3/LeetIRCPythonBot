"""
Lazy Getters and Helper Functions Module for LeetIRCPythonBot

This file provides lazy-initialized singletons and helper functions used by cmd_modules.

All commands have been moved to cmd_modules/ package:
- cmd_modules/basic.py: help, ping, version, servers, status, channels, about
- cmd_modules/admin.py: connect, disconnect, k (countdown), exit
- cmd_modules/games.py: kolikko, noppa, ksp, blackjack, sanaketju
- cmd_modules/misc.py: 420, kaiku, np, quote, matka, leets, schedule, ipfs
- cmd_modules/word_tracking.py: sana, tilaa, topwords, leaderboard, drinkword, drink, kraks,
                                tamagotchi, feed, pet, krak, muunnos, krakstats, kraksdebug
- cmd_modules/services.py: All service commands (weather, crypto, alko, etc.)

Use command_loader.load_all_commands() to load all commands.
"""

import logger
from command_registry import (
    CommandContext,
    CommandResponse,
    CommandScope,
    CommandType,
    command,
)
from config import get_config
from server import Server
from tamagotchi import TamagotchiBot
from word_tracking import DataManager, DrinkTracker, GeneralWords

# =====================
# Lazy-initialized singletons
# =====================

_data_manager = None
_drink_tracker = None
_general_words = None
_tamagotchi_bot = None


def _get_data_manager():
    """Lazy getter for DataManager to ensure single shared instance."""
    global _data_manager
    if _data_manager is None:
        config = get_config()
        _data_manager = DataManager(state_file=config.state_file)
    return _data_manager


def _get_drink_tracker():
    """Lazy getter for DrinkTracker."""
    global _drink_tracker
    if _drink_tracker is None:
        _drink_tracker = DrinkTracker(_get_data_manager())
    return _drink_tracker


def _get_general_words():
    """Lazy getter for GeneralWords."""
    global _general_words
    if _general_words is None:
        _general_words = GeneralWords(_get_data_manager())
    return _general_words


def _get_tamagotchi_bot():
    """Lazy getter for TamagotchiBot."""
    global _tamagotchi_bot
    if _tamagotchi_bot is None:
        _tamagotchi_bot = TamagotchiBot(_get_data_manager())
    return _tamagotchi_bot


# Backward compatibility: expose lazy getters as module-level attributes
# Tests and some code expect commands.data_manager, commands.drink_tracker, etc.
# to be instances (not functions), so we use property-like behavior with __getattr__
# Actually, let's just expose the getter functions - they'll be called by tests
# that do commands.general_words.search_word(...)

# For backward compatibility: these need to be objects, not functions
# We'll make them point directly to the lazy instances
data_manager = property(lambda self: _get_data_manager())
drink_tracker = property(lambda self: _get_drink_tracker())
general_words = property(lambda self: _get_general_words())
tamagotchi = property(lambda self: _get_tamagotchi_bot())


# But for tests that call general_words() as a function, we need to support both
# So create wrapper functions that work as both callable and attribute
class _LazyProxy:
    """Proxy that acts as the singleton instance but can be called."""

    def __init__(self, getter):
        self._getter = getter
        self._instance = None

    def _get_instance(self):
        if self._instance is None:
            self._instance = self._getter()
        return self._instance

    def __call__(self, *args, **kwargs):
        return self._get_instance()(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._get_instance(), name)

    def __repr__(self):
        return f"<_LazyProxy: {self._get_instance()} >"


data_manager = _LazyProxy(_get_data_manager)
drink_tracker = _LazyProxy(_get_drink_tracker)
general_words = _LazyProxy(_get_general_words)
tamagotchi = _LazyProxy(_get_tamagotchi_bot)

# Also expose the lazy getter functions for direct access
get_data_manager = _get_data_manager
get_drink_tracker = _get_drink_tracker
get_general_words = _get_general_words
get_tamagotchi_bot = _get_tamagotchi_bot


# =====================
# Helper functions
# =====================


def trim_with_dots(text: str, limit: int = 400) -> str:
    """Truncate text to limit with ellipsis."""
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "..."


# =====================
# Re-export commands from cmd_modules
# =====================

# Import cmd_modules to register commands
import cmd_modules.admin  # noqa: E402
import cmd_modules.basic  # noqa: E402
import cmd_modules.games  # noqa: E402
import cmd_modules.misc  # noqa: E402
import cmd_modules.services  # noqa: E402
import cmd_modules.word_tracking  # noqa: E402
from cmd_modules.admin import (  # noqa: E402
    connect_command,
    countdown_command,
    disconnect_command,
    exit_command,
)

# Re-export for backward compatibility
from cmd_modules.basic import help_command  # noqa: E402
from cmd_modules.games import (  # noqa: E402
    blackjack_command,
    get_sanaketju_game,
    kolikko_command,
    ksp_command,
    noppa_command,
    sanaketju_command,
)
from cmd_modules.misc import (  # noqa: E402
    command_ipfs,
    command_leets,
    command_schedule,
    driving_distance_osrm,
    echo_command,
    four_twenty_command,
    np_command,
    quote_command,
)
from cmd_modules.services import (  # noqa: E402
    alko_command,
    command_eurojackpot,
    crypto_command,
    drugs_command,
    electricity_command,
    euribor_command,
    imdb_command,
    leetwinners_command,
    otiedote_command,
    short_forecast_command,
    short_forecast_list_command,
    solarwind_command,
    trains_command,
    url_command,
    weather_command,
    wrap_command,
    youtube_command,
)

# Aliases for backward compatibility
eurojackpot_command = command_eurojackpot
junat_command = trains_command

# tilaa is in services.py
from cmd_modules.services import command_tilaa  # noqa: E402
from cmd_modules.word_tracking import (  # noqa: E402
    command_drink,
    command_drinkword,
    command_feed,
    command_krak,
    command_kraks,
    command_leaderboard,
    command_pet,
    command_sana,
    command_tamagotchi,
    command_topwords,
    kraksdebug_command,
    krakstats_command,
    muunnos_command,
)

# EOF
