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
        context: str = "",
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

            # Build message
            message = []
            if level:
                message.append(f"[{level.upper():<7}]")
            if context:
                message.append(f"[{context}]")

        except UnicodeEncodeError:
            # Fall back to ASCII-safe version
            if fallback_text:
                print(f"{timestamp} {context} {fallback_text}")
                debug(
                    "Note: Original text contained Unicode characters and was replaced.",
                )
            else:
                # Replace common Unicode characters with ASCII equivalents
                safe_text = (
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

        print(f"{timestamp} {context} {message}")  # Main log output

    def info(self, message: str, context: str = ""):
        """Log an info message."""
        self.log(message, "INFO", context)

    def error(self, message: str, context: str = ""):
        """Log an error message."""
        self.log(message, "ERROR", context)

    def warning(self, message: str, context: str = ""):
        """Log a warning message."""
        self.log(message, "WARNING", context)
        # Symbols can be used: ⚠

    def debug(self, message: str, context: str = ""):
        """Log a debug message."""
        self.log(message, "DEBUG", context)

    def msg(self, message: str, context: str = ""):
        """Log a message event."""
        self.log(message, "MSG", context)

    def server(self, message: str, context: str = ""):
        """Log a server event."""
        self.log(message, "SERVER", context)


# Global logger instance for general use
_global_logger = PrecisionLogger()


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


# Convenience functions for different log levels
def info(message: str, context: str = ""):
    """Log an info message."""
    PrecisionLogger().log(message, "INFO", context)


def error(message: str, context: str = ""):
    """Log an error message."""
    PrecisionLogger().log(message, "ERROR", context)


def warning(message: str, context: str = ""):
    """Log a warning message."""
    PrecisionLogger().log(message, "WARNING", context)


def debug(message: str, context: str = ""):
    """Log a debug message."""
    PrecisionLogger().log(message, "DEBUG", context)


def msg(message: str, context: str = ""):
    """Log a message event."""
    PrecisionLogger().log(message, "MSG", context)


def server(message: str, context: str = ""):
    """Log a server event."""
    PrecisionLogger().log(message, "SERVER", context)


# Expose global logger:
log = _global_logger.log
