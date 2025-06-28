import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

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
        tls: Enable TLS for secure connection
        name: Unique identifier for this server configuration
    """

    host: str
    port: int
    channels: List[str]
    keys: Optional[List[str]] = None
    tls: bool = False  # Enable TLS if needed
    name: str = ""

    def __post_init__(self):
        # Ensure channel names have # prefix
        self.channels = [
            f"#{channel.lstrip('#')}" if channel else "#" for channel in self.channels
        ]

        # Ensure keys list matches channels length if provided
        if self.keys and len(self.keys) < len(self.channels):
            self.keys.extend([""] * (len(self.channels) - len(self.keys)))


@dataclass
class BotConfig:
    """
    Centralized bot configuration.
    """

    # Bot identification
    name: str = "jl3b"
    version: str = "2.0.0"

    # Logging
    log_level: str = "INFO"

    # File paths
    history_file: str = "conversation_history.json"
    ekavika_file: str = "ekavika.json"
    words_file: str = "general_words.json"
    subscribers_file: str = "subscribers.json"

    # Connection settings
    reconnect_delay: int = 60
    quit_message: str = "🍺 Nähdään! 🍺"

    # Security
    admin_password: str = "changeme"

    # API Keys
    weather_api_key: str = ""
    electricity_api_key: str = ""
    openai_api_key: str = ""
    youtube_api_key: str = ""

    # Drink tracking words
    drink_words: Dict[str, int] = field(
        default_factory=lambda: {
            "krak": 0,
            "kr1k": 0,
            "kr0k": 0,
            "narsk": 0,
            "parsk": 0,
            "tlup": 0,
            "marsk": 0,
            "tsup": 0,
            "plop": 0,
            "tsirp": 0,
        }
    )

    # Server configurations
    servers: List[ServerConfig] = field(default_factory=list)

    # Default chat history for AI
    default_history: List[Dict[str, str]] = field(
        default_factory=lambda: [
            {
                "role": "system",
                "content": "You are a helpful assistant who knows about Finnish beer culture. You respond in a friendly, short and tight manner. If you don't know something, just say so. Keep responses brief, we are on IRC.",
            }
        ]
    )


class ConfigManager:
    """
    Centralized configuration manager for the IRC bot.
    """

    def __init__(self, env_file: str = ".env"):
        self.env_file = env_file
        self._config: Optional[BotConfig] = None
        self._load_environment()

    def _load_environment(self) -> bool:
        """
        Load environment variables from .env file.

        Returns:
            bool: True if .env file was loaded successfully, False otherwise
        """
        return load_dotenv(self.env_file)

    @property
    def config(self) -> BotConfig:
        """
        Get the current bot configuration, loading it if necessary.
        """
        if self._config is None:
            self._config = self._load_config()
        return self._config

    def _load_config(self) -> BotConfig:
        """
        Load configuration from environment variables.
        """
        config = BotConfig(
            # Bot identification
            name=os.getenv("BOT_NAME", "jl3b"),
            version=os.getenv("BOT_VERSION", "2.0.0"),
            # Logging
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            # File paths
            history_file=os.getenv("HISTORY_FILE", "conversation_history.json"),
            ekavika_file=os.getenv("EKAVIKA_FILE", "ekavika.json"),
            words_file=os.getenv("WORDS_FILE", "general_words.json"),
            subscribers_file=os.getenv("SUBSCRIBERS_FILE", "subscribers.json"),
            # Connection settings
            reconnect_delay=int(os.getenv("RECONNECT_DELAY", "60")),
            quit_message=os.getenv("QUIT_MESSAGE", "🍺 Nähdään! 🍺"),
            # Security
            admin_password=os.getenv("ADMIN_PASSWORD", "changeme"),
            # API Keys
            weather_api_key=os.getenv("WEATHER_API_KEY", ""),
            electricity_api_key=os.getenv("ELECTRICITY_API_KEY", ""),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            youtube_api_key=os.getenv("YOUTUBE_API_KEY", ""),
            # Server configurations
            servers=self._load_server_configs(),
        )

        return config

    def _load_server_configs(self) -> List[ServerConfig]:
        """
        Parse all server configurations from environment variables.

        Returns:
            List of ServerConfig objects
        """
        return get_server_configs()  # Use existing function

    def reload_config(self) -> None:
        """
        Force reload of configuration from environment.
        """
        self._load_environment()
        self._config = None

    def get_server_by_name(self, name: str) -> Optional[ServerConfig]:
        """
        Get a specific server configuration by its name.

        Args:
            name: The name identifier of the server (e.g., 'SERVER1')

        Returns:
            ServerConfig object if found, None otherwise
        """
        for server in self.config.servers:
            if server.name == name:
                return server
        return None

    def get_primary_server(self) -> Optional[ServerConfig]:
        """
        Get the first/primary server configuration.

        Returns:
            ServerConfig object if any servers are configured, None otherwise
        """
        servers = self.config.servers
        return servers[0] if servers else None

    def validate_config(self) -> List[str]:
        """
        Validate the current configuration and return any issues found.

        Returns:
            List of validation error messages
        """
        errors = []
        config = self.config

        # Check for servers
        if not config.servers:
            errors.append("No server configurations found")

        # Check API keys if needed
        if not config.weather_api_key:
            errors.append("Weather API key not configured")

        if not config.openai_api_key:
            errors.append("OpenAI API key not configured")

        # Check file paths exist
        for file_attr, desc in [
            ("history_file", "History file"),
            ("ekavika_file", "Ekavika file"),
            ("words_file", "Words file"),
            ("subscribers_file", "Subscribers file"),
        ]:
            file_path = getattr(config, file_attr)
            if not Path(file_path).parent.exists():
                errors.append(f"{desc} directory does not exist: {file_path}")

        return errors

    def save_config_to_json(self, file_path: str) -> None:
        """
        Save current configuration to a JSON file for backup/debugging.

        Args:
            file_path: Path where to save the configuration
        """
        config_dict = {
            "bot": {
                "name": self.config.name,
                "version": self.config.version,
                "log_level": self.config.log_level,
            },
            "files": {
                "history_file": self.config.history_file,
                "ekavika_file": self.config.ekavika_file,
                "words_file": self.config.words_file,
                "subscribers_file": self.config.subscribers_file,
            },
            "connection": {
                "reconnect_delay": self.config.reconnect_delay,
                "quit_message": self.config.quit_message,
            },
            "servers": [
                {
                    "name": server.name,
                    "host": server.host,
                    "port": server.port,
                    "channels": server.channels,
                    "keys": server.keys or [],
                }
                for server in self.config.servers
            ],
            "drink_words": self.config.drink_words,
        }

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(config_dict, f, indent=2, ensure_ascii=False)


# Global configuration manager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """
    Get the global configuration manager instance.

    Returns:
        ConfigManager instance
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def get_config() -> BotConfig:
    """
    Get the current bot configuration.

    Returns:
        BotConfig instance
    """
    return get_config_manager().config


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

    return [item.strip() for item in value.split(",")]


def get_server_configs() -> List[ServerConfig]:
    """
    Parse all server configurations from environment variables.

    Returns:
        List of ServerConfig objects
    """
    server_configs = []

    # Find all SERVER*_HOST variables to identify server configurations
    server_pattern = re.compile(r"^SERVER(\d+)_HOST$")
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
            host=host, port=port, channels=channels, keys=keys, name=f"SERVER{idx}"
        )

        server_configs.append(config)

    # If no server configs were found, create a default one
    if not server_configs:
        print("Warning: No server configurations found in .env file. Using defaults.")
        server_configs.append(
            ServerConfig(
                host="irc.libera.chat", port=6667, channels=["#test"], name="DEFAULT"
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
    parts = combined_id.split(":", 1)
    if len(parts) != 2:
        return (combined_id, "")
    return parts[0], parts[1]
