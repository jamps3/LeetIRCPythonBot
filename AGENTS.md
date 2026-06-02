# AGENTS.md

This file provides guidance to WARP (warp.dev) and other agents when working with code in this repository.

Project: LeetIRCPythonBot v2.4.74 (Python IRC bot with multi-server support, services, and a modern command system)

- Shell: pwsh (Windows). Adapt Linux/macOS variants where noted.

1. Common commands

 - First-time setup (Windows PowerShell):
   - python -m venv venv
   - .\venv\Scripts\Activate.ps1
   - pip install --upgrade pip
   - if (Test-Path requirements.txt) { pip install -r requirements.txt }
   - if (Test-Path requirements-dev.txt) { pip install -r requirements-dev.txt }

 - First-time setup (bash/zsh):
   - python3 -m venv venv
   - source venv/bin/activate
   - pip install --upgrade pip
   - [ -f requirements.txt ] && pip install -r requirements.txt
   - [ -f requirements-dev.txt ] && pip install -r requirements-dev.txt

- Run the bot locally:
  - pwsh: python .\main.py
  - bash/zsh: python3 main.py
  - Useful flags:
    - python main.py -l DEBUG # verbose logs
    - python main.py -nick MyBot # override nickname
    - python main.py -api # show API keys in logs

- Configuration: `data/state.json` stores bot settings and IRC servers. `.env` stores API keys and optional environment overrides.
  - For local test parity with CI, a minimal .env can include:
    BOT_NAME=TestBot,
    IRC_NICKNAME=test_bot,
    SERVER_HOST=irc.example.com,
    SERVER_PORT=6667,
    SERVER_NAME=TestServer,
    CHANNELS=#test,
    LOG_LEVEL=INFO,
    TAMAGOTCHI_ENABLED=true,
    USE_NOTICES=true
  - Optional API keys: OPENAI_API_KEY, WEATHER_API_KEY, ELECTRICITY_API_KEY, YOUTUBE_API_KEY

- Linting & formatting:
  - Ruff format: ruff format .
  - Ruff lint: ruff check .
  - Ruff lint with fixes, including import sorting: ruff check --fix .
  - Pre-commit setup (runs Ruff before commit)

- CI reference (GitHub Actions):
  - Installs: python-dotenv pytest pytest-xdist (and optionally requirements.txt)
  - Runs tests via: python -m pytest -v --tb=short -n auto
  - Lint job uses: ruff format --check and ruff check

- Local commands matching CI (pwsh):
  - $env:PYTHONPATH = (Get-Location)
  - python -m pytest -v --tb=short -n auto
  - Prefer the repo venv when available: .\venv\Scripts\python.exe -m pytest -v --tb=short -n auto
  - Full pytest runs can take time: keep `-n auto` enabled and allow a generous timeout (at least 5 minutes).
  - Lint (check-only):
    - ruff format --check --diff .
    - ruff check .
  - Security (optional, mirrors CI uploads but local files only):
    - ruff check --select S .
    - pip-audit -r requirements.txt -r requirements-dev.txt --progress-spinner off

2. High-level architecture

- Entrypoint (main.py):
  - Parses CLI flags (log level, nickname, API-key print mask)
  - Loads `.env` API keys via config.load*env_file() and IRC servers from `data/state.json`
  - Initializes and starts BotManager, then waits for shutdown

- Bot orchestration (bot_manager.BotManager):
  - Reads configured IRC servers from `data/state.json`
  - Constructs Server instances (server.Server) for each configured server
  - Registers callbacks for: message, notice, join, part, quit
  - Starts background monitors (if available): FMI warnings, Otiedote releases
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
  - IRC message callback (\_handle_message):
    1. Nanoleet detection with max-precision timestamp (leet_detector)
    2. Word tracking (drink/general), Tamagotchi response if enabled
    3. YouTube URL detection: auto-fetch basic video info via youtube_service
    4. Command handling via command_loader / command_registry
  - IRC notice callback (\_handle_notice):
    1. Leetwinners detection, updates leet_winners.json
  - command_loader:
    - process_irc_message/process_console_command bridge messages/inputs to the command registry
    - load_all_commands() imports the `cmd_modules` package, which registers modular commands
  - command_registry:
    - Provides CommandContext/CommandResponse types, registry, and process_command_message()
    - Centralizes parsing, routing, and response shaping (including splitting long responses when needed)

- IRC stack:
  - server.Server: encapsulates a single IRC connection lifecycle, channels, send_message/notice
  - irc_client.py and irc_processor.py: low-level IRC protocol handling and parsing utilities
  - USE_NOTICES toggle controls whether replies are NOTICE or PRIVMSG

- Services (services/\*):
  - alko_service.py: Search Alko product information
  - crypto_service.py: Crypto price fetch (CoinGecko)
  - digitraffic_service.py: Departing and arriving trains
  - electricity_service.py: Spot electricity price lookups, stats, daily summaries
  - eurojackpot_service.py: Eurojackpot draws, numbers and statistics
  - fmi_warning_service.py: FMI Warnings, background monitor invoking BotManager callbacks
  - gpt_service.py: OpenAI-backed chat with history persistence and limits
  - ipfs_service.py: admin-gated IPFS commands
  - otiedote_json_service.py: Otiedote releases (Onnettomuustiedotteet), ultralight version
  - scheduled_message_service.py: Scheduled messages
  - solarwind_service.py: Solarwind status
  - weather_forecast_service.py: Weather forecast
  - weather_service.py: Fetches weather data
  - youtube_service.py: YouTube ID extraction, metadata fetch

- URL title fetching:
  - BotManager.\_fetch_title: requests + BeautifulSoup; skips blacklisted domains/extensions (env-configurable)

- Configuration and logging:
  - config.py: `.env` loading, `data/state.json` config parsing, helper getters
  - logger.py: get_logger(name) used across components; respects LOG_LEVEL
  - Notable env toggles: TAMAGOTCHI_ENABLED, USE_NOTICES, FOUR_TWENTY_ENABLED

3. Command System Architecture

- Modular Command Structure:
  - cmd_modules/: Modular command packages (basic, admin, admin_privileged, games, irc, misc, services, word_tracking)
  - command_registry.py: Central command registration and routing
  - command_loader.py: Command loading and processing

- Command Reload System:
  - reload_manager.py: Hot-reload commands without restart
  - Supports atomic reload with rollback on failure
  - Usage: !reload (IRC) or !reload (console)

- Timing and Lag Compensation:
  - message_handler.py: Lag storage and measurement
  - commands_irc.py: !lag and !sexact commands for precise timing
  - scheduled_message_service.py: Lag-compensated scheduled messages
  - Usage: !lag <nick> to measure, !sexact <nick> <time> <message> for exact timing

4. Testing guidance

- Pytest is the standard. (see tests/!TEST_SUMMARY.md for context).
- Some tests intentionally skip external integrations; CI installs only minimal deps and relies on mocks/importorskip where needed.
- Before finishing any task, run the full test suite and ensure all tests pass. Do not treat a task as complete while any test is failing.
- Tests must never read from or write to the development machine's `data/state.json`. Use `tmp_path`, another temporary directory, or the pytest `STATE_FILE` sandbox for state persistence.
 - All tests: python -m pytest -v --tb=short -n auto
  - Single file: python -m pytest tests/test_config_new.py -v
  - Single test node: python -m pytest tests/test_config_new.py::test_load_env_file -v
  - With coverage (if pytest-cov installed): python -m pytest tests -v --cov=.
- Typical selective runs while iterating on a command or service:
  - Admin commands: python -m pytest tests/test_commands_admin.py -k password -v
  - Crypto service: python -m pytest tests/test_service_crypto\*.py -v
  - Flood protection: python -m pytest tests/test_server_flood_protection.py -v

5. Focus files when modifying behavior

- Adding/modifying commands: command modules (`command_loader.py`, `command_registry.py`, and `cmd_modules/`)
- Message handling behavior: bot_manager.BotManager.\_handle_message and subsequent helpers
- Services: services/<service>\_service.py and the corresponding wiring in BotManager.
- Server/IRC protocol details: server.py, irc_client.py, irc_processor.py
- Word tracking/persistence: word_tracking/
- Configuration shape: config.py and .env.sample, .env when running
- Shared `data/state.json` persistence: state_utils.py and every section writer
- Command reloading: reload_manager.py (hot-reload commands without restart)
- Lag measurement and timing: message_handler.py (lag storage), commands_irc.py (!lag, !sexact commands), scheduled_message_service.py (lag compensation)

6. Notes and conventions

- Console protection features in BotManager are intentionally disabled to avoid hangs in some terminals
- Some modules (lemmatizer, subscriptions, etc.) are optional; code guards against missing deps
- Do not add or preserve legacy compatibility layers, deprecated wrappers, or historical import paths. Migrate callers to the active modular implementation and delete obsolete code.
- Treat `data/state.json` as shared mutable state. Section writers must use strict locked atomic updates from `state_utils.py`; do not open it directly with truncating write mode.
- If `data/state.json` is temporarily invalid during a manual edit, writers must refuse the update and preserve the file bytes.
- Normal startup and graceful shutdown maintain `data/state.json.start.bak` and `data/state.json.end.bak`. These fixed-name snapshots are local recovery files and stay ignored by Git.
- After interactive configuration setup, reload the cached `ConfigManager` before continuing startup.

7. Git hygiene

- Commit early and often (project rule). Prefer small commits with clear messages
