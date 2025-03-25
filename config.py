import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union
from dotenv import load_dotenv


@dataclass
class ServerConfig:
    """
    Dataclass to store IRC server configuration.
    
    Attributes:
        host: The IRC server host address
        port: The IRC server port number
        channels: List of channels to join
        keys: Optional list of channel keys (passwords) matching the channels list
        name: Unique identifier for this server configuration
    """
    host: str
    port: int
    channels: List[str]
    keys: Optional[List[str]] = None
    name: str = ""
    
    def __post_init__(self):
        # Ensure channel names have # prefix
        self.channels = [
            f"#{channel.lstrip('#')}" if channel else "#" 
            for channel in self.channels
        ]
        
        # Ensure keys list matches channels length if provided
        if self.keys and len(self.keys) < len(self.channels):
            self.keys.extend([""] * (len(self.channels) - len(self.keys)))


def load_env_file() -> bool:
    """
    Load environment variables from .env file.
    
    Returns:
        bool: True if .env file was loaded successfully, False otherwise
    """
    return load_dotenv()


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
    
    # Handle quoted strings with commas inside by checking for quotes
    if value.startswith('"') and value.endswith('"'):
        value = value[1:-1]
    elif value.startswith("'") and value.endswith("'"):
        value = value[1:-1]
        
    return [item.strip() for item in value.split(',')]


def get_server_configs() -> List[ServerConfig]:
    """
    Parse all server configurations from environment variables.
    
    Returns:
        List of ServerConfig objects
    """
    server_configs = []
    
    # Find all SERVER*_HOST variables to identify server configurations
    server_pattern = re.compile(r'^SERVER(\d+)_HOST$')
    server_indices = []
    
    for key in os.environ:
        match = server_pattern.match(key)
        if match:
            server_indices.append(match.group(1))
    
    # Create ServerConfig for each server
    for idx in server_indices:
        prefix = f"SERVER{idx}_"
        
        host = os.environ.get(f"{prefix}HOST")
        if not host:
            continue
            
        # Get port with default fallback
        try:
            port = int(os.environ.get(f"{prefix}PORT", "6667"))
        except ValueError:
            port = 6667
            
        # Get channels and keys
        channels_str = os.environ.get(f"{prefix}CHANNELS", "")
        keys_str = os.environ.get(f"{prefix}KEYS", "")
        
        channels = parse_comma_separated_values(channels_str)
        keys = parse_comma_separated_values(keys_str) if keys_str else None
        
        # Create the server config
        config = ServerConfig(
            host=host,
            port=port,
            channels=channels,
            keys=keys,
            name=f"SERVER{idx}"
        )
        
        server_configs.append(config)
    
    # If no server configs were found, create a default one
    if not server_configs:
        print("Warning: No server configurations found in .env file. Using defaults.")
        server_configs.append(ServerConfig(
            host="irc.libera.chat",
            port=6667,
            channels=["#test"],
            name="DEFAULT"
        ))
    
    return server_configs


def get_server_config_by_name(name: str) -> Optional[ServerConfig]:
    """
    Get a specific server configuration by its name.
    
    Args:
        name: The name identifier of the server (e.g., 'SERVER1')
        
    Returns:
        ServerConfig object if found, None otherwise
    """
    for config in get_server_configs():
        if config.name == name:
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
    return os.environ.get(key_name, default)


def generate_server_channel_id(server_name: str, channel: str) -> str:
    """
    Generate a unique identifier for a server-channel combination.
    
    Args:
        server_name: The server name or identifier
        channel: The channel name
        
    Returns:
        Unique identifier string
    """
    # Normalize channel name (ensure it has # prefix)
    if not channel.startswith('#'):
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
    parts = combined_id.split(':', 1)
    if len(parts) != 2:
        return (combined_id, "")
    return parts[0], parts[1]

