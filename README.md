# LeetIRCPythonBot

## Description
Simple IRC Bot made with Python and as few libraries as possible.

## Features
| Feature | Commands/Info |
|----------------|-----------------|
| - 🚀 OpenAI - Responds using GPT-5-mini (or others)        |<automatic> from messages starting with bot name or private messages|
| - 🔥 Weather                                               |!s, !sää|
| - 🔥 Weather Forecast                                      |!se, !sel|
| - ✅ URL Titles                                            |<automatic> from http(s) links, !url|
| - ⚡ Electricity prices in Finland for today/tomorrow      |!sahko|
| - ✅ Scheduled messages                                    |!schedule, !scheduled|
| - 🔥 Statistics for words and special (drinking) words     |<automatic> from channel messages, !sana, !leaderboard, !topwords, !kraks, !drink, !drinkword|
| - ✅ Multiple servers and channels support                 |Configured in .env file|
| - 📺 Youtube search with text and ID                       |<automatic> from Youtube links, !youtube <searchwords>/<ID>|
| - 🔥 Keeping track of channel notifications                |!leets, !leetwinners|
| - ⚠️ Accident reports monitoring                           |!tilaa onnettomuustiedotteet|
| - ⚠️ FMI warnings monitoring                               |!tilaa varoitukset|
| - 🚉 Arriving and departing trains information             |!junat, !junat saapuvat|
| - 🌌 Solar wind status                                     |!solarwind|
| - ✅ Tamagotchi-like pet functionality                     |!tamagotchi, !feed, !pet|
| - ✅ Current time, echo message, ping, about, version      |!aika, !kaiku, !ping, !about, !version|
| - ✅ Eurojackpot statistics and draws                      |!eurojackpot|
| - ✅ IPFS file upload                                      |!ipfs add <url>|
| - ✅ Cryptocurrency price information                      |!crypto|
| - ✅ Euribor interest rate from yesterday                  |!euribor|
| - ✅ Basic IRC commands: join, nick, part, quit, raw       |!join, !nick, !part, !quit, !raw|

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

## run (might be updated in the source):
```bash
#!/bin/bash

SESSION_NAME="bot"
VENV_PATH="venv/bin/activate"
BOT_COMMAND="python3 main.py"

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
    tmux send-keys -t $SESSION_NAME "pip install -r requirements.txt" C-m
    tmux send-keys -t $SESSION_NAME "$BOT_COMMAND" C-m

    tmux attach -t $SESSION_NAME
fi
```

## Features Implemented

### 1. ⏰ Scheduled Messages

**Commands:**
- `!schedule #channel HH:MM:SS message` - Schedule a message
- `!schedule #channel HH:MM:SS.microseconds message` - Schedule with microsecond precision
- `!scheduled list` - List all scheduled messages (admin)
- `!scheduled cancel <message_id>` - Cancel a scheduled message (admin)

**Examples:**
```
!schedule #general 13:37:00 Leet time!
!schedule #test 15:30:45.123456 Precise timing message
!scheduled list
!scheduled cancel scheduled_1703012345_0
```

**Features:**
- **Threading**: Daemon threads for clean shutdown
- **Accuracy**: Sub-millisecond timing precision (up to 9 decimal places)
- **Admin** control for listing and cancelling messages
- **Memory Management**: Automatic cleanup of expired messages
- Automatic next-day scheduling if time has passed
- **Logging** Detailed logging of timing accuracy

### 2. 📁 IPFS Integration

**Commands:**
- `!ipfs add <url>` - Add file to IPFS (100MB limit)
- `!ipfs <password> <url>` - Add file to IPFS with admin password (no size limit)
- `!ipfs info <hash>` - Get IPFS object information

**Examples:**
```
!ipfs add https://example.com/document.pdf
!ipfs mypassword123 https://example.com/large_video.mp4
!ipfs info QmXYZ123...
```

**Features:**
- **Process Management**: Subprocess calls to IPFS CLI
- **Stream Processing**: Chunk-based downloads with size monitoring, no memory issues
- **Validation**: Pre-download size checking
- **Security**: Admin password validation for large files, unlimited size with correct admin password
- 100MB size limit without password
- **Reliability**: Comprehensive error handling and cleanup
- Real-time download progress monitoring
- File integrity verification (SHA256 hash)
- Graceful error handling for network issues
- Automatic IPFS daemon availability checking

### 3. 🎰 Eurojackpot Information

**Commands:**
- `!eurojackpot` - Get next draw information (date, time, jackpot amount)
- `!eurojackpot tulokset` - Get last draw results (numbers, date, winners)

**Examples:**
```
!eurojackpot
> 🎰 Seuraava Eurojackpot: 15.03.2024 klo 21:00 | Potti: 15.0 miljoonaa EUR

!eurojackpot tulokset  
> 🎰 Viimeisin Eurojackpot (12.03.2024): 07 - 14 - 21 - 28 - 35 + 03 - 08 | 2 jackpot-voittajaa
```

**Features:**
- Real-time data from API
- **Caching**: Service instance reuse for efficiency
- **Error Handling**: Graceful API failure handling
- **Rate Limiting**: Respectful API usage
- Automatic timezone conversion to Finnish time

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

Data flow overview:
- IRC messages -> BotManager._handle_message -> command_loader.enhanced_process_irc_message -> command_registry -> commands/commands_admin -> Services
- Console input -> command_loader.enhanced_process_console_command -> command_registry -> commands/commands_admin -> Services
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

## Next Steps (Optional Enhancements/TODO)

1. **Scheduled Messages**:
   - Persistent storage for messages across restarts
   - Recurring/cron-style scheduling
   - Message templates and variables

2. **IPFS Integration**:
   - Progress bars for large uploads
   - IPFS pinning management
   - File type validation

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

### 📈 **Analytics & Monitoring**
- **Service Health**: Automatic API availability checking
- **Performance Metrics**: Response time and accuracy tracking
- **Data Persistence**: JSON-based storage with automatic backups
- **Real-time Alerts**: Instant notifications for important events
