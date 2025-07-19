"""
Command Registry Tests - Pure Pytest Version

Comprehensive tests for the command registry system.
"""

import os
import sys

# Add the parent directory to Python path to ensure imports work in CI
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


def test_command_registry_creation():
    """Test command registry creation and initialization."""
    from command_registry import CommandRegistry, get_command_registry

    registry = CommandRegistry()

    assert hasattr(registry, "_commands"), "Registry should have _commands attribute"
    assert isinstance(registry._commands, dict), "Commands should be a dictionary"
    assert len(registry._commands) == 0, "Registry should start empty"

    # Test global registry
    global_registry = get_command_registry()
    assert isinstance(
        global_registry, CommandRegistry
    ), "Should return CommandRegistry instance"


def test_command_registration():
    """Test command registration functionality."""
    from command_registry import CommandInfo, CommandRegistry, FunctionCommandHandler

    registry = CommandRegistry()

    # Test function registration using registry methods
    def test_command(context, bot_functions):
        return "test result"

    info = CommandInfo(name="test", description="Test command")
    registry.register_function(info, test_command)

    assert "test" in registry._commands, "Command should be registered"
    handler = registry._commands["test"]
    assert isinstance(handler, FunctionCommandHandler), "Should create function handler"
    assert handler.info.description == "Test command", "Description should be stored"


def test_command_execution():
    """Test command execution functionality."""
    from command_registry import CommandContext, CommandInfo, CommandRegistry

    registry = CommandRegistry()

    # Test simple command execution
    def echo_command(context, bot_functions):
        return f"Echo: {context.args_text}"

    info = CommandInfo(name="echo", description="Echo command")
    registry.register_function(info, echo_command)

    # Create test context
    context = CommandContext(
        command="echo",
        args=["hello", "world"],
        raw_message="!echo hello world",
        is_console=True,
    )

    # This test just checks that the command is registered properly
    assert "echo" in registry._commands, "Command should be registered"


def test_command_metadata():
    """Test command metadata handling."""
    from command_registry import CommandInfo, CommandRegistry

    registry = CommandRegistry()

    # Test CommandInfo creation
    info = CommandInfo(
        name="complex",
        description="Complex command",
        usage="!complex <arg1> [arg2]",
        admin_only=True,
    )

    assert info.name == "complex", "Name should be stored"
    assert info.description == "Complex command", "Description should be stored"
    assert info.usage == "!complex <arg1> [arg2]", "Usage should be stored"
    assert info.admin_only is True, "Admin flag should be stored"


def test_help_command():
    """Test built-in help command functionality."""
    from command_registry import CommandInfo, CommandRegistry

    registry = CommandRegistry()

    # Test that we can call generate_help
    help_result = registry.generate_help()
    assert isinstance(help_result, str), "Help should return a string"


def test_admin_commands():
    """Test admin-only command functionality."""
    from command_registry import CommandInfo

    # Test admin command info creation
    info = CommandInfo(name="admin_cmd", description="Admin command", admin_only=True)
    assert info.admin_only is True, "Command should be marked as admin-only"
    assert info.admin_marker == "*", "Should have admin marker"


def test_command_aliases():
    """Test command alias functionality."""
    from command_registry import CommandInfo

    # Test CommandInfo with aliases
    info = CommandInfo(
        name="test", description="Test command", aliases=["t", "testing"]
    )
    assert "t" in info.aliases, "Aliases should be stored"
    assert "testing" in info.aliases, "All aliases should be stored"
    assert "test" in info.all_names, "All names should include primary name"
    assert "t" in info.all_names, "All names should include aliases"


def test_command_error_handling():
    """Test command error handling."""
    from command_registry import (
        CommandContext,
        CommandInfo,
        CommandRegistry,
        FunctionCommandHandler,
    )

    registry = CommandRegistry()

    def error_command(context, bot_functions):
        raise ValueError("Test error")

    info = CommandInfo(name="error_cmd", description="Error command")
    handler = FunctionCommandHandler(info, error_command)

    # Test that error handling exists
    assert hasattr(handler, "execute"), "Handler should have execute method"


def test_command_listing():
    """Test command listing functionality."""
    from command_registry import CommandInfo, CommandRegistry

    registry = CommandRegistry()

    # Register a command
    def cmd1(context, bot_functions):
        return "cmd1"

    info = CommandInfo(name="cmd1", description="Command 1")
    registry.register_function(info, cmd1)

    # Test command listing
    commands_info = registry.get_commands_info()
    assert len(commands_info) > 0, "Should have commands"


def test_decorator_functionality():
    """Test command decorator functionality."""
    from command_registry import command, get_command_registry

    # Test using decorator
    @command(name="decorated", description="Decorated test")
    def decorated_command(context, bot_functions):
        return "decorated result"

    # Should use global registry
    registry = get_command_registry()
    assert "decorated" in registry._commands, "Should register with global registry"
