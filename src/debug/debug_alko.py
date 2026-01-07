"""
Debug script for Alko service functionality.

This script contains various tests and debugging utilities for the Alko service,
including the fix for the product #83 search issue.
"""

import sys

sys.path.insert(0, "src")
import argparse

from services.alko_service import AlkoService


def test_product_83_issue():
    """Test the fix for the product 83 issue."""
    print("Testing product 83 issue fix...")
    service = AlkoService()

    # Test searching for "83"
    result1 = service.get_product_by_number("83")
    print(f'Search for "83": {result1["number"] if result1 else "Not found"}')

    # Test searching for "000083"
    result2 = service.get_product_by_number("000083")
    print(f'Search for "000083": {result2["number"] if result2 else "Not found"}')

    if result1 and result2:
        print(f"✅ Both searches found: {result1['number']} - {result1['name']}")
    else:
        print("❌ Issue not resolved")


def test_partial_matching():
    """Test partial matching functionality."""
    print("\nTesting partial matching...")
    service = AlkoService()

    test_cases = ["8", "83", "183", "3083", "13083"]
    for test_case in test_cases:
        result = service.get_product_by_number(test_case)
        if result:
            print(f'Search for "{test_case}": {result["number"]} - {result["name"]}')
        else:
            print(f'Search for "{test_case}": Not found')


def test_exact_matching():
    """Test that exact matching still works."""
    print("\nTesting exact matching...")
    service = AlkoService()

    # Test with a known product number
    if service.products_cache:
        sample_product = service.products_cache[0]
        exact_number = sample_product["number"]
        result = service.get_product_by_number(exact_number)
        if result and result["number"] == exact_number:
            print(f"✅ Exact match works: {exact_number}")
        else:
            print(f"❌ Exact match failed for: {exact_number}")


def test_edge_cases():
    """Test edge cases."""
    print("\nTesting edge cases...")
    service = AlkoService()

    # Test leading zeros
    result1 = service.get_product_by_number("0083")
    result2 = service.get_product_by_number("00083")
    if result1 and result2 and result1["number"] == result2["number"]:
        print(f"✅ Leading zeros handled correctly: {result1['number']}")
    else:
        print("❌ Leading zeros test failed")

    # Test non-existent product
    result = service.get_product_by_number("999999")
    if result is None:
        print("✅ Non-existent product returns None")
    else:
        print(f"❌ Non-existent product should return None, got: {result['number']}")


def test_cache_stats():
    """Show cache statistics."""
    print("\nCache statistics:")
    service = AlkoService()
    stats = service.get_stats()
    print(f"Total products: {stats['total_products']}")
    print(f"Cache file: {stats['cache_file']}")

    # Count products ending with 83
    if service.products_cache:
        products_ending_with_83 = [
            p for p in service.products_cache if p["number"].endswith("83")
        ]
        print(f"Products ending with '83': {len(products_ending_with_83)}")
        if products_ending_with_83:
            print("Examples:")
            for p in products_ending_with_83[:5]:
                print(f"  {p['number']}: {p['name']}")


def search_products(query: str, show_all: bool = False):
    """Search for products by name and show results."""
    print(f"🔍 Searching for products matching: '{query}'")
    print("-" * 60)

    service = AlkoService()

    if not service.products_cache:
        print("❌ No product data available")
        return

    # Search with a high limit to get all matches
    limit = 1000 if show_all else 10
    matches = service.search_products(query, limit=limit)

    if not matches:
        print(f"❌ No products found matching '{query}'")
        return

    print(
        f"✅ Found {len(matches)} matching product{'s' if len(matches) != 1 else ''}:"
    )

    for i, product in enumerate(matches, 1):
        number = product.get("number", "N/A")
        name = product.get("name", "Unknown")
        bottle_size = product.get("bottle_size_raw", "N/A")
        alcohol_percent = product.get("alcohol_percent", "N/A")
        price = product.get("price", "N/A")

        print(f"{i:2d}. {number}: {name}")
        print(
            f"    Size: {bottle_size} | Alcohol: {alcohol_percent}% | Price: {price}€"
        )
        print()

    if not show_all and len(matches) >= limit:
        print(f"💡 Showing first {limit} results. Use --all to show all matches.")


def check_excel_file():
    """Check Excel file contents and search for specific products."""
    import pandas as pd

    print("📊 Checking Excel file contents...")
    print("-" * 50)

    excel_path = "data/alkon-hinnasto-tekstitiedostona.xlsx"

    try:
        # Read the first sheet
        df = pd.read_excel(excel_path, header=None, engine="openpyxl")

        print(f"Total rows: {len(df)}")

        # Check the header row (first few rows)
        print("First 10 rows (potential headers):")
        for i in range(min(10, len(df))):
            row = df.iloc[i]
            row_str = " | ".join(str(val) for val in row if pd.notna(val))
            print(f"Row {i+1}: {row_str}")

        # Find header row by looking for "Nimi" or "Numero"
        header_row = None
        for i in range(min(20, len(df))):
            row = df.iloc[i]
            row_values = [str(val).strip() for val in row.values if pd.notna(val)]
            if any("Nimi" in val or "Numero" in val for val in row_values):
                header_row = i
                break

        print(
            f"\nDetected header row: {header_row + 1 if header_row is not None else 'None'}"
        )

        # Search for rows containing 'paperikassi'
        paperikassi_rows = []
        for idx, row in df.iterrows():
            row_str = " ".join(str(val) for val in row if pd.notna(val)).lower()
            if "paperikassi" in row_str:
                paperikassi_rows.append(idx + 1)  # 1-indexed

        print(f"\nRows containing 'paperikassi': {paperikassi_rows}")

        # Search for '000083'
        num_000083_rows = []
        for idx, row in df.iterrows():
            row_str = " ".join(str(val) for val in row if pd.notna(val))
            if "000083" in row_str:
                num_000083_rows.append(idx + 1)  # 1-indexed

        print(f"Rows containing '000083': {num_000083_rows}")

    except Exception as e:
        print(f"❌ Error checking Excel file: {e}")


def check_cache_products():
    """Check cache for products containing specific keywords."""
    print("🔍 Checking cache for products...")
    print("-" * 50)

    try:
        import json

        with open("data/alko_cache.json", "r", encoding="utf-8") as f:
            data = json.load(f)

        products = data["products"]

        # Search for "paperikassi"
        matches = [p for p in products if "paperikassi" in p.get("name", "").lower()]

        print(f'Found {len(matches)} products containing "paperikassi":')
        for p in matches[:10]:  # Show first 10
            print(f'  {p.get("number", "N/A")}: {p.get("name", "Unknown")}')

        if len(matches) > 10:
            print(f"  ... and {len(matches) - 10} more")

        # Also check for partial matches
        partial_matches = [
            p
            for p in products
            if any(word in p.get("name", "").lower() for word in ["paperi", "kassi"])
        ]
        print(
            f'\nFound {len(partial_matches)} products containing "paperi" or "kassi":'
        )
        for p in partial_matches[:10]:
            print(f'  {p.get("number", "N/A")}: {p.get("name", "Unknown")}')

    except Exception as e:
        print(f"❌ Error checking cache: {e}")


def force_update_alko():
    """Force update of Alko data."""
    print("🔄 Forcing update of Alko data...")
    print("-" * 50)

    service = AlkoService()
    success = service.update_data(force=True)
    print(f"Update success: {success}")

    if success:
        print(f"New cache has {len(service.products_cache)} products")

        # Check if 000083 is now in cache
        product = service.get_product_by_number("000083")
        if product:
            print(f"✅ Found product 000083: {product['name']}")
        else:
            print("❌ Still not found")
    else:
        print("❌ Update failed")


def main():
    """Run debug tests or search functionality based on command line arguments."""
    parser = argparse.ArgumentParser(description="Alko Service Debug Script")
    parser.add_argument("query", nargs="?", help="Search query for products")
    parser.add_argument(
        "--all", "-a", action="store_true", help="Show all search results (not limited)"
    )
    parser.add_argument("--test", "-t", action="store_true", help="Run all debug tests")
    parser.add_argument(
        "--excel", "-e", action="store_true", help="Check Excel file contents"
    )
    parser.add_argument(
        "--cache", "-c", action="store_true", help="Check cache for products"
    )
    parser.add_argument(
        "--update", "-u", action="store_true", help="Force update Alko data"
    )

    args = parser.parse_args()

    if args.test:
        # Test mode
        print("🔍 Alko Service Debug Script - Test Mode")
        print("=" * 50)

        test_product_83_issue()
        test_partial_matching()
        test_exact_matching()
        test_edge_cases()
        test_cache_stats()

        print("\n🎉 Debug script completed!")
    elif args.excel:
        # Check Excel file
        check_excel_file()
    elif args.cache:
        # Check cache
        check_cache_products()
    elif args.update:
        # Force update
        force_update_alko()
    elif args.query:
        # Search mode
        search_products(args.query, show_all=args.all)
    else:
        # Default: show help
        parser.print_help()


if __name__ == "__main__":
    main()
