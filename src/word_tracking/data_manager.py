"""
Data Manager for Word Tracking System

Handles all data persistence using JSON format.
Creates a backup file from the last file.
"""

import json
import os
import socket
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.logger import get_logger
from src.state_utils import save_json_atomic


class DataManager:
    """Manages all data persistence for the word tracking system."""

    # Class-level default for data directory (can be patched in tests)
    _data_dir: str = "data"

    def __init__(self, data_dir: str = None, state_file: Optional[str] = None):
        """
        Initialize the data manager.

        Args:
            data_dir: Directory where data files are stored (defaults to class _data_dir)
            state_file: Path to the state.json file (optional, defaults to data/state.json)
        """
        if data_dir is None:
            data_dir = DataManager._data_dir
        self.data_dir = data_dir
        self.drink_data_file = os.path.join(data_dir, "drink_tracking.json")
        self.general_words_file = os.path.join(data_dir, "general_words.json")
        self.state_file = os.path.normpath(
            state_file or os.path.join(data_dir, "state.json")
        )

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
                },
            },
            "subscriptions": {},
            "fmi_warnings": {"seen_hashes": [], "seen_data": []},
            "otiedote": {
                "latest_release": 0,
            },
            "drink_tracking_opt_out": {},
            "ai_teachings": {},
            "command_history": [],
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
            get_logger(__name__).error(f"Error loading {file_path}: {e}")
            return {}
        except Exception as e:
            get_logger(__name__).error(f"Unexpected error loading {file_path}: {e}")
            return {}

    def save_json(self, file_path: str, data: Dict[str, Any], backup: bool = True):
        """
        Save data to JSON file with backup functionality.

        Args:
            file_path: Path to save the JSON file
            data: Data to save
            backup: Whether to create a backup before saving
        """
        try:
            save_json_atomic(file_path, data, backup=backup)

        except Exception as e:
            get_logger(__name__).error(f"Error saving {file_path}: {e}")

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
                "drink_tracking_opt_out": {},
            }

        # Update the tamagotchi section
        state_data["tamagotchi"] = data

        # Save the full state file
        self.save_json(self.state_file, state_data)

    def load_drink_tracking_opt_out_state(self) -> Dict[str, Any]:
        """Load drink tracking opt-out state data from merged state.json."""
        state_data = self.load_json(self.state_file)
        return state_data.get("drink_tracking_opt_out", {})

    def save_drink_tracking_opt_out_state(self, data: Dict[str, Any]):
        """Save drink tracking opt-out state data to merged state.json."""
        # Load the full state file
        state_data = self.load_json(self.state_file)
        if not state_data:
            # Initialize with default structure if file is empty or corrupted
            state_data = {
                "tamagotchi": {},
                "subscriptions": {},
                "fmi_warnings": {"seen_hashes": [], "seen_data": []},
                "otiedote": {"latest_release": 0},
                "drink_tracking_opt_out": {},
            }

        # Update the drink_tracking_opt_out section
        state_data["drink_tracking_opt_out"] = data

        # Save the full state file
        self.save_json(self.state_file, state_data)

    def is_user_opted_out(self, server: str, nick: str) -> bool:
        """
        Check if a user has opted out of drink tracking.

        Args:
            server: Server name
            nick: User nickname

        Returns:
            True if user has opted out, False otherwise
        """
        opt_out_data = self.load_drink_tracking_opt_out_state()
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
        opt_out_data = self.load_drink_tracking_opt_out_state()

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

        return self.save_drink_tracking_opt_out_state(opt_out_data) is not None

    def get_opted_out_users(self, server: Optional[str] = None) -> Dict[str, List[str]]:
        """
        Get all opted-out users, optionally filtered by server.

        Args:
            server: Optional server name to filter by

        Returns:
            Dictionary mapping server names to lists of opted-out nicknames
        """
        opt_out_data = self.load_drink_tracking_opt_out_state()

        if server is not None:
            return {server: opt_out_data.get(server, [])}

        return opt_out_data

    def load_ksp_state(self) -> Optional[Dict[str, str]]:
        """Load KSP game state from merged state.json."""
        state_data = self.load_json(self.state_file)
        return state_data.get("ksp")

    def save_ksp_state(self, data: Optional[Dict[str, str]]):
        """Save KSP game state to merged state.json."""
        # Load the full state file
        state_data = self.load_json(self.state_file)
        if not state_data:
            # Initialize with default structure if file is empty or corrupted
            state_data = {
                "tamagotchi": {},
                "subscriptions": {},
                "fmi_warnings": {"seen_hashes": [], "seen_data": []},
                "otiedote": {"latest_release": 0},
                "drink_tracking_opt_out": {},
            }

        # Update the ksp section
        if data is None:
            state_data.pop("ksp", None)
        else:
            state_data["ksp"] = data

        # Save the full state file
        self.save_json(self.state_file, state_data)

    def load_kraksdebug_state(self) -> Dict[str, Any]:
        """Load kraksdebug state data from merged state.json."""
        state_data = self.load_json(self.state_file)
        default_kraksdebug = {"channels": [], "nick_notices": True, "nicks": []}
        kraksdebug = state_data.get("kraksdebug", default_kraksdebug)
        if "kraksdebug" not in state_data:
            state_data["kraksdebug"] = kraksdebug
            self.save_json(self.state_file, state_data)
        return kraksdebug

    def save_kraksdebug_state(self, data: Dict[str, Any]):
        """Save kraksdebug state data to merged state.json."""
        # Load the full state file
        state_data = self.load_json(self.state_file)
        if not state_data:
            # Initialize with default structure if file is empty or corrupted
            state_data = {
                "tamagotchi": {},
                "subscriptions": {},
                "fmi_warnings": {"seen_hashes": [], "seen_data": []},
                "otiedote": {"latest_release": 0},
                "drink_tracking_opt_out": {},
            }

        # Update the kraksdebug section
        state_data["kraksdebug"] = data

        # Save the full state file
        self.save_json(self.state_file, state_data)

    def load_leet_winners_state(self) -> Dict[str, Any]:
        """Load leet winners state data from merged state.json."""
        state_data = self.load_json(self.state_file)
        return state_data.get("leet_winners", {})

    def save_leet_winners_state(self, data: Dict[str, Any]):
        """Save leet winners state data to merged state.json."""
        # Load the full state file
        state_data = self.load_json(self.state_file)
        if not state_data:
            # Initialize with default structure if file is empty or corrupted
            state_data = {
                "tamagotchi": {},
                "subscriptions": {},
                "fmi_warnings": {"seen_hashes": [], "seen_data": []},
                "otiedote": {"latest_release": 0},
                "drink_tracking_opt_out": {},
            }

        # Update the leet_winners section
        state_data["leet_winners"] = data

        # Save the full state file
        self.save_json(self.state_file, state_data)

    def load_sanaketju_state(self) -> Dict[str, Any]:
        """Load sanaketju game state data from merged state.json."""
        state_data = self.load_json(self.state_file)
        return state_data.get("sanaketju", {})

    def save_sanaketju_state(self, data: Dict[str, Any]):
        """Save sanaketju game state data to merged state.json."""
        # Load the full state file
        state_data = self.load_json(self.state_file)
        if not state_data:
            # Initialize with default structure if file is empty or corrupted
            state_data = {
                "tamagotchi": {},
                "subscriptions": {},
                "fmi_warnings": {"seen_hashes": [], "seen_data": []},
                "otiedote": {"latest_release": 0},
                "drink_tracking_opt_out": {},
            }

        # Update the sanaketju section
        state_data["sanaketju"] = data

        # Save the full state file
        self.save_json(self.state_file, state_data)

    def load_state(self) -> Dict[str, Any]:
        """Load the full state file."""
        return self.load_json(self.state_file)

    def save_state(self, data: Dict[str, Any]):
        """Save the full state file."""
        self.save_json(self.state_file, data)

    def get_all_servers(self) -> List[str]:
        """
        Return a list of all server names present in general words data.
        """
        data = self.load_general_words_data()
        return list(data.get("servers", {}).keys())

    # AI Teachings methods
    def load_ai_teachings(
        self, network: str = None, channel: str = None
    ) -> List[Dict[str, Any]]:
        """Load AI teachings data from merged state.json.

        Args:
            network: IRC network (e.g., 'irc.libera.chat')
            channel: IRC channel (e.g., '#python')

        Returns:
            List of teachings for the specified network/channel, or global teachings if none specified
        """
        state_data = self.load_json(self.state_file)
        ai_teachings = state_data.get("ai_teachings", {})

        # Handle migration from old list format to new dict format
        if isinstance(ai_teachings, list):
            # Migrate old format to new structure under 'global' key
            migrated = {"global": ai_teachings}
            state_data["ai_teachings"] = migrated
            self.save_json(self.state_file, state_data)
            ai_teachings = migrated

        if network and channel:
            # Return teachings for specific network/channel
            key = f"{network}/{channel}"
            return ai_teachings.get(key, [])
        elif network:
            # Return teachings for specific network (across all channels)
            network_teachings = []
            for key, teachings in ai_teachings.items():
                if key.startswith(f"{network}/"):
                    network_teachings.extend(teachings)
            return network_teachings
        else:
            # Return global teachings (for backward compatibility)
            return ai_teachings.get("global", [])

    def save_ai_teachings(
        self, data: List[Dict[str, Any]], network: str = None, channel: str = None
    ):
        """Save AI teachings data to merged state.json.

        Args:
            data: List of teachings to save
            network: IRC network (optional)
            channel: IRC channel (optional)
        """
        # Load the full state file
        state_data = self.load_json(self.state_file)
        if not state_data:
            # Initialize with default structure if file is empty or corrupted
            state_data = {
                "tamagotchi": {},
                "subscriptions": {},
                "fmi_warnings": {"seen_hashes": [], "seen_data": []},
                "otiedote": {"latest_release": 0},
                "drink_tracking_opt_out": {},
                "ai_teachings": {},
            }

        # Ensure ai_teachings is a dict
        if "ai_teachings" not in state_data:
            state_data["ai_teachings"] = {}
        elif not isinstance(state_data["ai_teachings"], dict):
            # Migrate old list format
            state_data["ai_teachings"] = {"global": state_data["ai_teachings"]}

        # Determine the key for storing teachings
        if network and channel:
            key = f"{network}/{channel}"
        else:
            key = "global"

        # Update the teachings for this key
        state_data["ai_teachings"][key] = data

        # Save the updated state
        self.save_json(self.state_file, state_data)

    def load_command_history(self) -> List[str]:
        """Load command history from merged state.json."""
        state_data = self.load_json(self.state_file)
        return state_data.get("command_history", [])

    def save_command_history(self, history: List[str]):
        """Save command history to merged state.json."""
        # Load the full state file
        state_data = self.load_json(self.state_file)
        if not state_data:
            # Initialize with default structure if file is empty or corrupted
            state_data = {
                "tamagotchi": {},
                "subscriptions": {},
                "fmi_warnings": {"seen_hashes": [], "seen_data": []},
                "otiedote": {"latest_release": 0},
                "drink_tracking_opt_out": {},
                "ai_teachings": {},
                "command_history": [],
            }

        # Update the command_history section
        state_data["command_history"] = history

        # Save the updated state
        self.save_json(self.state_file, state_data)

    def add_teaching(
        self, content: str, added_by: str, network: str = None, channel: str = None
    ) -> int:
        """
        Add a new teaching to the AI knowledge base.

        Args:
            content: The teaching content
            added_by: Who added this teaching
            network: IRC network (optional)
            channel: IRC channel (optional)

        Returns:
            The ID of the new teaching, or -1 if failed (limit reached)
        """
        teachings = self.load_ai_teachings(network, channel)

        # Check 50-item limit per network/channel
        if len(teachings) >= 50:
            return -1

        # Calculate next_id: find the smallest missing ID starting from 1
        existing_ids = {t.get("id", 0) for t in teachings}
        next_id = 1
        while next_id in existing_ids:
            next_id += 1

        # Add new teaching
        new_teaching = {
            "id": next_id,
            "content": content.strip(),
            "added_by": added_by,
            "timestamp": datetime.now().isoformat(),
        }
        teachings.append(new_teaching)

        # Save
        self.save_ai_teachings(teachings, network, channel)
        return next_id

    def remove_teaching(
        self, teaching_id: int, network: str = None, channel: str = None
    ) -> bool:
        """
        Remove a teaching by its ID.

        Args:
            teaching_id: The ID of the teaching to remove
            network: IRC network (optional)
            channel: IRC channel (optional)

        Returns:
            True if removed, False if not found
        """
        teachings = self.load_ai_teachings(network, channel)

        # Find and remove teaching
        original_count = len(teachings)
        teachings = [t for t in teachings if t.get("id") != teaching_id]

        if len(teachings) == original_count:
            return False  # Not found

        # Save
        self.save_ai_teachings(teachings, network, channel)
        return True

    def get_teachings(
        self, network: str = None, channel: str = None
    ) -> List[Dict[str, Any]]:
        """Get all teachings sorted by ID."""
        teachings = self.load_ai_teachings(network, channel)
        return sorted(teachings, key=lambda x: x.get("id", 0))

    def get_teaching_by_id(
        self, teaching_id: int, network: str = None, channel: str = None
    ) -> Optional[Dict[str, Any]]:
        """Get a specific teaching by ID."""
        teachings = self.load_ai_teachings(network, channel)
        for teaching in teachings:
            if teaching.get("id") == teaching_id:
                return teaching
        return None

    def get_teachings_for_context(
        self, max_items: int = 100, network: str = None, channel: str = None
    ) -> List[str]:
        """
        Get teachings formatted for AI context, limited by max_items.

        Args:
            max_items: Maximum number of teachings to return
            network: IRC network (optional)
            channel: IRC channel (optional)

        Returns:
            List of teaching content strings
        """
        teachings = self.get_teachings(network, channel)
        # Return just the content, without IDs to save tokens
        return [t["content"] for t in teachings[:max_items]]


# Singleton instance for shared access
_data_manager_instance = None


def get_data_manager() -> DataManager:
    """
    Get the singleton DataManager instance.

    Returns:
        DataManager instance
    """
    global _data_manager_instance
    if _data_manager_instance is None:
        _data_manager_instance = DataManager()
    return _data_manager_instance
