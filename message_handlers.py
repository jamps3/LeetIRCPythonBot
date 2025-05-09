"""
Message handlers for the IRC bot.

This module contains functions to process incoming IRC messages,
handle commands, and manage bot responses for multiple servers.
All message handling is server-aware to support multi-server connections.
"""

import re
import json
import pickle
import threading
import requests
from datetime import datetime
import time
from typing import List, Optional
import urllib.parse
import os
import traceback
import logging
import openai
from bs4 import BeautifulSoup
from googleapiclient.discovery import build
from config import get_api_key

# Global variables (shared across servers, protected by locks)
DRINK_WORDS = {
    "krak": 0,
    "kr1k": 0,
    "kr0k": 0,
    "narsk": 0,
    "parsk": 0,
    "tlup": 0,
    "marsk": 0,
    "tsup": 0,
    "plop": 0,
}
last_title = ""
WORDS_FILE = "kraks_data.pkl"
HISTORY_FILE = "conversation_history.json"

# Threading locks for shared resources
kraks_lock = threading.Lock()
drink_words_lock = threading.Lock()
last_title_lock = threading.Lock()
leet_winners_lock = threading.Lock()
conversation_history_lock = threading.Lock()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def log(message: str, level: str = "INFO"):
    """Log a message with timestamp and level."""
    timestamp = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.{time.time_ns() % 1_000_000_000:09d}]"
    print(f"{timestamp} [{level.upper()}] {message}")


def save(file_path: str = WORDS_FILE):
    """Save kraks data to a file with thread safety."""
    with kraks_lock:
        try:
            with open(file_path, "wb") as f:
                pickle.dump({}, f)  # Placeholder for kraks data
        except Exception as e:
            log(f"Error saving data: {e}", "ERROR")


def load(file_path: str = WORDS_FILE) -> dict:
    """Load kraks data from a file with thread safety."""
    with kraks_lock:
        if not os.path.exists(file_path):
            log("Data file not found, creating a new one.", "WARNING")
            return {}
        try:
            with open(file_path, "rb") as f:
                return pickle.load(f)
        except (pickle.UnpicklingError, EOFError) as e:
            log(f"Corrupted data file: {e}", "ERROR")
            return {}
        except Exception as e:
            log(f"Error loading data: {e}", "ERROR")
            return {}


def save_conversation_history(history: dict):
    """Save conversation history to a file with thread safety."""
    with conversation_history_lock:
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as file:
                json.dump(history, file, indent=4, ensure_ascii=False)
        except Exception as e:
            log(f"Error saving conversation history: {e}", "ERROR")


def save_leet_winners(leet_winners: dict):
    """Save leet winners to a file with thread safety."""
    with leet_winners_lock:
        try:
            with open("leet_winners.json", "w", encoding="utf-8") as f:
                json.dump(leet_winners, f, indent=4, ensure_ascii=False)
        except Exception as e:
            log(f"Error saving leet winners: {e}", "ERROR")


def send_message(irc, channel: str, message: str):
    """Send a PRIVMSG to a channel or user."""
    try:
        irc.send_raw(f"PRIVMSG {channel} :{message}")
        log(f"Sent message to {channel}: {message}", "DEBUG")
    except Exception as e:
        log(f"Error sending message to {channel}: {e}", "ERROR")


def output_message(message: str):
    """Output a message to the console."""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")


def split_message_intelligently(message: str, max_length: int = 400) -> List[str]:
    """Split a message into parts while respecting word boundaries."""
    if len(message) <= max_length:
        return [message]

    parts = []
    current_part = ""
    words = message.split(" ")

    for word in words:
        if len(current_part) + len(word) + 1 <= max_length:
            current_part += (word + " ") if current_part else word
        else:
            if current_part:
                parts.append(current_part.strip())
            current_part = word + " "

    if current_part:
        parts.append(current_part.strip())

    return parts


def count_kraks(server, word: str, beverage: str):
    """Count occurrences of drink words for a server."""
    with drink_words_lock:
        if word in server.drink_words:
            server.drink_words[word] += 1
            log(
                f"Detected {word} ({beverage}). Total count: {server.drink_words[word]}"
            )
        else:
            log(f"Word {word} is not in the tracking list.")


def fetch_title(server, channel: str, url: str):
    """Fetch and send the title of a webpage from a URL."""
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        title = soup.title.string.strip() if soup.title else "No title found"
        formatted_title = (
            f"Title: {title[:100]}..." if len(title) > 100 else f"Title: {title}"
        )

        with last_title_lock:
            if formatted_title != server.last_title:
                server.send_message(channel, formatted_title)
                server.last_title = formatted_title
                log(f"Sent title: {title}", "DEBUG")
    except Exception as e:
        log(f"Error fetching title for {url}: {e}", "ERROR")


def send_weather(server, channel: str, location: str = "Joensuu"):
    """Fetch and send weather information for a location."""
    log(
        f"Fetching weather for {location} (server: {server.config.name if server else 'None'}, channel: {channel})",
        "DEBUG",
    )
    try:
        api_key = get_api_key("WEATHER_API_KEY")
        if not api_key:
            log("Weather API key not configured", "ERROR")
            if server and channel:
                server.send_message(channel, "Weather API key not configured.")
            return "Weather API key not configured."

        url = f"http://api.openweathermap.org/data/2.5/weather?q={urllib.parse.quote(location)}&appid={api_key}&units=metric&lang=fi"
        log(f"Sending weather API request: {url}", "DEBUG")
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()

        temp = data["main"]["temp"]
        feels_like = data["main"]["feels_like"]
        description = data["weather"][0]["description"]
        city = data["name"]
        message = f"Sää kohteessa {city}: {temp}°C (tuntuu kuin {feels_like}°C), {description}"
        log(f"Weather response: {message}", "DEBUG")
        if server and channel:
            server.send_message(channel, message)
        return message
    except Exception as e:
        log(f"Error fetching weather for {location}: {e}", "ERROR")
        error_message = f"Virhe haettaessa säätietoja kohteelle {location}."
        if server and channel:
            server.send_message(channel, error_message)
        return error_message


def send_electricity_price(server, channel: str, text: List[str]):
    """Fetch and send electricity price information."""
    try:
        api_key = get_api_key("ELECTRICITY_API_KEY")
        if not api_key:
            if server and channel:
                server.send_message(channel, "Electricity API key not configured.")
            return "Electricity API key not configured."

        date = datetime.now().strftime("%Y-%m-%d")
        url = f"https://api.porssisahko.net/v1/price.json?date={date}&hour={datetime.now().hour}&api_key={api_key}"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()

        price = data["price"]
        message = f"Sähkön hinta nyt: {price} snt/kWh"
        if server and channel:
            server.send_message(channel, message)
        return message
    except Exception as e:
        log(f"Error fetching electricity price: {e}", "ERROR")
        error_message = "Virhe haettaessa sähkön hintaa."
        if server and channel:
            server.send_message(channel, error_message)
        return error_message


def search_youtube(server, channel: str, query: str):
    """Search YouTube and send the first result."""
    try:
        api_key = get_api_key("YOUTUBE_API_KEY")
        if not api_key:
            if server and channel:
                server.send_message(channel, "YouTube API key not configured.")
            return "YouTube API key not configured."

        youtube = build("youtube", "v3", developerKey=api_key)
        request = youtube.search().list(
            part="snippet", q=query, type="video", maxResults=1
        )
        response = request.execute()

        if response["items"]:
            video = response["items"][0]
            title = video["snippet"]["title"]
            video_id = video["id"]["videoId"]
            url = f"https://www.youtube.com/watch?v={video_id}"
            message = f"{title} - {url}"
            if server and channel:
                server.send_message(channel, message)
            return message
        else:
            message = "Ei tuloksia haulle."
            if server and channel:
                server.send_message(channel, message)
            return message
    except Exception as e:
        log(f"Error searching YouTube for {query}: {e}", "ERROR")
        error_message = "Virhe haettaessa YouTube-videoita."
        if server and channel:
            server.send_message(channel, error_message)
        return error_message


def chat_with_gpt(server, channel: str, prompt: str):
    """Interact with OpenAI GPT model."""
    try:
        api_key = get_api_key("OPENAI_API_KEY")
        if not api_key:
            if server and channel:
                server.send_message(channel, "OpenAI API key not configured.")
            return "OpenAI API key not configured."

        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
        )
        message = response.choices[0].message.content.strip()

        with conversation_history_lock:
            history = load_conversation_history()
            history.append(
                {
                    "prompt": prompt,
                    "response": message,
                    "timestamp": datetime.now().isoformat(),
                }
            )
            save_conversation_history(history)

        if server and channel:
            for part in split_message_intelligently(message):
                server.send_message(channel, part)
        return message
    except Exception as e:
        log(f"Error in GPT chat: {e}", "ERROR")
        error_message = "Virhe GPT-keskustelussa."
        if server and channel:
            server.send_message(channel, error_message)
        return error_message


def load_conversation_history() -> dict:
    """Load conversation history from file."""
    with conversation_history_lock:
        if not os.path.exists(HISTORY_FILE):
            return []
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as file:
                return json.load(file)
        except Exception as e:
            log(f"Error loading conversation history: {e}", "ERROR")
            return []


def handle_youtube_search(
    server, channel: str, message: str, sender: str, args: List[str]
):
    """Handle !youtube command."""
    if not args:
        server.send_message(channel, "Käytä komentoa: !youtube <hakusana>")
        return
    query = " ".join(args)
    threading.Thread(
        target=search_youtube, args=(server, channel, query), daemon=True
    ).start()


def handle_eurojackpot(
    server, channel: str, message: str, sender: str, args: List[str]
):
    """Handle !eurojackpot command."""
    try:
        url = "https://www.veikkaus.fi/fi/tulokset#!/tulokset/eurojackpot"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        result = soup.find("div", class_="result").text.strip()[:100]
        server.send_message(channel, f"Eurojackpot: {result}")
    except Exception as e:
        log(f"Error fetching Eurojackpot results: {e}", "ERROR")
        server.send_message(channel, "Virhe haettaessa Eurojackpot-tuloksia.")


def handle_weather(server, sender: str, channel: str, message: str):
    """Handle !sää command."""
    log(f"Handling weather command: {message} from {sender} in {channel}", "DEBUG")
    parts = message.split(" ", 1)
    location = parts[1].strip() if len(parts) > 1 else "Joensuu"
    threading.Thread(
        target=send_weather, args=(server, channel, location), daemon=True
    ).start()


def handle_time(server, sender: str, channel: str, message: str):
    """Handle !aika command."""
    server.send_message(
        channel,
        f"Nykyinen aika: {datetime.now().isoformat(timespec='microseconds') + '000'}",
    )


def handle_echo(server, sender: str, channel: str, message: str):
    """Handle !kaiku command."""
    parts = message.split(" ", 1)
    if len(parts) > 1:
        server.send_message(channel, f"{sender}: {parts[1]}")
    else:
        server.send_message(channel, "Käytä komentoa: !kaiku <teksti>")


def handle_word_count(server, sender: str, channel: str, message: str):
    """Handle !sana command."""
    parts = message.split(" ", 1)
    if len(parts) < 2:
        server.send_message(channel, "Käytä komentoa: !sana <sana>")
        return
    search_word = parts[1].lower()
    kraks = load()
    word_counts = {
        nick: stats[search_word]
        for nick, stats in kraks.items()
        if search_word in stats
    }
    if word_counts:
        results = ", ".join(f"{nick}: {count}" for nick, count in word_counts.items())
        server.send_message(channel, f"Sana '{search_word}' on sanottu: {results}")
    else:
        server.send_message(
            channel, f"Kukaan ei ole sanonut sanaa '{search_word}' vielä."
        )


def handle_top_words(server, sender: str, channel: str, message: str):
    """Handle !top command."""
    kraks = load()
    if not kraks:
        server.send_message(channel, "Ei sanadataa saatavilla.")
        return
    top_words = sorted(
        [
            (word, count)
            for nick, stats in kraks.items()
            for word, count in stats.items()
        ],
        key=lambda x: x[1],
        reverse=True,
    )[:5]
    if top_words:
        results = ", ".join(f"{word}: {count}" for word, count in top_words)
        server.send_message(channel, f"Top sanat: {results}")
    else:
        server.send_message(channel, "Ei suosittuja sanoja vielä.")


def handle_leaderboard(server, sender: str, channel: str, message: str):
    """Handle !leaderboard command."""
    kraks = load()
    if not kraks:
        server.send_message(channel, "Ei sanadataa saatavilla.")
        return
    leaderboard = sorted(
        [(nick, sum(stats.values())) for nick, stats in kraks.items()],
        key=lambda x: x[1],
        reverse=True,
    )[:5]
    if leaderboard:
        results = ", ".join(f"{nick}: {count}" for nick, count in leaderboard)
        server.send_message(channel, f"Johtotaulu: {results}")
    else:
        server.send_message(channel, "Ei johtajia vielä.")


def handle_euribor(server, sender: str, channel: str, message: str):
    """Handle !euribor command."""
    try:
        url = "https://www.suomenpankki.fi/fi/Tilastot/korot/euribor-korot/"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        rate = soup.find("span", class_="euribor-rate").text.strip()
        server.send_message(channel, f"Euribor-korko: {rate}")
    except Exception as e:
        log(f"Error fetching Euribor rate: {e}", "ERROR")
        server.send_message(channel, "Virhe haettaessa Euribor-korkoa.")


def handle_leet_winners(server, sender: str, channel: str, message: str):
    """Handle !leet_winners command."""
    with leet_winners_lock:
        try:
            with open("leet_winners.json", "r", encoding="utf-8") as f:
                leet_winners = json.load(f)
        except Exception as e:
            log(f"Error loading leet winners: {e}", "ERROR")
            server.send_message(channel, "Virhe haettaessa leet-voittajia.")
            return
        if leet_winners:
            results = ", ".join(
                f"{nick}: {count}" for nick, count in leet_winners.items()
            )
            server.send_message(channel, f"Leet-voittajat: {results}")
        else:
            server.send_message(channel, "Ei leet-voittajia vielä.")


def handle_url_title(server, sender: str, channel: str, message: str):
    """Handle !title command."""
    parts = message.split(" ", 1)
    if len(parts) < 2:
        server.send_message(channel, "Käytä komentoa: !title <url>")
        return
    url = parts[1].strip()
    threading.Thread(
        target=fetch_title, args=(server, channel, url), daemon=True
    ).start()


def handle_leet(server, sender: str, channel: str, message: str):
    """Handle !leet command."""
    now = datetime.now()
    if now.hour == 13 and now.minute == 37:
        with leet_winners_lock:
            leet_winners = load_leet_winners()
            leet_winners[sender] = leet_winners.get(sender, 0) + 1
            save_leet_winners(leet_winners)
            server.send_message(
                channel, f"{sender} voitti leet-ajan! Yhteensä: {leet_winners[sender]}"
            )
    else:
        server.send_message(channel, "Ei ole leet-aika (13:37).")


def handle_kraks(server, sender: str, channel: str, message: str):
    """Handle !kraks command."""
    with drink_words_lock:
        if server.drink_words:
            results = ", ".join(
                f"{word}: {count}"
                for word, count in server.drink_words.items()
                if count > 0
            )
            server.send_message(channel, f"Kraks-tilastot: {results}")
        else:
            server.send_message(channel, "Ei kraks-tilastoja vielä.")


def handle_ekavika(server, sender: str, channel: str, message: str):
    """Handle !ekavika command."""
    try:
        url = "https://www.ekarjala.fi/viat"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        outage = soup.find("div", class_="outage-info").text.strip()[:100]
        server.send_message(channel, f"Sähkökatkot: {outage}")
    except Exception as e:
        log(f"Error fetching outage info: {e}", "ERROR")
        server.send_message(channel, "Virhe haettaessa sähkökatkotietoja.")


def handle_crypto(server, sender: str, channel: str, message: str):
    """Handle !crypto command."""
    parts = message.split(" ", 1)
    coin = parts[1].strip().upper() if len(parts) > 1 else "BTC"
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin.lower()}&vs_currencies=eur"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        price = data.get(coin.lower(), {}).get("eur", "N/A")
        server.send_message(channel, f"{coin} hinta: {price} EUR")
    except Exception as e:
        log(f"Error fetching crypto price for {coin}: {e}", "ERROR")
        server.send_message(channel, f"Virhe haettaessa {coin} hintaa.")


def load_leet_winners() -> dict:
    """Load leet winners from file."""
    with leet_winners_lock:
        if not os.path.exists("leet_winners.json"):
            return {}
        try:
            with open("leet_winners.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log(f"Error loading leet winners: {e}", "ERROR")
            return {}


def process_message(
    server, message: str, channel: Optional[str] = None, sender: Optional[str] = None
):
    """Process an incoming IRC message."""
    try:
        log(f"Processing message from {sender}: {message}", "DEBUG")

        if sender and sender.lower() == server.bot_name.lower():
            return False

        # Parse PRIVMSG
        match = re.search(r":(\S+)!(\S+) PRIVMSG (\S+) :(.+)", message)
        if match:
            sender, _, target, text = match.groups()
            channel = target if target.startswith("#") else sender

            # Handle commands
            if text.startswith("!"):
                parts = text.split(maxsplit=1)
                command = parts[0].lower()
                args = parts[1].split() if len(parts) > 1 else []

                # Delegate to registered handlers
                if command[1:] in server.handlers:
                    server.handlers[command[1:]](server, sender, channel, text)
                    return True

                # Direct command processing
                if command == "!youtube":
                    handle_youtube_search(server, channel, text, sender, args)
                    return True
                elif command in ("!s", "!sää"):  # Added !s as alias for !sää
                    handle_weather(server, sender, channel, text)
                    return True
                elif command == "!sahko" or command == "!sähkö":
                    threading.Thread(
                        target=send_electricity_price,
                        args=(server, channel, [command] + args),
                        daemon=True,
                    ).start()
                    return True
                elif command == "!eurojackpot":
                    handle_eurojackpot(server, channel, text, sender, args)
                    return True
                elif command == "!gpt":
                    if args:
                        threading.Thread(
                            target=chat_with_gpt,
                            args=(server, channel, " ".join(args)),
                            daemon=True,
                        ).start()
                    else:
                        server.send_message(channel, "Käytä komentoa: !gpt <teksti>")
                    return True

            # Handle URLs
            url_pattern = re.compile(r"https?://\S+")
            urls = url_pattern.findall(text)
            if urls:
                for url in urls:
                    threading.Thread(
                        target=fetch_title, args=(server, channel, url), daemon=True
                    ).start()

            # Handle drink words
            for word in server.drink_words:
                if word in text.lower():
                    count_kraks(server, word, "unknown")

            return False

        return False
    except Exception as e:
        log(f"Error processing message: {str(e)}", "ERROR")
        log(traceback.format_exc(), "ERROR")
        return False
