#!/usr/bin/env python3
"""
Test script to verify electricity price mapping for specific hours.
Tests hours 0, 1, 15, 16, 23, and 24 for today and tomorrow.
"""

import os
import sys
from datetime import datetime, timedelta

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

# Add the services directory to path to import directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "services"))
from electricity_service import ElectricityService


def test_electricity_mapping():
    """Test electricity price mapping for specific hours."""

    # Get API key from environment
    api_key = os.getenv("ELECTRICITY_API_KEY")
    if not api_key:
        print("ERROR: ELECTRICITY_API_KEY environment variable not set")
        print("Please set your ENTSO-E API key in the environment")
        return
    # Ask user for expected prices
    print("Please enter the CORRECT expected prices (c/kWh with VAT):")
    print("=" * 60)

    expected_prices = {"today": {}, "tomorrow": {}}
    test_hours = [0, 1, 23]

    for day in ["today", "tomorrow"]:
        print(f"\n📅 Expected prices for {day.upper()}:")
        for hour in test_hours:
            while True:
                try:
                    price = float(input(f"  Hour {hour:02d}: "))
                    expected_prices[day][hour] = price
                    break
                except ValueError:
                    print("  Please enter a valid number.")

    # Initialize service
    service = ElectricityService(api_key)

    # Test hours
    test_hours = [0, 1, 23]
    current_date = datetime.now()

    print(
        f"Testing electricity price mapping on {current_date.strftime('%Y-%m-%d %H:%M:%S')}"
    )
    print("=" * 80)

    for hour in test_hours:
        print(f"\n🕐 Testing Hour {hour}")
        print("-" * 40)

        try:
            result = service.get_electricity_price(
                hour=hour, date=current_date, include_tomorrow=True
            )

            if result.get("error"):
                print(f"❌ Error: {result.get('message', 'Unknown error')}")
                continue

            # Today's price
            today_price = result.get("today_price")
            if today_price:
                snt_per_kwh_today = today_price["snt_per_kwh_with_vat"]
                expected_today = expected_prices["today"].get(hour, None)
                if expected_today is not None:
                    if abs(snt_per_kwh_today - expected_today) > 0.01:
                        print(
                            f"⚠️ Mismatch for Today at hour {hour}: Got {snt_per_kwh_today:.2f} c/kWh, Expected {expected_today:.2f} c/kWh"
                        )
                print(f"📅 Today ({result['date']}) at hour {hour}:")
                print(f"   💰 {snt_per_kwh_today:.2f} c/kWh (with VAT)")
                print(f"   📊 {today_price['eur_per_mwh']:.2f} EUR/MWh")
            else:
                print(f"📅 Today ({result['date']}) at hour {hour}: No price available")

            # Tomorrow's price
            tomorrow_price = result.get("tomorrow_price")
            if tomorrow_price and result.get("tomorrow_available"):
                from datetime import timedelta as td

                tomorrow_date = (
                    current_date.replace(hour=0, minute=0, second=0, microsecond=0)
                    + td(days=1)
                ).strftime("%Y-%m-%d")
                snt_per_kwh_tomorrow = tomorrow_price["snt_per_kwh_with_vat"]
                expected_tomorrow = expected_prices["tomorrow"].get(hour, None)
                if expected_tomorrow is not None:
                    if abs(snt_per_kwh_tomorrow - expected_tomorrow) > 0.01:
                        print(
                            f"⚠️ Mismatch for Tomorrow at hour {hour}: Got {snt_per_kwh_tomorrow:.2f} c/kWh, Expected {expected_tomorrow:.2f} c/kWh"
                        )
                print(f"📅 Tomorrow ({tomorrow_date}) at hour {hour}:")
                print(f"   💰 {snt_per_kwh_tomorrow:.2f} c/kWh (with VAT)")
                print(f"   📊 {tomorrow_price['eur_per_mwh']:.2f} EUR/MWh")
            else:
                print(f"📅 Tomorrow at hour {hour}: No price available")

        except Exception as e:
            print(f"❌ Exception testing hour {hour}: {str(e)}")

    print("\n" + "=" * 80)
    print("🔍 Testing raw daily data to verify position mapping...")
    print("=" * 80)

    # Test raw daily prices to understand the data structure
    try:
        # Get yesterday's data
        yesterday = current_date - timedelta(days=1)
        yesterday_data = service.get_daily_prices(yesterday)

        # Get today's data
        today_data = service.get_daily_prices(current_date)

        # Get tomorrow's data
        tomorrow = current_date + timedelta(days=1)
        tomorrow_data = service.get_daily_prices(tomorrow)

        print("\n📊 Raw data analysis:")
        print(f"Yesterday ({yesterday.strftime('%Y-%m-%d')}):")
        if not yesterday_data.get("error"):
            positions = sorted(yesterday_data["prices"].keys())
            print(f"   Available positions: {positions}")
            if 24 in yesterday_data["prices"]:
                print(
                    f"   Position 24: {yesterday_data['prices'][24]:.2f} EUR/MWh (should be today's hour 0)"
                )

        print(f"\nToday ({current_date.strftime('%Y-%m-%d')}):")
        if not today_data.get("error"):
            positions = sorted(today_data["prices"].keys())
            print(f"   Available positions: {positions}")
            if 1 in today_data["prices"]:
                print(
                    f"   Position 1: {today_data['prices'][1]:.2f} EUR/MWh (should be today's hour 1)"
                )
            if 15 in today_data["prices"]:
                print(
                    f"   Position 15: {today_data['prices'][15]:.2f} EUR/MWh (should be today's hour 15)"
                )
            if 24 in today_data["prices"]:
                print(
                    f"   Position 24: {today_data['prices'][24]:.2f} EUR/MWh (should be tomorrow's hour 0)"
                )

        print(f"\nTomorrow ({tomorrow.strftime('%Y-%m-%d')}):")
        if not tomorrow_data.get("error"):
            positions = sorted(tomorrow_data["prices"].keys())
            print(f"   Available positions: {positions}")
            if 1 in tomorrow_data["prices"]:
                print(
                    f"   Position 1: {tomorrow_data['prices'][1]:.2f} EUR/MWh (should be tomorrow's hour 1)"
                )
            if 15 in tomorrow_data["prices"]:
                print(
                    f"   Position 15: {tomorrow_data['prices'][15]:.2f} EUR/MWh (should be tomorrow's hour 15)"
                )
        else:
            print(
                f"   Error or no data: {tomorrow_data.get('message', 'Unknown error')}"
            )

    except Exception as e:
        print(f"❌ Error analyzing raw data: {str(e)}")


if __name__ == "__main__":
    test_electricity_mapping()
