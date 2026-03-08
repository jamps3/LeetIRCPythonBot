"""Scrape hevonen and historiallinen namedays using Playwright with correct flow"""

import json
import os
from datetime import date, timedelta

from playwright.sync_api import sync_playwright

# Get project root
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if os.path.basename(project_root) == "src":
    project_root = os.path.dirname(project_root)
data_dir = os.path.join(project_root, "data")

BASE_URL = "https://almanakka.helsinki.fi/fi/nimipaivat"


def scrape_category_namedays(playwright, year, category_filter):
    """Scrape namedays by navigating to date search and extracting results"""
    namedays = {}
    start = date(year, 1, 1)
    end = date(year, 12, 31)
    delta = timedelta(days=1)

    total_days = (end - start).days + 1
    current_day = 0

    # Launch browser
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()

    print(f"Loading main page...")
    page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
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
        # Try alternative selector
        date_input = page.query_selector("input.namedays-search-input")

    if not date_input:
        print("ERROR: Could not find date input field!")
        browser.close()
        return {}

    print(f"Date input found: {date_input}")

    # Now iterate through days
    current = start
    while current <= end:
        current_day += 1

        # Print progress every 30 days
        if current_day % 30 == 0 or current_day == 1:
            print(
                f"Progress: {current_day}/{total_days} days ({current_day * 100 // total_days}%) - {current.strftime('%Y-%m-%d')}"
            )

        day = current.day
        month = current.month

        try:
            # Clear and fill the date input
            date_str = f"{day}.{month}"

            # Clear the input
            page.evaluate("""
                document.getElementById('namedays-date-input-widget_1772634673724').value = '';
            """)

            # Fill the date
            date_input.fill(date_str)

            # Wait for results to load
            page.wait_for_timeout(500)

            # Look for the category section (Hevonen or Historiallinen)
            category_names = []

            # Find all section titles
            section_titles = page.query_selector_all("h3.namedays-section-title")

            for title in section_titles:
                title_text = title.inner_text().strip()

                # Check if this is the category we're looking for
                if category_filter.lower() in title_text.lower():
                    # Find the parent or sibling with result cards
                    # Look for result cards after this title
                    parent = title.evaluate_handle("el => el.parentElement")
                    if parent:
                        # Look for result-name divs
                        result_names = parent.query_selector_all(
                            ".namedays-result-name"
                        )
                        for rn in result_names:
                            name = rn.inner_text().strip()
                            if name:
                                category_names.append(name)

            # Alternative: look for all result cards of the specific type
            if not category_names:
                result_cards = page.query_selector_all(".namedays-result-card")
                for card in result_cards:
                    # Check if this card is of the right type
                    type_div = card.query_selector(".namedays-result-type")
                    if type_div:
                        type_text = type_div.inner_text().strip()
                        if category_filter.lower() in type_text.lower():
                            name_div = card.query_selector(".namedays-result-name")
                            if name_div:
                                name = name_div.inner_text().strip()
                                if name:
                                    category_names.append(name)

            # Remove duplicates
            category_names = list(set(category_names))

            if category_names:
                namedays[current.isoformat()] = category_names
                # print(f"{current.isoformat()}: {category_names}")

        except Exception as e:
            print(f"Exception for {current.isoformat()}: {e}")

        current += delta

    browser.close()
    return namedays


if __name__ == "__main__":
    year = date.today().year
    print(f"Starting scraping for {year}...")
    print(f"Base URL: {BASE_URL}")

    # Ensure data directory exists
    os.makedirs(data_dir, exist_ok=True)

    with sync_playwright() as p:
        # Scrape horse names
        print("\n=== Scraping horse (hevonen) namedays ===")
        horse_data = scrape_category_namedays(p, year, "Hevonen")
        print(f"Horse names: {len(horse_data)} days found")

        # Scrape historical names
        print("\n=== Scraping historical (historiallinen) namedays ===")
        historical_data = scrape_category_namedays(p, year, "Historiallinen")
        print(f"Historical names: {len(historical_data)} days found")

    # Combine into one structure
    combined_data = {
        "hevonen": horse_data,
        "historiallinen": historical_data,
    }

    # Save to file
    output_file = os.path.join(data_dir, "nimipaivat_hevonen_historiallinen_temp.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(combined_data, f, ensure_ascii=False, indent=2)

    print(f"\nData saved to {output_file}")
    print(f"Horse days: {len(horse_data)}, Historical days: {len(historical_data)}")
