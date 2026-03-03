"""
Commands Package for LeetIRCPythonBot

This package contains modular command modules organized by category.

Modules:
- admin.py: connect, disconnect, exit
- basic.py: help, ping, version, servers, status, channels, about
- games.py: blackjack, sanaketju, noppa, kolikko, ksp, countdown (k)
- misc.py: 420, kaiku, np, quote, matka, leets, schedule, ipfs
- services.py: s, se, sel, solarwind, otiedote, sahko, euribor, junat, youtube, imdb, crypto, leetwinners, eurojackpot, alko, drugs, url, wrap
- word_tracking.py: drink, kraks, drinkword, krakstats, sana, tilaa, topwords, leaderboard, tamagotchi, feed, pet, krak, muunnos, kraksdebug
"""

# Import submodules to trigger @command decorators
# Order matters: dependencies first
from cmd_modules import basic  # noqa: E402, F401
from cmd_modules import admin  # noqa: E402, F401
from cmd_modules import games  # noqa: E402, F401
from cmd_modules import misc  # noqa: E402, F401
from cmd_modules import services  # noqa: E402, F401
from cmd_modules import word_tracking  # noqa: E402, F401
