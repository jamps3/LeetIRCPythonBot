import feedparser
import hashlib
import json
import os
import threading
import time

FEED_URL = "https://alerts.fmi.fi/cap/feed/rss_fi-FI.rss"
STATE_FILE = "last_warning.json"
CHECK_INTERVAL = 300  # sekunteina
# Version 1.0

# Alueet, jotka halutaan sulkea pois
EXCLUDED_LOCATIONS = [
    "ahvenanmaa",
    "etelä-pohjanmaa",
    "länsi-lappi",
    "maan länsiosa",
    "maan eteläosa",
    "maan pohjoisosa",
    "pohjois-pohjanmaa",
    "pohjanmaa",
]

# Alueet, joita halutaan seurata (jos tyhjä, kaikki kelpaavat)
ALLOWED_LOCATIONS = [
    "joensuu",
    "itä-suomi",
    "pohjois-karjala",
    "itä-",
    "itäosa",
    "keski-",
    "keskiosa",
    "koko maa",
    "kainuu",
]


class FMIWatcher:
    def __init__(self, callback, state_file=STATE_FILE, interval=CHECK_INTERVAL):
        self.callback = callback
        self.state_file = state_file
        self.interval = interval
        self.thread = threading.Thread(target=self.run_loop, daemon=True)
        self.running = False

    def start(self):
        self.running = True
        print("✅ FMI-varoitusvahti käynnistetty (taustasäie)")
        self.thread.start()

    def stop(self):
        self.running = False

    def run_loop(self):
        while self.running:
            try:
                new_warnings = self.check_new_warnings()
                if new_warnings:
                    self.callback(new_warnings)
            except Exception as e:
                print(f"⚠ Virhe tarkistuksessa: {e}")
            time.sleep(self.interval)

    def get_hash(self, entry):
        key = entry.get("title", "") + entry.get("published", "")
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def load_last_hash(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    return json.load(f).get("last_hash")
            except (json.JSONDecodeError, ValueError):
                print("⚠ Varoitus: JSON-tiedosto vioittunut, nollataan tila.")
        return None

    def save_last_hash(self, hash_val):
        with open(self.state_file, "w") as f:
            json.dump({"last_hash": hash_val}, f)

    def check_new_warnings(self):
        feed = feedparser.parse(FEED_URL)
        last_hash = self.load_last_hash()

        new_entries = []
        for entry in feed.entries:
            entry_hash = self.get_hash(entry)
            if entry_hash == last_hash:
                break
            new_entries.append((entry_hash, entry))

        if new_entries:
            self.save_last_hash(new_entries[0][0])
            messages = []
            for _, entry in reversed(new_entries):
                title = "⚠ " + entry.title
                summary = entry.summary
                lower_title = title.lower()
                lower_summary = summary.lower()

                # Blacklist-suodatus
                if any(bl in lower_title for bl in EXCLUDED_LOCATIONS):
                    continue

                # Whitelist-suodatus (jos määritelty)
                if ALLOWED_LOCATIONS and not any(
                    wl in lower_title for wl in ALLOWED_LOCATIONS
                ):
                    continue

                # Värisymbolit
                title = title.replace("Punainen", "🟥")
                title = title.replace("Oranssi", "🟠")
                title = title.replace("Keltainen", "🟡")
                title = title.replace("Vihreä", "🟢")

                # Varoitustyyppien symbolit
                if "tuulivaroitus" in lower_title or "tuulivaroitus" in lower_summary:
                    title = title.replace("tuulivaroitus", "🌪️ Tuulivaroitus")
                elif (
                    "maastopalovaroitus" in lower_title
                    or "maastopalovaroitus" in lower_summary
                ):
                    title = title.replace("maastopalovaroitus", "♨ Maastopalovaroitus")
                elif "liikennesää" in lower_title or "liikennesää" in lower_summary:
                    title = title.replace("liikennesää", "🚗 Liikennesää")
                elif (
                    "aallokkovaroitus" in lower_title
                    or "aallokkovaroitus" in lower_summary
                ):
                    title = title.replace("aallokkovaroitus", "🌊 Aallokkovaroitus")

                msg = f"{title} | {summary}"
                messages.append(msg)

            return messages
        return []


# -------------------------------
# Main-funktio testaukseen
# -------------------------------


def print_to_console(messages):
    for msg in messages:
        print("------------------------------------------------------------")
        print(msg)


def main():
    print("🛰️  Käynnistetään FMIWatcher testitilassa (console output)...")
    watcher = FMIWatcher(
        callback=print_to_console, interval=60  # testikäyttöön lyhyempi väli
    )
    watcher.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Lopetetaan...")
        watcher.stop()


if __name__ == "__main__":
    main()
