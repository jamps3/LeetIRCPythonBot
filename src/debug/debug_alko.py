"""
Debug script for Alko service functionality.

This script contains various tests and debugging utilities for the Alko service,
including the fix for the product #83 search issue.
"""

import sys

sys.path.insert(0, "src")
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


def main():
    """Run all debug tests."""
    print("🔍 Alko Service Debug Script")
    print("=" * 50)

    test_product_83_issue()
    test_partial_matching()
    test_exact_matching()
    test_edge_cases()
    test_cache_stats()

    print("\n🎉 Debug script completed!")


if __name__ == "__main__":
    main()
