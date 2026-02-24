"""
Commands Package for LeetIRCPythonBot

This package contains modular command modules organized by category.
For now, it re-exports from the main commands module for backward compatibility.

Modules (planned):
- basic.py: help, ping, version, about, servers, status, channels
- admin.py: connect, disconnect, exit, schedule, ipfs
- games.py: blackjack, sanaketju, noppa, kolikko, ksp
- word_tracking.py: drink, kraks, drinkword, krakstats, etc.
- misc.py: 420, muunnos, quote, np, leets, tamagotchi, etc.
"""

# Re-export everything from commands for backward compatibility
# The @command decorator auto-registers, so importing modules triggers registration
from commands import *  # noqa: F401, F403, E402
