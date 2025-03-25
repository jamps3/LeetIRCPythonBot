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

def handle_youtube_search(server, channel, message, sender
