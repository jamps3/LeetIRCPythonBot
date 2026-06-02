"""
Commands Package for LeetIRCPythonBot

This package contains modular command modules organized by category.

Modules:
- admin.py: connect, disconnect, exit
- basic.py: help, ping, version, servers, status, channels, about
- games.py: blackjack, sanaketju, noppa, kolikko, ksp, countdown (k)
- misc.py: 420, kaiku, np, quote, matka, leets, schedule, ipfs
  - services.py: s, se, sel, solarwind, otiedote, sahko, euribor, junat, youtube, imdb, tmdb, crypto, leetwinners, eurojackpot, alko, drugs, url, wrap
- word_tracking.py: drink, kraks, drinkword, krakstats, sana, tilaa, topwords, leaderboard, tamagotchi, feed, pet, krak, muunnos, kraksdebug
"""

import os
import sys

# Add project root to path for imports
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Import submodules to trigger @command decorators
# Order matters: dependencies first
from cmd_modules import (
    admin,  # noqa: E402, F401
    admin_privileged,  # noqa: E402, F401
    basic,  # noqa: E402, F401
    games,  # noqa: E402, F401
    irc,  # noqa: E402, F401
    misc,  # noqa: E402, F401
    services,  # noqa: E402, F401
    word_tracking,  # noqa: E402, F401
)
