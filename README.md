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

All features are implemented as independent services:

```
services/
├── scheduled_message_service.py  # Threading-based scheduling
├── ipfs_service.py              # IPFS CLI integration
└── eurojackpot_service.py       # Veikkaus API integration
```

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

## 🎯 Summary

1. ⏰ **Scheduled Messages**: Microsecond-precision timing with admin controls
2. 📁 **IPFS Integration**: Size-limited uploads with password override
3. 🎰 **Eurojackpot**: Real-time lottery information from official API
