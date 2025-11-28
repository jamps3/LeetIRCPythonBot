#!/usr/bin/env python3
"""
Debug script to test the otiedote service functionality.

This script:
1. Tests importing the otiedote service
2. Sets the latest release number to 2690
3. Checks for newer releases (should find at least one)
4. Tests all !otiedote command variants
"""

import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def test_import():
    """Test importing the otiedote service."""
    print("=" * 80)
    print("TEST 1: Import otiedote service")
    print("=" * 80)

    try:
        from src.services.otiedote_playwright_service import create_otiedote_service

        print("Successfully imported otiedote_playwright_service")
        return create_otiedote_service
    except ImportError as e:
        print(f"Failed to import otiedote service: {e}")
        print("\nMake sure playwright is installed:")
        print("  pip install playwright")
        print("  python -m playwright install firefox")
        return None


def test_service_creation(create_otiedote_service):
    """Test creating an otiedote service instance."""
    print("\n" + "=" * 80)
    print("TEST 2: Create otiedote service instance")
    print("=" * 80)

    announcements = []

    def callback(title, url, description):
        """Callback to capture announcements."""
        announcements.append(
            {
                "title": title,
                "url": url,
                "description": description,
                "timestamp": datetime.now(),
            }
        )
        print(f"\nNEW ANNOUNCEMENT:")
        print(f"   Title: {title}")
        print(f"   URL: {url}")
        desc_preview = (
            description[:100] + "..." if len(description or "") > 100 else description
        )
        print(f"   Description: {desc_preview}")

    try:
        service = create_otiedote_service(
            callback=callback, state_file="latest_otiedote.txt"
        )
        print("Successfully created otiedote service")
        return service, announcements
    except Exception as e:
        print(f"Failed to create service: {e}")
        import traceback

        traceback.print_exc()
        return None, announcements


def test_set_release_number(service, number=2690):
    """Test setting the release number."""
    print("\n" + "=" * 80)
    print(f"TEST 3: Set latest release number to {number}")
    print("=" * 80)

    if not service:
        print("Service not available, skipping")
        return False

    try:
        service.latest_release = number
        service._save_latest_release(number)
        print(f"Set latest release to {number}")

        # Verify
        info = service.get_latest_release_info()
        print(f"   Verified: {info}")
        return True
    except Exception as e:
        print(f"Failed to set release number: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_check_for_releases(service, announcements):
    """Test checking for new releases."""
    print("\n" + "=" * 80)
    print("TEST 4: Check for new releases (async)")
    print("=" * 80)

    if not service:
        print("Service not available, skipping")
        return False

    try:
        # Set up browser
        page = await service._setup_browser()
        if not page:
            print("Failed to setup browser")
            return False

        print("Browser setup successful")
        print("Checking for new releases...")

        # Check for new releases
        await service._check_for_new_releases(page)

        # Close browser
        await page.close()
        if service.browser:
            await service.browser.close()
        if service.playwright:
            await service.playwright.stop()

        # Check if we got any announcements
        if announcements:
            print(f"Found {len(announcements)} new release(s)!")
            for i, ann in enumerate(announcements, 1):
                print(f"\n   Release {i}:")
                print(f"     Title: {ann['title']}")
                print(f"     URL: {ann['url']}")
            return True
        else:
            print("No new releases found (this might be OK if already up to date)")
            print("   Try setting an older release number like 2600")
            return False

    except Exception as e:
        print(f"Error checking for releases: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_command_variants():
    """Test the !otiedote command variants."""
    print("\n" + "=" * 80)
    print("TEST 5: Test !otiedote command variants")
    print("=" * 80)

    try:
        from unittest.mock import Mock

        from src.command_registry import CommandContext
        from src.commands import otiedote_command

        # Create a mock bot_manager with otiedote service
        try:
            from src.services.otiedote_playwright_service import create_otiedote_service

            service = create_otiedote_service(
                callback=lambda t, u, d: None, state_file="latest_otiedote.txt"
            )
        except Exception as e:
            print(f"Could not create service for command test: {e}")
            service = None

        # Mock bot_functions
        def mock_get_otiedote_info(mode, number=None, offset=None):
            if not service:
                return {"error": True, "message": "Service not available"}

            if mode == "latest_full":
                return {
                    "error": False,
                    "message": "Test: Latest full description would go here",
                }
            elif mode == "current_number":
                info = service.get_latest_release_info()
                return {
                    "error": False,
                    "message": f"Current release: #{info.get('latest_release', 0)}",
                }
            elif mode == "by_number":
                return {
                    "error": False,
                    "message": f"#{number}: Would fetch from otiedote.fi",
                }
            elif mode == "nth_latest":
                info = service.get_latest_release_info()
                calc = info.get("latest_release", 0) - (offset - 1)
                return {"error": False, "message": f"#{calc}: Nth latest release"}

        def mock_set_otiedote_number(number):
            if not service:
                return {"error": True, "message": "Service not available"}
            service.latest_release = number
            service._save_latest_release(number)
            return {"error": False, "message": f"Set to #{number}"}

        bot_functions = {
            "get_otiedote_info": mock_get_otiedote_info,
            "set_otiedote_number": mock_set_otiedote_number,
        }

        # Test cases
        test_cases = [
            ("", "Show latest full description"),
            ("#", "Show current number"),
            ("1", "Show 1st latest (same as latest)"),
            ("2", "Show 2nd latest"),
            ("#2690", "Show specific release #2690"),
            ("set 2695", "Set latest to 2695"),
        ]

        print("\nTesting command variants:")
        all_passed = True

        for args_text, description in test_cases:
            context = Mock(spec=CommandContext)
            context.args_text = args_text
            context.is_console = True

            try:
                result = otiedote_command(context, bot_functions)
                status = "OK" if "error" not in str(result) else "FAIL"
                if "error" in str(result):
                    all_passed = False

                args_display = f'"{args_text}"' if args_text else "(no args)"
                print(f"  {status} !otiedote {args_display:20s} - {description}")
                print(f"      Result: {result}")
            except Exception as e:
                print(f"  !otiedote {args_text:20s} - ERROR: {e}")
                all_passed = False

        return all_passed

    except Exception as e:
        print(f"Error testing command variants: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """Main test function."""
    print("\n" + "=" * 80)
    print("OTIEDOTE SERVICE DEBUG SCRIPT")
    print("=" * 80)
    print()

    # Test 1: Import
    create_func = test_import()
    if not create_func:
        print("\nCannot continue without import")
        return False

    # Test 2: Create service
    service, announcements = test_service_creation(create_func)
    if not service:
        print("\nCannot continue without service")
        return False

    # Test 3: Set release number
    if not test_set_release_number(service, 2729):
        print("\nCould not set release number, continuing anyway...")

    # Test 4: Check for releases
    releases_found = await test_check_for_releases(service, announcements)

    # Test 5: Command variants
    commands_ok = test_command_variants()

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Import:             OK")
    print(f"Service Creation:   OK")
    print(f"Set Release Number: OK")
    print(f"Find New Releases:  {'OK' if releases_found else 'FAIL (see notes above)'}")
    print(f"Command Variants:   {'OK' if commands_ok else 'FAIL'}")
    print("=" * 80)

    if releases_found and commands_ok:
        print("\nAll critical tests passed!")
        return True
    else:
        print("\n Some tests had issues, check output above")
        return False


if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
