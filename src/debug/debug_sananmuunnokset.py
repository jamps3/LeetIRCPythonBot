#!/usr/bin/env python3
"""
Script to fix incorrect transformations in sananmuunnokset.json
"""

import json
import os
import random
import sys

# Import the functions used by the !muunnos command
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from commands import _find_first_syllable, transform_phrase  # noqa: E402


def main():
    """Main function with different modes based on arguments."""
    if len(sys.argv) > 1:
        if sys.argv[1] == "ask":
            # Interactive mode: ask user to verify transformations
            ask_mode()
        elif sys.argv[1] == "test":
            # Test mode: show random phrases with transformations
            if len(sys.argv) > 2 and sys.argv[2] == "singles":
                test_singles_mode()
            else:
                test_mode()
        else:
            print(f"Unknown mode: {sys.argv[1]}")
            print("Usage: python fix_sananmuunnokset.py [ask|test [singles]]")
            sys.exit(1)
    else:
        # Default mode: fix all transformations automatically
        fix_all_mode()


def ask_mode():
    """Interactive mode to verify and fix transformations."""
    json_path = os.path.join("data", "sananmuunnokset.json")

    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found")
        sys.exit(1)

    # Read current JSON
    with open(json_path, "r", encoding="utf-8") as f:
        transformations = json.load(f)

    print("Interactive verification mode: Enter phrases to check (type 'x' to exit)")
    print("=" * 70)

    updated_count = 0
    checked_count = 0

    while True:
        phrase = input("\nEnter a phrase to check (or 'x' to exit): ").strip()

        if phrase.lower() == "x":
            break

        if not phrase:
            continue

        checked_count += 1

        if phrase in transformations:
            current_transform = transformations[phrase]
            correct_transform = transform_phrase(phrase)

            print(f"Phrase: '{phrase}'")
            print(f"Current transformation: '{current_transform}'")
            print(f"Suggested transformation: '{correct_transform}'")

            custom = input(
                "Enter the correct transformation (or press Enter to keep current): "
            ).strip()
            if custom and custom != current_transform:
                transformations[phrase] = custom
                updated_count += 1
                print(f"✓ Updated: '{current_transform}' → '{custom}'")
            else:
                print("✓ Kept current transformation")
        else:
            # New phrase, add it
            correct_transform = transform_phrase(phrase)
            print(f"New phrase: '{phrase}'")
            print(f"Suggested transformation: '{correct_transform}'")

            custom = input(
                "Enter the correct transformation (or press Enter to use suggested): "
            ).strip()
            if custom:
                transformations[phrase] = custom
                updated_count += 1
                print(f"✓ Added: '{phrase}' → '{custom}'")
            elif correct_transform:
                transformations[phrase] = correct_transform
                updated_count += 1
                print(f"✓ Added: '{phrase}' → '{correct_transform}'")
            else:
                print("✗ Skipped: no transformation provided")

    # Write back the updated JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(transformations, f, ensure_ascii=False, indent=4)

    print(f"\n{'=' * 70}")
    print(f"Results: Checked {checked_count} phrases, updated {updated_count}")
    print(f"Saved changes to {json_path}")


def test_mode():
    """Test mode: interactively check random phrases with y/n verification."""
    json_path = os.path.join("data", "sananmuunnokset.json")

    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found")
        sys.exit(1)

    # Read current JSON
    with open(json_path, "r", encoding="utf-8") as f:
        transformations = json.load(f)

    if len(transformations) < 5:
        print("Error: Need at least 5 transformations for test mode")
        sys.exit(1)

    # Select 5 random phrases
    selected_phrases = random.sample(list(transformations.keys()), 5)

    print("Test mode: Checking 5 random transformations interactively")
    print("=" * 60)

    updated_count = 0

    for i, phrase in enumerate(selected_phrases, 1):
        current_transform = transformations[phrase]
        suggested_transform = transform_phrase(phrase)

        print(f"\n{i}/5: Phrase: '{phrase}'")
        print(f"Current transformation: '{current_transform}'")
        print(f"Suggested transformation: '{suggested_transform}'")

        while True:
            response = (
                input("Does the suggested transformation match? (y/n): ")
                .strip()
                .lower()
            )
            if response in ["y", "yes"]:
                if current_transform != suggested_transform:
                    transformations[phrase] = suggested_transform
                    updated_count += 1
                    print(f"✓ Updated: '{current_transform}' → '{suggested_transform}'")
                else:
                    print("✓ Already correct")
                break
            elif response in ["n", "no"]:
                custom = input("Enter the correct transformation: ").strip()
                if custom and custom != current_transform:
                    transformations[phrase] = custom
                    updated_count += 1
                    print(f"✓ Updated: '{current_transform}' → '{custom}'")
                else:
                    print("✓ Kept current transformation")
                break
            else:
                print("Please answer 'y' or 'n'")

    # Write back the updated JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(transformations, f, ensure_ascii=False, indent=4)

    print(f"\n{'=' * 60}")
    print(f"Test Results: Updated {updated_count} out of 5 transformations")
    print(f"Saved changes to {json_path}")


def test_singles_mode():
    """Test mode: interactively check random single-word transformations with y/n verification."""
    json_path = os.path.join("data", "sananmuunnokset.json")

    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found")
        sys.exit(1)

    # Read current JSON
    with open(json_path, "r", encoding="utf-8") as f:
        transformations = json.load(f)

    # Filter for single words (no spaces)
    single_words = {
        phrase: transform
        for phrase, transform in transformations.items()
        if " " not in phrase
    }

    if len(single_words) < 5:
        print(
            "Error: Need at least 5 single-word transformations for test singles mode"
        )
        sys.exit(1)

    # Select 5 random single words
    selected_phrases = random.sample(list(single_words.keys()), 5)

    print(
        "Test singles mode: Checking 5 random single-word transformations interactively"
    )
    print("=" * 70)

    updated_count = 0

    for i, phrase in enumerate(selected_phrases, 1):
        current_transform = single_words[phrase]
        suggested_transform = transform_phrase(phrase)

        print(f"\n{i}/5: Phrase: '{phrase}'")
        print(f"Current transformation: '{current_transform}'")
        print(f"Suggested transformation: '{suggested_transform}'")

        while True:
            response = (
                input("Does the suggested transformation match? (y/n): ")
                .strip()
                .lower()
            )
            if response in ["y", "yes"]:
                if current_transform != suggested_transform:
                    transformations[phrase] = suggested_transform
                    updated_count += 1
                    print(f"✓ Updated: '{current_transform}' → '{suggested_transform}'")
                else:
                    print("✓ Already correct")
                break
            elif response in ["n", "no"]:
                custom = input("Enter the correct transformation: ").strip()
                if custom and custom != current_transform:
                    transformations[phrase] = custom
                    updated_count += 1
                    print(f"✓ Updated: '{current_transform}' → '{custom}'")
                else:
                    print("✓ Kept current transformation")
                break
            else:
                print("Please answer 'y' or 'n'")

    # Write back the updated JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(transformations, f, ensure_ascii=False, indent=4)

    print(f"\n{'=' * 70}")
    print(
        f"Test Singles Results: Updated {updated_count} out of 5 single-word transformations"
    )
    print(f"Saved changes to {json_path}")


def fix_all_mode():
    """Fix all transformations in sananmuunnokset.json"""
    json_path = os.path.join("data", "sananmuunnokset.json")

    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found")
        sys.exit(1)

    # Read current JSON
    with open(json_path, "r", encoding="utf-8") as f:
        transformations = json.load(f)

    print(f"Processing {len(transformations)} entries...")

    # Fix each transformation
    fixed_transformations = {}
    for original_phrase, incorrect_transformation in transformations.items():
        correct_transformation = transform_phrase(original_phrase)
        fixed_transformations[original_phrase] = correct_transformation
        print(f"Fixed: '{original_phrase}' -> '{correct_transformation}'")

    # Write back the corrected JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(fixed_transformations, f, ensure_ascii=False, indent=4)

    print(
        f"\nFixed {len(fixed_transformations)} transformations and saved to {json_path}"
    )


if __name__ == "__main__":
    main()
