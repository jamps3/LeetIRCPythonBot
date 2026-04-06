#!/usr/bin/env python3
"""
Verify nameday data against https://almanakka.helsinki.fi/fi/nimipaivat
Shows differences between local JSON data and website.
"""

import json
import os
import sys
from datetime import date, timedelta

from playwright.sync_api import sync_playwright

# Get project root
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if os.path.basename(project_root) == "src":
    project_root = os.path.dirname(project_root)
data_dir = os.path.join(project_root, "data")

BASE_URL = "https://almanakka.helsinki.fi/fi/nimipaivat"


def load_local_data():
    """Load local JSON data"""
    local_data = {}

    # Load main nimipaivat.json
    main_file = os.path.join(data_dir, "nimipaivat.json")
    if os.path.exists(main_file):
        with open(main_file, "r", encoding="utf-8") as f:
            local_data["main"] = json.load(f)

    # Load nimipaivat_others.json
    others_file = os.path.join(data_dir, "nimipaivat_others.json")
    if os.path.exists(others_file):
        with open(others_file, "r", encoding="utf-8") as f:
            local_data["others"] = json.load(f)

    return local_data


def scrape_website(playwright, year):
    """Scrape all namedays from the website"""
    print(f"Scraping website: {BASE_URL}")

    website_data = {
        "official": {},  # Viralliset
        "unofficial": {},  # Epäviralliset
        "dogs": {},  # Koirat
        "cats": {},  # Kissat
        "hevonen": {},  # Hevonen
        "historiallinen": {},  # Historiallinen
        "suomi": {},  # Suomalainen
        "ruotsi": {},  # Suomenruotsalainen
        "saame": {},  # Saamelainen
        "ortodoksi": {},  # Ortodoksinen
    }

    start = date(year, 1, 1)
    end = date(year, 12, 31)

    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()

    page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2000)

    # Click search button
    try:
        search_btn = page.query_selector(".namedays-btn")
        if search_btn:
            search_btn.click()
            page.wait_for_timeout(2000)
    except Exception as e:
        print(f"Could not find .namedays-btn: {e}")

    # Click date tab
    try:
        paiva_btn = page.query_selector('button[data-tab="date"]')
        if paiva_btn:
            paiva_btn.click()
            page.wait_for_timeout(1000)
    except Exception as e:
        print(f"Could not find 'Päivä' button: {e}")

    date_input = page.query_selector("#namedays-date-input-widget_1772634673724")
    if not date_input:
        date_input = page.query_selector("input.namedays-search-input")

    if not date_input:
        print("ERROR: Could not find date input field!")
        browser.close()
        return {}

    print(f"Date input found, scraping all categories...")

    current = start
    total_days = (end - start).days + 1

    while current <= end:
        month_day = f"{current.month:02d}-{current.day:02d}"

        if current.day == 1 or current.day == 15:
            print(f"Progress: {current.strftime('%Y-%m-%d')}...")

        try:
            date_str = f"{current.day}.{current.month}"

            # Clear and fill date
            page.evaluate("""
                const inp = document.getElementById('namedays-date-input-widget_1772634673724') 
                          || document.querySelector('input.namedays-search-input');
                if (inp) inp.value = '';
            """)
            date_input.fill(date_str)
            page.wait_for_timeout(500)
            # Trigger input event for autocomplete
            page.evaluate("""
                const inp = document.getElementById('namedays-date-input-widget_1772634673724');
                if (inp) inp.dispatchEvent(new Event('input'));
            """)
            page.wait_for_timeout(500)

            # Get all result cards
            result_cards = page.query_selector_all(".namedays-result-card")

            for card in result_cards:
                name_div = card.query_selector(".namedays-result-name")
                type_div = card.query_selector(".namedays-result-type")

                if not name_div or not type_div:
                    continue

                name = name_div.inner_text().strip()
                type_text = type_div.inner_text().strip()

                if not name:
                    continue

                # Determine category from type class or text
                type_class = type_div.get_attribute("class") or ""

                # Check each category - class match or text match
                if "namedays-type-hevonen" in type_class or type_text == "Hevonen":
                    if month_day not in website_data["hevonen"]:
                        website_data["hevonen"][month_day] = []
                    if name not in website_data["hevonen"][month_day]:
                        website_data["hevonen"][month_day].append(name)
                elif (
                    "namedays-type-historiallinen" in type_class
                    or type_text == "Historiallinen"
                ):
                    if month_day not in website_data["historiallinen"]:
                        website_data["historiallinen"][month_day] = []
                    if name not in website_data["historiallinen"][month_day]:
                        website_data["historiallinen"][month_day].append(name)
                elif "namedays-type-suomi" in type_class or type_text == "Suomalainen":
                    if month_day not in website_data["suomi"]:
                        website_data["suomi"][month_day] = []
                    if name not in website_data["suomi"][month_day]:
                        website_data["suomi"][month_day].append(name)
                elif (
                    "namedays-type-ruotsi" in type_class
                    or type_text == "Suomenruotsalainen"
                ):
                    if month_day not in website_data["ruotsi"]:
                        website_data["ruotsi"][month_day] = []
                    if name not in website_data["ruotsi"][month_day]:
                        website_data["ruotsi"][month_day].append(name)
                elif "namedays-type-saame" in type_class or type_text == "Saamelainen":
                    if month_day not in website_data["saame"]:
                        website_data["saame"][month_day] = []
                    if name not in website_data["saame"][month_day]:
                        website_data["saame"][month_day].append(name)
                elif "namedays-type-ortod" in type_class or type_text == "Ortodoksinen":
                    if month_day not in website_data["ortodoksi"]:
                        website_data["ortodoksi"][month_day] = []
                    if name not in website_data["ortodoksi"][month_day]:
                        website_data["ortodoksi"][month_day].append(name)
                elif (
                    "namedays-type-virallinen" in type_class
                    or type_text == "Virallinen"
                ):
                    if month_day not in website_data["official"]:
                        website_data["official"][month_day] = []
                    if name not in website_data["official"][month_day]:
                        website_data["official"][month_day].append(name)
                elif (
                    "namedays-type-epavirallinen" in type_class
                    or type_text == "Epävirallinen"
                ):
                    if month_day not in website_data["unofficial"]:
                        website_data["unofficial"][month_day] = []
                    if name not in website_data["unofficial"][month_day]:
                        website_data["unofficial"][month_day].append(name)
                elif "namedays-type-koira" in type_class or type_text == "Koira":
                    if month_day not in website_data["dogs"]:
                        website_data["dogs"][month_day] = []
                    if name not in website_data["dogs"][month_day]:
                        website_data["dogs"][month_day].append(name)
                elif "namedays-type-kissa" in type_class or type_text == "Kissa":
                    if month_day not in website_data["cats"]:
                        website_data["cats"][month_day] = []
                    if name not in website_data["cats"][month_day]:
                        website_data["cats"][month_day].append(name)

        except Exception as e:
            print(f"Error at {current.strftime('%Y-%m-%d')}: {e}")

        current = current + timedelta(days=1)

    browser.close()
    return website_data


def compare_data(local_data, website_data):
    """Compare local and website data, show differences"""
    print("\n" + "=" * 60)
    print("COMPARISON RESULTS")
    print("=" * 60)

    differences_found = False

    # Check main categories
    if "main" in local_data:
        local_main = local_data["main"]

        for category, cat_name in [
            ("official", "Viralliset"),
            ("unofficial", "Epäviralliset"),
            ("dogs", "Koirat"),
            ("cats", "Kissat"),
        ]:
            print(f"\n--- {cat_name} ---")

            for date_key, local_names in local_main.items():
                # Skip timestamp key
                if date_key == "_scrape_timestamp":
                    continue
                if category in local_names:
                    local_list = sorted(local_names[category])
                    web_list = sorted(website_data.get(category, {}).get(date_key, []))

                    if local_list != web_list:
                        differences_found = True
                        print(f"\n  {date_key}:")
                        print(f"    Local:   {local_list}")
                        print(f"    Website: {web_list}")

                        # Show what's missing
                        missing_in_local = set(web_list) - set(local_list)
                        extra_in_local = set(local_list) - set(web_list)

                        if missing_in_local:
                            print(f"    Missing in local: {list(missing_in_local)}")
                        if extra_in_local:
                            print(f"    Extra in local:   {list(extra_in_local)}")

    # Check others (hevonen, historiallinen, suomi, ruotsi, saame, ortodoksi)
    if "others" in local_data:
        local_others = local_data["others"]

        for category in ["hevonen", "historiallinen", "ruotsi", "saame", "ortodoksi"]:
            if category in local_others:
                print(f"\n--- {category.capitalize()} ---")
                cat_data = local_others[category]

                for date_key, local_names in cat_data.items():
                    # Skip timestamp key
                    if date_key == "_scrape_timestamp":
                        continue

                    local_list = sorted(local_names)
                    web_list = sorted(website_data.get(category, {}).get(date_key, []))

                    if local_list != web_list:
                        differences_found = True
                        print(f"\n  {date_key}:")
                        print(f"    Local:   {local_list}")
                        print(f"    Website: {web_list}")

                        missing_in_local = set(web_list) - set(local_list)
                        extra_in_local = set(local_list) - set(web_list)

                        if missing_in_local:
                            print(f"    Missing in local: {list(missing_in_local)}")
                        if extra_in_local:
                            print(f"    Extra in local:   {list(extra_in_local)}")

    if not differences_found:
        print("\n✅ All data matches!")
    else:
        print("\n" + "=" * 60)
        print("Differences found! See above for details.")

    return differences_found


if __name__ == "__main__":
    year = date.today().year
    print(f"Verifying nameday data for {year}")

    # Load local data
    print("\nLoading local data...")
    local_data = load_local_data()
    print(f"Loaded: {list(local_data.keys())}")

    if "main" in local_data:
        print(f"  Main dates: {len(local_data['main'])}")
    if "others" in local_data:
        print(f"  Others categories: {list(local_data['others'].keys())}")

    # Scrape website
    print("\nScraping website...")
    with sync_playwright() as p:
        website_data = scrape_website(p, year)

    print(f"\nWebsite data scraped:")
    for cat, data in website_data.items():
        if data:
            print(f"  {cat}: {len(data)} days")

    # Compare
    compare_data(local_data, website_data)
