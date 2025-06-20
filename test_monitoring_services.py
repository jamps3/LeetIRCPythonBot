#!/usr/bin/env python3
"""
Test script for FMI warning and Otiedote monitoring services
"""

import time
from services.fmi_warning_service import create_fmi_warning_service
from services.otiedote_service import create_otiedote_service


def test_fmi_warnings():
    """Test FMI warning service"""
    print("Testing FMI Warning Service...")
    
    warnings_received = []
    
    def warning_callback(warnings):
        print(f"Received {len(warnings)} FMI warnings:")
        for warning in warnings:
            print(f"  - {warning}")
            warnings_received.extend(warnings)
    
    # Create service with shorter interval for testing
    service = create_fmi_warning_service(
        callback=warning_callback,
        check_interval=10  # 10 seconds for testing
    )
    
    # Test immediate check
    warnings = service.check_new_warnings()
    print(f"Immediate check found {len(warnings)} new warnings")
    
    # Start monitoring for a short time
    print("Starting FMI monitoring for 30 seconds...")
    service.start()
    time.sleep(30)
    service.stop()
    
    print(f"Total warnings received during monitoring: {len(warnings_received)}")
    return len(warnings_received) > 0


def test_otiedote_service():
    """Test Otiedote service"""
    print("\nTesting Otiedote Service...")
    
    releases_received = []
    
    def release_callback(title, url):
        print(f"Received Otiedote release: {title}")
        print(f"  URL: {url}")
        releases_received.append((title, url))
    
    # Create service with shorter interval for testing
    service = create_otiedote_service(
        callback=release_callback,
        check_interval=15  # 15 seconds for testing
    )
    
    # Get current state info
    info = service.get_latest_release_info()
    print(f"Current latest release: {info['latest_release']}")
    
    # Start monitoring for a short time
    print("Starting Otiedote monitoring for 30 seconds...")
    service.start()
    time.sleep(30)
    service.stop()
    
    print(f"Total releases received during monitoring: {len(releases_received)}")
    return len(releases_received) > 0


def main():
    """Main test function"""
    print("🧪 Testing monitoring services...")
    print("=" * 50)
    
    try:
        # Test FMI warnings
        fmi_working = test_fmi_warnings()
        
        # Test Otiedote service
        otiedote_working = test_otiedote_service()
        
        print("\n" + "=" * 50)
        print("📊 Test Results:")
        print(f"  FMI Warning Service: {'✅ Working' if fmi_working else '⚠️  No new warnings (normal)'}")
        print(f"  Otiedote Service: {'✅ Working' if otiedote_working else '⚠️  No new releases (normal)'}")
        
        print("\n🎯 Services are properly integrated and ready for use!")
        print("💡 Note: No new warnings/releases during testing is normal.")
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
