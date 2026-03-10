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

            # Map category to CSS class suffix
            category_class_map = {
                "Hevonen": "namedays-type-hevonen",
                "Historiallinen": "namedays-type-historiallinen",
            }

            class_suffix = category_class_map.get(
                category_filter, f"namedays-type-{category_filter.lower()}"
            )

            # Method 1: Look for result cards with the exact type class
            result_cards = page.query_selector_all(f".namedays-result-card")
            for card in result_cards:
                # Check if this card has the correct type class
                type_div = card.query_selector(".namedays-result-type")
                if type_div:
                    # Check if the type div has the class we want
                    if class_suffix in type_div.get_attribute("class"):
                        name_div = card.query_selector(".namedays-result-name")
                        if name_div:
                            name = name_div.inner_text().strip()
                            if name:
                                category_names.append(name)

            # Method 2: If no cards found with class, try section title approach
            if not category_names:
                section_titles = page.query_selector_all("h3.namedays-section-title")

                for title in section_titles:
                    title_text = title.inner_text().strip()

                    # Exact match for title
                    if title_text.lower() == category_filter.lower():
                        # Get all siblings after this title until the next title or section
                        parent = title.evaluate_handle("el => el.parentElement")
                        if parent:
                            siblings = page.evaluate(
                                """
                                (titleEl) => {
                                    const result = [];
                                    let current = titleEl.nextElementSibling;
                                    while (current) {
                                        if (current.tagName === 'H3') break;
                                        const names = current.querySelectorAll('.namedays-result-name');
                                        names.forEach(el => result.push(el.innerText.trim()));
                                        current = current.nextElementSibling;
                                    }
                                    return result;
                                }
                                """,
                                title,
                            )
                            category_names.extend(siblings)
                        break

            # Remove duplicates
            category_names = list(set(category_names))

            if category_names:
                # Save as month-day only (no year needed - namedays repeat yearly)
                month_day = f"{current.month:02d}-{current.day:02d}"
                namedays[month_day] = category_names
                print(f"{month_day} ({category_filter}): {category_names}")

        except Exception as e:
            print(f"Exception for {current.isoformat()}: {e}")

        current += delta

    browser.close()
    return namedays


if __name__ == "__main__":
    import sys

    year = date.today().year
    print(f"Starting scraping for {year}...")
    print(f"Base URL: {BASE_URL}")

    # Parse command line arguments
    category = None
    if len(sys.argv) > 1:
        category = sys.argv[1]
        # Validate category
        valid_categories = ["hevonen", "historiallinen", "both"]
        if category.lower() not in valid_categories:
            print(f"Error: Invalid category '{category}'")
            print(f"Usage: python {sys.argv[0]} [hevonen|historiallinen|both]")
            print(f"       Without arguments, scrapes both categories")
            sys.exit(1)

    # Map category name to display name
    category_map = {"hevonen": "Hevonen", "historiallinen": "Historiallinen"}

    # Ensure data directory exists
    os.makedirs(data_dir, exist_ok=True)

    with sync_playwright() as p:
        horse_data = {}
        historical_data = {}

        # Scrape horse names if requested or if no category specified (default is both)
        if (
            category is None
            or category.lower() == "both"
            or category.lower() == "hevonen"
        ):
            print("\n=== Scraping horse (hevonen) namedays ===")
            horse_data = scrape_category_namedays(p, year, "Hevonen")
            print(f"Horse names: {len(horse_data)} days found")

        # Scrape historical names if requested or if no category specified (default is both)
        if (
            category is None
            or category.lower() == "both"
            or category.lower() == "historiallinen"
        ):
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
