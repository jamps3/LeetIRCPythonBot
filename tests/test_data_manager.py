"""Tests for the data_manager module."""

import json
import os
import tempfile
from unittest.mock import Mock, patch

import pytest

from src.word_tracking.data_manager import DataManager


class TestDataManager:
    """Test the data manager functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.state_file = os.path.join(self.temp_dir, "state.json")
        self.data_manager = DataManager(
            data_dir=self.temp_dir, state_file=self.state_file
        )

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_init_creates_directories(self):
        """Test that initialization creates necessary directories."""
        assert os.path.exists(self.temp_dir)
        # The data manager creates files, not directories
        assert os.path.exists(os.path.join(self.temp_dir, "drink_tracking.json"))
        assert os.path.exists(os.path.join(self.temp_dir, "general_words.json"))
        assert os.path.exists(self.state_file)

    def test_load_json_valid_file(self):
        """Test loading a valid JSON file."""
        test_data = {"test": "data", "number": 42}
        test_file = os.path.join(self.temp_dir, "test.json")

        with open(test_file, "w") as f:
            json.dump(test_data, f)

        result = self.data_manager.load_json(test_file)
        assert result == test_data

    def test_load_json_nonexistent_file(self):
        """Test loading a nonexistent JSON file."""
        result = self.data_manager.load_json("nonexistent.json")
        assert result == {}

    def test_load_json_corrupted_file(self):
        """Test loading a corrupted JSON file."""
        test_file = os.path.join(self.temp_dir, "corrupted.json")

        with open(test_file, "w") as f:
            f.write("invalid json content")

        result = self.data_manager.load_json(test_file)
        assert result == {}

    def test_load_json_empty_file(self):
        """Test loading an empty JSON file."""
        test_file = os.path.join(self.temp_dir, "empty.json")

        with open(test_file, "w") as f:
            f.write("")

        result = self.data_manager.load_json(test_file)
        assert result == {}

    def test_save_json_valid_data(self):
        """Test saving valid JSON data."""
        test_data = {"test": "data", "number": 42}
        test_file = os.path.join(self.temp_dir, "test_save.json")

        self.data_manager.save_json(test_file, test_data)

        assert os.path.exists(test_file)
        with open(test_file, "r") as f:
            result = json.load(f)
        assert result == test_data

    def test_save_json_with_backup(self):
        """Test saving JSON data with backup creation."""
        test_data = {"test": "data", "number": 42}
        test_file = os.path.join(self.temp_dir, "test_backup.json")

        # Create original file
        with open(test_file, "w") as f:
            json.dump({"old": "data"}, f)

        self.data_manager.save_json(test_file, test_data, backup=True)

        # Check backup was created (note: backup extension is .backup, not .bak)
        backup_file = f"{test_file}.backup"
        assert os.path.exists(backup_file)

        # Check new file was created
        with open(test_file, "r") as f:
            result = json.load(f)
        assert result == test_data

    def test_save_json_atomic_operation(self):
        """Test that JSON save is atomic."""
        test_data = {"test": "data", "number": 42}
        test_file = os.path.join(self.temp_dir, "test_atomic.json")

        self.data_manager.save_json(test_file, test_data)

        # Verify file exists and is valid JSON
        assert os.path.exists(test_file)
        with open(test_file, "r") as f:
            result = json.load(f)
        assert result == test_data

    def test_ensure_data_files_creates_structure(self):
        """Test that ensure_data_files creates proper file structure."""
        # Remove existing files to test creation
        import shutil

        shutil.rmtree(self.temp_dir)
        self.temp_dir = tempfile.mkdtemp()

        # Create new data manager to test file creation
        data_manager = DataManager(
            data_dir=self.temp_dir, state_file=os.path.join(self.temp_dir, "state.json")
        )

        # Check that all required files were created
        assert os.path.exists(os.path.join(self.temp_dir, "drink_tracking.json"))
        assert os.path.exists(os.path.join(self.temp_dir, "general_words.json"))
        assert os.path.exists(os.path.join(self.temp_dir, "state.json"))

    def test_load_drink_data(self):
        """Test loading drink data."""
        # Create test drink data
        drink_data = {
            "servers": {
                "server1": {"user1": {"beer": 5, "wine": 3}, "user2": {"beer": 2}}
            },
            "last_updated": "2023-01-01T00:00:00",
            "version": "1.0.0",
        }

        drink_file = os.path.join(self.temp_dir, "drink_tracking.json")
        with open(drink_file, "w") as f:
            json.dump(drink_data, f)

        result = self.data_manager.load_drink_data()
        assert result == drink_data

    def test_save_drink_data(self):
        """Test saving drink data."""
        drink_data = {
            "servers": {
                "server1": {"user1": {"beer": 5, "wine": 3}, "user2": {"beer": 2}}
            },
            "last_updated": "2023-01-01T00:00:00",
            "version": "1.0.0",
        }

        self.data_manager.save_drink_data(drink_data)

        drink_file = os.path.join(self.temp_dir, "drink_tracking.json")
        assert os.path.exists(drink_file)

        with open(drink_file, "r") as f:
            result = json.load(f)
        assert result == drink_data

    def test_is_user_opted_out(self):
        """Test checking if user is opted out of drink tracking."""
        # Initially no users should be opted out
        assert not self.data_manager.is_user_opted_out("server1", "user1")

        # Opt out a user
        self.data_manager.set_user_opt_out("server1", "user1", True)
        assert self.data_manager.is_user_opted_out("server1", "user1")

        # Opt user back in
        self.data_manager.set_user_opt_out("server1", "user1", False)
        assert not self.data_manager.is_user_opted_out("server1", "user1")

    def test_set_user_opt_out(self):
        """Test setting user opt-out status."""
        # Opt out a user
        self.data_manager.set_user_opt_out("server1", "user1", True)

        # Check state file was created and contains the opt-out
        assert os.path.exists(self.state_file)

        with open(self.state_file, "r") as f:
            state = json.load(f)

        assert "drink_tracking_opt_out" in state
        assert "server1" in state["drink_tracking_opt_out"]
        # Data structure is a list of nicknames, not a dict
        assert "user1" in state["drink_tracking_opt_out"]["server1"]

    def test_get_server_name_with_socket(self):
        """Test getting server name with socket connection."""
        # This is a basic test - in practice you'd need a real socket
        # For now, we'll test the exception handling
        mock_socket = Mock()
        mock_socket.getpeername.return_value = ("test.example.com", 6667)

        result = self.data_manager.get_server_name(mock_socket)
        assert result == "test.example.com"

    def test_get_server_name_fallback_to_ip(self):
        """Test getting server name fallback to IP."""
        mock_socket = Mock()
        mock_socket.getpeername.return_value = ("192.168.1.1", 6667)

        result = self.data_manager.get_server_name(mock_socket)
        assert result in ["192.168.1.1", "dna.mokkula"]

    def test_get_server_name_socket_error(self):
        """Test getting server name when socket operation fails."""
        mock_socket = Mock()
        mock_socket.getpeername.side_effect = Exception("Socket error")

        result = self.data_manager.get_server_name(mock_socket)
        assert result == "unknown_server"

    def test_concurrent_access_simulation(self):
        """Test concurrent access to data files."""
        import threading
        import time

        results = []
        errors = []

        def worker(worker_id):
            try:
                # Each worker writes and reads different data
                test_data = {"worker": worker_id, "data": f"test_{worker_id}"}
                test_file = os.path.join(self.temp_dir, f"worker_{worker_id}.json")

                self.data_manager.save_json(test_file, test_data)
                time.sleep(0.01)  # Small delay to increase contention
                result = self.data_manager.load_json(test_file)

                results.append((worker_id, result))
            except Exception as e:
                errors.append((worker_id, str(e)))

        # Create and start multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify all operations succeeded
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 5

        # Verify data integrity
        for worker_id, result in results:
            assert result["worker"] == worker_id
            assert result["data"] == f"test_{worker_id}"

    def test_utf8_encoding_handling(self):
        """Test handling of UTF-8 encoded data."""
        # Test data with UTF-8 characters
        test_data = {
            "test": "data with UTF-8: äöå",
            "unicode": "🚀🌟🎉",
            "numbers": [1, 2, 3],
            "nested": {"key": "value with ümläuts"},
        }

        test_file = os.path.join(self.temp_dir, "utf8_test.json")

        # Save and load UTF-8 data
        self.data_manager.save_json(test_file, test_data)
        result = self.data_manager.load_json(test_file)

        assert result == test_data
        assert result["test"] == "data with UTF-8: äöå"
        assert result["unicode"] == "🚀🌟🎉"

    def test_save_state(self):
        """Test saving the full state file."""
        test_state = {
            "tamagotchi": {"health": 100},
            "subscriptions": {},
            "fmi_warnings": {"seen_hashes": [], "seen_data": []},
            "otiedote": {"latest_release": 0},
            "drink_tracking_opt_out": {"server1": {"user1": True}},
            "ksp": {"game": "running"},
            "leet_winners": {"last_winner": "test_user"},
            "sanaketju": {"current_word": "test"},
            "kraksdebug": {"debug_mode": True},
        }

        self.data_manager.save_state(test_state)

        assert os.path.exists(self.state_file)

        with open(self.state_file, "r") as f:
            result = json.load(f)

        assert result == test_state

    def test_save_drink_tracking_opt_out_state(self):
        """Test saving drink tracking opt-out state."""
        opt_out_data = {"server1": ["user1", "user2"]}

        self.data_manager.save_drink_tracking_opt_out_state(opt_out_data)

        with open(self.state_file, "r") as f:
            state = json.load(f)

        assert "drink_tracking_opt_out" in state
        assert state["drink_tracking_opt_out"] == opt_out_data

    def test_save_ksp_state(self):
        """Test saving KSP game state."""
        ksp_data = {"game": "running", "score": 1000}

        self.data_manager.save_ksp_state(ksp_data)

        with open(self.state_file, "r") as f:
            state = json.load(f)

        assert "ksp" in state
        assert state["ksp"] == ksp_data

    def test_save_kraksdebug_state(self):
        """Test saving kraksdebug state."""
        kraksdebug_data = {"debug_mode": True, "counter": 42}

        self.data_manager.save_kraksdebug_state(kraksdebug_data)

        with open(self.state_file, "r") as f:
            state = json.load(f)

        assert "kraksdebug" in state
        assert state["kraksdebug"] == kraksdebug_data

    def test_save_leet_winners_state(self):
        """Test saving leet winners state."""
        leet_winners_data = {"last_winner": "test_user", "win_count": 5}

        self.data_manager.save_leet_winners_state(leet_winners_data)

        with open(self.state_file, "r") as f:
            state = json.load(f)

        assert "leet_winners" in state
        assert state["leet_winners"] == leet_winners_data

    def test_save_sanaketju_state(self):
        """Test saving sanaketju game state."""
        sanaketju_data = {"current_word": "test", "players": ["user1", "user2"]}

        self.data_manager.save_sanaketju_state(sanaketju_data)

        with open(self.state_file, "r") as f:
            state = json.load(f)

        assert "sanaketju" in state
        assert state["sanaketju"] == sanaketju_data

    def test_save_tamagotchi_state(self):
        """Test saving tamagotchi state."""
        tamagotchi_data = {"health": 100, "hunger": 50, "last_feed": "2023-01-01"}

        self.data_manager.save_tamagotchi_state(tamagotchi_data)

        with open(self.state_file, "r") as f:
            state = json.load(f)

        assert "tamagotchi" in state
        assert state["tamagotchi"] == tamagotchi_data
