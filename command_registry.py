"""
Command Registry System for LeetIRCPythonBot

This module provides a clean, modular command system that replaces the large
elif chains with a registry-based approach. Commands can be registered with
metadata, and the system handles dispatch and help generation automatically.
"""

import inspect
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union


class CommandType(Enum):
    """Types of commands available in the bot."""

    PUBLIC = "public"  # Available to all users in channels
    PRIVATE = "private"  # Available in private messages
    ADMIN = "admin"  # Requires admin password
    CONSOLE = "console"  # Console-only commands
    ALL = "all"  # Available everywhere


class CommandScope(Enum):
    """Where a command can be executed."""

    IRC_ONLY = "irc"  # Only in IRC channels/private messages
    CONSOLE_ONLY = "console"  # Only in console
    BOTH = "both"  # Both IRC and console


@dataclass
class CommandContext:
    """Context information for command execution."""

    command: str  # The command name that was called
    args: List[str]  # Command arguments
    raw_message: str  # Original message text
    sender: Optional[str] = None  # IRC nickname of sender (None for console)
    target: Optional[str] = None  # IRC channel/target (None for console)
    is_private: bool = False  # True if sent via private message
    is_console: bool = False  # True if executed from console
    server_name: str = ""  # Server identifier

    @property
    def args_text(self) -> str:
        """Get arguments as a single string."""
        return " ".join(self.args)

    @property
    def is_admin_context(self) -> bool:
        """Check if this is an admin context (private message or console)."""
        return self.is_private or self.is_console


@dataclass
class CommandResponse:
    """Response from a command execution."""

    success: bool = True
    message: str = ""
    error: Optional[str] = None
    should_respond: bool = True  # Whether to send a response
    split_long_messages: bool = True  # Whether to split long messages

    @classmethod
    def success_msg(cls, message: str) -> "CommandResponse":
        """Create a successful response with a message."""
        return cls(success=True, message=message)

    @classmethod
    def error_msg(cls, error: str) -> "CommandResponse":
        """Create an error response."""
        return cls(success=False, error=error, message=error)

    @classmethod
    def no_response(cls) -> "CommandResponse":
        """Create a response that shouldn't send anything."""
        return cls(should_respond=False)


@dataclass
class CommandInfo:
    """Metadata about a command."""

    name: str
    aliases: List[str] = field(default_factory=list)
    description: str = ""
    usage: str = ""
    examples: List[str] = field(default_factory=list)
    command_type: CommandType = CommandType.PUBLIC
    scope: CommandScope = CommandScope.BOTH
    requires_args: bool = False
    admin_only: bool = False
    hidden: bool = False  # Hidden from help listing
    cooldown: float = 0.0  # Cooldown in seconds between uses

    @property
    def all_names(self) -> List[str]:
        """Get all names (primary + aliases) for this command."""
        return [self.name] + self.aliases

    @property
    def admin_marker(self) -> str:
        """Get admin marker for help display."""
        return "*" if self.admin_only else ""


class CommandHandler(ABC):
    """Abstract base class for command handlers."""

    def __init__(self, info: CommandInfo):
        self.info = info
        self._last_used: Dict[str, float] = {}  # Track cooldowns per user

    @abstractmethod
    async def execute(
        self, context: CommandContext, bot_functions: Dict[str, Any]
    ) -> CommandResponse:
        """Execute the command with the given context."""
        pass

    def can_execute(self, context: CommandContext) -> tuple[bool, Optional[str]]:
        """Check if the command can be executed in the given context."""
        # Check scope
        if self.info.scope == CommandScope.IRC_ONLY and context.is_console:
            return False, "This command is not available in console mode"
        elif self.info.scope == CommandScope.CONSOLE_ONLY and not context.is_console:
            return False, "This command is only available in console mode"

        # Admin commands: enforcement is handled inside the command function (e.g., password checks).
        # Do not restrict by context here so admin commands can be executed from IRC as well.

        # Check if arguments are required
        if self.info.requires_args and not context.args:
            return False, f"Usage: {self.info.usage or self.info.name}"

        # Check cooldown
        if self.info.cooldown > 0 and context.sender:
            import time

            user_key = f"{context.sender}@{context.server_name}"
            last_used = self._last_used.get(user_key, 0)
            if time.time() - last_used < self.info.cooldown:
                remaining = self.info.cooldown - (time.time() - last_used)
                return False, f"Command on cooldown. Wait {remaining:.1f} seconds."

        return True, None

    def update_cooldown(self, context: CommandContext):
        """Update the last used timestamp for cooldown tracking."""
        if self.info.cooldown > 0 and context.sender:
            import time

            user_key = f"{context.sender}@{context.server_name}"
            self._last_used[user_key] = time.time()


class FunctionCommandHandler(CommandHandler):
    """Command handler that wraps a function."""

    def __init__(self, info: CommandInfo, func: Callable):
        super().__init__(info)
        self.func = func
        self._validate_function()

    def _validate_function(self):
        """Validate that the function has the correct signature."""
        sig = inspect.signature(self.func)
        params = list(sig.parameters.keys())

        # Check if function takes the expected parameters
        if len(params) < 2:
            raise ValueError(
                f"Command function {self.func.__name__} must accept at least (context, bot_functions)"
            )

    async def execute(
        self, context: CommandContext, bot_functions: Dict[str, Any]
    ) -> CommandResponse:
        """Execute the wrapped function."""
        try:
            # Check if function is async
            if inspect.iscoroutinefunction(self.func):
                result = await self.func(context, bot_functions)
            else:
                result = self.func(context, bot_functions)

            # Handle different return types
            if isinstance(result, CommandResponse):
                return result
            elif isinstance(result, str):
                return CommandResponse.success_msg(result)
            elif result is None:
                return CommandResponse.no_response()
            else:
                return CommandResponse.success_msg(str(result))

        except Exception as e:
            return CommandResponse.error_msg(f"Command error: {str(e)}")


class CommandRegistry:
    """Registry for managing bot commands."""

    def __init__(self):
        self._commands: Dict[str, CommandHandler] = {}
        self._aliases: Dict[str, str] = {}  # alias -> command_name mapping

    def register(self, handler: CommandHandler) -> None:
        """Register a command handler."""
        info = handler.info

        # Register primary name
        if info.name in self._commands:
            raise ValueError(f"Command '{info.name}' is already registered")

        self._commands[info.name] = handler

        # Register aliases
        for alias in info.aliases:
            if alias in self._aliases or alias in self._commands:
                raise ValueError(f"Alias '{alias}' conflicts with existing command")
            self._aliases[alias] = info.name

    def register_function(self, info: CommandInfo, func: Callable) -> None:
        """Register a function as a command."""
        handler = FunctionCommandHandler(info, func)
        self.register(handler)

    def unregister(self, command_name: str) -> bool:
        """Unregister a command and its aliases."""
        if command_name not in self._commands:
            return False

        handler = self._commands[command_name]

        # Remove aliases
        for alias in handler.info.aliases:
            self._aliases.pop(alias, None)

        # Remove command
        del self._commands[command_name]
        return True

    def get_handler(self, command_name: str) -> Optional[CommandHandler]:
        """Get a command handler by name or alias."""
        # Check if it's an alias first
        if command_name in self._aliases:
            command_name = self._aliases[command_name]

        return self._commands.get(command_name)

    def get_command_names(
        self,
        include_aliases: bool = False,
        command_type: Optional[CommandType] = None,
        scope: Optional[CommandScope] = None,
        include_hidden: bool = False,
    ) -> List[str]:
        """Get list of available command names."""
        names = []

        for name, handler in self._commands.items():
            info = handler.info

            # Apply filters
            if (
                command_type
                and info.command_type != command_type
                and info.command_type != CommandType.ALL
            ):
                continue
            if scope and info.scope != scope and info.scope != CommandScope.BOTH:
                continue
            if not include_hidden and info.hidden:
                continue

            names.append(name)

            if include_aliases:
                names.extend(info.aliases)

        return sorted(names)

    def get_commands_info(
        self,
        command_type: Optional[CommandType] = None,
        scope: Optional[CommandScope] = None,
        include_hidden: bool = False,
    ) -> List[CommandInfo]:
        """Get command information for help generation."""
        commands = []

        for handler in self._commands.values():
            info = handler.info

            # Apply filters
            if (
                command_type
                and info.command_type != command_type
                and info.command_type != CommandType.ALL
            ):
                continue
            if scope and info.scope != scope and info.scope != CommandScope.BOTH:
                continue
            if not include_hidden and info.hidden:
                continue

            commands.append(info)

        return sorted(commands, key=lambda x: x.name)

    async def execute_command(
        self, command_name: str, context: CommandContext, bot_functions: Dict[str, Any]
    ) -> Optional[CommandResponse]:
        """Execute a command by name."""
        handler = self.get_handler(command_name)
        if not handler:
            return None

        # Check if command can be executed
        can_execute, error_msg = handler.can_execute(context)
        if not can_execute:
            return CommandResponse.error_msg(error_msg)

        # Update cooldown before execution
        handler.update_cooldown(context)

        # Execute the command
        return await handler.execute(context, bot_functions)

    def generate_help(
        self,
        command_type: Optional[CommandType] = None,
        scope: Optional[CommandScope] = None,
        specific_command: Optional[str] = None,
    ) -> str:
        """Generate help text for commands."""
        if specific_command:
            handler = self.get_handler(specific_command)
            if not handler:
                return f"Unknown command: {specific_command}"

            info = handler.info
            help_text = f"{info.name}{info.admin_marker}"
            if info.aliases:
                help_text += f" (aliases: {', '.join(info.aliases)})"

            if info.description:
                help_text += f" - {info.description}"

            if info.usage:
                help_text += f"\nUsage: {info.usage}"

            if info.examples:
                help_text += "\nExamples:\n" + "\n".join(
                    f"  {ex}" for ex in info.examples
                )

            return help_text

        # Generate general help
        commands = self.get_commands_info(command_type, scope, include_hidden=False)
        if not commands:
            return "No commands available."

        help_lines = []
        for info in commands:
            line = f"{info.name}{info.admin_marker}"
            if info.description:
                line += f" - {info.description}"
            help_lines.append(line)

        help_text = "Available commands:\n" + "\n".join(help_lines)
        if any(cmd.admin_only for cmd in commands):
            help_text += "\n\n* Admin command (requires password)"

        return help_text


# Global command registry instance
_command_registry: Optional[CommandRegistry] = None


def get_command_registry() -> CommandRegistry:
    """Get the global command registry instance."""
    global _command_registry
    if _command_registry is None:
        _command_registry = CommandRegistry()
    return _command_registry


def reset_command_registry() -> None:
    """Reset the global command registry instance. Used for testing."""
    global _command_registry
    _command_registry = None


def command(
    name: str,
    aliases: List[str] = None,
    description: str = "",
    usage: str = "",
    examples: List[str] = None,
    command_type: CommandType = CommandType.PUBLIC,
    scope: CommandScope = CommandScope.BOTH,
    requires_args: bool = False,
    admin_only: bool = False,
    hidden: bool = False,
    cooldown: float = 0.0,
):
    """
    Decorator to register a function as a command.

    Usage:
        @command("hello", aliases=["hi"], description="Say hello")
        def hello_command(context, bot_functions):
            return f"Hello, {context.sender}!"
    """

    def decorator(func):
        info = CommandInfo(
            name=name,
            aliases=aliases or [],
            description=description,
            usage=usage,
            examples=examples or [],
            command_type=command_type,
            scope=scope,
            requires_args=requires_args,
            admin_only=admin_only,
            hidden=hidden,
            cooldown=cooldown,
        )

        # Register the command
        registry = get_command_registry()
        registry.register_function(info, func)

        return func

    return decorator


def parse_command_message(
    message: str, command_prefix: str = "!"
) -> tuple[Optional[str], List[str], str]:
    """
    Parse a message to extract command and arguments.

    Args:
        message: The message to parse
        command_prefix: The prefix that indicates a command (default: "!")

    Returns:
        Tuple of (command_name, arguments, raw_message)
        Returns (None, [], message) if no command is found
    """
    if not message.startswith(command_prefix):
        return None, [], message

    # Remove prefix and split
    parts = message[len(command_prefix) :].split()
    if not parts:
        return None, [], message

    command = parts[0].lower()
    args = parts[1:] if len(parts) > 1 else []

    return command, args, message


async def process_command_message(
    message: str,
    context: CommandContext,
    bot_functions: Dict[str, Any],
    command_prefix: str = "!",
) -> Optional[CommandResponse]:
    """
    Process a message and execute any command found.

    Args:
        message: The message to process
        context: Command execution context
        bot_functions: Available bot functions
        command_prefix: Command prefix (default: "!")

    Returns:
        CommandResponse if a command was executed, None otherwise
    """
    command_name, args, raw_message = parse_command_message(message, command_prefix)
    if not command_name:
        return None

    # Update context with parsed command info
    context.command = command_name
    context.args = args
    context.raw_message = raw_message

    # Execute the command
    registry = get_command_registry()
    return await registry.execute_command(command_name, context, bot_functions)
