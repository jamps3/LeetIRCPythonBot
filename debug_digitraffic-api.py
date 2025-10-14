from datetime import datetime

import pytz
import requests
from dateutil import parser

# Aikavyöhyke: Helsinki
helsinki_tz = pytz.timezone("Europe/Helsinki")
now = datetime.now(tz=helsinki_tz)

# Kaupunki → asemakoodi
kaupunki_to_koodi = {
    "Helsinki": "HKI",
    "Joensuu": "JNS",
    "Tampere": "TPE",
    "Turku": "TKU",
    "Oulu": "OUL",
    "Jyväskylä": "JY",
    "Lahti": "LHI",
    "Kuopio": "KUO",
    "Seinäjoki": "SJ",
    "Rovaniemi": "ROI",
    "Lappeenranta": "LPR",
    "Kouvola": "KVL",
    "Vaasa": "VS",
    "Pieksämäki": "PM",
    "Imatra": "IMR",
    "Nurmes": "NRM",
    "Onttola": "ONT",
}

# Asemakoodi → kaupunki
koodi_to_kaupunki = {v: k for k, v in kaupunki_to_koodi.items()}


def kaupunki_lyhenne(kaupunki):
    return kaupunki_to_koodi.get(kaupunki)


def lyhenne_kaupunki(koodi):
    return koodi_to_kaupunki.get(koodi, koodi)


def format_time(iso_time):
    try:
        dt = parser.isoparse(iso_time).astimezone(helsinki_tz)
        return dt.strftime("%H:%M %d.%m.%y")
    except Exception:
        return "AIKA EI SAATAVILLA"


def parse_time(iso_time):
    try:
        return parser.isoparse(iso_time).astimezone(helsinki_tz)
    except Exception:
        return None


# Käyttäjän syöttämä lähtöasema
kaupunki = "Joensuu"
station_code = kaupunki_lyhenne(kaupunki)

if not station_code:
    print(f"Kaupunkia '{kaupunki}' ei löytynyt asemalistasta.")
else:
    url = f"https://rata.digitraffic.fi/api/v1/live-trains/station/{station_code}"

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.HTTPError:
        try:
            error_info = response.json()
        except ValueError:
            error_info = response.text
        print(f"API request failed ({response.status_code}): {error_info}")
        data = []
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
        data = []

    trains = (
        data
        if isinstance(data, list)
        else data.get("trains", []) if isinstance(data, dict) else []
    )

    for train in trains:
        train_type = train.get("trainType", "UNKNOWN")
        train_number = train.get("trainNumber", "UNKNOWN")
        time_table_rows = train.get("timeTableRows", [])

        # Määränpää: viimeinen aikataulurivi
        destination_row = time_table_rows[-1] if time_table_rows else {}
        destination_code = destination_row.get("stationShortCode", "UNKNOWN")
        destination_name = lyhenne_kaupunki(destination_code)
        arrival_time_raw = destination_row.get("scheduledTime")
        arrival_time = parse_time(arrival_time_raw)

        # Lähtöasema: etsitään DEPARTURE-rivi
        departure_row = next(
            (
                row
                for row in time_table_rows
                if row.get("stationShortCode") == station_code
                and row.get("type") == "DEPARTURE"
            ),
            None,
        )
        departure_time_raw = (
            departure_row.get("scheduledTime") if departure_row else None
        )
        departure_time = parse_time(departure_time_raw)

        # Myöhästymistieto (minuuteissa)
        delay_minutes = (
            departure_row.get("differenceInMinutes") if departure_row else None
        )
        delay_str = (
            f" (+{delay_minutes} min myöhässä)"
            if delay_minutes and delay_minutes > 0
            else ""
        )

        # Suodatus: poista jos ei lähtö- tai saapumisaikaa tai juna jo perillä
        if not departure_time or not arrival_time or arrival_time <= now:
            continue

        formatted_departure = format_time(departure_time_raw)
        formatted_arrival = format_time(arrival_time_raw)

        # Valitse verbi: "lähtee" vai "lähti"
        verb = "lähti" if departure_time <= now else "lähtee"

        print(
            f"Juna {train_type} {train_number} {verb} {kaupunki}-asemalta klo {formatted_departure}{delay_str} ja saapuu {destination_name}-asemalle klo {formatted_arrival}"
        )
