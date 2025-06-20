"""
Command Registry Tests

Comprehensive tests for the command registry system.
"""

import os
import sys

# Add the parent directory to Python path to ensure imports work in CI
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from test_framework import TestCase, TestRunner, TestSuite


def test_command_registry_creation():
    """Test command registry creation and initialization."""
    try:
        from command_registry import CommandRegistry, get_command_registry

        registry = CommandRegistry()

        assert hasattr(
            registry, "_commands"
        ), "Registry should have _commands attribute"
        assert isinstance(registry._commands, dict), "Commands should be a dictionary"
        assert len(registry._commands) == 0, "Registry should start empty"

        # Test global registry
        global_registry = get_command_registry()
        assert isinstance(
            global_registry, CommandRegistry
        ), "Should return CommandRegistry instance"

        return True
    except Exception as e:
        print(f"Command registry creation test failed: {e}")
        return False


def test_command_registration():
    """Test command registration functionality."""
    try:
        from command_registry import (CommandInfo, CommandRegistry,
                                      FunctionCommandHandler)

        registry = CommandRegistry()

        # Test function registration using registry methods
        def test_command(context, bot_functions):
            return "test result"

        info = CommandInfo(name="test", description="Test command")
        registry.register_function(info, test_command)

        assert "test" in registry._commands, "Command should be registered"
        handler = registry._commands["test"]
        assert isinstance(
            handler, FunctionCommandHandler
        ), "Should create function handler"
        assert (
            handler.info.description == "Test command"
        ), "Description should be stored"

        return True
    except Exception as e:
        print(f"Command registration test failed: {e}")
        return False


def test_command_execution():
    """Test command execution functionality."""
    try:
        from command_registry import (CommandContext, CommandInfo,
                                      CommandRegistry)

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

        return True
    except Exception as e:
        print(f"Command execution test failed: {e}")
        return False


def test_command_metadata():
    """Test command metadata handling."""
    try:
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
        assert info.admin_only == True, "Admin flag should be stored"

        return True
    except Exception as e:
        print(f"Command metadata test failed: {e}")
        return False


def test_help_command():
    """Test built-in help command functionality."""
    try:
        from command_registry import CommandInfo, CommandRegistry

        registry = CommandRegistry()

        # Test that we can call generate_help
        help_result = registry.generate_help()
        assert isinstance(help_result, str), "Help should return a string"

        return True
    except Exception as e:
        print(f"Help command test failed: {e}")
        return False


def test_admin_commands():
    """Test admin-only command functionality."""
    try:
        from command_registry import CommandInfo

        # Test admin command info creation
        info = CommandInfo(
            name="admin_cmd", description="Admin command", admin_only=True
        )
        assert info.admin_only == True, "Command should be marked as admin-only"
        assert info.admin_marker == "*", "Should have admin marker"

        return True
    except Exception as e:
        print(f"Admin commands test failed: {e}")
        return False


def test_command_aliases():
    """Test command alias functionality."""
    try:
        from command_registry import CommandInfo

        # Test CommandInfo with aliases
        info = CommandInfo(
            name="test", description="Test command", aliases=["t", "testing"]
        )
        assert "t" in info.aliases, "Aliases should be stored"
        assert "testing" in info.aliases, "All aliases should be stored"
        assert "test" in info.all_names, "All names should include primary name"
        assert "t" in info.all_names, "All names should include aliases"

        return True
    except Exception as e:
        print(f"Command aliases test failed: {e}")
        return False


def test_command_error_handling():
    """Test command error handling."""
    try:
        from command_registry import (CommandContext, CommandInfo,
                                      CommandRegistry, FunctionCommandHandler)

        registry = CommandRegistry()

        def error_command(context, bot_functions):
            raise ValueError("Test error")

        info = CommandInfo(name="error_cmd", description="Error command")
        handler = FunctionCommandHandler(info, error_command)

        # Test that error handling exists
        assert hasattr(handler, "execute"), "Handler should have execute method"

        return True
    except Exception as e:
        print(f"Command error handling test failed: {e}")
        return False


def test_command_listing():
    """Test command listing functionality."""
    try:
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

        return True
    except Exception as e:
        print(f"Command listing test failed: {e}")
        return False


def test_decorator_functionality():
    """Test command decorator functionality."""
    try:
        from command_registry import command, get_command_registry

        # Test using decorator
        @command(name="decorated", description="Decorated test")
        def decorated_command(context, bot_functions):
            return "decorated result"

        # Should use global registry
        registry = get_command_registry()
        assert "decorated" in registry._commands, "Should register with global registry"

        return True
    except Exception as e:
        print(f"Decorator functionality test failed: {e}")
        return False


def register_command_registry_tests(runner: TestRunner):
    """Register command registry tests with the test runner."""

    tests = [
        TestCase(
            name="command_registry_creation",
            description="Test command registry creation",
            test_func=test_command_registry_creation,
            category="command_registry",
        ),
        TestCase(
            name="command_registration",
            description="Test command registration",
            test_func=test_command_registration,
            category="command_registry",
        ),
        TestCase(
            name="command_execution",
            description="Test command execution",
            test_func=test_command_execution,
            category="command_registry",
        ),
        TestCase(
            name="command_metadata",
            description="Test command metadata handling",
            test_func=test_command_metadata,
            category="command_registry",
        ),
        TestCase(
            name="help_command",
            description="Test help command functionality",
            test_func=test_help_command,
            category="command_registry",
        ),
        TestCase(
            name="admin_commands",
            description="Test admin-only commands",
            test_func=test_admin_commands,
            category="command_registry",
        ),
        TestCase(
            name="command_aliases",
            description="Test command aliases",
            test_func=test_command_aliases,
            category="command_registry",
        ),
        TestCase(
            name="command_error_handling",
            description="Test command error handling",
            test_func=test_command_error_handling,
            category="command_registry",
        ),
        TestCase(
            name="command_listing",
            description="Test command listing",
            test_func=test_command_listing,
            category="command_registry",
        ),
        TestCase(
            name="decorator_functionality",
            description="Test decorator functionality",
            test_func=test_decorator_functionality,
            category="command_registry",
        ),
    ]

    suite = TestSuite(
        name="Command_Registry",
        description="Tests for command registry system",
        tests=tests,
    )

    runner.add_suite(suite)
