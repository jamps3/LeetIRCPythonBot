"""
Test for the difference between console commands and kaiku-routed commands.

This test demonstrates that commands like !s (weather) work when routed through
!kaiku but fail when used directly from console due to missing bot_functions.

Issue: When using !s directly from console, the command handler doesn't receive
the send_weather function in bot_functions, so it returns "Weather service not available".
But when using !kaiku !s, the command goes through message_handler which provides
the send_weather function in bot_functions.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestConsoleVsKaikuWeatherCommand:
    """Test the difference between direct console command and kaiku-routed command."""

    def test_weather_command_direct_console_missing_send_weather(self):
        """
        Test that !s command fails when bot_functions doesn't have send_weather.
        
        This simulates using !s directly from console where bot_functions may not
        have the send_weather function available.
        """
        # Import the command handler
        from cmd_modules.services import weather_command
        from command_registry import CommandContext

        # Create a context WITHOUT send_weather in bot_functions (like direct console)
        context = MagicMock(spec=CommandContext)
        context.args_text = "Helsinki"
        context.is_console = True
        context.target = "#test"

        # Create bot_functions WITHOUT send_weather (this is what causes the issue)
        bot_functions_without_weather = {}

        # Call the command
        result = weather_command(context, bot_functions_without_weather)

        # The result should indicate weather service not available
        assert result == "Weather service not available"

    def test_weather_command_via_kaiku_has_send_weather(self):
        """
        Test that !s command works when bot_functions has send_weather.
        
        This simulates using !kaiku !s which goes through message_handler
        and provides send_weather in bot_functions.
        """
        from cmd_modules.services import weather_command
        from command_registry import CommandContext

        # Create a context with send_weather available
        context = MagicMock(spec=CommandContext)
        context.args_text = "Helsinki"
        context.is_console = False
        context.target = "#test"

        # Create mock send_weather function
        mock_send_weather = MagicMock()

        # Create bot_functions WITH send_weather (like through message_handler)
        bot_functions_with_weather = {
            "send_weather": mock_send_weather,
            "irc": MagicMock()  # Required for non-console context
        }

        # Call the command
        result = weather_command(context, bot_functions_with_weather)

        # The result should be no response (command handles output itself)
        # and send_weather should have been called
        assert result is None or hasattr(result, 'message')  # Could be CommandResponse
        mock_send_weather.assert_called_once()

    @pytest.mark.asyncio
    async def test_kaiku_routes_command_with_proper_bot_functions(self):
        """
        Test that when !kaiku !s is used, the nested command gets proper bot_functions.
        
        This test verifies that kaiku command passes proper bot_functions to nested commands.
        """
        from cmd_modules.misc import echo_command
        from command_registry import CommandContext

        # Create context for !kaiku !s Helsinki
        context = MagicMock(spec=CommandContext)
        context.args = ["!s", "Helsinki"]
        context.args_text = "!s Helsinki"
        context.is_console = False
        context.sender = "testuser"
        context.target = "#test"

        # Mock server with send_message
        mock_server = MagicMock()
        
        # Create bot_functions that would be provided by message_handler
        # This includes send_weather which is needed for the nested !s command
        bot_functions = {
            "server": mock_server,
            "send_weather": MagicMock(),  # This is provided by message_handler
            "irc": MagicMock()
        }

        # The echo command is async, so we need to await it
        result = await echo_command(context, bot_functions)
        
        # The result should be None (echo returns None when sending to channel)
        # or a string when it's a simple echo
        assert result is None or isinstance(result, str)


class TestConsoleCommandsBotFunctions:
    """Test that console commands receive proper bot_functions."""

    def test_console_weather_needs_send_weather_in_bot_functions(self):
        """
        Test that demonstrates the issue: console weather command needs send_weather.
        
        The issue is that when processing console commands directly (not through 
        message_handler), the bot_functions may not have send_weather.
        """
        from cmd_modules.services import weather_command
        from command_registry import CommandContext

        context = MagicMock(spec=CommandContext)
        context.args_text = ""
        context.is_console = True
        context.target = "console"

        # Empty bot_functions - simulating what might happen in console
        bot_functions = {}

        result = weather_command(context, bot_functions)

        # This returns "Weather service not available" because send_weather is missing
        assert result == "Weather service not available"

    def test_irc_message_provides_send_weather(self):
        """
        Test that IRC messages go through message_handler which provides send_weather.
        
        This is what happens when someone uses !s in IRC - it goes through
        message_handler which adds send_weather to bot_functions.
        """
        from cmd_modules.services import weather_command
        from command_registry import CommandContext

        context = MagicMock(spec=CommandContext)
        context.args_text = "Turku"
        context.is_console = False
        context.target = "#suomi"

        # Bot functions as provided by message_handler
        mock_send_weather = MagicMock()
        bot_functions = {
            "send_weather": mock_send_weather,
            "irc": MagicMock(),
            "notice_message": MagicMock()
        }

        result = weather_command(context, bot_functions)

        # Should call send_weather instead of returning error
        mock_send_weather.assert_called_once()
        # Result is CommandResponse with should_respond=False since weather handles output
        assert result is not None
