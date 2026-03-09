"""
Merge scraped nameday data with existing nimipaivat_others.json
Usage: python merge_others_data.py

Can also be used to just sort the existing file.
"""

import json
import os
import sys

# Get project root
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if os.path.basename(project_root) == "src":
    project_root = os.path.dirname(project_root)
data_dir = os.path.join(project_root, "data")

temp_file = os.path.join(data_dir, "nimipaivat_others_temp.json")
output_file = os.path.join(data_dir, "nimipaivat_others.json")


def merge_data():
    # Load existing data
    existing = {}
    if os.path.exists(output_file):
        with open(output_file, "r", encoding="utf-8") as f:
            existing = json.load(f)
        print(f"Loaded existing data from: {output_file}")
        print(f"Existing categories: {list(existing.keys())}")
    else:
        print("No existing file found, starting fresh")
        return

    # Try to load temp data if it exists
    temp_data = None
    if os.path.exists(temp_file):
        with open(temp_file, "r", encoding="utf-8") as f:
            temp_data = json.load(f)
        print(f"\nTemp data has {len(temp_data)} days")
        print(
            f"Temp data categories in first entry: {list(list(temp_data.values())[0].keys()) if temp_data else 'none'}"
        )

        # Convert temp data format to match existing format
        # Temp: {"2026-01-02": {"swedish": [...], "sami": [...], "orthodox": [...]}}
        # Target: {"ruotsi": {"2026-01-02": [...]}, "saame": {"2026-01-02": [...]}, "ortodoksi": {"2026-01-02": [...]}}

        converted = {
            "ruotsi": {},
            "saame": {},
            "ortodoksi": {},
        }  # Swedish # Sami # Orthodox

        for date_key, categories in temp_data.items():
            if "swedish" in categories and categories["swedish"]:
                converted["ruotsi"][date_key] = categories["swedish"]
            if "sami" in categories and categories["sami"]:
                converted["saame"][date_key] = categories["sami"]
            if "orthodox" in categories and categories["orthodox"]:
                converted["ortodoksi"][date_key] = categories["orthodox"]

        print(f"\nConverted data:")
        for cat, days in converted.items():
            print(f"  {cat}: {len(days)} days")

        # Merge with existing - also handle renaming ortod to ortodoksi
        # First, rename ortod to ortodoksi if it exists
        if "ortod" in existing:
            existing["ortodoksi"] = existing.pop("ortod")

        for category, days in converted.items():
            if category not in existing:
                existing[category] = {}
            for date_key, names in days.items():
                existing[category][date_key] = names
    else:
        # Just sort existing data - rename ortod to ortodoksi if needed
        if "ortod" in existing:
            existing["ortodoksi"] = existing.pop("ortod")
        print("\nNo temp file - just sorting existing data")

    # Save - sort categories in specific order
    category_order = ["ruotsi", "saame", "ortodoksi", "historiallinen", "hevonen"]

    # Reorder existing dict by category_order
    sorted_existing = {}
    for cat in category_order:
        if cat in existing:
            sorted_existing[cat] = existing[cat]
    # Add any remaining categories not in the order list
    for cat in existing:
        if cat not in sorted_existing:
            sorted_existing[cat] = existing[cat]

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(sorted_existing, f, ensure_ascii=False, indent=2)

    print(f"\nMerged data saved to: {output_file}")
    print(f"Final categories: {list(sorted_existing.keys())}")

    # Summary
    for cat, days in sorted_existing.items():
        print(f"  {cat}: {len(days)} days")


if __name__ == "__main__":
    merge_data()
