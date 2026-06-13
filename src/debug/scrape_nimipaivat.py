import json
import sys
from datetime import date, datetime, timedelta

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://example.invalid/nimipaivat/"


def scrape_namedays(year, base_url):
    namedays = {}
    base_url = base_url.rstrip("/") + "/"
    start = date(year, 1, 1)
    end = date(year, 12, 31)
    delta = timedelta(days=1)

    current = start
    while current <= end:
        day = current.day
        month = current.month
        url = f"{base_url}{day}.{month}."
        response = requests.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")

            # Viralliset nimipäivät
            official = []
            p_official = soup.find("p", class_="is-size-5")
            if p_official:
                strongs = p_official.find_all("strong")
                official = [s.get_text(strip=True) for s in strongs]
                print(f"{current.isoformat()}: Viralliset nimipäivät: {official}")

            # Epäviralliset nimipäivät
            unofficial = []
            p_unofficial = soup.find(
                "p", string=lambda t: t and "Epävirallista nimipäivää" in t
            )
            if not p_unofficial:
                # fallback: etsi <p> jonka teksti alkaa "Epävirallista nimipäivää"
                for p in soup.find_all("p"):
                    if p.get_text().strip().startswith("Epävirallista nimipäivää"):
                        p_unofficial = p
                        break
            if p_unofficial:
                strongs = p_unofficial.find_all("strong")
                unofficial = [s.get_text(strip=True) for s in strongs]
                print(f"{current.isoformat()}: Epäviralliset nimipäivät: {unofficial}")

            namedays[f"{current.month:02d}-{current.day:02d}"] = {
                "official": official,
                "unofficial": unofficial,
            }
        else:
            print(f"Virhe haettaessa {url}: {response.status_code}")
        current += delta

    return namedays


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <base-url>")
        print(f"Example: python {sys.argv[0]} https://example.invalid/nimipaivat")
        sys.exit(1)

    year = date.today().year
    data = scrape_namedays(year, sys.argv[1])

    # Add scrape timestamp
    data["_scrape_timestamp"] = datetime.now().isoformat()

    with open("data/nimipaivat.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Nimipäivät tallennettu data/nimipaivat.json tiedostoon ({year})")
    print(f"Scrape timestamp: {data['_scrape_timestamp']}")
