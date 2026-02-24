"""
Commands Package for LeetIRCPythonBot

This package contains modular command modules organized by category.

Modules:
- basic.py: help, ping, version, about, servers, status, channels
- admin.py: connect, disconnect, exit, countdown
- games.py: blackjack, sanaketju, noppa, kolikko, ksp
- word_tracking.py: drink, kraks, drinkword, krakstats
- misc.py: 420, muunnos, quote, np, leets, tamagotchi

Importing this package triggers @command decorator registration for all commands.
"""

# Import all command modules to trigger @command decorator registration
from cmd_modules import admin  # noqa: F401, E402
from cmd_modules import basic  # noqa: F401, E402
from cmd_modules import commands_services  # noqa: F401, E402
from cmd_modules import games  # noqa: F401, E402
from cmd_modules import misc  # noqa: F401, E402
from cmd_modules import word_tracking  # noqa: F401, E402
