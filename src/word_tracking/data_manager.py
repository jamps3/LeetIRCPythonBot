"""
Data Manager for Word Tracking System

Handles all data persistence using JSON format.
Creates a backup file from the last file.
"""

import json
import os
import shutil
import socket
from datetime import datetime
from typing import Any, Dict, List, Optional

import logger


class DataManager:
    """Manages all data persistence for the word tracking system."""

    def __init__(self, data_dir: str = "."):
        """
        Initialize the data manager.

        Args:
            data_dir: Directory where data files are stored
        """
        self.data_dir = data_dir
        self.drink_data_file = os.path.join(data_dir, "drink_tracking.json")
        self.general_words_file = os.path.join(data_dir, "general_words.json")
        self.state_file = os.path.join(data_dir, "state.json")

        # Initialize data structures
        self._ensure_data_files()

    def _ensure_data_files(self):
        """Ensure all data files exist with proper structure."""
        # Drink tracking data structure
        drink_structure = {
            "servers": {},
            "last_updated": datetime.now().isoformat(),
            "version": "1.0.0",
        }

        # General words data structure
        general_words_structure = {
            "servers": {},
            "last_updated": datetime.now().isoformat(),
            "version": "1.0.0",
        }

        # Merged state file structure
        state_structure = {
            "tamagotchi": {
                "servers": {},
                "global_state": {
                    "level": 1,
                    "experience": 0,
                    "happiness": 50,
                    "hunger": 50,
                    "last_interaction": datetime.now().isoformat(),
                    "mood": "neutral",
                },
                "last_updated": datetime.now().isoformat(),
                "version": "1.0.0",
            },
            "subscriptions": {},
            "fmi_warnings": {
                "seen_hashes": [],
                "seen_data": [],
            },
            "otiedote": {
                "latest_release": 0,
            },
        }

        # Create files if they don't exist
        self._create_file_if_not_exists(self.drink_data_file, drink_structure)
        self._create_file_if_not_exists(
            self.general_words_file, general_words_structure
        )
        self._create_file_if_not_exists(self.state_file, state_structure)

    def _create_file_if_not_exists(
        self, file_path: str, default_structure: Dict[str, Any]
    ):
        """Create a JSON file with default structure if it doesn't exist."""
        if not os.path.exists(file_path):
            self.save_json(file_path, default_structure)

    def load_json(self, file_path: str) -> Dict[str, Any]:
        """
        Load JSON data from file with error handling.

        Args:
            file_path: Path to the JSON file

        Returns:
            Dictionary containing the data
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error loading {file_path}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error loading {file_path}: {e}")
            return {}

    def save_json(self, file_path: str, data: Dict[str, Any], backup: bool = True):
        """
        Save data to JSON file with backup functionality.

        Args:
            file_path: Path to save the JSON file
            data: Data to save
            backup: Whether to create a backup before saving
        """
        temp_path = None
        try:
            # Ensure target directory exists
            target_dir = os.path.dirname(file_path) or "."
            os.makedirs(target_dir, exist_ok=True)

            # Create backup if requested and file exists
            if backup and os.path.exists(file_path):
                backup_path = f"{file_path}.backup"
                shutil.copy2(file_path, backup_path)

            # Update timestamp
            data["last_updated"] = datetime.now().isoformat()

            # Save to a unique temporary file in the same directory, then rename atomically
            import tempfile

            with tempfile.NamedTemporaryFile(
                "w", delete=False, dir=target_dir, suffix=".tmp", encoding="utf-8"
            ) as tmp:
                temp_path = tmp.name
                json.dump(data, tmp, indent=2, ensure_ascii=False)
                tmp.flush()
                os.fsync(tmp.fileno())

            # Atomic replace
            os.replace(temp_path, file_path)
            temp_path = None  # consumed

        except Exception as e:
            logger.error(f"Error saving {file_path}: {e}")
            # Clean up temporary file if it exists
            try:
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception:
                pass

    def get_server_name(self, irc_socket) -> str:
        """
        Get server name from IRC socket.

        Args:
            irc_socket: IRC socket connection

        Returns:
            Server hostname or IP
        """
        try:
            remote_ip, remote_port = irc_socket.getpeername()
            try:
                hostname = socket.gethostbyaddr(remote_ip)[0]
                return hostname
            except (socket.herror, Exception):
                return remote_ip  # Fallback to IP if no reverse DNS or any DNS error
        except Exception:
            return "unknown_server"

    # Data accessor methods
    def load_drink_data(self) -> Dict[str, Any]:
        """Load drink tracking data."""
        return self.load_json(self.drink_data_file)

    def save_drink_data(self, data: Dict[str, Any]):
        """Save drink tracking data."""
        self.save_json(self.drink_data_file, data)

    def load_general_words_data(self) -> Dict[str, Any]:
        """Load general words data."""
        return self.load_json(self.general_words_file)

    def save_general_words_data(self, data: Dict[str, Any]):
        """Save general words data."""
        self.save_json(self.general_words_file, data)

    def load_tamagotchi_state(self) -> Dict[str, Any]:
        """Load tamagotchi state data from merged state.json."""
        state_data = self.load_json(self.state_file)
        return state_data.get("tamagotchi", {})

    def save_tamagotchi_state(self, data: Dict[str, Any]):
        """Save tamagotchi state data to merged state.json."""
        # Load the full state file
        state_data = self.load_json(self.state_file)
        if not state_data:
            # Initialize with default structure if file is empty or corrupted
            state_data = {
                "tamagotchi": {},
                "subscriptions": {},
                "fmi_warnings": {"seen_hashes": [], "seen_data": []},
                "otiedote": {"latest_release": 0},
            }

        # Update the tamagotchi section
        state_data["tamagotchi"] = data

        # Save the full state file
        self.save_json(self.state_file, state_data)

    # Privacy management methods
    def _parse_opt_out_env(self) -> Dict[str, List[str]]:
        """
        Parse the DRINK_TRACKING_OPT_OUT environment variable.

        Returns:
            Dictionary mapping server names to lists of opted-out nicknames
        """
        opt_out_str = os.getenv("DRINK_TRACKING_OPT_OUT", "")
        if not opt_out_str.strip():
            return {}

        result = {}
        try:
            # Split by comma and process each server:nick pair
            pairs = [pair.strip() for pair in opt_out_str.split(",") if pair.strip()]

            for pair in pairs:
                if ":" not in pair:
                    continue

                server, nick = pair.split(":", 1)
                server = server.strip()
                nick = nick.strip()

                if server and nick:
                    if server not in result:
                        result[server] = []
                    if nick not in result[server]:
                        result[server].append(nick)

        except Exception as e:
            logger.error(f"Error parsing DRINK_TRACKING_OPT_OUT: {e}")
            return {}

        return result

    def _format_opt_out_env(self, opt_out_data: Dict[str, List[str]]) -> str:
        """
        Format opt-out data back to environment variable format.

        Args:
            opt_out_data: Dictionary mapping server names to lists of opted-out nicknames

        Returns:
            Formatted string for environment variable
        """
        pairs = []
        for server, nicks in opt_out_data.items():
            for nick in nicks:
                pairs.append(f"{server}:{nick}")
        return ",".join(pairs)

    def _update_opt_out_env(self, opt_out_data: Dict[str, List[str]]) -> bool:
        """
        Update the DRINK_TRACKING_OPT_OUT environment variable.

        Args:
            opt_out_data: Dictionary mapping server names to lists of opted-out nicknames

        Returns:
            True if successful, False otherwise
        """
        try:
            env_value = self._format_opt_out_env(opt_out_data)
            os.environ["DRINK_TRACKING_OPT_OUT"] = env_value
            return True
        except Exception as e:
            logger.error(f"Error updating DRINK_TRACKING_OPT_OUT: {e}")
            return False

    def is_user_opted_out(self, server: str, nick: str) -> bool:
        """
        Check if a user has opted out of drink tracking.

        Args:
            server: Server name
            nick: User nickname

        Returns:
            True if user has opted out, False otherwise
        """
        opt_out_data = self._parse_opt_out_env()
        server_opts = opt_out_data.get(server, [])
        return nick.lower() in [n.lower() for n in server_opts]

    def set_user_opt_out(self, server: str, nick: str, opt_out: bool = True) -> bool:
        """
        Set user's opt-out status for drink tracking.

        Args:
            server: Server name
            nick: User nickname
            opt_out: True to opt out, False to opt back in

        Returns:
            True if successful, False otherwise
        """
        opt_out_data = self._parse_opt_out_env()

        if server not in opt_out_data:
            opt_out_data[server] = []

        server_opts = opt_out_data[server]
        nick_lower = nick.lower()

        if opt_out:
            # Add to opt-out list if not already there
            if nick_lower not in [n.lower() for n in server_opts]:
                server_opts.append(nick)
        else:
            # Remove from opt-out list
            opt_out_data[server] = [n for n in server_opts if n.lower() != nick_lower]

            # Clean up empty server entries
            if not opt_out_data[server]:
                del opt_out_data[server]

        return self._update_opt_out_env(opt_out_data)

    def get_opted_out_users(self, server: Optional[str] = None) -> Dict[str, List[str]]:
        """
        Get all opted-out users, optionally filtered by server.

        Args:
            server: Optional server name to filter by

        Returns:
            Dictionary mapping server names to lists of opted-out nicknames
        """
        opt_out_data = self._parse_opt_out_env()

        if server is not None:
            return {server: opt_out_data.get(server, [])}

        return opt_out_data

    def get_all_servers(self) -> List[str]:
        """
        Return a list of all server names present in general words data.
        """
        data = self.load_general_words_data()
        return list(data.get("servers", {}).keys())
