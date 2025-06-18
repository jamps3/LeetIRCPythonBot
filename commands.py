"""
IRC Command Processing Module

This module contains the main command processing functions extracted from main.py
for better code organization and maintainability.
"""

import re
import time
import json
import platform
import requests
import xml.etree.ElementTree as ElementTree
from datetime import datetime
from collections import Counter


def process_message(irc, message, bot_functions):
    """Processes incoming IRC messages and tracks word statistics."""
    # Extract all needed functions and variables from bot_functions dict
    tamagotchi = bot_functions['tamagotchi']
    count_kraks = bot_functions['count_kraks']
    notice_message = bot_functions['notice_message']
    send_electricity_price = bot_functions['send_electricity_price']
    measure_latency = bot_functions['measure_latency']
    get_crypto_price = bot_functions['get_crypto_price']
    load_leet_winners = bot_functions['load_leet_winners']
    save_leet_winners = bot_functions['save_leet_winners']
    send_weather = bot_functions['send_weather']
    send_scheduled_message = bot_functions['send_scheduled_message']
    get_eurojackpot_numbers = bot_functions['get_eurojackpot_numbers']
    search_youtube = bot_functions['search_youtube']
    handle_ipfs_command = bot_functions['handle_ipfs_command']
    lookup = bot_functions['lookup']
    format_counts = bot_functions['format_counts']
    chat_with_gpt = bot_functions['chat_with_gpt']
    wrap_irc_message_utf8_bytes = bot_functions['wrap_irc_message_utf8_bytes']
    send_message = bot_functions['send_message']
    load = bot_functions['load']
    save = bot_functions['save']
    update_kraks = bot_functions['update_kraks']
    log = bot_functions['log']
    fetch_title = bot_functions['fetch_title']
    lemmat = bot_functions['lemmat']
    subscriptions = bot_functions['subscriptions']
    DRINK_WORDS = bot_functions['DRINK_WORDS']
    EKAVIKA_FILE = bot_functions['EKAVIKA_FILE']
    bot_name = bot_functions['bot_name']
    get_latency_start = bot_functions['latency_start']
    set_latency_start = bot_functions['set_latency_start']
    is_private = False
    match = re.search(r":(\S+)!(\S+) PRIVMSG (\S+) :(.+)", message)

    if match:
        sender, _, target, text = match.groups()

        # Process each message and count words, except lines starting with !
        if not text.startswith("!"):
            tamagotchi(text, irc, target)

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
                irc.send(f"MODE {parts[2]} +o {parts[4]}\r\n".encode("utf-8"))
                # notice_message(f"MODE {parts[2]} +o {parts[4]}", irc)
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

