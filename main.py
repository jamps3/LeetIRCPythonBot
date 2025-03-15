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
import sys
import platform # For checking where are we running for correct datetime formatting
import socket
import os
import time
import threading
import re # Regular expression
import requests
import pickle # Tiedostojen tallennukseen
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from io import StringIO
import xml.etree.ElementTree as ElementTree
import openai
import xml.dom.minidom
import urllib.parse  # Lisätään URL-koodausta varten
from dotenv import load_dotenv # Load api-keys from .env file
from collections import Counter
import json
import argparse # Command line argument parsing

# File to store conversation history
HISTORY_FILE = "conversation_history.json"

# All drink words to track
DRINK_WORDS = {"krak": 0, "kr1k": 0, "kr0k": 0, "narsk": 0, "parsk": 0, "tlup": 0, "marsk": 0, "tsup": 0, "plop": 0}

# Default history with system prompt
DEFAULT_HISTORY = [
    {"role": "system", "content": "You are a helpful assistant who knows about Finnish beer culture. You respond in a friendly, conversational manner. If you don't know something, just say so. Keep responses brief."}
]

# Aseta API-avaimet
load_dotenv()  # Lataa .env-tiedoston muuttujat
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
ELECTRICITY_API_KEY = os.getenv("ELECTRICITY_API_KEY")
api_key = os.getenv("OPENAI_API_KEY")

if sys.gettrace():
    bot_name = "jL3b2"
    channels = [("#joensuutest", "")]
else:
    bot_name = "jL3b"
    channels = [
        ("#53", os.getenv("CHANNEL_KEY_53", "")),
        ("#joensuu", ""),
        ("#west", "")
    ]
QUIT_MESSAGE = "Nähdään!"

last_ping = time.time()
# Luo OpenAI-asiakasolio (uusi tapa OpenAI 1.0.0+ versiossa)
client = openai.OpenAI(api_key=api_key)

data_file = "kraks_data.pkl"

# Sanakirja, joka pitää kirjaa voitoista
voitot = {
    "ensimmäinen": {},
    "viimeinen": {},
    "multileet": {}
}

# Create a stop event to handle clean shutdown
stop_event = threading.Event()

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
        return {}  # Return an empty dictionary if the file does not exist or is corrupted

def save_leet_winners(leet_winners):
    """Saves the leet winners to a JSON file."""
    with open("leet_winners.json", "w", encoding="utf-8") as f:
        json.dump(leet_winners, f, indent=4, ensure_ascii=False)

def save(kraks, file_path=data_file):
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

def load(file_path=data_file):
    """Loads kraks (IRC nick word stats) from a file using pickle, with error handling."""
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

RECONNECT_DELAY = 60  # Time in seconds before retrying connection

def login(irc, writer, channels, show_api_keys=False):
    """
    Logs into the IRC server, waits for the MOTD to finish, and joins multiple channels.
    Implements automatic reconnection in case of disconnection.

    Args:
        irc: The IRC connection object (socket).
        writer: The socket writer used to send messages.
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
                log("API keys loaded (use -api flag to show values)", "DEBUG")

            writer.sendall(f"NICK {nick}\r\n".encode("utf-8"))
            writer.sendall(f"USER {login} 0 * :{nick}\r\n".encode("utf-8"))

            last_response_time = time.time()  # Track last received message time
            while True:
                response = irc.recv(2048).decode("utf-8", errors="ignore")
                if response:
                    last_response_time = time.time()  # Reset timeout on any message

                for line in response.split("\r\n"):
                    if line:
                        log(f"SERVER: {line}", "DEBUG")

                    # If server says "Please wait while we process your connection", don't disconnect yet
                    if " 020 " in line:
                        log("Server is still processing connection, continuing to wait...", "DEBUG")
                        last_response_time = time.time()  # Reset timeout so it doesn't assume failure
                        continue  # Keep waiting instead of assuming failure

                    # If welcome (001) or MOTD completion (376/422) received, join channels
                    if " 001 " in line or " 376 " in line or " 422 " in line:
                        log("MOTD complete, joining channels...", "INFO")

                        for channel, key in channels:
                            if key:
                                writer.sendall(f"JOIN {channel} {key}\r\n".encode("utf-8"))
                                log(f"Joined channel {channel} with key", "INFO")
                            else:
                                writer.sendall(f"JOIN {channel}\r\n".encode("utf-8"))
                                log(f"Joined channel {channel} (no key)", "INFO")

                        return  # Successfully joined, exit function

                # Timeout handling: If no response received in 30 seconds, assume failure
                if time.time() - last_response_time > 30:
                    raise socket.timeout("No response from server for 30 seconds")

        except (socket.error, ConnectionResetError, BrokenPipeError, socket.timeout) as e:
            log(f"Connection lost: {e}. Reconnecting in {RECONNECT_DELAY} seconds...", "ERROR")
            time.sleep(RECONNECT_DELAY)

        except Exception as e:
            log(f"Unexpected error: {e}. Reconnecting in {RECONNECT_DELAY} seconds...", "ERROR")
            time.sleep(RECONNECT_DELAY)

# Main loop to read messages from IRC
def read(irc, server, port, stop_event, reconnect_delay=5):
    global last_ping, latency_start
    
    try:
        while not stop_event.is_set():  # Check if shutdown is requested
            try:
                response = irc.recv(4096).decode("utf-8", errors="ignore")
                if not response:
                    continue  # If no response, keep listening
            except socket.timeout:
                continue  # Socket timeout occurred, just continue the loop

            for line in response.strip().split("\r\n"):  # Handle multiple messages
                log(line.strip(), "SERVER")
                
                if line.startswith("PING"):  # Handle PING more efficiently
                    last_ping = time.time()
                    ping_value = line.split(":", 1)[1].strip()
                    irc.sendall(f"PONG :{ping_value}\r\n".encode("utf-8"))
                    log(f"Sent PONG response to {ping_value}")
                
                process_message(irc, line)  # Process each message separately
    
    except KeyboardInterrupt:
        stop_event.set()  # Notify all threads to stop without logging
    
    finally:
        try:
            irc.shutdown(socket.SHUT_RDWR)
            irc.close()
        except Exception as e:
            log(f"Error while closing IRC connection: {e}", "ERROR")

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
                log(f"Processing command {command} with args: {args}", "INFO")
                
                # Handle commands similar to IRC commands
                if command == "!s" or command == "!sää":
                    location = args.strip() if args else "Joensuu"
                    log(f"Getting weather for {location} from console", "INFO")
                    send_weather(None, None, location)  # Pass None for IRC and channel
                
                elif command == "!sahko" or command == "!sähkö":
                    send_electricity_price(None, None, command_parts)
                
                elif command == "!aika":
                    output_message(f"Nykyinen aika: {datetime.now().isoformat(timespec='microseconds') + '000'}")
                
                elif command == "!kaiku":
                    output_message(f"Console: {args}")
                
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
                            results = ", ".join(f"{nick}: {count}" for nick, count in word_counts.items())
                            output_message(f"Sana '{search_word}' on sanottu: {results}")
                        else:
                            output_message(f"Kukaan ei ole sanonut sanaa '{search_word}' vielä.")
                    else:
                        output_message("Käytä komentoa: !sana <sana>")
                
                elif command == "!topwords":
                    kraks = load()
                    
                    if args:  # Specific nick provided
                        nick = args.strip()
                        if nick in kraks:
                            top_words = Counter(kraks[nick]).most_common(5)
                            word_list = ", ".join(f"{word}: {count}" for word, count in top_words)
                            output_message(f"{nick}: {word_list}")
                        else:
                            output_message(f"Käyttäjää '{nick}' ei löydy.")
                    else:  # Show top words for all users
                        overall_counts = Counter()
                        for words in kraks.values():
                            overall_counts.update(words)
                        
                        top_words = overall_counts.most_common(5)
                        word_list = ", ".join(f"{word}: {count}" for word, count in top_words)
                        output_message(f"Käytetyimmät sanat: {word_list}")
                
                elif command == "!leaderboard":
                    kraks = load()
                    user_word_counts = {nick: sum(words.values()) for nick, words in kraks.items()}
                    top_users = sorted(user_word_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                    
                    if top_users:
                        leaderboard_msg = ", ".join(f"{nick}: {count}" for nick, count in top_users)
                        output_message(f"Aktiivisimmat käyttäjät: {leaderboard_msg}")
                    else:
                        output_message("Ei vielä tarpeeksi dataa leaderboardille.")
                
                elif command == "!euribor":
                    # XML data URL from Suomen Pankki
                    url = "https://reports.suomenpankki.fi/WebForms/ReportViewerPage.aspx?report=/tilastot/markkina-_ja_hallinnolliset_korot/euribor_korot_today_xml_en&output=xml"
                    
                    # Fetch the XML data
                    response = requests.get(url)
                    
                    if response.status_code == 200:
                        # Parse the XML content
                        root = ElementTree.fromstring(response.content)
                        
                        # Namespace handling (because the XML uses a default namespace)
                        ns = {"ns": "euribor_korot_today_xml_en"}  # Update with correct namespace if needed
                        
                        # Find the correct period (yesterday's date)
                        period = root.find(".//ns:period", namespaces=ns)
                        if period is not None:
                            # Extract the date from the XML attribute
                            date_str = period.attrib.get("value")  # Muoto YYYY-MM-DD
                            date_obj = datetime.strptime(date_str, "%Y-%m-%d")  # Muunnetaan datetime-objektiksi
                            
                            # Käytetään oikeaa muotoilua riippuen käyttöjärjestelmästä
                            if platform.system() == "Windows":
                                formatted_date = date_obj.strftime("%#d.%#m.%y")  # Windows
                            else:
                                formatted_date = date_obj.strftime("%-d.%-m.%y")  # Linux & macOS
                            rates = period.findall(".//ns:rate", namespaces=ns)
                            
                            for rate in rates:
                                if rate.attrib.get("name") == "12 month (act/360)":
                                    euribor_12m = rate.find("./ns:intr", namespaces=ns)
                                    if euribor_12m is not None:
                                        output_message(f"{formatted_date} 12kk Euribor: {euribor_12m.attrib['value']}%")
                                    else:
                                        output_message("Interest rate value not found.")
                                    break
                            else:
                                output_message("12-month Euribor rate not found.")
                        else:
                            output_message("No period data found in XML.")
                    else:
                        output_message(f"Failed to retrieve XML data. HTTP Status Code: {response.status_code}")
                
                elif command == "!leetwinners":
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
                    
                    response = f"Leet winners: {winners_text}" if winners_text else "No leet winners recorded yet."
                    output_message(response)
                
                elif command.startswith("!url") or command == "!title":
                    # Handle URL title fetching
                    if args:
                        fetch_title(None, None, args)
                    else:
                        output_message("Käytä komentoa: !url <url>")
                
                else:
                    output_message(f"Command '{command}' not recognized or not implemented for console use")
            else:
                # Any text not starting with ! is sent to OpenAI
                log(f"Sending text to OpenAI: {user_input}", "INFO")
                response_parts = chat_with_gpt(user_input)
                for part in response_parts:
                    print(f"Bot: {part}")
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
        if stop_event.is_set():
            break
            
        if time.time() - last_ping > 120:
            irc.sendall("PING :keepalive\r\n".encode("utf-8"))
            log("Sent keepalive PING")
            last_ping = time.time()

def process_message(irc, message):
    """Processes incoming IRC messages and tracks word statistics."""
    global latency_start
    is_private = False
    match = re.search(r":(\S+)!(\S+) PRIVMSG (\S+) :(.+)", message)
    
    if match:
        sender, _, target, text = match.groups()

        # Process each message sent to the channel and detect drinking words.
        # Regex pattern to find words in the format "word (beverage)"
        match = re.search(r"(\w+)\s*\(\s*([\w\s]+)\s*\)", text)
        
        if match:
            word = match.group(1).lower() # First captured word (e.g., "krak"). Convert to lowercase for consistent matching
            beverage = match.group(2).lower() # Second captured word inside parentheses (e.g., "karhu")
            
            if word in DRINK_WORDS:  # Check if the first word is in the DRINKING_WORDS list
                count_kraks(word, beverage)  # Call the function with extracted values

        
        # Check if the message is a private message (not a channel)
        if target.lower() == bot_name.lower():  # Private message detected
            log(f"Private message from {sender}: {text}")
            # irc.sendall(f"PRIVMSG {sender} :Hello! You said: {text}\r\n".encode("utf-8"))
            is_private = target.lower() == bot_name.lower()  # Private message check
        
        else:  # Normal channel message
            log(f"Channel message in {target} from {sender}: {text}", "MSG")
            # Fetch titles of URLs
            fetch_title(irc, target, text)
        
        # ✅ Prevent bot from responding to itself
        if sender.lower() == bot_name.lower():
            log("🔄 Ignoring bot's own message to prevent loops.")

            # ❌ Ignore the bot's own latency response completely
            if text.startswith("Latency is ") and "ns" in text:
                return  # Stop processing immediately

            # Handle bot's own LatencyCheck response
            if "!LatencyCheck" in text:
                if 'latency_start' in globals():
                    elapsed_time = time.time() - latency_start
                    latency_ns = int(elapsed_time * 1_000_000_000)  # Convert to ns
                    
                    # ✅ Estimate one-way latency
                    half_latency_ns = latency_ns // 2  

                    log(f"✅ Recognized LatencyCheck response! Latency: {elapsed_time:.3f} s ({latency_ns} ns)")

                    # **Before sending, subtract half_latency_ns to improve accuracy**
                    corrected_latency_ns = latency_ns - half_latency_ns
                    irc.sendall(f"PRIVMSG {bot_name} :Latency is {corrected_latency_ns} ns\r\n".encode("utf-8"))

                else:
                    log("⚠️ Warning: Received LatencyCheck response, but no latency_start timestamp exists.")

            return  # Stop further processing

        # Track words only if it's not a bot command
        if not text.startswith(("!", "http")):
            words = re.findall(r"\b\w+\b", text.lower())  # Extract words, ignore case
            kraks = load()
            update_kraks(kraks, sender, words)
            save(kraks)  # Save updates immediately
        
        # !aika - Kerro nykyinen aika
        if text.startswith("!aika"):
            output_message(f"Nykyinen aika: {datetime.now()}", irc, target)
                
        # !kaiku - Kaiuta teksti
        elif text.startswith("!kaiku"):
            output_message(f"{sender}: {text[len(sender)+2:]}", irc, target)
            
        # !sahko - Kerro pörssisähkön hintatiedot tänään ja huomenna, jos saatavilla
        elif text.startswith("!sahko"):
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
                    results = ", ".join(f"{nick}: {count}" for nick, count in word_counts.items())
                    output_message(f"Sana '{search_word}' on sanottu: {results}", irc, target)
                else:
                    output_message(f"Kukaan ei ole sanonut sanaa '{search_word}' vielä.", irc, target)
            else:
                output_message("Käytä komentoa: !sana <sana>", irc, target)

        # !topwords - Käytetyimmät sanat
        elif text.startswith("!topwords"):
            parts = text.split(" ", 1)
            kraks = load()

            if len(parts) > 1:  # Specific nick provided
                nick = parts[1].strip()
                if nick in kraks:
                    top_words = Counter(kraks[nick]).most_common(5)
                    word_list = ", ".join(f"{word}: {count}" for word, count in top_words)
                    output_message(f"{nick}: {word_list}", irc, target)
                else:
                    output_message(f"Käyttäjää '{nick}' ei löydy.", irc, target)
            else:  # Show top words for all users
                overall_counts = Counter()
                for words in kraks.values():
                    overall_counts.update(words)

                top_words = overall_counts.most_common(5)
                word_list = ", ".join(f"{word}: {count}" for word, count in top_words)
                output_message(f"Käytetyimmät sanat: {word_list}", irc, target)
        
        # !leaderboard - Aktiivisimmat käyttäjät
        elif text.startswith("!leaderboard"):
            kraks = load()
            user_word_counts = {nick: sum(words.values()) for nick, words in kraks.items()}
            top_users = sorted(user_word_counts.items(), key=lambda x: x[1], reverse=True)[:5]

            if top_users:
                leaderboard_msg = ", ".join(f"{nick}: {count}" for nick, count in top_users)
                output_message(f"Aktiivisimmat käyttäjät: {leaderboard_msg}", irc, target)
            else:
                output_message("Ei vielä tarpeeksi dataa leaderboardille.", irc, target)
        
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

                    if count > 0 and (top_users[word] is None or count > kraks[top_users[word]].get(word, 0)):
                        top_users[word] = nick

            total_message = f"Krakit yhteensä: {total_kraks}"
            details = ", ".join(
                f"{word}: {count} [{top_users[word]}]" for word, count in word_counts.items() if count > 0
            )

            send_message(irc, target, f"{total_message}, {details}")
        
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
                ns = {"ns": "euribor_korot_today_xml_en"}  # Update with correct namespace if needed

                # Find the correct period (yesterday's date)
                period = root.find(".//ns:period", namespaces=ns)
                if period is not None:
                    # Extract the date from the XML attribute
                    date_str = period.attrib.get("value")  # Muoto YYYY-MM-DD
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d")  # Muunnetaan datetime-objektiksi
                    
                    # Käytetään oikeaa muotoilua riippuen käyttöjärjestelmästä
                    if platform.system() == "Windows":
                        formatted_date = date_obj.strftime("%#d.%#m.%y")  # Windows
                    else:
                        formatted_date = date_obj.strftime("%-d.%-m.%y")  # Linux & macOS
                    rates = period.findall(".//ns:rate", namespaces=ns)

                    for rate in rates:
                        if rate.attrib.get("name") == "12 month (act/360)":
                            euribor_12m = rate.find("./ns:intr", namespaces=ns)
                            if euribor_12m is not None:
                                print(f"{formatted_date} 12kk Euribor: {euribor_12m.attrib['value']}%")
                                send_message(irc, target, f"{formatted_date} 12kk Euribor: {euribor_12m.attrib['value']}%")
                            else:
                                print("Interest rate value not found.")
                            break
                    else:
                        print("12-month Euribor rate not found.")
                else:
                    print("No period data found in XML.")
            else:
                print(f"Failed to retrieve XML data. HTTP Status Code: {response.status_code}")

        # !latencycheck - Handle latency check response
        # User sent !latencycheck command
        elif text.startswith("!latencycheck"):
            log("Received !latencycheck command, measuring latency...")
            measure_latency(irc, bot_name)

        elif re.search(r"Ensimmäinen leettaaja oli (\w+) .*?, viimeinen oli (\w+) .*?Lähimpänä multileettiä oli (\w+)", text):
            # Handle leet winners
            leet_match = re.search(r"Ensimmäinen leettaaja oli (\w+) .*?, viimeinen oli (\w+) .*?Lähimpänä multileettiä oli (\w+)", text)
            first, last, multileet = leet_match.groups()
            leet_winners = load_leet_winners()
            
            for category, winner in zip(["ensimmäinen", "viimeinen", "multileet"], [first, last, multileet]):
                if winner in leet_winners:
                    leet_winners[winner][category] = leet_winners[winner].get(category, 0) + 1
                else:
                    leet_winners[winner] = {category: 1}
            
            save_leet_winners(leet_winners)
            log(f"Updated leet winners: {leet_winners}")
        
        # !s - Kerro sää
        elif text.startswith("!s"):
            parts = text.split(" ", 1)
            location = parts[1].strip() if len(parts) > 1 else "Joensuu"
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

            response = f"Leet winners: {winners_text}" if winners_text else "No leet winners recorded yet."
            send_message(irc, target, response)
            log(f"Sent leet winners: {response}")
        
        # !leet - Ajasta viestin lähetys
        elif text.startswith("!leet"):
            match = re.search(r"!leet (#\S+) (\d{1,2}):(\d{1,2}):(\d{1,2})\.(\d+) (.+)", text)

            if match:
                channel = match.group(1)
                hour = int(match.group(2))
                minute = int(match.group(3))
                second = int(match.group(4))
                microsecond = int(match.group(5))
                message = match.group(6)  # Capture the custom message

                send_scheduled_message(irc, channel, message, hour, minute, second, microsecond)
            else:
                log("Virheellinen komento! Käytä muotoa: !leet #kanava HH:MM:SS.mmmmmm", "ERROR")

        else:
            # ✅ Handle regular chat messages (send to GPT)
            # ✅ Only respond to private messages or messages mentioning the bot's name
            if is_private or bot_name.lower() in text.lower():
                # Get response from GPT
                response_parts = chat_with_gpt(text)
                reply_target = sender if is_private else target  # Send private replies to sender
                
                # Send each response part separately as full messages
                for part in response_parts:
                    send_message(irc, reply_target, part)
                log(f"\U0001F4AC Sent response to {reply_target}: {response_parts}")

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

def send_scheduled_message(irc, channel, message, target_hour=13, target_minute=37, target_second=13, target_nanosecond=371337133):
    def wait_and_send():
        now = datetime.now()
        target_time = now.replace(hour=target_hour, minute=target_minute % 60, second=target_second, microsecond=min(target_nanosecond // 1000, 999999))

        if now >= target_time:
            target_time += timedelta(days=1)

        # Convert to nanoseconds for precise timing
        target_ns = time.perf_counter_ns() + int((target_time - now).total_seconds() * 1e9)
        log(f"[Scheduled] time_to_wait: {(target_ns - time.perf_counter_ns()) / 1e9:.9f} s")

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
        actual_time_str = datetime.now().strftime('%H:%M:%S.%f')[:-3]  # Microsecond-level logging

        log(f"Viesti ajastettu kanavalle {channel} klo {scheduled_time_str}")
        log(f"Viesti lähetetty: {message} @ {actual_time_str}")

    # Run in a separate thread to avoid blocking execution
    threading.Thread(target=wait_and_send, daemon=True).start()

def send_weather(irc=None, channel=None, location="Joensuu"):
    location = location.strip().title()  # Ensimmäinen kirjain isolla
    encoded_location = urllib.parse.quote(location)  # Muutetaan sijainti URL-muotoon
    weather_url = f"http://api.openweathermap.org/data/2.5/weather?q={encoded_location}&appid={WEATHER_API_KEY}&units=metric&lang=fi"

    try:
        weather_response = requests.get(weather_url) # Lähetetään pyyntö
        if weather_response.status_code == 200: # Onnistunut vastaus
            data = weather_response.json() # Data JSON-muotoon
            description = data["weather"][0]["description"].capitalize() # Kuvaus
            temp = data["main"]["temp"] # Lämpötila °C
            feels_like = data["main"]["feels_like"] # Tuntuu kuin °C
            humidity = data["main"]["humidity"] # Kosteus %
            wind_speed = data["wind"]["speed"] # Tuuli m/s
            visibility = data.get("visibility", 0) / 1000  # Näkyvyys, muutetaan metreistä kilometreiksi
            pressure = data["main"]["pressure"]  # Ilmanpaine hPa
            clouds = data["clouds"]["all"]  # Pilvisyys prosentteina
            country = data["sys"].get("country", "?")  # Get country code, default to "?"

            # Tarkistetaan, onko sateen tai lumen tietoja
            rain = data.get("rain", {}).get("1h", 0)  # Sade viimeisen tunnin aikana (mm)
            snow = data.get("snow", {}).get("1h", 0)  # Lumi viimeisen tunnin aikana (mm)

            # Auringonnousu ja -lasku aikaleimoista
            sunrise = datetime.fromtimestamp(data["sys"]["sunrise"]).strftime("%H:%M")
            sunset = datetime.fromtimestamp(data["sys"]["sunset"]).strftime("%H:%M")

            # Rakennetaan viesti
            weather_info = (f"{location}, {country} 🔮: {description}, {temp}°C ({feels_like} ~°C), "
                            f"💦 {humidity}%, 🍃 {wind_speed} m/s, 👁  {visibility:.1f} km, "
                            f"{pressure} hPa, pilvisyys {clouds}%. "
                            f"Aurinko {sunrise} - {sunset}.")

            if rain > 0:
                weather_info += f" Sade: {rain} mm/tunti."
            if snow > 0:
                weather_info += f" Lumi: {snow} mm/tunti."

        else:
            weather_info = f"Sään haku epäonnistui. (Virhekoodi {weather_response.status_code})"

    except Exception as e:
        weather_info = f"Sään haku epäonnistui: {str(e)}"

    output_message(weather_info, irc, channel)

def send_electricity_price(irc=None, channel=None, text=None):
    log(f"Syöte: {text}")  # Tulostetaan koko syöte
    log(f"Syötteen pituus: {len(text)}")  # Tulostetaan syötteen pituus

    # Käydään läpi kaikki text-listan osat
    for i, part in enumerate(text):
        log(f"text[{i}] = {part}")  # Tulostetaan jokainen osa

    # Oletuksena haetaan nykyinen päivä ja tunti
    date = datetime.now()
    hour = date.hour

    # Tarkistetaan käyttäjän syöte
    if len(text) == 1:  # Käyttäjä ei antanut tuntia
        log(f"Haettu tunti tänään: {hour}")
    elif len(text) == 2:  # Käyttäjä antoi tunnin tai "huomenna" ja tunnin
        parts = text[1].strip().split()
        log(f"parts[0] = {parts[0]}")  # Lisätty debug-tulostus
        if parts[0].lower() == "huomenna" and len(parts) == 2:  # Käyttäjä antoi "huomenna" ja tunnin
            hour = int(parts[1])  # Käyttäjän syöttämä tunti huomenna
            date += timedelta(days=1)  # Lisätään yksi päivä nykyhetkeen
            log(f"Haettu tunti huomenna: {hour}")
        elif len(parts) == 1 and parts[0].isdigit():  # Käyttäjä antoi vain tunnin
            hour = int(parts[0])
            log(f"Haettu tunti tänään: {hour}")
        else:
            error_message = "Virheellinen komento! Käytä: !sahko [huomenna] <tunti>"
            log(error_message)
            send_message(irc, channel, error_message)
            return
    else:
        error_message = "Virheellinen komento! Käytä: !sahko [huomenna] <tunti>"
        log(error_message)
        send_message(irc, channel, error_message)
        return

    # Muodostetaan API-pyyntö oikealle päivälle
    date_str = date.strftime("%Y%m%d")
    date_plus_one = date + timedelta(days=1)  # Huomisen päivämäärä
    # Convert the updated date to string in the format "YYYYMMDD"
    date_tomorrow = date_plus_one.strftime("%Y%m%d")

    # Tulostetaan nykyinen ja huominen päivä konsoliin
    log(f"Tänään: {date_str}")
    log(f"Huominen: {date_tomorrow}")

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
                int(point.find("ns:position", ns).text): 
                float(point.find("ns:price.amount", ns).text)
                for point in xml_data.findall(".//ns:Point", ns)
            }
            return prices
        except Exception as e:
            log(f"Virhe sähkön hintojen haussa: {e}")
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
    log(f"\nSähkön hinnat huomenna {date_plus_one.strftime('%Y-%m-%d')} (ALV 25,5%):", "DEBUG")
    for pos, price in sorted(prices_tomorrow.items()):
        price_snt_per_kwh = (price / 10) * 1.255  # Muutetaan sentteihin ja lisätään ALV
        log(f"  Tunti {pos-1}: {price_snt_per_kwh:.2f} snt/kWh", "DEBUG")

    # Muunnetaan haettava tunti vastaamaan XML:n tuntien numerointia (1-24)
    hour_position = hour

    # Haetaan hinta tänään
    if hour_position in prices_today:
        price_eur_per_mwh_today = prices_today[hour_position]  # €/MWh
        price_snt_per_kwh_today = (price_eur_per_mwh_today / 10) * 1.255  # Muutetaan sentteihin ja lisätään ALV 25,5%
        electricity_info_today = f"Tänään klo {hour}: {price_snt_per_kwh_today:.2f} snt/kWh (ALV 25,5%)"
    else:
        electricity_info_today = f"Sähkön hintatietoa ei saatavilla tunnille {hour} tänään."

    # Haetaan hinta huomenna
    if hour_position in prices_tomorrow:
        price_eur_per_mwh_tomorrow = prices_tomorrow[hour_position]  # €/MWh
        price_snt_per_kwh_tomorrow = (price_eur_per_mwh_tomorrow / 10) * 1.255  # Muutetaan sentteihin ja lisätään ALV 25,5%
        electricity_info_tomorrow = f"Huomenna klo {hour}: {price_snt_per_kwh_tomorrow:.2f} snt/kWh (ALV 25,5%)"
    else:
        electricity_info_tomorrow = f"Sähkön hintatietoa ei saatavilla tunnille {hour} huomenna."

    # Tulostetaan haettu tuntihinta tänään ja huomenna
    log(f"\n{electricity_info_today}", "DEBUG")
    log(f"\n{electricity_info_tomorrow}", "DEBUG")

    # Lähetetään viesti IRC-kanavalle
    output_message(electricity_info_today + ", " + electricity_info_tomorrow, irc, channel)
    # output_message(electricity_info_tomorrow, irc, channel)

import re
import requests
from bs4 import BeautifulSoup

def fetch_title(irc=None, channel=None, text=""):
    log(f"Syöte: {text}")  # Logataan koko syöte

    # Regex to find URLs
    pattern = r"(https?:\/\/[^\s]+|www\.[^\s]+|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,4}(?:\/[^\s]*)?)"
    urls = re.findall(pattern, text)

    log(f"Löydetyt URL-osoitteet: {urls}")  # Logataan löydetyt URL-osoitteet

    if not urls:
        log("Ei löydetty kelvollisia URL-osoitteita.")
        return

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"}

    for url in urls:
        try:
            log(f"Käsitellään URL: {url}")  # Debug-tulostus

            # Lisätään HTTPS, jos URL ei ala sillä
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
                log(f"Korjattu URL: {url}")  # Debug: tulostetaan korjattu URL
            
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()  # Tarkistetaan, ettei tullut HTTP-virhettä
            
            soup = BeautifulSoup(response.text, "html.parser")
            title = soup.title.string.strip() if soup.title else None

            # Jos title puuttuu, haetaan meta description
            if not title:
                meta_desc = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
                title = meta_desc["content"].strip() if meta_desc and "content" in meta_desc.attrs else "(ei otsikkoa)"
            
            log(f"Haettu otsikko: {title}")  # Debug: tulostetaan otsikko
            if irc:
                output_message(f"'{title}'", irc, channel)
            else:
                log(f"Otsikko: {title}")
        
        except requests.RequestException as e:
            log(f"Virhe URL:n {url} haussa: {e}")
            if irc:
                # output_message(f"Otsikon haku epäonnistui: {url}", irc, channel)
                log(f"Otsikon haku epäonnistui: {url}")
            else:
                log(f"Otsikon haku epäonnistui: {url}")

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
        encoded_size = len((current_part + " " + word).encode("utf-8")) if current_part else len(word.encode("utf-8"))

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
    IRC_MESSAGE_LIMIT = 435  # Message limit, might not be enough considering UTF-8 encoding
    conversation_history = load_conversation_history() # Load conversation history
    conversation_history.append({"role": "user", "content": user_input}) # Append user's message

    # Get response from gpt-4o or gpt-4o-mini
    response = client.chat.completions.create(  # Use the new syntax
        model="gpt-4o",  # Specify the model
        messages=conversation_history,  # Provide the conversation history as the prompt
        max_tokens=500  # Adjust the token count as needed
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
    
    return response_parts

def output_message(message, irc=None, channel=None):
    """
    Utility function that handles output to both IRC and console.
    
    Args:
        message (str): The message to output
        irc (socket, optional): IRC socket object. If None, prints to console
        channel (str, optional): IRC channel to send to. Required if irc is provided
    """
    if irc and channel:
        # Send to IRC
        irc.sendall(f"NOTICE {channel} :{message}\r\n".encode("utf-8"))
        log(f"Message sent to {channel}: {message}")
    else:
        # Print to console
        print(f"Bot: {message}")

def log(message, level="INFO"):
    """Tulostaa viestin konsoliin aikaleiman ja tason kanssa.

    Args:
        message (str): Tulostettava viesti.
        level (str, optional): Viestin taso (INFO, WARNING, ERROR, DEBUG). Oletus: INFO.
    
    Käyttöesimerkkejä
        log("Ohjelma käynnistyy...")
        log("Tämä on varoitus!", "WARNING")
        log("Virhe tapahtui!", "ERROR")
        log("Debug-viesti", "DEBUG")
    """
    #timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S.%f]")[:-3]  # Mikrosekunnit 3 desimaalilla
    timestamp = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.{time.time_ns() % 1_000_000_000:09d}]"  # Nanosekunnit
    print(f"{timestamp} [{level.upper()}] {message}")

def euribor(irc, channel):
    #import requests
    #import xml.etree.ElementTree as ET

    # XML data URL from Suomen Pankki
    url = "https://reports.suomenpankki.fi/WebForms/ReportViewerPage.aspx?report=/tilastot/markkina-_ja_hallinnolliset_korot/euribor_korot_today_xml_en&output=xml"

    # Fetch the XML data
    response = requests.get(url)
    if response.status_code == 200:
        # Parse the XML content
        root = ElementTree.fromstring(response.content)

        # Namespace handling (because the XML uses a default namespace)
        ns = {"ns": "euribor_korot_today_xml_en"}  # Update with correct namespace if needed

        # Find the correct period (yesterday's date)
        period = root.find(".//ns:period", namespaces=ns)
        if period is not None:
            rates = period.findall(".//ns:rate", namespaces=ns)

            for rate in rates:
                if rate.attrib.get("name") == "12 month (act/360)":
                    euribor_12m = rate.find("./ns:intr", namespaces=ns)
                    if euribor_12m is not None:
                        print(f"Yesterday's 12-month Euribor rate: {euribor_12m.attrib['value']}%")
                        send_message(irc, channel, f"Yesterday's 12-month Euribor rate: {euribor_12m.attrib['value']}%")
                    else:
                        print("Interest rate value not found.")
                    break
            else:
                print("12-month Euribor rate not found.")
        else:
            print("No period data found in XML.")
    else:
        print(f"Failed to retrieve XML data. HTTP Status Code: {response.status_code}")

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='IRC Bot with API key handling')
    parser.add_argument('-api', action='store_true', help='Show API key values in logs')
    args = parser.parse_args()
    
    # API visibility preference will be passed to login()
    
    server = "irc.atw-inter.net"
    port = 6667
    stop_event = threading.Event()
    irc = None
    threads = []
    
    # Setup signal handler for graceful shutdown
    def signal_handler(sig, frame):
        stop_event.set()
        raise KeyboardInterrupt
    
    # Register SIGINT handler
    import signal
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        while not stop_event.is_set():
            try:
                load()
                irc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                irc.connect((server, port))
                irc.settimeout(1.0)  # Add a timeout so Ctrl+C is handled promptly
                writer = irc
                login(irc, writer, channels, show_api_keys=args.api)
                
                # Start Keepalive PING
                keepalive_thread = threading.Thread(target=keepalive_ping, args=(irc, stop_event), daemon=True)
                keepalive_thread.start()
                threads.append(keepalive_thread)
                
                # Start input listener in a separate thread
                input_thread = threading.Thread(target=listen_for_commands, args=(stop_event,), daemon=True)
                input_thread.start()
                threads.append(input_thread)
                
                # Main read loop - this will block until disconnect or interrupt
                read(irc, server, port, stop_event, reconnect_delay=5)
                
            except (socket.error, ConnectionError) as e:
                log(f"Server error: {e}", "ERROR")
                # Wait before reconnecting
                time.sleep(5)
                
            except KeyboardInterrupt:
                break
    
    except KeyboardInterrupt:
        pass  # Shutdown message will be handled in finally block
    
    finally:
        # Clean shutdown procedures
        log("Shutting down...", "INFO")  # Centralized shutdown message
        stop_event.set()  # Signal all threads to terminate
        
        # Wait for threads to finish (with timeout)
        for thread in threads:
            if thread.is_alive():
                thread.join(timeout=1.0)
        
        # Save data and close socket
        try:
            kraks = load()  # Load kraks data before saving
            save(kraks)  # Pass the loaded kraks data to save()
            if irc:
                try:
                    writer.sendall(f"QUIT :{QUIT_MESSAGE}\r\n".encode("utf-8"))
                    time.sleep(1)  # Allow time for the message to send
                    irc.shutdown(socket.SHUT_RDWR)
                except:
                    pass
                irc.close()
            log("Bot exited gracefully. Goodbye!", "INFO")
        except Exception as e:
            log(f"Error during cleanup: {e}", "ERROR")

if __name__ == "__main__":
    main()
