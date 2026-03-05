"""
Centralized path definitions for the project.

This module provides consistent path resolution for the project,
ensuring all file operations use absolute paths relative to the
project root (parent of src/).
"""

import os

# Project root directory (parent of src/)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Data directory
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

# Common data file paths
CONVERSATION_HISTORY_FILE = os.path.join(DATA_DIR, "conversation_history.json")
EKAVIKA_FILE = os.path.join(DATA_DIR, "ekavika.json")
GENERAL_WORDS_FILE = os.path.join(DATA_DIR, "general_words.json")
SUBSCRIBERS_FILE = os.path.join(DATA_DIR, "subscribers.json")
STATE_FILE = os.path.join(DATA_DIR, "state.json")
SANANMUUNNOKSET_FILE = os.path.join(DATA_DIR, "sananmuunnokset.json")
QUOTES_FILE = os.path.join(DATA_DIR, "quotes.txt")
