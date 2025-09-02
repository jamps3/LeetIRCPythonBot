#!/usr/bin/env python3
"""
GPT Service Test Suite - Pure Pytest Version

Tests for GPT service functionality including date correction.
"""

import os
import re
import sys
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

# Add the parent directory to sys.path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Mock only the external dependencies needed for GPT service
sys.modules["openai"] = Mock()


def test_gpt_service_initialization():
    """Test GPT service initialization."""
    # Import directly to avoid services package __init__.py
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))
    from gpt_service import GPTService

    api_key = "test_api_key"
    service = GPTService(api_key)

    assert service.api_key == api_key, "API key should be set correctly"
    assert hasattr(
        service, "_correct_outdated_dates"
    ), "Service should have date correction method"
    assert hasattr(
        service, "conversation_history"
    ), "Service should have conversation history"
    assert hasattr(service, "client"), "Service should have OpenAI client"
