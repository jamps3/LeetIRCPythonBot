#!/usr/bin/env python3
"""
Pytest tests for IRC server flood protection functionality.
"""

import threading
import time
from unittest.mock import Mock

import pytest

from config import ServerConfig
from server import Server


@pytest.fixture
def server_config():
    """Create a test server configuration."""
    return ServerConfig(
        name="test",
        host="irc.example.com",
        port=6667,
        channels=["#test"],
        keys=[],
        tls=False,
        allow_insecure_tls=False,
    )


@pytest.fixture
def test_server(server_config):
    """Create a test server instance."""
    stop_event = threading.Event()
    return Server(server_config, "testbot", stop_event)


class TestServerFloodProtection:
    """Test cases for IRC server flood protection."""

    def test_initial_rate_limit_tokens(self, test_server):
        """Test that server starts with correct number of rate limit tokens."""
        assert test_server._rate_limit_tokens == 5.0
        assert test_server._rate_limit_max_tokens == 5.0
        assert test_server._rate_limit_refill_rate == 0.5

    def test_can_send_message_with_tokens(self, test_server):
        """Test that messages can be sent when tokens are available."""
        # Should be able to send when tokens are available
        assert test_server._can_send_message() is True

        # Tokens should be decremented after checking
        assert test_server._rate_limit_tokens == 4.0

    def test_message_sending_exhausts_tokens(self, test_server):
        """Test that sending messages exhausts tokens correctly."""
        # Send 5 messages (all available tokens)
        for i in range(5):
            assert test_server._can_send_message() is True
            assert test_server._rate_limit_tokens == (4.0 - i)

        # Should be rate limited after exhausting tokens
        assert test_server._can_send_message() is False
        assert test_server._rate_limit_tokens == 0.0

    def test_rate_limiting_when_tokens_exhausted(self, test_server):
        """Test that rate limiting kicks in when tokens are exhausted."""
        # Exhaust all tokens
        for _ in range(5):
            test_server._can_send_message()

        # Should be rate limited now
        assert test_server._can_send_message() is False

    def test_token_refill_over_time(self, test_server):
        """Test that tokens refill correctly over time."""
        # Exhaust all tokens
        for _ in range(5):
            test_server._can_send_message()

        # Wait for some time and refill
        time.sleep(2.5)  # Should refill ~1.25 tokens (2.5 * 0.5)
        test_server._refill_rate_limit_tokens()

        # Should have some tokens now (around 1.25)
        assert test_server._rate_limit_tokens > 1.0
        assert test_server._rate_limit_tokens < 1.5

    def test_can_send_after_token_refill(self, test_server):
        """Test that messages can be sent again after token refill."""
        # Exhaust all tokens
        for _ in range(5):
            test_server._can_send_message()

        # Wait and refill
        time.sleep(2.5)
        test_server._refill_rate_limit_tokens()

        # Should be able to send again
        assert test_server._can_send_message() is True

    def test_tokens_dont_exceed_maximum(self, test_server):
        """Test that tokens don't exceed the maximum limit."""
        # Wait a long time and refill
        time.sleep(30.0)  # Much longer than needed to fill bucket
        test_server._refill_rate_limit_tokens()

        # Should not exceed maximum
        assert test_server._rate_limit_tokens <= test_server._rate_limit_max_tokens
        assert test_server._rate_limit_tokens == 5.0

    def test_wait_for_rate_limit_timeout(self, test_server):
        """Test that waiting for rate limit respects timeout."""
        # Exhaust all tokens
        for _ in range(5):
            test_server._can_send_message()

        # Should timeout when waiting for tokens with short timeout
        start_time = time.time()
        result = test_server._wait_for_rate_limit(timeout=1.0)
        end_time = time.time()

        assert result is False
        assert (end_time - start_time) >= 1.0
        assert (end_time - start_time) < 2.0  # Should not wait much longer

    def test_wait_for_rate_limit_success(self, test_server):
        """Test that waiting for rate limit succeeds when tokens become available."""
        # Exhaust all tokens
        for _ in range(5):
            test_server._can_send_message()

        # Should succeed with longer timeout (enough time for tokens to refill)
        result = test_server._wait_for_rate_limit(timeout=5.0)
        assert result is True

        # Should have tokens available now
        assert test_server._rate_limit_tokens > 0

    def test_rate_limit_initialization(self, test_server):
        """Test that rate limit components are properly initialized."""
        assert hasattr(test_server, "_rate_limit_tokens")
        assert hasattr(test_server, "_rate_limit_max_tokens")
        assert hasattr(test_server, "_rate_limit_refill_rate")
        assert hasattr(test_server, "_rate_limit_last_refill")
        assert hasattr(test_server, "_rate_limit_lock")

        # Lock should be a threading lock
        assert isinstance(test_server._rate_limit_lock, type(threading.Lock()))
