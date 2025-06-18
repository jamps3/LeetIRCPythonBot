#!/usr/bin/env python3
"""
Test script for high-precision logging functionality.
"""

from logger import get_logger, log, info, error, warning, debug, msg, server

def test_high_precision_logging():
    """Test the high-precision logging system."""
    print("🔍 Testing High-Precision Logging System...\n")
    
    # Test global logger functions
    print("1. Testing global logger functions:")
    log("This is a test info message", "INFO")
    log("This is a test error message", "ERROR") 
    log("This is a test warning message", "WARNING")
    log("This is a test debug message", "DEBUG")
    
    # Test convenience functions
    print("\n2. Testing convenience functions:")
    info("This is an info message")
    error("This is an error message")
    warning("This is a warning message")  
    debug("This is a debug message")
    msg("This is a message event")
    server("This is a server event")
    
    # Test logger with context
    print("\n3. Testing logger with context:")
    logger = get_logger("SERVER1")
    logger.info("Bot connected to server")
    logger.error("Connection failed")
    logger.warning("Rate limit approaching")
    logger.debug("Processing command")
    logger.msg("Channel message received")
    logger.server("PING received from server")
    
    # Test logger with multiple contexts
    print("\n4. Testing logger with extra context:")
    logger.info("User joined channel", "#test")
    logger.error("Command failed", "CommandProcessor")
    logger.msg("Private message received", "UserHandler")
    
    # Test bot manager style logging
    print("\n5. Testing BotManager style logging:")
    bot_logger = get_logger("BotManager")
    bot_logger.info("🌤️ Weather service initialized")
    bot_logger.warning("⚠️ No YouTube API key found. YouTube commands will not work.")
    bot_logger.error("Failed to connect to database")
    
    # Test server-style logging
    print("\n6. Testing Server style logging:")
    server_logger = get_logger("SERVER1")
    server_logger.info("Connected to irc.example.com:6667")
    server_logger.server(":irc.example.com NOTICE * :*** Looking up your hostname...")
    server_logger.server(":irc.example.com 001 botname :Welcome to the Example IRC Network")
    server_logger.server(":irc.example.com PONG irc.example.com :keepalive")
    
    print("\n✅ High-precision logging test completed!")
    print("All timestamps should show nanosecond precision in format: [YYYY-MM-DD HH:MM:SS.nnnnnnnnn]")

if __name__ == "__main__":
    test_high_precision_logging()

