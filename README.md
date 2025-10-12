# LeetIRCPythonBot

## Description

Advanced IRC Bot made with Python. Extended API use and highly customizable.

## Features

| Feature                                                | Commands/Info                                                                                 |
| ------------------------------------------------------ | --------------------------------------------------------------------------------------------- |
| - 🚀 OpenAI - Responds using GPT-5-mini (or others)    | <automatic> from messages starting with bot name or private messages                          |
| - 🔥 Weather                                           | !s, !sää                                                                                      |
| - 🔥 Weather Forecast                                  | !se, !sel                                                                                     |
| - ✅ URL Titles                                        | <automatic> from http(s) links, !url                                                          |
| - ⚡ Electricity prices in Finland for today/tomorrow  | !sahko                                                                                        |
| - ✅ Scheduled messages                                | !schedule, !scheduled                                                                         |
| - 🔥 Statistics for words and special (drinking) words | <automatic> from channel messages, !sana, !leaderboard, !topwords, !kraks, !drink, !drinkword |
| - ✅ Multiple servers and channels support             | Configured in .env file                                                                       |
| - 📺 Youtube search with text and ID                   | <automatic> from Youtube links, !youtube <searchwords>/<ID>                                   |
| - 🔥 Keeping track of channel notifications            | !leets, !leetwinners                                                                          |
| - ⚠️ Accident reports monitoring                       | !tilaa onnettomuustiedotteet                                                                  |
| - ⚠️ FMI warnings monitoring                           | !tilaa varoitukset                                                                            |
| - 🚉 Arriving and departing trains information         | !junat, !junat saapuvat                                                                       |
| - 🌌 Solar wind status                                 | !solarwind                                                                                    |
| - ✅ Tamagotchi-like pet functionality                 | !tamagotchi, !feed, !pet                                                                      |
| - ✅ Current time, echo message, ping, about, version  | !aika, !kaiku, !ping, !about, !version                                                        |
| - ✅ Eurojackpot statistics and draws                  | !eurojackpot                                                                                  |
| - ✅ IPFS file upload                                  | !ipfs add <url>                                                                               |
| - ✅ Cryptocurrency price information                  | !crypto                                                                                       |
| - ✅ Euribor interest rate from yesterday              | !euribor                                                                                      |
| - ✅ Basic IRC commands: join, nick, part, quit, raw   | !join, !nick, !part, !quit, !raw                                                              |

## Installation

Not needed!
Run file has all this included:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### For development: enable pre-commit hooks (format before commit)

```bash
pip install pre-commit
pre-commit install
# Optionally enforce on push too
# pre-commit install --hook-type pre-push
# Format everything once
pre-commit run -a
```

### Or use the built-in setup script (includes test-before-push protection):

```bash
python setup_hooks.py
```

This sets up:

- **Pre-commit hook**: Code formatting (black, isort, flake8)
- **Pre-push hook**: Runs `.	est -q` automatically before every push
- **Git commit template**: Helpful commit message format

⚠️ **Important**: All tests must pass before pushing! If tests fail, the push is automatically canceled.
If you want to use Voikko -features you need to install these packages with apt:

```bash
sudo apt install -y libvoikko1 voikko-fi python3-libvoikko
```

## .env file for configuration:

You need this for all the APIs to work and for the server and channel information:
Copy .env.sample to .env and make relevant changes like bot name, servers, channels and API-keys.

### Add admin password to your `.env` file:

```env
ADMIN_PASSWORD=your_secure_password_here
```

# Running

## Simple

Options to run in: Screen, Tmux or plain Python. I prefer Tmux.

```bash
screen python3 main.py
tmux new-session -d -s bot
python3 main.py
```

## Using run/start file to start the bot

```bash
./run

After shutting down the bot, we can reuse the activated venv, tmux and skip installing requirements.txt and just use ./start:
./start
```

What does the ./run script do?

✅Creates or activates virtual environment
✅Starts new tmux session with the name "bot"
✅Installs requirements with pip
✅Starts the bot with python3 main.py

## .\run Script:

```bash
#!/bin/bash

SESSION_NAME="bot"
VENV_PATH="venv/bin/activate"
BOT_COMMAND="python3 main.py $@"
LOG_FILE="crashlog.txt"

# Check if virtual environment exists, create if not
if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Creating one..."
    python3 -m venv venv
fi

# Start tmux session or attach if already running
if tmux has-session -t $SESSION_NAME 2>/dev/null; then
    echo "Session $SESSION_NAME already exists. Attaching..."
    tmux attach -t $SESSION_NAME
else
    echo "Starting new tmux session: $SESSION_NAME"
    tmux new-session -d -s $SESSION_NAME

    # Activate venv, install requirements, and run bot inside tmux
    tmux send-keys -t $SESSION_NAME "source $VENV_PATH" C-m
    tmux send-keys -t $SESSION_NAME "pip install --upgrade -r requirements.txt" C-m
    tmux send-keys -t $SESSION_NAME "$BOT_COMMAND" C-m
    #tmux send-keys -t $SESSION_NAME "$BOT_COMMAND; exit" C-m
    #tmux send-keys -t $SESSION_NAME "$BOT_COMMAND >> $LOG_FILE 2>&1; exit" C-m  # Redirect stdout and stderr to log file

    tmux attach -t $SESSION_NAME
fi  # This closes the if-else block correctly
```

## Technical Implementation

### Architecture

Key components of the codebase and how they fit together:

```
Core /
├── main.py                       # Entry point: starts BotManager and event loop
├── bot_manager.py                # Orchestrates servers, services, command routing, console
├── server.py                     # Server wrapper, callbacks, message dispatch
├── irc_client.py                 # IRC protocol client (send_message/NOTICE/raw)
├── command_loader.py             # Loads command modules, processes IRC/console commands
├── command_registry.py           # Command system (registry, parsing, dispatch, help)
├── commands.py                   # Public & console commands (weather, stats, etc.)
├── commands_admin.py             # Admin commands (join/part/nick/quit/raw/openai/scheduled)
├── config.py                     # Environment and settings loader (.env support)
├── logger.py                     # High-precision logger and safe console output
├── subscriptions.py              # User/topic subscription system (warnings, releases)
├── leet_detector.py              # 1337 timestamp detector (nanosecond precision)
├── lemmatizer.py                 # Optional Finnish lemmatization support (graceful fallback)
├── utils.py                      # Small helpers used in tests and utilities
└── setup_hooks.py                # Dev hooks (e.g., pre-commit formatting)

Services /
├── crypto_service.py             # Cryptocurrency prices (CoinGecko)
├── digitraffic_service.py        # Train schedules and station info (Fintraffic Digitraffic)
├── electricity_service.py        # Hourly electricity prices (Nord Pool / Fingrid)
├── eurojackpot_service.py        # Lottery info, stats, analytics
├── fmi_warning_service.py        # Finnish Meteorological Institute warnings monitor
├── gpt_service.py                # GPT chat service (OpenAI Responses API)
├── ipfs_service.py               # IPFS add/info via CLI, streaming and validation
├── otiedote_service.py           # Accident/incident press release monitoring
├── scheduled_message_service.py  # Nanosecond scheduling, threading, precise timing
├── solarwind_service.py          # NOAA SWPC space weather (solar wind)
├── weather_service.py            # Current weather data & formatting
├── weather_forecast_service.py   # Short forecasts (single/multi-line)
└── youtube_service.py            # YouTube search and URL metadata

Word Tracking /
├── word_tracking/
│   ├── data_manager.py           # Storage for words, stats, config, persistence
│   ├── drink_tracker.py          # Drink-related word tracking, privacy/opt-out
│   ├── general_words.py          # Word counters, top words, leaderboards
│   └── tamagotchi_bot.py         # Virtual pet reactions (toggleable)

Configuration & Docs /
├── .env.sample                   # Example configuration and feature toggles
├── pytest.ini                    # Test configuration
├── README.md                     # This file (features, usage, architecture)
├── UML.md                        # Optional diagrams/notes
└── WARP.md                       # Notes for Warp terminal/Agent usage

Developer Tools & Scripts /
├── run                           # Bootstrap script: venv + tmux + install + start
├── start                         # Fast start: reuse venv/tmux and run main.py
└── conftest.py                   # Pytest fixtures and shared test config
```

#### 📁 File Links (Core)

- **Entry Point**: [`main.py`](main.py) - Bot startup, signal handling, BotManager initialization
- **Bot Orchestration**: [`bot_manager.py`](bot_manager.py) - Multi-server management, service coordination, console interface
- **Server Management**: [`server.py`](server.py) - IRC server wrapper, connection handling, callbacks
- **IRC Protocol**: [`irc_client.py`](irc_client.py) - Low-level IRC client, message sending, raw commands
- **Command Processing**: [`command_loader.py`](command_loader.py) - Command module loader, IRC/console message routing
- **Command System**: [`command_registry.py`](command_registry.py) - Command registration, parsing, dispatch, help generation
- **Public Commands**: [`commands.py`](commands.py) - Weather, stats, utilities, echo, version, electricity, etc.
- **Admin Commands**: [`commands_admin.py`](commands_admin.py) - Join/part/nick/quit/raw/openai/scheduled (password-protected)
- **Configuration**: [`config.py`](config.py) - Environment variable loading, server configs, API keys
- **Logging**: [`logger.py`](logger.py) - High-precision timestamped logging, console output protection
- **Subscriptions**: [`subscriptions.py`](subscriptions.py) - User notification preferences (warnings, releases)
- **Leet Detection**: [`leet_detector.py`](leet_detector.py) - 1337 timestamp detection with nanosecond precision
- **Lemmatization**: [`lemmatizer.py`](lemmatizer.py) - Optional Finnish word lemmatization (Voikko)
- **Utilities**: [`utils.py`](utils.py) - Helper functions for tests and utilities
- **Development**: [`setup_hooks.py`](setup_hooks.py) - Pre-commit hooks and code formatting

#### 🌐 Service Links

- **Crypto**: [`services/crypto_service.py`](services/crypto_service.py) - CoinGecko API, price fetching
- **Trains**: [`services/digitraffic_service.py`](services/digitraffic_service.py) - Finnish train schedules, station search
- **Electricity**: [`services/electricity_service.py`](services/electricity_service.py) - Nord Pool spot prices, hourly data
- **Eurojackpot**: [`services/eurojackpot_service.py`](services/eurojackpot_service.py) - Lottery results, statistics, analytics
- **Weather Warnings**: [`services/fmi_warning_service.py`](services/fmi_warning_service.py) - FMI warning monitoring
- **AI Chat**: [`services/gpt_service.py`](services/gpt_service.py) - OpenAI GPT integration, conversation history
- **IPFS**: [`services/ipfs_service.py`](services/ipfs_service.py) - Decentralized file storage, streaming uploads
- **Incident Reports**: [`services/otiedote_service.py`](services/otiedote_service.py) - Accident report monitoring
- **Scheduling**: [`services/scheduled_message_service.py`](services/scheduled_message_service.py) - Precise message timing
- **Solar Wind**: [`services/solarwind_service.py`](services/solarwind_service.py) - NOAA space weather data
- **Weather**: [`services/weather_service.py`](services/weather_service.py) - Current weather conditions
- **Forecasts**: [`services/weather_forecast_service.py`](services/weather_forecast_service.py) - Short weather forecasts
- **YouTube**: [`services/youtube_service.py`](services/youtube_service.py) - Video search, URL metadata

#### 📊 Word Tracking Links

- **Data Storage**: [`word_tracking/data_manager.py`](word_tracking/data_manager.py) - Persistent data management
- **Drink Tracking**: [`word_tracking/drink_tracker.py`](word_tracking/drink_tracker.py) - Drinking word monitoring
- **Word Stats**: [`word_tracking/general_words.py`](word_tracking/general_words.py) - Message analysis, leaderboards
- **Virtual Pet**: [`word_tracking/tamagotchi_bot.py`](word_tracking/tamagotchi_bot.py) - Interactive tamagotchi features

#### 🔧 Configuration & Tools Links

- **Environment**: [`.env.sample`](.env.sample) - Configuration template with all options
- **Testing**: [`pytest.ini`](pytest.ini) - Test runner configuration
- **Documentation**: [`README.md`](README.md) - This comprehensive guide
- **Diagrams**: [`UML.md`](UML.md) - System architecture diagrams
- **Warp Notes**: [`WARP.md`](WARP.md) - Terminal/Agent usage notes
- **Bootstrap**: [`run`](run) - Full setup script (venv + tmux + install + start)
- **Quick Start**: [`start`](start) - Fast restart script (reuse existing setup)
- **Test Config**: [`conftest.py`](conftest.py) - Pytest fixtures and shared test setup

Data flow overview:

- IRC messages -> BotManager.\_handle_message -> command_loader.process_irc_message -> command_registry -> commands/commands_admin -> Services
- Console input -> command_loader.process_console_command -> command_registry -> commands/commands_admin -> Services
- Background monitors (FMI/Otiedote) -> Subscriptions -> BotManager -> Servers/IRC

## Usage Examples

### Setting up IPFS (Optional)

```bash
# Install IPFS (if you want IPFS functionality)
# Download from: https://ipfs.io/docs/install/
ipfs init
ipfs daemon
```

### Command Examples in IRC

```
# Schedule a message for later today
!schedule #general 20:00:00 Evening announcement!

# Schedule with ultimate precision
!schedule #dev 09:30:15.123456789 Daily standup reminder

# Add a small file to IPFS
!ipfs add https://httpbin.org/bytes/1024

# Add a large file with password
!ipfs mypassword123 https://example.com/large_dataset.zip

# Get Eurojackpot info
!eurojackpot [next|tulokset|last|date <DD.MM.YY|DD.MM.YYYY|YYYY-MM-DD>|freq [--extended|--ext] [--limit N]|stats|hot|cold|pairs|trends|streaks|help]

# Admin: List scheduled messages
!scheduled mypassword123 list

# Admin: Cancel a scheduled message
!scheduled mypassword123 cancel scheduled_1703012345_0
```

## Testing

All features have been thoroughly tested.

### Automatic Testing

With the pre-push hook enabled, all tests run automatically before every `git push`:

```bash
git push  # Runs tests first, cancels if any fail
```

### Manual Testing

```bash
.\test         # Run all tests (full output)
.\test -q      # Run all tests (quiet mode)
python -m pytest tests/specific_test.py  # Run specific test
```

### Bypass Git Hooks (Emergency Use Only)

```bash
git commit --no-verify   # Skip pre-commit formatting
git push --no-verify     # Skip pre-push tests (NOT RECOMMENDED)
```

## Next Steps (Optional Enhancements/TODO)

1. **Scheduled Messages**:

   - Persistent storage for messages across restarts
   - Recurring/cron-style scheduling
   - Message templates and variables

2. **IPFS Integration**:

   - Progress bars for large uploads
   - IPFS pinning management

3. **Eurojackpot**:

   - Historical data collection
   - Multiple lottery support

4. **Tamagotchi**:
   - Verify tamagotchi commands work properly

## 🎯 Summary

LeetIRCPythonBot is a comprehensive IRC bot with 50+ features across multiple categories:

### 🤖 **AI & Chat Features**

- **GPT Integration**: Responds to mentions and private messages using OpenAI GPT-5-mini
- **Smart Conversations**: Context-aware responses with conversation history
- **Multi-language Support**: Finnish and English responses

### ⏰ **Scheduling & Automation**

- **Scheduled Messages**: Microsecond-precision timing with admin controls (!schedule, !scheduled)
- **Automatic Monitoring**: FMI weather warnings, accident reports (Otiedote)
- **Background Services**: Multi-threaded execution with daemon cleanup

### 🌐 **Web & API Integration**

- **Weather Services**: Current conditions (!s, !sää) and forecasts (!se, !sel)
- **Electricity Prices**: Finnish spot prices with hourly/daily data (!sahko)
- **YouTube Integration**: Auto-detection of URLs and search functionality (!youtube)
- **Cryptocurrency**: Real-time price information (!crypto)
- **Solar Wind**: Space weather monitoring (!solarwind)
- **Eurojackpot**: Complete lottery information with analytics (!eurojackpot)
- **URL Title Fetching**: Automatic webpage title extraction with blacklisting

### 📊 **Statistics & Tracking**

- **Word Statistics**: Track and analyze channel conversations (!sana, !topwords, !leaderboard)
- **Drink Tracking**: Monitor drinking-related words with privacy controls (!kraks, !drink, !antikrak)
- **Leet Detection**: Nanosecond-precision 1337 timestamp detection with achievements
- **User Analytics**: Server-wide and per-user statistics

### 🐾 **Interactive Features**

- **Tamagotchi Bot**: Virtual pet with feeding, care, and status (!tamagotchi, !feed, !pet)
- **Subscription System**: User-configurable notifications (!tilaa, !lopeta)
- **Echo & Utility**: Time display, ping/pong, version info (!aika, !ping, !version)

### 🚉 **Transportation**

- **Train Information**: Real-time arrivals/departures from Finnish stations (!junat)
- **Station Search**: Find stations and their live schedules

### 📁 **File & Storage**

- **IPFS Integration**: Decentralized file storage with size limits (!ipfs)
- **Stream Processing**: Large file handling without memory issues
- **Admin Override**: Unlimited uploads with password authentication

### 🔧 **Administration**

- **IRC Control**: Channel join/part, nickname changes (!join, !part, !nick)
- **Server Management**: Multi-server support with independent configurations
- **Raw Commands**: Direct IRC protocol access for advanced control (!raw)
- **Graceful Shutdown**: Clean disconnection with custom messages (!quit)
- **Model Management**: Runtime OpenAI model switching (!openai)

### 🔒 **Security & Privacy**

- **Password Authentication**: Secure admin command access
- **Opt-out Controls**: User privacy for tracking features
- **Rate Limiting**: API abuse prevention with cooldowns
- **Input Validation**: Comprehensive security checks

### 🏗️ **Technical Features**

- **Command Registry**: Modular command system with metadata
- **Multi-threading**: Concurrent service execution
- **Error Handling**: Comprehensive exception management
- **Logging**: High-precision timestamped logs
- **Console Interface**: Interactive command-line control
- **Memory Management**: Automatic cleanup and optimization
- **UTF-8 Support**: Full Unicode message handling with IRC compliance
- **Configurable Output**: NOTICE vs PRIVMSG message types
- **Git Hooks**: Automatic test execution before push (cancels failed pushes)

### 📈 **Analytics & Monitoring**

- **Service Health**: Automatic API availability checking
- **Performance Metrics**: Response time and accuracy tracking
- **Data Persistence**: JSON-based storage with automatic backups
- **Real-time Alerts**: Instant notifications for important events
