"""
Reload Manager for hot-reloading bot components.

This module provides functionality to reload command modules and related Python files
without restarting the IRC bot, enabling rapid iteration during development and
hot-fixes on production systems.
"""

import importlib
import sys
import threading
from typing import Callable, Dict, List, Optional, Set, Tuple

import logger

# Modules that can be reloaded - order matters (dependencies first)
RELOADABLE_MODULES: List[str] = [
    # Base modules first
    "command_registry",
    "command_loader",
    # Backward compatibility modules
    "commands",
    # cmd_modules subpackages (modular command structure)
    "cmd_modules.basic",
    "cmd_modules.admin",
    "cmd_modules.games",
    "cmd_modules.misc",
    "cmd_modules.services",
    "cmd_modules.word_tracking",
]

# Service modules to reload (imported by commands_services)
SERVICE_MODULES: List[str] = [
    "services.youtube_service",
    "services.weather_service",
    "services.weather_forecast_service",
    "services.electricity_service",
    "services.crypto_service",
    "services.gpt_service",
    "services.alko_service",
    "services.drug_service",
    "services.digitraffic_service",
    "services.fmi_warning_service",
    "services.otiedote_json_service",
    "services.scheduled_message_service",
    "services.eurojackpot_service",
    "services.solarwind_service",
    "services.ipfs_service",
    "services.imdb_service",
    "services.url_tracker_service",
]

# Word tracking modules to reload
WORD_TRACKING_MODULES: List[str] = [
    "word_tracking.data_manager",
    "word_tracking.drink_tracker",
    "word_tracking.general_words",
    "word_tracking.bac_tracker",
]

# Core infrastructure modules (require special handling - mostly config)
CORE_MODULES: List[str] = [
    "config",
]

# Lock to prevent concurrent reloads
_reload_lock = threading.Lock()


def get_loaded_modules() -> Set[str]:
    """Get set of currently loaded reloadable modules."""
    return set(RELOADABLE_MODULES) & set(sys.modules.keys())


def clear_module_caches(module_name: str) -> None:
    """Clear any caches related to a module."""
    if module_name in sys.modules:
        module = sys.modules[module_name]
        if hasattr(module, "__dict__"):
            # Clear any _commands_cache or similar
            for key in list(module.__dict__.keys()):
                if key.startswith("_") and "cache" in key.lower():
                    try:
                        del module.__dict__[key]
                    except KeyError:
                        pass


def reload_single_module(module_name: str) -> Tuple[bool, str]:
    """
    Reload a single module.

    Args:
        module_name: Name of the module to reload

    Returns:
        Tuple of (success, message)
    """
    if module_name not in sys.modules:
        return False, f"Module '{module_name}' is not loaded"

    try:
        # Clear caches first
        clear_module_caches(module_name)

        # Reload the module
        module = sys.modules[module_name]
        importlib.reload(module)
        logger.info(f"ReloadManager: Successfully reloaded {module_name}")
        return True, f"Reloaded {module_name}"

    except Exception as e:
        logger.error(f"ReloadManager: Failed to reload {module_name}: {e}")
        return False, f"Failed to reload {module_name}: {e}"


def reload_all_commands() -> Tuple[bool, str]:
    """
    Reload all command modules and services.

    Returns:
        Tuple of (success, message_with_command_count)
    """
    with _reload_lock:
        try:
            # Get the registry and clear it
            from command_registry import get_command_registry

            registry = get_command_registry()
            old_count = len(registry._commands)

            # Clear the registry
            registry.clear_all()
            logger.debug(f"ReloadManager: Cleared {old_count} commands from registry")

            # Reload modules in order
            reloaded_modules = []
            failed_modules = []

            for module_name in RELOADABLE_MODULES:
                if module_name in sys.modules:
                    success, _ = reload_single_module(module_name)
                    if success:
                        reloaded_modules.append(module_name)
                    else:
                        failed_modules.append(module_name)

            # Reload service modules
            for module_name in SERVICE_MODULES:
                if module_name in sys.modules:
                    success, _ = reload_single_module(module_name)
                    if success:
                        reloaded_modules.append(module_name)
                    else:
                        failed_modules.append(module_name)

            # Reload word tracking modules
            for module_name in WORD_TRACKING_MODULES:
                if module_name in sys.modules:
                    success, _ = reload_single_module(module_name)
                    if success:
                        reloaded_modules.append(module_name)
                    else:
                        failed_modules.append(module_name)

            # Reload core modules (config, etc.)
            for module_name in CORE_MODULES:
                if module_name in sys.modules:
                    success, _ = reload_single_module(module_name)
                    if success:
                        reloaded_modules.append(module_name)
                    else:
                        failed_modules.append(module_name)

            # Reinitialize services through ServiceManager
            try:
                from service_manager import ServiceManager

                # Try multiple ways to get the service manager
                service_results = {}

                # First try: check if bot_manager module has the instance
                import bot_manager

                if hasattr(bot_manager, "BotManager"):
                    # Try to get the running instance
                    for attr_name in dir(bot_manager):
                        attr = getattr(bot_manager, attr_name)
                        if isinstance(attr, ServiceManager):
                            service_results = attr.reload_services()
                            reloaded_modules.append("service_instances")
                            logger.info(
                                f"ReloadManager: Reinitialized services: {service_results}"
                            )
                            break

                # If no instance found, just note that modules were reloaded
                if not service_results:
                    logger.debug(
                        "ReloadManager: Service modules reloaded but no live instances reinitialized"
                    )

            except Exception as e:
                logger.warning(f"ReloadManager: Could not reinitialize services: {e}")

            # Note: cmd_modules are already reloaded in the loop above (lines 140-164)
            # The 'commands' module is kept in RELOADABLE_MODULES for backward compatibility
            # but imports from cmd_modules instead (no longer has @command decorators)

            # Get new command count
            new_count = len(registry._commands)

            # Report results
            if failed_modules:
                msg = (
                    f"Reloaded with errors. Modules: {', '.join(reloaded_modules)}. "
                    f"Failed: {', '.join(failed_modules)}. "
                    f"Commands: {old_count} -> {new_count}"
                )
                logger.warning(f"ReloadManager: {msg}")
                return False, msg

            msg = (
                f"Reloaded {len(reloaded_modules)} modules. Total commands: {new_count}"
            )
            logger.info(f"ReloadManager: {msg}")
            return True, msg

        except Exception as e:
            logger.error(f"ReloadManager: Reload failed: {e}")
            return False, f"Reload failed: {e}"


def reload_specific_module(module_name: str) -> Tuple[bool, str]:
    """
    Reload a specific module and its dependent modules.

    Args:
        module_name: Name of the module to reload

    Returns:
        Tuple of (success, message)
    """
    # Check both command modules and service modules
    all_reloadable = RELOADABLE_MODULES + SERVICE_MODULES

    if module_name not in all_reloadable:
        return False, f"Unknown reloadable module: {module_name}"

    # Check if it's a service module
    if module_name in SERVICE_MODULES:
        with _reload_lock:
            success, msg = reload_single_module(module_name)
            if success:
                return True, f"Reloaded service module: {module_name}"
            return False, msg

    # Find the index and reload from that point onwards
    try:
        start_idx = RELOADABLE_MODULES.index(module_name)
    except ValueError:
        return False, f"Module {module_name} not in reloadable list"

    with _reload_lock:
        # Reload modules from the index onwards
        for mod in RELOADABLE_MODULES[start_idx:]:
            if mod in sys.modules:
                success, msg = reload_single_module(mod)
                if not success:
                    return False, f"Failed at {mod}: {msg}"

        return True, f"Reloaded {module_name} and dependents"


def get_reload_status() -> Dict[str, any]:
    """Get status of reloadable modules."""
    loaded = get_loaded_modules()

    # Get loaded service modules
    service_modules_loaded = set(SERVICE_MODULES) & set(sys.modules.keys())

    # Get command count
    try:
        from command_registry import get_command_registry

        registry = get_command_registry()
        command_count = len(registry._commands)
    except Exception:
        command_count = 0

    return {
        "available_modules": RELOADABLE_MODULES,
        "available_services": SERVICE_MODULES,
        "loaded_modules": sorted(loaded),
        "loaded_services": sorted(service_modules_loaded),
        "loaded_count": len(loaded),
        "service_count": len(service_modules_loaded),
        "command_count": command_count,
    }


def verify_critical_commands() -> List[str]:
    """
    Verify critical commands are loaded after a reload.

    Returns:
        List of missing critical commands (empty if all present)
    """
    critical_commands = ["help", "ping"]
    missing = []

    try:
        from command_registry import get_command_registry

        registry = get_command_registry()

        for cmd in critical_commands:
            if not registry.get_handler(cmd):
                missing.append(cmd)

    except Exception as e:
        logger.error(f"ReloadManager: Error verifying commands: {e}")
        missing = critical_commands  # Assume all missing on error

    return missing
