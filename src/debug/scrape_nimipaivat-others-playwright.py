"""
Scrape additional namedays (Swedish, Sami, Orthodox) from nimipaivat.fi using Playwright
Usage: python scrape_nimipaivat-others-playwright.py <url>
Example: python scrape_nimipaivat-others-playwright.py https://almanakka.helsinki.fi/fi/nimipaivat

This script uses the same Playwright approach as scrape_nimipaivat-hevonen-historiallinen.py
but allows URL as parameter (not hardcoded).
"""

import json
import os
import sys
from datetime import date, datetime, timedelta

from playwright.sync_api import sync_playwright

# Get project root
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if os.path.basename(project_root) == "src":
    project_root = os.path.dirname(project_root)
data_dir = os.path.join(project_root, "data")
temp_output = os.path.join(data_dir, "nimipaivat_others_temp.json")


def scrape_category(playwright, year, category_filter, base_url):
    """Scrape namedays for a specific category"""
    namedays = {}
    start = date(year, 1, 1)
    end = date(year, 12, 31)
    delta = timedelta(days=1)

    total_days = (end - start).days + 1
    current_day = 0

    # Launch browser
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()

    print(f"Loading main page: {base_url}")
    page.goto(base_url, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2000)

    # Step 1: Click the .namedays-btn to go to search page
    print("Clicking .namedays-btn...")
    try:
        search_btn = page.query_selector(".namedays-btn")
        if search_btn:
            search_btn.click()
            page.wait_for_timeout(2000)
    except Exception as e:
        print(f"Could not find .namedays-btn: {e}")

    # Step 2: Click the "Päivä" button (date tab)
    print("Clicking 'Päivä' tab...")
    try:
        paiva_btn = page.query_selector('button[data-tab="date"]')
        if paiva_btn:
            paiva_btn.click()
            page.wait_for_timeout(1000)
    except Exception as e:
        print(f"Could not find 'Päivä' button: {e}")

    # Find the date input field
    date_input = page.query_selector("#namedays-date-input-widget_1772634673724")
    if not date_input:
        date_input = page.query_selector("input.namedays-search-input")

    if not date_input:
        print("ERROR: Could not find date input field!")
        browser.close()
        return {}

    print(f"Date input found, starting scrape for category: {category_filter}")

    # Iterate through days
    current = start
    while current <= end:
        current_day += 1

        if current_day % 30 == 0 or current_day == 1:
            print(
                f"Progress: {current_day}/{total_days} days ({current_day * 100 // total_days}%) - {current.strftime('%Y-%m-%d')}"
            )

        day = current.day
        month = current.month

        try:
            date_str = f"{day}.{month}"

            # Clear and fill the date input
            page.evaluate("""
                const inp = document.getElementById('namedays-date-input-widget_1772634673724') 
                          || document.querySelector('input.namedays-search-input');
                if (inp) inp.value = '';
            """)

            date_input.fill(date_str)
            page.wait_for_timeout(500)

            # Look for the category section
            category_names = []

            # Find all section titles
            section_titles = page.query_selector_all("h3.namedays-section-title")

            for title in section_titles:
                title_text = title.inner_text().strip()

                if category_filter.lower() in title_text.lower():
                    parent = title.evaluate_handle("el => el.parentElement")
                    if parent:
                        result_names = parent.query_selector_all(
                            ".namedays-result-name"
                        )
                        for rn in result_names:
                            name = rn.inner_text().strip()
                            if name:
                                category_names.append(name)

            # Alternative: look for result cards
            if not category_names:
                result_cards = page.query_selector_all(".namedays-result-card")
                for card in result_cards:
                    type_div = card.query_selector(".namedays-result-type")
                    if type_div:
                        type_text = type_div.inner_text().strip()
                        if category_filter.lower() in type_text.lower():
                            name_div = card.query_selector(".namedays-result-name")
                            if name_div:
                                name = name_div.inner_text().strip()
                                if name:
                                    category_names.append(name)

            category_names = list(set(category_names))

            if category_names:
                # Save as month-day only (no year needed - namedays repeat yearly)
                month_day = f"{current.month:02d}-{current.day:02d}"
                namedays[month_day] = category_names

        except Exception as e:
            print(f"Error at {current.strftime('%Y-%m-%d')}: {e}")

        current += delta

    browser.close()
    return namedays


def main():
    if len(sys.argv) < 2:
        print("Usage: python scrape_nimipaivat-others-playwright.py <url>")
        print(
            "Example: python scrape_nimipaivat-others-playwright.py https://almanakka.helsinki.fi/fi/nimipaivat"
        )
        sys.exit(1)

    base_url = sys.argv[1]
    year = 2026

    print(f"Starting scrape for {year}...")
    print(f"URL: {base_url}")
    print()

    # Categories to scrape
    categories = ["ruotsi", "saame", "ortod"]

    print("Available categories: ruotsi (Swedish), saame (Sami), ortod (Orthodox)")
    print("Scraping all three categories by default...")
    print()

    result = {}

    with sync_playwright() as p:
        for cat in categories:
            print(f"=== Scraping {cat} ===")
            namedays = scrape_category(p, year, cat, base_url)
            result[cat] = namedays
            print(f"Got {len(namedays)} days with names for {cat}")
            print()

    # Add timestamp
    result["_scrape_timestamp"] = datetime.now().isoformat()

    # Save to temp file
    with open(temp_output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Saved to: {temp_output}")
    print(f"Scrape timestamp: {result['_scrape_timestamp']}")
    print("Next step: merge with existing nimipaivat_others.json")


if __name__ == "__main__":
    main()
