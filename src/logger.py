"""
Precision logging utility for the IRC bot.

Provides high-precision timestamps with nanosecond accuracy and
supports multiple log levels and context-aware messages.

Log Levels:
    - DEBUG   : Diagnostic messages for developers, useful for troubleshooting and development.
    - SERVER  : Server-level events, such as server status changes or protocol-level notifications.
    - INFO    : General informational messages about normal operations.
    - WARNING : Non-critical issues that may require attention or could potentially cause problems.
    - ERROR   : Serious issues that may impact functionality or require immediate attention.
    - MSG     : Chat or message-related events, such as user messages or bot responses.

Features:
    - Nanosecond-precision timestamps for accurate event tracking.
    - Context-aware logging to distinguish between different bot components or servers.
    - Unicode-safe output for compatibility across platforms.
    - Convenient global logger and helper functions for quick logging.
"""

import os
import time
from datetime import datetime

# from typing import Optional

# Default log level
_LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG").upper()
_LEVEL_ORDER = [
    "DEBUG",
    "SERVER",
    "INFO",
    "WARNING",
    "ERROR",
    "MSG",
]


class PrecisionLogger:
    """
    High-precision logger with nanosecond timestamp accuracy.

    This logger provides consistent, high-precision timestamps across
    all bot components, similar to the format shown in the PONG example:
    [2025-06-19 02:15:38.882221300] [LEVEL] [CONTEXT] message
    """

    def __init__(self, context: str = ""):
        """
        Initialize the precision logger.

        Args:
            context: Optional context string (e.g., server name, module name)
        """
        self.context = context

    def _should_log(self, level: str) -> bool:
        """
        Determine if a message at the given level should be logged
        based on the current log level setting.
        Undetermined levels default to DEBUG.
        SERVER level is logged only if LOG_LEVEL is set to DEBUG or SERVER.

        Args:
            level: Log level of the message
        Returns:
            True if the message should be logged (message level >= global LOG_LEVEL from .env), False otherwise
        """
        level = level.upper()
        if level not in _LEVEL_ORDER:
            level = "DEBUG"  # fallback to default

        # Only allow SERVER logs if LOG_LEVEL is DEBUG or SERVER
        if level == "SERVER" and _LOG_LEVEL not in ["DEBUG", "SERVER"]:
            return False
        return _LEVEL_ORDER.index(level) >= _LEVEL_ORDER.index(_LOG_LEVEL)

    def _get_timestamp(self) -> str:
        """
        Get high-precision timestamp with nanosecond accuracy.

        Returns:
            Formatted timestamp string with nanoseconds
        """
        now = datetime.now()
        nanoseconds = time.time_ns() % 1_000_000_000

        # Format: [2025-06-19 02:15:38.882221300]
        return f"[{now.strftime('%Y-%m-%d %H:%M:%S')}.{nanoseconds:09d}]"

    def log(
        self,
        message: str,
        level: str = "INFO",
        context: str = None,
        fallback_text: str = "",
    ):
        """
        Log a message with high-precision timestamp.

        Args:
            message: The message to log
            level: Log level. Supported levels include:
            - DEBUG   : Diagnostic messages for developers.
            - SERVER  : Server-level events (only shown if LOG_LEVEL is DEBUG or SERVER).
            - INFO    : General informational messages.
            - WARNING : Non-critical issues that may require attention.
            - ERROR   : Serious issues that may impact functionality.
            - MSG     : Chat or message-related events.
            context: Additional context information
            fallback_text: ASCII-safe fallback text if Unicode fails
        """
        try:
            if not self._should_log(level):  # Check log level
                return  # skip lower-level messages
            timestamp = self._get_timestamp()
            context = context if context else self.context  # Use instance context

            # Build message
            parts = []
            if level:
                parts.append(f"[{level.upper():<7}]")
            if context:
                parts.append(f"[{context}]")
            parts.append(message)

            # Only include string elements in parts
            output = " ".join(str(p) for p in parts if isinstance(p, str))

            # Forward to TUI if hook is set, otherwise print to console
            if _tui_hook:
                try:
                    from datetime import datetime

                    dt = datetime.now()
                    # Determine source type based on context and level
                    source_type = "SYSTEM"
                    if context and any(
                        word in context.lower() for word in ["irc", "server"]
                    ):
                        source_type = "IRC"
                    elif context and "gpt" in context.lower():
                        source_type = "AI"
                    elif level.upper() == "MSG":
                        source_type = "IRC"

                    _tui_hook(
                        dt, context or "System", level.upper(), message, source_type
                    )
                except Exception as e:
                    # Don't let TUI hook errors break logging
                    print(f"[LOGGER ERROR] TUI hook failed: {e}")
            else:
                # Only print to console if TUI hook is not active
                print(f"{timestamp} {output}")  # Main console log output

        except UnicodeEncodeError:
            # Fall back to ASCII-safe version
            try:
                if fallback_text:
                    safe_message = fallback_text
                else:
                    # Replace common Unicode characters with ASCII equivalents
                    safe_message = (
                        message.replace("🤖", "[BOT]")
                        .replace("🚀", "[START]")
                        .replace("🛑", "[STOP]")
                        .replace("✅", "[OK]")
                        .replace("❌", "[ERROR]")
                        .replace("💥", "[ERROR]")
                        .replace("💬", "[CHAT]")
                        .replace("🔧", "[CONFIG]")
                        .replace("🗣️", "[TALK]")
                    )

                # Handle output same way as normal logging
                if _tui_hook:
                    try:
                        from datetime import datetime

                        dt = datetime.now()
                        # Determine source type based on context and level
                        source_type = "SYSTEM"
                        if context and any(
                            word in context.lower() for word in ["irc", "server"]
                        ):
                            source_type = "IRC"
                        elif context and "gpt" in context.lower():
                            source_type = "AI"
                        elif level.upper() == "MSG":
                            source_type = "IRC"

                        _tui_hook(
                            dt,
                            context or "System",
                            level.upper(),
                            safe_message,
                            source_type,
                        )
                    except Exception as e:
                        print(f"[LOGGER ERROR] TUI hook failed in fallback: {e}")
                else:
                    # Only print to console if TUI hook is not active
                    fallback_output = f"{timestamp} [{level.upper():<7}]"
                    if context:
                        fallback_output += f" [{context}]"
                    fallback_output += f" {safe_message}"
                    print(fallback_output)
            except Exception:
                # Last resort: basic ASCII message - respect TUI hook
                error_msg = f"Could not display Unicode message: {repr(message)}"
                if _tui_hook:
                    try:
                        from datetime import datetime

                        dt = datetime.now()
                        _tui_hook(dt, "Logger", "ERROR", error_msg, "SYSTEM")
                    except Exception:
                        print(f"[LOGGER ERROR] {error_msg}")
                else:
                    print(f"[LOGGER ERROR] {error_msg}")

    def info(self, message: str, context: str = "", fallback_text: str = ""):
        self.log(message, "INFO", context, fallback_text)  # Log an info message

    def error(self, message: str, context: str = "", fallback_text: str = ""):
        self.log(message, "ERROR", context, fallback_text)  # Log an error message

    def warning(self, message: str, context: str = "", fallback_text: str = ""):
        self.log(message, "WARNING", context, fallback_text)  # Log a warning message ⚠

    def debug(self, message: str, context: str = "", fallback_text: str = ""):
        self.log(message, "DEBUG", context, fallback_text)  # Log a debug message

    def msg(self, message: str, context: str = "", fallback_text: str = ""):
        self.log(message, "MSG", context, fallback_text)  # Log a message event

    def server(self, message: str, context: str = "", fallback_text: str = ""):
        self.log(message, "SERVER", context, fallback_text)  # Log a server event


# Global logger instance for general use
_global_logger = PrecisionLogger()

# TUI hook for forwarding log messages
_tui_hook = None


def set_tui_hook(hook_function):
    """Set a hook function to forward log messages to TUI.

    Args:
        hook_function: Function that accepts (timestamp, server, level, message, source_type)
    """
    global _tui_hook
    _tui_hook = hook_function


def clear_tui_hook():
    """Clear the TUI hook."""
    global _tui_hook
    _tui_hook = None


# Expose global logger for convenience:
log = _global_logger.log
info = _global_logger.info
error = _global_logger.error
warning = _global_logger.warning
debug = _global_logger.debug
msg = _global_logger.msg
server = _global_logger.server


def get_logger(context: str = "") -> PrecisionLogger:
    """
    Get a logger instance with optional context.

    Args:
        context: Context string (e.g., "SERVER1", "BotManager", etc.)

    Returns:
        PrecisionLogger instance
    """
    if context:
        return PrecisionLogger(context)
    return _global_logger
