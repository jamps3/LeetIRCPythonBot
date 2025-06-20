"""
High-precision logging utility for the IRC bot.

Provides consistent, accurate timestamps across all bot components.
"""

import time
from datetime import datetime
from typing import Optional


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

    def log(self, message: str, level: str = "INFO", extra_context: str = ""):
        """
        Log a message with high-precision timestamp.

        Args:
            message: The message to log
            level: Log level (INFO, ERROR, WARNING, DEBUG, MSG, SERVER, etc.)
            extra_context: Additional context information
        """
        timestamp = self._get_timestamp()

        # Build context string
        context_parts = []
        if level:
            context_parts.append(f"[{level.upper()}]")
        if self.context:
            context_parts.append(f"[{self.context}]")
        if extra_context:
            context_parts.append(f"[{extra_context}]")

        context_str = " ".join(context_parts)
        print(f"{timestamp} {context_str} {message}")

    def info(self, message: str, extra_context: str = ""):
        """Log an info message."""
        self.log(message, "INFO", extra_context)

    def error(self, message: str, extra_context: str = ""):
        """Log an error message."""
        self.log(message, "ERROR", extra_context)

    def warning(self, message: str, extra_context: str = ""):
        """Log a warning message."""
        self.log(message, "WARNING", extra_context)

    def debug(self, message: str, extra_context: str = ""):
        """Log a debug message."""
        self.log(message, "DEBUG", extra_context)

    def msg(self, message: str, extra_context: str = ""):
        """Log a message event."""
        self.log(message, "MSG", extra_context)

    def server(self, message: str, extra_context: str = ""):
        """Log a server event."""
        self.log(message, "SERVER", extra_context)


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


def log(message: str, level: str = "INFO", context: str = "", extra_context: str = ""):
    """
    Convenience function for quick logging.

    Args:
        message: The message to log
        level: Log level
        context: Primary context (e.g., server name)
        extra_context: Additional context
    """
    if context:
        logger = PrecisionLogger(context)
    else:
        logger = _global_logger

    logger.log(message, level, extra_context)


# Convenience functions for different log levels
def info(message: str, context: str = ""):
    """Log an info message."""
    log(message, "INFO", context)


def error(message: str, context: str = ""):
    """Log an error message."""
    log(message, "ERROR", context)


def warning(message: str, context: str = ""):
    """Log a warning message."""
    log(message, "WARNING", context)


def debug(message: str, context: str = ""):
    """Log a debug message."""
    log(message, "DEBUG", context)


def msg(message: str, context: str = ""):
    """Log a message event."""
    log(message, "MSG", context)


def server(message: str, context: str = ""):
    """Log a server event."""
    log(message, "SERVER", context)
