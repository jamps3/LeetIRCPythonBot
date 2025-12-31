import json

import requests
from bs4 import BeautifulSoup


def fetch_pet_namedays(date_str):
    base_url = "https://url"
    result = {"dogs": [], "cats": []}

    for animal in ["dog", "cat"]:
        url = f"{base_url}?country={animal}&dateselect={date_str}"
        resp = requests.get(url)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            paragraphs = soup.find_all("p", class_="cent_text")
            names = []
            for p in paragraphs:
                text = p.get_text(" ", strip=True)
                if "nimipäivää viettää" in text or "nimipäivää viettävät" in text:
                    # 1) Jos <a>-tageja löytyy, käytetään niitä
                    for a in p.find_all("a"):
                        names.append(a.get_text(strip=True))
                    # 2) Jos ei <a>-tageja, pilkotaan tekstistä nimet
                    if not names:
                        # Ota lauseen loppu (nimet)
                        if "nimipäivää viettää" in text:
                            part = text.split("nimipäivää viettää", 1)[1]
                        else:
                            part = text.split("nimipäivää viettävät", 1)[1]
                        # Poista piste lopusta ja pilko "ja" mukaan
                        part = part.strip().rstrip(".")
                        for n in part.split(" ja "):
                            names.append(n.strip())
                    print(f"{date_str} Lisätty {animal}-nimi: {names}")
            result[animal + "s"] = names
    return result


def merge_namedays(human_json_path, output_path):
    """Yhdistää ihmisten nimipäivät ja lemmikkien nimipäivät samaan JSONiin."""
    with open(human_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for date_str in data.keys():
        pets = fetch_pet_namedays(date_str)
        data[date_str]["dogs"] = pets["dogs"]
        data[date_str]["cats"] = pets["cats"]

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Yhdistetty nimipäiväkalenteri tallennettu tiedostoon {output_path}")


if __name__ == "__main__":
    merge_namedays("ihmisten_nimipaivat.json", "nimipaivat_yhdistetty.json")
