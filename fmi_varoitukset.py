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
    "itämeren",
    "kainuu",
    "keski-",
    "keskiosa",
    "keski-lappi",
    "länsi-lappi",
    "maan länsiosa",
    "maan eteläosa",
    "maan pohjoisosa",
    "pohjois-pohjanmaa",
    "pohjanmaa",
    "merelle",
    "suomenlahden",
]

# Alueet, joita halutaan seurata (jos tyhjä, kaikki kelpaavat)
ALLOWED_LOCATIONS = [
    "joensuu",
    "itä-suomi",
    "pohjois-karjala",
    "itä-",
    "koko maa",
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
        title = entry.get("title", "")
        summary = entry.get("summary", "")[:100]
        cleaned = " ".join((title + summary).split())
        return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()

    def load_seen_hashes(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    return set(json.load(f).get("seen_hashes", []))
            except (json.JSONDecodeError, ValueError):
                print("⚠ Varoitus: JSON-tiedosto vioittunut, nollataan tila.")
        return set()

    def save_seen_hashes(self, hashes):
        with open(self.state_file, "w") as f:
            json.dump({"seen_hashes": list(hashes)}, f)

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
        seen_hashes = self.load_seen_hashes()

        new_entries = []
        for entry in feed.entries:
            entry_hash = self.get_hash(entry)
            if entry_hash in seen_hashes:
                continue
            new_entries.append((entry_hash, entry))

        if new_entries:
            messages = []
            for entry_hash, entry in reversed(new_entries):
                title = "⚠ " + entry.title
                summary = entry.summary
                lower_title = title.lower()
                lower_summary = summary.lower()

                # Blacklist-suodatus
                if any(bl in lower_title for bl in EXCLUDED_LOCATIONS):
                    continue

                # Whitelist-suodatus
                if ALLOWED_LOCATIONS and not any(
                    wl in lower_title for wl in ALLOWED_LOCATIONS
                ):
                    continue

                # Värisymbolit
                title = title.replace("Punainen ", "🟥")
                title = title.replace("Oranssi ", "🟠")
                title = title.replace("Keltainen ", "🟡")
                title = title.replace("Vihreä ", "🟢")

                # Varoitustyyppien symbolit
                if "tuulivaroitus" in lower_title or "tuulivaroitus" in lower_summary:
                    title = title.replace("tuulivaroitus", "🌪️")
                elif (
                    "maastopalovaroitus" in lower_title
                    or "maastopalovaroitus" in lower_summary
                ):
                    title = title.replace("maastopalovaroitus", "♨ ")
                elif "liikennesää" in lower_title or "liikennesää" in lower_summary:
                    title = title.replace("liikennesää", "🚗 ")
                elif (
                    "aallokkovaroitus" in lower_title
                    or "aallokkovaroitus" in lower_summary
                ):
                    title = title.replace("aallokkovaroitus", "🌊 ")
                title = title.replace(" maa-alueille:", "")
                title = title.replace("  ", " ")
                title = title.replace(": Paikoin", "Paikoin")
                msg = f"{title} | {summary} ⚠"
                messages.append(msg)

                seen_hashes.add(entry_hash)

            # Rajataan muistiin jäävät hashit esim. 50 uusimpaan
            seen_hashes = set(list(seen_hashes)[-50:])
            self.save_seen_hashes(seen_hashes)

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
