#!/usr/bin/env python3
"""
Solar Wind Command Test Suite

Tests for the solarwind command functionality, including both IRC and console contexts.
"""

import os
import sys
from unittest.mock import Mock, patch

import pytest
from dotenv import load_dotenv

# Load environment variables for testing
load_dotenv()

from commands_basic import solarwind_command
from command_registry import CommandContext


class TestSolarWindCommand:
    """Test cases for the solarwind command."""

    def test_solarwind_command_irc_context(self):
        """Test solarwind command in IRC context."""
        # Create IRC context
        context = CommandContext(
            command="solarwind",
            args=[],
            raw_message="!solarwind",
            sender="testuser",
            target="#testchannel",
            is_console=False,
            is_private=False
        )
        
        bot_functions = {}
        
        # Execute command
        result = solarwind_command(context, bot_functions)
        
        # Verify result
        assert isinstance(result, str)
        assert "Solar Wind" in result
        assert "Density:" in result
        assert "Speed:" in result
        assert "Temperature:" in result
        assert "Magnetic Field:" in result
        assert "🌌" in result
        print(f"IRC Result: {result}")

    def test_solarwind_command_console_context(self):
        """Test solarwind command in console context."""
        # Create console context
        context = CommandContext(
            command="solarwind",
            args=[],
            raw_message="!solarwind",
            sender=None,
            target=None,
            is_console=True,
            is_private=False
        )
        
        bot_functions = {}
        
        # Execute command
        result = solarwind_command(context, bot_functions)
        
        # Verify result
        assert isinstance(result, str)
        assert "Solar Wind" in result
        assert "Density:" in result
        assert "Speed:" in result
        assert "Temperature:" in result
        assert "Magnetic Field:" in result
        assert "🌌" in result
        print(f"Console Result: {result}")

    @patch('services.solarwind_service.requests.get')
    def test_solarwind_command_api_error(self, mock_get):
        """Test solarwind command when API fails."""
        # Mock API failure
        mock_get.side_effect = Exception("API connection failed")
        
        context = CommandContext(
            command="solarwind",
            args=[],
            raw_message="!solarwind",
            sender="testuser",
            target="#testchannel",
            is_console=False,
            is_private=False
        )
        
        bot_functions = {}
        
        # Execute command
        result = solarwind_command(context, bot_functions)
        
        # Verify error handling
        assert isinstance(result, str)
        assert "❌" in result
        assert ("Solar wind error" in result or "Solar Wind Error" in result)
        print(f"Error Result: {result}")

    def test_solarwind_service_directly(self):
        """Test the solar wind service directly."""
        from services.solarwind_service import get_solar_wind_info
        
        result = get_solar_wind_info()
        
        # Verify result format
        assert isinstance(result, str)
        if "❌" not in result:  # If no error
            assert "Solar Wind" in result
            assert "Density:" in result
            assert "Speed:" in result
            assert "Temperature:" in result
            assert "Magnetic Field:" in result
            assert "🌌" in result
        
        print(f"Direct Service Result: {result}")


if __name__ == "__main__":
    # Run tests directly
    test_instance = TestSolarWindCommand()
    print("=== Testing Solar Wind Command ===")
    
    print("\n1. Testing IRC context:")
    test_instance.test_solarwind_command_irc_context()
    
    print("\n2. Testing Console context:")
    test_instance.test_solarwind_command_console_context()
    
    print("\n3. Testing service directly:")
    test_instance.test_solarwind_service_directly()
    
    print("\n=== All tests completed ===")
