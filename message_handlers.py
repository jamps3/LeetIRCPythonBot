"""
This module contains message handler callbacks for the IRC bot.
It includes handlers for different command types and state tracking.

Functions:
    - output_message: Utility function to send messages to IRC or console
    - send_message: Send a message to a specified IRC channel
    - process_message: Main message processing function
    - send_weather: Fetch and send weather information
    - send_electricity_price: Fetch and send electricity price information
    - fetch_title: Fetch and send webpage titles
    - count_kraks: Track occurrences of drink-related words
    - chat_with_gpt: Process chat messages with OpenAI
    - split_message_intelligently: Split messages to fit IRC message size limits
"""
import re
import time
import threading
import requests
import urllib.parse
import html
import json
import os
import platform
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from collections import Counter
import xml.etree.ElementTree as ElementTree
from io import StringIO
import openai
from dotenv import load_dotenv
from googleapiclient.discovery import build  # Youtube API

# Load environment variables
load_dotenv()
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
ELECTRICITY_API_KEY = os.getenv("ELECTRICITY_API_KEY")
api_key = os.getenv("OPENAI_API_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# Initialize OpenAI client
client = openai.OpenAI(api_key=api_key)

# Initialize YouTube API client
youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

# File paths for persistent data
HISTORY_FILE = "conversation_history.json"
EKAVIKA_FILE = "ekavika.json"
WORDS_FILE = "kraks_data.pkl"

# All drink words to track
DRINK_WORDS = {"krak": 0, "kr1k": 0, "kr0k": 0, "narsk": 0, "parsk": 0, "tlup": 0, "marsk": 0, "tsup": 0, "plop": 0}

# Default history with system prompt
DEFAULT_HISTORY = [
    {"role": "system", "content": "You are a helpful assistant who knows about Finnish beer culture. You respond in a friendly, conversational manner. If you don't know something, just say so. Keep responses brief."}
]

# Global variables
last_title = ""

def log(message, level="INFO"):
    """Prints a message to the console with a timestamp and level.

    Args:
        message (str): The message to print.
        level (str, optional): The message level (INFO, WARNING, ERROR, DEBUG). Default: INFO.
    
    Examples:
        log("Program starting...")
        log("This is a warning!", "WARNING")
        log("An error occurred!", "ERROR")
        log("Debug message", "DEBUG")
    """
    import sys
    if level == "DEBUG":
        if sys.gettrace():
            timestamp = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.{time.time_ns() % 1_000_000_000:09d}]"  # Nanoseconds
            print(f"{timestamp} [{level.upper()}] {message}")
    else:
        timestamp = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.{time.time_ns() % 1_000_000_000:09d}]"  # Nanoseconds
        print(f"{timestamp} [{level.upper()}] {message}")

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

def fetch_title(irc, channel, url):
    """
    Fetches and sends the title of a webpage when a URL is posted in the channel.
    
    This function handles various content types and encodings, with special handling
    for YouTube URLs to extract video titles.
    
    Args:
        irc (socket): IRC socket object
        channel (str): IRC channel to send the title to
        url (str): URL to fetch the title from
    """
    global last_title
    
    # Skip URLs that are unlikely to have meaningful titles
    if any(skip_url in url.lower() for skip_url in ['.jpg', '.jpeg', '.png', '.gif', '.mp4', '.webm']):
        log(f"Skipping image/video URL: {url}", "DEBUG")
        return
    
    try:
        log(f"Fetching title for URL: {url}", "DEBUG")
        
        # Special handling for YouTube URLs to get more information
        youtube_pattern = re.compile(r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com|youtu\.be)\/(?:watch\?v=)?([a-zA-Z0-9_-]{11})')
        youtube_match = youtube_pattern.search(url)
        
        if youtube_match:
            video_id = youtube_match.group(1)
            log(f"YouTube video detected, ID: {video_id}", "DEBUG")
            
            try:
                # Use YouTube API to get detailed information
                video_response = youtube.videos().list(
                    part="snippet,contentDetails,statistics",
                    id=video_id
                ).execute()
                
                if video_response.get("items"):
                    video = video_response["items"][0]
                    snippet = video["snippet"]
                    statistics = video["statistics"]
                    
                    title = snippet["title"]
                    channel_name = snippet["channelTitle"]
                    view_count = int(statistics.get("viewCount", 0))
                    like_count = int(statistics.get("likeCount", 0))
                    
                    # Format view count with commas
                    view_count_str = f"{view_count:,}".replace(",", " ")
                    like_count_str = f"{like_count:,}".replace(",", " ")
                    
                    # Create formatted message
                    youtube_info = f"YouTube: \"{title}\" by {channel_name} | Views: {view_count_str} | Likes: {like_count_str}"
                    
                    if youtube_info != last_title:
                        send_message(irc, channel, youtube_info)
                        last_title = youtube_info
                    return
            except Exception as e:
                log(f"Error fetching YouTube video info: {str(e)}", "WARNING")
                # Fall back to regular title extraction if YouTube API fails
        
        # Regular title extraction for all other URLs
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0'
        }
        
        # Use a timeout to prevent hanging
        response = requests.get(url, headers=headers, timeout=10, stream=True)
        
        # Check content type before downloading everything
        content_type = response.headers.get('Content-Type', '').lower()
        log(f"Content type: {content_type}", "DEBUG")
        
        # Skip binary files and large content
        if 'text/html' not in content_type and 'application/xhtml+xml' not in content_type:
            log(f"Skipping non-HTML content: {content_type}", "DEBUG")
            return
            
        # Limit content size to prevent memory issues (100 KB should be enough for most titles)
        content_bytes = b''
        for chunk in response.iter_content(chunk_size=4096):
            content_bytes += chunk
            if len(content_bytes) > 102400:  # 100 KB
                break
                
        # Try to determine the encoding
        encoding = response.encoding
        
        # If the encoding is None or ISO-8859-1 (often default), try to detect it
        if not encoding or encoding.lower() == 'iso-8859-1':
            # Check for charset in meta tags
            charset_match = re.search(br'<meta[^>]*charset=["\']?([\w-]+)', content_bytes, re.IGNORECASE)
            if charset_match:
                encoding = charset_match.group(1).decode('ascii', errors='ignore')
                log(f"Found encoding in meta tag: {encoding}", "DEBUG")
        
        # Default to UTF-8 if detection failed
        if not encoding or encoding.lower() == 'iso-8859-1':
            encoding = 'utf-8'
            
        # Decode content with the detected encoding
        try:
            content = content_bytes.decode(encoding, errors='replace')
        except (UnicodeDecodeError, LookupError):
            log(f"Decoding failed with {encoding}, falling back to utf-8", "WARNING")
            content = content_bytes.decode('utf-8', errors='replace')
            
        # Use BeautifulSoup to extract the title
        soup = BeautifulSoup(content, 'html.parser')
        title_tag = soup.find('title')
        
        if title_tag and title_tag.string:
            title = title_tag.string.strip()
            
            # Clean the title by removing excessive whitespace
            title = re.sub(r'\s+', ' ', title)
            
            # HTML unescape to handle entities like &amp;
            title = html.unescape(title)
            
            # Prepend "Title:" to distinguish from regular messages
            formatted_title = f"Title: {title}"
            
            # Only send if the title is different from the last one to avoid spam
            if formatted_title != last_title:
                send_message(irc, channel, formatted_title)
                last_title = formatted_title
                log(f"Sent title: {title}", "DEBUG")
        else:
            log(f"No title found for URL: {url}", "DEBUG")
            
    except requests.exceptions.Timeout:
        log(f"Timeout while fetching URL: {url}", "WARNING")
    except requests.exceptions.TooManyRedirects:
        log(f"Too many redirects for URL: {url}", "WARNING")
    except requests.exceptions.RequestException as e:
        log(f"Request error for URL {url}: {str(e)}", "WARNING")
    except Exception as e:
        log(f"Error fetching title for {url}: {str(e)}", "ERROR")
        # More detailed error logging for debugging
        import traceback
        log(traceback.format_exc(), "ERROR")

def send_message(irc, reply_target, message):
    """
    Sends a message to a specified IRC channel.
    
    Args:
        irc (socket): IRC socket object
        reply_target (str): Channel or user to send the message to
        message (str): The message content
    """
    encoded_message = message.encode("utf-8")
    log(f"Sending message ({len(encoded_message)} bytes): {message}", "DEBUG")
    irc.sendall(f"PRIVMSG {reply_target} :{message}\r\n".encode("utf-8"))
    time.sleep(0.5)  # Prevent flooding

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

def process_message(server, message, channel=None, sender=None):
    """
    Main message processing function that parses and handles incoming IRC messages.
    
    This function routes messages to the appropriate handler based on commands
    and tracks certain types of content (like drink-related words).
    
    Args:
        server: The IRC server instance
        message (str): The message to process
        channel (str, optional): The channel where the message was received
        sender (str, optional): The user who sent the message
    
    Returns:
        bool: True if the message was handled, False otherwise
    """
    try:
        log(f"Processing message from {sender}: {message}", "DEBUG")
        
        # Skip messages from the bot itself
        if sender and sender.lower() == server.nickname.lower():
            return False
            
        # Handle commands
        if message.startswith("!"):
            parts = message.split(maxsplit=1)
            command = parts[0].lower()
            args = parts[1].split() if len(parts) > 1 else []
            
            # YouTube search
            if command == "!youtube":
                handle_youtube_search(server, channel, message, sender, args)
                return True
                
            # Weather information
            elif command == "!weather":
                location = " ".join(args) if args else "Joensuu"
                threading.Thread(target=send_weather, 
                                args=(server.irc, channel, location),
                                daemon=True).start()
                return True
                
            # Electricity price
            elif command == "!sahko":
                threading.Thread(target=send_electricity_price, 
                                args=(server.irc, channel, parts),
                                daemon=True).start()
                return True
                
            # Eurojackpot numbers
            elif command == "!eurojackpot":
                handle_eurojackpot(server, channel, message, sender, args)
                return True
                
            # AI conversation with GPT
            elif command == "!gpt":
                if len(parts) > 1:
                    user_input = parts[1]
                    threading.Thread(target=lambda: [
                        send_message(server.irc, channel, part) 
                        for part in chat_with_gpt(user_input)
                    ], daemon=True).start()
                    return True
                else:
                    server.send_message(channel, "Usage: !gpt <message>")
                    return True
        
        # Track drink-related words
        message_lower = message.lower()
        for word, drink_mapping in {
            "krak": "Karhu", 
            "kr1k": "Karhu", 
            "kr0k": "Karhu",
            "narsk": "Karjala", 
            "parsk": "Olut", 
            "tlup": "Keppana",
            "marsk": "Mariska", 
            "tsup": "Olut", 
            "plop": "Pullo"
        }.items():
            if word in message_lower:
                count_kraks(word, drink_mapping)
                
        # URL title fetching - this would need the fetch_title function implemented
        url_pattern = re.compile(r'https?://\S+')
        urls = url_pattern.findall(message)
        if urls:
            for url in urls:
                # Start a thread to fetch the title without blocking
                threading.Thread(target=fetch_title, 
                                args=(server.irc, channel, url),
                                daemon=True).start()
                
        return False  # Message wasn't explicitly handled
        
    except Exception as e:
        log(f"Error processing message: {str(e)}", "ERROR")
        import traceback
        log(traceback.format_exc(), "ERROR")
        return False

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

def send_weather(irc=None, channel=None, location="Joensuu"):
    """
    Fetches and sends weather information for a specified location.
    
    Args:
        irc (socket, optional): IRC socket object
        channel (str, optional): IRC channel to send to
        location (str): Location to get weather for. Default is "Joensuu"
    """
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
    # Validate input and set defaults
    date = datetime.now()
    hour = date.hour
    if len(text) == 1:
        log(f"Haettu tunti t�n��n: {hour}", "DEBUG")
    elif len(text) == 2:
        parts = text[1].strip().split()
        if parts[0].lower() == "huomenna" and len(parts) == 2:
            hour = int(parts[1])
            date += timedelta(days=1)
            log(f"Haettu tunti huomenna: {hour}", "DEBUG")
        elif len(parts) == 1 and parts[0].isdigit():
            hour = int(parts[0])
            log(f"Haettu tunti t�n��n: {hour}", "DEBUG")
        else:
            error_message = "Virheellinen komento! K�yt�: !sahko [huomenna] <tunti>"
            log(error_message)
            send_message(irc, channel, error_message)
            return

    # Format dates
    date_str = date.strftime("%Y%m%d")
    date_plus_one = date + timedelta(days=1)
    date_tomorrow = date_plus_one.strftime("%Y%m%d")

    # Form API URLs
    url_today = f"https://web-api.tp.entsoe.eu/api?securityToken={ELECTRICITY_API_KEY}&documentType=A44&in_Domain=10YFI-1--------U&out_Domain=10YFI-1--------U&periodStart={date_str}0000&periodEnd={date_str}2300"
    url_tomorrow = f"https://web-api.tp.entsoe.eu/api?securityToken={ELECTRICITY_API_KEY}&documentType=A44&in_Domain=10YFI-1--------U&out_Domain=10YFI-1--------U&periodStart={date_tomorrow}0000&periodEnd={date_tomorrow}2300"

    def fetch_prices(url):
        try:
            response = requests.get(url)
            if response.status_code != 200:
                return {}
            xml_data = ElementTree.parse(StringIO(response.text))
            ns = {"ns": "urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3"}
            prices = {
                int(point.find("ns:position", ns).text): 
                float(point.find("ns:price.amount", ns).text)
                for point in xml_data.findall(".//ns:Point", ns)
            }
            return prices
        except Exception as e:
            log(f"Virhe s�hk�n hintojen haussa: {e}")
            return {}

    # Fetch prices for today and tomorrow
    prices_today = fetch_prices(url_today)
    prices_tomorrow = fetch_prices(url_tomorrow)

    # Process and format the prices
    hour_position = hour + 1  # API uses 1-24 hour format
    result_parts = []

    if hour_position in prices_today:
        price_eur_per_mwh = prices_today[hour_position]
        price_snt_per_kwh = (price_eur_per_mwh / 10) * 1.255  # Convert to cents and add VAT 25.5%
        result_parts.append(f"T�n��n klo {hour}: {price_snt_per_kwh:.2f} snt/kWh (ALV 25,5%)")

    if hour_position in prices_tomorrow:
        price_eur_per_mwh = prices_tomorrow[hour_position]
        price_snt_per_kwh = (price_eur_per_mwh / 10) * 1.255
        result_parts.append(f"Huomenna klo {hour}: {price_snt_per_kwh:.2f} snt/kWh (ALV 25,5%)")

    # Send the results
    if result_parts:
        output_message(", ".join(result_parts), irc, channel)
    else:
        output_message(f"S�hk�n hintatietoja ei saatavilla tunneille {hour}. https://sahko.tk", irc, channel)
    """
    Fetches and sends electricity price information.
    
    Args:
        irc (socket, optional): IRC socket object
        channel (str, optional): IRC channel to send to
        text (list): Command parts containing time information
    """
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

# Eurojackpot functionality
EUROJACKPOT_URL = "https://www.euro-jackpot.net/fi/tilastot/numerotaajuus"

def get_eurojackpot_numbers():
    """
    Fetches the latest Eurojackpot numbers and most frequent numbers.
    
    Returns:
        tuple: (latest_numbers, most_frequent_numbers) or error message if failed
    """
    url = "https://www.euro-jackpot.net/fi/tilastot/numerotaajuus"
    response = requests.get(url)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, "html.parser")
    table_rows = soup.select("table tr")  # Adjust the selector based on actual table structure
    
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

def handle_eurojackpot(server, channel, message, sender, args):
    """Handler for !eurojackpot command"""
    result = get_eurojackpot_numbers()
    
    if isinstance(result, tuple):
        latest, frequent = result
        message = (f"Latest Eurojackpot: {', '.join(map(str, latest))} | "
                  f"Most Frequent Numbers: {', '.join(map(str, frequent))}")
    else:
        message = result  # Error message

    server.send_message(channel, message)

def search_youtube(query):
    """
    Search for videos on YouTube and return the top result URL.
    
    Args:
        query (str): Search terms for YouTube
        
    Returns:
        str: URL of the top video result or error message
    """
    try:
        search_response = youtube.search().list(
            q=query,
            part="id,snippet",
            maxResults=1,
            type="video"
        ).execute()

        # Check if we have results
        if search_response.get("items"):
            video_id = search_response["items"][0]["id"]["videoId"]
            title = search_response["items"][0]["snippet"]["title"]
            url = f"https://www.youtube.com/watch?v={video_id}"
            return f"{title}: {url}"
        else:
            return "No results found."
    except Exception as e:
        log(f"YouTube search error: {e}", "ERROR")
        return f"Error searching YouTube: {str(e)}"

def handle_youtube_search(server, channel, message, sender, args):
    """
    Handler for !youtube command - searches YouTube and returns first result
    
    Args:
        server: The IRC server instance
        channel: The IRC channel to respond to
        message: The original message
        sender: The user who sent the command
        args: Command arguments (search query)
    """
    log(f"YouTube search requested by {sender} with query: {args}")
    
    try:
        # Extract search query from arguments
        if not args:
            server.send_message(channel, "Usage: !youtube <search query>")
            return
            
        # Join all args to form the search query
        search_query = " ".join(args)
        log(f"Searching YouTube for: {search_query}", "DEBUG")
        
        # Search YouTube using the existing function
        result = search_youtube(search_query)
        
        # Send the result back to the channel
        server.send_message(channel, result)
        
    except Exception as e:
        error_msg = f"Error processing YouTube search: {str(e)}"
        log(error_msg, "ERROR")
        server.send_message(channel, "Sorry, an error occurred while searching YouTube.")
