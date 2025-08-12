# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

Project: LeetIRCPythonBot (Python IRC bot with multi-server support, services, and a modern command system)

- Shell: pwsh (Windows). Adapt Linux/macOS variants where noted.

1) Common commands

- First-time setup (Windows PowerShell):
  - python -m venv venv
  - .\venv\Scripts\Activate.ps1
  - pip install --upgrade pip
  - if (Test-Path requirements.txt) { pip install -r requirements.txt }

- First-time setup (bash/zsh):
  - python3 -m venv venv
  - source venv/bin/activate
  - pip install --upgrade pip
  - [ -f requirements.txt ] && pip install -r requirements.txt

- Run the bot locally:
  - pwsh: python .\main.py
  - bash/zsh: python3 main.py
  - Useful flags:
    - python main.py -l DEBUG              # verbose logs
    - python main.py -nick MyBot           # override nickname
    - python main.py -api                  # show masked API keys in logs

- Environment config (.env): copy .env.sample to .env and set at least one server and any API keys you intend to use.
  - For local test parity with CI, a minimal .env can include: BOT_NAME=TestBot, BOT_VERSION=test, IRC_NICKNAME=test_bot, IRC_REALNAME=Test Bot, IRC_IDENT=testbot, SERVER_HOST=irc.example.com, SERVER_PORT=6667, SERVER_NAME=TestServer, CHANNELS=#test, LOG_LEVEL=INFO, TAMAGOTCHI_ENABLED=true, USE_NOTICES=false
  - Optional API keys: OPENAI_API_KEY, WEATHER_API_KEY, ELECTRICITY_API_KEY, YOUTUBE_API_KEY
  - Behavior toggles: TAMAGOTCHI_ENABLED=true|false, USE_NOTICES=true|false

- Run tests (pytest):
  - Set PYTHONPATH for local runs (pwsh): $env:PYTHONPATH = (Get-Location)
  - All tests: python -m pytest -v --tb=short
  - Single file: python -m pytest tests/test_config_new.py -v
  - Single test node: python -m pytest tests/test_config_new.py::test_load_env_file -v
  - Filter by expression: python -m pytest -k "weather and not integration" -v
  - Pattern (e.g., migrated tests): python -m pytest tests/test_*_new.py -v
  - With coverage (if pytest-cov installed): python -m pytest tests -v --cov=.

- Linting & formatting:
  - Black (format): black .
  - Isort (imports): isort --profile black .
  - Flake8 (lint): flake8 . --max-line-length=127 --extend-ignore=E203,E501,F401,F841,E402
  - Pre-commit (optional, if installed): pre-commit run --all-files

- CI reference (GitHub Actions):
  - Installs: python-dotenv pytest (and optionally requirements.txt)
  - Runs tests via: python -m pytest -v --tb=short
  - Lint job uses: black --check, isort --check-only, flake8 with the ignore list above

- Local commands matching CI (pwsh):
  - $env:PYTHONPATH = (Get-Location)
  - python -m pytest -v --tb=short
  - Lint (check-only):
    - black --check --diff .
    - isort --check-only --diff .
    - flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
    - flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --extend-ignore=E203,E501,F401,F841,E402 --statistics
  - Security (optional, mirrors CI uploads but local files only):
    - bandit -r . -f json -o bandit-report.json || $true
    - safety check --json --output safety-report.json || $true

2) High-level architecture

- Entrypoint (main.py):
  - Parses CLI flags (log level, nickname, API-key print mask)
  - Loads .env via config.load_env_file(), validates at least one SERVERx_* block
  - Initializes and starts BotManager, then waits for shutdown

- Bot orchestration (bot_manager.BotManager):
  - Reads environment-driven server configs via get_server_configs()
  - Constructs Server instances (server.Server) for each configured server
  - Registers callbacks for: message, join, part, quit
  - Starts background monitors (if available): FMI warnings, Otiedote press releases
  - Manages services (conditional on available keys/deps):
    - WeatherService (WEATHER_API_KEY)
    - Electricity service (ELECTRICITY_API_KEY)
    - GPTService (OPENAI_API_KEY)
    - YouTube service (YOUTUBE_API_KEY)
    - Crypto service (CoinGecko, no key)
  - Manages word tracking stack from word_tracking/:
    - DataManager: JSON persistence
    - DrinkTracker: drink word counting
    - GeneralWords: general word stats
    - TamagotchiBot: opt-in virtual pet replies (TAMAGOTCHI_ENABLED)
  - Console listener thread: reads local console input
    - `!`-prefixed inputs are routed through the same command system as IRC messages
    - Non-`!` inputs go to GPT chat if configured
  - Shutdown: propagates quit_message to servers; joins threads with timeouts

- Command processing pipeline (high-level):
  - IRC message callback (_handle_message):
    1) Nanoleet detection with max-precision timestamp (leet_detector)
    2) Word tracking (drink/general), Tamagotchi response if enabled
    3) YouTube URL detection: auto-fetch basic video info via youtube_service
    4) Command handling via command_loader / command_registry
  - command_loader:
    - enhanced_process_irc_message/enhanced_process_console_command bridge messages/inputs to the command registry
    - load_all_commands() imports command modules (e.g., commands_admin, commands_basic, commands_extended) which self-register with the registry
  - command_registry:
    - Provides CommandContext/CommandResponse types, registry, and process_command_message()
    - Centralizes parsing, routing, and response shaping (including splitting long responses when needed)

- IRC stack:
  - server.Server: encapsulates a single IRC connection lifecycle, channels, send_message/notice
  - irc_client.py and irc_processor.py: low-level IRC protocol handling and parsing utilities
  - USE_NOTICES toggle controls whether replies are NOTICE or PRIVMSG

- Services (services/*):
  - weather_service.py: fetches weather data, formats messages
  - electricity_service.py: spot price lookups, stats, daily summaries, message formatting
  - gpt_service.py: OpenAI-backed chat with history persistence and limits
  - youtube_service.py: ID extraction, metadata fetch, concise message formatting
  - crypto_service.py: price fetch + friendly formatting (CoinGecko)
  - fmi_warning_service.py, otiedote_service.py: background monitors invoking BotManager callbacks
  - ipfs_service.py: admin-gated IPFS helper commands

- URL title fetching:
  - BotManager._fetch_title: requests + BeautifulSoup; skips blacklisted domains/extensions (env-configurable) and YouTube (handled by YouTube service)

- Configuration and logging:
  - config.py: .env loading, server config parsing, helper getters
  - logger.py: get_logger(name) used across components; respects LOG_LEVEL
  - Notable env toggles: TAMAGOTCHI_ENABLED, USE_NOTICES, QUIT_MESSAGE; TITLE_BLACKLIST_DOMAINS/EXTENSIONS, TITLE_BANNED_TEXTS

3) Focus files when modifying behavior

- Adding/modifying commands: command modules (e.g., commands_admin.py) + command_registry.py
- Message handling behavior: bot_manager.BotManager._handle_message and subsequent helpers
- Services: services/<service>_service.py and the corresponding wiring in BotManager.__init__
- Server/IRC protocol details: server.py, irc_client.py, irc_processor.py
- Word tracking/persistence: word_tracking/
- Configuration shape: config.py and .env.sample

4) Testing guidance specific to this repo

- Pytest is the standard. Many tests are being/may be migrated to pure pytest (see tests/MIGRATION_PROGRESS.md for context).
- Some tests intentionally skip external integrations; CI installs only minimal deps and relies on mocks/importorskip where needed.
- To run only migrated tests locally (faster, fewer optional deps):
  - python -m pytest tests/test_*_new.py -v
- Typical selective runs while iterating on a command or service:
  - python -m pytest tests/test_admin_commands_new.py -k password -v
  - python -m pytest tests/test_crypto_service*.py -v

5) Notes and conventions

- Windows Unicode: main.py sets up UTF-8 printing; safe_print fallbacks exist
- Console protection features in BotManager are intentionally disabled to avoid hangs in some terminals
- USE_NOTICES vs PRIVMSG is unified in _send_response; change behavior centrally if needed
- Some modules (lemmatizer, subscriptions, etc.) are optional; code guards against missing deps
- Keep regular expressions stable in this repo (owner rule). If a change touches a regex, prefer removing or isolating the whole line first and re-adding carefully rather than in-place edits

Appendix: quick references

- Activate venv (pwsh): .\\venv\\Scripts\\Activate.ps1
- Deactivate venv: deactivate
- Format + lint all: isort --profile black .; black .; flake8 . --max-line-length=127 --extend-ignore=E203,E501,F401,F841,E402
- Run a single test node: python -m pytest path\\to\\test_file.py::test_case -v


Recent updates and gotchas (Aug 2025)

- Command help (!help)
  - In IRC, help lists only IRC_ONLY commands and is sent privately to the caller (NOTICE to nick), not to the channel
  - The help command itself is excluded from listings
  - Ordering: regular commands A–Z, then Tamagotchi commands (tamagotchi, feed, pet) A–Z, then admin commands A–Z with footer
  - Duplicates were eliminated by deduping across scopes
  - Tests: python -m pytest tests/test_irc_help.py -v

- IRC message sending
  - Multi-line command responses are split into separate notices, and long lines are chunked to <= 400 bytes to avoid truncation

- Commands context fix
  - Weather (!s) and Electricity (!sahko/!sähkö) now pass the IRC connection and channel properly so replies go to the correct place
  - Tests: python -m pytest tests/test_irc_basic_commands.py -v

- Rate limiter stabilization
  - server.Server: token bucket refill skips sub-100ms intervals to avoid micro-increments and flakiness
  - Related tests (server flood protection) are green

- Otiedote shutdown noise reduction
  - Selenium Chrome is started with keep_alive=False (where supported)
  - urllib3.connectionpool warnings are temporarily silenced during driver shutdown to avoid retry spam

- Solar wind
  - tests/test_solarwind_command.py passing; Windows console may require PYTHONIOENCODING=utf-8 to render emojis in manual runs

- Git hygiene
  - Commit early and often (project rule). Prefer small commits with clear messages

How to run only the updated/related tests

- Help (IRC): python -m pytest tests/test_irc_help.py -v
- Basic IRC commands (!s, !sahko): python -m pytest tests/test_irc_basic_commands.py -v
- Flood protection: python -m pytest tests/test_server_flood_protection.py -v
- Solar wind: python -m pytest tests/test_solarwind_command.py -v

