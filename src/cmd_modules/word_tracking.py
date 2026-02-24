"""
Word Tracking Commands Module

Contains word tracking commands: drink, kraks, drinkword, krakstats, etc.

This module re-exports from commands.py - the actual command implementations
are in the main commands.py file to maintain backward compatibility.
"""

# Import everything from commands.py - triggers @command decorator registration
from commands import *  # noqa: F401, F403, E402
