"""
Word Tracking Module

This module provides comprehensive word tracking functionality including:
- Enhanced drink word tracking with specific drinks and timestamps
- General word counting
- Privacy controls for users
- Server-specific tracking
- Rich statistics and search capabilities

Modules:
    - drink_tracker: Enhanced drink word tracking system
    - general_words: General word counting functionality
    - data_manager: Unified data management with JSON storage
"""

from .data_manager import DataManager
from .drink_tracker import DrinkTracker
from .general_words import GeneralWords

__version__ = "1.0.0"
__author__ = "LeetIRCPythonBot"

__all__ = ["DrinkTracker", "GeneralWords", "DataManager"]
