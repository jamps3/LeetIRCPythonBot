# TEST_PLAN.md - Test Coverage Improvement Plan

## Current Test Coverage (as of v2.4.91)

Overall Coverage: **82%**

### Coverage by File (Sorted by Lowest First)

| Priority | File                                  | Current Coverage | Target Coverage | Status               |
| -------- | ------------------------------------- | ---------------- | --------------- | -------------------- |
| 1        | services/otiedote_service.py          | 24%              | 70%             | 🔴 Needs tests       |
| 2        | lemmatizer.py                         | 26%              | 50%             | 🔴 Needs tests       |
| 3        | services/ipfs_service.py              | 34%              | 50%             | 🔴 Needs tests       |
| 4        | services/scheduled_message_service.py | 58%              | 70%             | 🟡 Needs improvement |
| 5        | word_tracking/tamagotchi_bot.py       | 62%              | 70%             | 🟡 Needs improvement |
| 6        | word_tracking/general_words.py        | 64%              | 70%             | 🟡 Needs improvement |
| 7        | command_loader.py                     | 51%              | 70%             | 🔴 Needs tests       |
| 8        | services/eurojackpot_service.py       | 78%              | 80%             | 🟢 Good              |
| 9        | services/solarwind_service.py         | 78%              | 80%             | 🟢 Good              |
| 10       | bot_manager.py                        | 79%              | 80%             | 🟢 Good              |
| 11       | command_registry.py                   | 76%              | 80%             | 🟢 Good              |
| 12       | word_tracking/data_manager.py         | 86%              | 90%             | 🟢 Good              |
| 13       | word_tracking/drink_tracker.py        | 85%              | 90%             | 🟢 Good              |
| 14       | services/electricity_service.py       | 86%              | 90%             | 🟢 Good              |
| 15       | subscriptions.py                      | 87%              | 90%             | 🟢 Good              |
| 16       | commands.py                           | 91%              | 95%             | 🟢 Good              |
| 17       | commands_admin.py                     | 90%              | 95%             | 🟢 Good              |

### Files with 100% Coverage (Already Complete)

- config.py: 100%
- logger.py: 100%
- main.py: 100%
- leet_detector.py: 100%
- services/gpt_service.py: 100%
- services/weather_forecast_service.py: 100%
- services/weather_service.py: 100%
- services/youtube_service.py: 100%
- irc_client.py: 98%
- services/fmi_warning_service.py: 98%
- services/digitraffic_service.py: 99%
- server.py: 96%

---

## Test Coverage Improvement Tasks

### Priority 1: Critical Services (24-35% coverage)

#### 1.1 services/otiedote_service.py (24% → 70%)

- [ ] Test OtiedoteService initialization
- [ ] Test fetch_latest method
- [ ] Test JSON parsing
- [ ] Test error handling for network failures
- [ ] Test cache management

#### 1.2 lemmatizer.py (26% → 50%)

- [ ] Test Lemmatizer class initialization
- [ ] Test lemmatize_word method
- [ ] Test word caching
- [ ] Test error handling for missing Voikko

#### 1.3 services/ipfs_service.py (34% → 50%)

- [ ] Test IPFS service initialization
- [ ] Test hash operations
- [ ] Test pin/unpin operations
- [ ] Test error handling

### Priority 2: Important Modules (51-64% coverage)

#### 2.1 command_loader.py (51% → 70%)

- [ ] Test load_all_commands function
- [ ] Test command processing
- [ ] Test bot_functions dictionary
- [ ] Test error handling

#### 2.2 services/scheduled_message_service.py (58% → 70%)

- [ ] Test schedule_message function
- [ ] Test message storage and retrieval
- [ ] Test time-based triggers
- [ ] Test error handling

#### 2.3 word_tracking/tamagotchi_bot.py (62% → 70%)

- [ ] Test TamagotchiBot initialization
- [ ] Test pet interaction methods
- [ ] Test state persistence

#### 2.4 word_tracking/general_words.py (64% → 70%)

- [ ] Test GeneralWords class methods
- [ ] Test word counting
- [ ] Test statistics generation

---

## Progress Tracking

### Completed Tasks

- [x] Added test_service_availability.py with basic sanity checks
- [x] Fixed import issues that prevented tests from running
- [x] Added SERVICE CommandType enum value

### In Progress

- [ ] Working on improving coverage for Priority 1 files

### Test Execution Commands

```bash
# Run tests with coverage for specific file
python -m pytest tests/test_service_otiedote_json.py -v --cov=src/services/otiedote_json_service.py

# Run all tests and see coverage
python -m pytest --cov=. --cov-report=term-missing tests/

# Run only low-coverage file tests
python -m pytest tests/test_lemmatizer.py tests/test_service_ipfs.py tests/test_service_otiedote_json.py -v
```

---

## Notes

- Some services require API keys or external dependencies that may not be available in CI
- Use `pytest.importorskip` for optional dependencies
- Focus on unit tests that don't require network access
- Mock external API calls where possible
