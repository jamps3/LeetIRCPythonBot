"""
Configuration module for the IRC bot.

This module provides functions to load and parse server configurations
from environment variables, typically stored in a .env file.
"""

import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union
from dotenv import load_dotenv
import threading


@dataclass
class ServerConfig:
    """
    Dataclass to store IRC server configuration.

    Attributes:
        host: The IRC server host address (e.g., irc.libera.chat)
        port: The IRC server port number (e.g., 6667)
        channels: List of channel names to join (e.g., ['#test1', '#test2'])
        keys: Optional list of channel keys (passwords) matching the channels list
        name: Unique identifier for this server configuration (e.g., SERVER1)
    """

    host: str
    port: int
    channels: List[str]
    keys: Optional[List[str]] = None
    name: str = ""

    def __post_init__(self):
        """Normalize channel names and align keys with channels."""
        # Ensure channel names have # prefix
        self.channels = [
            f"#{channel.lstrip('#')}" if channel else "#" for channel in self.channels
        ]

        # Ensure keys list matches channels length if provided
        if self.keys and len(self.keys) < len(self.channels):
            self.keys.extend([""] * (len(self.channels) - len(self.keys)))

        # Validate configuration
        if not self.host:
            raise ValueError("Server host cannot be empty")
        if self.port <= 0 or self.port > 65535:
            raise ValueError(f"Invalid port number: {self.port}")
        if not self.channels:
            raise ValueError("At least one channel must be specified")
        if not self.name:
            self.name = f"{self.host}:{self.port}"


# Threading lock for potential dynamic configuration updates
config_lock = threading.Lock()


def load_env_file() -> bool:
    """
    Load environment variables from .env file.

    Returns:
        bool: True if .env file was loaded successfully, False otherwise
    """
    with config_lock:
        try:
            return load_dotenv()
        except Exception as e:
            print(f"Error loading .env file: {e}")
            return False


def parse_comma_separated_values(value: str) -> List[str]:
    """
    Parse comma-separated values from environment variable.

    Args:
        value: Comma-separated string

    Returns:
        List of individual values with whitespace trimmed
    """
    if not value:
        return []

    # Handle quoted strings with commas inside
    if value.startswith('"') and value.endswith('"'):
        value = value[1:-1]
    elif value.startswith("'") and value.endswith("'"):
        value = value[1:-1]

    return [item.strip() for item in value.split(",") if item.strip()]


def get_server_configs() -> List[ServerConfig]:
    """
    Parse all server configurations from environment variables.

    Environment variables should be formatted as:
    - SERVER<index>_HOST (e.g., SERVER1_HOST=irc.libera.chat)
    - SERVER<index>_PORT (e.g., SERVER1_PORT=6667)
    - SERVER<index>_CHANNELS (e.g., SERVER1_CHANNELS=#test1,#test2)
    - SERVER<index>_KEYS (e.g., SERVER1_KEYS=,key2)

    Returns:
        List of ServerConfig objects
    """
    with config_lock:
        server_configs = []

        # Find all SERVER*_HOST variables
        server_pattern = re.compile(r"^SERVER(\d+)_HOST$")
        server_indices = []

        for key in os.environ:
            match = server_pattern.match(key)
            if match:
                server_indices.append(match.group(1))

        # Create ServerConfig for each server
        for idx in sorted(server_indices):
            prefix = f"SERVER{idx}_"

            host = os.environ.get(f"{prefix}HOST")
            if not host:
                print(f"Warning: Missing host for {prefix}HOST, skipping...")
                continue

            # Get port with default fallback
            try:
                port = int(os.environ.get(f"{prefix}PORT", "6667"))
            except ValueError:
                print(f"Warning: Invalid port for {prefix}PORT, using default 6667")
                port = 6667

            # Get channels and keys
            channels_str = os.environ.get(f"{prefix}CHANNELS", "")
            keys_str = os.environ.get(f"{prefix}KEYS", "")

            channels = parse_comma_separated_values(channels_str)
            keys = parse_comma_separated_values(keys_str) if keys_str else None

            if not channels:
                print(
                    f"Warning: No channels specified for {prefix}CHANNELS, using default #test"
                )
                channels = ["#test"]

            # Create the server config
            try:
                config = ServerConfig(
                    host=host,
                    port=port,
                    channels=channels,
                    keys=keys,
                    name=f"SERVER{idx}",
                )
                server_configs.append(config)
                print(
                    f"Loaded configuration for {config.name}: {config.host}:{config.port}, channels: {config.channels}"
                )
            except ValueError as e:
                print(f"Error creating config for {prefix}: {e}")
                continue

        # Fallback to default configuration if none found
        if not server_configs:
            print(
                "Warning: No server configurations found in .env file. Using default."
            )
            server_configs.append(
                ServerConfig(
                    host="irc.libera.chat",
                    port=6667,
                    channels=["#test"],
                    name="DEFAULT",
                )
            )

        return server_configs


def get_server_config_by_name(name: str) -> Optional[ServerConfig]:
    """
    Get a specific server configuration by its name.

    Args:
        name: The name identifier of the server (e.g., 'SERVER1')

    Returns:
        ServerConfig object if found, None otherwise
    """
    with config_lock:
        for config in get_server_configs():
            if config.name.lower() == name.lower():
                return config
        return None


def get_channel_key_pairs(server_config: ServerConfig) -> List[Tuple[str, str]]:
    """
    Get channel-key pairs for a server configuration.

    Args:
        server_config: A ServerConfig object

    Returns:
        List of tuples with (channel, key) pairs
    """
    with config_lock:
        if not server_config.keys:
            return [(channel, "") for channel in server_config.channels]
        return list(zip(server_config.channels, server_config.keys))


def get_api_key(key_name: str, default: str = "") -> str:
    """
    Get an API key from environment variables.

    Args:
        key_name: Name of the environment variable
        default: Default value if the key doesn't exist

    Returns:
        API key value or default
    """
    with config_lock:
        value = os.environ.get(key_name, default)
        if not value and default == "":
            print(f"Warning: API key {key_name} not found in environment variables")
        return value


def generate_server_channel_id(server_name: str, channel: str) -> str:
    """
    Generate a unique identifier for a server-channel combination.

    Args:
        server_name: The server name or identifier
        channel: The channel name

    Returns:
        Unique identifier string (e.g., SERVER1:#channel)
    """
    with config_lock:
        # Normalize channel name
        if not channel.startswith("#"):
            channel = f"#{channel}"
        return f"{server_name}:{channel}"


def parse_server_channel_id(combined_id: str) -> Tuple[str, str]:
    """
    Parse a server-channel identifier back into its components.

    Args:
        combined_id: Combined server:channel identifier

    Returns:
        Tuple of (server_name, channel)
    """
    with config_lock:
        parts = combined_id.split(":", 1)
        if len(parts) != 2:
            return (combined_id, "")
        return parts[0], parts[1]
