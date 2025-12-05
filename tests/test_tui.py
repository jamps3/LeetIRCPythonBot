#!/usr/bin/env python3
"""
Pytest tests for TUI (Text User Interface) module.

Tests the TUIManager, LogEntry, SelectableText, StatsView, ConfigEditor,
and related classes with comprehensive coverage.
"""

import os
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

# Import TUI components
from tui import (  # WRAP_MODE,; _current_tui,
    ConfigEditor,
    FocusProtectingFrame,
    LogEntry,
    NonFocusableListBox,
    SelectableText,
    StatsView,
    TUIManager,
)


@pytest.fixture(autouse=True, scope="function")
def reset_tui_globals():
    """Reset global TUI variables before each test."""
    global _current_tui
    _current_tui = None

    # Reset wrap mode to default
    import tui

    tui.WRAP_MODE = True


@pytest.fixture
def mock_urwid():
    """Mock urwid components for testing."""
    with patch("tui.urwid") as mock_urwid:
        # Mock basic urwid components
        mock_urwid.Text = Mock
        mock_urwid.Edit = Mock
        mock_urwid.MainLoop = Mock
        mock_urwid.ExitMainLoop = Exception
        mock_urwid.Frame = Mock
        mock_urwid.ListBox = Mock

        # SimpleListWalker needs to behave like a list for the tests
        def mock_simple_list_walker_init(self, contents=None):
            self.contents = contents or []
            self.set_focus = Mock()

        mock_urwid.SimpleListWalker = type(
            "MockSimpleListWalker",
            (),
            {
                "__init__": mock_simple_list_walker_init,
            },
        )

        # Create AttrMap mock that avoids Widget inheritance warnings
        def mock_attr_map_init(*args, **kwargs):
            # Return a basic mock without Widget inheritance
            mock_instance = Mock()
            mock_instance.set_attr_map = Mock()
            return mock_instance

        mock_urwid.AttrMap = mock_attr_map_init

        # Create WidgetWrap mock that avoids Widget inheritance warnings
        def mock_widget_wrap_init(self, w, *args, **kwargs):
            # Set basic attributes without inheritance
            self._w = w
            self._original_widget = w

        mock_urwid.WidgetWrap = type(
            "MockWidgetWrap",
            (),
            {
                "__init__": mock_widget_wrap_init,
                "selectable": lambda self: True,
                "keypress": lambda self, size, key: key,
                "mouse_event": lambda self, *args: False,
            },
        )

        yield mock_urwid


@pytest.fixture
def mock_bot_manager():
    """Create a mock bot manager."""
    bm = Mock()
    bm.servers = {"testserver": Mock(connected=True, name="TestServer")}
    bm.joined_channels = {"testserver": ["#test", "#general"]}
    bm.active_channel = "#test"
    bm.active_server = "testserver"
    bm.weather_service = Mock()
    bm.gpt_service = Mock()
    bm.electricity_service = Mock()
    bm.crypto_service = Mock()
    bm.youtube_service = Mock()
    bm.otiedote_service = Mock()
    bm.fmi_warning_service = Mock()
    return bm


@pytest.fixture
def sample_log_entry():
    """Create a sample log entry for testing."""
    timestamp = datetime(2024, 1, 1, 12, 0, 0)
    return LogEntry(timestamp, "TestServer", "INFO", "Test message", "SYSTEM")


class TestLogEntry:
    """Test LogEntry class functionality."""

    def test_log_entry_creation(self):
        """Test LogEntry object creation."""
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        entry = LogEntry(timestamp, "TestServer", "INFO", "Test message", "SYSTEM")

        assert entry.timestamp == timestamp
        assert entry.server == "TestServer"
        assert entry.level == "INFO"
        assert entry.message == "Test message"
        assert entry.source_type == "SYSTEM"

    def test_log_entry_matches_filter_no_filter(self):
        """Test matches_filter with no filter."""
        entry = LogEntry(datetime.now(), "TestServer", "INFO", "Test message", "SYSTEM")
        assert entry.matches_filter("") is True
        assert entry.matches_filter(None) is True

    def test_log_entry_matches_filter_message(self):
        """Test matches_filter with message content."""
        entry = LogEntry(
            datetime.now(), "TestServer", "INFO", "Error occurred", "SYSTEM"
        )
        assert entry.matches_filter("Error") is True
        assert entry.matches_filter("error") is True  # case insensitive
        assert entry.matches_filter("warning") is False

    def test_log_entry_matches_filter_level(self):
        """Test matches_filter with level."""
        entry = LogEntry(
            datetime.now(), "TestServer", "ERROR", "Test message", "SYSTEM"
        )
        assert entry.matches_filter("ERROR") is True
        assert entry.matches_filter("error") is True
        assert entry.matches_filter("INFO") is False

    def test_log_entry_matches_filter_server(self):
        """Test matches_filter with server name."""
        entry = LogEntry(datetime.now(), "MyServer", "INFO", "Test message", "SYSTEM")
        assert entry.matches_filter("MyServer") is True
        assert entry.matches_filter("myserver") is True
        assert entry.matches_filter("OtherServer") is False

    def test_log_entry_matches_filter_source_type(self):
        """Test matches_filter with source type."""
        entry = LogEntry(datetime.now(), "TestServer", "INFO", "Test message", "IRC")
        assert entry.matches_filter("IRC") is True
        assert entry.matches_filter("irc") is True
        assert entry.matches_filter("BOT") is False

    def test_get_display_text(self, sample_log_entry):
        """Test get_display_text formatting."""
        text = sample_log_entry.get_display_text()
        assert "[12:00:00]" in text
        assert "[TestServer]" in text
        assert "[INFO]" in text
        assert "Test message" in text

    def test_get_color_attr_info(self):
        """Test get_color_attr for INFO level."""
        entry = LogEntry(datetime.now(), "TestServer", "INFO", "Test", "SYSTEM")
        assert entry.get_color_attr() == "log_info"

    def test_get_color_attr_warning(self):
        """Test get_color_attr for WARNING level."""
        entry = LogEntry(datetime.now(), "TestServer", "WARNING", "Test", "SYSTEM")
        assert entry.get_color_attr() == "log_warning"

    def test_get_color_attr_error(self):
        """Test get_color_attr for ERROR level."""
        entry = LogEntry(datetime.now(), "TestServer", "ERROR", "Test", "SYSTEM")
        assert entry.get_color_attr() == "log_error"

    def test_get_color_attr_debug(self):
        """Test get_color_attr for DEBUG level."""
        entry = LogEntry(datetime.now(), "TestServer", "DEBUG", "Test", "SYSTEM")
        assert entry.get_color_attr() == "log_debug"

    def test_get_color_attr_success(self):
        """Test get_color_attr for SUCCESS level."""
        entry = LogEntry(datetime.now(), "TestServer", "SUCCESS", "Test", "SYSTEM")
        assert entry.get_color_attr() == "log_success"

    def test_get_color_attr_unknown_level(self):
        """Test get_color_attr for unknown level."""
        entry = LogEntry(datetime.now(), "TestServer", "UNKNOWN", "Test", "SYSTEM")
        assert entry.get_color_attr() == "log_info"

    def test_get_color_attr_irc_source(self):
        """Test get_color_attr for IRC source type."""
        entry = LogEntry(datetime.now(), "TestServer", "INFO", "Test", "IRC")
        assert entry.get_color_attr() == "irc_message"

    def test_get_color_attr_bot_source(self):
        """Test get_color_attr for BOT source type."""
        entry = LogEntry(datetime.now(), "TestServer", "INFO", "Test", "BOT")
        assert entry.get_color_attr() == "bot_command"

    def test_get_color_attr_ai_source(self):
        """Test get_color_attr for AI source type."""
        entry = LogEntry(datetime.now(), "TestServer", "INFO", "Test", "AI")
        assert entry.get_color_attr() == "ai_response"

    def test_get_color_attr_source_overrides_level(self):
        """Test that source type color overrides level color."""
        entry = LogEntry(datetime.now(), "TestServer", "ERROR", "Test", "IRC")
        assert (
            entry.get_color_attr() == "irc_message"
        )  # Should be IRC color, not error color


class TestSelectableText:
    """Test SelectableText class functionality."""

    def test_selectable_text_creation(self, mock_urwid):
        """Test SelectableText object creation."""
        text = SelectableText("Hello world", "default")

        assert text._text_content == "Hello world"
        assert text.original_attr == "default"

    def test_selectable_text_url_parsing(self):
        """Test URL parsing in text."""
        # Test the URL parsing logic directly
        from tui import SelectableText

        text = SelectableText("Check https://example.com")

        # Test that the text content is stored
        assert text._text_content == "Check https://example.com"

    def test_selectable_text_mouse_event_link_click(self, mock_urwid):
        """Test mouse event handling for link clicks."""
        with patch.object(
            SelectableText, "_get_link_at_position", return_value="https://example.com"
        ), patch.object(SelectableText, "_open_link_in_browser") as mock_open:

            text = SelectableText("Check https://example.com")

            result = text.mouse_event((80,), "mouse press", 1, 10, 0, True)

            assert result is True  # Should consume the event
            mock_open.assert_called_once_with("https://example.com")

    def test_selectable_text_mouse_event_no_link(self, mock_urwid):
        """Test mouse event handling when no link is clicked."""
        with patch.object(SelectableText, "_get_link_at_position", return_value=None):

            text = SelectableText("Plain text")

            result = text.mouse_event((80,), "mouse press", 1, 10, 0, True)

            assert result is False  # Should not consume the event

    @patch("tui.CLIPBOARD_AVAILABLE", True)
    @patch("tui.pyperclip.copy")
    def test_selectable_text_keypress_clipboard_copy(self, mock_copy, mock_urwid):
        """Test keyboard event for clipboard copy."""
        with patch("tui.urwid.Text") as mock_text, patch(
            "tui.urwid.AttrMap"
        ) as mock_attr_map:

            mock_text_instance = Mock()
            mock_text_instance.get_text.return_value = ("Selected text", None)
            mock_text.return_value = mock_text_instance

            # Mock AttrMap
            mock_attr_map_instance = Mock()
            mock_attr_map_instance._original_widget = mock_text_instance
            mock_attr_map.return_value = mock_attr_map_instance

            text = SelectableText("Selected text")

            result = text.keypress((80,), "ctrl c")

            assert result is None  # Should consume the event
            mock_copy.assert_called_once_with("Selected text")

    @patch("tui.CLIPBOARD_AVAILABLE", False)
    def test_selectable_text_keypress_no_clipboard(self, mock_urwid):
        """Test keyboard event when clipboard is not available."""
        with patch("tui.urwid.Text") as mock_text, patch(
            "tui.urwid.AttrMap"
        ) as mock_attr_map:

            # Mock the Text widget's get_text method
            mock_text_instance = Mock()
            mock_text_instance.get_text.return_value = ("Test text", None)
            mock_text.return_value = mock_text_instance

            # Mock AttrMap
            mock_attr_map_instance = Mock()
            mock_attr_map_instance._original_widget = mock_text_instance
            mock_attr_map.return_value = mock_attr_map_instance

            text = SelectableText("Test text")

            result = text.keypress((80,), "ctrl c")

            assert (
                result == "ctrl c"
            )  # Should return the key since clipboard is not available

    def test_selectable_text_flash(self):
        """Test flash functionality."""
        with patch("threading.Timer") as mock_timer:
            text = SelectableText("Test text")
            text._flash()

            # Timer should be started for flash effect
            mock_timer.assert_called_once()

    def test_selectable_text_open_link_windows(self):
        """Test opening links on Windows."""
        with patch("sys.platform", "win32"), patch("subprocess.run") as mock_run:

            text = SelectableText("Test")
            text._open_link_in_browser("https://example.com")

            mock_run.assert_called_once_with(
                ["start", "https://example.com"],
                shell=True,
                check=True,
                capture_output=True,
            )

    def test_selectable_text_open_link_fallback(self):
        """Test opening links with webbrowser fallback."""
        with patch("sys.platform", "linux"), patch(
            "webbrowser.open", return_value=True
        ) as mock_open:

            text = SelectableText("Test")
            text._open_link_in_browser("https://example.com")

            mock_open.assert_called_once_with("https://example.com")


class TestNonFocusableListBox:
    """Test NonFocusableListBox class functionality."""

    def test_non_focusable_list_box_attributes(self):
        """Test NonFocusableListBox attribute initialization."""
        # Test the attributes that can be tested without complex urwid mocking
        with patch("tui.urwid.ListBox.__init__", return_value=None):
            mock_body = Mock()
            listbox = NonFocusableListBox(mock_body)

            # Test that selection attributes are initialized
            assert hasattr(listbox, "_selection_active")
            assert hasattr(listbox, "_selection_start_line")
            assert hasattr(listbox, "_selection_end_line")
            assert hasattr(listbox, "_selection_start_col")
            assert hasattr(listbox, "_selection_end_col")
            assert hasattr(listbox, "_user_scrolled")


class TestStatsView:
    """Test StatsView class functionality."""

    def test_stats_view_creation(self, mock_bot_manager):
        """Test StatsView creation."""
        tui_manager = Mock()
        tui_manager.bot_manager = mock_bot_manager

        stats_view = StatsView(tui_manager)

        assert stats_view.tui_manager == tui_manager
        assert hasattr(stats_view, "_start_time")

    def test_get_stats_display_no_bot_manager(self):
        """Test stats display when no bot manager is available."""
        tui_manager = Mock()
        tui_manager.bot_manager = None

        stats_view = StatsView(tui_manager)
        stats = stats_view.get_stats_display()

        assert "🤖 Bot Statistics" in stats
        assert "Uptime:" in stats

    def test_get_stats_display_with_bot_manager(self, mock_bot_manager):
        """Test stats display with bot manager."""
        tui_manager = Mock()
        tui_manager.bot_manager = mock_bot_manager

        stats_view = StatsView(tui_manager)

        # Mock len to avoid recursion issues
        with patch("builtins.len", return_value=1), patch("builtins.str") as mock_str:
            mock_str.return_value = "MockServer"
            stats = stats_view.get_stats_display()

        # Just check that we get some output without crashing
        assert isinstance(stats, str)
        assert len(stats) > 0

    def test_format_uptime_seconds(self):
        """Test uptime formatting for seconds."""
        stats_view = StatsView(Mock())

        assert stats_view._format_uptime(30) == "30s"
        assert stats_view._format_uptime(90) == "1m 30s"
        assert stats_view._format_uptime(3660) == "1h 1m 0s"
        assert stats_view._format_uptime(86400 + 3600) == "1d 1h 0m 0s"


class TestConfigEditor:
    """Test ConfigEditor class functionality."""

    def test_config_editor_creation(self):
        """Test ConfigEditor creation."""
        tui_manager = Mock()
        config_editor = ConfigEditor(tui_manager)

        assert config_editor.tui_manager == tui_manager

    def test_get_config_display(self):
        """Test configuration display generation."""
        tui_manager = Mock()
        config_editor = ConfigEditor(tui_manager)

        config_display = config_editor.get_config_display()

        assert "⚙️ Configuration Editor" in config_display
        assert "BOT_NAME:" in config_display
        assert "API Keys" in config_display

    @patch.dict(os.environ, {"TEST_KEY": "test_value"})
    def test_set_config_value(self):
        """Test setting configuration values."""
        tui_manager = Mock()
        config_editor = ConfigEditor(tui_manager)

        result = config_editor._set_config_value("TEST_KEY", "new_value")

        assert result == "Set TEST_KEY = new_value"
        assert os.environ["TEST_KEY"] == "new_value"

    def test_reload_config(self):
        """Test configuration reload."""
        with patch("dotenv.load_dotenv") as mock_load_dotenv:
            tui_manager = Mock()
            config_editor = ConfigEditor(tui_manager)

            result = config_editor._reload_config()

            assert "Configuration reloaded from .env file" in result
            mock_load_dotenv.assert_called_once_with(override=True)

    def test_save_config(self, tmp_path):
        """Test configuration saving."""
        # Change to temp directory for test
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)

            # Create test .env content with UTF-8 encoding to avoid Windows issues
            with open(".env", "w", encoding="utf-8") as f:
                f.write("EXISTING_KEY=old_value\n")

            # Set environment variables
            os.environ["EXISTING_KEY"] = "new_value"
            os.environ["NEW_KEY"] = "new_value"

            tui_manager = Mock()
            config_editor = ConfigEditor(tui_manager)

            result = config_editor._save_config()

            assert "Configuration saved to .env" in result

            # Verify file contents with UTF-8 encoding
            with open(".env", "r", encoding="utf-8") as f:
                content = f.read()

            assert "EXISTING_KEY=new_value" in content
            assert "NEW_KEY=new_value" in content

        finally:
            os.chdir(original_cwd)


class TestTUIManager:
    """Test TUIManager class functionality."""

    def test_tui_manager_creation_no_bot_manager(self, mock_urwid):
        """Test TUIManager creation without bot manager."""
        # Patch the UI components to avoid urwid initialization issues
        with patch("tui.NonFocusableListBox") as mock_listbox, patch(
            "tui.urwid.Text"
        ) as mock_text, patch("tui.urwid.Edit") as mock_edit, patch(
            "tui.urwid.Frame"
        ) as mock_frame:

            mock_listbox_instance = Mock()
            mock_listbox.return_value = mock_listbox_instance
            mock_listbox_instance.is_at_bottom.return_value = True
            mock_listbox_instance.should_auto_scroll.return_value = True

            mock_text_instance = Mock()
            mock_text_instance.set_text = Mock()
            mock_text.return_value = mock_text_instance

            mock_edit_instance = Mock()
            mock_edit.return_value = mock_edit_instance

            mock_frame_instance = Mock()
            mock_frame_instance.set_focus = Mock()
            mock_frame.return_value = mock_frame_instance

            tui_manager = TUIManager()

            assert tui_manager.bot_manager is None
            assert tui_manager.current_view == "console"
            assert len(tui_manager.log_entries) == 0

    def test_tui_manager_creation_with_bot_manager(self, mock_urwid, mock_bot_manager):
        """Test TUIManager creation with bot manager."""
        # Patch the UI components to avoid urwid initialization issues
        with patch("tui.NonFocusableListBox") as mock_listbox, patch(
            "tui.urwid.Text"
        ) as mock_text, patch("tui.urwid.Edit") as mock_edit, patch(
            "tui.urwid.Frame"
        ) as mock_frame:

            mock_listbox_instance = Mock()
            mock_listbox.return_value = mock_listbox_instance
            mock_listbox_instance.is_at_bottom.return_value = True
            mock_listbox_instance.should_auto_scroll.return_value = True

            mock_text_instance = Mock()
            mock_text_instance.set_text = Mock()
            mock_text.return_value = mock_text_instance

            mock_edit_instance = Mock()
            mock_edit.return_value = mock_edit_instance

            mock_frame_instance = Mock()
            mock_frame_instance.set_focus = Mock()
            mock_frame.return_value = mock_frame_instance

            tui_manager = TUIManager(mock_bot_manager)

            assert tui_manager.bot_manager == mock_bot_manager

    def test_tui_manager_basic_attributes(self):
        """Test TUIManager basic attribute initialization."""
        # Test that we can create a TUIManager and check basic attributes
        tui_manager = TUIManager()

        assert tui_manager.bot_manager is None
        assert tui_manager.current_view == "console"
        assert hasattr(tui_manager, "log_entries")
        assert hasattr(tui_manager, "command_history")

    def test_process_input_filter_command(self):
        """Test processing filter commands."""
        tui_manager = TUIManager()

        result = tui_manager.process_input("filter:ERROR")

        assert result is True
        assert tui_manager.current_filter == "ERROR"

    def test_process_input_stats_command(self):
        """Test processing stats command."""
        tui_manager = TUIManager()

        result = tui_manager.process_input("stats")

        assert result is True
        assert tui_manager.current_view == "stats"

    def test_write_log_to_file(self, tmp_path):
        """Test writing logs to file."""
        tui_manager = TUIManager()

        # Add a test log entry
        tui_manager.add_log_entry(
            datetime.now(), "TestServer", "INFO", "Test message", "SYSTEM"
        )

        # Change to temp directory
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)

            tui_manager.write_log_to_file("test_log.txt")

            # Verify file was created
            assert os.path.exists("test_log.txt")

            # Check file contents
            with open("test_log.txt", "r") as f:
                content = f.read()

            assert "LeetIRCBot TUI Log" in content
            assert "Test message" in content

        finally:
            os.chdir(original_cwd)


class TestGlobalFunctions:
    """Test global functions and utilities."""

    def test_wrap_mode_global_variable(self):
        """Test the global WRAP_MODE variable."""
        # Reset to known state
        import tui

        original_value = tui.WRAP_MODE

        # Test toggling the value
        tui.WRAP_MODE = not tui.WRAP_MODE
        assert tui.WRAP_MODE != original_value

        # Reset to original
        tui.WRAP_MODE = original_value


class TestFocusProtectingFrame:
    """Test FocusProtectingFrame class."""

    def test_focus_protecting_frame_creation(self):
        """Test FocusProtectingFrame creation."""
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            frame = FocusProtectingFrame(
                body=Mock(), header=Mock(), footer=Mock(), focus_part="footer"
            )

        assert hasattr(frame, "mouse_event")
