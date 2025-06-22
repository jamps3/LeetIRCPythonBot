#!/usr/bin/env python3
"""
Test script to verify Eurojackpot service debugging and API calls.
"""
import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print(f"DEBUG_MODE: {os.getenv('DEBUG_MODE')}")
print(f"EUROJACKPOT_API_KEY exists: {bool(os.getenv('EUROJACKPOT_API_KEY'))}")

# Set up logging to see debug output
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')

from services.eurojackpot_service import get_eurojackpot_service

print("\n=== Initializing Eurojackpot Service ===")
service = get_eurojackpot_service()

print("\n=== Testing next draw info ===")
result = service.get_next_draw_info()
print(f"Result: {result}")

print("\n=== Testing latest results ===")
result = service.get_last_results()
print(f"Result: {result}")

print("\n=== Testing scrape functionality ===")
result = service.scrape_all_draws(start_year=2024, max_draws=5)  # Small test
print(f"Scrape result: {result}")

print("\n=== Testing database stats ===")
result = service.get_database_stats()
print(f"Database stats: {result}")

print("\n=== Testing combined info ===")
result = service.get_combined_info()
print(f"Result: {result}")

print("\n=== Testing with a date query ===")
result = service.get_draw_by_date("20.12.24")
print(f"Result: {result}")
