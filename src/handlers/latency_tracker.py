"""
Latency Tracker Mixin

Provides IRC latency measurement and tracking functionality.
"""

import time
from typing import Any, Dict, Optional

from state_utils import load_json_file, save_json_atomic


class LatencyTrackerMixin:
    """
    Mixin for latency tracking functionality.

    Measures, stores, and retrieves IRC latency data.
    """

    # Abstract properties to be defined by the including class
    data_manager = None

    # File path for lag storage
    LAG_STORAGE_FILE = "data/lag_storage.json"

    def _measure_latency(self):
        """Measure latency by sending a PING and awaiting PONG."""
        return time.time()

    def _send_latency_ping(self, server, target: str) -> str:
        """
        Send a latency PING to the target and return the unique ID.

        Returns:
            Unique ping ID for tracking the response
        """
        ping_id = f"lag_{int(time.time() * 1000)}"
        server.send_raw(f"PING :{ping_id}")
        return ping_id

    def _check_latency_response(self, server, sender: str, text: str) -> Optional[str]:
        """
        Check if a PONG response matches a pending latency measurement.

        Returns:
            Formatted latency string if matched, None otherwise
        """
        if not text.startswith("PONG"):
            return None

        # Extract ping ID from PONG
        parts = text.split(":", 1)
        if len(parts) < 2:
            return None

        ping_id = parts[1].strip()

        # Check if this is a latency ping we sent
        if not ping_id.startswith("lag_"):
            return None

        try:
            ping_time = int(ping_id[4:]) / 1000.0
            lag_ms = (time.time() - ping_time) * 1000

            # Store the lag measurement
            self._store_lag(server.name, sender, lag_ms)

            return f"{lag_ms:.1f}ms"
        except (ValueError, IndexError):
            return None

    def _load_lag_storage(self) -> Dict[tuple, float]:
        """Load lag storage from data file."""
        try:
            data = load_json_file(self.LAG_STORAGE_FILE, default=dict)
            if not isinstance(data, dict):
                return {}
            # Convert dict keys from strings back to tuples
            return {
                (k.split("|")[0], k.split("|")[1]): v
                for k, v in data.items()
                if "|" in k
            }
        except KeyError:
            pass
        return {}

    def _save_lag_storage(self):
        """Save lag storage to data file."""
        try:
            # Convert tuple keys to strings for JSON serialization
            data = {f"{k[0]}|{k[1]}": v for k, v in self._lag_storage.items()}
            save_json_atomic(
                self.LAG_STORAGE_FILE,
                data,
                update_timestamp=False,
                ensure_ascii=True,
            )
        except OSError:
            pass

    def _store_lag(self, server_name: str, nick: str, lag_ms: float):
        """
        Store a lag measurement.

        Args:
            server_name: Name of the server
            nick: Nick of the user
            lag_ms: Lag in milliseconds
        """
        if not hasattr(self, "_lag_storage"):
            self._lag_storage = self._load_lag_storage()

        self._lag_storage[(server_name, nick)] = lag_ms
        self._save_lag_storage()

    def _get_lag(self, server_name: str, nick: str) -> Optional[float]:
        """
        Get lag for a specific user.

        Returns:
            Lag in milliseconds, or None if not found
        """
        if not hasattr(self, "_lag_storage"):
            self._lag_storage = self._load_lag_storage()

        return self._lag_storage.get((server_name, nick))

    def _list_lags(self, server_name: Optional[str] = None) -> Dict[tuple, float]:
        """
        List all lag measurements, optionally filtered by server.

        Returns:
            Dictionary of (server_name, nick) -> lag_ms
        """
        if not hasattr(self, "_lag_storage"):
            self._lag_storage = self._load_lag_storage()

        if server_name:
            return {k: v for k, v in self._lag_storage.items() if k[0] == server_name}
        return dict(self._lag_storage)

    def _clear_lag(self, server_name: str, nick: str) -> bool:
        """
        Clear lag for a specific user.

        Returns:
            True if lag was cleared, False if not found
        """
        if not hasattr(self, "_lag_storage"):
            self._lag_storage = self._load_lag_storage()

        key = (server_name, nick)
        if key in self._lag_storage:
            del self._lag_storage[key]
            self._save_lag_storage()
            return True
        return False
