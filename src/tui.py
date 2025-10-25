#!/usr/bin/env python3
"""
TUI implementation for LeetIRCPythonBot using urwid.
The default interface. Use --console for the simple interface.
"""

import asyncio
import os
import re
import time
from collections import deque
from datetime import datetime
from typing import Dict, List, Optional

import urwid

import logger

# Try to import clipboard functionality
try:
    import pyperclip

    CLIPBOARD_AVAILABLE = True
except ImportError:
    CLIPBOARD_AVAILABLE = False

# Color palette for the TUI
PALETTE = [
    # Basic colors
    ("default", "light gray", "black"),
    ("focus", "black", "light gray"),
    ("header", "white", "dark blue"),
    ("footer", "white", "dark blue"),
    # Flash effect
    ("flash", "black", "light green"),
    # Log levels
    ("log_info", "light gray", "black"),
    ("log_warning", "yellow", "black"),
    ("log_error", "light red", "black"),
    ("log_debug", "dark gray", "black"),
    ("log_success", "light green", "black"),
    # Message types
    ("irc_message", "light cyan", "black"),
    ("bot_command", "light green", "black"),
    ("ai_response", "light magenta", "black"),
    # Input field
    ("input_normal", "light gray", "black"),
    ("input_command", "light green", "black"),
    ("input_ai", "light magenta", "black"),
]


class LogEntry:
    """Represents a single log entry."""

    def __init__(
        self,
        timestamp: datetime,
        server: str,
        level: str,
        message: str,
        source_type: str = "SYSTEM",
    ):
        self.timestamp = timestamp
        self.server = server
        self.level = level.upper()
        self.message = message
        self.source_type = source_type  # SYSTEM, IRC, BOT, AI

    def matches_filter(self, filter_text: str) -> bool:
        """Check if this log entry matches the given filter."""
        if not filter_text:
            return True

        filter_lower = filter_text.lower()
        return (
            filter_lower in self.message.lower()
            or filter_lower in self.level.lower()
            or filter_lower in self.server.lower()
            or filter_lower in self.source_type.lower()
        )

    def get_display_text(self) -> str:
        """Get formatted display text for this log entry."""
        time_str = self.timestamp.strftime("%H:%M:%S")
        return f"[{time_str}] [{self.server}] [{self.level}] {self.message}"

    def get_color_attr(self) -> str:
        """Get the urwid color attribute for this log entry."""
        level_colors = {
            "INFO": "log_info",
            "WARNING": "log_warning",
            "ERROR": "log_error",
            "DEBUG": "log_debug",
            "SUCCESS": "log_success",
        }

        source_colors = {
            "IRC": "irc_message",
            "BOT": "bot_command",
            "AI": "ai_response",
        }

        # Prefer source type coloring over level coloring
        if self.source_type in source_colors:
            return source_colors[self.source_type]

        return level_colors.get(self.level, "log_info")


class SelectableText(urwid.WidgetWrap):
    """Text widget that supports mouse selection and clipboard copying."""

    def __init__(self, text, original_attr=None):
        self.text = text
        self.original_attr = original_attr or "default"
        self._flash_handle = None

        # Create the underlying text widget
        text_widget = urwid.Text(text)
        super().__init__(text_widget)

    def selectable(self):
        return True

    def keypress(self, size, key):
        if key in ("ctrl c", "ctrl C"):
            if self.text and CLIPBOARD_AVAILABLE:
                try:
                    pyperclip.copy(self.text)
                    return None
                except Exception:
                    pass
        return key

    def mouse_event(self, *args):
        if len(args) >= 5:
            size, event, button, col, row = args[:5]
            if event == "mouse press" and button == 1:  # Left click
                # On click, copy the entire line to clipboard
                if self.text and CLIPBOARD_AVAILABLE:
                    try:
                        pyperclip.copy(self.text)
                        # Trigger flash effect
                        self._flash()
                    except Exception:
                        pass
                return True
        # Forward to parent class
        return super().mouse_event(*args)

    def _flash(self):
        """Flash the line briefly to indicate it was copied."""
        # Get the parent widget (AttrMap) to change its attribute
        parent = getattr(self, "_parent", None)
        if parent and hasattr(parent, "set_attr_map"):
            # Change to flash color
            parent.set_attr_map({None: "flash"})

            # Set a timer to restore original color
            import threading

            def restore_color():
                if parent and hasattr(parent, "set_attr_map"):
                    parent.set_attr_map({None: self.original_attr})

            # Flash for 200ms
            timer = threading.Timer(0.2, restore_color)
            timer.start()


class StatsView:
    """Statistics view showing bot and service metrics."""

    def __init__(self, tui_manager):
        self.tui_manager = tui_manager
        self._start_time = time.time()

    def get_stats_display(self):
        """Get formatted statistics display."""
        stats_lines = []

        try:
            # Bot uptime and basic info
            uptime = time.time() - self._start_time
            uptime_str = self._format_uptime(uptime)

            stats_lines.extend(
                [
                    "🤖 Bot Statistics",
                    "=" * 40,
                    f"Uptime: {uptime_str}",
                    "",
                ]
            )

            # Server statistics
            if self.tui_manager.bot_manager:
                servers = getattr(self.tui_manager.bot_manager, "servers", {})
                stats_lines.append("📡 Server Status:")

                if servers:
                    for server_name, server_obj in servers.items():
                        try:
                            is_connected = getattr(server_obj, "connected", False)
                            status = (
                                "🟢 Connected" if is_connected else "🔴 Disconnected"
                            )

                            # Get channels from bot_manager's joined_channels tracking
                            channels = set()
                            if hasattr(self.tui_manager.bot_manager, "joined_channels"):
                                channels = (
                                    self.tui_manager.bot_manager.joined_channels.get(
                                        server_name, set()
                                    )
                                )
                            channel_count = len(channels)

                            stats_lines.extend(
                                [
                                    f"  {server_name}: {status}",
                                    f"    Channels: {channel_count}",
                                ]
                            )

                            # Show channel details if any
                            if channels:
                                active_channel = getattr(
                                    self.tui_manager.bot_manager, "active_channel", None
                                )
                                active_server = getattr(
                                    self.tui_manager.bot_manager, "active_server", None
                                )
                                for channel in sorted(channels):
                                    active_marker = (
                                        " (active)"
                                        if channel == active_channel
                                        and server_name == active_server
                                        else ""
                                    )
                                    stats_lines.append(
                                        f"      {channel}{active_marker}"
                                    )
                        except Exception as e:
                            stats_lines.append(f"  {server_name}: ❌ Error: {e}")
                else:
                    stats_lines.append("  No servers configured")

                stats_lines.append("")

                # Service statistics
                stats_lines.append("🔧 Services Status:")
                services = {
                    "⚡ Electricity": getattr(
                        self.tui_manager.bot_manager, "electricity_service", None
                    ),
                    "🌤️ Weather": getattr(
                        self.tui_manager.bot_manager, "weather_service", None
                    ),
                    "🤖 GPT Chat": getattr(
                        self.tui_manager.bot_manager, "gpt_service", None
                    ),
                    "💰 Crypto": getattr(
                        self.tui_manager.bot_manager, "crypto_service", None
                    ),
                    "▶️ YouTube": getattr(
                        self.tui_manager.bot_manager, "youtube_service", None
                    ),
                    "📢 Otiedote": getattr(
                        self.tui_manager.bot_manager, "otiedote_service", None
                    ),
                    "⚠️ FMI Warnings": getattr(
                        self.tui_manager.bot_manager, "fmi_warning_service", None
                    ),
                }

                for service_name, service_obj in services.items():
                    status = "🟢 Active" if service_obj is not None else "🔴 Inactive"
                    stats_lines.append(f"  {service_name}: {status}")

                stats_lines.append("")

                # Memory and performance stats (if psutil is available)
                stats_lines.append("💾 Memory & Performance:")

                try:
                    import os

                    import psutil

                    process = psutil.Process(os.getpid())
                    memory_info = process.memory_info()
                    memory_mb = memory_info.rss / 1024 / 1024
                    cpu_percent = process.cpu_percent()

                    stats_lines.extend(
                        [
                            f"  Memory Usage: {memory_mb:.1f} MB",
                            f"  CPU Usage: {cpu_percent:.1f}%",
                        ]
                    )
                except ImportError:
                    stats_lines.append(
                        "  Install psutil for detailed performance stats"
                    )
                except Exception as e:
                    stats_lines.append(f"  Performance stats error: {e}")

                # Log statistics
                stats_lines.append("")
                stats_lines.append("📊 Log Statistics:")

                total_logs = len(self.tui_manager.log_entries)
                buffer_size = self.tui_manager.log_entries.maxlen

                stats_lines.extend(
                    [
                        f"  Total Log Entries: {total_logs}/{buffer_size}",
                        (
                            f"  Current Filter: '{self.tui_manager.current_filter}' (active)"
                            if self.tui_manager.current_filter
                            else "  Filter: None"
                        ),
                    ]
                )

        except Exception as e:
            stats_lines = ["❌ Error loading statistics:", f"   {e}"]

        return "\n".join(stats_lines)

    def _format_uptime(self, seconds):
        """Format uptime in a human-readable way."""
        days, remainder = divmod(int(seconds), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, secs = divmod(remainder, 60)

        if days > 0:
            return f"{days}d {hours}h {minutes}m {secs}s"
        elif hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"


class ConfigEditor:
    """Configuration editor for runtime settings changes."""

    def __init__(self, tui_manager):
        self.tui_manager = tui_manager

    def get_config_display(self):
        """Get formatted configuration display."""
        config_lines = []

        config_sections = {
            "🤖 Bot Settings": [
                ("BOT_NAME", "Bot nickname"),
                ("LOG_LEVEL", "Logging level (DEBUG, INFO, WARNING, ERROR)"),
                ("AUTO_CONNECT", "Auto-connect to servers (true/false)"),
                ("LOG_BUFFER_SIZE", "Maximum log entries in memory"),
                ("USE_NOTICES", "Use IRC NOTICEs instead of PRIVMSG (true/false)"),
                ("TAMAGOTCHI_ENABLED", "Enable tamagotchi responses (true/false)"),
            ],
            "🔑 API Keys": [
                ("WEATHER_API_KEY", "OpenWeatherMap API key"),
                ("OPENAI_API_KEY", "OpenAI API key"),
                ("ELECTRICITY_API_KEY", "Electricity price API key"),
                ("YOUTUBE_API_KEY", "YouTube Data API key"),
                ("EUROJACKPOT_API_KEY", "Eurojackpot API key"),
            ],
            "📁 File Paths": [
                ("HISTORY_FILE", "Conversation history file"),
                ("EKAVIKA_FILE", "Ekavika data file"),
                ("WORDS_FILE", "General words file"),
                ("SUBSCRIBERS_FILE", "Subscribers file"),
            ],
            "🔧 Advanced Settings": [
                ("RECONNECT_DELAY", "Reconnection delay in seconds"),
                ("QUIT_MESSAGE", "Default quit message"),
                ("GPT_HISTORY_LIMIT", "Max GPT conversation history"),
                ("ADMIN_PASSWORD", "Admin command password"),
            ],
        }

        config_lines.extend(
            [
                "⚙️ Configuration Editor",
                "=" * 40,
                "Use 'config:key=value' to change settings",
                "Use 'config:save' to save to .env file",
                "Use 'config:reload' to reload from .env file",
                "",
            ]
        )

        for section_name, config_list in config_sections.items():
            config_lines.append(section_name)
            config_lines.append("-" * len(section_name))

            for key, description in config_list:
                current_value = os.getenv(key, "[Not Set]")
                # Mask sensitive values
                if "KEY" in key.upper() or "PASSWORD" in key.upper():
                    display_value = (
                        "[Hidden]" if current_value != "[Not Set]" else "[Not Set]"
                    )
                else:
                    display_value = (
                        current_value[:50] + "..."
                        if len(current_value) > 50
                        else current_value
                    )

                config_lines.extend(
                    [
                        f"{key}:",
                        f"  {description}",
                        f"  Current: {display_value}",
                        "",
                    ]
                )

        return "\n".join(config_lines)

    def handle_config_command(self, command):
        """Handle a configuration command."""
        try:
            if command == "save":
                return self._save_config()
            elif command == "reload":
                return self._reload_config()
            elif "=" in command:
                # Setting a value
                key, value = command.split("=", 1)
                return self._set_config_value(key.strip(), value.strip())
            else:
                return "Invalid config command. Use: config:key=value, config:save, or config:reload"
        except Exception as e:
            return f"Config error: {e}"

    def _set_config_value(self, key, value):
        """Set a configuration value."""
        os.environ[key] = value
        return f"Set {key} = {value[:50]}{'...' if len(value) > 50 else ''}"

    def _save_config(self):
        """Save current configuration to .env file."""
        try:
            env_content = []

            # Read current .env file if it exists
            env_file = ".env"
            if os.path.exists(env_file):
                with open(env_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            else:
                lines = []

            # Update or add environment variables
            updated_keys = set()
            for i, line in enumerate(lines):
                if "=" in line and not line.strip().startswith("#"):
                    key = line.split("=")[0]
                    if key in os.environ:
                        lines[i] = f"{key}={os.environ[key]}\n"
                        updated_keys.add(key)
                env_content.append(lines[i].rstrip())

            # Add new environment variables that weren't in the file
            for key, value in os.environ.items():
                if (
                    key not in updated_keys
                    and not key.startswith("_")
                    and key.isupper()
                ):
                    env_content.append(f"{key}={value}")

            # Write back to file
            with open(env_file, "w", encoding="utf-8") as f:
                f.write("\n".join(env_content) + "\n")

            return f"Configuration saved to {env_file}"

        except Exception as e:
            return f"Failed to save configuration: {e}"

    def _reload_config(self):
        """Reload configuration from .env file."""
        try:
            from dotenv import load_dotenv

            load_dotenv(override=True)
            return "Configuration reloaded from .env file"
        except Exception as e:
            return f"Failed to reload configuration: {e}"


class TUIManager:
    """Main TUI manager class with statistics and configuration editor."""

    def __init__(self, bot_manager=None):
        self.bot_manager = bot_manager

        # Configuration
        self.log_buffer_size = int(os.getenv("LOG_BUFFER_SIZE", "1000"))

        # State
        self.log_entries = deque(maxlen=self.log_buffer_size)
        self.command_history = []
        self.history_index = 0
        self.current_filter = ""
        self.current_view = "console"  # console, stats, config

        # UI components
        self.header = urwid.Text("")
        self.log_walker = urwid.SimpleListWalker([])
        self.log_display = urwid.ListBox(self.log_walker)
        self.input_field = urwid.Edit("> Enter message (! for bot, - for AI): ")

        # Additional views
        self.stats_view = StatsView(self)
        self.config_editor = ConfigEditor(self)

        # Set up layout
        self.setup_layout()

        # Update header initially
        self.update_header()

    def setup_layout(self):
        """Set up the main TUI layout."""
        # Header with status information
        header = urwid.AttrMap(self.header, "header")

        # Footer with input
        footer = urwid.AttrMap(self.input_field, "footer")

        # Main layout
        self.main_layout = urwid.Frame(
            body=self.log_display, header=header, footer=footer, focus_part="footer"
        )

    def update_header(self):
        """Update the header with current status."""
        current_time = datetime.now().strftime("%H:%M:%S")

        # Get server status if bot manager is available
        server_status = "No servers"
        if self.bot_manager:
            try:
                servers = getattr(self.bot_manager, "servers", {})
                if servers:
                    server_count = len(servers)
                    connected_count = 0

                    # Check each server's connection status
                    for server in servers.values():
                        try:
                            if hasattr(server, "connected") and server.connected:
                                connected_count += 1
                        except Exception:
                            pass

                    if connected_count > 0:
                        server_status = f"🟢 {connected_count}/{server_count} connected"
                    else:
                        server_status = f"🔴 {server_count} servers (disconnected)"
                else:
                    server_status = "No servers configured"
            except Exception:
                server_status = "Server status unknown"

        # Get service status
        service_status = self._get_service_status()

        # View indicator
        view_indicator = f"View: {self.current_view.title()}"

        # Update header text with two lines
        status_line1 = (
            f"LeetIRC Bot TUI | {current_time} | {server_status} | {service_status} | "
            f"{view_indicator} | Logs: {len(self.log_entries)}"
        )
        status_line2 = "F1=Help F2=Console F3=Stats F4=Config"

        status_text = f"{status_line1}\n{status_line2}"
        self.header.set_text(status_text)

    def _get_service_status(self) -> str:
        """Get service status indicators."""
        if not self.bot_manager:
            return "No services"

        services = []
        try:
            # Check each service
            if (
                hasattr(self.bot_manager, "weather_service")
                and self.bot_manager.weather_service
            ):
                services.append("🌤")
            if (
                hasattr(self.bot_manager, "gpt_service")
                and self.bot_manager.gpt_service
            ):
                services.append("🤖")
            if (
                hasattr(self.bot_manager, "electricity_service")
                and self.bot_manager.electricity_service
            ):
                services.append("⚡")
            if (
                hasattr(self.bot_manager, "crypto_service")
                and self.bot_manager.crypto_service
            ):
                services.append("💰")
            if (
                hasattr(self.bot_manager, "youtube_service")
                and self.bot_manager.youtube_service
            ):
                services.append("📺")
        except Exception:
            pass

        if services:
            return " ".join(services)
        else:
            return "No services"

    def add_log_entry(
        self,
        timestamp: datetime,
        server: str,
        level: str,
        message: str,
        source_type: str = "SYSTEM",
    ):
        """Add a new log entry to the display."""
        entry = LogEntry(timestamp, server, level, message, source_type)
        self.log_entries.append(entry)

        # Check if entry matches current filter
        if entry.matches_filter(self.current_filter):
            # Create selectable text widget with mouse support
            color_attr = entry.get_color_attr()
            selectable_text = urwid.AttrMap(
                SelectableText(entry.get_display_text(), color_attr),
                color_attr,
            )
            self.log_walker.append(selectable_text)

            # Auto-scroll to bottom (safe focus handling)
            try:
                if len(self.log_walker) > 0:
                    self.log_display.set_focus(len(self.log_walker) - 1)
            except IndexError:
                # Fallback: try to set focus to the last available position
                try:
                    if len(self.log_walker) > 0:
                        self.log_display.set_focus(0)
                except IndexError:
                    # If still failing, ignore focus setting
                    pass

    def apply_filter(self, filter_text: str):
        """Apply a filter to the log display."""
        self.current_filter = filter_text

        # Store current focus position before clearing
        current_focus = None
        try:
            if len(self.log_walker) > 0:
                current_focus = self.log_display.focus_position
        except (IndexError, AttributeError):
            current_focus = None

        # Rebuild the display with filtered entries
        self.log_walker.clear()

        for entry in self.log_entries:
            if entry.matches_filter(filter_text):
                # Create selectable text widget with mouse support
                color_attr = entry.get_color_attr()
                selectable_text = urwid.AttrMap(
                    SelectableText(entry.get_display_text(), color_attr),
                    color_attr,
                )
                self.log_walker.append(selectable_text)

        # Auto-scroll to bottom (safe focus handling)
        try:
            if len(self.log_walker) > 0:
                self.log_display.set_focus(len(self.log_walker) - 1)
        except IndexError:
            # Fallback: try to set focus to the first position or maintain previous position
            try:
                if len(self.log_walker) > 0:
                    # Try to maintain focus at a safe position
                    safe_focus = min(current_focus or 0, len(self.log_walker) - 1)
                    self.log_display.set_focus(safe_focus)
            except (IndexError, TypeError):
                # If still failing, ignore focus setting
                pass

    def process_input(self, text: str) -> bool:
        """Process user input.

        Returns:
            bool: True to continue, False to exit
        """
        if not text.strip():
            return True

        # Add to history
        if text not in self.command_history:
            self.command_history.append(text)
        self.history_index = len(self.command_history)

        # Handle TUI-specific commands first
        if text.lower().startswith("filter:"):
            # Filter command
            filter_text = text[7:].strip()
            self.apply_filter(filter_text)
            self.add_log_entry(
                datetime.now(),
                "Console",
                "INFO",
                f"Applied filter: '{filter_text}'" if filter_text else "Cleared filter",
                "SYSTEM",
            )
            return True
        elif text.lower().startswith("config:"):
            # Configuration command
            config_command = text[7:].strip()
            result = self.config_editor.handle_config_command(config_command)
            self.add_log_entry(datetime.now(), "Config", "INFO", result, "SYSTEM")
            return True
        elif text.lower() in ["stats", "statistics"]:
            # Switch to stats view
            self.switch_view("stats")
            return True
        elif text.lower() in ["config", "configuration"]:
            # Switch to config view
            self.switch_view("config")
            return True
        elif text.lower() in ["console", "logs"]:
            # Switch to console view
            self.switch_view("console")
            return True
        else:
            # Use unified command processing from command_loader
            if self.bot_manager:
                try:
                    from command_loader import process_user_input

                    should_continue = process_user_input(text, self.bot_manager, "TUI")
                    return should_continue
                except Exception as e:
                    self.add_log_entry(
                        datetime.now(),
                        "Console",
                        "ERROR",
                        f"Error processing input: {e}",
                        "SYSTEM",
                    )
                    return True
            else:
                self.add_log_entry(
                    datetime.now(),
                    "Console",
                    "WARNING",
                    "Bot manager not available",
                    "SYSTEM",
                )
                return True

    def handle_key(self, key):
        """Handle keyboard input."""
        if key in ("ctrl c", "ctrl C"):
            raise urwid.ExitMainLoop()

        elif key == "enter":
            # Process input
            text = self.input_field.get_edit_text()
            if text.strip():
                should_continue = self.process_input(text)
                if not should_continue:
                    # Exit was requested
                    raise urwid.ExitMainLoop()
                self.input_field.set_edit_text("")
                self.update_input_style()

        elif key == "up":
            # Command history up
            if self.command_history and self.history_index > 0:
                self.history_index -= 1
                self.input_field.set_edit_text(self.command_history[self.history_index])
                self.update_input_style()

        elif key == "down":
            # Command history down
            if (
                self.command_history
                and self.history_index < len(self.command_history) - 1
            ):
                self.history_index += 1
                self.input_field.set_edit_text(self.command_history[self.history_index])
                self.update_input_style()
            elif self.history_index >= len(self.command_history) - 1:
                self.input_field.set_edit_text("")
                self.history_index = len(self.command_history)
                self.update_input_style()

        elif key == "esc":
            # Clear input
            self.input_field.set_edit_text("")
            self.history_index = len(self.command_history)
            self.update_input_style()

        elif key in ("f1", "?"):
            # Show help
            self.show_help()

        elif key == "f2":
            # Switch to console view
            self.switch_view("console")

        elif key == "f3":
            # Switch to stats view
            self.switch_view("stats")

        elif key == "f4":
            # Switch to config view
            self.switch_view("config")

        elif key == "shift tab":
            # Switch focus between input field and log display
            current_focus = self.main_layout.focus_part
            if current_focus == "footer":
                # Switch to body (log display)
                self.main_layout.focus_part = "body"
                self.add_log_entry(
                    datetime.now(),
                    "Console",
                    "DEBUG",
                    "Focus switched to log display. Use Shift+Tab to return to input.",
                    "SYSTEM",
                )
            else:
                # Switch back to footer (input field)
                self.main_layout.focus_part = "footer"
                self.add_log_entry(
                    datetime.now(),
                    "Console",
                    "DEBUG",
                    "Focus switched to input field.",
                    "SYSTEM",
                )

    def mouse_event(self, size, event, button, col, row):
        """Handle mouse events."""
        # Handle focus switching first
        if event == "mouse press" and button == 1:  # Left click
            # If clicking in the log area, switch focus to body
            if row < size[1] - 3:  # Rough estimate of log area
                self.main_layout.focus_part = "body"
            else:
                # Click in input area, switch focus to footer
                self.main_layout.focus_part = "footer"

        # Forward mouse events to the focused widget for text selection
        return self.main_layout.mouse_event(size, event, button, col, row)

    def switch_view(self, view_name):
        """Switch between different views (console, stats, config)."""
        self.current_view = view_name

        try:
            if view_name == "stats":
                # Show statistics in log display
                stats_text = self.stats_view.get_stats_display()
                self.log_walker.clear()
                for line in stats_text.split("\n"):
                    text_widget = urwid.Text(line)
                    self.log_walker.append(text_widget)

                # Safe focus handling after switching to stats
                try:
                    if len(self.log_walker) > 0:
                        self.log_display.set_focus(0)
                except IndexError:
                    pass

                self.add_log_entry(
                    datetime.now(),
                    "Console",
                    "INFO",
                    "Switched to statistics view",
                    "SYSTEM",
                )

            elif view_name == "config":
                # Show configuration editor in log display
                config_text = self.config_editor.get_config_display()
                self.log_walker.clear()
                for line in config_text.split("\n"):
                    text_widget = urwid.Text(line)
                    self.log_walker.append(text_widget)

                # Safe focus handling after switching to config
                try:
                    if len(self.log_walker) > 0:
                        self.log_display.set_focus(0)
                except IndexError:
                    pass

                self.add_log_entry(
                    datetime.now(),
                    "Console",
                    "INFO",
                    "Switched to configuration editor view",
                    "SYSTEM",
                )

            elif view_name == "console":
                # Restore normal log display
                self.apply_filter(self.current_filter)  # This rebuilds the log display

                self.add_log_entry(
                    datetime.now(),
                    "Console",
                    "INFO",
                    "Switched to console view",
                    "SYSTEM",
                )
        except Exception as e:
            # Log the error but don't crash the view switching
            try:
                self.add_log_entry(
                    datetime.now(),
                    "Console",
                    "ERROR",
                    f"Error switching to {view_name} view: {e}",
                    "SYSTEM",
                )
            except Exception:
                # If even logging fails, just ignore
                pass

    def update_input_style(self):
        """Update input field caption based on current text."""
        text = self.input_field.get_edit_text()
        if text.startswith("!"):
            self.input_field.set_caption("> Bot command: ")
        elif text.startswith("-"):
            self.input_field.set_caption("> AI chat: ")
        elif text.lower().startswith("filter:"):
            self.input_field.set_caption("> Filter logs: ")
        elif text.lower().startswith("config:"):
            self.input_field.set_caption("> Config command: ")
        else:
            self.input_field.set_caption("> Channel message: ")

    def write_log_to_file(self, filename="tui.log"):
        """Write all log entries to a file.

        Args:
            filename: The filename to write the log to (default: tui.log)
        """
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write("=" * 80 + "\n")
                f.write("LeetIRC Bot TUI Log\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total Entries: {len(self.log_entries)}\n")
                f.write("=" * 80 + "\n\n")

                for entry in self.log_entries:
                    # Write each log entry in a formatted way
                    timestamp_str = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    f.write(
                        f"[{timestamp_str}] [{entry.server}] [{entry.level}] [{entry.source_type}]\n"
                    )
                    f.write(f"  {entry.message}\n")
                    f.write("\n")

                f.write("=" * 80 + "\n")
                f.write("End of TUI Log\n")
                f.write("=" * 80 + "\n")

            # Log success (but only if we still have access to the logger)
            try:
                logger.get_logger("TUI").info(f"TUI log written to {filename}")
            except Exception:
                pass  # Ignore if logger is unavailable

        except Exception as e:
            # Try to log the error, but don't fail if we can't
            try:
                logger.get_logger("TUI").error(f"Failed to write TUI log: {e}")
            except Exception:
                pass  # Ignore if logger is unavailable

    def show_help(self):
        """Show help information."""
        help_text = """
Leet IRC Python Bot TUI Help:

Views:
  F2 / console     - Console view (logs and messages)
  F3 / stats       - Statistics view (bot performance)
  F4 / config      - Configuration editor

Commands:
  !command        - Send bot command (e.g., !help, !connect, !exit)
  -message        - Send to AI chat
  filter:text     - Filter logs by text (use 'filter:' to clear)
  config:key=val  - Set configuration value
  config:save     - Save config to .env file
  config:reload   - Reload config from .env file
  message         - Send to IRC channel

Keyboard Shortcuts:
  Ctrl+C          - Exit TUI immediately
  !exit, !quit    - Shutdown bot gracefully
  F1, ?           - Show this help
  F2              - Console view
  F3              - Statistics view
  F4              - Configuration editor
  Up/Down         - Navigate command history
  Enter           - Send message/command
  Escape          - Clear input field
  Shift+Tab       - Switch focus between input and log display

Tips:
  - Use 'filter:ERROR' to show only error messages
  - Use 'filter:' to clear all filters
  - Command history remembers your previous inputs
  - Commands run asynchronously - you can type while commands process
  - Statistics view shows real-time bot performance
  - Config editor allows runtime configuration changes
  - Click on any log line to copy it to clipboard (pyperclip)
        """

        self.add_log_entry(datetime.now(), "Console", "INFO", help_text, "SYSTEM")

    def run(self):
        """Run the TUI main loop."""
        # Set up logger hook to receive all log messages
        logger.set_tui_hook(self.add_log_entry)

        # Add initial log entries
        self.add_log_entry(
            datetime.now(),
            "Console",
            "INFO",
            "TUI started successfully! Type commands or messages below.",
            "SYSTEM",
        )

        # Show clipboard status
        clipboard_status = (
            "Click-to-copy functionality enabled - click any log line to copy it"
            if CLIPBOARD_AVAILABLE
            else "Click functionality available (install pyperclip for clipboard copy)"
        )
        self.add_log_entry(
            datetime.now(),
            "Console",
            "INFO",
            clipboard_status,
            "SYSTEM",
        )

        if self.bot_manager:
            self.add_log_entry(
                datetime.now(), "Console", "INFO", "Bot manager connected", "SYSTEM"
            )

            # Check if AUTO_CONNECT is enabled
            auto_connect = os.getenv("AUTO_CONNECT", "false").lower() == "true"
            if auto_connect:
                self.add_log_entry(
                    datetime.now(),
                    "Console",
                    "INFO",
                    "Auto-connecting to configured servers...",
                    "SYSTEM",
                )
                try:
                    self.bot_manager.connect_to_servers()
                    self.add_log_entry(
                        datetime.now(),
                        "Console",
                        "INFO",
                        "Connection initiated. Channels will be joined automatically.",
                        "SYSTEM",
                    )
                except Exception as e:
                    self.add_log_entry(
                        datetime.now(),
                        "Console",
                        "ERROR",
                        f"Failed to connect to servers: {e}",
                        "SYSTEM",
                    )
            else:
                self.add_log_entry(
                    datetime.now(),
                    "Console",
                    "INFO",
                    "AUTO_CONNECT is disabled. Use !connect to connect to IRC servers.",
                    "SYSTEM",
                )

            self.add_log_entry(
                datetime.now(),
                "Console",
                "INFO",
                "Available commands: !help, !connect, !status, stats, config",
                "SYSTEM",
            )
        else:
            self.add_log_entry(
                datetime.now(),
                "Console",
                "WARNING",
                "No bot manager - running in standalone mode",
                "SYSTEM",
            )

        # Create and run main loop with mouse support
        self.loop = urwid.MainLoop(
            self.main_layout,
            palette=PALETTE,
            unhandled_input=self.handle_key,
            handle_mouse=True,  # Enable mouse support
        )

        # Set up periodic updates
        def update_callback():
            try:
                self.update_header()

                # Auto-refresh current view if it's stats or config
                if self.current_view == "stats":
                    # Refresh stats display
                    stats_text = self.stats_view.get_stats_display()
                    self.log_walker.clear()
                    for line in stats_text.split("\n"):
                        text_widget = urwid.Text(line)
                        self.log_walker.append(text_widget)

                    # Safe focus handling after refresh
                    try:
                        if len(self.log_walker) > 0:
                            self.log_display.set_focus(
                                0
                            )  # Set to first item for stats view
                    except IndexError:
                        pass

                elif self.current_view == "config":
                    # Refresh config display
                    config_text = self.config_editor.get_config_display()
                    self.log_walker.clear()
                    for line in config_text.split("\n"):
                        text_widget = urwid.Text(line)
                        self.log_walker.append(text_widget)

                    # Safe focus handling after refresh
                    try:
                        if len(self.log_walker) > 0:
                            self.log_display.set_focus(
                                0
                            )  # Set to first item for config view
                    except IndexError:
                        pass

                self.loop.set_alarm_in(1, lambda *args: update_callback())
            except Exception as e:
                # Log the error but don't crash the update loop
                try:
                    self.add_log_entry(
                        datetime.now(),
                        "Console",
                        "ERROR",
                        f"Update callback error: {e}",
                        "SYSTEM",
                    )
                except Exception:
                    # If even logging fails, just continue
                    pass
                # Continue the update loop anyway
                self.loop.set_alarm_in(1, lambda *args: update_callback())

        # Start update cycle
        self.loop.set_alarm_in(1, lambda *args: update_callback())

        # Run the loop
        try:
            self.loop.run()
        finally:
            # Write TUI log to file before exiting
            self.write_log_to_file()
            # Clear the logger hook when TUI exits
            logger.clear_tui_hook()


def main():
    """Main entry point for testing."""
    tui = TUIManager()
    tui.run()


if __name__ == "__main__":
    main()
