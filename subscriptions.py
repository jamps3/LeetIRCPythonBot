import json
import os
import shutil
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

SUBSCRIBERS_FILE = "subscriptions.json"

# Valid topics for subscriptions
VALID_TOPICS = {"varoitukset", "onnettomuustiedotteet"}


def is_valid_nick_or_channel(nick: str) -> bool:
    """Validate IRC nick or channel name."""
    if not nick or len(nick) > 30:  # IRC spec limit
        return False

    # Channel names start with #
    if nick.startswith("#"):
        if len(nick) < 2:  # Must have at least one character after #
            return False
        # Channel names can't contain spaces, commas, or control characters
        invalid_chars = {" ", ",", "\x07", "\r", "\n", "\0"}
        return not any(char in invalid_chars for char in nick)

    # Nick names validation
    if nick.startswith("#"):  # This check is redundant but kept for clarity
        return False

    # First character must be letter or special char (not digit)
    if nick[0].isdigit():
        return False

    # Valid characters for nicks
    valid_chars = set(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789[]\\`_^{|}-"
    )
    return all(char in valid_chars for char in nick)


def validate_and_clean_data(data: Any) -> Dict[str, Dict[str, List[str]]]:
    """Validate and clean subscription data, removing invalid entries.

    Expected format:
    {
        "server1": {
            "nick1": ["topic1", "topic2"],
            "#channel1": ["topic1"]
        },
        "server2": {
            "nick2": ["topic1"]
        }
    }
    """
    if not isinstance(data, dict):
        return {}

    cleaned_data = {}

    for server_name, server_data in data.items():
        if not isinstance(server_name, str) or not server_name:
            continue

        if not isinstance(server_data, dict):
            continue

        cleaned_server_data = {}

        for nick, topics in server_data.items():
            # Validate nick/channel
            if not isinstance(nick, str) or not is_valid_nick_or_channel(nick):
                continue

            # Validate topics
            if not isinstance(topics, list):
                continue

            cleaned_topics = []
            for topic in topics:
                if isinstance(topic, str) and topic in VALID_TOPICS:
                    cleaned_topics.append(topic)

            # Only keep nick if it has valid topics
            if cleaned_topics:
                cleaned_server_data[nick] = cleaned_topics

        # Only keep server if it has valid nicks
        if cleaned_server_data:
            cleaned_data[server_name] = cleaned_server_data

    return cleaned_data


def load_subscriptions() -> Dict[str, Dict[str, List[str]]]:
    """Load subscriptions from file with error handling and validation."""
    if not os.path.exists(SUBSCRIBERS_FILE):
        return {}

    try:
        with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Validate and clean the data
        cleaned_data = validate_and_clean_data(data)

        # If data was corrupted and cleaned, save the cleaned version
        if cleaned_data != data:
            save_subscriptions(cleaned_data)

        return cleaned_data

    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {SUBSCRIBERS_FILE}: {e}")
        # Create backup of corrupted file
        backup_path = (
            f"{SUBSCRIBERS_FILE}.corrupted.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        try:
            shutil.copy2(SUBSCRIBERS_FILE, backup_path)
            print(f"Corrupted file backed up to {backup_path}")
        except Exception as backup_error:
            print(f"Could not create backup: {backup_error}")

        # Return empty dict and let save_subscriptions recreate the file
        return {}

    except Exception as e:
        print(f"Unexpected error loading {SUBSCRIBERS_FILE}: {e}")
        return {}


def save_subscriptions(data: Dict[str, Dict[str, List[str]]]) -> bool:
    """Save subscriptions to file with error handling and atomic writes."""
    try:
        # Validate data before saving
        cleaned_data = validate_and_clean_data(data)

        # Create backup if file exists
        if os.path.exists(SUBSCRIBERS_FILE):
            backup_path = f"{SUBSCRIBERS_FILE}.backup"
            try:
                shutil.copy2(SUBSCRIBERS_FILE, backup_path)
            except Exception as backup_error:
                print(f"Warning: Could not create backup: {backup_error}")

        # Write to temporary file first for atomic operation
        temp_file = f"{SUBSCRIBERS_FILE}.tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(cleaned_data, f, ensure_ascii=False, indent=2)

        # Atomic rename
        os.replace(temp_file, SUBSCRIBERS_FILE)
        return True

    except Exception as e:
        print(f"Error saving subscriptions: {e}")
        # Clean up temp file if it exists
        temp_file = f"{SUBSCRIBERS_FILE}.tmp"
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except Exception:
                pass
        return False


def toggle_subscription(nick: str, server: str, topic: str) -> str:
    """Toggle subscription for a nick/channel on a specific server."""
    if topic not in VALID_TOPICS:
        return f"❌ Invalid topic: {topic}. Valid topics are: {', '.join(VALID_TOPICS)}"

    if not is_valid_nick_or_channel(nick):
        return f"❌ Invalid nick/channel: {nick}"

    data = load_subscriptions()

    if server not in data:
        data[server] = {}

    if nick not in data[server]:
        data[server][nick] = []

    if topic in data[server][nick]:
        data[server][nick].remove(topic)
        action = "❌ Poistettu tilaus"
    else:
        data[server][nick].append(topic)
        action = "✅ Tilaus lisätty"

    # Clean up empty entries
    if not data[server][nick]:
        del data[server][nick]

    if not data[server]:
        del data[server]

    if save_subscriptions(data):
        return f"{action}: {nick} on network {server} for {topic}"
    else:
        return "❌ Error saving subscription."


def get_subscribers(topic: str) -> List[Tuple[str, str]]:
    """Get all subscribers for a topic.

    Returns:
        List of (nick, server) tuples subscribed to the topic
    """
    data = load_subscriptions()
    subscribers = []

    for server_name, server_data in data.items():
        for nick, topics in server_data.items():
            if topic in topics:
                subscribers.append((nick, server_name))

    return subscribers


def get_server_subscribers(topic: str, server: str) -> List[str]:
    """Get subscribers for a topic on a specific server.

    Returns:
        List of nicks/channels subscribed to the topic on the server
    """
    data = load_subscriptions()

    if server not in data:
        return []

    return [nick for nick, topics in data[server].items() if topic in topics]


def get_user_subscriptions(nick: str, server: str) -> List[str]:
    """Get all subscriptions for a specific user on a server.

    Returns:
        List of topics the user is subscribed to
    """
    data = load_subscriptions()

    if server not in data or nick not in data[server]:
        return []

    return data[server][nick].copy()


def format_user_subscriptions(nick: str, server: str) -> str:
    """Format user subscriptions for display.

    Returns:
        Formatted string showing user's current subscriptions
    """
    subscriptions = get_user_subscriptions(nick, server)

    if not subscriptions:
        return (
            f"📋 {nick} ei ole tilannut mitään varoituksia tai onnettomuustiedotteita."
        )

    subscriptions_text = ", ".join(subscriptions)
    return f"📋 {nick} on tilannut: {subscriptions_text}"


def get_all_subscriptions() -> Dict[str, Dict[str, List[str]]]:
    """Get all subscriptions across all servers.

    Returns:
        Dictionary with server -> {nick: [topics]} structure
    """
    return load_subscriptions()


def format_all_subscriptions() -> str:
    """Format all subscriptions for display.

    Returns:
        Formatted string showing all subscriptions across all servers
    """
    data = get_all_subscriptions()

    if not data:
        return "📋 Ei tilauksia tallennettuna."

    lines = ["📋 Kaikki tilaukset:"]

    for server_name, server_data in data.items():
        if server_data:
            lines.append(f"  🌐 {server_name}:")
            for nick, topics in server_data.items():
                topics_text = ", ".join(topics)
                lines.append(f"    • {nick}: {topics_text}")

    return "\n".join(lines)


def format_server_subscriptions(server: str) -> str:
    """Format all subscriptions for a specific server.

    Returns:
        Formatted string showing all subscriptions for the server
    """
    data = load_subscriptions()

    if server not in data or not data[server]:
        return f"📋 Ei tilauksia palvelimella {server}."

    lines = [f"📋 Tilaukset palvelimella {server}:"]

    for nick, topics in data[server].items():
        topics_text = ", ".join(topics)
        lines.append(f"  • {nick}: {topics_text}")

    return "\n".join(lines)


def format_channel_subscriptions(channel: str, server: str) -> str:
    """Format subscriptions for a specific channel.

    Returns:
        Formatted string showing subscriptions for the channel
    """
    subscriptions = get_user_subscriptions(channel, server)

    if not subscriptions:
        return f"📋 Kanava {channel} ei ole tilannut mitään varoituksia tai onnettomuustiedotteita."

    subscriptions_text = ", ".join(subscriptions)
    return f"📋 Kanava {channel} on tilannut: {subscriptions_text}"
