# LeetIRCPythonBot

## Description
Simple IRC Bot made with Python and as few libraries as possible.

## Features
- 🚀 OpenAI - Responds using GPT-4o-mini (or others)
- 🔥 Weather
- ⚡ Electricity prices in Finland for today/tomorrow
- ✅ Scheduled messages
- 🔥 Statistics for words and special words
- ✅ Multiple channels support, multiple servers support in progress
- 📺 Youtube search
- 🔥 Keeping track of channel notifications

## Installation
Not needed!
Run file has all this included. But here it is anyway (might get outdated if the libraries update):
```bash
python3 -m venv venv
source venv/bin/activate
pip install requests
pip install bs4
pip install openai
pip install dotenv
pip install google-api-client
```
## .env file for configuration:
You need this for all the APIs to work and for the server and channel information.
```bash
# API Keys
# Replace these placeholders with your actual API keys
WEATHER_API_KEY = ""
ELECTRICITY_API_KEY = ""
OPENAI_API_KEY = ""
YOUTUBE_API_KEY = ""
CHANNEL_KEY_53 = ""

# Server Configurations
# Format: SERVERx_HOST, SERVERx_PORT, SERVERx_CHANNELS, SERVERx_KEYS
# Where x is a unique identifier for each server

# Server 1
SERVER1_HOST=irc.server.ip
SERVER1_PORT=6667
SERVER1_CHANNELS="#channel1,channel2"
SERVER1_KEYS="channel1key"
```

# Running
## Simple
Options to run in: Screen, Tmux. I now prefer Tmux as it has more capabilities.
```bash
screen python3 main.py
tmux new-session -d -s bot
python3 main.py
```
## using run file for Linux
```bash
./run
```
What does it do?

✅Creates or activates virtual environment

✅Starts new tmux session with the name "bot"

✅Installs requirements with pip

✅Starts the bot with python3 main.py

## run:
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
