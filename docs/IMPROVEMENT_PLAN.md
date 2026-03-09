# Project Improvement Plan for LeetIRCPythonBot

Generated: 2026-02-22

## v2.5.3 Update - Test Fixes Needed (2026-03-09)

### Known Test Failures: 49 tests

**Status**: Needs refactoring

**Issue**: The test file `test_commands_services_comprehensive.py` uses incorrect mock paths. Tests patch `cmd_modules.services.X` but the actual code imports things locally inside functions from `services.X`, `config.X`, etc.

**Affected Tests**:

- 44 failing tests in `test_commands_services_comprehensive.py`
- 5 failing tests in `test_sanaketju.py`

**Root Cause**:

- Functions in `cmd_modules/services.py` import modules locally (e.g., `from config import get_api_key` inside functions)
- Tests try to patch `cmd_modules.services.get_api_key` but the import isn't in that namespace

**Solution Options**:

1. **Fix test patches**: Change patches from `cmd_modules.services.X` to `config.X`, `services.Y`, etc.
2. **Add module-level imports**: Add commonly-mocked imports at top of `cmd_modules/services.py` for test compatibility
3. **Skip tests**: Mark failing tests with `@pytest.mark.skip` until fixed

**Current Test Results**: 952 passed, 49 failed, 4 skipped

---

## v2.4.92 Update - Nameday Scraping Challenge (2026-03-08)

### Hevonen and Historiallinen Namedays Scraping

**Status**: Completed ✓

**Solution**: Used Playwright browser automation to iterate through all 365 days with the correct website flow provided by user.

**Website Flow** (via user guidance):

1. Load `https://almanakka.helsinki.fi/fi/nimipaivat`
2. Click `.namedays-btn` to enter search mode
3. Click the "Päivä" tab button with `data-tab="date"`
4. Fill date input widget (e.g., "1.1", "1.2")
5. Extract names from `.namedays-result-card` elements

**Results**:

- Hevonen: 355 days with names
- Historiallinen: 342 days with names
- Data merged into `data/nimipaivat_others.json`

**Scraper Script**: `src/debug/scrape_nimipaivat-hevonen-historiallinen.py`

---

## v2.4.91 Update - Test Coverage (2026-03-06)

### Current Test Coverage: 82%

See [TEST_PLAN.md](../TEST_PLAN.md) for detailed coverage improvement plan.

### Priority Files Needing Tests:

| File                                  | Current Coverage | Target |
| ------------------------------------- | ---------------- | ------ |
| services/otiedote_service.py          | 24%              | 70%    |
| lemmatizer.py                         | 26%              | 50%    |
| services/ipfs_service.py              | 34%              | 50%    |
| command_loader.py                     | 51%              | 70%    |
| services/scheduled_message_service.py | 58%              | 70%    |

### Recent Fixes:

- Fixed import issues that prevented tests from running
- Added SERVICE to CommandType enum
- Created test_service_availability.py with sanity checks

---

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
- **cmd_modules/word_tracking.py** - sana, topwords, leaderboard, drinkword, drink, kraks, tamagotchi, feed, pet, krak, muunnos, krakstats, kraksdebug, assoc

### commands.py Status:

**DEPRECATED** - Now a thin backward-compatibility layer (~6.5KB, down from 129KB originally)

**NO @command decorated functions exist in commands.py anymore**

**Contents:**

1. Lazy getters (`_get_data_manager()`, `_get_drink_tracker()`, etc.)
2. Backward compatibility proxies (`_LazyProxy` class)
3. Re-exports: `CommandContext`, `CommandResponse`, `CommandScope`, `CommandType`, `command`, `DataManager`, `DrinkTracker`, `GeneralWords`, `TamagotchiBot`, `Server`
4. Helper classes moved to cmd_modules/games.py (CardSuit, CardRank, etc.)

**All 56 commands are now in cmd_modules/ package**

The commands.py file is NOT actively used for command registration - all @command decorated functions in commands.py are duplicates of those in cmd_modules/ and are skipped due to the idempotent registration in the command registry.

Tests: 952 passed, 49 failed, 4 skipped (2026-03-09)

**Current Test Issues:**

- 44 failing tests in `test_commands_services_comprehensive.py` - incorrect mock paths (patching `cmd_modules.services.X` but imports done locally)
- 5 failing tests in `test_sanaketju.py` - game module mocking issues

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
- np command: cmd_modules/misc.py ✅ (fixed to handle new dict format with year-month-day keys, includes fallback for old list format)
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

---

## 2026-03-03: NP Command Verification - COMPLETED ✅

**Issue:** np_command was returning "No name day found for today" from console but working via !kaiku from IRC.

**Investigation:**

1. Verified np_command implementation in cmd_modules/misc.py:
   - ✅ Uses @command("np") decorator (line 213)
   - ✅ Function is np_command (line 214)
   - ✅ Handles new dict format: {"2025-01-01": {"official": [...]}}
   - ✅ Searches by month-day ignoring year (line 238: `month_day_key = f"-{today_month:02d}-{today_day:02d}"`)
   - ✅ Has fallback for old list format

2. Verified data file (data/nimipaivat.json):
   - ✅ Data exists for today (2025-03-03): {'official': ['Kauko'], ...}
   - ✅ Format is dict with date keys

3. Tested via process_console_command:
   - ✅ Returns correct output: "Tänään (3.3) on nimipäivä: Kauko"

**Conclusion:**
The np_command is correctly implemented. The issue reported by user may have been:

1. A stale pycache issue (cleared by restarting the bot)
2. Running from an older version before the fix
3. Different execution context

**Status:** COMPLETED ✅

Command count verified: 56 commands loaded successfully.

---

## Remaining Refactoring Tasks from commands.py

**Current Status:** commands.py is now a thin backward-compatibility layer (214 lines, ~6.5KB).

**All 56 commands are in cmd_modules/ package.**

### What Remains in commands.py (Needed for backward compatibility):

1. **Lazy Getters** (lines 35-71):
   - `_get_data_manager()`, `_get_drink_tracker()`, `_get_general_words()`, `_get_tamagotchi_bot()`
   - These are used by cmd_modules to get singleton instances

2. **\_LazyProxy class** (lines 90-115):
   - Provides backward compatibility for code that expects `commands.data_manager`, `commands.drink_tracker`, etc. as objects

3. **Helper Functions** (lines 129-131):
   - `trim_with_dots()` - Used by some commands

4. **Re-exports** (lines 139-212):
   - Imports and re-exports all commands from cmd_modules for backward compatibility
   - Also exports: `CommandContext`, `CommandResponse`, `CommandScope`, `CommandType`, `command`, `Server`, `DataManager`, `DrinkTracker`, `GeneralWords`, `TamagotchiBot`

### External Dependencies on commands.py (Now UPDATED ✅)

| File                             | Usage                                      | Status                                             |
| -------------------------------- | ------------------------------------------ | -------------------------------------------------- |
| `message_handler.py`             | `get_sanaketju_game`                       | Updated to import from `cmd_modules.games`         |
| `debug/debug_kaiku.py`           | `echo_command`                             | Updated to import from `cmd_modules.misc`          |
| `debug/debug_sananmuunnokset.py` | `_find_first_syllable`, `transform_phrase` | Updated to import from `cmd_modules.word_tracking` |

### New: Simplified cmd_modules Imports ✅

Now just `import cmd_modules` loads all 56 commands!

- `cmd_modules/__init__.py` auto-loads all submodules
- `command_loader.py` and `tui.py` simplified to single import

### Optional Cleanup (Not Required):

1. **Remove re-export statements** - Once all imports are updated, commands.py could be completely removed
2. **Move lazy getters to a dedicated module** (e.g., `src/singletons.py`)
3. **Move `_LazyProxy` class to command_registry** or a shared utils module

### Current File Sizes:

- `src/commands.py`: 214 lines (~6.5KB) - Already refactored!
- Original size was ~129KB with all commands

### Status: **Mostly Complete** ✅

The refactoring is essentially done. commands.py now serves only as a backward-compatibility layer and could eventually be removed once all external dependencies are updated to import directly from cmd_modules.

---

## 2026-03-03: Test Files Created - COMPLETED ✅

**Task:** Create comprehensive test files for all command modules.

**Created Test Files:**

1. **tests/test_commands_basic.py** - Tests for basic commands
   - TestHelpCommand, TestPingCommand, TestVersionCommand, TestAboutCommand
   - TestServersCommand, TestStatusCommand, TestChannelsCommand

2. **tests/test_commands_admin.py** - Tests for admin commands
   - TestConnectCommand, TestDisconnectCommand, TestExitCommand
   - TestKCommand (countdown)

3. **tests/test_commands_games.py** - Tests for games commands
   - TestKolikkoCommand, TestNoppaCommand, TestKspCommand
   - TestBlackjackCommand, TestSanaketjuCommand

4. **tests/test_commands_services.py** - Tests for service commands
   - TestWeatherCommand, TestShortForecastCommand, TestShortForecastListCommand
   - TestSolarwindCommand, TestOtiedoteCommand, TestElectricityCommand
   - TestEuriborCommand, TestTrainsCommand, TestYoutubeCommand
   - TestImdbCommand, TestCryptoCommand, TestLeetwinnersCommand
   - TestEurojackpotCommand, TestAlkoCommand, TestDrugsCommand
   - TestUrlCommand, TestWrapCommand, TestTilaaCommand

5. **tests/test_commands_word_tracking.py** - Tests for word_tracking commands
   - TestTopwordsCommand, TestLeaderboardCommand, TestDrinkwordCommand
   - TestDrinkCommand, TestKraksCommand, TestTamagotchiCommand
   - TestFeedCommand, TestPetCommand, TestKrakCommand
   - TestSanaCommand, TestAssocCommand, TestMuunnosCommand
   - TestKrakstatsCommand, TestKraksdebugCommand

6. **tests/test_commands_misc.py** - Tests for misc commands (already existed)
   - Test420Command, TestKaikuCommand, TestNpCommand
   - TestQuoteCommand, TestMatkaCommand, TestScheduleCommand
   - TestLeetsCommand, TestIpfsCommand

**Status:** COMPLETED ✅

---

## AI Teachings Feature - COMPLETED ✅

The AI Teachings feature allows users to teach the bot persistent knowledge that is included in AI responses.

### Implementation:

1. **Data Storage** (`src/word_tracking/data_manager.py`)
   - Added `ai_teachings` section to existing `state.json`
   - Methods: `add_teaching()`, `remove_teaching()`, `get_teachings()`, `get_teaching_by_id()`, `get_teachings_for_context()`
   - 50-item limit enforced

2. **Commands** (`src/cmd_modules/services.py`)
   - `!teach <content>` - Add new teaching
   - `!teach` - List all teachings
   - `!unlearn <id>` - Remove teaching (admin only)

3. **GPT Integration** (`src/services/gpt_service.py`)
   - `_get_teachings_context()` loads teachings for AI context
   - Included in responses (max 100 items combined with history)
