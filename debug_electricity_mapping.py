#!/usr/bin/env python3
"""
Test file to validate electricity service pricing against debug_electricity_mapping_prices.txt
"""

import re
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Tuple

import pytz


def parse_test_date(filename: str) -> date:
    """
    Parse the FIRST date from the debug_electricity_mapping_prices.txt file.
    Format: "October 16, 2025" on a date header line.
    Returns: date object
    """
    with open(filename, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # Date header like: October 16, 2025
            m = re.match(r"^[A-Za-z]+\s+\d{1,2},\s+\d{4}$", line)
            if m:
                try:
                    date_obj = datetime.strptime(line, "%B %d, %Y").date()
                    print(f"Parsed date from file: {date_obj}")
                    return date_obj
                except ValueError as e:
                    print(f"Could not parse date from '{line}': {e}")
                    break
    # Fallback to today
    return date.today()


def parse_all_test_prices(
    filename: str,
) -> List[Tuple[date, Dict[Tuple[int, int], float]]]:
    """
    Parse ALL date sections and their prices from debug_electricity_mapping_prices.txt.
    Returns a list of tuples: (date, {(hour, quarter): cents, ...})
    """
    results: List[Tuple[date, Dict[Tuple[int, int], float]]] = []
    current_date: date | None = None
    current_prices: Dict[Tuple[int, int], float] | None = None

    with open(filename, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            # Date header
            if re.match(r"^[A-Za-z]+\s+\d{1,2},\s+\d{4}$", line):
                # Flush previous block
                if current_date and current_prices is not None:
                    results.append((current_date, current_prices))
                # Start new block
                try:
                    current_date = datetime.strptime(line, "%B %d, %Y").date()
                    current_prices = {}
                    print(f"Found date section: {current_date}")
                except ValueError:
                    current_date = None
                    current_prices = None
                continue
            # Stop at hourly averages section
            if line.startswith("Hourly averages:"):
                # Flush current block and stop parsing further
                if current_date and current_prices is not None:
                    results.append((current_date, current_prices))
                break
            # Price line: allow optional space between time and value
            m = re.match(r"^(\d{2}):(\d{2})\s*([0-9.-]+)¢$", line)
            if m and current_prices is not None:
                hour = int(m.group(1))
                minute = int(m.group(2))
                cents = float(m.group(3))
                quarter = (minute // 15) + 1
                current_prices[(hour, quarter)] = cents
                # Do not spam too much; remove verbose per-line prints here
                continue
            # Otherwise ignore unknown lines

    # Flush last block if not yet appended
    if (
        current_date
        and current_prices is not None
        and (not results or results[-1][0] != current_date)
    ):
        results.append((current_date, current_prices))

    return results


def parse_test_prices(filename: str) -> Dict[Tuple[int, int], float]:
    """
    Backwards-compatible helper: return prices for the FIRST date block only.
    """
    all_blocks = parse_all_test_prices(filename)
    if not all_blocks:
        return {}
    return all_blocks[0][1]


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


def generate_mock_xml_response(
    expected_prices: Dict[Tuple[int, int], float], test_date: date
) -> str:
    """
    Generate a mock ENTSO-E XML response for testing.
    Convert expected prices (in cents) back to EUR/MWh for the XML.
    """
    vat_rate = 1.255

    # Calculate UTC times for the XML (Helsinki is UTC+3 in October)
    # For Helsinki date, UTC period starts at 21:00 previous day and ends at 21:00 on the date
    utc_start = test_date - timedelta(days=1)
    utc_end = test_date

    start_str = f"{utc_start.strftime('%Y-%m-%d')}T21:00Z"
    end_str = f"{utc_end.strftime('%Y-%m-%d')}T21:00Z"

    print(f"Generating XML for UTC period: {start_str} to {end_str}")

    # XML header
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
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
                <start>{start_str}</start>
                <end>{end_str}</end>
            </timeInterval>
            <resolution>PT15M</resolution>"""

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


def test_statistics_and_bar_graph_with_mocked_api():
    """
    Test statistics and bar graph functionality.
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

    # Parse test date from file
    test_date = parse_test_date("debug_electricity_mapping_prices.txt")

    # Generate mock XML response
    mock_xml = generate_mock_xml_response(expected_prices, test_date)

    # Create service
    service = ElectricityService("dummy_api_key")

    print(f"\nTesting statistics and bar graph functionality for {test_date}")
    print("=" * 60)

    # Mock the requests.get call
    with mock.patch("services.electricity_service.requests.get") as mock_get:
        # Setup mock response
        mock_response = mock.Mock()
        mock_response.text = mock_xml
        mock_response.raise_for_status = mock.Mock()
        mock_get.return_value = mock_response

        try:
            # Test statistics
            print("Testing get_price_statistics()...")
            stats = service.get_price_statistics(test_date)

            if stats.get("error"):
                print(f"  ERROR Statistics error: {stats.get('message')}")
                return False

            print(
                f"  OK Min price: {stats['min_price']['snt_per_kwh_with_vat']:.2f} snt/kWh at hour {stats['min_price']['hour']:02d}"
            )
            print(
                f"  OK Max price: {stats['max_price']['snt_per_kwh_with_vat']:.2f} snt/kWh at hour {stats['max_price']['hour']:02d}"
            )
            print(
                f"  OK Avg price: {stats['avg_price']['snt_per_kwh_with_vat']:.2f} snt/kWh"
            )

            # Test formatted statistics message with bar graph
            print("\nTesting format_statistics_message() with bar graph...")
            formatted_stats = service.format_statistics_message(stats)

            if "tilastojen haku epäonnistui" in formatted_stats:
                print(f"  ERROR Statistics formatting error: {formatted_stats}")
                return False

            # Check if bar graph is included (should have pipe separator and colored bars)
            if " | " in formatted_stats and "\x03" in formatted_stats:
                print("  OK Statistics message with bar graph generated successfully")
                print(f"  OK Length: {len(formatted_stats)} characters")
                # Show a sample of the message (without IRC color codes for readability)
                clean_msg = (
                    formatted_stats.replace("\x033", "G")
                    .replace("\x037", "Y")
                    .replace("\x034", "R")
                    .replace("\x03", "")
                )
                print(
                    f"  Sample: {clean_msg[:100]}{'...' if len(clean_msg) > 100 else ''}"
                )
            else:
                print("  ERROR Bar graph not found in statistics message")
                print(f"  Message: {formatted_stats[:200]}")
                return False

            # Test command parsing for stats
            print("\nTesting parse_command_args() for stats...")

            # Test "stats" command
            parsed_stats = service.parse_command_args(["stats"])
            if not parsed_stats.get("show_stats"):
                print("  ERROR Failed to parse 'stats' command")
                return False
            print("  OK 'stats' command parsed correctly")

            # Test "tilastot" command
            parsed_tilastot = service.parse_command_args(["tilastot"])
            if not parsed_tilastot.get("show_stats"):
                print("  ERROR Failed to parse 'tilastot' command")
                return False
            print("  OK 'tilastot' command parsed correctly")

            return True

        except Exception as e:
            print(f"  ERROR Exception during statistics test: {e}")
            import traceback

            traceback.print_exc()
            return False


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

    # Parse test date from file
    test_date = parse_test_date("debug_electricity_mapping_prices.txt")

    # Generate mock XML response
    mock_xml = generate_mock_xml_response(expected_prices, test_date)

    # Create service
    service = ElectricityService("dummy_api_key")

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
                    print(f"  ERROR Service error: {result.get('message')}")
                    failures.append((hour, expected_avg, None))
                    continue

                today_price = result.get("today_price", {})
                service_hourly_avg = today_price.get("hour_avg_snt_kwh")

                if service_hourly_avg is None:
                    print("  ERROR No hourly average returned by service")
                    failures.append((hour, expected_avg, None))
                    continue

                print(f"  Service hourly avg: {service_hourly_avg:.2f} snt/kWh")

                # Check if they match (within small tolerance)
                if abs(service_hourly_avg - expected_avg) < 0.01:
                    successes.append(hour)
                    print("  OK MATCH")
                else:
                    failures.append((hour, expected_avg, service_hourly_avg))
                    print("  ERROR MISMATCH")

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
                print(f"  ERROR Exception: {e}")
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
    Test the electricity service with mocked API response for all date blocks.
    """
    import unittest.mock as mock

    try:
        from services.electricity_service import ElectricityService
    except ImportError:
        print("Could not import ElectricityService")
        return False

    # Parse ALL dates and price blocks
    blocks = parse_all_test_prices("debug_electricity_mapping_prices.txt")
    print(f"\nParsed {len(blocks)} date sections with prices")

    # Create a mapping of date -> prices for easy lookup
    date_to_prices = {date_obj: prices for date_obj, prices in blocks}

    # Create service
    service = ElectricityService("dummy_api_key")

    overall_success = True

    for test_date, expected_prices in blocks:
        print(f"\n--- Testing electricity service with mocked API for {test_date} ---")
        print(f"Parsed {len(expected_prices)} expected price points")

        print("=" * 60)

        # Create a dynamic mock that returns different XML based on requested date range
        def mock_response_func(url, params=None, **kwargs):
            if params and "periodStart" in params:
                period_start = params["periodStart"]
                # Extract date from periodStart (format: YYYYMMDDHHMM)
                start_date_str = period_start[:8]  # YYYYMMDD
                # Convert to date object for comparison
                try:
                    # The period start is for the UTC day, so we need to map it to Helsinki date
                    # For Helsinki date X, UTC period is (X-1 day 21:00) to (X day 21:00)
                    # So if periodStart is YYYYMMDD2100, that's requesting Helsinki date YYYYMMDD+1
                    if period_start.endswith("2100"):
                        utc_date = datetime.strptime(start_date_str, "%Y%m%d").date()
                        helsinki_date = utc_date + timedelta(days=1)
                    else:
                        helsinki_date = datetime.strptime(
                            start_date_str, "%Y%m%d"
                        ).date()

                    # Find matching price data
                    if helsinki_date in date_to_prices:
                        prices = date_to_prices[helsinki_date]
                        xml_content = generate_mock_xml_response(prices, helsinki_date)
                        print(
                            f"    Mock API returning data for {helsinki_date} (period: {period_start})"
                        )
                    else:
                        # Return empty/error response for unknown dates
                        xml_content = '<?xml version="1.0" encoding="UTF-8"?><Publication_MarketDocument xmlns="urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:0"><mRID>no-data</mRID></Publication_MarketDocument>'
                        print(
                            f"    Mock API: No data for {helsinki_date} (period: {period_start})"
                        )

                except ValueError:
                    # Invalid date format, return empty response
                    xml_content = '<?xml version="1.0" encoding="UTF-8"?><Publication_MarketDocument xmlns="urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:0"><mRID>invalid</mRID></Publication_MarketDocument>'
            else:
                # Default response
                xml_content = generate_mock_xml_response(expected_prices, test_date)

            mock_response = mock.Mock()
            mock_response.text = xml_content
            mock_response.raise_for_status = mock.Mock()
            return mock_response

        # Mock the requests.get call with our dynamic function
        with mock.patch(
            "services.electricity_service.requests.get", side_effect=mock_response_func
        ) as mock_get:

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
                        print(f"  ERROR Service error: {result.get('message')}")
                        failures.append((hour, quarter, expected_cents, None))
                        continue

                    today_price = result.get("today_price", {})
                    quarter_prices_snt = today_price.get("quarter_prices_snt", {})
                    actual_cents = quarter_prices_snt.get(quarter)

                    if actual_cents is None:
                        print(f"  ERROR No price data for quarter {quarter}")
                        failures.append((hour, quarter, expected_cents, None))
                        continue

                    print(f"  Service returned: {actual_cents:.2f} snt/kWh")

                    # Check if they match (within small tolerance)
                    if abs(actual_cents - expected_cents) < 0.01:
                        successes.append((hour, quarter))
                        print("  OK MATCH")

                    else:
                        failures.append((hour, quarter, expected_cents, actual_cents))
                        print("  ERROR MISMATCH")

                except Exception as e:
                    print(f"  ERROR Exception: {e}")
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

            section_success = len(failures) == 0
            overall_success = overall_success and section_success

    return overall_success


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

    # Parse test date from file
    test_date = parse_test_date("debug_electricity_mapping_prices.txt")

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
            print("  OK MATCH")
        else:
            failures.append((hour, quarter, expected_cents, actual_snt_kwh))
            print("  ERROR MISMATCH")

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

    # Parse test date from file
    test_date = parse_test_date("debug_electricity_mapping_prices.txt")

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
    test_date = parse_test_date("debug_electricity_mapping_prices.txt")

    print(f"\nTesting service timezone diagnostics for {test_date}:")
    diag = service.diagnose_timezone_handling(test_date)

    for key, value in diag.items():
        print(f"  {key}: {value}")

    # Calculate expected values based on parsed date (UTC+3 in October)
    expected_start_date = test_date - timedelta(days=1)
    expected_end_date = test_date
    expected_api_start = (
        f"{expected_start_date.strftime('%Y%m%d')}2100"  # Previous day 21:00 UTC
    )
    expected_api_end = (
        f"{expected_end_date.strftime('%Y%m%d')}2100"  # Same day 21:00 UTC
    )

    print("\nValidation:")
    print(f"  Expected API start: {expected_api_start}")
    print(f"  Actual API start:   {diag['api_period_start']}")
    print(f"  Expected API end:   {expected_api_end}")
    print(f"  Actual API end:     {diag['api_period_end']}")

    start_match = diag["api_period_start"] == expected_api_start
    end_match = diag["api_period_end"] == expected_api_end

    if start_match and end_match:
        print("  OK Timezone handling is correct")
        return True
    else:
        print("  ERROR Timezone handling has issues")
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

    # Run the statistics and bar graph test
    print("\n" + "=" * 50)
    print("PHASE 5: Testing statistics and bar graph")
    print("=" * 50)
    success4 = test_statistics_and_bar_graph_with_mocked_api()

    print("\n" + "=" * 50)
    print("FINAL RESULTS")
    print("=" * 50)

    if success_tz:
        print("OK Timezone diagnostics: PASSED")
    else:
        print("ERROR Timezone diagnostics: FAILED")

    if success1:
        print("OK Conversion logic: PASSED")
    else:
        print("ERROR Conversion logic: FAILED")

    if success2:
        print("OK Mocked API test: PASSED")
    else:
        print("ERROR Mocked API test: FAILED")

    if success3:
        print("OK Hourly averages test: PASSED")
    else:
        print("ERROR Hourly averages test: FAILED")

    if success4:
        print("OK Statistics and bar graph test: PASSED")
    else:
        print("ERROR Statistics and bar graph test: FAILED")

    if success_tz and success1 and success2 and success3 and success4:
        print("\n🎉 All tests passed!")
    else:
        print("\nERROR Some tests failed - service needs fixing")
