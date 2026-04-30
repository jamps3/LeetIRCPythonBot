import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add project root to path for imports before any src.* imports
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from dotenv import load_dotenv  # noqa: E402

from src.logger import get_logger  # noqa: E402

logger = get_logger("Config")

# Project root directory (parent of src/)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Data directory
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

# Common data file paths
CONVERSATION_HISTORY_FILE = os.path.join(DATA_DIR, "conversation_history.json")
EKAVIKA_FILE = os.path.join(DATA_DIR, "ekavika.json")
GENERAL_WORDS_FILE = os.path.join(DATA_DIR, "general_words.json")
SUBSCRIBERS_FILE = os.path.join(DATA_DIR, "subscribers.json")
STATE_FILE = os.path.join(DATA_DIR, "state.json")
OTIEDOTE_FILE = os.path.join(DATA_DIR, "otiedote.json")
SANANMUUNNOKSET_FILE = os.path.join(DATA_DIR, "sananmuunnokset.json")
QUOTES_FILE = os.path.join(DATA_DIR, "quotes.txt")

# Log rotation defaults
LOG_ROTATION_SIZE = 10485760  # 10MB in bytes
LOG_ROTATION_COUNT = 5  # Maximum number of log files to keep
LOG_ROTATION_INTERVAL = (
    ""  # Time-based rotation: minute, hour, day, week, month, year (optional)
)
LOG_ROTATION_TIME = (
    "00:00"  # Time of day for daily/weekly/monthly rotation (HH:MM format)
)

# Bot Configuration Settings
BOT_NAME = "LeetIRCBot"  # Bot nickname
LOG_LEVEL = "INFO"  # Logging level
RECONNECT_DELAY = 60  # Seconds to wait before reconnecting
QUIT_MESSAGE = "🍺 Nähdään! 🍺"  # Quit message

# TUI Configuration
LOG_BUFFER_SIZE = 1000  # Maximum number of log entries to keep in memory
AUTO_CONNECT = True  # Automatically connect to servers on startup
AUTO_RECONNECT = True  # Automatically reconnect if disconnected

# Message Output Settings
USE_NOTICES = (
    True  # Send all channel responses as IRC NOTICEs instead of regular messages
)

# Tamagotchi Settings
TAMAGOTCHI_ENABLED = True  # Enable tamagotchi responses to trigger words

# Ops Command Settings
OPS_ALLOWED_CHANNELS = (
    ""  # Channels where the !ops command is allowed (comma-separated)
)

# Title Fetching Blacklist Settings
TITLE_BLACKLIST_DOMAINS = "youtube.com,youtu.be,facebook.com,fb.com,x.com,twitter.com,instagram.com,tiktok.com,discord.com,reddit.com,imgur.com"
TITLE_BLACKLIST_EXTENSIONS = (
    ".jpg,.jpeg,.png,.gif,.mp4,.webm,.pdf,.zip,.rar,.mp3,.wav,.flac"
)
TITLE_BANNED_TEXTS = "Bevor Sie zu Google Maps weitergehen;Just a moment...;403 Forbidden;404 Not Found;Access Denied;Ennen kuin jatkat Google Mapsiin"

# GPT Service Settings
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-nano")  # Model for the Responses API
GPT_HISTORY_LIMIT = 100  # Maximum number of messages to keep in conversation history


def _read_version_from_file() -> str:
    """
    Read version from VERSION file.

    Returns:
        Version string, defaults to "1.0.1" if file doesn't exist
    """
    version_file = "VERSION"
    try:
        with open(version_file, "r", encoding="utf-8") as f:
            version = f.read().strip()
            # Validate version format (basic check)
            if version and re.match(r"^\d+\.\d+\.\d+$", version):
                return version
            else:
                logger.warning(  # noqa: F821
                    f"Invalid version format in {version_file}: {version}, using default"
                )
                return "1.0.1"
    except (FileNotFoundError, IOError) as e:
        logger.warning(  # noqa: F821
            f"Could not read version from {version_file}: {e}, using default"
        )
        return "1.0.1"


@dataclass
class ServerConfig:
    """
    Dataclass to store IRC server configuration.
    """

    host: str
    port: int
    channels: List[str]
    keys: Optional[List[str]] = None
    tls: bool = False  # Enable TLS if needed
    allow_insecure_tls: bool = False  # Allow insecure TLS connections
    name: str = ""
    nick: Optional[str] = None  # Bot nickname for this server
    nickserv_password: Optional[str] = None  # NickServ password for identification
    nickserv_email: Optional[str] = None  # Email for NickServ registration

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
    name: str = BOT_NAME
    version: str = field(default_factory=_read_version_from_file)

    # Logging
    log_level: str = "INFO"

    # File paths
    history_file: str = CONVERSATION_HISTORY_FILE
    ekavika_file: str = EKAVIKA_FILE
    words_file: str = GENERAL_WORDS_FILE
    subscribers_file: str = SUBSCRIBERS_FILE
    otiedote_file: str = OTIEDOTE_FILE
    quotes_source: str = "data/quotes.txt"
    state_file: str = STATE_FILE

    # Connection settings
    reconnect_delay: int = 60
    quit_message: str = "🍺 Nähdään! 🍺"

    # Security
    admin_password: str = "changeme"

    # Channel restrictions
    ops_allowed_channels: List[str] = field(default_factory=list)

    # API Keys
    weather_api_key: str = ""
    weather_forecast_api_key: str = ""
    electricity_api_key: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-5.4-nano"
    youtube_api_key: str = ""
    eurojackpot_api_key: str = ""

    # Drink tracking words
    drink_words: Dict[str, int] = field(
        default_factory=lambda: {
            "krak": 0,
            "kr1k": 0,
            "kr0k": 0,
            "kr3k": 0,
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

    # Feature toggles
    use_notices: bool = False
    tamagotchi_enabled: bool = True
    four_twenty_enabled: bool = True
    auto_connect: bool = True
    auto_reconnect: bool = True
    log_buffer_size: int = 1000
    gpt_history_limit: int = 100

    # X (Twitter) API settings
    x_bearer_token: str = ""

    # URL title fetching settings
    title_blacklist_domains: str = ""
    title_blacklist_extensions: str = ""
    title_banned_texts: str = ""


class ConfigManager:
    """
    Centralized configuration manager for the IRC bot.
    """

    def __init__(self, env_file: str = ".env"):
        # Resolve .env relative to project root if needed
        if not os.path.isabs(env_file):
            src_dir = os.path.dirname(__file__)
            project_root = os.path.abspath(os.path.join(src_dir, ".."))
            env_file = os.path.join(project_root, env_file)

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
        Load configuration from state.json and environment variables.
        """
        # Prepare state_file with data directory
        state_file = os.getenv("STATE_FILE", STATE_FILE)
        if not state_file.startswith(("data/", "data\\")):
            state_file = os.path.join("data", state_file)

        # Load settings from state.json
        state_config = self._load_state_config()

        config = BotConfig(
            # Bot identification
            name=state_config.get("bot_name", BOT_NAME),
            version=os.getenv("BOT_VERSION") or _read_version_from_file(),
            # Logging
            log_level=state_config.get("log_level", "INFO"),
            # File paths
            history_file=state_config.get("history_file", CONVERSATION_HISTORY_FILE),
            ekavika_file=state_config.get("ekavika_file", EKAVIKA_FILE),
            words_file=state_config.get("words_file", GENERAL_WORDS_FILE),
            subscribers_file=state_config.get("subscribers_file", SUBSCRIBERS_FILE),
            otiedote_file=state_config.get("otiedote_file", OTIEDOTE_FILE),
            quotes_source=state_config.get("quotes_source", "data/quotes.txt"),
            state_file=state_file,
            # Connection settings
            reconnect_delay=state_config.get("reconnect_delay", RECONNECT_DELAY),
            quit_message=state_config.get("quit_message", QUIT_MESSAGE),
            # Security
            admin_password=state_config.get("admin_password", "changeme"),
            # Channel restrictions
            ops_allowed_channels=parse_comma_separated_values(
                state_config.get("ops_allowed_channels", OPS_ALLOWED_CHANNELS)
            ),
            # API Keys (still from env)
            weather_api_key=os.getenv("WEATHER_API_KEY", ""),
            weather_forecast_api_key=os.getenv("WEATHER_FORECAST_API_KEY", ""),
            electricity_api_key=os.getenv("ELECTRICITY_API_KEY", ""),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_model=state_config.get(
                "openai_model", os.getenv("OPENAI_MODEL", "gpt-5.4-nano")
            ),
            youtube_api_key=os.getenv("YOUTUBE_API_KEY", ""),
            eurojackpot_api_key=os.getenv("EUROJACKPOT_API_KEY", ""),
            # Feature toggles
            use_notices=state_config.get("use_notices", USE_NOTICES),
            tamagotchi_enabled=state_config.get(
                "tamagotchi_enabled", TAMAGOTCHI_ENABLED
            ),
            four_twenty_enabled=state_config.get("four_twenty_enabled", True),
            auto_connect=state_config.get("auto_connect", AUTO_CONNECT),
            auto_reconnect=state_config.get("auto_reconnect", AUTO_RECONNECT),
            log_buffer_size=state_config.get("log_buffer_size", LOG_BUFFER_SIZE),
            gpt_history_limit=state_config.get("gpt_history_limit", GPT_HISTORY_LIMIT),
            # X (Twitter) API settings
            x_bearer_token=os.getenv("X_BEARER_TOKEN", ""),
            # URL title fetching settings
            title_blacklist_domains=state_config.get(
                "title_blacklist_domains", TITLE_BLACKLIST_DOMAINS
            ),
            title_blacklist_extensions=state_config.get(
                "title_blacklist_extensions", TITLE_BLACKLIST_EXTENSIONS
            ),
            title_banned_texts=state_config.get(
                "title_banned_texts", TITLE_BANNED_TEXTS
            ),
        )

        # Load server configurations from state.json
        servers = self._load_server_configs_from_state(state_config)
        logger.info(f"Loaded {len(servers)} servers from state.json")
        config.servers = servers

        return config

    def _load_state_config(self) -> dict:
        """
        Load configuration from state.json file.
        If file doesn't exist or has no servers, run interactive setup.
        """
        state_file = os.path.join(PROJECT_ROOT, "data", "state.json")

        if not os.path.exists(state_file):
            logger.info("state.json not found, running interactive setup...")
            self._run_interactive_setup(state_file)

        if os.path.exists(state_file):
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                config = data.get("config", {})
                # Check if servers are configured
                servers = config.get("servers", [])
                if not servers:
                    logger.info(
                        "No servers configured in state.json, running interactive setup..."
                    )
                    self._run_interactive_setup(state_file)
                    # Reload after setup
                    with open(state_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    config = data.get("config", {})
                return config
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load state.json: {e}")
                logger.info("Running interactive setup due to config loading error...")
                self._run_interactive_setup(state_file)
                try:
                    with open(state_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    return data.get("config", {})
                except Exception:
                    return {}
            except Exception:
                logger.error("Unexpected error in config loading")
                return {}
        else:
            logger.error("Failed to create state.json during setup")
            return {}

    def _run_interactive_setup(self, state_file: str) -> None:
        """
        Run interactive setup to create or update state.json
        """
        print("🤖 LeetIRCPythonBot Configuration Setup")
        print("=" * 40)

        # Load existing configuration if available
        existing_config = {}
        if os.path.exists(state_file):
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                existing_config = data.get("config", {})
                print("Loaded existing configuration. Using as defaults.")
                print(
                    "Press Enter to keep existing values, or enter new values to change."
                )
                print()
            except Exception as e:
                print(f"Could not load existing config: {e}. Starting fresh.")
                print()

        config = {}

        # Bot Configuration
        print("\n📝 Bot Configuration:")
        default_name = existing_config.get("bot_name", "LeetIRCBot")
        config["bot_name"] = (
            input(f"Bot nickname ({default_name}): ").strip() or default_name
        )
        default_level = existing_config.get("log_level", "INFO")
        config["log_level"] = (
            input(f"Log level ({default_level}): ").strip().upper() or default_level
        )
        default_password = existing_config.get("admin_password", "changeme")
        config["admin_password"] = (
            input(f"Admin password ({default_password}): ").strip() or default_password
        )

        # Connection settings
        print("\n🌐 Connection Settings:")
        default_delay = existing_config.get("reconnect_delay", 60)
        config["reconnect_delay"] = int(
            input(f"Reconnect delay in seconds ({default_delay}): ").strip()
            or str(default_delay)
        )
        default_quit = existing_config.get("quit_message", "🍺 Nähdään! 🍺")
        config["quit_message"] = (
            input(f"Quit message ({default_quit}): ").strip() or default_quit
        )

        # Feature toggles
        print("\n⚙️ Feature Toggles:")
        default_notices = (
            "true" if existing_config.get("use_notices", USE_NOTICES) else "false"
        )
        config["use_notices"] = input(
            f"Use IRC NOTICEs instead of PRIVMSG? ({default_notices}): "
        ).strip().lower() in ("true", "1", "yes", "on", "")
        default_tama = (
            "true"
            if existing_config.get("tamagotchi_enabled", TAMAGOTCHI_ENABLED)
            else "false"
        )
        config["tamagotchi_enabled"] = input(
            f"Enable tamagotchi responses? ({default_tama}): "
        ).strip().lower() in ("true", "1", "yes", "on", "")
        default_420 = (
            "true" if existing_config.get("four_twenty_enabled", True) else "false"
        )
        config["four_twenty_enabled"] = input(
            f"Enable 4:20 time announcements? ({default_420}): "
        ).strip().lower() in ("true", "1", "yes", "on", "")
        default_auto_connect = (
            "true" if existing_config.get("auto_connect", AUTO_CONNECT) else "false"
        )
        config["auto_connect"] = input(
            f"Auto-connect to servers on startup? ({default_auto_connect}): "
        ).strip().lower() in ("true", "1", "yes", "on", "")
        default_auto_reconnect = (
            "true" if existing_config.get("auto_reconnect", AUTO_RECONNECT) else "false"
        )
        config["auto_reconnect"] = input(
            f"Auto-reconnect if disconnected? ({default_auto_reconnect}): "
        ).strip().lower() in ("true", "1", "yes", "on", "")

        # Buffer settings
        print("\n📊 Buffer Settings:")
        default_log_buffer = existing_config.get("log_buffer_size", LOG_BUFFER_SIZE)
        config["log_buffer_size"] = int(
            input(f"Max log entries in memory ({default_log_buffer}): ").strip()
            or str(default_log_buffer)
        )
        default_gpt_limit = existing_config.get("gpt_history_limit", GPT_HISTORY_LIMIT)
        config["gpt_history_limit"] = int(
            input(f"Max GPT conversation history ({default_gpt_limit}): ").strip()
            or str(default_gpt_limit)
        )

        # AI settings
        print("\n🤖 AI Settings:")
        default_model = existing_config.get("openai_model", "gpt-5.4-nano")
        config["openai_model"] = (
            input(f"OpenAI model ({default_model}): ").strip() or default_model
        )

        # Server configuration
        print("\n🖥️ Server Configuration:")
        existing_servers = existing_config.get("servers", [])
        servers = existing_servers.copy()  # Start with existing servers

        if existing_servers:
            print(f"Found {len(existing_servers)} existing server(s):")
            for i, server in enumerate(existing_servers):
                host = server.get("host", "unknown")
                port = server.get("port", "unknown")
                channels = server.get("channels", [])
                print(f"  {i+1}. {host}:{port} - {len(channels)} channels")
            print()

            # Ask to edit existing servers
            edit_choice = input("Edit existing servers? (y/n): ").strip().lower()
            if edit_choice == "y":
                while True:
                    edit_input = input(
                        "Enter server number to edit (or empty to finish editing): "
                    ).strip()
                    if not edit_input:
                        break
                    try:
                        idx = int(edit_input) - 1
                        if 0 <= idx < len(servers):
                            server = servers[idx]
                            print(f"Editing server {idx+1}:")

                            # Edit host
                            current_host = server.get("host", "")
                            new_host = input(f"Server host ({current_host}): ").strip()
                            if new_host:
                                server["host"] = new_host

                            # Edit port
                            current_port = server.get("port", 6697)
                            new_port_str = input(
                                f"Server port ({current_port}): "
                            ).strip()
                            if new_port_str:
                                try:
                                    server["port"] = int(new_port_str)
                                except ValueError:
                                    print("Invalid port, keeping current.")

                            # Edit TLS
                            current_tls = server.get("tls", True)
                            tls_str = (
                                input(f"Use TLS ({current_tls}): ").strip().lower()
                            )
                            if tls_str in ("true", "false", "1", "0", "yes", "no"):
                                server["tls"] = tls_str in ("true", "1", "yes")

                            # Edit channels
                            current_channels = server.get("channels", [])
                            channels_str = input(
                                f"Channels (comma-separated) ({','.join(current_channels)}): "
                            ).strip()
                            if channels_str:
                                server["channels"] = [
                                    ch.strip()
                                    for ch in channels_str.split(",")
                                    if ch.strip()
                                ]

                            # Edit nick
                            current_nick = server.get("nick")
                            nick_str = input(
                                f"Bot nick (optional, {current_nick or 'global'}): "
                            ).strip()
                            server["nick"] = nick_str if nick_str else None

                            print(f"Server {idx+1} updated.")
                        else:
                            print("Invalid server number.")
                    except ValueError:
                        print("Please enter a valid number.")
                print()
        while True:
            add_server = input("Add another IRC server? (y/n): ").strip().lower()
            if add_server not in ("y", "yes"):
                break

            server = {}
            server["host"] = input("Server host: ").strip()
            if not server["host"]:
                continue
            server["port"] = int(input("Server port (6697): ").strip() or "6697")
            server["tls"] = input("Use TLS? (true): ").strip().lower() in (
                "true",
                "1",
                "yes",
                "on",
                "",
            )
            server["allow_insecure_tls"] = input(
                "Allow insecure TLS? (true): "
            ).strip().lower() in ("true", "1", "yes", "on", "")
            channels = input(
                "Channels (comma-separated, e.g. #channel1,#channel2): "
            ).strip()
            server["channels"] = [
                ch.strip() for ch in channels.split(",") if ch.strip()
            ]
            keys = input(
                "Channel keys/passwords (comma-separated, leave empty if none): "
            ).strip()
            server["keys"] = (
                [k.strip() for k in keys.split(",") if k.strip()] if keys else None
            )
            server["nick"] = (
                input(
                    "Bot nick for this server (optional, defaults to bot_name): "
                ).strip()
                or None
            )
            nickserv = input(
                "NickServ password (optional, for networks requiring registration): "
            ).strip()
            server["nickserv_password"] = nickserv if nickserv else None
            if nickserv:
                email = input(
                    "NickServ email (optional, for first-time registration): "
                ).strip()
                server["nickserv_email"] = email if email else None

            servers.append(server)

        config["servers"] = servers

        # Create data directory if needed
        os.makedirs(os.path.dirname(state_file), exist_ok=True)

        # Create state.json with config and empty state
        state_data = {
            "config": config,
            "state": {
                "last_updated": None,
                "otiedote": {"latest_release": 0, "filters": {}, "subscribers": []},
                "ai_teachings": [],
            },
        }

        try:
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(state_data, f, indent=2, ensure_ascii=False)
            print(f"\n✅ Configuration saved to {state_file}")
            print("🔑 Add your API keys to .env file (see .env.sample)")
        except Exception as e:
            print(f"❌ Failed to save configuration: {e}")

    def _load_server_configs_from_state(self, state_config: dict) -> List[ServerConfig]:
        """
        Load server configurations from state config dict.
        """
        servers = []
        server_list = state_config.get("servers", [])
        logger.info(f"Found {len(server_list)} server entries in state config")

        for i, server_data in enumerate(server_list, 1):
            try:
                logger.info(
                    f"Loading server {i}: {server_data.get('host', 'unknown')}:{server_data.get('port', 'unknown')}"
                )
                config = ServerConfig(
                    host=server_data["host"],
                    port=server_data["port"],
                    channels=server_data["channels"],
                    keys=server_data.get("keys"),
                    tls=server_data.get("tls", False),
                    allow_insecure_tls=server_data.get("allow_insecure_tls", False),
                    name=f"Server{i}",
                    nick=server_data.get("nick"),
                    nickserv_password=server_data.get("nickserv_password"),
                    nickserv_email=server_data.get("nickserv_email"),
                )
                servers.append(config)
                logger.info(f"Successfully loaded server {config.name}")
            except KeyError as e:
                logger.warning(
                    f"Missing required field {e} in server config {i}, skipping"
                )
            except Exception as e:
                logger.warning(f"Error loading server config {i}: {e}, skipping")

        logger.info(f"Total servers loaded: {len(servers)}")
        return servers

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
            ("state_file", "State file"),
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
                "state_file": self.config.state_file,
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
    # Load .env file from project root
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    env_file = os.path.join(project_root, ".env")
    return load_dotenv(env_file)


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
    # Ensure .env file is loaded first
    load_env_file()

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

        # Get channels, keys and TLS settings
        channels_str = os.environ.get(f"{prefix}CHANNELS", "")
        keys_str = os.environ.get(f"{prefix}KEYS", "")
        tls = os.environ.get(f"{prefix}TLS", "false").lower() in (
            "true",
            "1",
            "yes",
        )  # Enable TLS if specified
        allow_insecure_tls = os.environ.get(
            f"{prefix}ALLOW_INSECURE_TLS", "false"
        ).lower() in (
            "true",
            "1",
            "yes",
        )
        nick = (
            os.environ.get(f"{prefix}NICK", "").strip() or None
        )  # Optional per-server nick

        channels = parse_comma_separated_values(channels_str)
        keys = parse_comma_separated_values(keys_str) if keys_str else None

        # Create the server config
        # Use hostname environment variable if set, otherwise use host (IP address)
        hostname = os.environ.get(f"{prefix}HOSTNAME")
        server_name = hostname if hostname else host

        config = ServerConfig(
            host=host,
            port=port,
            channels=channels,
            keys=keys,
            name=server_name,
            tls=tls,
            allow_insecure_tls=allow_insecure_tls,  # Default to allow insecure TLS connections
            nick=nick,
        )

        server_configs.append(config)

    # If no server configs were found, create a default one
    if not server_configs:
        logger.warning(  # noqa: F821
            "Warning: No server configurations found in .env file. Using defaults."
        )
        server_configs.append(
            ServerConfig(
                host="irc.libera.chat",
                port=6667,
                channels=["#test"],
                name="irc.libera.chat",
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

    This function ensures the .env file is properly loaded from the project root
    before attempting to read environment variables. It provides unified API key
    fetching across the entire project.

    Args:
        key_name: Name of the environment variable
        default: Default value if the key doesn't exist

    Returns:
        API key value or default
    """
    # Ensure .env is loaded from project root before reading from os.environ
    # This matches the pattern used in other parts of the codebase
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    env_file = os.path.join(project_root, ".env")

    # Load .env file from project root
    load_dotenv(env_file)

    # Get the API key value
    api_key = os.environ.get(key_name, default)

    # Log the result for debugging (but don't log the actual key value)
    if api_key:
        logger.debug(  # noqa: F821
            f"API key '{key_name}' loaded successfully (length: {len(api_key)})"
        )
    else:
        logger.debug(  # noqa: F821
            f"API key '{key_name}' not found, using default value"
        )

    return api_key


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
