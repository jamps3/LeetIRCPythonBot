def send_electricity_price(irc=None, channel=None, text=None):
    # Validate input and set defaults
    date = datetime.now()
    hour = date.hour
    if len(text) == 1:
        log(f"Haettu tunti tänään: {hour}", "DEBUG")
    elif len(text) == 2:
        parts = text[1].strip().split()
        if parts[0].lower() == "huomenna" and len(parts) == 2:
            hour = int(parts[1])
            date += timedelta(days=1)
            log(f"Haettu tunti huomenna: {hour}", "DEBUG")
        elif len(parts) == 1 and parts[0].isdigit():
            hour = int(parts[0])
            log(f"Haettu tunti tänään: {hour}", "DEBUG")
        else:
            error_message = "Virheellinen komento! Käytä: !sahko [huomenna] <tunti>"
            log(error_message)
            send_message(irc, channel, error_message)
            return

    # Format dates
    date_str = date.strftime("%Y%m%d")
    date_plus_one = date + timedelta(days=1)
    date_tomorrow = date_plus_one.strftime("%Y%m%d")

    # Form API URLs
    url_today = f"https://web-api.tp.entsoe.eu/api?securityToken={ELECTRICITY_API_KEY}&documentType=A44&in_Domain=10YFI-1--------U&out_Domain=10YFI-1--------U&periodStart={date_str}0000&periodEnd={date_str}2300"
    url_tomorrow = f"https://web-api.tp.entsoe.eu/api?securityToken={ELECTRICITY_API_KEY}&documentType=A44&in_Domain=10YFI-1--------U&out_Domain=10YFI-1--------U&periodStart={date_tomorrow}0000&periodEnd={date_tomorrow}2300"

    def fetch_prices(url):
        try:
            response = requests.get(url)
            if response.status_code != 200:
                return {}
            xml_data = ElementTree.parse(StringIO(response.text))
            ns = {"ns": "urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3"}
            prices = {
                int(point.find("ns:position", ns).text): 
                float(point.find("ns:price.amount", ns).text)
                for point in xml_data.findall(".//ns:Point", ns)
            }
            return prices
        except Exception as e:
            log(f"Virhe sähkön hintojen haussa: {e}")
            return {}

    # Fetch prices for today and tomorrow
    prices_today = fetch_prices(url_today)
    prices_tomorrow = fetch_prices(url_tomorrow)

    # Process and format the prices
    hour_position = hour + 1  # API uses 1-24 hour format
    result_parts = []

    if hour_position in prices_today:
        price_eur_per_mwh = prices_today[hour_position]
        price_snt_per_kwh = (price_eur_per_mwh / 10) * 1.255  # Convert to cents and add VAT 25.5%
        result_parts.append(f"Tänään klo {hour}: {price_snt_per_kwh:.2f} snt/kWh (ALV 25,5%)")

    if hour_position in prices_tomorrow:
        price_eur_per_mwh = prices_tomorrow[hour_position]
        price_snt_per_kwh = (price_eur_per_mwh / 10) * 1.255
        result_parts.append(f"Huomenna klo {hour}: {price_snt_per_kwh:.2f} snt/kWh (ALV 25,5%)")

    # Send the results
    if result_parts:
        output_message(", ".join(result_parts), irc, channel)
    else:
        output_message(f"Sähkön hintatietoja ei saatavilla tunneille {hour}. https://sahko.tk", irc, channel)
