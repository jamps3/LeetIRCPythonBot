# Project Improvement Plan for LeetIRCPythonBot

Generated: 2026-02-22

## Overview

This document outlines the planned improvements, optimizations, and simplifications for the LeetIRCPythonBot project. Items are prioritized by criticality and can be tracked as they are implemented.

---

## ✅ ALL ISSUES COMPLETED

All planned improvements have been implemented:

1. ✅ **Duplicate DataManager Instances** - Fixed to use single shared instance
2. ✅ **Duplicate Word Tracking** - Fixed to use shared components
3. ✅ **Logger Imports** - Standardized to `from logger import get_logger`
4. ✅ **Multiple load_dotenv()** - Removed redundant calls
5. ✅ **os.getenv()** - Centralized to config.py
6. ✅ **handlers/** - Created with url_handler.py and latency_tracker.py mixins
7. ✅ **message_handler.py** - Updated to use handler mixins
8. ✅ **cmd_modules/** - Created modular command package structure
9. ✅ **commands_services.py** - Moved to cmd_modules/
10. ✅ **eurojackpot_service.py** - Simplified API fallback logic (~100 lines removed)
11. ✅ **commands.py refactoring** - All commands moved to cmd_modules/ (see below)

---

## Commands Refactoring - COMPLETED ✅

All commands have been successfully moved from the monolithic `commands.py` to modular files in `cmd_modules/`:

### Final cmd_modules Structure:

- **cmd_modules/basic.py** - help, ping, version, about, servers, status, channels
- **cmd_modules/admin.py** - connect, disconnect, exit, countdown (k)
- **cmd_modules/games.py** - kolikko, noppa, ksp, blackjack, sanaketju
- **cmd_modules/misc.py** - 420, kaiku/echo, np (name day), leets, quote, matka, schedule, ipfs
- **cmd_modules/word_tracking.py** - sana, tilaa, topwords, leaderboard, drinkword, drink, kraks, tamagotchi, feed, pet, krak, muunnos, krakstats, kraksdebug
- **cmd_modules/commands_services.py** - all service commands (s, se, sel, solarwind, otiedote, sahko, euribor, junat, youtube, imdb, crypto, leetwinners, eurojackpot, alko, drugs, url, wrap)

### commands.py Status:

**DEPRECATED** - The commands.py file now serves only as a backward-compatibility layer containing:

- Lazy getter functions (\_get_data_manager, \_get_drink_tracker, etc.)
- Proxy classes for DataManager, DrinkTracker, etc.
- Helper classes (CardSuit, CardRank, BlackjackGame, SanaketjuGame, etc.)
- Import re-exports for backward compatibility

The commands.py file is NOT actively used for command registration - all @command decorated functions in commands.py are duplicates of those in cmd_modules/ and are skipped due to the idempotent registration in the command registry.

Tests: 766 passed, 4 skipped (all tests pass)

---

## 2026-02-24: Log Timestamp Issue

**Issue:** Log timestamps are not in chronological order, causing messages to have wrong order in the log file.

**Priority:** High - Affects debugging and log analysis

**Status: FIXED** ✅ (log file only)

- Added thread lock (`_file_lock`) to ensure thread-safe writes in correct order
- Fixed timestamp calculation to use single time source (`time.time_ns()`) for both seconds and nanoseconds
- Log file timestamps are now in chronological order

**Note:** TUI display shows buffered logs after current logs (cosmetic issue, does not affect log file)

---

## Summary

The project has been significantly improved:

- **Code duplication eliminated** (DataManager, word tracking)
- **Consistent patterns** (logger imports, config usage)
- **Modular structure** (handlers/, cmd_modules/)
- **Simplified APIs** (eurojackpot_service.py)
- **55 commands** load successfully
