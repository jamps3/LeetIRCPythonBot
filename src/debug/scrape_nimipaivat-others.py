"""
Scrape additional namedays from url
Ruotsinkieliset, Saamenkieliset ja Ortodoksiset (Orthodox) nimet.
"""

import json
import os
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

# Get the project root directory (parent of src/)
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
# Go up to the actual project root (parent of src/)
if os.path.basename(project_root) == "src":
    project_root = os.path.dirname(project_root)
data_dir = os.path.join(project_root, "data")


def scrape_other_namedays(year):
    """Scrape Swedish, Sami, and Orthodox namedays from url"""
    namedays = {}
    start = date(year, 1, 1)
    end = date(year, 12, 31)
    delta = timedelta(days=1)

    total_days = (end - start).days + 1
    current_day = 0

    current = start
    while current <= end:
        current_day += 1
        day = current.day
        month = current.month
        url = f"{url}/{day}.{month}."

        # Print progress every 10 days
        if current_day % 10 == 0 or current_day == 1:
            print(
                f"Progress: {current_day}/{total_days} days ({current_day * 100 // total_days}%) - {current.strftime('%Y-%m-%d')}"
            )

        response = requests.get(url)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")

            # Initialize categories
            swedish = []  # Ruotsinkieliset nimet
            sami = []  # Saamenkieliset nimet
            orthodox = []  # Ortodoksiset nimet

            # Find all paragraphs that might contain name sections
            all_ps = soup.find_all("p")

            for p in all_ps:
                text = p.get_text()

                # Check for Swedish names section (multiple pattern variations)
                if (
                    "Ruotsinkielistä nimipäivää viettävät" in text
                    or "Ruotsinkieliset nimet:" in text
                ):
                    strongs = p.find_all("strong")
                    swedish = [s.get_text(strip=True) for s in strongs]

                # Check for Sami names section (multiple pattern variations)
                elif (
                    "Saamenkielistä nimipäivää viettävät" in text
                    or "Saamenkieliset nimet:" in text
                ):
                    strongs = p.find_all("strong")
                    sami = [s.get_text(strip=True) for s in strongs]

                # Check for Orthodox names section (multiple pattern variations)
                elif (
                    "Ortodoksista nimipäivää viettävät" in text
                    or "Ortodoksiset nimet:" in text
                ):
                    strongs = p.find_all("strong")
                    orthodox = [s.get_text(strip=True) for s in strongs]

            # Only add entry if there's at least one category with names
            if swedish or sami or orthodox:
                namedays[current.isoformat()] = {
                    "swedish": swedish,
                    "sami": sami,
                    "orthodox": orthodox,
                }
        else:
            print(f"Virhe haettaessa {url}: {response.status_code}")

        current += delta

    return namedays


if __name__ == "__main__":
    year = date.today().year
    print(f"Aloitetaan muiden nimipäivien skraptaus vuodelle {year}...")
    data = scrape_other_namedays(year)

    # Ensure data directory exists
    os.makedirs(data_dir, exist_ok=True)

    output_file = os.path.join(data_dir, "nimipaivat_others.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Muut nimipäivät tallennettu {output_file} tiedostoon ({year})")
    print(f"Yhteensä {len(data)} päivää löydetty")
