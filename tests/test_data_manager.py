import json
import os
import tempfile
import threading
import time
from unittest.mock import Mock, patch

import pytest

from word_tracking.data_manager import DataManager


@pytest.fixture
def data_manager():
    """Set up and tear down temporary data manager for testing."""
    temp_dir = tempfile.mkdtemp()
    dm = DataManager(temp_dir)
    yield dm

    # Cleanup temporary directory
    for file in os.listdir(temp_dir):
        file_path = os.path.join(temp_dir, file)
        if os.path.isfile(file_path):
            os.unlink(file_path)
    os.rmdir(temp_dir)


def test_load_json_valid_file(data_manager):
    """Test loading valid JSON file."""
    test_data = {"test": "data", "number": 42}
    test_file = os.path.join(data_manager.data_dir, "test.json")

    with open(test_file, "w", encoding="utf-8") as f:
        json.dump(test_data, f)

    result = data_manager.load_json(test_file)
    assert result == test_data, "Loaded data should match the test data"


def test_load_json_nonexistent_file(data_manager):
    """Test loading non-existent JSON file."""
    test_file = os.path.join(data_manager.data_dir, "nonexistent.json")
    result = data_manager.load_json(test_file)
    assert result == {}, "Non-existent file should return an empty dictionary"


def test_load_json_corrupted_file(data_manager):
    """Test loading corrupted JSON file."""
    test_file = os.path.join(data_manager.data_dir, "corrupted.json")

    with open(test_file, "w", encoding="utf-8") as f:
        f.write('{"invalid": json}')

    result = data_manager.load_json(test_file)
    assert result == {}, "Corrupted file should return an empty dictionary"


def test_load_json_empty_file(data_manager):
    """Test loading empty JSON file."""
    test_file = os.path.join(data_manager.data_dir, "empty.json")

    with open(test_file, "w", encoding="utf-8") as f:
        f.write("")

    result = data_manager.load_json(test_file)
    assert result == {}, "Empty file should return an empty dictionary"


def test_save_json_valid_data(data_manager):
    """Test saving valid JSON data."""
    test_data = {"test": "data", "number": 42}
    test_file = os.path.join(data_manager.data_dir, "test.json")

    data_manager.save_json(test_file, test_data)

    # Verify file was created and contains correct data
    assert os.path.exists(test_file), "Test file should exist"
    with open(test_file, "r", encoding="utf-8") as f:
        saved_data = json.load(f)

    # Check that last_updated was added
    assert "last_updated" in saved_data, "Data should have a last_updated field"
    assert saved_data["test"] == "data", "Saved data should match the test data"
    assert saved_data["number"] == 42, "Saved data should match the test number"


def test_save_json_with_backup(data_manager):
    """Test that backup is created when saving over existing file."""
    test_file = os.path.join(data_manager.data_dir, "test.json")

    # Create initial file
    initial_data = {"initial": "data"}
    with open(test_file, "w", encoding="utf-8") as f:
        json.dump(initial_data, f)

    # Save new data
    new_data = {"new": "data"}
    data_manager.save_json(test_file, new_data)

    # Check backup was created
    backup_file = test_file + ".backup"
    assert os.path.exists(backup_file), "Backup file should exist"

    # Verify backup contains original data
    with open(backup_file, "r", encoding="utf-8") as f:
        backup_data = json.load(f)
    assert backup_data == initial_data, "Backup data should match the initial data"


def test_save_json_atomic_operation(data_manager):
    """Test that save operation is atomic."""
    test_file = os.path.join(data_manager.data_dir, "test.json")
    test_data = {"test": "data"}

    data_manager.save_json(test_file, test_data)

    # Check that temporary file was cleaned up
    temp_files = [f for f in os.listdir(data_manager.data_dir) if f.endswith(".tmp")]
    assert len(temp_files) == 0, "No temporary files should remain"


def test_ensure_data_files_creates_structure(data_manager):
    """Test that data files are created with proper structure."""
    # The DataManager should create files on initialization
    drink_file = os.path.join(data_manager.data_dir, "drink_tracking.json")
    assert os.path.exists(drink_file), "Drink file should exist"

    # Check structure
    with open(drink_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    expected_keys = ["servers", "last_updated", "version"]
    for key in expected_keys:
        assert key in data, f"Key {key} should be in the data"


def test_load_drink_data(data_manager):
    """Test loading drink data."""
    data = data_manager.load_drink_data()
    assert "servers" in data, "Data should contain key 'servers'"
    assert "version" in data, "Data should contain key 'version'"


def test_save_drink_data(data_manager):
    """Test saving drink data."""
    test_data = {
        "servers": {"test_server": {"nicks": {"user1": {"drinks": {}}}}},
        "version": "1.0.0",
    }

    data_manager.save_drink_data(test_data)

    # Verify data was saved
    loaded_data = data_manager.load_drink_data()
    assert (
        loaded_data["servers"] == test_data["servers"]
    ), "Saved servers data should match"


def test_load_privacy_settings(data_manager):
    """Test loading privacy settings."""
    data = data_manager.load_privacy_settings()
    assert "opted_out_users" in data, "Data should contain key 'opted_out_users'"
    assert "version" in data, "Data should contain key 'version'"


def test_save_privacy_settings(data_manager):
    """Test saving privacy settings."""
    test_data = {
        "opted_out_users": {"server1": ["user1", "user2"]},
        "version": "1.0.0",
    }

    data_manager.save_privacy_settings(test_data)

    # Verify data was saved
    loaded_data = data_manager.load_privacy_settings()
    assert (
        loaded_data["opted_out_users"] == test_data["opted_out_users"]
    ), "Saved privacy settings should match"


def test_is_user_opted_out(data_manager):
    """Test checking if user is opted out."""
    # Initially no users opted out
    assert not data_manager.is_user_opted_out(
        "server1", "user1"
    ), "User should not be opted out initially"

    # Add user to opted out list
    data_manager.set_user_opt_out("server1", "user1", True)
    assert data_manager.is_user_opted_out(
        "server1", "user1"
    ), "User should be opted out"

    # Different server should not be affected
    assert not data_manager.is_user_opted_out(
        "server2", "user1"
    ), "User opt-out should not affect other servers"


def test_set_user_opt_out(data_manager):
    """Test setting user opt-out status."""
    # Opt user out
    data_manager.set_user_opt_out("server1", "user1", True)
    assert data_manager.is_user_opted_out(
        "server1", "user1"
    ), "User should be opted out"

    # Opt user back in
    data_manager.set_user_opt_out("server1", "user1", False)
    assert not data_manager.is_user_opted_out(
        "server1", "user1"
    ), "User should not be opted out anymore"


def test_get_server_name_with_socket(data_manager):
    """Test getting server name from socket."""
    # Mock socket with IP address
    mock_socket = Mock()
    mock_socket.getpeername.return_value = ("192.168.1.1", 6667)

    with patch("socket.gethostbyaddr", return_value=("irc.example.com", [], [])):
        server_name = data_manager.get_server_name(mock_socket)
        assert (
            server_name == "irc.example.com"
        ), "Server name should be resolved from IP address"


def test_get_server_name_fallback_to_ip(data_manager):
    """Test getting server name falls back to IP when DNS fails."""
    # Mock socket with IP address
    mock_socket = Mock()
    mock_socket.getpeername.return_value = ("192.168.1.1", 6667)

    with patch("socket.gethostbyaddr", side_effect=Exception("DNS error")):
        server_name = data_manager.get_server_name(mock_socket)
        assert server_name == "192.168.1.1", "Should fallback to IP if DNS fails"


def test_get_server_name_socket_error(data_manager):
    """Test getting server name when socket error occurs."""
    # Mock socket that raises exception
    mock_socket = Mock()
    mock_socket.getpeername.side_effect = Exception("Socket error")

    server_name = data_manager.get_server_name(mock_socket)
    assert (
        server_name == "unknown_server"
    ), "Should return unknown_server on socket error"


def test_concurrent_access_simulation(data_manager):
    """Test handling of concurrent access patterns."""
    test_file = os.path.join(data_manager.data_dir, "concurrent.json")
    write_errors = []
    write_success_count = 0
    lock = threading.Lock()

    def write_data(thread_id):
        nonlocal write_success_count
        try:
            data = {"thread": thread_id, "timestamp": time.time()}
            data_manager.save_json(test_file, data)
            with lock:
                write_success_count += 1
        except Exception as e:
            with lock:
                write_errors.append((thread_id, str(e)))

    # Create fewer threads to reduce Windows file locking issues
    threads = []
    for i in range(3):
        thread = threading.Thread(target=write_data, args=(i,))
        threads.append(thread)

    # Start all threads
    for thread in threads:
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    # Give the system a moment to release file handles
    time.sleep(0.1)

    # At least one write should succeed
    assert write_success_count > 0, f"No writes succeeded. Errors: {write_errors}"

    # If file exists, verify it's valid JSON
    if os.path.exists(test_file):
        data = data_manager.load_json(test_file)
        assert "thread" in data, "Data should contain thread key"


def test_utf8_encoding_handling(data_manager):
    """Test proper UTF-8 encoding handling."""
    test_data = {
        "finnish": "Tämä on testi",
        "emoji": "🤖👍💯",
        "special": "åäö ÅÄÖ",
    }
    test_file = os.path.join(data_manager.data_dir, "utf8.json")

    data_manager.save_json(test_file, test_data)
    loaded_data = data_manager.load_json(test_file)

    assert (
        loaded_data["finnish"] == test_data["finnish"]
    ), "File should handle Finnish characters"
    assert loaded_data["emoji"] == test_data["emoji"], "File should handle emojis"
    assert (
        loaded_data["special"] == test_data["special"]
    ), "File should handle special characters"


def test_large_data_handling(data_manager):
    """Test handling of large data structures."""
    # Create a large data structure
    large_data = {
        "servers": {
            f"server_{i}": {
                "nicks": {
                    f"user_{j}": {"words": {f"word_{k}": k for k in range(100)}}
                    for j in range(50)
                }
            }
            for i in range(10)
        },
        "version": "1.0.0",
    }

    test_file = os.path.join(data_manager.data_dir, "large.json")

    # Should handle large data without issues
    data_manager.save_json(test_file, large_data)
    loaded_data = data_manager.load_json(test_file)

    assert len(loaded_data["servers"]) == 10, "There should be 10 servers in the data"
    assert "server_0" in loaded_data["servers"], "server_0 should be in the data"

    """Set up and tear down temporary data manager for testing."""
    temp_dir = tempfile.mkdtemp()
    dm = DataManager(temp_dir)
    yield dm

    # Cleanup temporary directory
    for file in os.listdir(temp_dir):
        file_path = os.path.join(temp_dir, file)
        if os.path.isfile(file_path):
            os.unlink(file_path)
    os.rmdir(temp_dir)

    def test_load_json_valid_file(self):
        """Test loading valid JSON file."""
        test_data = {"test": "data", "number": 42}
        test_file = os.path.join(self.temp_dir, "test.json")

        with open(test_file, "w", encoding="utf-8") as f:
            json.dump(test_data, f)

        result = self.data_manager.load_json(test_file)
        self.assertEqual(result, test_data)

    def test_load_json_nonexistent_file(self):
        """Test loading non-existent JSON file."""
        test_file = os.path.join(self.temp_dir, "nonexistent.json")
        result = self.data_manager.load_json(test_file)
        self.assertEqual(result, {})

    def test_load_json_corrupted_file(self):
        """Test loading corrupted JSON file."""
        test_file = os.path.join(self.temp_dir, "corrupted.json")

        with open(test_file, "w", encoding="utf-8") as f:
            f.write('{"invalid": json}')

        result = self.data_manager.load_json(test_file)
        self.assertEqual(result, {})

    def test_load_json_empty_file(self):
        """Test loading empty JSON file."""
        test_file = os.path.join(self.temp_dir, "empty.json")

        with open(test_file, "w", encoding="utf-8") as f:
            f.write("")

        result = self.data_manager.load_json(test_file)
        self.assertEqual(result, {})

    def test_save_json_valid_data(self):
        """Test saving valid JSON data."""
        test_data = {"test": "data", "number": 42}
        test_file = os.path.join(self.temp_dir, "test.json")

        self.data_manager.save_json(test_file, test_data)

        # Verify file was created and contains correct data
        self.assertTrue(os.path.exists(test_file))
        with open(test_file, "r", encoding="utf-8") as f:
            saved_data = json.load(f)

        # Check that last_updated was added
        self.assertIn("last_updated", saved_data)
        self.assertEqual(saved_data["test"], "data")
        self.assertEqual(saved_data["number"], 42)

    def test_save_json_with_backup(self):
        """Test that backup is created when saving over existing file."""
        test_file = os.path.join(self.temp_dir, "test.json")

        # Create initial file
        initial_data = {"initial": "data"}
        with open(test_file, "w", encoding="utf-8") as f:
            json.dump(initial_data, f)

        # Save new data
        new_data = {"new": "data"}
        self.data_manager.save_json(test_file, new_data)

        # Check backup was created
        backup_file = test_file + ".backup"
        self.assertTrue(os.path.exists(backup_file))

        # Verify backup contains original data
        with open(backup_file, "r", encoding="utf-8") as f:
            backup_data = json.load(f)
        self.assertEqual(backup_data, initial_data)

    def test_save_json_atomic_operation(self):
        """Test that save operation is atomic."""
        test_file = os.path.join(self.temp_dir, "test.json")
        test_data = {"test": "data"}

        self.data_manager.save_json(test_file, test_data)

        # Check that temporary file was cleaned up
        temp_files = [f for f in os.listdir(self.temp_dir) if f.endswith(".tmp")]
        self.assertEqual(len(temp_files), 0)

    def test_ensure_data_files_creates_structure(self):
        """Test that data files are created with proper structure."""
        # The DataManager should create files on initialization
        drink_file = os.path.join(self.temp_dir, "drink_tracking.json")
        self.assertTrue(os.path.exists(drink_file))

        # Check structure
        with open(drink_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        expected_keys = ["servers", "last_updated", "version"]
        for key in expected_keys:
            self.assertIn(key, data)

    def test_load_drink_data(self):
        """Test loading drink data."""
        data = self.data_manager.load_drink_data()
        self.assertIn("servers", data)
        self.assertIn("version", data)

    def test_save_drink_data(self):
        """Test saving drink data."""
        test_data = {
            "servers": {"test_server": {"nicks": {"user1": {"drinks": {}}}}},
            "version": "1.0.0",
        }

        self.data_manager.save_drink_data(test_data)

        # Verify data was saved
        loaded_data = self.data_manager.load_drink_data()
        self.assertEqual(loaded_data["servers"], test_data["servers"])

    def test_load_privacy_settings(self):
        """Test loading privacy settings."""
        data = self.data_manager.load_privacy_settings()
        self.assertIn("opted_out_users", data)
        self.assertIn("version", data)

    def test_save_privacy_settings(self):
        """Test saving privacy settings."""
        test_data = {
            "opted_out_users": {"server1": ["user1", "user2"]},
            "version": "1.0.0",
        }

        self.data_manager.save_privacy_settings(test_data)

        # Verify data was saved
        loaded_data = self.data_manager.load_privacy_settings()
        self.assertEqual(loaded_data["opted_out_users"], test_data["opted_out_users"])

    def test_is_user_opted_out(self):
        """Test checking if user is opted out."""
        # Initially no users opted out
        self.assertFalse(self.data_manager.is_user_opted_out("server1", "user1"))

        # Add user to opted out list
        self.data_manager.set_user_opt_out("server1", "user1", True)
        self.assertTrue(self.data_manager.is_user_opted_out("server1", "user1"))

        # Different server should not be affected
        self.assertFalse(self.data_manager.is_user_opted_out("server2", "user1"))

    def test_set_user_opt_out(self):
        """Test setting user opt-out status."""
        # Opt user out
        self.data_manager.set_user_opt_out("server1", "user1", True)
        self.assertTrue(self.data_manager.is_user_opted_out("server1", "user1"))

        # Opt user back in
        self.data_manager.set_user_opt_out("server1", "user1", False)
        self.assertFalse(self.data_manager.is_user_opted_out("server1", "user1"))

    def test_get_server_name_with_socket(self):
        """Test getting server name from socket."""
        from unittest.mock import Mock

        # Mock socket with IP address
        mock_socket = Mock()
        mock_socket.getpeername.return_value = ("192.168.1.1", 6667)

        with patch("socket.gethostbyaddr", return_value=("irc.example.com", [], [])):
            server_name = self.data_manager.get_server_name(mock_socket)
            self.assertEqual(server_name, "irc.example.com")

    def test_get_server_name_fallback_to_ip(self):
        """Test getting server name falls back to IP when DNS fails."""
        from unittest.mock import Mock

        # Mock socket with IP address
        mock_socket = Mock()
        mock_socket.getpeername.return_value = ("192.168.1.1", 6667)

        with patch("socket.gethostbyaddr", side_effect=Exception("DNS error")):
            server_name = self.data_manager.get_server_name(mock_socket)
            self.assertEqual(server_name, "192.168.1.1")

    def test_get_server_name_socket_error(self):
        """Test getting server name when socket error occurs."""
        from unittest.mock import Mock

        # Mock socket that raises exception
        mock_socket = Mock()
        mock_socket.getpeername.side_effect = Exception("Socket error")

        server_name = self.data_manager.get_server_name(mock_socket)
        self.assertEqual(server_name, "unknown_server")

    def test_concurrent_access_simulation(self):
        """Test handling of concurrent access patterns."""
        import threading
        import time

        test_file = os.path.join(self.temp_dir, "concurrent.json")
        write_errors = []
        write_success_count = 0
        lock = threading.Lock()

        def write_data(thread_id):
            nonlocal write_success_count
            try:
                data = {"thread": thread_id, "timestamp": time.time()}
                self.data_manager.save_json(test_file, data)
                with lock:
                    write_success_count += 1
            except Exception as e:
                with lock:
                    write_errors.append((thread_id, str(e)))

        # Create fewer threads to reduce Windows file locking issues
        threads = []
        for i in range(3):
            thread = threading.Thread(target=write_data, args=(i,))
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Give the system a moment to release file handles
        time.sleep(0.1)

        # At least one write should succeed
        self.assertGreater(
            write_success_count, 0, f"No writes succeeded. Errors: {write_errors}"
        )

        # If file exists, verify it's valid JSON
        if os.path.exists(test_file):
            data = self.data_manager.load_json(test_file)
            self.assertIn("thread", data)

    def test_utf8_encoding_handling(self):
        """Test proper UTF-8 encoding handling."""
        test_data = {
            "finnish": "Tämä on testi",
            "emoji": "🤖👍💯",
            "special": "åäö ÅÄÖ",
        }
        test_file = os.path.join(self.temp_dir, "utf8.json")

        self.data_manager.save_json(test_file, test_data)
        loaded_data = self.data_manager.load_json(test_file)

        self.assertEqual(loaded_data["finnish"], test_data["finnish"])
        self.assertEqual(loaded_data["emoji"], test_data["emoji"])
        self.assertEqual(loaded_data["special"], test_data["special"])

    def test_large_data_handling(self):
        """Test handling of large data structures."""
        # Create a large data structure
        large_data = {
            "servers": {
                f"server_{i}": {
                    "nicks": {
                        f"user_{j}": {"words": {f"word_{k}": k for k in range(100)}}
                        for j in range(50)
                    }
                }
                for i in range(10)
            },
            "version": "1.0.0",
        }

        test_file = os.path.join(self.temp_dir, "large.json")

        # Should handle large data without issues
        self.data_manager.save_json(test_file, large_data)
        loaded_data = self.data_manager.load_json(test_file)

        self.assertEqual(len(loaded_data["servers"]), 10)
        self.assertIn("server_0", loaded_data["servers"])
