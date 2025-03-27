# LeetIRCPythonBot

## Description
Simple IRC Bot made with Python.

## Features
- ✅ Scheduled messages
- 🚀 OpenAI - Responds using GPT-4o-mini (or others)
- 🔥 Weather
- 🔥 Statistics for words etc.

## Installation
```bash
python3 -m venv venv
source venv/bin/activate
pip install requests
pip install bs4
pip install openai
pip install dotenv
```
## .env file for configuration:
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

## Running
# Simple
```bash
Options to run in: Screen, Tmux
screen python3 main.py
tmux
python3 main.py
```
## using run file for Linux
```bash
./run
```
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
