#!/usr/bin/env python3
"""
IPFS Service for LeetIRC Bot

This service handles IPFS file operations including adding files from URLs
with size limits and password protection for large files.
"""

import hashlib
import logging
import os
import subprocess
import tempfile
from typing import Dict, Optional, Tuple

import requests


class IPFSService:
    """Service for IPFS operations."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.max_size_without_password = 100 * 1024 * 1024  # 100MB

        # Check if IPFS is available
        self.ipfs_available = self._check_ipfs_availability()
        if not self.ipfs_available:
            self.logger.warning(
                "IPFS daemon not available. IPFS commands will be disabled."
            )

    def _check_ipfs_availability(self) -> bool:
        """Check if IPFS daemon is running and accessible."""
        try:
            result = subprocess.run(
                ["ipfs", "version"], capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except (
            subprocess.TimeoutExpired,
            subprocess.CalledProcessError,
            FileNotFoundError,
        ):
            return False

    def _download_file(
        self, url: str, max_size: int
    ) -> Tuple[Optional[str], Optional[str], int]:
        """
        Download file from URL and check size.

        Args:
            url: URL to download
            max_size: Maximum allowed size in bytes

        Returns:
            Tuple[temp_file_path, error_message, file_size]
        """
        try:
            # Make HEAD request to check content length
            head_response = requests.head(url, timeout=10, allow_redirects=True)
            content_length = head_response.headers.get("content-length")

            if content_length:
                file_size = int(content_length)
                if file_size > max_size:
                    return (
                        None,
                        f"File too large: {file_size} bytes (max: {max_size} bytes)",
                        file_size,
                    )

            # Download the file
            response = requests.get(url, timeout=30, stream=True)
            response.raise_for_status()

            # Create temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            downloaded_size = 0

            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    temp_file.write(chunk)
                    downloaded_size += len(chunk)

                    # Check size during download
                    if downloaded_size > max_size:
                        temp_file.close()
                        os.unlink(temp_file.name)
                        return (
                            None,
                            f"File too large: {downloaded_size} bytes (max: {max_size} bytes)",
                            downloaded_size,
                        )

            temp_file.close()
            return temp_file.name, None, downloaded_size

        except requests.RequestException as e:
            return None, f"Download error: {str(e)}", 0
        except Exception as e:
            return None, f"Unexpected error: {str(e)}", 0

    def _add_to_ipfs(self, file_path: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Add file to IPFS.

        Args:
            file_path: Path to the file to add

        Returns:
            Tuple[ipfs_hash, error_message]
        """
        try:
            result = subprocess.run(
                ["ipfs", "add", file_path], capture_output=True, text=True, timeout=60
            )

            if result.returncode == 0:
                # Parse output to get hash
                output_lines = result.stdout.strip().split("\n")
                for line in output_lines:
                    if line.startswith("added "):
                        parts = line.split()
                        if len(parts) >= 2:
                            return parts[1], None
                return None, "Could not parse IPFS hash from output"
            else:
                return None, f"IPFS add failed: {result.stderr}"

        except subprocess.TimeoutExpired:
            return None, "IPFS add timeout"
        except Exception as e:
            return None, f"IPFS add error: {str(e)}"

    def add_file_from_url(
        self,
        url: str,
        admin_password: Optional[str] = None,
        provided_password: Optional[str] = None,
    ) -> Dict[str, any]:
        """
        Add a file from URL to IPFS.

        Args:
            url: URL of the file to add
            admin_password: Admin password from environment
            provided_password: Password provided by user

        Returns:
            Dict with success status, message, hash, and file info
        """
        if not self.ipfs_available:
            return {
                "success": False,
                "message": "IPFS daemon not available. Please start IPFS daemon.",
                "hash": None,
                "file_size": 0,
            }

        # Determine if password was provided and is correct
        has_valid_password = (
            admin_password and provided_password and provided_password == admin_password
        )

        # Set size limit based on password
        max_size = (
            float("inf") if has_valid_password else self.max_size_without_password
        )

        self.logger.info(
            f"Adding file from URL: {url} (password: {'yes' if has_valid_password else 'no'})"
        )

        # Download file
        temp_file, error, file_size = self._download_file(url, max_size)

        if error:
            # If file is too large and no password provided, suggest using password
            if "too large" in error and not has_valid_password:
                error += f". Use password to bypass size limit: !ipfs <password> {url}"

            return {
                "success": False,
                "message": error,
                "hash": None,
                "file_size": file_size,
            }

        try:
            # Add to IPFS
            ipfs_hash, ipfs_error = self._add_to_ipfs(temp_file)

            if ipfs_error:
                return {
                    "success": False,
                    "message": f"IPFS error: {ipfs_error}",
                    "hash": None,
                    "file_size": file_size,
                }

            # Calculate file hash for verification
            with open(temp_file, "rb") as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()[:16]

            success_message = (
                f"✅ File added to IPFS! Hash: {ipfs_hash} "
                f"({self._format_file_size(file_size)}, SHA256: {file_hash})"
            )

            return {
                "success": True,
                "message": success_message,
                "hash": ipfs_hash,
                "file_size": file_size,
                "file_hash": file_hash,
            }

        finally:
            # Clean up temporary file
            if temp_file and os.path.exists(temp_file):
                os.unlink(temp_file)

    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    def get_ipfs_info(self, ipfs_hash: str) -> Dict[str, any]:
        """
        Get information about an IPFS object.

        Args:
            ipfs_hash: IPFS hash to query

        Returns:
            Dict with object information
        """
        if not self.ipfs_available:
            return {"success": False, "message": "IPFS not available"}

        try:
            result = subprocess.run(
                ["ipfs", "object", "stat", ipfs_hash],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                # Parse output
                info = {}
                for line in result.stdout.strip().split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        info[key.strip()] = value.strip()

                return {
                    "success": True,
                    "message": f"IPFS object info: {info}",
                    "info": info,
                }
            else:
                return {
                    "success": False,
                    "message": f"Failed to get IPFS info: {result.stderr}",
                }

        except Exception as e:
            return {"success": False, "message": f"Error getting IPFS info: {str(e)}"}


# Global service instance
_ipfs_service = None


def get_ipfs_service() -> IPFSService:
    """Get the global IPFS service instance."""
    global _ipfs_service
    if _ipfs_service is None:
        _ipfs_service = IPFSService()
    return _ipfs_service


def handle_ipfs_command(command_text: str, admin_password: Optional[str] = None) -> str:
    """
    Handle IPFS commands.

    Args:
        command_text: The full command text
        admin_password: Admin password from environment

    Returns:
        str: Response message
    """
    service = get_ipfs_service()

    # Parse command
    parts = command_text.split()

    if len(parts) < 2:
        return "Usage: !ipfs add <url> or !ipfs <password> <url>"

    command = parts[1].lower()

    if command == "add":
        if len(parts) < 3:
            return "Usage: !ipfs add <url>"

        url = parts[2]
        result = service.add_file_from_url(url, admin_password)
        return result["message"]

    elif command == "info":
        if len(parts) < 3:
            return "Usage: !ipfs info <hash>"

        ipfs_hash = parts[2]
        result = service.get_ipfs_info(ipfs_hash)
        return result["message"]

    else:
        # Check if first argument might be a password
        if len(parts) >= 3:
            potential_password = parts[1]
            url = parts[2]

            result = service.add_file_from_url(url, admin_password, potential_password)
            return result["message"]
        else:
            return "Usage: !ipfs add <url> or !ipfs <password> <url>"
