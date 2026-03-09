"""
Scrape additional namedays from nimipaivat.fi using Playwright
Usage: python scrape_nimipaivat-others.py <url>
Example: python scrape_nimipaivat-others.py https://www.nimipaivat.fi

Ruotsinkieliset, Saamenkieliset ja Ortodoksiset (Orthodox) nimet.
"""

import json
import os
import re
import sys
from datetime import date, timedelta

from playwright.sync_api import sync_playwright

# Get project root
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if os.path.basename(project_root) == "src":
    project_root = os.path.dirname(project_root)
data_dir = os.path.join(project_root, "data")


def get_browser(playwright):
    """Try to get a browser using different channels"""
    channels = ["chrome", "chromium", "msedge"]
    for channel in channels:
        try:
            browser = playwright.chromium.launch(channel=channel, headless=True)
            print(f"Using browser channel: {channel}")
            return browser
        except Exception as e:
            continue

    # Fallback: try without channel
    try:
        browser = playwright.chromium.launch(headless=True)
        return browser
    except Exception as e:
        print(f"Failed to launch browser: {e}")
        return None


def scrape_with_playwright(base_url, year=2026):
    """Scrape namedays using Playwright"""
    result = {}

    with sync_playwright() as p:
        browser = get_browser(p)
        if not browser:
            print("ERROR: Could not find any browser")
            return {}

        page = browser.new_page()

        start = date(year, 1, 1)
        end = date(year, 12, 31)
        total_days = (end - start).days + 1
        current_day = 0

        current = start
        while current <= end:
            current_day += 1
            day = current.day
            month = current.month

            if current_day % 30 == 0 or current_day == 1:
                print(
                    f"Progress: {current_day}/{total_days} days ({current_day * 100 // total_days}%) - {current.strftime('%Y-%m-%d')}"
                )

            try:
                # Navigate to URL with trailing dot (the correct format)
                url = f"{base_url}/{day}.{month}."
                page.goto(url, wait_until="domcontentloaded")
                page.wait_for_timeout(1000)

                # Get full page text
                page_text = page.inner_text("body")

                # Extract names from text patterns
                # Note: text format is "Ruotsinkielistä nimipäivää viettävät: names"
                swedish = []
                sami = []
                orthodox = []

                # Swedish names - handle both singular and plural
                match = re.search(
                    r"Ruotsinkielistä nimipäivää viettävät?:\s*(.+)",
                    page_text,
                    re.IGNORECASE,
                )
                if match:
                    names_text = match.group(1).strip()
                    # Split by comma or "ja" (and)
                    names = re.split(r",\s*|\s+ja\s+", names_text)
                    swedish = [n.strip() for n in names if n.strip() and n != "ja"]

                # Sami names
                match = re.search(
                    r"Saamenkielistä nimipäivää viettää(?:vät)?:\s*(.+)",
                    page_text,
                    re.IGNORECASE,
                )
                if match:
                    names_text = match.group(1).strip()
                    names = re.split(r",\s*|\s+ja\s+", names_text)
                    sami = [n.strip() for n in names if n.strip() and n != "ja"]

                # Orthodox names
                match = re.search(
                    r"Ortodoksista nimipäivää viettää(?:vät)?:\s*(.+)",
                    page_text,
                    re.IGNORECASE,
                )
                if match:
                    names_text = match.group(1).strip()
                    names = re.split(r",\s*|\s+ja\s+", names_text)
                    orthodox = [n.strip() for n in names if n.strip() and n != "ja"]

                # Store data if found
                if swedish or sami or orthodox:
                    result[current.isoformat()] = {
                        "swedish": swedish,
                        "sami": sami,
                        "orthodox": orthodox,
                    }

            except Exception as e:
                print(f"Error at {current.strftime('%Y-%m-%d')}: {e}")

            current += timedelta(days=1)

        browser.close()

    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: python scrape_nimipaivat-others.py <url>")
        print("Example: python scrape_nimipaivat-others.py https://www.nimipaivat.fi")
        sys.exit(1)

    base_url = sys.argv[1].rstrip("/")
    year = date.today().year

    print(f"Starting scrape for {year}...")
    print(f"URL: {base_url}")
    print()

    data = scrape_with_playwright(base_url, year)

    # Ensure data directory exists
    os.makedirs(data_dir, exist_ok=True)

    output_file = os.path.join(data_dir, "nimipaivat_others_temp.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nData saved to {output_file}")
    print(f"Total days with data: {len(data)}")


if __name__ == "__main__":
    main()
