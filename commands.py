"""
IRC Command Processing Module

This module contains the main command processing functions extracted from main.py
for better code organization and maintainability.
"""

import html
import json
import os
import platform
import re
import time
import urllib.parse
import xml.etree.ElementTree as ElementTree
from collections import Counter
from datetime import datetime
from io import StringIO

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from googleapiclient.discovery import build

import commands
from logger import get_logger

# Load environment variables
load_dotenv()
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme")
BOT_VERSION = "2.0.0"


def verify_admin_password(command_text):
    """Check if command contains correct admin password."""
    parts = command_text.split()
    if len(parts) >= 2 and parts[1] == ADMIN_PASSWORD:
        return True
    return False


def send_raw_irc_command(irc, command, log_func):
    """Send a raw IRC command to the server."""
    try:
        irc.sendall(f"{command}\r\n".encode("utf-8"))
        log_func(f"Sent raw IRC command: {command}", "INFO")
        return True
    except Exception as e:
        log_func(f"Error sending raw IRC command: {e}", "ERROR")
        return False


# Initialize YouTube API client
youtube = (
    build("youtube", "v3", developerKey=YOUTUBE_API_KEY) if YOUTUBE_API_KEY else None
)

# Initialize logger
_logger = get_logger("Commands")

# Import new word tracking system
from word_tracking import DataManager, DrinkTracker, GeneralWords, TamagotchiBot

# Initialize word tracking system
data_manager = DataManager()
drink_tracker = DrinkTracker(data_manager)
general_words = GeneralWords(data_manager)
tamagotchi_bot = TamagotchiBot(data_manager)


def fetch_title_improved(
    irc, channel, url, last_title_ref, send_message_func, log_func
):
    """
    Improved version of fetch_title from message_handlers.py with better YouTube handling
    and encoding detection.
    """
    # Skip URLs that are unlikely to have meaningful titles
    if any(
        skip_url in url.lower()
        for skip_url in [".jpg", ".jpeg", ".png", ".gif", ".mp4", ".webm"]
    ):
        log_func(f"Skipping image/video URL: {url}", "DEBUG")
        return

    try:
        log_func(f"Fetching title for URL: {url}", "DEBUG")

        # Special handling for YouTube URLs to get more information
        youtube_pattern = re.compile(
            r"(?:https?:\/\/)?(?:www\.)?(?:youtube\.com|youtu\.be)\/(?:watch\?v=)?([a-zA-Z0-9_-]{11})"
        )
        youtube_match = youtube_pattern.search(url)

        if youtube_match and youtube:
            video_id = youtube_match.group(1)
            _logger.debug(f"YouTube video detected, ID: {video_id}")

            try:
                # Use YouTube API to get detailed information
                video_response = (
                    youtube.videos()
                    .list(part="snippet,contentDetails,statistics", id=video_id)
                    .execute()
                )

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
                    youtube_info = f'YouTube: "{title}" by {channel_name} | Views: {view_count_str} | Likes: {like_count_str}'

                    if youtube_info != last_title_ref[0]:
                        send_message_func(irc, channel, youtube_info)
                        last_title_ref[0] = youtube_info
                    return
            except Exception as e:
                _logger.warning(f"Error fetching YouTube video info: {str(e)}")
                # Fall back to regular title extraction if YouTube API fails

        # Regular title extraction for all other URLs
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
        }

        # Use a timeout to prevent hanging
        response = requests.get(url, headers=headers, timeout=10, stream=True)

        # Check content type before downloading everything
        content_type = response.headers.get("Content-Type", "").lower()
        log_func(f"Content type: {content_type}", "DEBUG")

        # Skip binary files and large content
        if (
            "text/html" not in content_type
            and "application/xhtml+xml" not in content_type
        ):
            log_func(f"Skipping non-HTML content: {content_type}", "DEBUG")
            return

        # Limit content size to prevent memory issues (100 KB should be enough for most titles)
        content_bytes = b""
        for chunk in response.iter_content(chunk_size=4096):
            content_bytes += chunk
            if len(content_bytes) > 102400:  # 100 KB
                break

        # Try to determine the encoding
        encoding = response.encoding

        # If the encoding is None or ISO-8859-1 (often default), try to detect it
        if not encoding or encoding.lower() == "iso-8859-1":
            # Check for charset in meta tags
            charset_match = re.search(
                rb'<meta[^>]*charset=["\']?([\w-]+)', content_bytes, re.IGNORECASE
            )
            if charset_match:
                encoding = charset_match.group(1).decode("ascii", errors="ignore")
                log_func(f"Found encoding in meta tag: {encoding}", "DEBUG")

        # Default to UTF-8 if detection failed
        if not encoding or encoding.lower() == "iso-8859-1":
            encoding = "utf-8"

        # Decode content with the detected encoding
        try:
            content = content_bytes.decode(encoding, errors="replace")
        except (UnicodeDecodeError, LookupError):
            log_func(
                f"Decoding failed with {encoding}, falling back to utf-8", "WARNING"
            )
            content = content_bytes.decode("utf-8", errors="replace")

        # Use BeautifulSoup to extract the title
        soup = BeautifulSoup(content, "html.parser")
        title_tag = soup.find("title")

        if title_tag and title_tag.string:
            title = title_tag.string.strip()

            # Clean the title by removing excessive whitespace
            title = re.sub(r"\s+", " ", title)

            # HTML unescape to handle entities like &amp;
            title = html.unescape(title)

            # Prepend "Title:" to distinguish from regular messages
            formatted_title = f"Title: {title}"

            # Only send if the title is different from the last one to avoid spam
            if formatted_title != last_title_ref[0]:
                send_message_func(irc, channel, formatted_title)
                last_title_ref[0] = formatted_title
                _logger.debug(f"Sent title: {title}")
        else:
            _logger.debug(f"No title found for URL: {url}")

    except requests.exceptions.Timeout:
        _logger.warning(f"Timeout while fetching URL: {url}")
    except requests.exceptions.TooManyRedirects:
        _logger.warning(f"Too many redirects for URL: {url}")
    except requests.exceptions.RequestException as e:
        _logger.warning(f"Request error for URL {url}: {str(e)}")
    except Exception as e:
        _logger.error(f"Error fetching title for {url}: {str(e)}")
        # More detailed error logging for debugging
        import traceback

        _logger.error(traceback.format_exc())


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

    return parts


def process_console_command(command_text, bot_functions):
    """Process commands from console input (unified with IRC commands)."""
    # Extract functions from bot_functions for console use
    notice_message = bot_functions["notice_message"]
    send_electricity_price = bot_functions["send_electricity_price"]
    load_leet_winners = bot_functions["load_leet_winners"]
    send_weather = bot_functions["send_weather"]
    load = bot_functions["load"]
    log = bot_functions["log"]
    fetch_title = bot_functions["fetch_title"]
    handle_ipfs_command = bot_functions["handle_ipfs_command"]
    chat_with_gpt = bot_functions["chat_with_gpt"]
    wrap_irc_message_utf8_bytes = bot_functions["wrap_irc_message_utf8_bytes"]

    # Parse command
    command_parts = command_text.split(" ", 1)
    command = command_parts[0].lower()
    args = command_parts[1] if len(command_parts) > 1 else ""

    # Handle commands
    if command == "!help":
        help_text = (
            "📋 Available commands:\n"
            "🌤️ Weather: !s [location]\n"
            "⚡ Electricity: !sahko [hour|huomenna hour]\n"
            "📊 Words: !sana <word>, !topwords [nick], !leaderboard\n"
            "🍺 Drinks: !drinkstats [nick|server|global], !drinkword <word>, !drink <specific>, !drinktop, !antikrak\n"
            "🐣 Tamagotchi: !tamagotchi, !feed [food], !pet\n"
            "🎯 Other: !aika, !kaiku, !euribor, !leetwinners, !crypto [coin], !version\n"
            "🎰 Games: !eurojackpot, !youtube <query>\n"
            "⚙️ Advanced: !leet, !get_total_counts, !tilaa, !url <url>, !ipfs add <url>\n"
            "🔒 Admin*: !join*, !part*, !nick*, !quit*, !raw*\n"
            "💬 Chat: Any message not starting with ! will be sent to AI\n"
            "* = Requires admin password"
        )
        for line in help_text.split("\n"):
            if line.strip():
                notice_message(line)

    elif command == "!s" or command == "!sää":
        location = args.strip() if args else "Joensuu"
        _logger.info(f"Getting weather for {location} from console")
        send_weather(None, None, location)  # Pass None for IRC and channel

    elif command == "!sahko" or command == "!sähkö":
        send_electricity_price(None, None, command_parts)

    elif command == "!aika":
        now_ns = time.time_ns()
        dt = datetime.fromtimestamp(now_ns // 1_000_000_000)
        nanoseconds = now_ns % 1_000_000_000
        formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S") + f".{nanoseconds:09d}"
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
                    f"{nick}: {count}" for nick, count in word_counts.items()
                )
                notice_message(f"Sana '{search_word}' on sanottu: {results}")
            else:
                notice_message(f"Kukaan ei ole sanonut sanaa '{search_word}' vielä.")
        else:
            notice_message("Käytä komentoa: !sana <sana>")

    elif command == "!topwords":
        kraks = load()
        if args:  # Specific nick provided
            nick = args.strip()
            if nick in kraks:
                top_words = Counter(kraks[nick]).most_common(5)
                word_list = ", ".join(f"{word}: {count}" for word, count in top_words)
                notice_message(f"{nick}: {word_list}")
            else:
                notice_message(f"Käyttäjää '{nick}' ei löydy.")
        else:  # Show top words for all users
            overall_counts = Counter()
            for words in kraks.values():
                overall_counts.update(words)
            top_words = overall_counts.most_common(5)
            word_list = ", ".join(f"{word}: {count}" for word, count in top_words)
            notice_message(f"Käytetyimmät sanat: {word_list}")

    elif command == "!leaderboard":
        kraks = load()
        user_word_counts = {nick: sum(words.values()) for nick, words in kraks.items()}
        top_users = sorted(user_word_counts.items(), key=lambda x: x[1], reverse=True)[
            :5
        ]
        if top_users:
            leaderboard_msg = ", ".join(f"{nick}: {count}" for nick, count in top_users)
            notice_message(f"Aktiivisimmat käyttäjät: {leaderboard_msg}")
        else:
            notice_message("Ei vielä tarpeeksi dataa leaderboardille.")

    elif command == "!euribor":
        # XML data URL from Suomen Pankki
        url = "https://reports.suomenpankki.fi/WebForms/ReportViewerPage.aspx?report=/tilastot/markkina-_ja_hallinnolliset_korot/euribor_korot_today_xml_en&output=xml"
        response = requests.get(url)
        if response.status_code == 200:
            root = ElementTree.fromstring(response.content)
            ns = {"ns": "euribor_korot_today_xml_en"}
            period = root.find(".//ns:period", namespaces=ns)
            if period is not None:
                date_str = period.attrib.get("value")
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                if platform.system() == "Windows":
                    formatted_date = date_obj.strftime("%#d.%#m.%y")
                else:
                    formatted_date = date_obj.strftime("%-d.%-m.%y")
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
        filtered_winners = {}
        for winner, categories in leet_winners.items():
            for cat, count in categories.items():
                if cat not in filtered_winners or count > filtered_winners[cat][1]:
                    filtered_winners[cat] = (winner, count)
        winners_text = ", ".join(
            f"{cat}: {winner} [{count}]"
            for cat, (winner, count) in filtered_winners.items()
        )
        response = (
            f"𝓛𝓮𝓮𝓽𝔀𝓲𝓷𝓷𝓮𝓻𝓼: {winners_text}"
            if winners_text
            else "No 𝓛𝓮𝓮𝓽𝔀𝓲𝓷𝓷𝓮𝓻𝓼 recorded yet."
        )
        notice_message(response)

    elif command.startswith("!url"):
        if args:
            fetch_title(None, None, args)
        else:
            notice_message("Käytä komentoa: !url <url>")

    elif command.startswith("!ipfs"):
        handle_ipfs_command(command_text, None, target=None)

    # Handle new drink tracking commands for console
    elif command == "!drinkstats":
        # For console, we'll use a dummy server name
        console_server = "console"
        if args:
            arg = args.strip().lower()
            if arg == "server":
                stats = drink_tracker.get_server_stats(console_server)
                response = f"Server {stats['server']}: {stats['total_users']} users, {stats['total_drink_words']} drink words"
            elif arg == "global":
                stats = drink_tracker.get_global_stats()
                response = f"Global: {stats['total_users']} users, {stats['total_drink_words']} drink words"
            else:
                nick = args.strip()
                top_drinks = drink_tracker.get_user_top_drinks(console_server, nick, 5)
                if top_drinks:
                    drinks_text = ", ".join(
                        [f"{d['drink_word']}:{d['total']}" for d in top_drinks]
                    )
                    response = f"{nick}: {drinks_text}"
                else:
                    response = f"Ei juomatilastoja käyttäjälle {nick}"
        else:
            stats = drink_tracker.get_server_stats(console_server)
            response = f"Top 5: {', '.join([f'{nick}:{count}' for nick, count in stats['top_users'][:5]])}"
        notice_message(response)

    elif command == "!drinkword":
        if args:
            drink_word = args.strip()
            results = drink_tracker.search_drink_word(drink_word)
            if results["total_occurrences"] > 0:
                top_users = results["users"][:5]
                users_text = ", ".join([f"{u['nick']}:{u['total']}" for u in top_users])
                response = f"'{drink_word}': {results['total_occurrences']} total. Top: {users_text}"
            else:
                response = f"Ei löydetty juomasanaa '{drink_word}'"
        else:
            response = "Käytä: !drinkword <sana>"
        notice_message(response)

    elif command == "!drink":
        if args:
            specific_drink = args.strip()
            results = drink_tracker.search_specific_drink(specific_drink)
            if results["total_occurrences"] > 0:
                top_users = results["users"][:5]
                users_text = ", ".join([f"{u['nick']}:{u['total']}" for u in top_users])
                response = f"'{specific_drink}': {results['total_occurrences']} total. Top: {users_text}"
            else:
                response = f"Ei löydetty juomaa '{specific_drink}'"
        else:
            response = "Käytä: !drink <juoma>"
        notice_message(response)

    elif command == "!drinktop":
        stats = drink_tracker.get_global_stats()
        top_users = stats["top_users"][:10]
        if top_users:
            users_text = ", ".join(
                [f"{u['nick']}@{u['server']}:{u['total']}" for u in top_users]
            )
            response = f"🍺 Top 10 drinkers: {users_text}"
        else:
            response = "Ei vielä juomatilastoja"
        notice_message(response)

    elif command == "!tamagotchi":
        if args and args.lower() == "toggle":
            # Toggle tamagotchi responses (only in console)
            notice_message(
                "🐣 Tamagotchi toggle functionality is only available in IRC channels."
            )
        else:
            console_server = "console"
            status = tamagotchi_bot.get_status(console_server)
            lines = status.split("\n")
            for line in lines:
                notice_message(line)

    elif command == "!feed":
        food = args if args else None
        console_server = "console"
        response = tamagotchi_bot.feed(console_server, food)
        notice_message(response)

    elif command == "!pet":
        console_server = "console"
        response = tamagotchi_bot.pet(console_server)
        notice_message(response)

    elif command == "!version":
        notice_message(f"Bot version: {BOT_VERSION}")

    # Admin commands requiring password
    elif command == "!join":
        if verify_admin_password(command_text):
            # Extract channel from command: !join password #channel [key]
            parts = command_text.split()
            if len(parts) >= 3:
                channel = parts[2]
                key = parts[3] if len(parts) > 3 else ""
                notice_message(
                    f"Admin command: JOIN {channel} {key if key else '(no key)'}"
                )
            else:
                notice_message("Usage: !join <password> #channel [key]")
        else:
            notice_message("Invalid password for admin command.")

    elif command == "!part":
        if verify_admin_password(command_text):
            # Extract channel from command: !part password #channel
            parts = command_text.split()
            if len(parts) >= 3:
                channel = parts[2]
                notice_message(f"Admin command: PART {channel}")
            else:
                notice_message("Usage: !part <password> #channel")
        else:
            notice_message("Invalid password for admin command.")

    elif command == "!nick":
        if verify_admin_password(command_text):
            # Extract new nickname from command: !nick password newnick
            parts = command_text.split()
            if len(parts) >= 3:
                new_nick = parts[2]
                notice_message(f"Admin command: NICK {new_nick}")
            else:
                notice_message("Usage: !nick <password> <new_nickname>")
        else:
            notice_message("Invalid password for admin command.")

    elif command == "!quit":
        if verify_admin_password(command_text):
            # Extract quit message from command: !quit password [message]
            parts = command_text.split(" ", 2)
            quit_message = parts[2] if len(parts) > 2 else "Admin quit"
            notice_message(f"Admin command: QUIT :{quit_message}")
        else:
            notice_message("Invalid password for admin command.")

    elif command == "!raw":
        if verify_admin_password(command_text):
            # Extract raw IRC command: !raw password COMMAND
            parts = command_text.split(" ", 2)
            if len(parts) >= 3:
                raw_command = parts[2]
                notice_message(f"Admin command: {raw_command}")
            else:
                notice_message("Usage: !raw <password> <IRC_COMMAND>")
        else:
            notice_message("Invalid password for admin command.")

    else:
        # Check if it's a crypto command
        if re.search(r"!crypto\b", command_text, re.IGNORECASE):
            get_crypto_price = bot_functions["get_crypto_price"]
            match = re.search(r"!crypto\s+(\w+)", command_text, re.IGNORECASE)
            if match:
                coin = match.group(1).lower()
                price = get_crypto_price(coin, "eur")
                message = f"The current price of {coin.capitalize()} is {price} €."
            else:
                top_coins = ["bitcoin", "ethereum", "tether"]
                prices = {coin: get_crypto_price(coin, "eur") for coin in top_coins}
                message = " | ".join(
                    [f"{coin.capitalize()}: {prices[coin]} €" for coin in top_coins]
                )
            notice_message(message)
        else:
            # Any unrecognized command
            notice_message(
                f"Command '{command}' not recognized. Type !help for available commands."
            )


def process_message(irc, message, bot_functions):
    """Processes incoming IRC messages and tracks word statistics."""
    # Extract all needed functions and variables from bot_functions dict
    tamagotchi = bot_functions["tamagotchi"]
    count_kraks = bot_functions["count_kraks"]
    notice_message = bot_functions["notice_message"]
    send_electricity_price = bot_functions["send_electricity_price"]
    measure_latency = bot_functions["measure_latency"]
    get_crypto_price = bot_functions["get_crypto_price"]
    load_leet_winners = bot_functions["load_leet_winners"]
    save_leet_winners = bot_functions["save_leet_winners"]
    send_weather = bot_functions["send_weather"]
    send_scheduled_message = bot_functions["send_scheduled_message"]
    get_eurojackpot_numbers = bot_functions["get_eurojackpot_numbers"]
    search_youtube = bot_functions["search_youtube"]
    handle_ipfs_command = bot_functions["handle_ipfs_command"]
    lookup = bot_functions["lookup"]
    format_counts = bot_functions["format_counts"]
    chat_with_gpt = bot_functions["chat_with_gpt"]
    wrap_irc_message_utf8_bytes = bot_functions["wrap_irc_message_utf8_bytes"]
    send_message = bot_functions["send_message"]
    load = bot_functions["load"]
    save = bot_functions["save"]
    update_kraks = bot_functions["update_kraks"]
    log = bot_functions["log"]
    fetch_title = bot_functions["fetch_title"]
    lemmat = bot_functions["lemmat"]
    subscriptions = bot_functions["subscriptions"]
    DRINK_WORDS = bot_functions["DRINK_WORDS"]
    EKAVIKA_FILE = bot_functions["EKAVIKA_FILE"]
    bot_name = bot_functions["bot_name"]
    get_latency_start = bot_functions["latency_start"]
    set_latency_start = bot_functions["set_latency_start"]
    is_private = False
    match = re.search(r":(\S+)!(\S+) PRIVMSG (\S+) :(.+)", message)

    if match:
        sender, _, target, text = match.groups()

        # === NEW WORD TRACKING SYSTEM ===
        # Get server name for tracking
        server_name = data_manager.get_server_name(irc)

        # Process each message and count words, except lines starting with !
        if not text.startswith("!"):
            # General words tracking (renamed from tamagotchi)
            general_words.process_message(server_name, sender, text, target)

            # Drink words tracking with privacy controls
            drink_matches = drink_tracker.process_message(server_name, sender, text)

            # Note: Tamagotchi interaction is now handled by bot_manager._track_words()
            # which properly respects the tamagotchi_enabled toggle setting

            # Legacy tamagotchi call removed - now handled by bot_manager._track_words()
            # with proper toggle support

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
            # irc.sendall(f"PRIVMSG {sender} :Hello! You said: {text}\\r\\n".encode("utf-8"))
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
                latency_start_value = get_latency_start()
                if latency_start_value > 0:
                    elapsed_time = time.time() - latency_start_value
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
            help_text = (
                "📋 Available commands:\n"
                "🌤️ Weather: !s [location]\n"
                "⚡ Electricity: !sahko [hour|huomenna hour]\n"
                "📊 Words: !sana <word>, !topwords [nick], !leaderboard\n"
                "🍺 Drinks: !drinkstats [nick|server|global], !drinkword <word>, !drink <specific>, !drinktop, !antikrak\n"
                "🐣 Tamagotchi: !tamagotchi, !feed [food], !pet\n"
                "🎯 Other: !aika, !kaiku, !euribor, !leetwinners, !crypto [coin], !version\n"
                "🎰 Games: !eurojackpot [date|scrape|stats], !youtube <query>\n"
                "⚙️ Advanced: !leet, !get_total_counts, !tilaa, !url <url>, !ipfs add <url>\n"
                "🔒 Admin*: !join*, !part*, !nick*, !quit*, !raw*\n"
                "💬 Chat: Mention bot name or send private message for AI chat\n"
                "* = Requires admin password"
            )
            # Split help into multiple messages
            for line in help_text.split("\n"):
                if line.strip():
                    notice_message(line, irc, target)

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
            parts = text.split()
            if len(parts) >= 2:
                coin = parts[1].lower()
                currency = parts[2] if len(parts) > 2 else "eur"
                price = get_crypto_price(coin, currency)
                message = f"💸 {coin.capitalize()}: {price} {currency.upper()}"
                notice_message(message, irc, target)
            else:
                notice_message(
                    "💸 Usage: !crypto <coin> [currency]. Example: !crypto btc eur",
                    irc,
                    target,
                )

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
            match = re.match(
                r"!leet\s+(#\S+)\s+(\d{1,2}):(\d{1,2}):(\d{1,2})(?:\.(\d{1,9}))?\s+(.+)",
                text,
            )

            if match:
                channel = match.group(1)
                hour = int(match.group(2))
                minute = int(match.group(3))
                second = int(match.group(4))
                microsecond_str = match.group(5)
                message = match.group(6)

                microsecond = (
                    int(microsecond_str.ljust(6, "0")[:6]) if microsecond_str else 0
                )

                send_scheduled_message(
                    irc, channel, message, hour, minute, second, microsecond
                )
            else:
                notice_message(
                    (
                        "Virheellinen komento! Käytä muotoa: !leet #kanava HH:MM:SS viesti tai !leet #kanava HH:MM:SS.mmmmmm viesti - Ajan perään tulee antaa viesti, esim.: !leet #kanava 12:34:56.123456 Hei maailma!"
                    ),
                    irc,
                    target,
                )

        # !link - Lyhennä linkki
        elif text.startswith("!link"):
            match = re.search(r"!link\s+(\S+)", text)
            if match:
                url = match.group(1)
                log("!link", "DEBUG")

        elif text.startswith("!eurojackpot"):
            log(f"Eurojackpot command received: {text}", "DEBUG")
            parts = text.split()
            command = parts[1] if len(parts) > 1 else None
            arg = parts[2] if len(parts) > 2 else None
            log(f"Parsed command: {command}, arg: {arg}", "DEBUG")

            # Import the service
            from services.eurojackpot_service import get_eurojackpot_service
            service = get_eurojackpot_service()
            log("Eurojackpot service imported and initialized", "DEBUG")

            try:
                if command == "scrape":
                    # Handle scrape command
                    log("Executing scrape command", "DEBUG")
                    result = service.scrape_all_draws()
                    log(f"Scrape result: {result}", "DEBUG")
                    notice_message(result["message"], irc, target)
                elif command == "stats":
                    # Handle stats command
                    log("Executing stats command", "DEBUG")
                    result = service.get_database_stats()
                    log(f"Stats result: {result}", "DEBUG")
                    notice_message(result["message"], irc, target)
                elif command == "add":
                    # Handle manual add command
                    log("Executing add command", "DEBUG")
                    # Parse remaining arguments: date, numbers, [jackpot]
                    remaining_parts = text.split()[2:]  # Skip "!eurojackpot" and "add"
                    
                    if len(remaining_parts) < 2:
                        notice_message("❌ Käyttö: !eurojackpot add PP.KK.VVVV 1,2,3,4,5,6,7 [päävoitto]", irc, target)
                        notice_message("Esim: !eurojackpot add 20.12.2024 1,5,12,25,35,3,8 15000000", irc, target)
                    else:
                        date_str = remaining_parts[0]
                        numbers_str = remaining_parts[1]
                        jackpot_str = remaining_parts[2] if len(remaining_parts) > 2 else "Tuntematon"
                        
                        log(f"Adding draw manually: date={date_str}, numbers={numbers_str}, jackpot={jackpot_str}", "DEBUG")
                        result = service.add_draw_manually(date_str, numbers_str, jackpot_str)
                        log(f"Add result: {result}", "DEBUG")
                        notice_message(result["message"], irc, target)
                elif command and command not in ["scrape", "stats", "add"]:
                    # Date-specific query
                    log(f"Executing date-specific query for: {command}", "DEBUG")
                    result = service.get_draw_by_date(command)
                    log(f"Date query result: {result}", "DEBUG")
                    message = result["message"]
                    # Split message if it contains newlines
                    lines = message.split("\n")
                    for line in lines:
                        if line.strip():
                            notice_message(line, irc, target)
                else:
                    # Default: show combined info (latest + next draw)
                    log("Executing default combined info command", "DEBUG")
                    from services.eurojackpot_service import eurojackpot_command
                    message = eurojackpot_command(arg)
                    log(f"Combined info result: {message}", "DEBUG")
                    # Split message if it contains newlines (combined info)
                    lines = message.split("\n")
                    for line in lines:
                        if line.strip():
                            notice_message(line, irc, target)
            except Exception as e:
                log(f"Error in eurojackpot command handling: {e}", "ERROR")
                import traceback
                log(f"Eurojackpot exception traceback: {traceback.format_exc()}", "DEBUG")
                notice_message(f"Eurojackpot: Virhe - {str(e)}", irc, target)

        elif text.startswith("!youtube"):
            match = re.search(r"!youtube\s+(.+)", text)
            if match:
                query_or_url = match.group(1)
                # Use search_youtube function from bot_functions
                try:
                    response = search_youtube(query_or_url)
                    notice_message(response, irc, target)
                except Exception as e:
                    log(f"YouTube search error: {e}", "ERROR")
                    notice_message(f"YouTube search error: {str(e)}", irc, target)

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
            parts = text.split()
            if len(parts) >= 2:  # !opzor nick
                nick_to_op = parts[1]
                channel = target  # Use the current channel
                if channel.startswith("#"):  # Only work in channels
                    irc.send_raw(f"MODE {channel} +o {nick_to_op}")
                    notice_message(f"Giving ops to {nick_to_op} in {channel}", irc, target)
                else:
                    notice_message("!opzor command only works in channels", irc, target)
            else:
                notice_message("Usage: !opzor <nick>", irc, target)
        elif text.startswith("!ipfs"):
            # Extracts the command and URL from the given text after the !ipfs command.
            # parts = message.split()
            # if len(parts) >= 3 and parts[1] == "!ipfs":
            # command = parts[1]
            # url = parts[2]
            # Handle the IPFS command
            handle_ipfs_command(text, irc, target)
        elif text.startswith("!get_total_counts"):
            parts = text.strip().split()
            if len(parts) >= 1:
                if len(parts) >= 2:
                    server_name = parts[1]
                else:
                    server_name = lookup(irc)
                counts = lemmat.get_total_counts(server_name)
                counts = format_counts(counts)
                notice_message(counts, irc, target)
            else:
                notice_message(
                    "⚠ Anna palvelimen nimi: !get_total_counts <server>", irc, target
                )
        elif text.startswith("!get_counts_for_source"):
            parts = text.strip().split()
            if len(parts) >= 2:
                source = parts[1]
                server_name = parts[2] if len(parts) >= 3 else lookup(irc)
                counts = lemmat.get_counts_for_source(server_name, source)
                counts = format_counts(counts)
                notice_message(counts, irc, target)
            else:
                notice_message(
                    "⚠ Käyttö: !get_counts_for_source <source> [<server>]", irc, target
                )
        elif text.startswith("!get_top_words"):
            parts = text.strip().split()
            if len(parts) >= 1:
                if len(parts) >= 2:
                    server_name = parts[1]
                else:
                    server_name = lookup(irc)
                counts = lemmat.get_top_words(server_name)
                counts = format_counts(counts)
                notice_message(counts, irc, target)
            else:
                notice_message(
                    "⚠ Anna palvelimen nimi: !get_top_words <server>", irc, target
                )
        elif text.lower().startswith("!tilaa"):
            parts = text.strip().split()
            if len(parts) >= 2:
                topic = parts[1].lower()
                if topic in ["varoitukset", "onnettomuustiedotteet"]:
                    # Tarkistetaan, onko kohde annettu (esim. #kanava)
                    if len(parts) >= 3:
                        subscriber = parts[2]  # esim. #kanava tai nick
                    else:
                        subscriber = sender  # käytä viestin lähettäjän nimeä oletuksena
                    result = subscriptions.toggle_subscription(subscriber, topic)
                    notice_message(f"{result}: {topic}", irc, target)
                else:
                    notice_message(
                        "⚠ Tuntematon tilaustyyppi. Käytä: varoitukset tai onnettomuustiedotteet",
                        irc,
                        target,
                    )
            else:
                notice_message(
                    "⚠ Anna tilaustyyppi: varoitukset tai onnettomuustiedotteet",
                    irc,
                    target,
                )

        # === NEW DRINK TRACKING COMMANDS ===
        elif text.startswith("!drinkstats"):
            # !drinkstats [nick|server|global]
            parts = text.split(" ", 1)
            server_name = data_manager.get_server_name(irc)

            if len(parts) > 1:
                arg = parts[1].strip().lower()
                if arg == "server":
                    stats = drink_tracker.get_server_stats(server_name)
                    response = f"Server {stats['server']}: {stats['total_users']} users, {stats['total_drink_words']} drink words. Top: {', '.join([f'{nick}:{count}' for nick, count in stats['top_users'][:5]])}"
                elif arg == "global":
                    stats = drink_tracker.get_global_stats()
                    top_users_text = ", ".join(
                        [
                            f"{u['nick']}@{u['server']}:{u['total']}"
                            for u in stats["top_users"][:5]
                        ]
                    )
                    response = f"Global: {stats['total_users']} users, {stats['total_drink_words']} drink words. Top: {top_users_text}"
                else:
                    # Specific nick
                    nick = parts[1].strip()
                    top_drinks = drink_tracker.get_user_top_drinks(server_name, nick, 5)
                    if top_drinks:
                        drinks_text = ", ".join(
                            [
                                f"{d['drink_word']}:{d['total']}({d['most_common_drink']})"
                                for d in top_drinks
                            ]
                        )
                        response = f"{nick}: {drinks_text}"
                    else:
                        response = f"Ei juomatilastoja käyttäjälle {nick}"
            else:
                # Show top users for current server
                stats = drink_tracker.get_server_stats(server_name)
                response = f"Top 5: {', '.join([f'{nick}:{count}' for nick, count in stats['top_users'][:5]])}"

            notice_message(response, irc, target)

        elif text.startswith("!drinkword"):
            # !drinkword <word>
            parts = text.split(" ", 1)
            if len(parts) > 1:
                drink_word = parts[1].strip()
                results = drink_tracker.search_drink_word(drink_word)
                if results["total_occurrences"] > 0:
                    top_users = results["users"][:5]
                    users_text = ", ".join(
                        [f"{u['nick']}:{u['total']}" for u in top_users]
                    )
                    response = f"'{drink_word}': {results['total_occurrences']} total. Top: {users_text}"
                else:
                    response = f"Ei löydetty juomasanaa '{drink_word}'"
            else:
                response = "Käytä: !drinkword <sana>"
            notice_message(response, irc, target)

        elif text.startswith("!drink "):
            # !drink <specific_drink>
            parts = text.split(" ", 1)
            if len(parts) > 1:
                specific_drink = parts[1].strip()
                results = drink_tracker.search_specific_drink(specific_drink)
                if results["total_occurrences"] > 0:
                    top_users = results["users"][:5]
                    users_text = ", ".join(
                        [f"{u['nick']}:{u['total']}" for u in top_users]
                    )
                    response = f"'{specific_drink}': {results['total_occurrences']} total. Top: {users_text}"
                else:
                    response = f"Ei löydetty juomaa '{specific_drink}'"
            else:
                response = "Käytä: !drink <juoma>"
            notice_message(response, irc, target)

        elif text.startswith("!drinktop"):
            # Global drink leaderboard
            stats = drink_tracker.get_global_stats()
            top_users = stats["top_users"][:10]
            if top_users:
                users_text = ", ".join(
                    [f"{u['nick']}@{u['server']}:{u['total']}" for u in top_users]
                )
                response = f"🍺 Top 10 drinkers: {users_text}"
            else:
                response = "Ei vielä juomatilastoja"
            notice_message(response, irc, target)

        elif text.startswith("!antikrak"):
            # Privacy opt-out/opt-in
            server_name = data_manager.get_server_name(irc)
            response = drink_tracker.handle_opt_out(server_name, sender)
            notice_message(response, irc, target)

        # === TAMAGOTCHI COMMANDS ===
        elif text.startswith("!tamagotchi"):
            parts = text.split(" ", 1)
            if len(parts) > 1 and parts[1].lower() == "toggle":
                # Toggle tamagotchi responses
                toggle_func = bot_functions.get("toggle_tamagotchi")
                if toggle_func:
                    # Call with required parameters: server, target, sender
                    toggle_func(irc, target, sender)
                else:
                    notice_message("Tamagotchi toggle not available.", irc, target)
            else:
                # Show tamagotchi status
                server_name = data_manager.get_server_name(irc)
                status = tamagotchi_bot.get_status(server_name)
                # Split into multiple messages if too long
                lines = status.split("\n")
                for line in lines:
                    notice_message(line, irc, target)

        elif text.startswith("!feed"):
            parts = text.split(" ", 1)
            food = parts[1] if len(parts) > 1 else None
            server_name = data_manager.get_server_name(irc)
            response = tamagotchi_bot.feed(server_name, food)
            notice_message(response, irc, target)

        elif text.startswith("!pet"):
            server_name = data_manager.get_server_name(irc)
            response = tamagotchi_bot.pet(server_name)
            notice_message(response, irc, target)

        elif text.startswith("!version"):
            notice_message(f"Bot version: {BOT_VERSION}", irc, target)

        # Admin commands requiring password
        elif text.startswith("!join "):
            if verify_admin_password(text):
                # Extract channel from command: !join password #channel [key]
                parts = text.split()
                if len(parts) >= 3:
                    channel = parts[2]
                    key = parts[3] if len(parts) > 3 else ""
                    if key:
                        irc.sendall(f"JOIN {channel} {key}\r\n".encode("utf-8"))
                        log(f"Admin joined channel {channel} with key", "INFO")
                    else:
                        irc.sendall(f"JOIN {channel}\r\n".encode("utf-8"))
                        log(f"Admin joined channel {channel}", "INFO")
                    notice_message(f"Joined {channel}", irc, target)
                else:
                    notice_message(
                        "Usage: !join <password> #channel [key]", irc, target
                    )
            else:
                notice_message("Invalid password for admin command.", irc, target)

        elif text.startswith("!part "):
            if verify_admin_password(text):
                # Extract channel from command: !part password #channel
                parts = text.split()
                if len(parts) >= 3:
                    channel = parts[2]
                    irc.sendall(f"PART {channel}\r\n".encode("utf-8"))
                    log(f"Admin left channel {channel}", "INFO")
                    notice_message(f"Left {channel}", irc, target)
                else:
                    notice_message("Usage: !part <password> #channel", irc, target)
            else:
                notice_message("Invalid password for admin command.", irc, target)

        elif text.startswith("!nick "):
            if verify_admin_password(text):
                # Extract new nickname from command: !nick password newnick
                parts = text.split()
                if len(parts) >= 3:
                    new_nick = parts[2]
                    irc.sendall(f"NICK {new_nick}\r\n".encode("utf-8"))
                    log(f"Admin changed nick to {new_nick}", "INFO")
                    notice_message(f"Changed nick to {new_nick}", irc, target)
                else:
                    notice_message(
                        "Usage: !nick <password> <new_nickname>", irc, target
                    )
            else:
                notice_message("Invalid password for admin command.", irc, target)

        elif text.startswith("!quit "):
            if verify_admin_password(text):
                # Extract quit message from command: !quit password [message]
                parts = text.split(" ", 2)
                quit_message = parts[2] if len(parts) > 2 else "Admin quit"
                irc.sendall(f"QUIT :{quit_message}\r\n".encode("utf-8"))
                log(f"Admin quit with message: {quit_message}", "INFO")
            else:
                notice_message("Invalid password for admin command.", irc, target)

        elif text.startswith("!raw "):
            if verify_admin_password(text):
                # Extract raw IRC command: !raw password COMMAND
                parts = text.split(" ", 2)
                if len(parts) >= 3:
                    raw_command = parts[2]
                    irc.sendall(f"{raw_command}\r\n".encode("utf-8"))
                    log(f"Admin sent raw command: {raw_command}", "INFO")
                    notice_message(f"Sent: {raw_command}", irc, target)
                else:
                    notice_message("Usage: !raw <password> <IRC_COMMAND>", irc, target)
            else:
                notice_message("Invalid password for admin command.", irc, target)

        elif "säätänää" in text:
            # elif text.startswith("Onks siel millane säätänää?"):
            print(sender)
            match = re.match(r"~?([^@]+)@", sender)
            if target == bot_name:
                target = sender
            if match:
                username = match.group(1)
                notice_message(
                    "https://img-9gag-fun.9cache.com/photo/aqGwo2R_700bwp.webp",
                    irc,
                    target,
                )
        else:
            # ✅ Handle regular chat messages (send to GPT)
            # ✅ Only respond to private messages or messages mentioning the bot's name exactly
            if is_private or re.match(
                rf"^{re.escape(bot_name)}[ ,.:;]", text
            ):  # Only respond when the message begins with the bot's name
                response = chat_with_gpt(text)  # Get response from GPT
                reply_target = (
                    sender if is_private else target
                )  # Send private replies to sender
                # Split the response into parts if it's too long
                response_parts = wrap_irc_message_utf8_bytes(
                    response, reply_target=reply_target, max_lines=5, placeholder="..."
                )
                # Send each response part separately as max length IRC messages
                for part in response_parts:
                    send_message(irc, reply_target, part)
                log(
                    f"\U0001f4ac Sent AI response to {reply_target}: {response_parts}",
                    "MSG",
                )

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
