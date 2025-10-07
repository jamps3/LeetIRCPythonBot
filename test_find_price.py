#!/usr/bin/env python3
"""
Script to explore ENTSO-E API data and find the 1.76 c/kWh price.
"""

import os
import sys
from datetime import datetime, timedelta

from services.electricity_service import ElectricityService

# Load environment variables from .env file
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # If python-dotenv is not available, try to load manually
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    key, value = line.strip().split("=", 1)
                    # Remove quotes from value if present
                    value = value.strip("\"'")
                    os.environ[key.strip()] = value


def convert_to_cents(eur_per_mwh):
    """Convert EUR/MWh to c/kWh with VAT."""
    return (eur_per_mwh / 10) * 1.255


def find_price_target():
    """Find where the 1.76 c/kWh price might be in the API data."""

    # Get API key from environment
    api_key = os.getenv("ELECTRICITY_API_KEY")
    if not api_key:
        print("ERROR: ELECTRICITY_API_KEY environment variable not set")
        return

    # Initialize service
    service = ElectricityService(api_key)

    # Target price we're looking for
    target_cents = 1.76
    target_eur_mwh = target_cents / 1.255 * 10  # ≈ 14.02 EUR/MWh

    print(
        f"🎯 Looking for price: {target_cents:.2f} c/kWh (≈ {target_eur_mwh:.2f} EUR/MWh)"
    )
    print("=" * 80)

    current_date = datetime.now()

    # Check multiple days around current date
    dates_to_check = [
        current_date - timedelta(days=2),  # Day before yesterday
        current_date - timedelta(days=1),  # Yesterday
        current_date,  # Today
        current_date + timedelta(days=1),  # Tomorrow
        current_date + timedelta(days=2),  # Day after tomorrow
    ]

    for check_date in dates_to_check:
        print(
            f"\n📅 Checking {check_date.strftime('%Y-%m-%d')} ({check_date.strftime('%A')}):"
        )

        try:
            daily_prices = service._fetch_daily_prices(check_date)

            if daily_prices.get("error"):
                print(f"   ❌ Error: {daily_prices.get('message')}")
                continue

            prices = daily_prices.get("prices", {})
            if not prices:
                print("   ❌ No price data available")
                continue

            # Check all positions for this date
            found_matches = []
            for position in range(1, 25):
                if position in prices:
                    eur_mwh = prices[position]
                    cents_kwh = convert_to_cents(eur_mwh)

                    # Check if this matches our target (within 0.01 c/kWh tolerance)
                    if abs(cents_kwh - target_cents) < 0.01:
                        hour = position if position != 24 else 0
                        found_matches.append((position, hour, eur_mwh, cents_kwh))
                        print(
                            f"   🎯 MATCH! Position {position} (Hour {hour}): {eur_mwh:.2f} EUR/MWh = {cents_kwh:.2f} c/kWh"
                        )

            if not found_matches:
                # Show all prices for this day
                print("   📊 All positions for this day:")
                for position in range(1, 25):
                    if position in prices:
                        eur_mwh = prices[position]
                        cents_kwh = convert_to_cents(eur_mwh)
                        hour = position if position != 24 else 0
                        print(
                            f"      Position {position:2d} (Hour {hour:2d}): {eur_mwh:6.2f} EUR/MWh = {cents_kwh:5.2f} c/kWh"
                        )

        except Exception as e:
            print(f"   ❌ Exception: {str(e)}")

    print("\n" + "=" * 80)
    print("🔍 Summary:")
    print(f"   Target: {target_cents:.2f} c/kWh (≈ {target_eur_mwh:.2f} EUR/MWh)")
    print("   If no matches found above, the expected value might be from:")
    print("   • A different time period")
    print("   • A different API endpoint or parameter")
    print("   • Manual calculation or external source")


if __name__ == "__main__":
    find_price_target()
