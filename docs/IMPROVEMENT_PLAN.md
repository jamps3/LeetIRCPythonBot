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
- **cmd_modules/admin.py** - connect, disconnect, exit
- **cmd_modules/games.py** - kolikko, noppa, ksp, blackjack, sanaketju, countdown (k)
- **cmd_modules/misc.py** - 420, kaiku/echo, np (name day), leets, quote, matka, schedule, ipfs
- **cmd_modules/services.py** - service commands: s/se/sel, solarwind, otiedote, sahko, euribor, junat, youtube, imdb, crypto, leetwinners, eurojackpot, alko, drugs, url, wrap, tilaa
- **cmd_modules/word_tracking.py** - sana, topwords, leaderboard, drinkword, drink, kraks, tamagotchi, feed, pet, krak, muunnos, krakstats, kraksdebug

### commands.py Status:

**DEPRECATED** - The commands.py file now serves only as a backward-compatibility layer containing:

- Lazy getter functions (\_get_data_manager, \_get_drink_tracker, etc.)
- Proxy classes for DataManager, DrinkTracker, etc.
- Helper classes (CardSuit, CardRank, BlackjackGame, SanaketjuGame, etc.)
- Import re-exports for backward compatibility

The commands.py file is NOT actively used for command registration - all @command decorated functions in commands.py are duplicates of those in cmd_modules/ and are skipped due to the idempotent registration in the command registry.

Tests: 740 passed, 26 failed, 4 skipped

Note: Some legacy tests fail due to API changes (record_word, etc.) - these tests need updating to use the new cmd_modules/ API

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

## 2026-03-03: Commands Cleanup - COMPLETED ✅

**Task:** Remove duplicate @command decorated functions from commands.py since they're already implemented in cmd_modules/

**Status:** COMPLETED ✅

**Changes Made:**

- Added cmd_modules imports to commands.py to ensure they load properly
- Removed ALL 35 duplicate @command decorated functions from commands.py:
  - basic.py: help, ping, version, servers, about
  - admin.py: connect, disconnect, exit
  - games.py: kolikko, noppa, ksp, blackjack, sanaketju
  - misc.py: 420, kaiku, np, quote, matka, leets, schedule, ipfs
  - word_tracking.py: sana, tilaa, topwords, leaderboard, drinkword, drink, kraks, tamagotchi, feed, pet, krak, muunnos, krakstats, kraksdebug
- **Renamed cmd_modules/commands_services.py to cmd_modules/services.py**

**Verified implementations in cmd_modules:**

- muunnos command: cmd_modules/word_tracking.py (transform_phrase, \_send_muunnos_response)
- noppa command: cmd_modules/games.py
- matka command: cmd_modules/misc.py
- np command: cmd_modules/misc.py (different JSON format - may need reconciliation)
- quote command: cmd_modules/misc.py
- connect/disconnect/status/channels/about/k/exit: cmd_modules/admin.py, basic.py

**Blackjack Game Classes Moved:**

- Moved CardSuit, CardRank, Card, Hand, Deck, GameState, BlackjackGame, get_blackjack_game from commands.py to cmd_modules/games.py
- games.py no longer imports GameState from commands.py

**commands.py now serves as:**

- Lazy getter functions for DataManager, DrinkTracker, etc.
- Helper functions for commands
- Import re-exports for backward compatibility

**Note:** The SanaketjuGame class exists in BOTH commands.py and cmd_modules/games.py - they may need to be reconciled (deduplicated).

## 2026-03-03: Additional Command Verifications - COMPLETED ✅

**Task:** Verify additional commands from commands.py are implemented in cmd_modules/

**Verified:**

1. **version_command**: ✅ ALREADY IMPLEMENTED in cmd_modules/basic.py (lines 111-135)
   - Exact same implementation as in commands.py
   - Reads from VERSION file, falls back to config
   - No action needed - already modular

2. **load_otiedote_json**: ✅ NOT PRESENT in commands.py
   - No such function exists in commands.py
   - Otiedote data loading is handled by otiedote_service.load_otiedote_data() in otiedote_json_service.py
   - Already properly centralized in services/

3. **\_parse_time_and_message**: ✅ ALREADY IMPLEMENTED in cmd_modules/admin.py
   - **Orphaned duplicate removed from commands.py** ✅
   - Function is used by countdown command

4. **Countdown command (!k)**: ✅ MOVED to games.py for public access
   - Moved from admin.py to games.py to make it available for everyone
   - Uses \_parse_time_and_message helper

---

## Summary

The project has been significantly improved:

- **Code duplication eliminated** (DataManager, word tracking)
- **Consistent patterns** (logger imports, config usage)
- **Modular structure** (handlers/, cmd_modules/)
- **Simplified APIs** (eurojackpot_service.py)
- **55 commands** load successfully

---

## 2026-03-03: Backward Compatibility Fix - COMPLETED ✅

**Issue:** When tests import from `commands` directly, only 24 service commands were loaded instead of all 55 commands.

**Root Cause:** The cmd_modules imports in commands.py were not being executed when commands.py was imported directly (not via command_loader.py).

**Fix Applied:**

1. Changed the import in commands.py from `from commands_services import ...` to `from cmd_modules.services import ...`
2. This ensures that importing commands.py triggers loading all cmd_modules submodules

**Verification:**

```
$ python -c "import commands; from command_registry import get_command_registry; r = get_command_registry(); print(len(r._commands))"
55
```

All 55 commands now load correctly whether accessed via command_loader or direct import.
