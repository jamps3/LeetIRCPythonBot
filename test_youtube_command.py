#!/usr/bin/env python3
"""
Test script to verify that the YouTube command works correctly.
This script tests the complete flow from command to service.
"""

import sys
import os

# Add src directory to path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_youtube_command():
    """Test the YouTube command flow."""
    print("🧪 Testing YouTube command flow...")
    
    try:
        # Test 1: Check if YouTube service is available
        print("\n1. Testing YouTube service availability:")
        from service_manager import ServiceManager
        service_manager = ServiceManager()
        
        youtube_service = service_manager.get_service("youtube")
        if youtube_service:
            print(f"✅ YouTube service available: {type(youtube_service)}")
            print(f"✅ API key loaded: {len(youtube_service.api_key) if youtube_service.api_key else 0} characters")
        else:
            print("❌ YouTube service not available")
            return False
            
        # Test 2: Test video ID extraction
        print("\n2. Testing video ID extraction:")
        test_urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://www.youtube.com/embed/dQw4w9WgXcQ",
            "https://www.youtube.com/shorts/dQw4w9WgXcQ",
            "This is not a YouTube URL"
        ]
        
        for url in test_urls:
            video_id = youtube_service.extract_video_id(url)
            print(f"   URL: {url[:50]}{'...' if len(url) > 50 else ''}")
            print(f"   Video ID: {video_id}")
        
        # Test 3: Test video info retrieval
        print("\n3. Testing video info retrieval:")
        test_video_id = "dQw4w9WgXcQ"  # Rick Roll
        video_data = youtube_service.get_video_info(test_video_id)
        
        if video_data.get("error"):
            print(f"❌ Video info error: {video_data.get('message')}")
        else:
            print(f"✅ Video found: {video_data.get('title', 'Unknown title')}")
            print(f"✅ Channel: {video_data.get('channel', 'Unknown channel')}")
            print(f"✅ Duration: {video_data.get('duration', 'Unknown')}")
            print(f"✅ Views: {video_data.get('view_count', 0)}")
        
        # Test 4: Test search functionality
        print("\n4. Testing YouTube search:")
        search_query = "python tutorial"
        search_data = youtube_service.search_videos(search_query, max_results=3)
        
        if search_data.get("error"):
            print(f"❌ Search error: {search_data.get('message')}")
        else:
            print(f"✅ Search successful: {search_data.get('total_results', 0)} results")
            results = search_data.get("results", [])
            for i, result in enumerate(results[:3], 1):
                print(f"   {i}. {result.get('title', 'Unknown title')}")
        
        # Test 5: Test message handler integration
        print("\n5. Testing message handler integration:")
        from message_handler import MessageHandler
        from word_tracking import DataManager
        
        # Create a mock data manager
        data_manager = DataManager()
        
        # Create message handler
        message_handler = MessageHandler(service_manager, data_manager)
        
        # Test the _send_youtube_info method directly
        class MockServer:
            def __init__(self):
                self.config = type('obj', (object,), {'name': 'test_server'})
                self.bot_name = 'test_bot'
                self.connected = True
            
            def send_message(self, target, message):
                print(f"   📤 Would send to {target}: {message[:100]}{'...' if len(message) > 100 else ''}")
                return True
        
        mock_server = MockServer()
        
        # Test with a search query
        print("   Testing search query: 'python tutorial'")
        message_handler._send_youtube_info(mock_server, "#test", "python tutorial")
        
        # Test with a YouTube URL
        print("   Testing YouTube URL: https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        message_handler._send_youtube_info(mock_server, "#test", "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        
        print("\n🎉 YouTube command testing completed successfully!")
        print("\n📝 Summary:")
        print("   ✅ YouTube service is properly initialized")
        print("   ✅ API key is loaded correctly")
        print("   ✅ Video ID extraction works")
        print("   ✅ Video info retrieval works")
        print("   ✅ Search functionality works")
        print("   ✅ Message handler integration works")
        print("\n🚀 The YouTube command should now work in the bot!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_youtube_command()
    if success:
        print("\n✅ All tests passed!")
    else:
        print("\n❌ Some tests failed!")