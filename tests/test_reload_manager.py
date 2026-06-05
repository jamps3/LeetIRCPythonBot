"""Tests for the reload_manager module."""

import sys
from types import ModuleType
from unittest.mock import Mock, patch

import reload_manager


class TestReloadManager:
    """Test the reload manager functionality."""

    def test_get_loaded_modules(self):
        """Test getting currently loaded reloadable modules."""
        # Initially, no modules should be loaded
        loaded = reload_manager.get_loaded_modules()
        assert isinstance(loaded, set)

        with patch.dict(
            sys.modules, {"command_registry": ModuleType("command_registry")}
        ):
            loaded = reload_manager.get_loaded_modules()
            assert "command_registry" in loaded

    def test_clear_module_caches(self):
        """Test clearing module caches."""
        module = ModuleType("test_module")
        module._commands_cache = {}
        module._some_other_cache = []
        module.__cache_info = "info"
        module.normal_attribute = "value"

        with patch.dict(sys.modules, {"test_module": module}):
            reload_manager.clear_module_caches("test_module")

        assert not hasattr(module, "_commands_cache")
        assert not hasattr(module, "_some_other_cache")
        assert not hasattr(module, "__cache_info")
        assert module.normal_attribute == "value"

    def test_reload_single_module_not_loaded(self):
        """Test reloading a module that is not loaded."""
        result, message = reload_manager.reload_single_module("nonexistent_module")
        assert result is False
        assert "not loaded" in message

    @patch("importlib.reload")
    def test_reload_single_module_success(self, mock_reload):
        """Test successful module reload."""
        # Create a mock module
        mock_module = Mock()
        sys.modules["test_module"] = mock_module

        result, message = reload_manager.reload_single_module("test_module")

        assert result is True
        assert "Reloaded test_module" in message
        mock_reload.assert_called_once_with(mock_module)

    @patch("importlib.reload")
    def test_reload_single_module_failure(self, mock_reload):
        """Test module reload failure."""
        mock_reload.side_effect = Exception("Import error")

        # Create a mock module
        mock_module = Mock()
        sys.modules["test_module"] = mock_module

        result, message = reload_manager.reload_single_module("test_module")

        assert result is False
        assert "Failed to reload test_module" in message

    @patch("command_registry.get_command_registry")
    @patch("reload_manager.reload_single_module")
    def test_reload_all_commands_with_failures(
        self, mock_reload_single, mock_get_registry
    ):
        """Test reload with some module failures."""
        # Mock the registry
        mock_registry = Mock()
        mock_registry._commands = {"cmd1": Mock()}
        mock_registry.clear_all = Mock()
        mock_get_registry.return_value = mock_registry

        # Mock some failures - make sure at least one module fails
        def side_effect(module_name):
            if module_name == "command_registry":
                return False, f"Failed to reload {module_name}"
            return True, f"Reloaded {module_name}"

        mock_reload_single.side_effect = side_effect

        # Mock loaded modules
        with patch("sys.modules", {"command_registry": Mock()}):
            result, message = reload_manager.reload_all_commands()

        assert result is False
        assert "errors" in message
        assert "Failed" in message

    @patch("reload_manager.reload_single_module")
    def test_reload_specific_module_success(self, mock_reload_single):
        """Test successful reload of specific module."""
        mock_reload_single.return_value = (True, "Reloaded module")

        result, message = reload_manager.reload_specific_module("command_registry")

        assert result is True
        assert "Reloaded command_registry" in message

    def test_reload_specific_module_unknown(self):
        """Test reload of unknown module."""
        result, message = reload_manager.reload_specific_module("unknown_module")

        assert result is False
        assert "Unknown reloadable module" in message

    def test_get_reload_status(self):
        """Test getting reload status."""
        status = reload_manager.get_reload_status()

        assert isinstance(status, dict)
        assert "available_modules" in status
        assert "available_services" in status
        assert "available_core" in status
        assert "loaded_modules" in status
        assert "loaded_services" in status
        assert "loaded_core" in status
        assert "loaded_count" in status
        assert "service_count" in status
        assert "core_count" in status
        assert "command_count" in status

    def test_verify_critical_commands_all_present(self):
        """Test verification when all critical commands are present."""
        # Import and load commands to ensure they exist
        from command_loader import load_all_commands

        load_all_commands()

        # Now verify - should return empty list
        missing = reload_manager.verify_critical_commands()

        assert missing == [], f"Expected no missing commands, got: {missing}"

    def test_verify_critical_commands_missing(self):
        """Test verification when critical commands are missing."""
        from command_loader import load_all_commands
        from command_registry import get_command_registry

        # First ensure commands are loaded
        load_all_commands()
        registry = get_command_registry()

        original_commands = registry._commands.copy()
        original_aliases = registry._aliases.copy()
        try:
            registry.unregister("help")
            registry.unregister("latency")
            assert reload_manager.verify_critical_commands() == ["help", "latency"]
        finally:
            registry._commands = original_commands
            registry._aliases = original_aliases

    def test_load_all_commands_reregisters_cached_modules_after_registry_reset(self):
        """Cached modular commands are restored after the registry is cleared."""
        from command_loader import load_all_commands
        from command_registry import get_command_registry, reset_command_registry

        load_all_commands()
        assert get_command_registry().get_handler("help")

        reset_command_registry()
        assert not get_command_registry()._commands

        load_all_commands()
        assert get_command_registry().get_handler("help")
        assert get_command_registry().get_handler("latency")

    def test_reload_lock_prevents_concurrent_access(self):
        """Test that reload lock prevents concurrent reloads."""
        # This is a basic test - in practice you'd need more sophisticated
        # testing with threading to verify the lock actually works
        assert hasattr(reload_manager, "_reload_lock")
        # Use type checking instead of isinstance for threading.Lock compatibility
        # across different Python versions (Lock is not always a type in 3.13+)
        lock = reload_manager._reload_lock
        lock_type = type(lock)
        assert "lock" in lock_type.__name__.lower() or hasattr(lock, "acquire")

    def test_reloadable_modules_list(self):
        """Test that reloadable modules list is properly defined."""
        assert isinstance(reload_manager.RELOADABLE_MODULES, list)
        assert len(reload_manager.RELOADABLE_MODULES) > 0
        assert "command_registry" in reload_manager.RELOADABLE_MODULES
        assert "command_loader" in reload_manager.RELOADABLE_MODULES

    def test_service_modules_list(self):
        """Test that service modules list is properly defined."""
        assert isinstance(reload_manager.SERVICE_MODULES, list)
        assert len(reload_manager.SERVICE_MODULES) > 0
        assert "services.youtube_service" in reload_manager.SERVICE_MODULES

    def test_word_tracking_modules_list(self):
        """Test that word tracking modules list is properly defined."""
        assert isinstance(reload_manager.WORD_TRACKING_MODULES, list)
        assert len(reload_manager.WORD_TRACKING_MODULES) > 0
        assert "word_tracking.data_manager" in reload_manager.WORD_TRACKING_MODULES

    def test_core_modules_list(self):
        """Test that core modules list is properly defined."""
        assert isinstance(reload_manager.CORE_MODULES, list)
        assert len(reload_manager.CORE_MODULES) > 0
        assert "config" in reload_manager.CORE_MODULES
        assert "subscriptions" in reload_manager.CORE_MODULES

    @patch("reload_manager.reload_single_module")
    def test_reload_specific_module_accepts_subscriptions(self, mock_reload_single):
        """Subscription topic validation must be refreshable without restart."""
        mock_reload_single.return_value = (True, "Reloaded subscriptions")

        result, message = reload_manager.reload_specific_module("subscriptions")

        assert result is True
        assert message == "Reloaded module: subscriptions"
        mock_reload_single.assert_called_once_with("subscriptions")

    @patch("command_registry.get_command_registry")
    @patch("reload_manager.reload_single_module")
    def test_reload_all_commands_reloads_loaded_subscriptions(
        self, mock_reload_single, mock_get_registry
    ):
        """Hot reload updates shared subscription topic validation constants."""
        mock_registry = Mock()
        mock_registry._commands = {}
        mock_registry.clear_all = Mock()
        mock_get_registry.return_value = mock_registry
        mock_reload_single.return_value = (True, "Reloaded module")
        command_registry_module = ModuleType("command_registry")
        command_registry_module.get_command_registry = mock_get_registry
        command_loader_module = ModuleType("command_loader")
        command_loader_module.load_all_commands = Mock()

        with (
            patch.dict(
                sys.modules,
                {
                    "config": ModuleType("config"),
                    "subscriptions": ModuleType("subscriptions"),
                    "command_registry": command_registry_module,
                    "command_loader": command_loader_module,
                },
            ),
        ):
            result, _ = reload_manager.reload_all_commands()

        assert result is True
        reloaded = [call.args[0] for call in mock_reload_single.call_args_list]
        assert reloaded.index("config") < reloaded.index("subscriptions")
        assert reloaded.index("subscriptions") < reloaded.index("command_registry")
