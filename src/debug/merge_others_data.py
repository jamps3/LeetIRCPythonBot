"""
Merge scraped nameday data with existing nimipaivat_others.json
Usage: python merge_others_data.py

The scraped data has format:
{
  "2026-01-02": {
    "swedish": [...],
    "sami": [...],
    "orthodox": [...]
  }
}

The existing file has format:
{
  "hevonen": {"2026-01-02": [...]},
  "historiallinen": {"2026-01-02": [...]}
}

This script converts and merges properly.
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

    # Load temp data
    if not os.path.exists(temp_file):
        print(f"ERROR: Temp file not found: {temp_file}")
        sys.exit(1)

    with open(temp_file, "r", encoding="utf-8") as f:
        temp_data = json.load(f)

    print(f"\nTemp data has {len(temp_data)} days")
    print(
        f"Temp data categories in first entry: {list(list(temp_data.values())[0].keys()) if temp_data else 'none'}"
    )

    # Convert temp data format to match existing format
    # Temp: {"2026-01-02": {"swedish": [...], "sami": [...], "orthodox": [...]}}
    # Target: {"ruotsi": {"2026-01-02": [...]}, "saame": {"2026-01-02": [...]}, "ortod": {"2026-01-02": [...]}}

    converted = {"ruotsi": {}, "saame": {}, "ortod": {}}  # Swedish  # Sami  # Orthodox

    for date_key, categories in temp_data.items():
        if "swedish" in categories and categories["swedish"]:
            converted["ruotsi"][date_key] = categories["swedish"]
        if "sami" in categories and categories["sami"]:
            converted["saame"][date_key] = categories["sami"]
        if "orthodox" in categories and categories["orthodox"]:
            converted["ortod"][date_key] = categories["orthodox"]

    print(f"\nConverted data:")
    for cat, days in converted.items():
        print(f"  {cat}: {len(days)} days")

    # Merge with existing
    for category, days in converted.items():
        if category not in existing:
            existing[category] = {}
        for date_key, names in days.items():
            existing[category][date_key] = names

    # Save
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    print(f"\nMerged data saved to: {output_file}")
    print(f"Final categories: {list(existing.keys())}")

    # Summary
    for cat, days in existing.items():
        print(f"  {cat}: {len(days)} days")


if __name__ == "__main__":
    merge_data()
