"""
Precision logging utility for the IRC bot.

Provides high-precision timestamps with nanosecond accuracy and
supports multiple log levels and context-aware messages.
"""

import os
import readline
import sys
import threading
import time
from datetime import datetime
from typing import Optional

# Default log level
_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
_LEVEL_ORDER = ["DEBUG", "INFO", "WARNING", "ERROR", "MSG", "SERVER"]


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

    def log(self, message: str, level: str = "INFO", extra_context: str = ""):
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
            extra_context: Additional context information
        """
        if not self._should_log(level):
            return  # skip lower-level messages
        timestamp = self._get_timestamp()

        # Build context string
        context_parts = []
        if level:
            context_parts.append(f"[{level.upper():<7}]")
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
        # Symbols can be used: ⚠

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


# Safe print function that handles Unicode gracefully
def safe_print(text, fallback_text=None):
    """Print text with Unicode fallback for Windows console compatibility."""
    try:
        log(text)
    except UnicodeEncodeError:
        # Fall back to ASCII-safe version
        if fallback_text:
            log(fallback_text)
            log(
                "Note: Original text contained Unicode characters and was replaced.",
                level="DEBUG",
            )
        else:
            # Replace common Unicode characters with ASCII equivalents
            safe_text = (
                text.replace("🤖", "[BOT]")
                .replace("🚀", "[START]")
                .replace("🛑", "[STOP]")
                .replace("✅", "[OK]")
                .replace("❌", "[ERROR]")
                .replace("💥", "[ERROR]")
                .replace("💬", "[CHAT]")
                .replace("🔧", "[CONFIG]")
                .replace("🗣️", "[TALK]")
            )
            log(safe_text)


def _setup_console_output_protection(self):
    """Set up console output protection to prevent log messages from overwriting input line."""
    self._input_active = False
    self._print_lock = threading.Lock()
    self._original_print = print
    self._original_stdout_write = sys.stdout.write
    self._original_stderr_write = sys.stderr.write

    # Add protection against recursive calls
    self._protection_active = False

    # TEMPORARILY DISABLE CONSOLE PROTECTION TO PREVENT HANGING ISSUES
    # This feature can cause hanging on some systems due to terminal manipulation
    self.logger.debug("Console output protection disabled (prevents hanging issues)")
    self.logger.debug("To re-enable, modify _setup_console_output_protection()")
    return

    # Only set up protected output if readline is available and we're not on Windows
    # Also check if we're in an interactive terminal to avoid issues with non-interactive environments
    # if READLINE_AVAILABLE and os.name != "nt" and self._is_interactive_terminal():
    #    try:
    #        self._setup_protected_output()
    #        self.logger.debug("Console protection enabled successfully")
    #    except Exception as e:
    #        self.logger.debug(f"Could not set up console output protection: {e}")
    #        # Don't log this error as it could cause recursion
    # else:
    #    self.logger.debug(
    #        "Skipping console output protection (Windows, no readline, or non-interactive)"
    #    )


def _setup_protected_output(self):
    """Replace print and stdout/stderr with readline-aware versions."""
    import builtins
    import sys

    try:
        # Store originals for later restoration
        self._original_print = builtins.print
        self._original_stdout_write = sys.stdout.write
        self._original_stderr_write = sys.stderr.write

        builtins.print = self._protected_print
        sys.stdout.write = self._protected_stdout_write
        sys.stderr.write = self._protected_stderr_write

    except Exception as e:
        # Use original print to avoid recursion if logger depends on patched output
        try:
            self._original_print(f"Could not set up console output protection: {e}")
        except Exception:
            pass


def _should_preserve_line(self, text=None):
    if not (self._input_active and getattr(self, "_history_file", None)):
        return False
    return bool(text.strip()) if text is not None else True


def _protected_print(self, *args, **kwargs):
    """Print function that preserves readline input line."""
    with self._print_lock:
        if self._should_preserve_line():
            sys.stdout.write("\r\033[K")
            sys.stdout.flush()

        self._original_print(*args, **kwargs)

        if self._should_preserve_line():
            try:
                readline.redisplay()
            except (AttributeError, OSError):
                pass


def _protected_stdout_write(self, text):
    """Protected stdout.write that preserves input line."""
    with self._print_lock:
        if self._should_preserve_line(text):
            self._original_stdout_write("\r\033[K")
            self._original_stdout_write(text)
            try:
                readline.redisplay()
            except (AttributeError, OSError):
                pass
        else:
            self._original_stdout_write(text)


def _protected_stderr_write(self, text):
    """Protected stderr.write that preserves input line."""
    with self._print_lock:
        if self._should_preserve_line(text):
            self._original_stderr_write("\r\033[K")
            self._original_stderr_write(text)
            try:
                readline.redisplay()
            except (AttributeError, OSError):
                pass
        else:
            self._original_stderr_write(text)


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
