#!/usr/bin/env python3
"""
Migration script to move subscriptions from subscriptions.json to state.json
"""

import json
import os
import shutil
from datetime import datetime


def migrate_subscriptions():
    """Migrate subscriptions from subscriptions.json to state.json"""

    subscriptions_file = "subscriptions.json"
    state_file = "state.json"

    # Check if subscriptions.json exists
    if not os.path.exists(subscriptions_file):
        print("No subscriptions.json file found - nothing to migrate")
        return

    # Load existing subscriptions
    try:
        with open(subscriptions_file, "r", encoding="utf-8") as f:
            subscriptions_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error reading subscriptions.json: {e}")
        return

    print(f"Found subscriptions data: {subscriptions_data}")

    # Load existing state.json or create empty dict
    state_data = {}
    if os.path.exists(state_file):
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                state_data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Warning: Could not read state.json: {e}")
            # Backup corrupted state.json
            backup_name = (
                f"state.json.corrupted.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            shutil.copy2(state_file, backup_name)
            print(f"Backed up corrupted state.json to {backup_name}")

    # Add subscriptions to state data
    state_data["subscriptions"] = subscriptions_data

    # Backup original state.json
    if os.path.exists(state_file):
        backup_name = f"state.json.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(state_file, backup_name)
        print(f"Backed up original state.json to {backup_name}")

    # Write updated state.json
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state_data, f, ensure_ascii=False, indent=2)

    print("Migrated subscriptions to state.json")

    # Backup subscriptions.json
    backup_subs = (
        f"subscriptions.json.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    shutil.copy2(subscriptions_file, backup_subs)
    print(f"Backed up subscriptions.json to {backup_subs}")

    # Remove old subscriptions.json
    os.remove(subscriptions_file)
    print("Removed old subscriptions.json file")


if __name__ == "__main__":
    migrate_subscriptions()
