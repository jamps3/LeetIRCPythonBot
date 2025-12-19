#!/usr/bin/env python3
"""
TUI implementation for LeetIRCPythonBot using urwid.
The default interface. Use --console for the simple interface.
"""

import json
import os
import time
from collections import deque
from datetime import datetime

import urwid

import logger

# Try to import clipboard functionality
try:
    import pyperclip

    CLIPBOARD_AVAILABLE = True
except ImportError:
    CLIPBOARD_AVAILABLE = False

# Global wrapping mode for log display (will be loaded from state)
WRAP_MODE = True  # True for wrap, False for clip (default)

# Global reference to current TUI instance
_current_tui = None

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
    ("log_debug", "light gray", "black"),
    ("log_success", "light green", "black"),
    # Message types
    ("irc_message", "light cyan", "black"),
    ("bot_command", "light green", "black"),
    ("ai_response", "light magenta", "black"),
    # Input field
    ("input_normal", "light gray", "black"),
    ("input_command", "light green", "black"),
    ("input_ai", "light magenta", "black"),
    # Links
    ("link", "light blue", "black", "underline"),
    # Text selection
    ("selected", "black", "white"),
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


class NonFocusableListBox(urwid.ListBox):
    """A ListBox that is not focusable but allows mouse interactions and scrolling."""

    def __init__(self, body, *args, **kwargs):
        super().__init__(body, *args, **kwargs)
        self._user_scrolled = False

        # Multi-line text selection state
        self._selection_active = False
        self._selection_start_line = None
        self._selection_end_line = None
        self._selection_start_col = None
        self._selection_end_col = None

    def selectable(self):
        return True  # Allow mouse events to reach child widgets

    def mouse_event(self, size, event, button, col, row, focus):
        """Handle multi-line text selection across the list."""
        # First try to forward to child widgets (for link clicking)
        result = super().mouse_event(size, event, button, col, row, focus)
        if result:
            # Child widget handled the event (e.g., link clicking)
            return True

        # Child didn't handle it, handle selection ourselves
        if event == "mouse press" and button == 1:
            # Start multi-line selection
            self._start_multi_line_selection(row, col)
            return True

        elif event == "mouse drag" and button == 1:
            # Update multi-line selection
            self._update_multi_line_selection(row, col)
            return True

        elif event == "mouse release" and button == 1:
            # End multi-line selection and copy
            self._end_multi_line_selection(row, col)
            return True

        return False

    def _start_multi_line_selection(self, row, col):
        """Start multi-line text selection."""
        # For ListBox, row is the visible row index
        # We need to convert this to the actual walker position
        try:
            # Calculate the scroll offset (top visible item index)
            # The scroll position is the index of the top visible item
            scroll_offset = self._calculate_scroll_offset()
            list_index = scroll_offset + row

            # Ensure bounds
            if 0 <= list_index < len(self.body):
                self._selection_active = True
                self._selection_start_line = list_index
                self._selection_end_line = list_index
                self._selection_start_col = col
                self._selection_end_col = col
                self._update_multi_line_display()
        except (AttributeError, IndexError, TypeError, ValueError):
            # Fallback: assume no scrolling, row = list_index
            if 0 <= row < len(self.body):
                self._selection_active = True
                self._selection_start_line = row
                self._selection_end_line = row
                self._selection_start_col = col
                self._selection_end_col = col
                self._update_multi_line_display()

    def _update_multi_line_selection(self, row, col):
        """Update multi-line text selection during drag."""
        if not self._selection_active:
            return

        try:
            # Calculate the scroll offset (top visible item index)
            scroll_offset = self._calculate_scroll_offset()
            list_index = scroll_offset + row

            # Ensure bounds
            if 0 <= list_index < len(self.body):
                self._selection_end_line = list_index
                self._selection_end_col = col
                self._update_multi_line_display()
        except (AttributeError, IndexError, TypeError, ValueError):
            # Fallback: assume no scrolling, row = list_index
            if 0 <= row < len(self.body):
                self._selection_end_line = list_index
                self._selection_end_col = col
                self._update_multi_line_display()

    def _calculate_scroll_offset(self):
        """Calculate the index of the top visible item (scroll offset)."""
        try:
            total_items = len(self.body)
            focus_pos = self.focus_position
            focus_offset = getattr(self, "focus_position_offset", 0)

            # Method 0: Check if scrolling is actually needed
            # If all items fit in visible area, or very few items, no scroll offset
            try:
                # Estimate visible rows (rough approximation)
                estimated_visible_rows = getattr(self, "_rows_max", 20)
                if total_items <= estimated_visible_rows or total_items <= 5:
                    # All items are visible or very few items - no scrolling
                    return 0
            except (AttributeError, TypeError, ValueError):
                pass

            # Method 1: Use focus_position - focus_position_offset
            offset1 = max(0, focus_pos - focus_offset)

            # Method 2: Check if we're at the bottom and adjust
            # If focus is near the end, and offset is small, we might be at bottom
            if focus_pos >= total_items - 3 and focus_offset <= 2:
                # We're likely at the bottom, estimate visible area
                # Assume typical visible area of 20-30 lines
                estimated_visible_rows = 25  # Conservative estimate
                offset2 = max(0, total_items - estimated_visible_rows)
            else:
                offset2 = offset1

            # Method 3: Use the widget's internal position if available
            try:
                # Try to get position from the walker
                current_pos = self.get_focus()[1]
                if current_pos is not None and current_pos > 10:
                    # If we're deeply scrolled, use a position-based estimate
                    offset3 = max(
                        0, current_pos - 12
                    )  # Assume focused item is 12 rows from top
                else:
                    offset3 = offset2
            except (AttributeError, TypeError, ValueError):
                offset3 = offset2

            # Method 4: Sanity check - if offset would be >= total_items, it's wrong
            final_offset = max(offset1, offset2, offset3)
            if final_offset >= total_items:
                # Offset can't be >= total items, fallback to 0
                final_offset = 0

            return final_offset

        except (AttributeError, TypeError):
            # Fallback: try to estimate from focus position
            try:
                focus_pos = self.focus_position
                # Estimate: assume focused item is roughly in the middle of visible area
                visible_rows = getattr(self, "_rows_max", 10)  # Rough estimate
                return max(0, focus_pos - visible_rows // 2)
            except (AttributeError, TypeError):
                return 0  # No scrolling

    def _end_multi_line_selection(self, row, col):
        """End multi-line text selection and copy to clipboard."""
        if not self._selection_active:
            return

        # Update final position
        self._update_multi_line_selection(row, col)

        # Extract and copy selected text (before clearing selection)
        selected_text = self._extract_multi_line_selected_text()
        if selected_text and CLIPBOARD_AVAILABLE:
            try:
                pyperclip.copy(selected_text)
                # Flash all selected lines
                self._flash_selected_lines()
            except Exception:
                # Log error but don't crash
                pass

        # Clear selection
        self._selection_active = False
        self._selection_start_line = None
        self._selection_end_line = None
        self._selection_start_col = None
        self._selection_end_col = None
        self._update_multi_line_display()

    def _update_multi_line_display(self):
        """Update the visual display of all affected lines."""
        if not self._selection_active:
            # Clear all selections
            for i, item in enumerate(self.body):
                if hasattr(item, "_update_selection_display"):
                    item._selection_start = None
                    item._selection_end = None
                    item._update_selection_display()
            return

        # Determine affected line range
        start_line = min(self._selection_start_line, self._selection_end_line)
        end_line = max(self._selection_start_line, self._selection_end_line)

        # Update each line in the selection
        for i, item in enumerate(self.body):
            if hasattr(item, "_update_selection_display"):
                if start_line <= i <= end_line:
                    # This line is in the selection range
                    if (
                        i == self._selection_start_line
                        and i == self._selection_end_line
                    ):
                        # Single line selection
                        item._selection_start = min(
                            self._selection_start_col, self._selection_end_col
                        )
                        item._selection_end = max(
                            self._selection_start_col, self._selection_end_col
                        )  # noqa: E203
                    elif i == self._selection_start_line:
                        # First line of multi-line selection
                        item._selection_start = self._selection_start_col
                        item._selection_end = len(
                            item._text_content
                        )  # Select to end of line
                    elif i == self._selection_end_line:
                        # Last line of multi-line selection
                        item._selection_start = 0  # Select from start of line
                        item._selection_end = self._selection_end_col
                    else:
                        # Middle line of multi-line selection
                        item._selection_start = 0
                        item._selection_end = len(
                            item._text_content
                        )  # Select entire line

                    item._update_selection_display()
                else:
                    # This line is not in selection
                    item._selection_start = None
                    item._selection_end = None
                    item._update_selection_display()

    def _extract_multi_line_selected_text(self):
        """Extract the selected text across multiple lines (called before clearing selection)."""
        if not self._selection_active:
            return None

        selected_lines = []
        start_line = min(self._selection_start_line, self._selection_end_line)
        end_line = max(self._selection_start_line, self._selection_end_line)
        start_col = min(self._selection_start_col, self._selection_end_col)
        end_col = max(self._selection_start_col, self._selection_end_col)

        for i in range(start_line, end_line + 1):
            if i < len(self.body):
                item = self.body[i]
                if hasattr(item, "_text_content"):
                    line_content = item._text_content

                    if i == start_line and i == end_line:
                        # Single line selection
                        selected_text = line_content[
                            min(start_col, end_col) : max(  # noqa: E203
                                start_col, end_col
                            )
                        ]
                    elif i == start_line:
                        # First line of multi-line selection
                        selected_text = line_content[start_col:]
                    elif i == end_line:
                        # Last line of multi-line selection
                        selected_text = line_content[:end_col]
                    else:
                        # Middle line - entire line
                        selected_text = line_content

                    if selected_text:
                        selected_lines.append(selected_text)

        return "\n".join(selected_lines) if selected_lines else None

    def _get_multi_line_selected_text(self):
        """Get the selected text across multiple lines."""
        if not self._selection_active:
            return None

        selected_lines = []
        start_line = min(self._selection_start_line, self._selection_end_line)
        end_line = max(self._selection_start_line, self._selection_end_line)
        start_col = min(self._selection_start_col, self._selection_end_col)
        end_col = max(self._selection_start_col, self._selection_end_col)

        for i in range(start_line, end_line + 1):
            if i < len(self.body):
                item = self.body[i]
                if hasattr(item, "_text_content"):
                    line_content = item._text_content

                    if i == start_line and i == end_line:
                        # Single line selection
                        selected_text = line_content[
                            min(start_col, end_col) : max(  # noqa: E203
                                start_col, end_col
                            )
                        ]
                    elif i == start_line:
                        # First line of multi-line selection
                        selected_text = line_content[start_col:]
                    elif i == end_line:
                        # Last line of multi-line selection
                        selected_text = line_content[:end_col]
                    else:
                        # Middle line - entire line
                        selected_text = line_content

                    if selected_text:
                        selected_lines.append(selected_text)

        return "\n".join(selected_lines) if selected_lines else None

    def _flash_selected_lines(self):
        """Flash all lines that were selected."""
        if not self._selection_active:
            return

        start_line = min(self._selection_start_line, self._selection_end_line)
        end_line = max(self._selection_start_line, self._selection_end_line)

        for i in range(start_line, end_line + 1):
            if i < len(self.body):
                item = self.body[i]
                if hasattr(item, "_flash"):
                    item._flash()

    def scroll_up_page(self):
        """Scroll up by one page (20 lines) and mark as user scrolled."""
        self._user_scrolled = True
        # Scroll up by changing walker focus position
        if hasattr(self, "body") and len(self.body) > 0:
            try:
                current_focus = self.get_focus()[1]
                if current_focus is not None:
                    new_focus = max(0, current_focus - 20)
                    self.body.set_focus(new_focus)
            except (AttributeError, TypeError):
                # If we can't get current focus, just set to top
                self.body.set_focus(0)

    def scroll_down_page(self):
        """Scroll down by one page (20 lines) and mark as user scrolled."""
        self._user_scrolled = True
        # Scroll down by changing walker focus position
        if hasattr(self, "body") and len(self.body) > 0:
            try:
                current_focus = self.get_focus()[1]
                if current_focus is not None:
                    new_focus = min(len(self.body) - 1, current_focus + 20)
                    self.body.set_focus(new_focus)
            except (AttributeError, TypeError):
                # If we can't get current focus, just set to bottom
                self.body.set_focus(len(self.body) - 1)

    def scroll_up(self):
        """Scroll up by one line and mark as user scrolled."""
        self._user_scrolled = True
        # Scroll up by changing walker focus position
        if hasattr(self, "body") and len(self.body) > 0:
            try:
                current_focus = self.get_focus()[1]
                if current_focus is not None and current_focus > 0:
                    self.body.set_focus(current_focus - 1)
            except (AttributeError, TypeError):
                # If we can't get current focus, just set to top
                self.body.set_focus(0)

    def scroll_down(self):
        """Scroll down by one line and mark as user scrolled."""
        self._user_scrolled = True
        # Scroll down by changing walker focus position
        if hasattr(self, "body") and len(self.body) > 0:
            try:
                current_focus = self.get_focus()[1]
                if current_focus is not None and current_focus < len(self.body) - 1:
                    self.body.set_focus(current_focus + 1)
            except (AttributeError, TypeError):
                # If we can't get current focus, just set to bottom
                self.body.set_focus(len(self.body) - 1)

    def scroll_to_bottom(self):
        """Scroll to the bottom and reset user scroll flag."""
        # Scroll to bottom by setting focus to the last item in the walker
        if hasattr(self, "body") and len(self.body) > 0:
            # Set focus to the last item
            self.body.set_focus(len(self.body) - 1)
        # Reset user scroll flag after scrolling is complete
        self._user_scrolled = False

    def scroll_to_top(self):
        """Scroll to the top and mark as user scrolled."""
        self._user_scrolled = True
        # Scroll to top by setting focus to the first item in the walker
        if hasattr(self, "body") and len(self.body) > 0:
            # Set focus to the first item
            self.body.set_focus(0)

    def is_at_bottom(self):
        """Check if currently at the bottom."""
        if not hasattr(self, "body") or len(self.body) == 0:
            return True
        # Get the current focus position from the body
        try:
            focus_position = self.focus_position
            if focus_position is not None:
                return focus_position >= len(self.body) - 2  # Within 2 lines of bottom
        except (AttributeError, TypeError):
            pass
        return True  # Default to True if we can't determine

    def should_auto_scroll(self):
        """Check if auto-scroll should be enabled."""
        return not self._user_scrolled or self.is_at_bottom()


class SelectableText(urwid.WidgetWrap):
    """Text widget that supports mouse selection and clipboard copying."""

    def __init__(self, text, original_attr=None):
        self._text_content = text  # Store the actual text content
        self.original_attr = original_attr or "default"
        self._flash_handle = None
        self._selection_start = None
        self._selection_end = None
        self._is_flashing = False

        # Parse text for URLs and create markup
        self.markup_text = self._parse_text_with_links(text)

        # Create the underlying Text widget with current wrap mode
        wrap_mode = "any" if WRAP_MODE else "clip"
        self._text_widget = urwid.Text(self.markup_text, wrap=wrap_mode)

        # Wrap in AttrMap for coloring
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            self._attr_map = urwid.AttrMap(self._text_widget, self.original_attr)
            super().__init__(self._attr_map)

    def selectable(self):
        return True

    def keypress(self, size, key):
        if key in ("ctrl c", "ctrl C"):
            text_widget = self._w._original_widget  # Get the Text widget
            text = text_widget.get_text()[0]  # Get the actual text content
            if text and CLIPBOARD_AVAILABLE:
                try:
                    pyperclip.copy(text)
                    return None
                except Exception:
                    pass
        return key

    def mouse_event(self, size, event, button, col, row, focus):
        """Handle mouse events for link clicking and text selection."""
        # Handle link clicking on mouse press
        if event == "mouse press" and button == 1:
            link_url = self._get_link_at_position(size[0], row, col)
            if link_url:
                self._open_link_in_browser(link_url)
                self._flash()  # Flash to indicate click
                return True  # Consume the event

        # For other events, let parent handle text selection
        return False

    def _parse_text_with_links(self, text):
        """Parse text and highlight URLs."""
        import re

        # URL regex pattern
        url_pattern = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"

        # Find all URLs in the text
        urls = re.findall(url_pattern, text)

        if not urls:
            return text

        # Create markup with highlighted links
        markup = []
        remaining_text = text

        for url in urls:
            # Find the URL in remaining text
            url_start = remaining_text.find(url)
            if url_start == -1:
                continue

            # Add text before URL
            if url_start > 0:
                markup.append(remaining_text[:url_start])

            # Add highlighted URL
            markup.append(("link", url))

            # Remove processed text
            remaining_text = remaining_text[url_start + len(url) :]  # noqa: E203

        # Add remaining text
        if remaining_text:
            markup.append(remaining_text)

        return markup if markup else text

    def _visual_to_logical_pos(self, text, maxcol, visual_row, visual_col):
        """Convert visual (row, col) coordinates to logical character position in text."""
        if visual_row == 0 and visual_col < len(text):
            return visual_col

        lines = []
        remaining = text
        while remaining:
            if len(remaining) <= maxcol:
                lines.append(remaining)
                break
            # Find last space before maxcol for word wrapping
            cut = remaining.rfind(" ", 0, maxcol + 1)
            if cut == -1 or cut == 0:
                # No space found or space at beginning, cut at maxcol
                cut = maxcol
            lines.append(remaining[:cut])
            remaining = remaining[cut:].lstrip()

        if visual_row >= len(lines):
            return len(text)

        line = lines[visual_row]
        if visual_col >= len(line):
            # Position beyond line end
            char_pos = sum(
                len(l) + (1 if i < visual_row else 0)
                for i, l in enumerate(lines[: visual_row + 1])
            )
            return min(char_pos, len(text))

        # Count characters up to this visual position
        char_pos = 0
        for i in range(visual_row):
            # Add the length of previous lines plus the space that was stripped
            prev_line = lines[i]
            char_pos += len(prev_line)
            if i < visual_row - 1:  # Add space that was stripped between lines
                char_pos += 1

        char_pos += visual_col
        return min(char_pos, len(text))

    def _get_link_at_position(self, maxcol, visual_row, visual_col):
        """Get the URL at the given visual position."""
        # Get the plain text
        text_widget = self._w._original_widget
        plain_text = text_widget.get_text()[0]

        # Convert visual position to logical position
        logical_pos = self._visual_to_logical_pos(
            plain_text, maxcol, visual_row, visual_col
        )

        # Find URL at this position
        import re

        url_pattern = r"http[s]?://[^\s]+"
        for match in re.finditer(url_pattern, plain_text):
            if match.start() <= logical_pos < match.end():
                return match.group()

        return None

    def _get_selected_text(self):
        """Get the currently selected text."""
        if self._selection_start is None or self._selection_end is None:
            return None

        # Get the markup and plain text
        text_widget = self._w._original_widget  # Get the Text widget
        # markup = text_widget.get_text()[1]  # Get the markup
        plain_text = text_widget.get_text()[0]  # Get the plain text

        # For selection, we need to find the text between the start and end screen positions
        # Since markup can affect positioning, we'll use a simpler approach:
        # Just extract based on screen positions, assuming the markup doesn't change character positions
        start_col = min(self._selection_start, self._selection_end)
        end_col = max(self._selection_start, self._selection_end)

        # Ensure bounds
        start_col = max(0, min(start_col, len(plain_text)))
        end_col = max(0, min(end_col, len(plain_text)))

        return plain_text[start_col:end_col]

    def _update_selection_display(self):
        """Update the visual display to show selected text."""
        if self._selection_start is None or self._selection_end is None:
            # No selection, restore original markup
            self._text_widget.set_text(self.markup_text)
            return

        # Get the plain text
        plain_text = self._text_content

        # Calculate selection bounds
        start_col = min(self._selection_start, self._selection_end)
        end_col = max(self._selection_start, self._selection_end)

        # Ensure bounds
        start_col = max(0, min(start_col, len(plain_text)))
        end_col = max(0, min(end_col, len(plain_text)))

        if start_col >= end_col:
            # Invalid selection, restore original
            self._text_widget.set_text(self.markup_text)
            return

        # Create new markup with selection highlighting
        new_markup = []
        current_pos = 0

        # Process original markup and insert selection highlights
        for item in self.markup_text:
            if isinstance(item, tuple):
                # This is a markup tuple (attr, text)
                attr, text = item
                text_len = len(text)

                # Check if this text segment overlaps with selection
                segment_start = current_pos
                segment_end = current_pos + text_len

                # Find overlap between segment and selection
                overlap_start = max(segment_start, start_col)
                overlap_end = min(segment_end, end_col)

                if overlap_start < overlap_end:
                    # There is overlap - split the text
                    # Text before selection
                    if segment_start < overlap_start:
                        before_text = text[: overlap_start - segment_start]
                        if before_text:
                            new_markup.append((attr, before_text))

                    # Selected text
                    selected_text = text[
                        overlap_start
                        - segment_start : overlap_end  # noqa: E203
                        - segment_start
                    ]
                    if selected_text:
                        # Use the more specific attribute if it exists, otherwise combine
                        if attr:
                            new_markup.append(("selected", selected_text))
                        else:
                            new_markup.append(("selected", selected_text))

                    # Text after selection
                    if overlap_end < segment_end:
                        after_text = text[overlap_end - segment_start :]  # noqa: E203
                        if after_text:
                            new_markup.append((attr, after_text))
                else:
                    # No overlap, use original
                    new_markup.append(item)

                current_pos += text_len
            else:
                # This is plain text
                text = item
                text_len = len(text)

                # Check if this text segment overlaps with selection
                segment_start = current_pos
                segment_end = current_pos + text_len

                # Find overlap between segment and selection
                overlap_start = max(segment_start, start_col)
                overlap_end = min(segment_end, end_col)

                if overlap_start < overlap_end:
                    # There is overlap - split the text
                    # Text before selection
                    if segment_start < overlap_start:
                        before_text = text[: overlap_start - segment_start]
                        if before_text:
                            new_markup.append(before_text)

                    # Selected text
                    selected_text = text[
                        overlap_start
                        - segment_start : overlap_end  # noqa: E203
                        - segment_start
                    ]
                    if selected_text:
                        new_markup.append(("selected", selected_text))

                    # Text after selection
                    if overlap_end < segment_end:
                        after_text = text[overlap_end - segment_start :]  # noqa: E203
                        if after_text:
                            new_markup.append(after_text)
                else:
                    # No overlap, use original
                    new_markup.append(item)

                current_pos += text_len

        # Update the text widget with the new markup
        self._text_widget.set_text(new_markup)

    def _open_link_in_browser(self, url):
        """Open URL in default browser."""
        import subprocess
        import sys
        import webbrowser

        # Log the attempt to open URL
        import logger

        log = logger.get_logger("TUI")
        log.info(f"Trying to open URL: {url}")

        try:
            # Try different methods based on platform
            if sys.platform == "win32":
                # Windows: try start command first
                try:
                    subprocess.run(
                        ["start", url], shell=True, check=True, capture_output=True
                    )
                    log.info(f"Successfully opened URL with start command: {url}")
                    return
                except subprocess.CalledProcessError as e:
                    log.warning(f"Start command failed: {e}, trying webbrowser")

            # Fallback to webbrowser
            result = webbrowser.open(url)
            log.info(f"webbrowser.open returned: {result} for URL: {url}")

        except Exception as e:
            log.error(f"Error opening browser for URL {url}: {e}")
            # Could show error to user, but for now just ignore

    def _flash(self):
        """Flash the line briefly to indicate it was copied or clicked."""
        if self._is_flashing:
            return  # Already flashing

        self._is_flashing = True

        # Get the AttrMap and change its attribute
        attr_map = self._w  # The wrapped AttrMap
        attr_map.set_attr_map({None: "flash"})

        # Set a timer to restore original color
        import threading

        def restore_color():
            attr_map.set_attr_map({None: self.original_attr})
            self._is_flashing = False

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


class FocusProtectingFrame(urwid.Frame):
    """A Frame that prevents focus changes when clicking on the body area."""

    def mouse_event(self, size, event, button, col, row, focus):
        """Override mouse_event to prevent focus changes on body clicks."""
        # Get the layout of the Frame
        head_size = self.header.rows((size[0],)) if self.header else 0
        foot_size = self.footer.rows((size[0],)) if self.footer else 0

        # Check if the mouse event is in the header
        if row < head_size:
            # Header area - let parent handle
            return super().mouse_event(size, event, button, col, row, focus)

        # Check if the mouse event is in the footer (input field)
        elif row >= size[1] - foot_size:
            # Input field area - let parent handle (this will focus footer)
            return super().mouse_event(size, event, button, col, row, focus)

        # Mouse event is in the body area
        else:
            # Calculate the relative position within the body
            body_row = row - head_size

            # Let the body handle the mouse event WITHOUT changing focus
            if self.body and hasattr(self.body, "mouse_event"):
                body_result = self.body.mouse_event(
                    (size[0], size[1] - head_size - foot_size),
                    event,
                    button,
                    col,
                    body_row,
                    focus,
                )
                # Always keep focus on footer
                if self.focus_part != "footer":
                    self.set_focus("footer")
                return body_result

        return False


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

        # Initialize log file for immediate writing
        self.log_file = None
        self._open_log_file()

        # UI components
        self.header = urwid.Text("")
        self.log_walker = urwid.SimpleListWalker([])
        self.log_display = NonFocusableListBox(self.log_walker)
        self.input_field = urwid.Edit("> Enter message (! for bot, - for AI): ")

        # Additional views
        self.stats_view = StatsView(self)
        self.config_editor = ConfigEditor(self)

        # Set global reference
        global _current_tui
        _current_tui = self

        # Set up layout
        self.setup_layout()

        # Load wrap mode from state.json (after UI is initialized)
        self._load_wrap_mode()

        # Update header initially
        self.update_header()

    def setup_layout(self):
        """Set up the main TUI layout."""
        # Header with status information
        header = urwid.AttrMap(self.header, "header")

        # Footer with input
        footer = urwid.AttrMap(self.input_field, "footer")

        # Main layout - use FocusProtectingFrame to prevent focus changes on body clicks
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            self.main_layout = FocusProtectingFrame(
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
            f"LeetIRCBot TUI | {current_time} | {server_status} | {service_status} | "
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

        # Write to log file immediately
        self._write_log_entry_to_file(entry)

        # Check if entry matches current filter
        if entry.matches_filter(self.current_filter):
            # Check if we were at the bottom before adding the new item
            was_at_bottom = self.log_display.is_at_bottom()

            # Create selectable text widget with mouse support
            color_attr = entry.get_color_attr()
            selectable_text = SelectableText(entry.get_display_text(), color_attr)
            self.log_walker.append(selectable_text)

            # Auto-scroll to bottom only if we were previously at bottom or auto-scroll is enabled
            if was_at_bottom or self.log_display.should_auto_scroll():
                self.log_display.scroll_to_bottom()

    def apply_filter(self, filter_text: str):
        """Apply a filter to the log display."""
        self.current_filter = filter_text

        # Rebuild the display with filtered entries
        self.log_walker.clear()

        for entry in self.log_entries:
            if entry.matches_filter(filter_text):
                # Create selectable text widget with mouse support
                color_attr = entry.get_color_attr()
                selectable_text = SelectableText(entry.get_display_text(), color_attr)
                self.log_walker.append(selectable_text)

        # Auto-scroll to bottom after filtering
        self.log_display.scroll_to_bottom()

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
        elif text.startswith("#"):
            # Channel select command - handle locally instead of going through command_loader
            try:
                channel_name = text[1:].strip()
                if channel_name:
                    result = self.bot_manager._console_select_channel(channel_name)
                    self.add_log_entry(
                        datetime.now(), "Console", "INFO", result, "SYSTEM"
                    )
                else:
                    result = self.bot_manager._get_channel_status()
                    self.add_log_entry(
                        datetime.now(), "Console", "INFO", result, "SYSTEM"
                    )
                return True
            except Exception as e:
                self.add_log_entry(
                    datetime.now(),
                    "Console",
                    "ERROR",
                    f"Channel command error: {e}",
                    "SYSTEM",
                )
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

    def mouse_event(self, size, event, button, col, row, focus):
        """Handle mouse events - route them to the appropriate child widget."""
        self.add_log_entry(
            datetime.now(),
            "DEBUG",
            f"Mouse event: event={event}, button={button}, col={col}, row={row}, focus={focus}",
            "SYSTEM",
        )
        # Get the layout of the Frame
        head_size = self.header.rows((size[0],))
        foot_size = self.input_field.rows((size[0],))

        # Check if the mouse event is in the header
        if row < head_size:
            # Header area - no special handling
            return False

        # Check if the mouse event is in the footer (input field)
        elif row >= size[1] - foot_size:
            # Input field area - let it handle the event
            return self.input_field.mouse_event(
                (size[0], foot_size),
                event,
                button,
                col,
                row - (size[1] - foot_size),
                focus,
            )

        # Mouse event is in the body (log display) area
        else:
            # Calculate the relative position within the body
            body_row = row - head_size

            # Debug: Log scroll state on mouse press
            if event == "mouse press" and button == 1:
                try:
                    focus_pos = self.log_display.focus_position
                    focus_offset = getattr(
                        self.log_display, "focus_position_offset", "N/A"
                    )
                    scroll_offset = self.log_display._calculate_scroll_offset()
                    total_items = len(self.log_display.body)
                    self.add_log_entry(
                        datetime.now(),
                        "DEBUG",
                        f"Mouse press: row={body_row}, focus_pos={focus_pos}, focus_offset={focus_offset}, "
                        f"scroll_offset={scroll_offset}, total_items={total_items}",
                        "SYSTEM",
                    )
                except Exception as e:
                    self.add_log_entry(
                        datetime.now(), "ERROR", f"Debug error: {e}", "SYSTEM"
                    )

            # Let the log display handle the mouse event
            result = self.log_display.mouse_event(
                (size[0], size[1] - head_size - foot_size),
                event,
                button,
                col,
                body_row,
                focus,
            )
            # Ensure focus stays on the input field
            self.main_layout.set_focus("footer")
            return result

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
                command = self.command_history[self.history_index]
                self.input_field.set_edit_text(command)
                self.input_field.set_edit_pos(len(command))  # Move cursor to end
                self.update_input_style()

        elif key == "down":
            # Command history down
            if (
                self.command_history
                and self.history_index < len(self.command_history) - 1
            ):
                self.history_index += 1
                command = self.command_history[self.history_index]
                self.input_field.set_edit_text(command)
                self.input_field.set_edit_pos(len(command))  # Move cursor to end
                self.update_input_style()
            elif self.history_index >= len(self.command_history) - 1:
                self.input_field.set_edit_text("")
                self.input_field.set_edit_pos(0)
                self.history_index = len(self.command_history)
                self.update_input_style()

        elif key == "esc":
            # Clear input
            self.input_field.set_edit_text("")
            self.history_index = len(self.command_history)
            self.update_input_style()

        elif key in ("f1", "ctrl f1"):
            # Show help
            self.show_help()

        elif key in ("f2", "ctrl f2"):
            # Switch to console view
            self.switch_view("console")

        elif key in ("f3", "ctrl f3"):
            # Switch to stats view
            self.switch_view("stats")

        elif key in ("f4", "ctrl f4"):
            # Switch to config view
            self.switch_view("config")

        elif key == "page up":
            # Scroll log display up by one page
            self.log_display.scroll_up_page()

        elif key == "page down":
            # Scroll log display down by one page
            self.log_display.scroll_down_page()

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

                # Scroll to top for stats view
                self.log_display.scroll_to_top()

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

                # Scroll to top for config view
                self.log_display.scroll_to_top()

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

    def _load_wrap_mode(self):
        """Load text wrapping mode from state.json."""
        global WRAP_MODE
        try:
            state_file = os.path.join("data", "state.json")
            if os.path.exists(state_file):
                with open(state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Check for TUI settings in state.json
                tui_settings = data.get("tui", {})
                default_wrap_mode = False
                if "wrap_mode" not in tui_settings:
                    # Set default if not present
                    tui_settings["wrap_mode"] = default_wrap_mode
                    data["tui"] = tui_settings
                    # Update last_updated timestamp
                    data["last_updated"] = datetime.now().isoformat()
                    with open(state_file, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)

                WRAP_MODE = bool(tui_settings.get("wrap_mode", default_wrap_mode))
                self.add_log_entry(
                    datetime.now(),
                    "Console",
                    "INFO",
                    f"Loaded wrap mode from state.json: {'wrapped' if WRAP_MODE else 'clipped'}",
                    "SYSTEM",
                )
        except Exception as e:
            # If loading fails, keep default and log warning
            self.add_log_entry(
                datetime.now(),
                "Console",
                "WARNING",
                f"Failed to load wrap mode from state.json: {e}",
                "SYSTEM",
            )

    def _save_wrap_mode(self):
        """Save text wrapping mode to state.json."""
        try:
            state_file = os.path.join("data", "state.json")

            # Load existing state
            data = {}
            if os.path.exists(state_file):
                with open(state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

            # Update TUI settings
            if "tui" not in data:
                data["tui"] = {}
            data["tui"]["wrap_mode"] = WRAP_MODE

            # Update last_updated timestamp
            data["last_updated"] = datetime.now().isoformat()

            # Save state
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            self.add_log_entry(
                datetime.now(),
                "Console",
                "ERROR",
                f"Failed to save wrap mode to state.json: {e}",
                "SYSTEM",
            )

    def toggle_wrap(self):
        """Toggle text wrapping mode and rebuild the display."""
        global WRAP_MODE
        WRAP_MODE = not WRAP_MODE

        # Save the new wrap mode to state.json
        self._save_wrap_mode()

        # Rebuild the current view with new wrap mode
        if self.current_view == "console":
            self.apply_filter(self.current_filter)  # This rebuilds the log display
        elif self.current_view == "stats":
            # Refresh stats display
            stats_text = self.stats_view.get_stats_display()
            self.log_walker.clear()
            for line in stats_text.split("\n"):
                text_widget = urwid.Text(line)
                self.log_walker.append(text_widget)
            self.log_display.scroll_to_top()
        elif self.current_view == "config":
            # Refresh config display
            config_text = self.config_editor.get_config_display()
            self.log_walker.clear()
            for line in config_text.split("\n"):
                text_widget = urwid.Text(line)
                self.log_walker.append(text_widget)
            self.log_display.scroll_to_top()

        # Log the change
        mode_str = "wrapped" if WRAP_MODE else "clipped"
        self.add_log_entry(
            datetime.now(),
            "Console",
            "INFO",
            f"Text wrapping toggled to: {mode_str}",
            "SYSTEM",
        )

    def _get_timestamp_string(self):
        """Get formatted timestamp string in Finnish format [ke@vko49_12:58:53]."""
        now = datetime.now()

        # Finnish day abbreviations
        days_fi = {
            0: "ma",  # Monday
            1: "ti",  # Tuesday
            2: "ke",  # Wednesday
            3: "to",  # Thursday
            4: "pe",  # Friday
            5: "la",  # Saturday
            6: "su",  # Sunday
        }

        # Get ISO week number
        week_num = now.isocalendar()[1]

        # Format: [day@vko{week}_{HH:MM:SS}]
        return f"[{days_fi[now.weekday()]}@vko{week_num}_{now.strftime('%H:%M:%S')}]"

    def update_input_style(self):
        """Update input field caption based on current text."""
        timestamp = self._get_timestamp_string()
        text = self.input_field.get_edit_text()
        if text.startswith("!"):
            self.input_field.set_caption(f"{timestamp} > [CMD   ]: ")
        elif text.startswith("-"):
            self.input_field.set_caption(f"{timestamp} > [AI    ]: ")
        elif text.lower().startswith("filter:"):
            self.input_field.set_caption(f"{timestamp} > [Filter]: ")
        elif text.lower().startswith("config:"):
            self.input_field.set_caption(f"{timestamp} > [Config]: ")
        else:
            # Show active channel name instead of generic [MSG]
            active_channel = "[No Channel]"
            if (
                self.bot_manager
                and hasattr(self.bot_manager, "active_channel")
                and self.bot_manager.active_channel
            ):
                active_channel = self.bot_manager.active_channel
            self.input_field.set_caption(f"{timestamp} > [{active_channel}]: ")

    def _open_log_file(self, filename="tui.log"):
        """Open the log file for immediate writing."""
        try:
            self.log_file = open(filename, "a", encoding="utf-8")
            # Write header if file is new or empty
            self.log_file.seek(0, 2)  # Seek to end
            if self.log_file.tell() == 0:  # File is empty
                self.log_file.write("=" * 80 + "\n")
                self.log_file.write("LeetIRCBot TUI Log\n")
                self.log_file.write(
                    f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                )
                self.log_file.write("=" * 80 + "\n\n")
            self.log_file.flush()
        except Exception as e:
            # Try to log the error, but don't fail if we can't
            try:
                logger.get_logger("TUI").error(f"Failed to open TUI log file: {e}")
            except Exception:
                pass  # Ignore if logger is unavailable
            self.log_file = None

    def _write_log_entry_to_file(self, entry: LogEntry):
        """Write a single log entry to the file immediately."""
        if self.log_file is None:
            return

        try:
            # Write each log entry in a compact single-line format
            timestamp_str = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            self.log_file.write(
                f"[{timestamp_str}] [{entry.server}] [{entry.level}] {entry.message}\n"
            )
            self.log_file.flush()  # Ensure it's written immediately
        except Exception as e:
            # Try to log the error, but don't fail if we can't
            try:
                logger.get_logger("TUI").error(
                    f"Failed to write log entry to file: {e}"
                )
            except Exception:
                pass  # Ignore if logger is unavailable

    def _close_log_file(self):
        """Close the log file."""
        if self.log_file is not None:
            try:
                self.log_file.close()
                self.log_file = None
            except Exception as e:
                # Try to log the error, but don't fail if we can't
                try:
                    logger.get_logger("TUI").error(f"Failed to close TUI log file: {e}")
                except Exception:
                    pass  # Ignore if logger is unavailable

    def write_log_to_file(self, filename="tui.log"):
        """Write all log entries to a file.

        Args:
            filename: The filename to write the log to (default: tui.log)
        """
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write("=" * 80 + "\n")
                f.write("LeetIRCBot TUI Log\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total Entries: {len(self.log_entries)}\n")
                f.write("=" * 80 + "\n\n")

                for entry in self.log_entries:
                    # Write each log entry in a compact single-line format
                    timestamp_str = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    f.write(
                        f"[{timestamp_str}] [{entry.server}] [{entry.level}] {entry.message}\n"
                    )

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
  F1, Ctrl+F1     - Show this help
  F2, Ctrl+F2     - Console view
  F3, Ctrl+F3     - Statistics view
  F4, Ctrl+F4     - Configuration editor
  Up/Down         - Navigate command history
  PageUp/PageDown - Scroll log display
  Enter           - Send message/command
  Escape          - Clear input field

Tips:
  - Use 'filter:ERROR' to show only error messages
  - Use 'filter:' to clear all filters
  - Command history remembers your previous inputs
  - Commands run asynchronously - you can type while commands process
  - Statistics view shows real-time bot performance
  - Config editor allows runtime configuration changes
  - Mouse selection: Click and drag to select text, releases to copy to clipboard
  - PageUp/PageDown scroll the log display (works from input field)
        """

        self.add_log_entry(datetime.now(), "Console", "INFO", help_text, "SYSTEM")

    def run(self):
        """Run the TUI main loop."""
        # Set up logger hook to receive all log messages immediately
        logger.set_tui_hook(self.add_log_entry)

        # Add initial log entries
        self.add_log_entry(
            datetime.now(),
            "Console",
            "INFO",
            "TUI starting up - capturing all logs from now on.",
            "SYSTEM",
        )

        # Show clipboard status
        clipboard_status = (
            "Select-to-copy functionality enabled - select text with mouse to copy it"
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

            # Report connection status (auto-connect is handled by bot manager)
            auto_connect_enabled = os.getenv("AUTO_CONNECT", "false").lower() == "true"
            if auto_connect_enabled:
                self.add_log_entry(
                    datetime.now(),
                    "Console",
                    "INFO",
                    "AUTO_CONNECT is enabled. Servers should connect automatically.",
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

            # Generate dynamic command list for TUI
            try:
                # Import command modules to ensure they're loaded
                import commands  # noqa: F401
                import commands_admin  # noqa: F401
                import commands_irc  # noqa: F401
                from command_registry import CommandScope as _CS
                from command_registry import get_command_registry

                registry = get_command_registry()
                infos = registry.get_commands_info(
                    scope=_CS.CONSOLE_ONLY
                ) + registry.get_commands_info(scope=_CS.BOTH)

                # Use a set to avoid duplicates
                command_names_set = set()
                for info in infos:
                    if info.name == "help":
                        continue  # exclude help itself
                    name = "!" + info.name  # Add ! prefix for console commands
                    if info.admin_only:
                        name += "*"
                    command_names_set.add(name)

                # Convert to sorted list
                command_names = sorted(command_names_set)

                # Join into one line
                available_commands = "Available commands: " + ", ".join(command_names)
            except Exception:
                # Fallback to static list if registry not available
                available_commands = "Available commands: !help, !connect, !status, !exit, !quit, !join, !part, !msg, !notice, !nick..."

            self.add_log_entry(
                datetime.now(),
                "Console",
                "INFO",
                available_commands,
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

        # Brief pause to allow initial setup to complete
        time.sleep(0.5)

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
                self.update_input_style()  # Update timestamp in input field

                # Auto-refresh current view if it's stats or config
                if self.current_view == "stats":
                    # Refresh stats display
                    stats_text = self.stats_view.get_stats_display()
                    self.log_walker.clear()
                    for line in stats_text.split("\n"):
                        text_widget = urwid.Text(line)
                        self.log_walker.append(text_widget)

                    # Scroll to top for refreshed stats view
                    self.log_display.scroll_to_top()

                elif self.current_view == "config":
                    # Refresh config display
                    config_text = self.config_editor.get_config_display()
                    self.log_walker.clear()
                    for line in config_text.split("\n"):
                        text_widget = urwid.Text(line)
                        self.log_walker.append(text_widget)

                    # Scroll to top for refreshed config view
                    self.log_display.scroll_to_top()

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
            # Close the log file
            self._close_log_file()
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
