"""
IRC Bot - Core Server Management Module

This module contains the core server management code for the IRC bot.
It handles server connections, thread management, and main program execution.

Architecture:
    - ServerManager class: Manages multiple server connections
    - Server class (from server.py): Handles individual server connections
    - message_handlers.py: Contains all message processing functionality
    - config.py: Loads server configurations from environment variables

Functions:
    - load(): Loads the state of 'kraks' from a binary file
    - save(): Saves the current state of 'kraks' to a binary file
    - countdown(): Sends countdown notifications for leet time
    - listen_for_commands(): Console command interface for interacting with servers
    - keepalive_ping(): Sends periodic PING messages to keep connections alive
    - main(): Main function to start the bot and manage server connections
"""
import sys
import os
import time
import threading
import pickle
import argparse
import signal
from datetime import datetime, timedelta
import json
from dotenv import load_dotenv

# Import the modules for the new architecture
from config import get_server_configs
from server import Server
import message_handlers

# File to store conversation history
HISTORY_FILE = "conversation_history.json"
# File to store ekavika winners
EKAVIKA_FILE = "ekavika.json"
# File to store words data
WORDS_FILE = "kraks_data.pkl"

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
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# Default bot name based on debugging state
BOT_NAME = "jL3b2" if sys.gettrace() else "jL3b"
QUIT_MESSAGE = "Nähdään!"

last_ping = time.time()
global last_title
last_title = ""

# Luo OpenAI-asiakasolio (uusi tapa OpenAI 1.0.0+ versiossa)
client = openai.OpenAI(api_key=api_key)

# No need for YouTube API client here - moved to message_handlers.py

# Sanakirja, joka pitää kirjaa voitoista
voitot = {
    "ensimmäinen": {},
    "viimeinen": {},
    "multileet": {}
}

# Create a stop event to handle clean shutdown
stop_event = threading.Event()

# YouTube search functionality moved to message_handlers.py

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

# Server manager class to handle multiple servers
class ServerManager:
    """
    Manages multiple IRC server connections.
    
    Handles server configuration, initialization, connection, and message processing.
    Each server runs in its own thread but shares common data structures.
    """
    def __init__(self, show_api_keys=False):
        """
        Initialize the ServerManager with server configurations from the config module.
        
        Args:
            show_api_keys (bool): Whether to display API keys in logs.
        """
        self.bot_name = BOT_NAME
        self.servers = []
        self.stop_event = threading.Event()
        self.show_api_keys = show_api_keys
        
        # Log API keys if requested
        if show_api_keys:
            log(f"Weather API Key: {WEATHER_API_KEY}", "DEBUG")
            log(f"Electricity API Key: {ELECTRICITY_API_KEY}", "DEBUG")
            log(f"OpenAI API Key: {api_key}", "DEBUG")
        else:
            log("API keys loaded (use -api flag to show values)", "DEBUG")
        
        # Load configurations from the config module
        self.server_configs = load_server_configs()
        log(f"Loaded {len(self.server_configs)} server configurations", "INFO")
    
    def initialize_servers(self):
        """Initialize server objects for each server configuration."""
        for server_config in self.server_configs:
            server = Server(
                server_config.host,
                server_config.port,
                self.bot_name,
                server_config.channels,
                self.stop_event
            )
            
            # Set up message handlers for this server
            self.setup_handlers(server)
            
            self.servers.append(server)
            log(f"Initialized server {server_config.host}", "INFO")
    
    def setup_handlers(self, server):
        """
        Set up message handlers for the server.
        
        Args:
            server (Server): The server object to set up handlers for.
        """
        # Register command handlers from message_handlers module
        server.register_handler("!s", message_handlers.handle_weather)
        server.register_handler("!sää", message_handlers.handle_weather)
        server.register_handler("!sahko", message_handlers.handle_electricity_price)
        server.register_handler("!sähkö", message_handlers.handle_electricity_price)
        server.register_handler("!aika", message_handlers.handle_time)
        server.register_handler("!kaiku", message_handlers.handle_echo)
        server.register_handler("!sana", message_handlers.handle_word_count)
        server.register_handler("!topwords", message_handlers.handle_top_words)
        server.register_handler("!leaderboard", message_handlers.handle_leaderboard)
        server.register_handler("!euribor", message_handlers.handle_euribor)
        server.register_handler("!leetwinners", message_handlers.handle_leet_winners)
        server.register_handler("!url", message_handlers.handle_url_title)
        server.register_handler("!title", message_handlers.handle_url_title)
        server.register_handler("!leet", message_handlers.handle_leet)
        server.register_handler("!youtube", message_handlers.handle_youtube_search)
        server.register_handler("!kraks", message_handlers.handle_kraks)
        server.register_handler("!ekavika", message_handlers.handle_ekavika)
        server.register_handler("!crypto", message_handlers.handle_crypto)
        server.register_handler("!eurojackpot", message_handlers.handle_eurojackpot)
        
        # Register special message handlers
        server.register_leet_message_handler(message_handlers.handle_leet_message)
        server.register_ekavika_message_handler(message_handlers.handle_ekavika_message)
        server.register_chat_handler(message_handlers.handle_chat_message)
        
        # Register URL handler for title fetching
        server.register_url_handler(message_handlers.handle_url_title)
        
        # Register word tracking
        server.register_word_handler(message_handlers.handle_tracking_words)
    
    def start_all(self):
        """Start all server connections in separate threads."""
        server_threads = []
        
        for server in self.servers:
            thread = threading.Thread(
                target=server.connect_and_run,
                name=f"Server-{server.host}",
                daemon=True
            )
            thread.start()
            server_threads.append(thread)
            log(f"Started server thread for {server.host}", "INFO")
        
        # Start additional functionality threads
        self.start_auxiliary_threads()
        
        # Wait for threads to finish or shutdown
        try:
            while not self.stop_event.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            log("Keyboard interrupt detected, shutting down...", "INFO")
            self.stop_event.set()
        
        # Wait for all threads to terminate
        for thread in server_threads:
            thread.join(timeout=5.0)
        
        log("All server threads stopped", "INFO")
    
    def start_auxiliary_threads(self):
        """Start auxiliary threads like command listener and countdown timer."""
        # Start input listener in a separate thread
        input_thread = threading.Thread(
            target=listen_for_commands,
            args=(self.stop_event,),
            name="CommandListener",
            daemon=True
        )
        input_thread.start()
        
        # Start leet countdown timer for each server's #joensuu channel if it exists
        for server in self.servers:
            for channel, _ in server.channels:
                if channel.lower() == "#joensuu":
                    threading.Thread(
                        target=countdown,
                        args=(server, channel, self.stop_event),
                        name=f"LeetCountdown-{server.host}-{channel}",
                        daemon=True
                    ).start()
                    log(f"Started countdown thread for {server.host}:{channel}", "INFO")
                    break

def listen_for_commands(stop_event, server_manager=None):
    """
    Listen for user input from the terminal and send to IRC servers or process locally.
    
    This function reads commands from the console and either:
    1. Executes them locally (like weather queries, time display, etc.)
    2. Sends them to specific or all connected IRC servers
    
    Args:
        stop_event (threading.Event): Event to signal when the bot should stop
        server_manager (ServerManager, optional): Reference to the server manager for sending commands to IRC servers
    """
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
                command_parts = user_input.split(" ", 2)  # Allow for server specification
                command = command_parts[0].lower()
                
                # Check if command targets a specific server
                target_server = None
                if len(command_parts) > 1 and command_parts[1].startswith("@"):
                    server_name = command_parts[1][1:]  # Remove @ prefix
                    args = command_parts[2] if len(command_parts) > 2 else ""
                    
                    # Find the specified server
                    if server_manager:
                        for server in server_manager.servers:
                            if server.host.lower() == server_name.lower():
                                target_server = server
                                break
                    
                    if not target_server:
                        log(f"Server '{server_name}' not found", "WARNING")
                        continue
                else:
                    # No specific server, regular command processing
                    args = command_parts[1] if len(command_parts) > 1 else ""
                
                log(f"Processing command {command} with args: {args}", "COMMAND")
                
                # Special command for sending a message to a specific channel on a server
                if command == "!send" and server_manager:
                    if len(command_parts) >= 2:
                        parts = args.split(" ", 1)
                        if len(parts) == 2:
                            channel = parts[0]
                            message = parts[1]
                            
                            # Send to specific server or all servers
                            if target_server:
                                target_server.send_message(channel, message)
                                log(f"Sent message to {target_server.host} {channel}: {message}", "INFO")
                            else:
                                for server in server_manager.servers:
                                    server.send_message(channel, message)
                                log(f"Sent message to all servers {channel}: {message}", "INFO")
                        else:
                            output_message("Usage: !send #channel message")
                    else:
                        output_message("Usage: !send #channel message")
                
                # Toggle debug mode for a server
                elif command == "!debug" and server_manager:
                    if target_server:
                        target_server.debug = not target_server.debug
                        log(f"Debug mode for {target_server.host} set to {target_server.debug}", "INFO")
                    else:
                        # Toggle debug for all servers
                        for server in server_manager.servers:
                            server.debug = not server.debug
                        log(f"Debug mode for all servers set to {server_manager.servers[0].debug}", "INFO")
                
                # List all connected servers
                elif command == "!servers" and server_manager:
                    server_list = "\n".join([
                        f"{i+1}. {s.host} - Connected: {s.is_connected} - Channels: {', '.join([c for c, _ in s.channels])}"
                        for i, s in enumerate(server_manager.servers)
                    ])
                    output_message(f"Connected servers:\n{server_list}")
                
                # Handle commands similar to IRC commands
                elif command == "!s" or command == "!sää":
                    location = args.strip() if args else "Joensuu"
                    log(f"Getting weather for {location} from console", "INFO")
                    
                    # Get weather and optionally send to server
                    result = message_handlers.get_weather_info(location)
                    output_message(result)
                    
                    # Send to server if specified
                    if target_server and server_manager:
                        for channel, _ in target_server.channels:
                            target_server.send_message(channel, result)
                
                elif command == "!sahko" or command == "!sähkö":
                    # Use the message handler to get electricity price
                    result = message_handlers.get_electricity_price(args)
                    output_message(result)
                    
                    # Send to server if specified
                    if target_server and server_manager:
                        for channel, _ in target_server.channels:
                            target_server.send_message(channel, result)
                
                elif command == "!aika":
                    result = f"Nykyinen aika: {datetime.now().isoformat(timespec='microseconds') + '000'}"
                    output_message(result)
                    
                    # Send to server if specified
                    if target_server and server_manager:
                        for channel, _ in target_server.channels:
                            target_server.send_message(channel, result)
    except (EOFError, KeyboardInterrupt):
        stop_event.set()

# Word tracking functionality moved to message_handlers.py

def keepalive_ping(irc, stop_event):
    global last_ping
    while not stop_event.is_set():
        time.sleep(2)  # Check more frequently for stop event
        if stop_event.is_set():
            break
            
        if time.time() - last_ping > 120:
            # Throws error when socket is lost, need to capture it
            irc.sendall("PING :keepalive\r\n".encode("utf-8"))
            # log("Sent keepalive PING", "DEBUG")
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
            log(f"Private message from {sender}: {text}", "MSG")
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
                message = " | ".join([f"{coin.capitalize()}: {prices[coin]} €" for coin in top_coins])
            
            if irc:
                output_message(message, irc, target)
            else:
                print(message)

        # Show top eka and vika winners
        elif text.startswith("!ekavika"):
            try:
                with open(EKAVIKA_FILE, "r", encoding="utf-8") as f:
                    ekavika_data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                output_message("Ei vielä yhtään eka- tai vika-voittoja tallennettuna.")
                return

            # Find top winners
            top_eka = max(ekavika_data["eka"], key=ekavika_data["eka"].get, default=None)
            top_vika = max(ekavika_data["vika"], key=ekavika_data["vika"].get, default=None)

            eka_count = ekavika_data["eka"].get(top_eka, 0) if top_eka else 0
            vika_count = ekavika_data["vika"].get(top_vika, 0) if top_vika else 0

            # Generate response message
            if top_eka and top_vika:
                response = f"📢 Eniten 𝖊𝖐𝖆-voittoja: {top_eka} ({eka_count} kertaa), eniten 𝙫𝙞𝙠𝙖-voittoja: {top_vika} ({vika_count} kertaa)"
                output_message(response)
                send_message(irc, target, response)
            else:
                response = "Ei vielä tarpeeksi dataa eka- ja vika-voittajista."
                output_message(response)
                send_message(irc, target, response)
                
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

            response = f"𝓛𝓮𝓮𝓽𝔀𝓲𝓷𝓷𝓮𝓻𝓼: {winners_text}" if winners_text else "No 𝓛𝓮𝓮𝓽𝔀𝓲𝓷𝓷𝓮𝓻𝓼 recorded yet."
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
                message = (f"Latest Eurojackpot: {', '.join(map(str, latest))} | "
                   f"Most Frequent Numbers: {', '.join(map(str, frequent))}")
            else:
                message = result  # Error message

            output_message(message, irc, target)
        
        # YouTube search functionality moved to message_handlers.py

        elif text.startswith("!join"):
            match = re.search(r"!join\s+(.+)", text)
            #Extracts the channel and key from the given text after the !join command.
            parts = text.split()
            channel = ""
            key = ""
            if len(parts) >= 2 and parts[0] == "!join":
                channel = parts[1]
            elif len(parts) == 3 and parts[0] == "!join":
                channel = parts[1]
                key = parts[2]
            if match:
                    output_message(f"JOIN {channel} {key}", irc)
        
        elif text.startswith("!opzor"):
            #Extracts the nick from the given text after the !opzor command.
            parts = message.split()
            if len(parts) == 5 and parts[3] == ":!opzor":
                viesti = f"MODE {parts[2]} +o {parts[4]}"
                output_message(f"MODE {parts[2]} +o {parts[4]}", irc)

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
    
    # Keep track of leet winners
    if re.search(r"Ensimmäinen leettaaja oli (\S+) .*?, viimeinen oli (\S+) .*?Lähimpänä multileettiä oli (\S+)", message):
        leet_match = re.search(r"Ensimmäinen leettaaja oli (\S+) .*?, viimeinen oli (\S+) .*?Lähimpänä multileettiä oli (\S+)", message)
        first, last, multileet = leet_match.groups()
        leet_winners = load_leet_winners()
        
        for category, winner in zip(["ensimmäinen", "viimeinen", "multileet"], [first, last, multileet]):
            if winner in leet_winners:
                leet_winners[winner][category] = leet_winners[winner].get(category, 0) + 1
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
                ekavika_data = {"eka": {}, "vika": {}}  # Initialize if file doesn't exist or is empty

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

def countdown(server, target, stop_event):
    """
    Sends countdown notifications for leet time (13:37) to a specified channel.
    
    Args:
        server (Server): The Server object to send messages through
        target (str): The channel to send messages to
        stop_event (threading.Event): Event to signal when the bot should stop
    """
    while not stop_event.is_set():
        now = datetime.now()
        current_time = now.strftime("%H:%M")

        if current_time == "12:37":
            message = "⏳ 1 tunti aikaa leettiin!"
            server.send_message(target, message)
            log(f"Sent 1-hour leet countdown to {server.host}:{target}", "INFO")

        elif current_time == "13:36":
            message = "⚡ 1 minuutti aikaa leettiin! Brace yourselves!"
            server.send_message(target, message)
            log(f"Sent 1-minute leet countdown to {server.host}:{target}", "INFO")

        # Sleep for a short time to check for stop event more frequently
        for _ in range(60):  # Still check once per minute, but in smaller increments
            if stop_event.is_set():
                return
            time.sleep(1)


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
                            f"P: {pressure} hPa, pilvisyys {clouds}%. "
                            f"🌄{sunrise} - {sunset}🌅.")

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
        if parts[0].lower() == "huomenna" and len(parts) == 2:  # Käyttäjä antoi "huomenna" ja tunnin
            hour = int(parts[1])  # Käyttäjän syöttämä tunti huomenna
            date += timedelta(days=1)  # Lisätään yksi päivä nykyhetkeen
            log(f"Haettu tunti huomenna: {hour}", "DEBUG")
        elif len(parts) == 1 and parts[0].isdigit():  # Käyttäjä antoi vain tunnin
            hour = int(parts[0])
            log(f"Haettu tunti tänään: {hour}", "DEBUG")
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
        electricity_info_tomorrow = f"Sähkön hintatietoa ei saatavilla tunnille {hour} huomenna. https://liukuri.fi/"

    # Tulostetaan haettu tuntihinta tänään ja huomenna
    log(f"\n{electricity_info_today}", "DEBUG")
    log(f"\n{electricity_info_tomorrow}", "DEBUG")

    # Lähetetään viesti IRC-kanavalle
    output_message(electricity_info_today + ", " + electricity_info_tomorrow, irc, channel)
    # output_message(electricity_info_tomorrow, irc, channel)

def fetch_title(irc=None, channel=None, text=""):
    # log(f"Syöte: {text}", "DEBUG")  # Logataan koko syöte
    global last_title
    # Regex to find URLs
    pattern = r"(https?:\/\/[^\s]+|www\.[^\s]+|[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.[a-zA-Z]{2,}(?:\/[^\s]*)?)"
    urls = re.findall(pattern, text)

    if urls:
        log(f"Löydetyt URL-osoitteet: {urls}", "DEBUG")  # Logataan löydetyt URL-osoitteet
    else:
        log("Ei löydetty kelvollisia URL-osoitteita.", "DEBUG")
        return

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"}

    for url in urls:
        banned_urls = ["irc.cc.tut.fi", "irc.swepipe.net", "irc.spadhausen.com"] # Don't fetch !ekavika server titles
        if any(banned_url in url for banned_url in banned_urls):
            log(f"Skipping banned URL: {url}", "DEBUG")
            continue
        try:
            log(f"Käsitellään URL: {url}", "DEBUG")  # Debug-tulostus

            # Lisätään HTTPS, jos URL ei ala sillä
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
                log(f"Korjattu URL: {url}", "DEBUG")  # Debug: tulostetaan korjattu URL
            
            # Käsitellään PDF-URL erikseen
            if url.lower().endswith(".pdf"):
                title = get_pdf_title(url)
                title = title if title else "(ei otsikkoa)"
                log(f"PDF-otsikko: {title}")  # Debug-tulostus
            else:
                response = requests.get(url, headers=headers, timeout=5)
                response.raise_for_status()  # Tarkistetaan, ettei tullut HTTP-virhettä
                
                try:
                    soup = BeautifulSoup(response.text, "html.parser")
                except Exception as e:
                    log(f"Error while parsing HTML: {e}", "ERROR")
                    continue
                
                title = soup.title.string.strip() if soup.title else None

                # Jos title puuttuu, haetaan meta description
                if not title:
                    meta_desc = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
                    title = meta_desc["content"].strip() if meta_desc and "content" in meta_desc.attrs else "(ei otsikkoa)"
                
                log(f"Haettu otsikko: {title}", "DEBUG")  # Debug: tulostetaan otsikko
                if irc:
                    banned_titles = ["- YouTube", "403 Forbidden", "404 Not Found", "(ei otsikkoa)", "Bevor Sie zu YouTube weitergehen"]
                    if title and title not in banned_titles:
                        while "  " in title:
                            title = title.replace("  ", " ") # Remove double spaces
                        title = title.replace("Ã¤", "ä") # Fix bad ä characters
                        title = title.replace("Ã¶", "ö") # Fix bad ö characters
                        title = title.replace("â@S", "-") # Fix bad - characters
                        if title == last_title:
                            log("Skipping duplicate title", "DEBUG")
                            continue
                        last_title = title
                        output_message(f"'{title}'", irc, channel)
                else:
                    log(f"Sivun otsikko: {title}")
        
        except requests.RequestException as e:
            log(f"Virhe URL:n {url} haussa: {e}")
            if irc:
                # output_message(f"Otsikon haku epäonnistui: {url}", irc, channel)
                log(f"Otsikon haku epäonnistui: {url}")
            else:
                log(f"Otsikon haku epäonnistui: {url}")

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
        print(f"Error fetching PDF: {e}")
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
        model="gpt-4o-mini",  # Specify the model
        messages=conversation_history,  # Provide the conversation history as the prompt
        max_tokens=350  # Adjust the token count as needed
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
    response_parts = [part.replace("  ", " ") for part in response_parts]  # Remove double spaces
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
    elif irc:
        # Send command to IRC
        irc.sendall(f"{message}\r\n".encode("utf-8"))
        log(f"Command '{message}' sent.")
    else:
        # Print to console
        print(f"OpenAI: {message}")

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
    if level == "DEBUG":
        if sys.gettrace():
            timestamp = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.{time.time_ns() % 1_000_000_000:09d}]"  # Nanosekunnit
            print(f"{timestamp} [{level.upper()}] {message}")
    else:
        timestamp = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.{time.time_ns() % 1_000_000_000:09d}]"  # Nanosekunnit
        print(f"{timestamp} [{level.upper()}] {message}")

def euribor(irc, channel):
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
    
    # Create a global stop event
    global stop_event
    stop_event = threading.Event()
    
    # Setup signal handlers for graceful shutdown
    def signal_handler(sig, frame):
        log(f"Received signal {sig}, initiating shutdown...", "INFO")
        stop_event.set()
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Initialize the server manager
        server_manager = ServerManager(show_api_keys=args.api)
        
        # Initialize and start all servers
        server_manager.initialize_servers()
        server_manager.start_all()
        
    except KeyboardInterrupt:
        log("Keyboard interrupt detected, shutting down...", "INFO")
    except Exception as e:
        log(f"Unexpected error: {e}", "ERROR")
    finally:
        # Ensure stop event is set to terminate all threads
        stop_event.set()
        
        # Save data before exiting
        try:
            kraks = load()  # Load kraks data before saving
            save(kraks)  # Pass the loaded kraks data to save()
            log("Data saved successfully", "INFO")
        except Exception as e:
            log(f"Error saving data during shutdown: {e}", "ERROR")
            
        log("Bot exited gracefully. Goodbye!", "INFO")

if __name__ == "__main__":
    main()
