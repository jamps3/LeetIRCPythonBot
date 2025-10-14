#!/usr/bin/env python3
"""
Test file to validate electricity service pricing against debug_electricity_mapping_prices.txt
"""

import re
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Tuple

import pytz


def parse_test_prices(filename: str) -> Dict[Tuple[int, int], float]:
    """
    Parse debug_electricity_mapping_prices.txt file.
    Format: HH:MM*price*¢ on each line after date
    Returns dict mapping (hour, quarter) -> price_in_cents
    """
    prices = {}

    with open(filename, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Skip first two lines (date and empty line)
    data_lines = lines[2:]

    for line in data_lines:
        line = line.strip()
        if not line or line.startswith("Hourly averages:"):
            break  # Stop when we reach hourly averages section

        # Parse format like "    00:0011.51¢"
        # Extract time and price with regex
        match = re.match(r"\s*(\d{2}):(\d{2})([0-9.]+)¢", line)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2))
            price_cents = float(match.group(3))

            # Convert minute to quarter (0-14 -> Q1, 15-29 -> Q2, etc.)
            quarter = (minute // 15) + 1

            prices[(hour, quarter)] = price_cents
            print(f"Parsed: {hour:02d}:{minute:02d} (Q{quarter}) -> {price_cents}¢")
        else:
            print(f"Could not parse line: {line}")

    return prices


def parse_test_hourly_averages(filename: str) -> Dict[int, float]:
    """
    Parse hourly averages from debug_electricity_mapping_prices.txt file.
    Format: "0:00 - 1:00 10.40" etc.
    Returns dict mapping hour -> average_price_in_cents
    """
    hourly_averages = {}

    with open(filename, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Find the "Hourly averages:" section
    in_hourly_section = False
    for line in lines:
        line = line.strip()

        if line == "Hourly averages:":
            in_hourly_section = True
            continue

        if in_hourly_section and line:
            # Parse format like "0:00 - 1:00 10.40" or "23:00 - 24:00 16.17"
            match = re.match(r"(\d{1,2}):00 - (\d{1,2}):00 ([0-9.]+)", line)
            if match:
                start_hour = int(match.group(1))
                end_hour = int(match.group(2))
                avg_price = float(match.group(3))

                # The range "0:00 - 1:00" represents hour 0, "1:00 - 2:00" represents hour 1, etc.
                hour = start_hour
                hourly_averages[hour] = avg_price
                print(
                    f"Parsed hourly avg: {hour:02d}:00-{hour+1:02d}:00 -> {avg_price:.2f}¢"
                )
            else:
                print(f"Could not parse hourly average line: {line}")

    return hourly_averages


def generate_mock_xml_response(expected_prices: Dict[Tuple[int, int], float]) -> str:
    """
    Generate a mock ENTSO-E XML response for testing.
    Convert expected prices (in cents) back to EUR/MWh for the XML.
    """
    vat_rate = 1.255

    # XML header
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<Publication_MarketDocument xmlns="urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:0">
    <mRID>test-market-doc</mRID>
    <revisionNumber>1</revisionNumber>
    <type>A44</type>
    <process.processType>A01</process.processType>
    <TimeSeries>
        <mRID>test-timeseries</mRID>
        <businessType>A62</businessType>
        <in_Domain.mRID codingScheme="A01">10YFI-1--------U</in_Domain.mRID>
        <out_Domain.mRID codingScheme="A01">10YFI-1--------U</out_Domain.mRID>
        <currency_Unit.name>EUR</currency_Unit.name>
        <price_Measure_Unit.name>MWH</price_Measure_Unit.name>
        <curveType>A01</curveType>
        <Period>
            <timeInterval>
                <start>2025-10-13T21:00Z</start>
                <end>2025-10-14T21:00Z</end>
            </timeInterval>
            <resolution>PT15M</resolution>
"""

    # Generate price points (96 15-minute intervals in a day)
    position = 1
    for hour in range(24):
        for quarter in range(1, 5):
            cents = expected_prices.get((hour, quarter), 10.0)  # Default fallback
            # Convert cents back to EUR/MWh (reverse of the service conversion)
            eur_mwh = (cents * 10) / vat_rate

            xml_content += f"""            <Point>
                <position>{position}</position>
                <price.amount>{eur_mwh:.2f}</price.amount>
            </Point>
"""
            position += 1

    xml_content += """        </Period>
    </TimeSeries>
</Publication_MarketDocument>"""

    return xml_content


def test_hourly_averages_with_mocked_api():
    """
    Test hourly averages calculated by the service against expected values.
    """
    import unittest.mock as mock

    try:
        from services.electricity_service import ElectricityService
    except ImportError:
        print("Could not import ElectricityService")
        return False

    # Parse expected prices and hourly averages
    expected_prices = parse_test_prices("debug_electricity_mapping_prices.txt")
    expected_hourly_averages = parse_test_hourly_averages(
        "debug_electricity_mapping_prices.txt"
    )

    print(f"\nParsed {len(expected_prices)} expected price points")
    print(f"Parsed {len(expected_hourly_averages)} expected hourly averages")

    # Generate mock XML response
    mock_xml = generate_mock_xml_response(expected_prices)

    # Create service
    service = ElectricityService("dummy_api_key")

    # Test date
    test_date = date(2025, 10, 14)

    print(f"\nTesting hourly averages with mocked API for {test_date}")
    print("=" * 60)

    # Mock the requests.get call
    with mock.patch("services.electricity_service.requests.get") as mock_get:
        # Setup mock response
        mock_response = mock.Mock()
        mock_response.text = mock_xml
        mock_response.raise_for_status = mock.Mock()
        mock_get.return_value = mock_response

        failures = []
        successes = []

        # Test a subset of hours to verify hourly averages
        test_hours = [
            0,
            1,
            6,
            7,
            12,
            18,
            19,
            20,
            23,
        ]  # Mix of low, medium, and high price hours

        for hour in test_hours:
            expected_avg = expected_hourly_averages.get(hour)
            if expected_avg is None:
                print(f"No expected hourly average for hour {hour}")
                continue

            print(f"Testing hour {hour:02d}:00")
            print(f"  Expected hourly avg: {expected_avg:.2f}¢")

            try:
                # Get price data for this hour (any quarter will give us the hourly data)
                result = service.get_electricity_price(
                    hour=hour, quarter=1, date=test_date
                )

                if result.get("error"):
                    print(f"  ❌ Service error: {result.get('message')}")
                    failures.append((hour, expected_avg, None))
                    continue

                today_price = result.get("today_price", {})
                service_hourly_avg = today_price.get("hour_avg_snt_kwh")

                if service_hourly_avg is None:
                    print("  ❌ No hourly average returned by service")
                    failures.append((hour, expected_avg, None))
                    continue

                print(f"  Service hourly avg: {service_hourly_avg:.2f} snt/kWh")

                # Check if they match (within small tolerance)
                if abs(service_hourly_avg - expected_avg) < 0.01:
                    successes.append(hour)
                    print("  ✅ MATCH")
                else:
                    failures.append((hour, expected_avg, service_hourly_avg))
                    print("  ❌ MISMATCH")

                # Also show individual quarter prices that make up the average
                quarter_prices = today_price.get("quarter_prices_snt", {})
                if quarter_prices:
                    quarters_str = ", ".join(
                        [
                            f"Q{q}:{price:.2f}"
                            for q, price in sorted(quarter_prices.items())
                        ]
                    )
                    calculated_avg = sum(quarter_prices.values()) / len(quarter_prices)
                    print(
                        f"  Quarter prices: {quarters_str} (avg: {calculated_avg:.2f})"
                    )

            except Exception as e:
                print(f"  ❌ Exception: {e}")
                failures.append((hour, expected_avg, None))

            print()

        print("\nHourly Averages Test Summary:")
        print(f"Successes: {len(successes)}")
        print(f"Failures: {len(failures)}")

        if failures:
            print("\nFailures:")
            for hour, expected, actual in failures:
                actual_str = f"{actual:.2f}¢" if actual is not None else "None"
                print(f"  {hour:02d}:00: expected {expected:.2f}¢, got {actual_str}")

        return len(failures) == 0


def test_electricity_service_with_mocked_api():
    """
    Test the electricity service with mocked API response.
    """
    import unittest.mock as mock

    try:
        from services.electricity_service import ElectricityService
    except ImportError:
        print("Could not import ElectricityService")
        return False

    # Parse expected prices
    expected_prices = parse_test_prices("debug_electricity_mapping_prices.txt")
    print(f"\nParsed {len(expected_prices)} expected price points")

    # Generate mock XML response
    mock_xml = generate_mock_xml_response(expected_prices)

    # Create service
    service = ElectricityService("dummy_api_key")

    # Test date
    test_date = date(2025, 10, 14)

    print(f"\nTesting electricity service with mocked API for {test_date}")
    print("=" * 60)

    # Mock the requests.get call
    with mock.patch("services.electricity_service.requests.get") as mock_get:
        # Setup mock response
        mock_response = mock.Mock()
        mock_response.text = mock_xml
        mock_response.raise_for_status = mock.Mock()
        mock_get.return_value = mock_response

        # Test specific times
        test_times = [
            (0, 1),  # 00:00
            (0, 2),  # 00:15
            (7, 2),  # 07:15 - peak morning
            (12, 1),  # 12:00 - midday
            (18, 4),  # 18:45 - evening peak
            (19, 4),  # 19:45 - highest price
            (23, 4),  # 23:45 - late evening
        ]

        failures = []
        successes = []

        for hour, quarter in test_times:
            expected_cents = expected_prices.get((hour, quarter))
            if expected_cents is None:
                print(f"No expected price for {hour:02d}:{(quarter-1)*15:02d}")
                continue

            print(f"Testing {hour:02d}:{(quarter-1)*15:02d} (Q{quarter})")
            print(f"  Expected: {expected_cents}¢")

            # Get actual price from service
            try:
                result = service.get_electricity_price(
                    hour=hour, quarter=quarter, date=test_date
                )

                if result.get("error"):
                    print(f"  ❌ Service error: {result.get('message')}")
                    failures.append((hour, quarter, expected_cents, None))
                    continue

                today_price = result.get("today_price", {})
                quarter_prices_snt = today_price.get("quarter_prices_snt", {})
                actual_cents = quarter_prices_snt.get(quarter)

                if actual_cents is None:
                    print(f"  ❌ No price data for quarter {quarter}")
                    failures.append((hour, quarter, expected_cents, None))
                    continue

                print(f"  Service returned: {actual_cents:.2f} snt/kWh")

                # Check if they match (within small tolerance)
                if abs(actual_cents - expected_cents) < 0.01:
                    successes.append((hour, quarter))
                    print("  ✅ MATCH")
                else:
                    failures.append((hour, quarter, expected_cents, actual_cents))
                    print("  ❌ MISMATCH")

            except Exception as e:
                print(f"  ❌ Exception: {e}")
                failures.append((hour, quarter, expected_cents, None))

            print()

        print("\nTest Summary:")
        print(f"Successes: {len(successes)}")
        print(f"Failures: {len(failures)}")

        if failures:
            print("\nFailures:")
            for hour, quarter, expected, actual in failures:
                actual_str = f"{actual:.2f}¢" if actual is not None else "None"
                print(
                    f"  {hour:02d}:{(quarter-1)*15:02d}: expected {expected}¢, got {actual_str}"
                )

        return len(failures) == 0


def test_electricity_service_against_expected():
    """
    Test just the conversion logic of the electricity service.
    """
    try:
        from services.electricity_service import ElectricityService
    except ImportError:
        print("Could not import ElectricityService")
        return False

    # Parse expected prices
    expected_prices = parse_test_prices("debug_electricity_mapping_prices.txt")
    print(f"\nParsed {len(expected_prices)} expected price points")

    # Create service (we'll mock the API response later)
    service = ElectricityService("dummy_api_key")

    # Test specific times against expected values
    test_date = date(2025, 10, 14)

    print(f"\nTesting electricity service conversion logic for {test_date}")
    print("=" * 60)

    failures = []
    successes = []

    # Test a few key times
    test_times = [
        (0, 1),  # 00:00
        (0, 2),  # 00:15
        (7, 2),  # 07:15 - peak morning
        (12, 1),  # 12:00 - midday
        (18, 4),  # 18:45 - evening peak
        (19, 4),  # 19:45 - highest price
        (23, 4),  # 23:45 - late evening
    ]

    for hour, quarter in test_times:
        expected_cents = expected_prices.get((hour, quarter))
        if expected_cents is None:
            print(f"No expected price for {hour:02d}:{(quarter-1)*15:02d}")
            continue

        # Get price from service (this will likely fail without proper API)
        # For now, just test the conversion logic
        print(f"Testing {hour:02d}:{(quarter-1)*15:02d} (Q{quarter})")
        print(f"  Expected: {expected_cents}¢")

        # Test the price conversion function directly
        # Expected format is cents, service returns snt/kWh
        # Need to reverse engineer what EUR/MWh would give us expected cents

        # If service expects EUR/MWh and outputs snt/kWh with VAT:
        # snt/kWh = (EUR/MWh / 10) * VAT_RATE
        # So: EUR/MWh = (snt/kWh * 10) / VAT_RATE

        vat_rate = 1.255  # From service
        expected_snt_kwh = expected_cents  # Assuming they're the same unit
        implied_eur_mwh = (expected_snt_kwh * 10) / vat_rate

        # Test conversion
        actual_snt_kwh = service._convert_price(implied_eur_mwh)

        print(f"  Implied EUR/MWh: {implied_eur_mwh:.2f}")
        print(f"  Service converts to: {actual_snt_kwh:.2f} snt/kWh")

        # Check if they match (within small tolerance)
        if abs(actual_snt_kwh - expected_cents) < 0.01:
            successes.append((hour, quarter))
            print("  ✅ MATCH")
        else:
            failures.append((hour, quarter, expected_cents, actual_snt_kwh))
            print("  ❌ MISMATCH")

        print()

    print("\nConversion Logic Test Summary:")
    print(f"Successes: {len(successes)}")
    print(f"Failures: {len(failures)}")

    if failures:
        print("\nFailures:")
        for hour, quarter, expected, actual in failures:
            print(
                f"  {hour:02d}:{(quarter-1)*15:02d}: expected {expected}¢, got {actual:.2f}¢"
            )

    return len(failures) == 0


def analyze_timezone_offset():
    """
    Analyze what timezone offset might be causing issues
    """
    print("\nAnalyzing timezone behavior:")

    helsinki_tz = pytz.timezone("Europe/Helsinki")
    utc_tz = pytz.utc

    # Test for October 14, 2025
    test_date = date(2025, 10, 14)

    # Create midnight in Helsinki time
    helsinki_midnight = helsinki_tz.localize(datetime.combine(test_date, time(0, 0)))
    utc_midnight = helsinki_midnight.astimezone(utc_tz)

    print(f"Helsinki midnight: {helsinki_midnight}")
    print(f"UTC equivalent: {utc_midnight}")
    print(f"Offset: {helsinki_midnight.utcoffset()}")

    # In October, Finland is on Eastern European Time (UTC+3 during summer, UTC+2 during winter)
    # DST ends on the last Sunday of October, which in 2025 is October 26
    # So October 14, 2025 should be UTC+3 (summer time)

    return helsinki_midnight.utcoffset()


def test_service_timezone_diagnostics():
    """
    Test the service's timezone diagnostic function
    """
    try:
        from services.electricity_service import ElectricityService
    except ImportError:
        print("Could not import ElectricityService")
        return False

    service = ElectricityService("dummy_api_key")
    test_date = date(2025, 10, 14)

    print(f"\nTesting service timezone diagnostics for {test_date}:")
    diag = service.diagnose_timezone_handling(test_date)

    for key, value in diag.items():
        print(f"  {key}: {value}")

    # Expected values for October 14, 2025 (UTC+3)
    expected_api_start = "202510132100"  # 2025-10-13 21:00 UTC
    expected_api_end = "202510142100"  # 2025-10-14 21:00 UTC

    print("\nValidation:")
    print(f"  Expected API start: {expected_api_start}")
    print(f"  Actual API start:   {diag['api_period_start']}")
    print(f"  Expected API end:   {expected_api_end}")
    print(f"  Actual API end:     {diag['api_period_end']}")

    start_match = diag["api_period_start"] == expected_api_start
    end_match = diag["api_period_end"] == expected_api_end

    if start_match and end_match:
        print("  ✅ Timezone handling is correct")
        return True
    else:
        print("  ❌ Timezone handling has issues")
        return False


if __name__ == "__main__":
    print("Testing electricity price mapping")
    print("=" * 50)

    # Analyze timezone
    offset = analyze_timezone_offset()

    # Test timezone diagnostics
    print("\n" + "=" * 50)
    print("PHASE 1: Testing timezone diagnostics")
    print("=" * 50)
    success_tz = test_service_timezone_diagnostics()

    # Run the conversion logic test
    print("\n" + "=" * 50)
    print("PHASE 2: Testing conversion logic")
    print("=" * 50)
    success1 = test_electricity_service_against_expected()

    # Run the full API test
    print("\n" + "=" * 50)
    print("PHASE 3: Testing with mocked API")
    print("=" * 50)
    success2 = test_electricity_service_with_mocked_api()

    # Run the hourly averages test
    print("\n" + "=" * 50)
    print("PHASE 4: Testing hourly averages")
    print("=" * 50)
    success3 = test_hourly_averages_with_mocked_api()

    print("\n" + "=" * 50)
    print("FINAL RESULTS")
    print("=" * 50)

    if success_tz:
        print("✅ Timezone diagnostics: PASSED")
    else:
        print("❌ Timezone diagnostics: FAILED")

    if success1:
        print("✅ Conversion logic: PASSED")
    else:
        print("❌ Conversion logic: FAILED")

    if success2:
        print("✅ Mocked API test: PASSED")
    else:
        print("❌ Mocked API test: FAILED")

    if success3:
        print("✅ Hourly averages test: PASSED")
    else:
        print("❌ Hourly averages test: FAILED")

    if success_tz and success1 and success2 and success3:
        print("\n🎉 All tests passed!")
    else:
        print("\n❌ Some tests failed - service needs fixing")
