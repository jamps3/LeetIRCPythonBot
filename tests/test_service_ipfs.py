#!/usr/bin/env python3
"""
Pytest tests for IPFS service.

Tests IPFS file operations including URL downloads, size limits,
password protection, and IPFS daemon interactions.
"""

from unittest.mock import Mock, patch

import pytest

from services.ipfs_service import IPFSService, get_ipfs_service, handle_ipfs_command


@pytest.fixture
def ipfs_service(mock_subprocess):
    """Create IPFS service instance with mocked subprocess."""
    # Mock subprocess for IPFS availability check
    mock_subprocess.run.return_value = Mock(returncode=0, stdout="ipfs version")
    return IPFSService()


@pytest.fixture
def mock_requests():
    """Mock requests module."""
    with patch("services.ipfs_service.requests") as mock_req:
        yield mock_req


@pytest.fixture
def mock_subprocess():
    """Mock subprocess module."""
    with patch("services.ipfs_service.subprocess") as mock_sub:
        yield mock_sub


class TestIPFSService:
    """Test IPFSService class functionality."""

    def test_init_ipfs_unavailable(self, mock_subprocess):
        """Test initialization when IPFS is not available."""
        mock_subprocess.run.side_effect = FileNotFoundError("ipfs not found")

        service = IPFSService()

        assert service.ipfs_available is False

    def test_init_ipfs_timeout(self, mock_subprocess):
        """Test initialization when IPFS times out."""
        mock_subprocess.run.side_effect = TimeoutError("timeout")

        service = IPFSService()

        assert service.ipfs_available is False

    def test_add_file_from_url_ipfs_unavailable(self, ipfs_service):
        """Test add_file_from_url when IPFS is not available."""
        ipfs_service.ipfs_available = False

        result = ipfs_service.add_file_from_url("http://example.com")

        assert result["success"] is False
        assert "not available" in result["message"]
        assert result["hash"] is None

    def test_get_ipfs_info_ipfs_unavailable(self, ipfs_service):
        """Test IPFS info when IPFS is not available."""
        ipfs_service.ipfs_available = False

        result = ipfs_service.get_ipfs_info("QmTest123")

        assert result["success"] is False
        assert "not available" in result["message"]

    def test_format_file_size(self, ipfs_service):
        """Test file size formatting."""
        assert ipfs_service._format_file_size(512) == "512.0 B"
        assert ipfs_service._format_file_size(1024) == "1.0 KB"
        assert ipfs_service._format_file_size(1024 * 1024) == "1.0 MB"
        assert ipfs_service._format_file_size(1024 * 1024 * 1024) == "1.0 GB"


class TestIPFSServiceGlobal:
    """Test global IPFS service functions."""

    def test_get_ipfs_service_singleton(self):
        """Test that get_ipfs_service returns singleton instance."""
        service1 = get_ipfs_service()
        service2 = get_ipfs_service()

        assert service1 is service2
        assert isinstance(service1, IPFSService)


class TestHandleIPFSCommand:
    """Test handle_ipfs_command function."""

    def test_handle_ipfs_command_invalid(self):
        """Test invalid IPFS command."""
        result = handle_ipfs_command("invalid")

        assert "Usage:" in result

    def test_handle_ipfs_command_empty(self):
        """Test empty IPFS command."""
        result = handle_ipfs_command("")

        assert "Usage:" in result
