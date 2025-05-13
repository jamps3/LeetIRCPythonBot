"""
This script is an IRC bot that connects to an IRC server, joins a channel, and responds to various commands.
It includes functionalities such as fetching weather information, electricity prices, webpage titles and scheduled messages.
Modules:
    - socket: Provides low-level networking interface.
    - os: Provides a way of using operating system dependent functionality.
    - time: Provides various time-related functions.
    - threading: Provides higher-level threading interface.
    - re: Provides regular expression matching operations.
    - requests: Allows sending HTTP requests.
    - pickle: Implements binary protocols for serializing and de-serializing a Python object structure.
    - datetime: Supplies classes for manipulating dates and times.
    - BeautifulSoup: Parses HTML and XML documents.
    - ElementTree: Provides a simple and efficient API for parsing and creating XML data.
    - urllib.parse: Defines functions to manipulate URLs.
Functions:
    - save(): Saves the current state of 'kraks' and 'leets' to a binary file.
    - load(): Loads the state of 'kraks' and 'leets' from a binary file.
    - login(irc, writer): Logs the bot into the IRC server and joins a specified channel.
    - read(irc): Reads messages from the IRC server and processes them.
    - keepalive_ping(irc): Sends periodic PING messages to keep the connection alive.
    - process_message(irc, message): Processes incoming IRC messages and responds to commands.
    - send_leet(irc, channel, message, target_hour, target_minute, target_second, target_microsecond): Sends a message at a specific time.
    - send_weather(irc, channel, location): Fetches and sends weather information for a specified location.
    - send_electricity_price(irc, channel, text): Fetches and sends electricity price information for a specified hour.
    - fetch_title(irc, channel, text): Fetches and sends the title of a webpage from a URL.
    - send_message(irc, channel, message): Sends a message to a specified IRC channel.
    - log(message, level): Logs a message with a timestamp and specified log level.
    - main(): Main function to start the bot, connect to the IRC server, and handle reconnections.
"""

import random
import sys  # Check if Debugging
import platform  # For checking where are we running for correct datetime formatting
import socket
import os  # For file handling and environment variables
import time
import threading  # Threading
import re  # Regular expression
import requests
import pickle  # Tiedostojen tallennukseen
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from io import StringIO
import xml.etree.ElementTree as ElementTree
import openai
import urllib.parse  # Lisätään URL-koodausta varten
from dotenv import load_dotenv  # Load api-keys, servers and channels from .env file
from collections import Counter
import json  # json support
import argparse  # Command line argument parsing
from googleapiclient.discovery import build  # Youtube API
import signal
import html  # Title quote removal
import subprocess  # IPFS
import tempfile  # IPFS

bot_name = "jl3b"  # Botin oletus nimi, voi vaihtaa komentoriviltä -nick parametrilla
LOG_LEVEL = "INFO"  # Log level oletus, EI VAIHDA TÄTÄ, se tapahtuu main-funktiossa
HISTORY_FILE = "conversation_history.json"  # File to store conversation history
EKAVIKA_FILE = "ekavika.json"  # File to store ekavika winners
WORDS_FILE = "kraks_data.pkl"  # File to store words data
RECONNECT_DELAY = 60  # Time in seconds before retrying connection (irc.settimeout = RECONNECT_DELAY * 2)
QUIT_MESSAGE = "🍺 Nähdään! 🍺"

# All drink words to track
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
    "tsirp": 0,
}

# Default history with system prompt
DEFAULT_HISTORY = [
    {
        "role": "system",
        "content": "You are a helpful assistant who knows about Finnish beer culture. You respond in a friendly, short and tight manner. If you don't know something, just say so. Keep responses brief, we are on IRC.",
    }
]

# Aseta API-avaimet
load_dotenv()  # Lataa .env-tiedoston muuttujat
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
ELECTRICITY_API_KEY = os.getenv("ELECTRICITY_API_KEY")
api_key = os.getenv("OPENAI_API_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

last_ping = time.time()
last_title = ""

# Luo OpenAI-asiakasolio (uusi tapa OpenAI 1.0.0+ versiossa)
client = openai.OpenAI(api_key=api_key)

# Initialize YouTube API client
youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

# Sanakirja, joka pitää kirjaa voitoista
voitot = {"ensimmäinen": {}, "viimeinen": {}, "multileet": {}}

# Create a stop event to handle clean shutdown
stop_event = threading.Event()


def search_youtube(query, max_results=1):
    """
    Example usage:
    result = search_youtube("Python tutorial")
    result = search_youtube("dQw4w9WgXcQ")
    """
    try:
        if query is None:
            log("Received query is None", "ERROR")
            return "Error: Received query is None."

        log(f"Received query: {query}", "DEBUG")

        # Tarkistetaan onko query todennäköisesti video-ID
        is_video_id = re.fullmatch(r"[a-zA-Z0-9_-]{11}", query)
        log(f"Is query a valid video ID? {is_video_id}", "DEBUG")

        # Tarkistetaan onko query YouTube Shorts -linkki
        if not is_video_id:
            short_match = re.match(
                r"https://www\.youtube\.com/shorts/([a-zA-Z0-9_-]{11})", query
            )
            if short_match:
                query = short_match.group(1)
                is_video_id = True
                log(
                    f"Detected YouTube Shorts link, extracted video ID: {query}",
                    "DEBUG",
                )
            else:
                log(f"Query is not a valid YouTube Shorts link: {query}", "DEBUG")

        log(f"After processing Shorts link, query is: {query}", "DEBUG")

        if query is None:
            log("Query is None after Shorts extraction", "DEBUG")
            return "Error: Query is None after Shorts extraction."

        if is_video_id:  # Hae videon tiedot ID:llä
            log(f"Searching video by ID: {query}", "DEBUG")
            request = youtube.videos().list(id=query, part="snippet")
            response = request.execute()

            log(f"Response received: {response}", "DEBUG")

            items = response.get("items", [])
            if not items:
                log(f"No video found with the given ID: {query}", "INFO")
                return "No video found with the given ID."

            item = items[0]
            video_title = html.unescape(item["snippet"]["title"]).replace("  ", " ")
            video_url = f"https://www.youtube.com/watch?v={query}"
            log(f"Found video: {video_title} ({video_url})", "DEBUG")
            return f"'{video_title}' URL: {video_url}"
        else:  # Tekstihaku
            log(f"Searching video by query: {query}", "DEBUG")
            request = youtube.search().list(
                q=query,
                part="snippet",
                maxResults=max_results,
                type="video",  # This will ensure only videos are returned
            )
            response = request.execute()

            log(f"Response received: {response}", "DEBUG")

            items = response.get("items", [])
            if not items:
                log(f"No results found for query: {query}", "INFO")
                return "No results found."

            item = items[0]
            video_title = html.unescape(item["snippet"]["title"]).replace("  ", " ")
            video_id = item["id"]["videoId"]
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            log(f"Found video: {video_title} ({video_url})", "DEBUG")
            return f"'{video_title}' URL: {video_url}"

    except Exception as e:
        log(f"An error occurred while searching for YouTube video: {e}", "ERROR")
        return f"An error occurred: {e}"


def load_conversation_history():
    """Loads the conversation history from a file or initializes a new one."""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    return DEFAULT_HISTORY.copy()


def save_conversation_history(history):
    """Saves the conversation history to a file."""
    with open(HISTORY_FILE, "w", encoding="utf-8") as file:
        json.dump(history, file, indent=4, ensure_ascii=False)


def tallenna_voittaja(tyyppi, nimi):
    if nimi in voitot[tyyppi]:
        voitot[tyyppi][nimi] += 1
    else:
        voitot[tyyppi][nimi] = 1


def load_leet_winners():
    """Loads the leet winners from a JSON file."""
    try:
        with open("leet_winners.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        log(
            "Error loading leet winners from file leet_winners.json, creating a new file.",
            "ERROR",
        )
        return (
            {}
        )  # Return an empty dictionary if the file does not exist or is corrupted


def save_leet_winners(leet_winners):
    """Saves the leet winners to a JSON file."""
    with open("leet_winners.json", "w", encoding="utf-8") as f:
        json.dump(leet_winners, f, indent=4, ensure_ascii=False)


def save(kraks, file_path=WORDS_FILE):
    """
    Saves kraks (IRC nick word stats) to a file using pickle.

    # Example Usage:
    kraks = load()  # Load existing stats or create a new one

    # Simulating message tracking
    update_kraks(kraks, "Alice", ["hello", "world", "hello"])
    update_kraks(kraks, "Bob", ["python", "hello"])

    # Save the updated data
    save(kraks)
    """
    try:
        with open(file_path, "wb") as f:
            pickle.dump(kraks, f)
    except Exception as e:
        log(f"Error saving data: {e}", "ERROR")


def load(file_path=WORDS_FILE):
    """Loads kraks (IRC nick word stats) from a file using pickle, with error handling."""
    if not os.path.exists(file_path):
        log("Data file not found, creating a new one.", "ERROR")
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


def update_kraks(kraks, nick, words):
    """
    Updates the word stats for a given IRC nick.
    - `nick`: The IRC nickname.
    - `words`: A list of words the nick has used.
    """
    if nick not in kraks:
        kraks[nick] = {}

    for word in words:
        kraks[nick][word] = kraks[nick].get(word, 0) + 1


def login(irc, writer, bot_name, channels, show_api_keys=False):
    """
    Logs into the IRC server, waits for the MOTD to finish, and joins multiple channels.
    Implements automatic reconnection in case of disconnection.

    Args:
        irc: The IRC connection object (socket).
        writer: The socket writer used to send messages.
        bot_name: The name of the bot.
        channels (list): List of channels to join.
        show_api_keys (bool): Whether to display API keys in logs.
    """
    while True:  # Infinite loop for automatic reconnection
        try:
            nick = bot_name
            login = bot_name

            # Log API keys if requested
            if show_api_keys:
                log(f"Weather API Key: {WEATHER_API_KEY}", "DEBUG")
                log(f"Electricity API Key: {ELECTRICITY_API_KEY}", "DEBUG")
                log(f"OpenAI API Key: {api_key}", "DEBUG")
            else:
                log("API keys loaded (use -api flag to show values)", "INFO")

            writer.sendall(f"NICK {nick}\r\n".encode("utf-8"))
            writer.sendall(f"USER {login} 0 * :{nick}\r\n".encode("utf-8"))

            last_response_time = time.time()  # Track last received message time
            while True:
                response = irc.recv(2048).decode("utf-8", errors="ignore")
                if response:
                    last_response_time = time.time()  # Reset timeout on any message

                for line in response.split("\r\n"):
                    if line:
                        log(f"MOTD: {line}", "SERVER")

                    if "jl3b2 :Nickname is already in use." in line:
                        log(
                            "Nickname is already in use. Trying again with a different one...",
                            "ERROR",
                        )
                        nick = f"{bot_name}{random.randint(1, 100)}"
                        writer.sendall(f"NICK {nick}\r\n".encode("utf-8"))
                        continue

                    # If server says "Please wait while we process your connection", don't disconnect yet
                    if " 020 " in line:
                        log(
                            "Server is processing connection, waiting...",
                            "INFO",
                        )
                        last_response_time = (
                            time.time()
                        )  # Reset timeout so it doesn't assume failure
                        continue  # Keep waiting instead of assuming failure

                    # If MOTD completion (376/422) received, join channels
                    if " 376 " in line or " 422 " in line:
                        log("MOTD complete, joining channels...", "INFO")

                        for channel, key in channels:
                            if key:
                                writer.sendall(
                                    f"JOIN {channel} {key}\r\n".encode("utf-8")
                                )
                                log(f"Joined channel {channel} with key", "INFO")
                            else:
                                writer.sendall(f"JOIN {channel}\r\n".encode("utf-8"))
                                log(f"Joined channel {channel} (no key)", "INFO")

                        return  # Successfully joined, exit function

                # Timeout handling: If no response received in RECONNECT_DELAY seconds, assume failure
                if time.time() - last_response_time > RECONNECT_DELAY:
                    raise socket.timeout(
                        f"No response from server for {RECONNECT_DELAY} seconds"
                    )

        except socket.timeout:
            continue  # Ignore timeout errors silently and keep going
        except (
            socket.error,
            ConnectionResetError,
            BrokenPipeError,
        ) as e:
            log(
                f"Connection lost: {e}. Reconnecting in {RECONNECT_DELAY} seconds...",
                "ERROR",
            )
            time.sleep(RECONNECT_DELAY)

        except Exception as e:
            log(
                f"Unexpected error: {e}. Reconnecting in {RECONNECT_DELAY} seconds...",
                "ERROR",
            )
            time.sleep(RECONNECT_DELAY)


# Main loop to read messages from IRC
def read(irc, stop_event):
    log("Starting read loop...", "DEBUG")
    global last_ping, latency_start

    try:
        while not stop_event.is_set():  # Check if shutdown is requested
            try:
                data = irc.recv(4096)
                if not data:
                    log(
                        "Received empty data, server may have closed the connection.",
                        "ERROR",
                    )
                    raise ConnectionError("Server closed connection.")
                response = data.decode("utf-8", errors="ignore")
            except socket.timeout:
                continue  # Ignore timeout errors silently and keep listening

            for line in response.strip().split("\r\n"):  # Handle multiple messages
                log(line.strip(), "SERVER")

                if line.startswith("PING"):  # Handle PING
                    last_ping = time.time()
                    ping_value = line.split(":", 1)[1].strip()
                    irc.sendall(f"PONG :{ping_value}\r\n".encode("utf-8"))
                    log(f"Sent PONG response to {ping_value}", "DEBUG")

                try:
                    process_message(irc, line)  # Process each message separately
                except Exception as e:
                    log(f"Error while processing message: {e}", "ERROR")

    except Exception as e:
        log(f"Error in read(): {e}", "ERROR")
        raise


def listen_for_commands(stop_event):
    """Listen for user input from the terminal and send to IRC or process locally."""
    try:
        while not stop_event.is_set():
            user_input = input("")  # Read input from terminal
            if not user_input:
                continue

            if user_input.lower() == "quit":
                log("Exiting bot...", "INFO")
                stop_event.set()  # Notify all threads to stop
                break
            elif user_input.startswith("!"):
                # Parse command
                command_parts = user_input.split(" ", 1)
                command = command_parts[0].lower()
                args = command_parts[1] if len(command_parts) > 1 else ""
                log(f"Processing command {command} with args: {args}", "CMD")

                # List all commands
                if command == "!help":
                    notice_message(
                        "Available commands: quit, !s !sää, !sahko !sähkö, !aika, !kaiku, !sana, !topwords, !leaderboard, !euribor, !leetwinners, !url <url>, (!kraks, !clearkraks)"
                    )

                # Handle commands similar to IRC commands
                elif command == "!s" or command == "!sää":
                    location = args.strip() if args else "Joensuu"
                    log(f"Getting weather for {location} from console", "INFO")
                    send_weather(None, None, location)  # Pass None for IRC and channel

                elif command == "!sahko" or command == "!sähkö":
                    send_electricity_price(None, None, command_parts)

                elif command == "!aika":
                    now_ns = time.time_ns()
                    dt = datetime.fromtimestamp(now_ns // 1_000_000_000)
                    nanoseconds = now_ns % 1_000_000_000

                    formatted_time = (
                        dt.strftime("%Y-%m-%d %H:%M:%S") + f".{nanoseconds:09d}"
                    )
                    notice_message(f"Nykyinen aika: {formatted_time}")

                elif command == "!kaiku":
                    notice_message(f"Console: {args}")

                elif command == "!sana":
                    if args:
                        search_word = args.strip().lower()
                        kraks = load()

                        word_counts = {
                            nick: stats[search_word]
                            for nick, stats in kraks.items()
                            if search_word in stats
                        }

                        if word_counts:
                            results = ", ".join(
                                f"{nick}: {count}"
                                for nick, count in word_counts.items()
                            )
                            notice_message(
                                f"Sana '{search_word}' on sanottu: {results}"
                            )
                        else:
                            notice_message(
                                f"Kukaan ei ole sanonut sanaa '{search_word}' vielä."
                            )
                    else:
                        notice_message("Käytä komentoa: !sana <sana>")

                elif command == "!topwords":
                    kraks = load()

                    if args:  # Specific nick provided
                        nick = args.strip()
                        if nick in kraks:
                            top_words = Counter(kraks[nick]).most_common(5)
                            word_list = ", ".join(
                                f"{word}: {count}" for word, count in top_words
                            )
                            notice_message(f"{nick}: {word_list}")
                        else:
                            notice_message(f"Käyttäjää '{nick}' ei löydy.")
                    else:  # Show top words for all users
                        overall_counts = Counter()
                        for words in kraks.values():
                            overall_counts.update(words)

                        top_words = overall_counts.most_common(5)
                        word_list = ", ".join(
                            f"{word}: {count}" for word, count in top_words
                        )
                        notice_message(f"Käytetyimmät sanat: {word_list}")

                elif command == "!leaderboard":
                    kraks = load()
                    user_word_counts = {
                        nick: sum(words.values()) for nick, words in kraks.items()
                    }
                    top_users = sorted(
                        user_word_counts.items(), key=lambda x: x[1], reverse=True
                    )[:5]

                    if top_users:
                        leaderboard_msg = ", ".join(
                            f"{nick}: {count}" for nick, count in top_users
                        )
                        notice_message(f"Aktiivisimmat käyttäjät: {leaderboard_msg}")
                    else:
                        notice_message("Ei vielä tarpeeksi dataa leaderboardille.")

                elif command == "!euribor":
                    # XML data URL from Suomen Pankki
                    url = "https://reports.suomenpankki.fi/WebForms/ReportViewerPage.aspx?report=/tilastot/markkina-_ja_hallinnolliset_korot/euribor_korot_today_xml_en&output=xml"

                    # Fetch the XML data
                    response = requests.get(url)

                    if response.status_code == 200:
                        # Parse the XML content
                        root = ElementTree.fromstring(response.content)

                        # Namespace handling (because the XML uses a default namespace)
                        ns = {
                            "ns": "euribor_korot_today_xml_en"
                        }  # Update with correct namespace if needed

                        # Find the correct period (yesterday's date)
                        period = root.find(".//ns:period", namespaces=ns)
                        if period is not None:
                            # Extract the date from the XML attribute
                            date_str = period.attrib.get("value")  # Muoto YYYY-MM-DD
                            date_obj = datetime.strptime(
                                date_str, "%Y-%m-%d"
                            )  # Muunnetaan datetime-objektiksi

                            # Käytetään oikeaa muotoilua riippuen käyttöjärjestelmästä
                            if platform.system() == "Windows":
                                formatted_date = date_obj.strftime(
                                    "%#d.%#m.%y"
                                )  # Windows
                            else:
                                formatted_date = date_obj.strftime(
                                    "%-d.%-m.%y"
                                )  # Linux & macOS
                            rates = period.findall(".//ns:rate", namespaces=ns)

                            for rate in rates:
                                if rate.attrib.get("name") == "12 month (act/360)":
                                    euribor_12m = rate.find("./ns:intr", namespaces=ns)
                                    if euribor_12m is not None:
                                        notice_message(
                                            f"{formatted_date} 12kk Euribor: {euribor_12m.attrib['value']}%"
                                        )
                                    else:
                                        notice_message("Interest rate value not found.")
                                    break
                            else:
                                notice_message("12-month Euribor rate not found.")
                        else:
                            notice_message("No period data found in XML.")
                    else:
                        notice_message(
                            f"Failed to retrieve XML data. HTTP Status Code: {response.status_code}"
                        )

                elif command == "!leetwinners":
                    leet_winners = load_leet_winners()

                    # Dictionary to store only one winner per category
                    filtered_winners = {}

                    for winner, categories in leet_winners.items():
                        for cat, count in categories.items():
                            # Ensure only one winner per category
                            if (
                                cat not in filtered_winners
                                or count > filtered_winners[cat][1]
                            ):
                                filtered_winners[cat] = (winner, count)

                    # Format the output
                    winners_text = ", ".join(
                        f"{cat}: {winner} [{count}]"
                        for cat, (winner, count) in filtered_winners.items()
                    )

                    response = (
                        f"Leet winners: {winners_text}"
                        if winners_text
                        else "No leet winners recorded yet."
                    )
                    notice_message(response)

                elif command.startswith("!url"):  # Handle URL title fetching
                    if args:
                        fetch_title(None, None, args)
                    else:
                        notice_message("Käytä komentoa: !url <url>")

                elif command.startswith("!ipfs"):
                    if not args:
                        notice_message("Usage: !ipfs <url>")
                        return
                    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
                    url = args.strip()
                    log(f"Received !ipfs command with URL: {url}", "DEBUG")

                    try:
                        # Stream download and limit size
                        response = requests.get(url, stream=True, timeout=10)
                        response.raise_for_status()

                        total_size = 0
                        with tempfile.NamedTemporaryFile(delete=False) as tmp:
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    total_size += len(chunk)
                                    if total_size > MAX_FILE_SIZE:
                                        tmp.close()
                                        os.remove(tmp.name)
                                        notice_message(
                                            "File too large (limit is 100MB)."
                                        )
                                        log(
                                            "Aborted: File exceeded 100MB during download.",
                                            "DEBUG",
                                        )
                                        return
                                    tmp.write(chunk)
                            tmp_path = tmp.name

                        log(
                            f"Downloaded file to temporary path: {tmp_path} ({total_size} bytes)",
                            "DEBUG",
                        )

                        # Add file to IPFS
                        result = subprocess.run(
                            ["ipfs", "add", "-q", tmp_path],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                        )

                        os.remove(tmp_path)

                        if result.returncode == 0:
                            ipfs_hash = result.stdout.strip()
                            ipfs_url = f"https://ipfs.io/ipfs/{ipfs_hash}"
                            log(f"File added to IPFS with hash: {ipfs_hash}", "DEBUG")
                            notice_message(f"Added to IPFS: {ipfs_url}")
                        else:
                            error_msg = result.stderr.strip()
                            log(f"IPFS add failed: {error_msg}", "DEBUG")
                            notice_message("Failed to add file to IPFS.")

                    except Exception as e:
                        log(f"Exception during !ipfs handling: {str(e)}", "DEBUG")
                        notice_message("Error handling !ipfs request.")

                else:
                    notice_message(
                        f"Command '{command}' not recognized or not implemented for console use"
                    )
            else:
                # Any text not starting with ! is sent to OpenAI
                log(f"Sending text to OpenAI: {user_input}", "INFO")
                response_parts = chat_with_gpt(user_input)
                for part in response_parts:
                    log(f"Bot: {part}", "MSG")
    except (EOFError, KeyboardInterrupt):
        stop_event.set()


def count_kraks(word, beverage):
    """
    Counts the occurrences of a specific word (beverage) in the IRC messages.

    Args:
        word (str): The word to track (e.g., "krak").
        beverage (str): The beverage associated with the word (e.g., "karhu").
    """
    if word in DRINK_WORDS:
        DRINK_WORDS[word] += 1
        log(f"Detected {word} ({beverage}). Total count: {DRINK_WORDS[word]}")
    else:
        log(f"Word {word} is not in the tracking list.")


def keepalive_ping(irc, stop_event):
    global last_ping
    while not stop_event.is_set():
        time.sleep(2)  # Check more frequently for stop event

        if time.time() - last_ping > 120:
            try:
                # Send keepalive ping to server
                irc.sendall("PING :keepalive\r\n".encode("utf-8"))
                log("Sent keepalive PING", "DEBUG")
                last_ping = time.time()
            except Exception as e:  # Continue running but log the error
                log(f"Unexpected error during keepalive ping: {e}", "ERROR")
                raise


def process_message(irc, message):
    """Processes incoming IRC messages and tracks word statistics."""
    global latency_start
    global bot_name
    is_private = False
    match = re.search(r":(\S+)!(\S+) PRIVMSG (\S+) :(.+)", message)

    if match:
        sender, _, target, text = match.groups()

        # Process each message sent to the channel and detect drinking words.
        # Regex pattern to find words in the format "word (beverage)"
        match = re.search(r"(\w+)\s*\(\s*([\w\s]+)\s*\)", text)

        if match:
            word = match.group(
                1
            ).lower()  # First captured word (e.g., "krak"). Convert to lowercase for consistent matching
            beverage = match.group(
                2
            ).lower()  # Second captured word inside parentheses (e.g., "karhu")

            if (
                word in DRINK_WORDS
            ):  # Check if the first word is in the DRINKING_WORDS list
                count_kraks(word, beverage)  # Call the function with extracted values

        # Check if the message is a private message (not a channel)
        if target.lower() == bot_name.lower():  # Private message detected
            log(f"Private message from {sender}: {text}", "MSG")
            # irc.sendall(f"PRIVMSG {sender} :Hello! You said: {text}\r\n".encode("utf-8"))
            is_private = target.lower() == bot_name.lower()  # Private message check

        else:  # Normal channel message
            log(f"Channel message in {target} from {sender}: {text}", "MSG")
            # Fetch titles of URLs
            fetch_title(irc, target, text)

        # ✅ Prevent bot from responding to itself
        if sender.lower() == bot_name.lower():
            log("🔄 Ignoring bot's own message to prevent loops.", "DEBUG")

            # ❌ Ignore the bot's own latency response completely
            if text.startswith("Latency is ") and "ns" in text:
                return  # Stop processing immediately

            # Handle bot's own LatencyCheck response
            if "!LatencyCheck" in text:
                if "latency_start" in globals():
                    elapsed_time = time.time() - latency_start
                    latency_ns = int(elapsed_time * 1_000_000_000)  # Convert to ns

                    # ✅ Estimate one-way latency
                    half_latency_ns = latency_ns // 2

                    log(
                        f"✅ Recognized LatencyCheck response! Latency: {elapsed_time:.3f} s ({latency_ns} ns)"
                    )

                    # **Before sending, subtract half_latency_ns to improve accuracy**
                    corrected_latency_ns = latency_ns - half_latency_ns
                    irc.sendall(
                        f"PRIVMSG {bot_name} :Latency is {corrected_latency_ns} ns\r\n".encode(
                            "utf-8"
                        )
                    )

                else:
                    log(
                        "⚠️ Warning: Received LatencyCheck response, but no latency_start timestamp exists.",
                        "ERROR",
                    )

            return  # Stop further processing

        # Track words only if it's not a bot command
        if not text.startswith(("!")):  # Track all lines except commands
            words = re.findall(r"\b\w+\b", text.lower())  # Extract words, ignore case
            kraks = load()
            update_kraks(kraks, sender, words)
            save(kraks)  # Save updates immediately

        # Output all available commands
        if text.startswith("!help"):
            notice_message(
                "Available commands: !s !sää, !sahko !sähkö, !aika, !kaiku, !sana, !topwords, !leaderboard, !euribor, !leetwinners, !url <url>, !kraks",
                irc,
                target,
            )

        # !aika - Kerro nykyinen aika
        elif text.startswith("!aika"):
            notice_message(f"Nykyinen aika: {datetime.now()}", irc, target)

        # !kaiku - Kaiuta teksti
        elif text.startswith("!kaiku"):
            notice_message(f"{sender}: {text[len(sender)+2:]}", irc, target)

        # !sahko - Kerro pörssisähkön hintatiedot tänään ja huomenna, jos saatavilla
        elif text.startswith("!sahko") or text.startswith("!sähkö"):
            parts = text.split(" ", 1)
            send_electricity_price(irc, target, parts)

        # !sana - Sanalaskuri
        elif text.startswith("!sana "):
            parts = text.split(" ", 1)
            if len(parts) > 1:
                search_word = parts[1].strip().lower()  # Normalize case
                kraks = load()  # Reload word data

                word_counts = {
                    nick: stats[search_word]
                    for nick, stats in kraks.items()
                    if search_word in stats
                }

                if word_counts:
                    results = ", ".join(
                        f"{nick}: {count}" for nick, count in word_counts.items()
                    )
                    notice_message(
                        f"Sana '{search_word}' on sanottu: {results}", irc, target
                    )
                else:
                    notice_message(
                        f"Kukaan ei ole sanonut sanaa '{search_word}' vielä.",
                        irc,
                        target,
                    )
            else:
                notice_message("Käytä komentoa: !sana <sana>", irc, target)

        # !topwords - Käytetyimmät sanat
        elif text.startswith("!topwords"):
            parts = text.split(" ", 1)
            kraks = load()

            if len(parts) > 1:  # Specific nick provided
                nick = parts[1].strip()
                if nick in kraks:
                    top_words = Counter(kraks[nick]).most_common(5)
                    word_list = ", ".join(
                        f"{word}: {count}" for word, count in top_words
                    )
                    notice_message(f"{nick}: {word_list}", irc, target)
                else:
                    notice_message(f"Käyttäjää '{nick}' ei löydy.", irc, target)
            else:  # Show top words for all users
                overall_counts = Counter()
                for words in kraks.values():
                    overall_counts.update(words)

                top_words = overall_counts.most_common(5)
                word_list = ", ".join(f"{word}: {count}" for word, count in top_words)
                notice_message(f"Käytetyimmät sanat: {word_list}", irc, target)

        # !leaderboard - Aktiivisimmat käyttäjät
        elif text.startswith("!leaderboard"):
            kraks = load()
            user_word_counts = {
                nick: sum(words.values()) for nick, words in kraks.items()
            }
            top_users = sorted(
                user_word_counts.items(), key=lambda x: x[1], reverse=True
            )[:5]

            if top_users:
                leaderboard_msg = ", ".join(
                    f"{nick}: {count}" for nick, count in top_users
                )
                notice_message(
                    f"Aktiivisimmat käyttäjät: {leaderboard_msg}", irc, target
                )
            else:
                notice_message("Ei vielä tarpeeksi dataa leaderboardille.", irc, target)

        # !kraks - Krakkaukset
        elif text.startswith("!kraks"):
            kraks = load()
            total_kraks = 0
            word_counts = DRINK_WORDS.copy()
            top_users = {word: None for word in word_counts.keys()}

            # Count occurrences and track top users
            for nick, words in kraks.items():
                for word in word_counts.keys():
                    count = words.get(word, 0)
                    word_counts[word] += count
                    total_kraks += count

                    if count > 0 and (
                        top_users[word] is None
                        or count > kraks[top_users[word]].get(word, 0)
                    ):
                        top_users[word] = nick

            total_message = f"Krakit yhteensä: {total_kraks}"
            details = ", ".join(
                f"{word}: {count} [{top_users[word]}]"
                for word, count in word_counts.items()
                if count > 0
            )
            notice_message(f"{total_message}, {details}", irc, target)

        elif text.startswith("!clearkraks"):
            kraks = load()

            # Reset all tracked words
            for nick in kraks.keys():
                kraks[nick] = {}

            save(kraks)  # Save the cleared data
            log("Kaikki krakit on nollattu!")

        # !euribor - Uusin 12kk euribor
        elif text.startswith("!euribor"):
            # XML data URL from Suomen Pankki
            url = "https://reports.suomenpankki.fi/WebForms/ReportViewerPage.aspx?report=/tilastot/markkina-_ja_hallinnolliset_korot/euribor_korot_today_xml_en&output=xml"

            # Fetch the XML data
            response = requests.get(url)

            if response.status_code == 200:
                # Parse the XML content
                root = ElementTree.fromstring(response.content)

                # Namespace handling (because the XML uses a default namespace)
                ns = {
                    "ns": "euribor_korot_today_xml_en"
                }  # Update with correct namespace if needed

                # Find the correct period (yesterday's date)
                period = root.find(".//ns:period", namespaces=ns)
                if period is not None:
                    # Extract the date from the XML attribute
                    date_str = period.attrib.get("value")  # Muoto YYYY-MM-DD
                    date_obj = datetime.strptime(
                        date_str, "%Y-%m-%d"
                    )  # Muunnetaan datetime-objektiksi

                    # Käytetään oikeaa muotoilua riippuen käyttöjärjestelmästä
                    if platform.system() == "Windows":
                        formatted_date = date_obj.strftime("%#d.%#m.%y")  # Windows
                    else:
                        formatted_date = date_obj.strftime(
                            "%-d.%-m.%y"
                        )  # Linux & macOS
                    rates = period.findall(".//ns:rate", namespaces=ns)

                    for rate in rates:
                        if rate.attrib.get("name") == "12 month (act/360)":
                            euribor_12m = rate.find("./ns:intr", namespaces=ns)
                            if euribor_12m is not None:
                                log(
                                    f"{formatted_date} 12kk Euribor: {euribor_12m.attrib['value']}%",
                                    "DEBUG",
                                )
                                notice_message(
                                    f"{formatted_date} 12kk Euribor: {euribor_12m.attrib['value']}%",
                                    irc,
                                    target,
                                )
                            else:
                                log("Interest rate value not found.", "ERROR")
                            break
                    else:
                        log("12-month Euribor rate not found.", "ERROR")
                else:
                    log("No period data found in XML.", "ERROR")
            else:
                log(
                    f"Failed to retrieve XML data. HTTP Status Code: {response.status_code}",
                    "ERROR",
                )

        # !latencycheck - Handle latency check response
        # User sent !latencycheck command
        elif text.startswith("!latencycheck"):
            log("Received !latencycheck command, measuring latency...")
            measure_latency(irc, bot_name)

        # Checks if the message contains a crypto request and fetches price.
        elif re.search(r"!crypto\b", text, re.IGNORECASE):
            match = re.search(r"!crypto\s+(\w+)", text, re.IGNORECASE)

            if match:
                # Fetch specific coin price
                coin = match.group(1).lower()
                price = get_crypto_price(coin, "eur")
                message = f"The current price of {coin.capitalize()} is {price} €."
            else:
                # Fetch top 3 most popular cryptocurrencies
                top_coins = ["bitcoin", "ethereum", "tether"]
                prices = {coin: get_crypto_price(coin, "eur") for coin in top_coins}
                message = " | ".join(
                    [f"{coin.capitalize()}: {prices[coin]} €" for coin in top_coins]
                )

            if irc:
                notice_message(message, irc, target)
            else:
                log(message, "MSG")

        # Show top eka and vika winners
        elif text.startswith("!ekavika"):
            try:
                with open(EKAVIKA_FILE, "r", encoding="utf-8") as f:
                    ekavika_data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                log("Ei vielä yhtään eka- tai vika-voittoja tallennettuna.", "INFO")
                notice_message(
                    "Ei vielä yhtään eka- tai vika-voittoja tallennettuna.", irc, target
                )
                return

            # Find top winners
            top_eka = max(
                ekavika_data["eka"], key=ekavika_data["eka"].get, default=None
            )
            top_vika = max(
                ekavika_data["vika"], key=ekavika_data["vika"].get, default=None
            )

            eka_count = ekavika_data["eka"].get(top_eka, 0) if top_eka else 0
            vika_count = ekavika_data["vika"].get(top_vika, 0) if top_vika else 0

            # Generate response message
            if top_eka and top_vika:
                response = f"📢 Eniten 𝖊𝖐𝖆-voittoja: {top_eka} ({eka_count} kertaa), eniten 𝙫𝙞𝙠𝙖-voittoja: {top_vika} ({vika_count} kertaa)"
                notice_message(response, irc, target)
            else:
                response = "Ei vielä tarpeeksi dataa eka- ja vika-voittajista."
                notice_message(response, irc, target)

        # !s - Kerro sää
        elif text.startswith("!s"):
            parts = text.split(" ", 1)
            location = parts[1].strip() if len(parts) > 1 else "Joensuu"
            if is_private:
                send_weather(irc, sender, location)
            else:
                send_weather(irc, target, location)

        # Handle !leetwinners command
        elif text.strip() == "!leetwinners":
            leet_winners = load_leet_winners()

            # Dictionary to store only one winner per category
            filtered_winners = {}

            for winner, categories in leet_winners.items():
                for cat, count in categories.items():
                    # Ensure only one winner per category
                    if cat not in filtered_winners or count > filtered_winners[cat][1]:
                        filtered_winners[cat] = (winner, count)

            # Format the output
            winners_text = ", ".join(
                f"{cat}: {winner} [{count}]"
                for cat, (winner, count) in filtered_winners.items()
            )

            response = (
                f"𝓛𝓮𝓮𝓽𝔀𝓲𝓷𝓷𝓮𝓻𝓼: {winners_text}"
                if winners_text
                else "No 𝓛𝓮𝓮𝓽𝔀𝓲𝓷𝓷𝓮𝓻𝓼 recorded yet."
            )
            send_message(irc, target, response)
            log(f"Sent leet winners: {response}")

        # !leet - Ajasta viestin lähetys
        elif text.startswith("!leet"):
            match = re.search(
                r"!leet (#\S+) (\d{1,2}):(\d{1,2}):(\d{1,2})\.(\d+) (.+)", text
            )

            if match:
                channel = match.group(1)
                hour = int(match.group(2))
                minute = int(match.group(3))
                second = int(match.group(4))
                microsecond = int(match.group(5))
                message = match.group(6)  # Capture the custom message

                send_scheduled_message(
                    irc, channel, message, hour, minute, second, microsecond
                )
            else:
                log(
                    "Virheellinen komento! Käytä muotoa: !leet #kanava HH:MM:SS.mmmmmm",
                    "ERROR",
                )

        # !link - Lyhennä linkki
        elif text.startswith("!link"):
            match = re.search(r"!link\s+(\S+)", text)
            if match:
                url = match.group(1)
                log("!link", "DEBUG")

        elif text.startswith("!eurojackpot"):
            result = get_eurojackpot_numbers()

            if isinstance(result, tuple):
                latest, frequent = result
                message = (
                    f"Latest Eurojackpot: {', '.join(map(str, latest))} | "
                    f"Most Frequent Numbers: {', '.join(map(str, frequent))}"
                )
            else:
                log(f"Error with !link: {result}", "ERROR")
                message = result  # Error message

            notice_message(message, irc, target)

        elif text.startswith("!youtube"):
            match = re.search(r"!youtube\s+(.+)", text)
            if match:
                url = match.group(1)
                result = search_youtube(url)
                if result and result != "No results found.":
                    notice_message(result, irc, target)

        elif text.startswith("!join"):
            match = re.search(r"!join\s+(.+)", text)
            # Extracts the channel and key from the given text after the !join command.
            parts = text.split()
            channel = ""
            key = ""
            if len(parts) >= 2 and parts[0] == "!join":
                channel = parts[1]
            elif len(parts) == 3 and parts[0] == "!join":
                channel = parts[1]
                key = parts[2]
            if match:
                notice_message(f"JOIN {channel} {key}", irc)

        elif text.startswith("!opzor"):
            # Extracts the nick from the given text after the !opzor command.
            parts = message.split()
            if len(parts) == 5 and parts[3] == ":!opzor":
                viesti = f"MODE {parts[2]} +o {parts[4]}"
                notice_message(f"MODE {parts[2]} +o {parts[4]}", irc)

        else:
            # ✅ Handle regular chat messages (send to GPT)
            # ✅ Only respond to private messages or messages mentioning the bot's name
            if is_private or bot_name.lower() in text.lower():
                # Get response from GPT
                response_parts = chat_with_gpt(text)
                reply_target = (
                    sender if is_private else target
                )  # Send private replies to sender

                # Send each response part separately as full messages
                for part in response_parts:
                    send_message(irc, reply_target, part)
                log(f"\U0001f4ac Sent response to {reply_target}: {response_parts}")

    # Keep track of leet winners
    if re.search(
        r"Ensimmäinen leettaaja oli (\S+) .*?, viimeinen oli (\S+) .*?Lähimpänä multileettiä oli (\S+)",
        message,
    ):
        leet_match = re.search(
            r"Ensimmäinen leettaaja oli (\S+) .*?, viimeinen oli (\S+) .*?Lähimpänä multileettiä oli (\S+)",
            message,
        )
        first, last, multileet = leet_match.groups()
        leet_winners = load_leet_winners()

        for category, winner in zip(
            ["ensimmäinen", "viimeinen", "multileet"], [first, last, multileet]
        ):
            if winner in leet_winners:
                leet_winners[winner][category] = (
                    leet_winners[winner].get(category, 0) + 1
                )
            else:
                leet_winners[winner] = {category: 1}

        save_leet_winners(leet_winners)
        log(f"Updated leet winners: {leet_winners}")

    # Keep track of ekavika winners
    if re.search(r"𝙫𝙞𝙠𝙖 oli (\w+) kello .*?, ja 𝖊𝖐𝖆 oli (\w+)", message):
        match = re.search(r"𝙫𝙞𝙠𝙖 oli (\w+) kello .*?, ja 𝖊𝖐𝖆 oli (\w+)", message)
        if match:
            # Load existing data or initialize a new dictionary
            try:
                with open(EKAVIKA_FILE, "r", encoding="utf-8") as f:
                    ekavika_data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                log("Ekavika file not found or corrupt, creating a new file.", "INFO")
                ekavika_data = {
                    "eka": {},
                    "vika": {},
                }  # Initialize if file doesn't exist or is empty

            vika = match.group(1)
            eka = match.group(2)
            log(f"Vika: {vika}, Eka: {eka}")

            # Update win counts
            ekavika_data["eka"][eka] = ekavika_data["eka"].get(eka, 0) + 1
            ekavika_data["vika"][vika] = ekavika_data["vika"].get(vika, 0) + 1

            # Save updated data
            with open(EKAVIKA_FILE, "w", encoding="utf-8") as f:
                json.dump(ekavika_data, f, indent=4, ensure_ascii=False)
        else:
            log("No match found for eka and vika winners.", "DEBUG")


def get_crypto_price(coin="bitcoin", currency="eur"):
    """
    Fetches the latest cryptocurrency price from CoinGecko.
    """
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies={currency}"
    response = requests.get(url).json()
    return response.get(coin, {}).get(currency, "Price not available")


def countdown(irc, target, stop_event):
    sent_messages = {"12:37": False, "13:36": False}

    while not stop_event.is_set():
        now = datetime.now()
        current_time = now.strftime("%H:%M")

        if current_time in sent_messages and not sent_messages[current_time]:
            if stop_event.is_set():
                break

            message = (
                "⏳ 1 tunti aikaa leettiin!"
                if current_time == "12:37"
                else "⚡ 1 minuutti aikaa leettiin! Brace yourselves!"
            )

            try:
                notice_message(message, irc, target)
                sent_messages[current_time] = True  # Merkitään viesti lähetetyksi
                log(f"Sent countdown message for {current_time}", "INFO")
            except Exception as e:
                log(f"Error sending countdown message: {e}", "ERROR")

            # Sleep in smaller intervals to check for stop_event
            for _ in range(82440):  # 22.9 hours total
                if stop_event.is_set():
                    break
                time.sleep(1)  # Check every second

            if stop_event.is_set():
                break

        time.sleep(1)  # Tarkistetaan aika joka sekunti


EUROJACKPOT_URL = "https://www.euro-jackpot.net/fi/tilastot/numerotaajuus"


def get_eurojackpot_numbers():
    url = "https://www.euro-jackpot.net/fi/tilastot/numerotaajuus"
    response = requests.get(url)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    table_rows = soup.select(
        "table tr"
    )  # Adjust the selector based on actual table structure

    latest_numbers = []
    most_frequent_numbers = []

    draw_data = []  # Store tuples of (Arvontaa sitten, Number)

    for row in table_rows:
        columns = row.find_all("td")
        if len(columns) >= 3:
            draw_order = columns[2].text.strip()  # "Arvontaa sitten"
            number = columns[1].text.strip()  # The number itself

            if draw_order.isdigit():
                draw_data.append((int(draw_order), int(number)))

    # Sort by "Arvontaa sitten" to get the latest draw (smallest value should be 0)
    draw_data.sort()

    # Extract numbers with "Arvontaa sitten" = 0 (latest draw)
    latest_numbers = [num for order, num in draw_data if order == 0]

    # Extract most frequent numbers (sort by frequency, needs correct column parsing)
    frequency_data = []

    for row in table_rows:
        columns = row.find_all("td")
        if len(columns) >= 3:
            number = columns[1].text.strip()
            frequency = columns[2].text.strip()

            if number.isdigit() and frequency.isdigit():
                frequency_data.append((int(frequency), int(number)))

    # Sort by frequency in descending order to get most frequent numbers
    frequency_data.sort(reverse=True, key=lambda x: x[0])
    most_frequent_numbers = [num for freq, num in frequency_data[:7]]  # Top 7 numbers

    return latest_numbers, most_frequent_numbers


def send_message(irc, reply_target, message):
    encoded_message = message.encode("utf-8")
    log(f"Sending message ({len(encoded_message)} bytes): {message}", "DEBUG")
    irc.sendall(f"PRIVMSG {reply_target} :{message}\r\n".encode("utf-8"))
    time.sleep(0.5)  # Prevent flooding


def measure_latency(irc, nickname):
    """Sends a latency test message to self and starts the timer."""
    global latency_start
    latency_start = time.time()  # Store timestamp
    test_message = "!LatencyCheck"
    irc.sendall(f"PRIVMSG {nickname} :{test_message}\r\n".encode("utf-8"))
    log(f"Sent latency check message: {test_message}")


def send_scheduled_message(
    irc,
    channel,
    message,
    target_hour=13,
    target_minute=37,
    target_second=13,
    target_nanosecond=371337133,
):
    def wait_and_send():
        now = datetime.now()
        target_time = now.replace(
            hour=target_hour,
            minute=target_minute % 60,
            second=target_second,
            microsecond=min(target_nanosecond // 1000, 999999),
        )

        if now >= target_time:
            target_time += timedelta(days=1)

        # Convert to nanoseconds for precise timing
        target_ns = time.perf_counter_ns() + int(
            (target_time - now).total_seconds() * 1e9
        )
        log(
            f"[Scheduled] time_to_wait: {(target_ns - time.perf_counter_ns()) / 1e9:.9f} s"
        )

        # 🕒 **Nanosecond-level wait**
        while time.perf_counter_ns() < target_ns - 2_000_000:  # Wait until last ~2ms
            time.sleep(0.0005)  # Sleep in small increments

        # 🎯 **Final busy wait for nanosecond accuracy**
        while time.perf_counter_ns() < target_ns:
            pass  # Active wait loop

        # 📨 **Send message**
        send_message(irc, channel, message)

        # 📝 **Log accurate timestamps**
        scheduled_time_str = f"{target_hour:02}:{target_minute:02}:{target_second:02}.{target_nanosecond:09}"
        actual_time_str = datetime.now().strftime("%H:%M:%S.%f")[
            :-3
        ]  # Microsecond-level logging

        log(f"Viesti ajastettu kanavalle {channel} klo {scheduled_time_str}")
        log(f"Viesti lähetetty: {message} @ {actual_time_str}")

    # Run in a separate thread to avoid blocking execution
    threading.Thread(target=wait_and_send, daemon=True).start()


def send_weather(irc=None, target=None, location="Joensuu"):
    location = location.strip().title()  # Ensimmäinen kirjain isolla
    encoded_location = urllib.parse.quote(location)  # Muutetaan sijainti URL-muotoon
    weather_url = f"http://api.openweathermap.org/data/2.5/weather?q={encoded_location}&appid={WEATHER_API_KEY}&units=metric&lang=fi"

    try:
        weather_response = requests.get(weather_url)  # Lähetetään pyyntö
        if weather_response.status_code == 200:  # Onnistunut vastaus
            data = weather_response.json()  # Data JSON-muotoon
            description = data["weather"][0]["description"].capitalize()  # Kuvaus
            temp = data["main"]["temp"]  # Lämpötila °C
            feels_like = data["main"]["feels_like"]  # Tuntuu kuin °C
            humidity = data["main"]["humidity"]  # Kosteus %
            wind_speed = data["wind"]["speed"]  # Tuuli m/s
            visibility = (
                data.get("visibility", 0) / 1000
            )  # Näkyvyys, muutetaan metreistä kilometreiksi
            pressure = data["main"]["pressure"]  # Ilmanpaine hPa
            clouds = data["clouds"]["all"]  # Pilvisyys prosentteina
            country = data["sys"].get(
                "country", "?"
            )  # Get country code, default to "?"

            # Tarkistetaan, onko sateen tai lumen tietoja
            rain = data.get("rain", {}).get(
                "1h", 0
            )  # Sade viimeisen tunnin aikana (mm)
            snow = data.get("snow", {}).get(
                "1h", 0
            )  # Lumi viimeisen tunnin aikana (mm)

            # Auringonnousu ja -lasku aikaleimoista
            sunrise = datetime.fromtimestamp(data["sys"]["sunrise"]).strftime("%H:%M")
            sunset = datetime.fromtimestamp(data["sys"]["sunset"]).strftime("%H:%M")

            # Lasketaan ilmanpaineen ero ja muodostetaan visuaalinen esitys
            pressure_diff = (
                pressure - 1013.25
            )  # Oletetaan, että normaali ilmanpaine on 1013.25 hPa
            pressure_percent = (pressure_diff / 1000) * 100  # Muutetaan prosentteina

            if pressure_diff == 0:
                pressure_visual = "〇"  # Ei muutosta
            elif abs(pressure_percent) > 4:
                pressure_visual = "☠"  # Suuri muutos
            else:
                if abs(pressure_percent) <= 1:
                    pressure_visual = "🟢"
                elif abs(pressure_percent) <= 2:
                    pressure_visual = "🟡"
                elif abs(pressure_percent) <= 3:
                    pressure_visual = "🟠"
                else:
                    pressure_visual = "🔴"

                # Lisätään suuntanuoli lopuksi
                # pressure_visual += "⬆️" if pressure_diff > 0 else "⬇️"

            lat = data["coord"]["lat"]
            lon = data["coord"]["lon"]
            uv_url = f"http://api.openweathermap.org/data/2.5/uvi?lat={lat}&lon={lon}&appid={WEATHER_API_KEY}"
            uv_index = None

            try:
                uv_response = requests.get(uv_url)
                if uv_response.status_code == 200:
                    uv_data = uv_response.json()
                    uv_index = uv_data.get("value", None)
            except Exception as e:
                log(f"UV-indeksin haku epäonnistui: {str(e)}", "ERROR")

            wind_deg = data["wind"].get("deg", 0)
            directions = [
                ("⬆️"),
                ("↗️"),
                ("➡️"),
                ("↘️"),
                ("⬇️"),
                ("↙️"),
                ("⬅️"),
                ("↖️"),
            ]
            idx = round(wind_deg % 360 / 45) % 8
            wind_dir_emoji = directions[idx]

            # Arvotaan symboli alkuun
            random_symbol = random.choice(["🌈", "🔮", "🍺", "☀️", "❄️", "🌊", "🔥"])

            # Muodostetaan säätilasymboli
            weather_icons = {
                "Clear": "☀️",
                "Clouds": "☁️",
                "Rain": "🌧️",
                "Drizzle": "🌦️",
                "Thunderstorm": "⛈️",
                "Snow": "❄️",
                "Mist": "🌫️",
                "Smoke": "🌫️",
                "Haze": "🌫️",
                "Dust": "🌪️",
                "Fog": "🌁",
                "Sand": "🌪️",
                "Ash": "🌋",
                "Squall": "💨",
                "Tornado": "🌪️",
            }
            main_weather = data["weather"][0]["main"]  # Esim. "Rain", "Clear"
            weather_emoji = weather_icons.get(main_weather, "🌈")  # Oletuksena 🌈

            # Rakennetaan viesti 🌡️
            weather_info = (
                f"{random_symbol}{location},{country}:{weather_emoji} {description}, {temp}°C ({feels_like}🌡️°C), "
                f"💦{humidity}%, 🍃{wind_speed}{wind_dir_emoji}m/s, 👁 {visibility:.1f} km, "
                f"⚖️ {pressure} hPa{pressure_visual}, ☁️{clouds}%, "
                f"🌄{sunrise}-{sunset}🌅"
            )

            # Lisää UV-indeksi ja sade/lumi tiedot
            if uv_index is not None:
                weather_info += f", 🔆(UV): {uv_index:.1f}"
            if rain > 0:
                weather_info += f", Sade: {rain} mm/tunti."
            if snow > 0:
                weather_info += f", Lumi: {snow} mm/tunti."
            if rain == 0 and snow == 0:
                weather_info += "."

            log(f"Weather: {weather_info}", "DEBUG")
            notice_message(weather_info, irc, target)  # Send weather information

        else:
            weather_info = (
                f"Sään haku epäonnistui. (Virhekoodi {weather_response.status_code})"
            )
            log(weather_info, "ERROR")

    except Exception as e:
        weather_info = f"Sään haku epäonnistui: {str(e)}"
        log(weather_info, "ERROR")


def send_electricity_price(irc=None, target=None, text=None):
    log(f"Syöte: {text}", "DEBUG")  # Tulostetaan koko syöte
    log(f"Syötteen pituus: {len(text)}", "DEBUG")  # Tulostetaan syötteen pituus

    # Käydään läpi kaikki text-listan osat
    for i, part in enumerate(text):
        log(f"text[{i}] = {part}", "DEBUG")  # Tulostetaan jokainen osa

    # Oletuksena haetaan nykyinen päivä ja tunti
    date = datetime.now()
    hour = date.hour

    # Tarkistetaan käyttäjän syöte
    if len(text) == 1:  # Käyttäjä ei antanut tuntia
        log(f"Haettu tunti tänään: {hour}", "DEBUG")
    elif len(text) == 2:  # Käyttäjä antoi tunnin tai "huomenna" ja tunnin
        parts = text[1].strip().split()
        log(f"parts[0] = {parts[0]}")  # Lisätty debug-tulostus
        if (
            parts[0].lower() == "huomenna" and len(parts) == 2
        ):  # Käyttäjä antoi "huomenna" ja tunnin
            hour = int(parts[1])  # Käyttäjän syöttämä tunti huomenna
            date += timedelta(days=1)  # Lisätään yksi päivä nykyhetkeen
            log(f"Haettu tunti huomenna: {hour}", "DEBUG")
        elif len(parts) == 1 and parts[0].isdigit():  # Käyttäjä antoi vain tunnin
            hour = int(parts[0])
            log(f"Haettu tunti tänään: {hour}", "DEBUG")
        else:
            error_message = "Virheellinen komento! Käytä: !sahko [huomenna] <tunti>"
            log(error_message, "ERROR")
            notice_message(error_message, irc, target)
            return
    else:
        error_message = "Virheellinen komento! Käytä: !sahko [huomenna] <tunti>"
        log(error_message)
        notice_message(error_message, irc, target)
        return

    # Muodostetaan API-pyyntö oikealle päivälle
    date_str = date.strftime("%Y%m%d")
    date_plus_one = date + timedelta(days=1)  # Huomisen päivämäärä
    # Convert the updated date to string in the format "YYYYMMDD"
    date_tomorrow = date_plus_one.strftime("%Y%m%d")

    # Tulostetaan nykyinen ja huominen päivä konsoliin
    log(f"Tänään: {date_str}", "DEBUG")
    log(f"Huominen: {date_tomorrow}", "DEBUG")

    # Haetaan sähkön hinnat tänään
    electricity_url_today = f"https://web-api.tp.entsoe.eu/api?securityToken={ELECTRICITY_API_KEY}&documentType=A44&in_Domain=10YFI-1--------U&out_Domain=10YFI-1--------U&periodStart={date_str}0000&periodEnd={date_str}2300"

    # Haetaan sähkön hinnat huomenna
    electricity_url_tomorrow = f"https://web-api.tp.entsoe.eu/api?securityToken={ELECTRICITY_API_KEY}&documentType=A44&in_Domain=10YFI-1--------U&out_Domain=10YFI-1--------U&periodStart={date_tomorrow}0000&periodEnd={date_tomorrow}2300"

    def fetch_prices(url):
        try:
            electricity_response = requests.get(url)
            xml_data = ElementTree.parse(StringIO(electricity_response.text))

            # Haetaan kaikki hintapisteet
            ns = {"ns": "urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3"}
            prices = {
                int(point.find("ns:position", ns).text): float(
                    point.find("ns:price.amount", ns).text
                )
                for point in xml_data.findall(".//ns:Point", ns)
            }
            return prices
        except Exception as e:
            log(f"Virhe sähkön hintojen haussa: {e}", "ERROR")
            return {}

    # Hae tänään ja huomenna hinnat
    prices_today = fetch_prices(electricity_url_today)
    prices_tomorrow = fetch_prices(electricity_url_tomorrow)

    # Tulostetaan kaikki haetut hintatiedot tänään
    log(f"\nSähkön hinnat tänään {date.strftime('%Y-%m-%d')} (ALV 25,5%):", "DEBUG")
    for pos, price in sorted(prices_today.items()):
        price_snt_per_kwh = (price / 10) * 1.255  # Muutetaan sentteihin ja lisätään ALV
        log(f"  Tunti {pos-1}: {price_snt_per_kwh:.2f} snt/kWh", "DEBUG")

    # Tulostetaan kaikki haetut hintatiedot huomenna
    log(
        f"\nSähkön hinnat huomenna {date_plus_one.strftime('%Y-%m-%d')} (ALV 25,5%):",
        "DEBUG",
    )
    for pos, price in sorted(prices_tomorrow.items()):
        price_snt_per_kwh = (price / 10) * 1.255  # Muutetaan sentteihin ja lisätään ALV
        log(f"  Tunti {pos-1}: {price_snt_per_kwh:.2f} snt/kWh", "DEBUG")

    # Muunnetaan haettava tunti vastaamaan XML:n tuntien numerointia (1-24)
    hour_position = hour

    # Haetaan hinta tänään
    if hour_position in prices_today:
        price_eur_per_mwh_today = prices_today[hour_position]  # €/MWh
        price_snt_per_kwh_today = (
            price_eur_per_mwh_today / 10
        ) * 1.255  # Muutetaan sentteihin ja lisätään ALV 25,5%
        electricity_info_today = (
            f"Tänään klo {hour}: {price_snt_per_kwh_today:.2f} snt/kWh (ALV 25,5%)"
        )
    else:
        electricity_info_today = (
            f"Sähkön hintatietoa ei saatavilla tunnille {hour} tänään."
        )

    # Haetaan hinta huomenna
    if hour_position in prices_tomorrow:
        price_eur_per_mwh_tomorrow = prices_tomorrow[hour_position]  # €/MWh
        price_snt_per_kwh_tomorrow = (
            price_eur_per_mwh_tomorrow / 10
        ) * 1.255  # Muutetaan sentteihin ja lisätään ALV 25,5%
        electricity_info_tomorrow = (
            f"Huomenna klo {hour}: {price_snt_per_kwh_tomorrow:.2f} snt/kWh (ALV 25,5%)"
        )
    else:
        electricity_info_tomorrow = f"Sähkön hintatietoa ei saatavilla tunnille {hour} huomenna. https://liukuri.fi/"

    # Tulostetaan haettu tuntihinta tänään ja huomenna
    log(f"\n{electricity_info_today}", "DEBUG")
    log(f"\n{electricity_info_tomorrow}", "DEBUG")

    # Lähetetään viesti IRC-kanavalle
    notice_message(
        electricity_info_today + ", " + electricity_info_tomorrow, irc, target
    )


def fetch_title(irc=None, target=None, text=""):
    # log(f"Syöte: {text}", "DEBUG")  # Logataan koko syöte
    global last_title  # Viimeisin haettu otsikko
    pattern = r"(https?:\/\/[^\s]+|www\.[^\s]+|[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.[a-zA-Z]{2,}(?:\/[^\s]*)?)"  # Regex URLien etsimiseen
    urls = re.findall(pattern, text)

    if not urls:
        # log("Ei löydetty kelvollisia URL-osoitteita.", "DEBUG")
        return

    log(f"Löydetyt URL-osoitteet: {urls}", "DEBUG")  # Logataan löydetyt URL-osoitteet

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
    }

    banned_urls = ["irc.cc.tut.fi", "irc.swepipe.net", "irc.spadhausen.com"]
    banned_titles = [
        "YouTube",
        "- YouTube",
        "403 Forbidden",
        "404 Not Found",
        "(ei otsikkoa)",
        "Bevor Sie zu YouTube weitergehen",
        "Bevor Sie zu Google Maps weitergehen",
    ]

    for url in urls:
        if any(banned_url in url for banned_url in banned_urls):
            log(f"Skipping banned URL: {url}", "DEBUG")
            continue

        if not url.startswith(
            ("http://", "https://")
        ):  # Lisätään HTTPS, jos URL ei ala sillä
            url = "https://" + url
            log(f"Korjattu URL: {url}", "DEBUG")  # Debug: korjattu URL

        if "youtube.com" in url or "youtu.be" in url:
            video_id = None

            # Kokeillaan ensin shorts-linkkiä
            shorts_match = re.search(r"youtube\.com/shorts/([a-zA-Z0-9_-]{11})", url)
            if shorts_match:
                video_id = shorts_match.group(1)
                log(f"Detected YouTube Shorts URL. Video ID: {video_id}", "DEBUG")

            # Kokeillaan normaalia youtube.com/watch?v=... tai /embed/... ym.
            if not video_id:
                standard_match = re.search(
                    r"(?:v=|\/embed\/|\/watch\/|\/)([a-zA-Z0-9_-]{11})(?:\W|$)", url
                )
                if standard_match:
                    video_id = standard_match.group(1)
                    log(f"Detected standard YouTube URL. Video ID: {video_id}", "DEBUG")

            # Kokeillaan youtu.be-lyhytlinkkiä
            if not video_id:
                short_match = re.search(r"youtu\.be/([a-zA-Z0-9_-]{11})", url)
                if short_match:
                    video_id = short_match.group(1)
                    log(f"Detected youtu.be short link. Video ID: {video_id}", "DEBUG")

            # Käytetään ID:tä, jos löytyi — muuten haetaan tekstillä koko url
            query = video_id if video_id else url
            if not query:
                log(
                    f"Could not extract video ID or use URL as query from: {url}",
                    "ERROR",
                )
                notice_message("Error: Could not parse YouTube link.", irc, target)
                continue

            result = search_youtube(query)
            if result and result != "No results found.":
                notice_message(result, irc, target)
            else:
                notice_message("No video found for given link or query.", irc, target)
            continue

        if url.lower().endswith((".iso", ".mp3")):
            log(".iso tai .mp3 found, skipping!")
            continue

        try:
            log(f"Käsitellään URL: {url}", "DEBUG")  # Debug-tulostus

            if url.lower().endswith(".pdf"):  # Käsitellään PDF-URL erikseen
                title = get_pdf_title(url) or "(ei otsikkoa)"
                log(f"PDF-otsikko: {title}")
            else:
                response = requests.get(url, headers=headers, timeout=5)
                response.raise_for_status()  # Tarkistetaan, ettei tullut HTTP-virhettä

                if (
                    not response.encoding or response.encoding.lower() == "iso-8859-1"
                ):  # Varmistetaan oikea merkistökoodaus
                    response.encoding = response.apparent_encoding

                try:
                    soup = BeautifulSoup(response.text, "html.parser")
                except Exception as e:
                    log(f"Error while parsing HTML: {e}", "ERROR")
                    continue

                title = None
                if soup and soup.title and soup.title.string:
                    try:
                        title = soup.title.string.strip()
                    except Exception as e:
                        log(f"Error while extracting title: {e}", "ERROR")

                if not title:  # Jos title puuttuu, haetaan meta description
                    meta_desc = soup.find(
                        "meta", attrs={"name": "description"}
                    ) or soup.find("meta", attrs={"property": "og:description"})
                    title = (
                        meta_desc["content"].strip()
                        if meta_desc and "content" in meta_desc.attrs
                        else "(ei otsikkoa)"
                    )

            if irc and title and title not in banned_titles:
                log(f"Haettu otsikko: {title}", "DEBUG")  # Debug: tulostetaan otsikko
                log(
                    f"Declared encoding: {response.encoding}", "DEBUG"
                )  # Debug: tulostetaan merkistökoodaus
                log(
                    f"Apparent encoding: {response.apparent_encoding}", "DEBUG"
                )  # Debug: tulostetaan oletettu merkistökoodaus

                while "  " in title:
                    title = title.replace("  ", " ")  # Remove double spaces
                title = title.replace("Ã¤", "ä").replace("Ã¶", "ö").replace("â@S", "-")

                if title == last_title:
                    log("Skipping duplicate title", "DEBUG")
                    continue
                last_title = title
                notice_message(f"'{title}'", irc, target)
            else:
                log(f"Sivun otsikko: {title}", "INFO")

        except requests.RequestException as e:
            log(f"Virhe URL:n {url} haussa: {e}")


def get_pdf_title(url):
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()  # Raise an error for HTTP issues

        buffer = b""
        for chunk in response.iter_content(256):  # Read in chunks
            buffer += chunk
            if b"</title>" in buffer:  # Stop early if title is found
                break

        text = buffer.decode(errors="ignore")
        match = re.search(r"<title>(.*?)</title>", text, re.IGNORECASE)

        return match.group(1) if match else None

    except requests.RequestException as e:
        log(f"Error fetching PDF: {e}", "ERROR")
        return None


def split_message_intelligently(message, limit):
    """
    Splits a message into parts without cutting words, ensuring correct byte-size limits.

    Args:
        message (str): The full message to split.
        limit (int): Max length per message.

    Returns:
        list: List of message parts that fit within the limit.
    """
    words = message.split(" ")
    parts = []
    current_part = ""

    for word in words:
        # Calculate encoded byte size
        encoded_size = (
            len((current_part + " " + word).encode("utf-8"))
            if current_part
            else len(word.encode("utf-8"))
        )

        if encoded_size > limit:
            if current_part:  # Store the current part before starting a new one
                parts.append(current_part)
            current_part = word  # Start new part with the long word
        else:
            current_part += (" " + word) if current_part else word

    if current_part:
        parts.append(current_part)

    log(f"Final split messages: {parts}", "DEBUG")  # Log split messages
    return parts


def chat_with_gpt(user_input):
    """
    Simulates a chat with GPT and updates the conversation history.

    Args:
        user_input (str): The user's input message.

    Returns:
        list: List of the assistant's response parts.
    """
    IRC_MESSAGE_LIMIT = (
        435  # Message limit, might not be enough considering UTF-8 encoding
    )
    conversation_history = load_conversation_history()  # Load conversation history
    conversation_history.append(
        {"role": "user", "content": user_input}
    )  # Append user's message

    # Get response from gpt-4o or gpt-4o-mini
    response = client.chat.completions.create(  # Use the new syntax
        model="gpt-4o-mini",  # Specify the model
        messages=conversation_history,  # Provide the conversation history as the prompt
        max_tokens=350,  # Adjust the token count as needed
    )

    # Correct way to access the response
    assistant_reply = response.choices[0].message.content.strip()

    # Append assistant's response
    conversation_history.append({"role": "assistant", "content": assistant_reply})

    # Muutetaan rivinvaihdot yhdeksi välilyönniksi, jotta viesti ei katkea
    assistant_reply = assistant_reply.replace("\n", " ")

    # Save updated conversation history
    save_conversation_history(conversation_history)

    # Split the message intelligently
    response_parts = split_message_intelligently(assistant_reply, IRC_MESSAGE_LIMIT)
    response_parts = [
        part.replace("  ", " ") for part in response_parts
    ]  # Remove double spaces
    return response_parts


def notice_message(message, irc=None, target=None):
    """
    Utility function that handles output to both IRC and console.

    Args:
        message (str): The message to output
        irc (socket, optional): IRC socket object. If None, outputs to console
        target (str, optional): IRC nick/channel to send to.
    """
    if irc and target:  # Send message to IRC target
        irc.sendall(f"NOTICE {target} :{message}\r\n".encode("utf-8"))
        log(f"Message sent to {target}: {message}", "MSG")
    else:
        log(message, "MSG")  # Output to console


def log(message, level="INFO"):
    """Tulostaa viestin konsoliin aikaleiman ja tason kanssa.

    Args:
        message (str): Tulostettava viesti.
        level (str, optional): Viestin taso (ERROR, CMD, MSG, SERVER, INFO, DEBUG). Oletus: INFO.

    Käyttöesimerkkejä
        log("Ohjelma käynnistyy...") # Oletus INFO, sama kuin:
        log("Ohjelma käynnistyy!", "INFO")
        log("Virhe tapahtui!", "ERROR")
        log("Komento", "CMD")
        log("Viesti kanavalle", "MSG")
        log("Palvelinviesti", "SERVER")
        log("Debug-viesti", "DEBUG")
    """
    levels = ["ERROR", "CMD", "MSG", "SERVER", "INFO", "DEBUG"]
    if levels.index(level) <= levels.index(LOG_LEVEL):
        timestamp = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.{time.time_ns() % 1_000_000_000:09d}"  # Nanosekunnit
        print(f"[{timestamp}] [{level:^6}] {message}")


def euribor(irc, target):
    # XML data URL from Suomen Pankki
    url = "https://reports.suomenpankki.fi/WebForms/ReportViewerPage.aspx?report=/tilastot/markkina-_ja_hallinnolliset_korot/euribor_korot_today_xml_en&output=xml"

    # Fetch the XML data
    response = requests.get(url)
    if response.status_code == 200:
        # Parse the XML content
        root = ElementTree.fromstring(response.content)

        # Namespace handling (because the XML uses a default namespace)
        ns = {
            "ns": "euribor_korot_today_xml_en"
        }  # Update with correct namespace if needed

        # Find the correct period (yesterday's date)
        period = root.find(".//ns:period", namespaces=ns)
        if period is not None:
            rates = period.findall(".//ns:rate", namespaces=ns)

            for rate in rates:
                if rate.attrib.get("name") == "12 month (act/360)":
                    euribor_12m = rate.find("./ns:intr", namespaces=ns)
                    if euribor_12m is not None:
                        log(
                            f"Yesterday's 12-month Euribor rate: {euribor_12m.attrib['value']}%",
                            "DEBUG",
                        )
                        notice_message(
                            f"Yesterday's 12-month Euribor rate: {euribor_12m.attrib['value']}%",
                            irc,
                            target,
                        )
                    else:
                        log("Interest rate value not found.", "ERROR")
                    break
            else:
                log("12-month Euribor rate not found.", "ERROR")
        else:
            log("No period data found in XML.", "ERROR")
    else:
        log(
            f"Failed to retrieve XML data. HTTP Status Code: {response.status_code}",
            "ERROR",
        )


def parse_server_config(prefix):
    host = os.getenv(f"{prefix}_HOST")
    port = os.getenv(f"{prefix}_PORT")
    channels_raw = os.getenv(f"{prefix}_CHANNELS", "")
    keys_raw = os.getenv(f"{prefix}_KEYS", "")

    if not host or not port:
        return None  # skip if missing core data

    channels = [ch.strip() for ch in channels_raw.split(",") if ch.strip()]
    keys = [k.strip() for k in keys_raw.split(",") if k.strip()]

    # Pad keys list to match length of channels
    while len(keys) < len(channels):
        keys.append("")

    return {"host": host, "port": int(port), "channels": list(zip(channels, keys))}


def main():
    log("Bot starting...", "DEBUG")  # Centralized startup message
    global LOG_LEVEL
    global bot_name
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="IRC Bot with API key handling")
    parser.add_argument(  # -api näyttää API-avaimet
        "-api", action="store_true", help="Show API key values in logs"
    )
    parser.add_argument(  # -l tai --loglevel *ERROR*, *INFO* tai *DEBUG* määrittää lokitason
        "-l",
        "--loglevel",
        choices=["ERROR", "INFO", "DEBUG"],
        default="DEBUG",  # Oletus: DEBUG
        help="Set the logging level (default: INFO)",
    )
    parser.add_argument("-nick", "--nickname", type=str, default=bot_name)
    args = parser.parse_args()

    LOG_LEVEL = args.loglevel  # Set the log level based on command line argument
    bot_name = args.nickname  # Set the bot nickname based on command line argument

    channels_raw = os.getenv("CHANNELS", "")
    channels = []

    for ch in channels_raw.split(","):
        if ":" in ch:
            name, key = ch.split(":", 1)
            channels.append((name.strip(), key.strip()))

    # List of possible server prefixes
    server_prefixes = ["SERVER1", "SERVER2"]

    servers = []
    for prefix in server_prefixes:
        server = parse_server_config(prefix)
        if server:
            servers.append(server)

    log(servers, "DEBUG")  # Log the server configurations
    port = servers[0]["port"]
    server = servers[0]["host"]
    channels = servers[0]["channels"]

    stop_event = threading.Event()
    irc = None
    threads = []

    # Setup signal handler for graceful shutdown
    def signal_handler(sig, frame):
        stop_event.set()
        raise KeyboardInterrupt

    # Register SIGINT handler
    signal.signal(signal.SIGINT, signal_handler)

    try:
        while not stop_event.is_set():
            try:
                load()
                irc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                irc.connect((server, port))
                irc.settimeout(
                    5
                )  # Set a timeout for socket operations, ctrl+c will not hang longer than this
                writer = irc
                login(
                    irc, writer, bot_name, channels, show_api_keys=args.api
                )  # Login to IRC

                # Start Keepalive PING
                keepalive_thread = threading.Thread(
                    target=keepalive_ping, args=(irc, stop_event), daemon=True
                )
                keepalive_thread.start()
                threads.append(keepalive_thread)

                # Start input listener in a separate thread
                input_thread = threading.Thread(
                    target=listen_for_commands, args=(stop_event,), daemon=True
                )
                input_thread.start()
                threads.append(input_thread)

                # Start leet countdown timer
                countdown_thread = threading.Thread(
                    target=countdown, args=(irc, "#joensuu", stop_event), daemon=True
                )
                countdown_thread.start()
                threads.append(countdown_thread)  # Add to threads list for cleanup

                # Main read loop - this will block until disconnect or interrupt
                read(irc, stop_event)

            except (socket.error, ConnectionError) as e:
                log(f"Server error: {e}, retrying after 5 seconds...", "ERROR")
                # Wait before reconnecting
                time.sleep(5)

            except KeyboardInterrupt:
                log("KeyboardInterrupt received. Shutting down...", "INFO")
                break

    finally:
        try:
            log("Shutting down, saving data...", "INFO")
            kraks = load()
            save(kraks)
            if irc:
                try:
                    writer.sendall(f"QUIT :{QUIT_MESSAGE}\r\n".encode("utf-8"))
                    writer.shutdown(socket.SHUT_WR)  # Half-close write side
                    time.sleep(1)  # Give time for the server to receive the QUIT
                    stop_event.set()
                    for thread in threads:
                        if thread.is_alive():
                            thread.join(timeout=1.0)
                            if thread.is_alive():
                                log(
                                    f"Thread {thread.name} did not terminate cleanly.",
                                    "ERROR",
                                )
                    log("Cleanup complete. Shutting down IRC connection...", "DEBUG")
                    irc.shutdown(socket.SHUT_RDWR)
                    irc.close()
                except Exception as e:
                    log(f"Error during shutdown: {e}", "ERROR")
            log("Bot exited gracefully. Goodbye!", "INFO")
            sys.exit(0)
        except Exception as e:
            log(f"Error saving data: {e}", "ERROR")


if __name__ == "__main__":
    main()
