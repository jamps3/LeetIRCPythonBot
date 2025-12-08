#!/usr/bin/env python3
"""
Comprehensive debug tool for Otiedote flow testing.

This script tests the complete Otiedote pipeline:
- Organization extraction from HTML
- JSON file updates
- Filtering logic
- Full announcement flow simulation

Usage: python src/debug/debug_otiedote_flow.py
"""

import json
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import requests
from bs4 import BeautifulSoup

from services.otiedote_json_service import fetch_release

BASE_URL = "https://otiedote.fi/release_view/{}"


def test_organization_extraction():
    """Test organization extraction methods."""
    print("=" * 60)
    print("TESTING ORGANIZATION EXTRACTION")
    print("=" * 60)

    test_release_id = 2861

    # Method 1: otiedote_json_service.py approach
    print(f"Testing release #{test_release_id}:")
    result1 = fetch_release(test_release_id)
    if result1:
        print(f"  Service method: '{result1['organization']}'")
    else:
        print("  Service method: FAILED")
        return

    # Method 2: scrape_otiedote.py approach
    def fetch_release_scrape_style(id):
        url = BASE_URL.format(id)
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return None

        soup = BeautifulSoup(r.text, "html.parser")
        h1 = soup.find("h1")
        if not h1 or "Tiedotetta ei löytynyt" in h1.get_text(strip=True):
            return None

        organization = ""
        org_label = soup.find(
            "b", string=lambda s: s and "Julkaiseva organisaatio" in s
        )
        if org_label:
            col_parent = org_label.find_parent("div", class_="col-lg-2")
            if col_parent:
                col_auto = col_parent.find_next_sibling("div", class_="col-auto")
                if col_auto:
                    mb3_div = col_auto.find("div", class_="mb-3")
                    if mb3_div:
                        organization = mb3_div.get_text(strip=True)

        return {
            "organization": organization,
            "title": h1.get_text(strip=True) if h1 else "",
        }

    result2 = fetch_release_scrape_style(test_release_id)
    if result2:
        print(f"  Scrape method:  '{result2['organization']}'")
    else:
        print("  Scrape method: FAILED")

    # Compare results
    if result1 and result2:
        match = result1["organization"] == result2["organization"]
        print(f"  Methods match: {match}")
        if not match:
            print("  ❌ WARNING: Extraction methods produce different results!")
        else:
            print("  ✅ Organization extraction working correctly")


def test_json_file_updates():
    """Test that JSON file contains organization data."""
    print("\n" + "=" * 60)
    print("TESTING JSON FILE UPDATES")
    print("=" * 60)

    test_release_id = 2861

    try:
        with open("data/otiedote.json", "r", encoding="utf-8") as f:
            data = json.load(f)

        # Find the test release
        found = False
        for item in data:
            if item["id"] == test_release_id:
                saved_org = item.get("organization", "MISSING")
                print(f"Release #{test_release_id} in JSON:")
                print(f"  Saved organization: '{saved_org}'")

                # Compare with fresh extraction
                fresh_result = fetch_release(test_release_id)
                if fresh_result:
                    fresh_org = fresh_result["organization"]
                    print(f"  Fresh extraction:  '{fresh_org}'")
                    match = saved_org == fresh_org
                    print(f"  JSON matches fresh: {match}")
                    if match:
                        print("  ✅ JSON file is up to date")
                    else:
                        print("  ❌ JSON file needs updating")
                found = True
                break

        if not found:
            print(f"Release #{test_release_id} not found in JSON file")

        print(f"\nTotal releases in JSON: {len(data)}")

    except Exception as e:
        print(f"Error reading JSON file: {e}")


def test_filtering_logic():
    """Test the filtering logic with current state."""
    print("\n" + "=" * 60)
    print("TESTING FILTERING LOGIC")
    print("=" * 60)

    test_release_id = 2861
    test_subscriber = "#joensuutest"

    # Get the release
    release = fetch_release(test_release_id)
    if not release:
        print(f"Could not fetch release #{test_release_id}")
        return

    print(f"Testing filtering for release #{test_release_id}:")
    print(f"  Title: {release['title']}")
    print(f"  Organization: '{release['organization']}'")

    # Load filters from state.json
    try:
        with open("data/state.json", "r", encoding="utf-8") as f:
            state = json.load(f)
        filters = state.get("otiedote", {}).get("filters", {})
        print(f"\nLoaded filters: {filters}")
    except Exception as e:
        print(f"Error loading state.json: {e}")
        return

    # Simulate the filtering logic from bot_manager.py
    channel_filters = filters.get(test_subscriber, [])
    print(f"\nFilters for {test_subscriber}: {channel_filters}")

    should_send = True

    if channel_filters:
        print("Channel has filters, checking if any match...")
        should_send = False

        for filter_entry in channel_filters:
            print(f"  Checking filter: '{filter_entry}'")

            # Parse filter entry
            if ":" in filter_entry:
                organization, field = filter_entry.split(":", 1)
            else:
                organization = filter_entry
                field = "organization"

            print(f"    Parsed: org='{organization}', field='{field}'")

            # Check the field
            if field == "organization":
                release_org = release.get("organization", "")
                match = organization.lower() in release_org.lower()
                print(
                    f"    Match check: '{organization.lower()}' in '{release_org.lower()}' = {match}"
                )

                if match:
                    should_send = True
                    print("    ✅ FILTER MATCH - message will be sent")
                    break
                else:
                    print("    ❌ No match")
            else:
                print(f"    ❌ Unsupported field: {field}")

    print(f"\nFINAL RESULT: should_send = {should_send}")
    if should_send:
        print(f"❌ MESSAGE WILL BE SENT TO {test_subscriber}")
    else:
        print(f"✅ MESSAGE WILL BE FILTERED for {test_subscriber}")


def test_subscriptions():
    """Test subscription system."""
    print("\n" + "=" * 60)
    print("TESTING SUBSCRIPTIONS")
    print("=" * 60)

    try:
        import subscriptions

        subs = subscriptions.get_subscribers("onnettomuustiedotteet")
        print(f"Subscribers for 'onnettomuustiedotteet': {len(subs)}")
        for nick, server in subs:
            print(f"  - {nick} on {server}")
    except Exception as e:
        print(f"Error checking subscriptions: {e}")


def run_all_tests():
    """Run all debug tests."""
    print("OTIEDOTE FLOW DEBUG TEST")
    print("========================")

    try:
        test_organization_extraction()
        test_json_file_updates()
        test_filtering_logic()
        test_subscriptions()

        print("\n" + "=" * 60)
        print("DEBUG TEST COMPLETE")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ DEBUG TEST FAILED: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    run_all_tests()
