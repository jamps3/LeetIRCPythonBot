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

---

## 2026-02-24: Commands Refactoring

### Current Status (2026-02-28)

Progress made on splitting commands.py into modular files in cmd_modules/:

**Already split (have actual implementations):**

- **cmd_modules/basic.py** - help, ping, version, about, servers, status, channels
- **cmd_modules/admin.py** - connect, disconnect, exit, countdown
- **cmd_modules/games.py** - kolikko, noppa, ksp, blackjack
- **cmd_modules/misc.py** - 420, kaiku/echo, np (name day), leets, quote, matka, schedule, ipfs (NEWLY MOVED)
- **cmd_modules/commands_services.py** - all service commands (s, se, sel, solarwind, otiedote, sahko, euribor, junat, youtube, imdb, crypto, leetwinners, eurojackpot, alko, drugs, url, wrap)

**Backward compatibility layer (still in commands.py, need to be moved):**

- word_tracking.py: `from commands import *` imports drink, kraks, drinkword, krakstats, tamagotchi, feed, pet, krak, kraksdebug, leaderboard, topwords, sana, tilaa
- misc.py placeholders: muunnos (complex - has many helper deps), ipfs (MOVED ✅)
- games.py: sanaketju

**Architecture Note:**
The command registry handles duplicate registrations gracefully (idempotent). When the same command is defined in both commands.py and cmd_modules with identical metadata, the second registration is skipped. This allows for incremental migration - commands can be moved one at a time.

**Commands remaining in commands.py (complex, need more work):**

- muunnos: Depends on Finnish word transformation helper functions (\_find_first_syllable, transform_phrase)
- sanaketju: Depends on SanaketjuGame class with data persistence
- word_tracking commands (drink, kraks, tilaa, etc.): Complex dependencies on drink tracker and data manager

**Progress this session:**

- ✅ Moved leets command to misc.py
- ✅ Moved schedule command to misc.py
- ✅ Moved ipfs command to misc.py

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
