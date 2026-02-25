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
import shutil
import threading
import time
from datetime import datetime, timedelta, timezone

# from typing import Optional


def get_log_files(log_file: str = "data/leet.log"):
    """Get sorted list of existing log files."""
    base_name = os.path.basename(log_file)
    dir_name = os.path.dirname(log_file)
    files = []
    for f in os.listdir(dir_name):
        if f.startswith(base_name):
            files.append(os.path.join(dir_name, f))
    # Sort by modification time (oldest first)
    files.sort(key=lambda x: os.path.getmtime(x))
    return files


def rotate_logs(log_file: str = "data/leet.log", max_count: int = 10):
    """Rotate log files, keeping maximum of max_count files."""
    # Ensure data directory exists
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    # Get existing log files
    files = get_log_files(log_file)

    # Remove oldest file if we have too many
    if len(files) >= max_count:
        try:
            os.remove(files[0])
            files.pop(0)
        except Exception:
            pass

    # Rename files: leet.log.9 -> leet.log.10, leet.log.8 -> leet.log.9, etc.
    for i in range(len(files) - 1, -1, -1):
        try:
            new_index = i + 2  # leet.log.1 becomes leet.log.2, etc.
            if new_index <= max_count:
                new_name = f"{log_file}.{new_index}"
                os.rename(files[i], new_name)
        except Exception:
            pass

    # Rename current log file to .1
    try:
        if os.path.exists(log_file):
            os.rename(log_file, f"{log_file}.1")
    except Exception:
        pass

    # Create new empty log file
    try:
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("LeetIRCBot Log - Rotated at startup\n")
    except Exception:
        pass


def check_log_size(log_file: str = "data/leet.log", max_size: int = 10485760):
    """Check if log file exceeds max_size and rotate if needed."""
    try:
        if os.path.exists(log_file) and os.path.getsize(log_file) > max_size:
            rotate_logs(log_file)
    except Exception:
        pass


def should_rotate_by_time(
    log_file: str = "data/leet.log", interval: str = "", rotation_time: str = "00:00"
):
    """
    Check if log should be rotated based on time interval.
    interval: minute, hour, day, week, month, year
    rotation_time: time of day for daily/weekly/monthly rotation (HH:MM format)
    """
    try:
        if not interval:
            return False

        # Get last rotation time from log file metadata
        if not os.path.exists(log_file):
            return True  # First run, rotate

        last_mod_time = datetime.fromtimestamp(os.path.getmtime(log_file))
        now = datetime.now()

        # Calculate time since last rotation
        time_since = now - last_mod_time

        # Check interval
        if interval == "minute":
            return time_since >= timedelta(minutes=1)
        elif interval == "hour":
            return time_since >= timedelta(hours=1)
        elif interval == "day":
            # Check if it's a new day at the specified time
            target_time = now.replace(
                hour=int(rotation_time.split(":")[0]),
                minute=int(rotation_time.split(":")[1]),
                second=0,
                microsecond=0,
            )
            if now >= target_time and last_mod_time < target_time:
                return True
        elif interval == "week":
            # Check if it's a new week (Monday at specified time)
            target_day = now - timedelta(days=now.weekday())  # Monday
            target_time = target_day.replace(
                hour=int(rotation_time.split(":")[0]),
                minute=int(rotation_time.split(":")[1]),
                second=0,
                microsecond=0,
            )
            if now >= target_time and last_mod_time < target_time:
                return True
        elif interval == "month":
            # Check if it's a new month at specified time
            if now.month != last_mod_time.month or now.year != last_mod_time.year:
                target_time = now.replace(
                    day=1,
                    hour=int(rotation_time.split(":")[0]),
                    minute=int(rotation_time.split(":")[1]),
                    second=0,
                    microsecond=0,
                )
                if now >= target_time:
                    return True
        elif interval == "year":
            # Check if it's a new year at specified time
            if now.year != last_mod_time.year:
                target_time = now.replace(
                    month=1,
                    day=1,
                    hour=int(rotation_time.split(":")[0]),
                    minute=int(rotation_time.split(":")[1]),
                    second=0,
                    microsecond=0,
                )
                if now >= target_time:
                    return True

        return False
    except Exception:
        return False


def check_log_rotation(
    log_file: str = "data/leet.log",
    max_size: int = 10485760,
    interval: str = "",
    rotation_time: str = "00:00",
):
    """Check both size and time-based rotation conditions."""
    # Check size-based rotation
    check_log_size(log_file, max_size)

    # Check time-based rotation
    if should_rotate_by_time(log_file, interval, rotation_time):
        rotate_logs(log_file)


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

        Uses a single time source (time.time_ns()) to ensure consistent timestamps.

        Returns:
            Formatted timestamp string with nanoseconds
        """
        # Use time.time_ns() as single source for both seconds and nanoseconds
        # This ensures the datetime and nanoseconds are from the same moment
        ns = time.time_ns()
        seconds = ns // 1_000_000_000
        nanoseconds = ns % 1_000_000_000

        # Convert to datetime using UTC to avoid timezone issues
        dt = datetime.fromtimestamp(seconds, tz=timezone.utc).astimezone()

        # Format: [2025-06-19 02:15:38.882221300]
        return f"[{dt.strftime('%Y-%m-%d %H:%M:%S')}.{nanoseconds:09d}]"

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

            # Forward to file if hook is set (always do this for file logging)
            # Use lock to ensure thread-safe writes in correct order
            if _file_hook:
                try:
                    with _file_lock:
                        _file_hook(timestamp, level.upper(), output)
                except Exception as e:
                    # Don't let file hook errors break logging
                    print(f"[LOGGER ERROR] File hook failed: {e}")

            # Forward to TUI if hook is set, otherwise print to console
            if _tui_hook:
                try:
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

                    # Pass datetime to TUI - TUI recalculates nanoseconds when displaying
                    # using its own time.time_ns() call in get_display_text()
                    _tui_hook(
                        datetime.now(),
                        context or "System",
                        level.upper(),
                        message,
                        source_type,
                    )
                except Exception as e:
                    # Don't let TUI hook errors break logging
                    print(f"[LOGGER ERROR] TUI hook failed: {e}")
            else:
                # Only print to console if TUI hook is not active
                print(f"{timestamp} {output}")  # Main console log output
                # Also buffer for TUI display later
                source_type = "SYSTEM"
                if context and any(
                    word in context.lower() for word in ["irc", "server"]
                ):
                    source_type = "IRC"
                elif context and "gpt" in context.lower():
                    source_type = "AI"
                elif level.upper() == "MSG":
                    source_type = "IRC"
                add_to_log_buffer(
                    datetime.now(),
                    context or "System",
                    level.upper(),
                    message,
                    source_type,
                )

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

                        # Pass datetime to TUI - TUI recalculates nanoseconds when displaying
                        _tui_hook(
                            datetime.now(),
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
                        # Pass datetime to TUI - TUI recalculates nanoseconds when displaying
                        _tui_hook(
                            datetime.now(), "Logger", "ERROR", error_msg, "SYSTEM"
                        )
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

# File hook for writing logs to file
_file_hook = None

# Lock for thread-safe file writing
_file_lock = threading.Lock()

# Buffer for logs before TUI starts
_log_buffer = []


def add_to_log_buffer(timestamp, server, level, message, source_type):
    """Add a log entry to the buffer for later display in TUI."""
    _log_buffer.append((timestamp, server, level, message, source_type))


def get_and_clear_log_buffer():
    """Get all buffered log entries and clear the buffer."""
    global _log_buffer
    buffer = _log_buffer.copy()
    _log_buffer = []
    return buffer


def set_file_hook(hook_function):
    """Set a hook function to forward log messages to file.

    Args:
        hook_function: Function that accepts (timestamp, level, message)
    """
    global _file_hook
    _file_hook = hook_function


def clear_file_hook():
    """Clear the file hook."""
    global _file_hook
    _file_hook = None


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
