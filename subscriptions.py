import json
import os

SUBSCRIBERS_FILE = "subscriptions.json"


def load_subscriptions():
    if os.path.exists(SUBSCRIBERS_FILE):
        with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_subscriptions(data):
    with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def toggle_subscription(nick, topic):
    data = load_subscriptions()
    if nick not in data:
        data[nick] = []

    if topic in data[nick]:
        data[nick].remove(topic)
        action = "❌ Poistettu tilaus"
    else:
        data[nick].append(topic)
        action = "✅ Tilaus lisätty"

    if not data[nick]:
        del data[nick]  # poista tyhjät tilaukset

    save_subscriptions(data)
    return action


def get_subscribers(topic):
    data = load_subscriptions()
    return [nick for nick, topics in data.items() if topic in topics]
