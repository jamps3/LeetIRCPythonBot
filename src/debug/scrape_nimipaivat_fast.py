#!/usr/bin/env python3
"""
Robust scraper for nimipaivat data from almanakka.helsinki.fi
Saves incrementally and restarts browser when needed.
"""

import json
import os
import sys
from datetime import date, timedelta

from playwright.sync_api import sync_playwright

BASE_URL = "https://almanakka.helsinki.fi/fi/nimipaivat"

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if os.path.basename(project_root) == "src":
    project_root = os.path.dirname(project_root)
data_dir = os.path.join(project_root, "data")

OUTPUT_FILE = os.path.join(data_dir, "nimipaivat_scrape_temp.json")

# Number of days to scrape before restarting browser
BATCH_SIZE = 50


def init_data():
    """Initialize empty data structure"""
    return {
        "official": {},
        "unofficial": {},
        "dogs": {},
        "cats": {},
        "suomi": {},
        "ruotsi": {},
        "saame": {},
        "ortodoksi": {},
        "hevonen": {},
        "historiallinen": {},
    }


def scrape_batch(playwright, year, start_day, end_day, website_data):
    """Scrape a batch of days"""
    start = date(year, 1, 1) + timedelta(days=start_day)
    if start > date(year, 12, 31):
        return False
    end = min(date(year, 12, 31), start + timedelta(days=BATCH_SIZE))

    # Launch fresh browser for each batch
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()

    try:
        page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1500)

        # Click search button
        try:
            search_btn = page.query_selector(".namedays-btn")
            if search_btn:
                search_btn.click()
                page.wait_for_timeout(1000)
        except:
            pass

        # Click date tab
        try:
            paiva_btn = page.query_selector('button[data-tab="date"]')
            if paiva_btn:
                paiva_btn.click()
                page.wait_for_timeout(500)
        except:
            pass

        date_input = page.query_selector("#namedays-date-input-widget_1772634673724")
        if not date_input:
            print("ERROR: Could not find date input field!")
            browser.close()
            return False

    except Exception as e:
        print(f"Error during page load: {e}")
        browser.close()
        return False

    current = start
    while current <= end:
        month_day = f"{current.month:02d}-{current.day:02d}"

        if current.day == 1:
            print(f"Progress: {current.strftime('%Y-%m-%d')}...")

        try:
            date_str = f"{current.day}.{current.month}"

            page.evaluate(
                f"""const inp = document.getElementById('namedays-date-input-widget_1772634673724'); 
                if (inp) {{ inp.value = ''; inp.value = '{date_str}'; inp.dispatchEvent(new Event('input')); }}"""
            )
            page.wait_for_timeout(350)

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

                type_class = type_div.get_attribute("class") or ""

                # Map to categories - prioritize type_text over class
                type_text_cats = {
                    "Hevonen": "hevonen",
                    "Historiallinen": "historiallinen",
                    "Suomalainen": "suomi",
                    "Suomenruotsalainen": "ruotsi",
                    "Saamelainen": "saame",
                    "Ortodoksinen": "ortodoksi",
                    "Virallinen": "official",
                    "Epävirallinen": "unofficial",
                    "Koira": "dogs",
                    "Kissa": "cats",
                }
                if type_text in type_text_cats:
                    cat = type_text_cats[type_text]
                elif "namedays-type-hevonen" in type_class:
                    cat = "hevonen"
                elif "namedays-type-historiallinen" in type_class:
                    cat = "historiallinen"
                elif "namedays-type-suomi" in type_class:
                    cat = "suomi"
                elif "namedays-type-ruotsi" in type_class:
                    cat = "ruotsi"
                elif "namedays-type-saame" in type_class:
                    cat = "saame"
                elif "namedays-type-ortod" in type_class:
                    cat = "ortodoksi"
                elif "namedays-type-virallinen" in type_class:
                    cat = "official"
                elif "namedays-type-epavirallinen" in type_class:
                    cat = "unofficial"
                elif "namedays-type-koira" in type_class:
                    cat = "dogs"
                elif "namedays-type-kissa" in type_class:
                    cat = "cats"
                else:
                    continue

                if month_day not in website_data[cat]:
                    website_data[cat][month_day] = []
                if name not in website_data[cat][month_day]:
                    website_data[cat][month_day].append(name)

        except Exception as e:
            print(f"Error at {current.strftime('%Y-%m-%d')}: {e}")

        current = current + timedelta(days=1)

    try:
        browser.close()
    except:
        pass
    return True


if __name__ == "__main__":
    year = 2026
    total_days = 366  # 2026 is leap year

    print(f"Scraping nameday data for {year}")

    # Load existing data if any
    website_data = init_data()
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                website_data = json.load(f)
            print("Loaded existing data, continuing...")
        except:
            pass

    # Track progress
    all_dates = set()
    for cat in website_data:
        all_dates.update(website_data[cat].keys())
    batch_start = (
        0  # Always start from beginning, since incremental save handles progress
    )
    print(f"Loaded {len(all_dates)} existing dates")

    with sync_playwright() as p:
        while batch_start < total_days:
            success = scrape_batch(
                p, year, batch_start, batch_start + BATCH_SIZE, website_data
            )
            if not success:
                print("Batch failed, retrying...")
                continue

            # Save progress
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(website_data, f, ensure_ascii=False, indent=2)

            # Update progress
            all_dates = set()
            for cat in website_data:
                all_dates.update(website_data[cat].keys())
            print(
                f"Progress: {len(all_dates)}/{total_days} days scraped (batch {batch_start}-{min(total_days-1, batch_start + BATCH_SIZE-1)})"
            )

            # Increment batch
            batch_start += BATCH_SIZE

    print(f"\nScraped data saved to {OUTPUT_FILE}")
    print("Categories scraped:")
    for cat, data in website_data.items():
        print(f"  {cat}: {len(data)} dates")
