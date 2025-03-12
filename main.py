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

# Initialize conversation history
conversation_history = [{"role": "system", "content": "Olet nerokas irkkikanavan botti. Perustiedot: krak=alkoholijuoman avaus"}]

# Aseta API-avaimet
load_dotenv()  # Lataa .env-tiedoston muuttujat
WEATHER_API_KEY = os.getenv("weatherApiKey")
ELECTRICITY_API_KEY = os.getenv("electricityApiKey")
api_key = os.getenv("OPENAI_API_KEY")

bot_name = "jL3b2"
channel = "#joensuutest"
data_file = "values.bin"
last_ping = time.time()
# Luo OpenAI-asiakasolio (uusi tapa OpenAI 1.0.0+ versiossa)
client = openai.OpenAI(api_key=api_key)

data_file = "kraks_data.pkl"

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

    # Print to verify
    print(kraks)  
    # Example Output: {'Alice': {'hello': 2, 'world': 1}, 'Bob': {'python': 1, 'hello': 1}}
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

def login(irc, writer):
    nick = bot_name
    login = bot_name

    log(f"Weather API Key: {WEATHER_API_KEY}", "DEBUG")
    log(f"Electricity API Key: {ELECTRICITY_API_KEY}", "DEBUG")

    writer.sendall(f"NICK {nick}\r\n".encode("utf-8"))
    writer.sendall(f"USER {login} 0 * :{nick}\r\n".encode("utf-8"))
    time.sleep(2)
    writer.sendall(f"JOIN {channel}\r\n".encode("utf-8"))
    log(f"Joined channel {channel}")

def read(irc):
    global last_ping, latency_start
    while True:
        response = irc.recv(4096).decode("utf-8", errors="ignore")
        if response:
            for line in response.strip().split("\n"):  # Split into separate lines
                log(line.strip())  # Log each line separately
            # Handle PING messages (keep connection alive)
            if response.startswith("PING"):
                last_ping = time.time()
                ping_value = response.split(":", 1)[1].strip()
                irc.sendall(f"PONG :{ping_value}\r\n".encode("utf-8"))
                log(f"Sent PONG response to {ping_value}")
            process_message(irc, response)

def keepalive_ping(irc):
    global last_ping
    while True:
        time.sleep(120)
        if time.time() - last_ping > 120:
            irc.sendall("PING :keepalive\r\n".encode("utf-8"))
            log("Sent keepalive PING")
            last_ping = time.time()

def process_message(irc, message):
    """Processes incoming IRC messages and tracks word statistics."""
    global latency_start
    match = re.search(r":(\S+)!(\S+) PRIVMSG (\S+) :(.+)", message)
    log(f"Raw IRC message received: {message}")
    
    if match:
        sender, _, channel, text = match.groups()

        # Track words only if it's not a bot command
        if not text.startswith(("!", "http")):
            words = re.findall(r"\b\w+\b", text.lower())  # Extract words, ignore case
            kraks = load()
            update_kraks(kraks, sender, words)
            save(kraks)  # Save updates immediately
        
        # !sana - Sanalaskuri
        if text.startswith("!sana "):
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
                    send_message(irc, channel, f"Sana '{search_word}' on sanottu: {results}")
                else:
                    send_message(irc, channel, f"Kukaan ei ole sanonut sanaa '{search_word}' vielä.")
            else:
                send_message(irc, channel, "Käytä komentoa: !sana <sana>")

        # !topwords - Käytetyimmät sanat
        elif text.startswith("!topwords"):
            parts = text.split(" ", 1)
            kraks = load()

            if len(parts) > 1:  # Specific nick provided
                nick = parts[1].strip()
                if nick in kraks:
                    top_words = Counter(kraks[nick]).most_common(5)
                    word_list = ", ".join(f"{word}: {count}" for word, count in top_words)
                    send_message(irc, channel, f"{nick}: {word_list}")
                else:
                    send_message(irc, channel, f"Käyttäjää '{nick}' ei löydy.")
            else:  # Show top words for all users
                overall_counts = Counter()
                for words in kraks.values():
                    overall_counts.update(words)

                top_words = overall_counts.most_common(5)
                word_list = ", ".join(f"{word}: {count}" for word, count in top_words)
                send_message(irc, channel, f"Käytetyimmät sanat: {word_list}")
        
        # !leaderboard - Aktiivisimmat käyttäjät
        elif text.startswith("!leaderboard"):
            kraks = load()
            user_word_counts = {nick: sum(words.values()) for nick, words in kraks.items()}
            top_users = sorted(user_word_counts.items(), key=lambda x: x[1], reverse=True)[:5]

            if top_users:
                leaderboard_msg = ", ".join(f"{nick}: {count}" for nick, count in top_users)
                send_message(irc, channel, f"Aktiivisimmat käyttäjät: {leaderboard_msg}")
            else:
                send_message(irc, channel, "Ei vielä tarpeeksi dataa leaderboardille.")
        
        # !kraks - Krakkaukset
        elif text.startswith("!kraks"):
            kraks = load()
            total_kraks = 0
            word_counts = {"krak": 0, "kr1k": 0, "kr0k": 0}
            top_users = {"krak": None, "kr1k": None, "kr0k": None}

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

            send_message(irc, channel, f"{total_message}, {details}")
        
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
                                print(f"Yesterday's 12-month Euribor rate: {euribor_12m.attrib['value']}%")
                                send_message(irc, channel, f"{formatted_date} 12kk Euribor: {euribor_12m.attrib['value']}%")
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

        # Bot received the latency test message back
        # Handle the bot's own LatencyCheck response
        #elif re.search(rf"PRIVMSG {re.escape(bot_name)} :!LatencyCheck", text):
        elif "!LatencyCheck" in text:
            if 'latency_start' in globals():
                latency = time.time() - latency_start
                latency_ns = int((time.time() - latency_start) * 1_000_000_000)  # Convert to ns
                global half_latency_ns
                half_latency_ns = latency_ns // 2  # Divide by 2 and store globally
                log(f"✅ Recognized LatencyCheck response! Latency: {latency:.3f} seconds")
                irc.sendall(f"PRIVMSG {bot_name} :Latency is {latency_ns} ns\r\n".encode("utf-8"))
            else:
                log("⚠️ Warning: Received LatencyCheck response, but no latency_start timestamp exists.")

def measure_latency(irc, nickname):
    """Sends a latency test message to self and starts the timer."""
    global latency_start
    latency_start = time.time()  # Store timestamp
    test_message = "!LatencyCheck"
    irc.sendall(f"PRIVMSG {nickname} :{test_message}\r\n".encode("utf-8"))
    log(f"Sent latency check message: {test_message}")

def send_scheduled_message(irc, channel, message, target_hour=13, target_minute=37, target_second=13, target_microsecond=371337):
    """
    Lähettää viestin tarkalleen tiettynä kellonaikana nanosekunnin tarkkuudella.

    :param irc: IRC-yhteysolio
    :param channel: IRC-kanava, johon viesti lähetetään
    :param message: Lähetettävä viesti
    :param target_hour: Kellotunti (0-23), jolloin viesti lähetetään
    :param target_minute: Minuutti (0-59), jolloin viesti lähetetään (oletus 37)
    :param target_second: Sekunti (0-59), jolloin viesti lähetetään (oletus 13)
    :param target_microsecond: Mikrosekunti (0-999999), jolloin viesti lähetetään (oletus 371337)
    """
    while True:
        now = datetime.now()
        log(now)
        target_time = now.replace(hour=target_hour, minute=target_minute, second=target_second, microsecond=target_microsecond)

        log(f"Kohdeaika: {target_time}")

        # Jos aika on jo mennyt tänään, siirretään se huomiseen
        if now >= target_time:
            target_time += timedelta(days=1)

        time_to_wait = (target_time - now).total_seconds()

        log(f"Odotusaika: {time_to_wait}")

        # Nukutaan suurin osa ajasta, 10 millisekuntia aktiiviseen odotukseen
        if time_to_wait > 0.01:
            log(f"Odotetaan {time_to_wait:.6f} sekuntia ({target_hour:02d}:{target_minute:02d}:{target_second:02d}.{target_microsecond:06d}) asti...")
            time.sleep(time_to_wait - 0.01)
            log(f"[{datetime.now()}] Hienosäätö alkaa...")

        # Hienosäätö: käytetään time.perf_counter_ns() laskemaan tarkka viive nanosekunneissa
        start_ns = time.perf_counter_ns()
        wait_ns = int(time_to_wait * 1_000_000_000)  # Muutetaan odotettava aika nanosekunneiksi
        target_ns = start_ns + wait_ns  # Määritetään tarkka kohdeaika nanosekunteina

        log("Aktiivinen odotus viimeisille mikrosekunneille...")
        # Asetetaan kohde-aika 2 sekuntia nykyhetkeä pidemmälle
        # target_ns = time.perf_counter_ns() + int(2e9)  # 2 sekuntia = 2 * 10^9 nanosekuntia
        target_ns = time.perf_counter_ns() + int(10e6)  # 10ms = 10 * 10^6 nanosekuntia

        # Odotetaan kunnes nykyinen aika ylittää target_ns
        while time.perf_counter_ns() < target_ns:
            print(f"Nykyinen ns: {time.perf_counter_ns()}, Tavoite ns: {target_ns}")
            #time.sleep(0.001)  # Lyhyt tauko CPU-kuorman vähentämiseksi

        # Lähetetään viesti
        send_message(irc, channel, message)
        log(f"Viesti lähetetty: {message} @ ({target_hour}:{target_minute}:{target_second}.{target_microsecond})")

        # Odotetaan seuraavaan päivään
        # time.sleep(86400)  # 24 tuntia

def send_weather(irc, channel, location):
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

            # Tarkistetaan, onko sateen tai lumen tietoja
            rain = data.get("rain", {}).get("1h", 0)  # Sade viimeisen tunnin aikana (mm)
            snow = data.get("snow", {}).get("1h", 0)  # Lumi viimeisen tunnin aikana (mm)

            # Auringonnousu ja -lasku aikaleimoista
            sunrise = datetime.fromtimestamp(data["sys"]["sunrise"]).strftime("%H:%M")
            sunset = datetime.fromtimestamp(data["sys"]["sunset"]).strftime("%H:%M")

            # Rakennetaan viesti
            weather_info = (f"{location} 🔮: {description}, {temp}°C ({feels_like} ~°C), "
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

    send_message(irc, channel, weather_info)

def send_electricity_price(irc, channel, text):
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
    send_message(irc, channel, electricity_info_today + ", " + electricity_info_tomorrow)
    # send_message(irc, channel, electricity_info_tomorrow)

def fetch_title(irc, channel, text):
    log(f"Syöte: {text}")  # Logataan koko syöte

    # Päivitetty regex, joka löytää myös "www.youtube.com"
    pattern = r"(https:\/\/?[^\s]+|www\.[^\s]+|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})"
    urls = re.findall(pattern, text)

    log(f"Löydetyt URL-osoitteet: {urls}")  # Logataan löydetyt URL-osoitteet

    if not urls:
        send_message(irc, channel, "Ei löydetty kelvollisia URL-osoitteita.")
        return

    for url in urls:
        try:
            log(f"Käsitellään URL: {url}")  # Debug-tulostus

            # Lisätään HTTPS, jos URL ei ala sillä
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
                log(f"Korjattu URL: {url}")  # Debug: tulostetaan korjattu URL
            
            response = requests.get(url, timeout=5)
            response.raise_for_status()  # Tarkistetaan, ettei tullut HTTP-virhettä
            
            soup = BeautifulSoup(response.text, "html.parser")
            title = soup.title.string.strip() if soup.title else "(ei otsikkoa)"
            
            log(f"Haettu otsikko: {title}")  # Debug: tulostetaan otsikko
            send_message(irc, channel, f"Otsikko: {title}")
        
        except requests.RequestException as e:
            log(f"Virhe URL:n {url} haussa: {e}")
            # send_message(irc, channel, f"Otsikon haku epäonnistui URL-osoitteelle: {url}")

# Funktio, joka ottaa keskustelun syötteen ja palauttaa GPT-4:n vastauksen
# Käytä OpenAI APIa keskusteluun
def keskustele(prompt, model="gpt-3.5-turbo", max_tokens=150):
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.7,
        n=1
    )
    return response.choices[0].message.content.strip()

# Example of using the function
#user_input = "What is the weather like today?"
#print(chat_with_gpt_4o_mini(user_input))
def chat_with_gpt_4o_mini(user_input):
    # Add user message to conversation history
    conversation_history.append({"role": "user", "content": user_input})

    # Get response from GPT-4o mini
    response = client.chat.completions.create(  # Use the new syntax
        model="gpt-4o-mini",  # Specify the model
        messages=conversation_history,  # Provide the conversation history as the prompt
        max_tokens=150  # Adjust the token count as needed
    )
    
    # Correct way to access the response
    assistant_reply = response.choices[0].message.content.strip()

    # Add assistant's response to conversation history
    conversation_history.append({"role": "assistant", "content": assistant_reply})

    # Muutetaan rivinvaihdot yhdeksi välilyönniksi, jotta viesti ei katkea
    assistant_reply = assistant_reply.replace("\n", " ")

    return assistant_reply

def send_message(irc, channel, message):
    irc.sendall(f"NOTICE {channel} :{message}\r\n".encode("utf-8"))

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

def euribor():
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
    server = "irc.atw-inter.net"
    port = 6667
    while True:
        try:
            load()
            irc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            irc.connect((server, port))
            writer = irc
            login(irc, writer)
            threading.Thread(target=keepalive_ping, args=(irc,), daemon=True).start()
            read(irc)
        except (socket.error, ConnectionError) as e:
            log(f"Server error: {e}", "ERROR")
        finally:
            try:
                save()
                irc.close()
                log("Bot exited successfully.")
            except Exception:
                pass

if __name__ == "__main__":
    main()
