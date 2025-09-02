# LeetIRCPythonBot

## Description
Simple IRC Bot made with Python and as few libraries as possible.

## Features
- 🚀 OpenAI - Responds using GPT-5-mini (or others)        <automatic> from messages starting with bot name or private messages
- 🔥 Weather                                               !s, !sää
- 🔥 Weather Forecast                                      !se, !sel
- ✅ URL Titles                                            <automatic> from http(s) links | !url
- ⚡ Electricity prices in Finland for today/tomorrow      !sahko
- ✅ Scheduled messages                                    !schedule, !scheduled
- 🔥 Statistics for words and special (drinking) words     <automatic> from channel messages | !sana, !leaderboard, !topwords, !kraks, !drink, !drinkword
- ✅ Multiple servers and channels support                 Configured in .env file
- 📺 Youtube search with text and ID                       <automatic> from Youtube links | !youtube <searchwords>/<ID>
- 🔥 Keeping track of channel notifications                !leets, !leetwinners
- ⚠️ Accident reports monitoring                           !tilaa onnettomuustiedotteet
- ⚠️ FMI warnings monitoring                               !tilaa varoitukset
- 🚉 Arriving and departing trains information             !junat, !junat saapuvat
- 🌌 Solar wind status                                     !solarwind
- ✅ Tamagotchi-like pet functionality                     !tamagotchi, !feed, !pet
- ✅ Current time, echo message, ping, about, version      !aika, !kaiku, !ping, !about, !version
- ✅ Eurojackpot statistics and draws                      !eurojackpot
- ✅ IPFS file upload                                      !ipfs add <url>
- ✅ Cryptocurrency price information                      !crypto
- ✅ Euribor interest rate from yesterday                  !euribor
- ✅ Basic IRC commands: join, nick, part, quit, raw       !join, !nick, !part, !quit, !raw

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
