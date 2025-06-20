"""
Configuration System Tests

Comprehensive tests for the configuration management system.
"""

import os
import sys
import tempfile
import json

# Add the parent directory to Python path to ensure imports work in CI
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from test_framework import TestCase, TestSuite, TestRunner


def test_config_loading():
    """Test basic configuration loading."""
    try:
        from config import get_config_manager, get_config

        config_manager = get_config_manager()
        config = get_config()

        # Basic validation
        assert config.name is not None, "Bot name should be set"
        assert config.version is not None, "Version should be set"
        assert isinstance(config.servers, list), "Servers should be a list"

        return True
    except Exception as e:
        print(f"Config loading test failed: {e}")
        return False


def test_config_validation():
    """Test configuration validation."""
    try:
        from config import get_config_manager

        config_manager = get_config_manager()
        errors = config_manager.validate_config()

        # Should not have critical errors
        critical_errors = [e for e in errors if "not found" in e.lower()]

        if critical_errors:
            print(f"Critical config errors: {critical_errors}")
            return False

        return True
    except Exception as e:
        print(f"Config validation test failed: {e}")
        return False


def test_server_config_parsing():
    """Test server configuration parsing."""
    try:
        from config import get_config_manager

        config_manager = get_config_manager()
        config = config_manager.config

        if not config.servers:
            print("No servers configured")
            return False

        server = config.servers[0]

        # Validate server structure
        assert hasattr(server, "host"), "Server should have host"
        assert hasattr(server, "port"), "Server should have port"
        assert hasattr(server, "channels"), "Server should have channels"
        assert isinstance(server.port, int), "Port should be integer"
        assert isinstance(server.channels, list), "Channels should be list"

        return True
    except Exception as e:
        print(f"Server config parsing test failed: {e}")
        return False


def test_environment_variable_handling():
    """Test environment variable handling."""
    try:
        from config import ConfigManager
        import os

        # Save current environment state
        original_bot_name = os.environ.get("BOT_NAME")

        # Create temporary .env file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("BOT_NAME=test_bot\n")
            f.write("TEST_VAR=test_value\n")
            temp_env_path = f.name

        try:
            # Clear any existing BOT_NAME from environment
            if "BOT_NAME" in os.environ:
                del os.environ["BOT_NAME"]

            # Test loading from specific file
            manager = ConfigManager(temp_env_path)

            # Check if bot name was loaded from the temporary file
            config = manager.config
            assert config.name == "test_bot", f"Expected test_bot, got {config.name}"

            return True
        finally:
            # Restore original environment
            if original_bot_name is not None:
                os.environ["BOT_NAME"] = original_bot_name
            elif "BOT_NAME" in os.environ:
                del os.environ["BOT_NAME"]

            os.unlink(temp_env_path)

    except Exception as e:
        print(f"Environment variable test failed: {e}")
        return False


def test_config_json_export():
    """Test configuration JSON export functionality."""
    try:
        from config import get_config_manager

        config_manager = get_config_manager()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_json_path = f.name

        try:
            config_manager.save_config_to_json(temp_json_path)

            # Verify file was created and contains valid JSON
            # Use UTF-8 encoding explicitly to handle any Unicode characters
            with open(temp_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Check structure
            assert "bot" in data, "JSON should contain bot section"
            assert "servers" in data, "JSON should contain servers section"
            assert "files" in data, "JSON should contain files section"

            # Verify bot section has required fields
            bot_section = data["bot"]
            assert "name" in bot_section, "Bot section should have name"
            assert "version" in bot_section, "Bot section should have version"

            return True
        finally:
            if os.path.exists(temp_json_path):
                os.unlink(temp_json_path)

    except Exception as e:
        print(f"Config JSON export test failed: {e}")
        return False


def test_config_server_lookup():
    """Test server configuration lookup functionality."""
    try:
        from config import get_config_manager

        config_manager = get_config_manager()

        # Test primary server lookup
        primary = config_manager.get_primary_server()
        assert primary is not None, "Should have a primary server"

        # Test server lookup by name
        if config_manager.config.servers:
            server_name = config_manager.config.servers[0].name
            found_server = config_manager.get_server_by_name(server_name)
            assert found_server is not None, f"Should find server {server_name}"
            assert found_server.name == server_name, "Should return correct server"

        # Test non-existent server
        non_existent = config_manager.get_server_by_name("NON_EXISTENT")
        assert non_existent is None, "Should return None for non-existent server"

        return True
    except Exception as e:
        print(f"Config server lookup test failed: {e}")
        return False


def register_config_tests(runner: TestRunner):
    """Register configuration tests with the test runner."""

    tests = [
        TestCase(
            name="config_loading",
            description="Test basic configuration loading",
            test_func=test_config_loading,
            category="config",
            dependencies=["file:.env"],
        ),
        TestCase(
            name="config_validation",
            description="Test configuration validation",
            test_func=test_config_validation,
            category="config",
        ),
        TestCase(
            name="server_config_parsing",
            description="Test server configuration parsing",
            test_func=test_server_config_parsing,
            category="config",
        ),
        TestCase(
            name="environment_variable_handling",
            description="Test environment variable handling",
            test_func=test_environment_variable_handling,
            category="config",
        ),
        TestCase(
            name="config_json_export",
            description="Test configuration JSON export",
            test_func=test_config_json_export,
            category="config",
        ),
        TestCase(
            name="config_server_lookup",
            description="Test server configuration lookup",
            test_func=test_config_server_lookup,
            category="config",
        ),
    ]

    suite = TestSuite(
        name="Configuration",
        description="Tests for configuration management system",
        tests=tests,
    )

    runner.add_suite(suite)
