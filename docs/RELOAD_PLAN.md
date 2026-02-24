# Command Reload Plan

This document outlines the implementation plan for reloading bot commands (and related modules) without restarting the IRC bot.

## Overview

The goal is to allow hot-reloading of command modules and related Python files while the bot is running, enabling:

- Rapid iteration during development
- Adding/modifying commands without downtime
- Fixing bugs in commands on production systems

## Current Architecture Analysis

### Command Registration System

1. **Command Registry** (`command_registry.py`):
   - Global `CommandRegistry` singleton stores all registered commands in `self._commands` dict
   - Aliases stored in `self._aliases` dict
   - Already has `unregister()` method to remove commands
   - Has `reset_command_registry()` for testing purposes

2. **Command Loading** (`command_loader.py`):
   - `load_all_commands()` imports `commands` module, triggering `@command` decorators
   - Uses lazy loading via `_commands_loaded` flag
   - `reset_commands_loaded_flag()` exists for tests

3. **Command Modules**:
   - `commands.py` - Main unified commands module
   - `commands_services.py` - Service-related commands
   - `commands_admin.py` - Admin commands
   - `commands_basic.py` - Basic commands
   - `commands_irc.py` - IRC-specific commands

### Key Findings

- ✅ Registry already supports unregistration (`unregister()` method)
- ✅ Registry has reset function (`reset_command_registry()`)
- ⚠️ Python's `sys.modules` caching needs handling for true reloading
- ⚠️ Need to track which modules need reloading

---

## Implementation Plan

### Phase 1: Core Reload Infrastructure

#### 1.1 Enhance Command Registry

Add methods to `command_registry.py`:

```python
def clear_all(self) -> None:
    """Clear all registered commands and aliases."""
    self._commands.clear()
    self._aliases.clear()

def reload(self) -> int:
    """Reload all command modules. Returns count of reloaded commands."""
    self.clear_all()
    # Re-import command modules (see Phase 2)
    from command_loader import load_all_commands
    load_all_commands()
    return len(self._commands)
```

#### 1.2 Create Reload Manager Module

Create `src/reload_manager.py`:

```python
"""Reload Manager for hot-reloading bot components."""

import importlib
import sys
import logging
from typing import List, Set, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Modules that can be reloaded
RELOADABLE_MODULES = {
    # Command modules
    "commands",
    "commands_services",
    "commands_admin",
    "commands_basic",
    "commands_irc",
    # Registry and loader
    "command_registry",
    "command_loader",
}

# Module dependencies - reload order matters
RELOAD_ORDER = [
    "command_registry",  # Base first
    "command_loader",    # Depends on registry
    "commands",          # Main commands
    "commands_services", # Services depend on commands
    "commands_admin",    # Admin depends on commands
    "commands_basic",    # Basic depends on commands
    "commands_irc",      # IRC depends on commands
]


def get_reloadable_modules() -> Set[str]:
    """Get set of currently loaded reloadable modules."""
    return RELOADABLE_MODULES & set(sys.modules.keys())


def clear_module_caches(module_name: str) -> None:
    """Clear any caches related to a module."""
    # Clear importlib cache
    if module_name in sys.modules:
        module = sys.modules[module_name]
        if hasattr(module, '__dict__'):
            # Clear any _commands_cache or similar
            for key in list(module.__dict__.keys()):
                if key.startswith('_') and 'cache' in key.lower():
                    del module.__dict__[key]


def reload_module(module_name: str) -> bool:
    """Reload a single module. Returns True if successful."""
    if module_name not in sys.modules:
        logger.warning(f"Module {module_name} not loaded, skipping")
        return False

    try:
        # Clear caches first
        clear_module_caches(module_name)

        # Reload the module
        module = sys.modules[module_name]
        importlib.reload(module)
        logger.info(f"Successfully reloaded {module_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to reload {module_name}: {e}")
        return False


def reload_all_commands(registry) -> int:
    """Reload all command modules and return command count."""
    # Reset the registry first
    registry.clear_all()

    # Reload modules in order
    for module_name in RELOAD_ORDER:
        reload_module(module_name)

    # Re-register by re-importing commands
    import commands
    # This triggers @command decorators again

    return len(registry._commands)


def get_reload_status() -> dict:
    """Get status of reloadable modules."""
    return {
        "loaded": list(get_reloadable_modules()),
        "count": len(get_reloadable_modules()),
    }
```

### Phase 2: IRC Command Integration

#### 2.1 Add Reload Command

Add to `commands_admin.py`:

```python
@command(
    name="reload",
    aliases=["rl"],
    description="Reload command modules without restart",
    usage="!reload [module]",
    examples=["!reload", "!reload commands_services"],
    command_type=CommandType.ADMIN,
    scope=CommandScope.IRC_ONLY,
    admin_only=True,
)
async def reload_command(context, bot_functions):
    """Reload bot commands."""
    from reload_manager import reload_all_commands, get_reload_status
    from command_registry import get_command_registry

    args = context.args

    if not args:
        # Reload all commands
        registry = get_command_registry()
        count = reload_all_commands(registry)
        return CommandResponse.success_msg(
            f"Reloaded all commands. Total: {count} commands loaded."
        )
    else:
        # TODO: Single module reload
        module_name = args[0]
        return CommandResponse.success_msg(
            f"Module-specific reload not yet implemented. Use !reload for full reload."
        )
```

#### 2.2 Console Command Support

Add to console command processor:

```python
# In console_manager.py or similar
async def handle_console_reload(args: List[str]) -> str:
    """Handle reload from console."""
    from reload_manager import reload_all_commands
    from command_registry import get_command_registry

    registry = get_command_registry()
    count = reload_all_commands(registry)
    return f"Reloaded {count} commands"
```

---

### Phase 3: Extended Reload Capabilities

#### 3.1 Service Module Reload Support

Allow reloading service modules that commands depend on:

```python
# Extend RELOADABLE_MODULES
SERVICE_RELOADABLE = {
    "services.weather_service",
    "services.electricity_service",
    "services.crypto_service",
    # etc.
}
```

#### 3.2 Configuration Reload

```python
@command(
    name="rehash",
    description="Reload configuration without restart",
    admin_only=True,
)
async def rehash_command(context, bot_functions):
    """Reload bot configuration."""
    from config import load_env_file, get_config

    # Reload .env file
    load_env_file()
    config = get_config()

    return CommandResponse.success_msg("Configuration reloaded.")
```

#### 3.3 Watch File Mode (Optional)

For development, auto-reload on file changes:

```python
def start_file_watcher(paths: List[str], callback: Callable):
    """Watch files and call callback on changes."""
    # Use watchdog or simple polling
    pass
```

---

### Phase 4: Safety & Error Handling

#### 4.1 Atomic Reload

Ensure reload is atomic - rollback on failure:

```python
def safe_reload() -> tuple[bool, str]:
    """Safely reload with rollback on failure."""
    from command_registry import get_command_registry

    registry = get_command_registry()

    # Save current state
    old_commands = dict(registry._commands)
    old_aliases = dict(registry._aliases)

    try:
        # Perform reload
        registry.clear_all()
        import commands  # Re-import
        # Verify
        if not registry._commands:
            raise RuntimeError("No commands loaded after reload")
        return True, "Success"
    except Exception as e:
        # Rollback
        registry._commands = old_commands
        registry._aliases = old_aliases
        return False, str(e)
```

#### 4.2 Reload Lock

Prevent concurrent reloads:

```python
import threading

_reload_lock = threading.Lock()

def atomic_reload():
    with _reload_lock:
        # perform reload
        pass
```

#### 4.3 Health Check After Reload

Verify critical commands are loaded:

```python
def verify_reload() -> List[str]:
    """Verify critical commands are available."""
    from command_registry import get_command_registry

    registry = get_command_registry()
    critical = ["help", "ping", "reload"]  # Must-have commands

    missing = []
    for cmd in critical:
        if not registry.get_handler(cmd):
            missing.append(cmd)

    return missing
```

---

## Usage

### IRC Usage

```
!reload          # Reload all commands
!reload help    # Show reload help
!rehash         # Reload configuration
```

### Console Usage

```
!reload
reload
```

---

## Testing Plan

1. **Unit Tests**:
   - Test `reload_module()` with mock modules
   - Test `reload_all_commands()` clears and restores registry
   - Test atomic reload rollback

2. **Integration Tests**:
   - Test reload via IRC command
   - Test reload via console
   - Verify commands work after reload

3. **Error Cases**:
   - Test reload with syntax errors in command module
   - Test reload with missing dependencies

---

## Files to Modify

| File                           | Changes                               |
| ------------------------------ | ------------------------------------- |
| `src/command_registry.py`      | Add `clear_all()`, enhance `reload()` |
| `src/reload_manager.py`        | **New file** - core reload logic      |
| `src/commands_admin.py`        | Add `reload` command                  |
| `src/console_manager.py`       | Add console reload support            |
| `tests/test_command_reload.py` | **New file** - reload tests           |

---

## Future Enhancements

1. **Per-Module Reload**: Reload specific modules instead of all
2. **Plugin System**: Dynamic command loading from plugins directory
3. **File Watching**: Auto-reload on source file changes
4. **Remote Reload**: Trigger reload via HTTP API or other triggers
5. **Diff View**: Show what commands changed between reloads
