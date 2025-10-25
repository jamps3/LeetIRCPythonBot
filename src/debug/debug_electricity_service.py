#!/usr/bin/env python3
"""
Debug script for electricity service issues.
Use this when the service is returning incorrect prices.
"""

import sys
from datetime import date, datetime
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from services.electricity_service import ElectricityService


def main():
    if len(sys.argv) < 2:
        print(
            "Usage: python debug_electricity_service.py <API_KEY> [date] [hour] [quarter]"
        )
        print("  date format: YYYY-MM-DD (defaults to today)")
        print("  hour: 0-23 (defaults to current hour)")
        print("  quarter: 1-4 (defaults to current quarter)")
        sys.exit(1)

    api_key = sys.argv[1]

    # Parse arguments
    test_date = date.today()
    test_hour = datetime.now().hour
    test_quarter = (datetime.now().minute // 15) + 1

    if len(sys.argv) > 2:
        test_date = datetime.strptime(sys.argv[2], "%Y-%m-%d").date()

    if len(sys.argv) > 3:
        test_hour = int(sys.argv[3])

    if len(sys.argv) > 4:
        test_quarter = int(sys.argv[4])

    print("Debugging electricity service for:")
    print(f"  Date: {test_date}")
    print(f"  Time: {test_hour:02d}:{(test_quarter-1)*15:02d} (Q{test_quarter})")
    print("=" * 60)

    # Create service
    service = ElectricityService(api_key)

    # 1. Timezone diagnostics
    print("1. TIMEZONE DIAGNOSTICS")
    print("-" * 30)
    diag = service.diagnose_timezone_handling(test_date)
    for key, value in diag.items():
        print(f"  {key}: {value}")

    # 2. Cache info
    print("\n2. CACHE INFO")
    print("-" * 30)
    cache_info = service.get_cache_info()
    if cache_info:
        for date_key, info in cache_info.items():
            print(f"  {date_key}: {info}")
    else:
        print("  Cache is empty")

    # 3. Clear cache and fetch fresh data
    print("\n3. FRESH API CALL")
    print("-" * 30)
    service.clear_cache()

    try:
        result = service.get_electricity_price(
            hour=test_hour, quarter=test_quarter, date=test_date
        )

        if result.get("error"):
            print(f"  ERROR: {result.get('message')}")
        else:
            print("  SUCCESS!")
            today_price = result.get("today_price", {})

            # Show requested quarter price
            quarter_prices = today_price.get("quarter_prices_snt", {})
            requested_price = quarter_prices.get(test_quarter)

            if requested_price:
                print(f"  Requested quarter price: {requested_price:.2f} snt/kWh")
            else:
                print(f"  No data for quarter {test_quarter}")

            # Show all quarter prices for the hour
            print(f"  All quarters for hour {test_hour:02d}:")
            for q in [1, 2, 3, 4]:
                price = quarter_prices.get(q)
                if price:
                    minute = (q - 1) * 15
                    print(
                        f"    {test_hour:02d}:{minute:02d} (Q{q}): {price:.2f} snt/kWh"
                    )
                else:
                    print(f"    Q{q}: No data")

    except Exception as e:
        print(f"  EXCEPTION: {e}")

    # 4. Cache info after fetch
    print("\n4. CACHE AFTER FETCH")
    print("-" * 30)
    cache_info = service.get_cache_info()
    if cache_info:
        for date_key, info in cache_info.items():
            print(f"  {date_key}: {info}")
    else:
        print("  Cache is still empty (unexpected)")


if __name__ == "__main__":
    main()
