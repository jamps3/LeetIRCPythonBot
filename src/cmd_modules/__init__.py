"""
Commands Package for LeetIRCPythonBot

This package contains modular command modules organized by category.

NOTE: Do NOT import submodules from this package directly - it will cause circular imports.
Use command_loader.load_all_commands() instead to properly load all commands.

Modules (import via command_loader, not directly):
- admin.py: connect, disconnect, exit
- basic.py: help, ping, version, servers, status, channels, about
- games.py: blackjack, sanaketju, noppa, kolikko, ksp, countdown (k)
- misc.py: 420, kaiku, np, quote, matka, leets, schedule, ipfs
- services.py: s, se, sel, solarwind, otiedote, sahko, euribor, junat, youtube, imdb, crypto, leetwinners, eurojackpot, alko, drugs, url, wrap
- word_tracking.py: drink, kraks, drinkword, krakstats, sana, tilaa, topwords, leaderboard, tamagotchi, feed, pet, krak, muunnos, kraksdebug
"""

# NOTE: This package should NOT import submodules directly to avoid circular imports.
# The command_loader module handles importing submodules in the correct order.
# See command_loader.load_all_commands() for the proper way to load commands.
