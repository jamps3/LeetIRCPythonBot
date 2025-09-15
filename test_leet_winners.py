#!/usr/bin/env python3
"""
Test script to verify leet winners processing functionality
"""

import json
import os
import re
import sys

# Test data from your examples
test_messages = [
    'Beici!~vekotin@heiki.1337.cx NOTICE #joensuu :Ensimmäinen leettaaja oli Ekaleet kello 13.37.00,218154740 ("leet"), viimeinen oli Vikaleet kello 13.37.56,267236192 ("leet"). Lähimpänä multileettiä oli Multileet kello 13.37.13,269664703 ("leet").',
    'Beibi!~vekotin@heiki.1337.cx NOTICE #joensuu :Ensimmäinen leettaaja oli  kello 13.37.00,212268597 ("leet"), viimeinen oli Vikaleet kello 13.37.59,839985573 ("leet"). Lähimpänä multileettiä oli Multileet kello 13.37.13,263745320 ("leet").',
    'Beiki!~vekotin@heiki.1337.cx NOTICE #joensuu :Ensimmäinen leettaaja oli jamps kello 13.37.00,218614708 ("leet"), viimeinen oli Vikaleet kello 13.37.56,423323747 ("leet"). Lähimpänä multileettiä oli Multileet kello 13.37.13,278570137 ("leet").',
]


def load_leet_winners():
    """Load leet winners data."""
    try:
        with open("leet_winners.json", "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_leet_winners(data):
    """Save leet winners data."""
    try:
        with open("leet_winners.json", "w") as f:
            json.dump(data, f, indent=2)
        print("✅ Successfully saved data to leet_winners.json")
        return True
    except Exception as e:
        print(f"❌ Error saving leet winners: {e}")
        return False


def process_leet_winner_summary(text: str):
    """Parser for leet winners summary lines."""
    # Regex pattern for detection
    pattern = r"Ensimmäinen leettaaja oli (\S+) .*?, viimeinen oli (\S+) .*?Lähimpänä multileettiä oli (\S+)"
    match = re.search(pattern, text)
    if not match:
        return False

    first, last, multileet = match.groups()
    print(f"🎯 Regex matched: first={first}, last={last}, multileet={multileet}")

    # Load current winners
    winners = load_leet_winners()
    print(f"📁 Loaded current winners: {winners}")

    # Helper to bump count in winners dict
    def bump(name: str, category: str):
        if not name:
            return
        if name in winners:
            winners[name][category] = winners[name].get(category, 0) + 1
        else:
            winners[name] = {category: 1}

    bump(first, "first")
    bump(last, "last")
    bump(multileet, "multileet")

    print(f"📊 Updated winners: {winners}")

    if save_leet_winners(winners):
        print(
            f"✅ Updated leet winners (first={first}, last={last}, multileet={multileet})"
        )
        return True
    else:
        print("❌ Failed to save leet winners")
        return False


def main():
    print("🧪 Testing leet winners processing...")
    print("=" * 60)

    # Show current working directory
    print(f"📂 Working directory: {os.getcwd()}")

    # Check if file exists before testing
    if os.path.exists("leet_winners.json"):
        print("📄 leet_winners.json exists, showing current content:")
        try:
            with open("leet_winners.json", "r") as f:
                current_data = json.load(f)
                print(json.dumps(current_data, indent=2))
        except Exception as e:
            print(f"❌ Error reading file: {e}")
    else:
        print("📄 leet_winners.json does not exist, will be created")

    print("\n🔄 Processing test messages...")
    print("-" * 40)

    success_count = 0
    for i, message in enumerate(test_messages, 1):
        print(f"\n📝 Message {i}:")
        print(f"Text: {message}")

        if process_leet_winner_summary(message):
            success_count += 1
            print("✅ Successfully processed")
        else:
            print("❌ Failed to process")

    print("\n" + "=" * 60)
    print(
        f"📊 Summary: {success_count}/{len(test_messages)} messages processed successfully"
    )

    # Show final file content
    if os.path.exists("leet_winners.json"):
        print("\n📄 Final leet_winners.json content:")
        try:
            with open("leet_winners.json", "r") as f:
                final_data = json.load(f)
                print(json.dumps(final_data, indent=2))
        except Exception as e:
            print(f"❌ Error reading final file: {e}")
    else:
        print("❌ leet_winners.json was not created")


if __name__ == "__main__":
    main()
