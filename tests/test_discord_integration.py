import inspect
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import discord_bot
from command_registry import (
    CommandContext,
    CommandInfo,
    CommandResponse,
    CommandScope,
    FunctionCommandHandler,
)
from discord_bot import CORE_COMMANDS, DiscordBot, get_discord_command_map
from services.community_state_service import CommunityStateService
from state_migrations import migrate_state_data


def test_discord_migration_initializes_configuration_and_poll_state():
    data = migrate_state_data({})

    assert data["config"]["discord"]["enabled"] is False
    assert data["config"]["discord"]["allowed_channels"] == []
    assert data["state"]["discord_polls"] == {}


def test_discord_migration_splits_comma_separated_ids():
    data = migrate_state_data(
        {"config": {"discord": {"allowed_channels": ["123, 456"]}}}
    )

    assert data["config"]["discord"]["allowed_channels"] == ["123", "456"]


def test_discord_context_rejects_irc_scoped_command():
    handler = FunctionCommandHandler(
        CommandInfo(name="irc", scope=CommandScope.IRC_AND_CONSOLE),
        lambda context, functions: "never",
    )
    context = CommandContext(
        command="irc", args=[], raw_message="!irc", platform="discord"
    )

    allowed, message = handler.can_execute(context)

    assert allowed is False
    assert "Discord" in message


def test_discord_native_poll_state_is_channel_specific(tmp_path):
    service = CommunityStateService(str(tmp_path / "state.json"))
    service.save_discord_poll(
        "discord:1", "#10", "100", "Lunch?", ["pizza", "sushi"], "42", [2, 1]
    )

    poll = service.get_discord_poll("discord:1", "#10", "100")

    assert poll["results"] == [2, 1]
    assert service.get_discord_poll("discord:1", "#11", "100") is None
    assert service.get_discord_poll("discord:2", "#10", "100") is None


def test_discord_seen_uses_stable_user_identity(tmp_path):
    service = CommunityStateService(str(tmp_path / "state.json"))
    service.record_seen("discord:1", "#10", "Renamed User", "hello", identity="42")

    seen = service.get_seen("discord:1", "#10", "42")

    assert seen["nick"] == "Renamed User"
    assert seen["identity"] == "42"


def test_discord_allowlist_and_admin_ids_do_not_depend_on_discord_library():
    settings = {
        "enabled": True,
        "allowed_channels": ["123"],
        "admin_user_ids": ["9"],
        "admin_role_ids": ["7"],
    }
    bot = DiscordBot(SimpleNamespace(), settings)
    interaction = SimpleNamespace(
        user=SimpleNamespace(id=9, roles=[]),
        guild=SimpleNamespace(id=1),
        channel=SimpleNamespace(id=123),
    )

    assert bot._allowed_interaction(interaction) is True
    assert bot.is_admin(interaction) is True


def test_discord_allowlist_splits_legacy_comma_separated_entries():
    bot = DiscordBot(
        SimpleNamespace(),
        {"enabled": True, "allowed_channels": ["123, 456"]},
    )

    assert bot._allowed_channel(123) is True
    assert bot._allowed_channel(456) is True


def test_discord_core_commands_include_community_feature_alias():
    assert CORE_COMMANDS["features"] == "feature"


def test_discord_command_map_covers_every_supported_registry_command():
    from command_loader import ensure_commands_loaded
    from command_registry import get_command_registry

    ensure_commands_loaded()
    registry = get_command_registry()
    commands = get_discord_command_map()
    expected = {
        name
        for name, handler in registry._commands.items()
        if handler.info.supports_discord
        and name not in {"ask", "poll", "seen", "status"}
    }

    assert expected <= commands.keys()
    assert commands["weather"] == "s"
    assert commands["roll"] == "noppa"
    assert "raw" not in commands
    assert "join" not in commands
    assert "connect" not in commands
    assert "time" not in commands


def test_discord_capability_metadata_can_disable_a_shared_command():
    handler = FunctionCommandHandler(
        CommandInfo(name="shared", discord_available=False),
        lambda context, functions: "never",
    )
    context = CommandContext(
        command="shared", args=[], raw_message="!shared", platform="discord"
    )

    allowed, message = handler.can_execute(context)

    assert allowed is False
    assert message == "This command is not available on Discord"


def test_discord_help_excludes_irc_and_console_only_commands():
    from cmd_modules.basic import help_command
    from command_loader import ensure_commands_loaded

    ensure_commands_loaded()
    context = CommandContext(
        command="help",
        args=[],
        raw_message="!help",
        sender="User",
        target="#10",
        platform="discord",
    )

    response = help_command(context, {})

    assert "about" in response.message
    assert "raw" not in response.message
    assert "join" not in response.message


def test_discord_generated_callback_has_only_typed_slash_arguments():
    bot = DiscordBot(SimpleNamespace(), {})

    callback = bot._make_command_callback("weather")
    parameters = inspect.signature(callback).parameters

    assert list(parameters) == ["interaction", "arguments"]
    assert parameters["arguments"].annotation == "str"


def test_discord_registers_seen_member_command_without_global_discord_import():
    discord = pytest.importorskip("discord")
    from discord import app_commands

    bot = DiscordBot(SimpleNamespace(), {})
    bot.client = discord.Client(intents=discord.Intents.default())
    bot.tree = app_commands.CommandTree(bot.client)

    bot._register_commands(discord, app_commands)

    seen = bot.tree.get_command("seen")
    assert seen is not None
    assert seen.parameters[0].type is discord.AppCommandOptionType.user
    registered_names = {command.name for command in bot.tree.get_commands()}
    assert set(get_discord_command_map()) <= registered_names
    assert "raw" not in registered_names
    assert "join" not in registered_names


def test_discord_status_distinguishes_dm_and_allowed_guild_channel():
    bot = DiscordBot(SimpleNamespace(), {"enabled": True, "allowed_channels": ["2"]})
    dm = SimpleNamespace(guild=None)
    guild = SimpleNamespace(guild=SimpleNamespace(id=1), channel=SimpleNamespace(id=2))

    assert (
        bot._status_message(dm)
        == "Discord status: online. DMs support slash commands only."
    )
    assert "Guild 1, channel 2 is enabled." in bot._status_message(guild)


def test_discord_stop_skips_a_closed_event_loop():
    class ClosedLoop:
        def is_closed(self):
            return True

        def is_running(self):
            return False

    class Client:
        def is_closed(self):
            return False

        async def close(self):
            raise AssertionError("A closed loop must not receive a close coroutine")

    bot = DiscordBot(SimpleNamespace(), {})
    bot.loop = ClosedLoop()
    bot.client = Client()

    bot.stop()

    assert bot.connected is False


def test_discord_start_requires_enabled_setting_and_token(monkeypatch):
    bot = DiscordBot(SimpleNamespace(), {"enabled": True})
    warning = Mock()
    monkeypatch.setattr(bot.logger, "warning", warning)

    assert bot.start() is False
    warning.assert_called_once_with("Discord is enabled but DISCORD_TOKEN is not set")

    disabled = DiscordBot(SimpleNamespace(), {"enabled": False})
    assert disabled.start() is False


@pytest.mark.asyncio
async def test_discord_send_fetches_channel_and_limits_message_length():
    channel = SimpleNamespace(send=AsyncMock())
    client = SimpleNamespace(
        get_channel=Mock(return_value=None),
        fetch_channel=AsyncMock(return_value=channel),
    )
    bot = DiscordBot(SimpleNamespace(), {})
    bot.client = client

    await bot._send("#10", "x" * 2001)

    client.get_channel.assert_called_once_with(10)
    client.fetch_channel.assert_awaited_once_with(10)
    channel.send.assert_awaited_once_with("x" * 2000, allowed_mentions=None)


def test_discord_stop_closes_active_client_on_its_loop(monkeypatch):
    client = SimpleNamespace(is_closed=Mock(return_value=False), close=AsyncMock())

    class Loop:
        def is_closed(self):
            return False

        def call_soon_threadsafe(self, callback):
            callback()

    bot = DiscordBot(SimpleNamespace(), {})
    bot.loop = Loop()
    bot.client = client

    def run_task(coroutine):
        import asyncio

        return asyncio.run(coroutine)

    monkeypatch.setattr(discord_bot.asyncio, "create_task", run_task)

    bot.stop()

    client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_discord_response_splits_long_messages_and_uses_followups():
    interaction = SimpleNamespace(
        response=SimpleNamespace(
            is_done=Mock(return_value=False), send_message=AsyncMock()
        ),
        followup=SimpleNamespace(send=AsyncMock()),
    )
    bot = DiscordBot(SimpleNamespace(), {})

    await bot._respond(interaction, "x" * 3801, ephemeral=True)

    interaction.response.send_message.assert_awaited_once_with(
        "x" * 1900, ephemeral=True
    )
    assert interaction.followup.send.await_args_list[0].args == ("x" * 1900,)
    assert interaction.followup.send.await_args_list[1].args == ("x",)
    assert all(
        call.kwargs == {"ephemeral": True}
        for call in interaction.followup.send.await_args_list
    )


@pytest.mark.asyncio
async def test_discord_message_forwards_only_allowlisted_guild_messages():
    handler = SimpleNamespace(handle_message=AsyncMock())
    manager = SimpleNamespace(message_handler=handler)
    bot = DiscordBot(manager, {"allowed_channels": ["10"]})
    message = SimpleNamespace(
        author=SimpleNamespace(
            bot=False, id=42, name="renamed", display_name="Renamed"
        ),
        guild=SimpleNamespace(id=1),
        channel=SimpleNamespace(id=10),
        content="hello",
    )

    await bot._on_message(message)

    handler.handle_message.assert_awaited_once()
    args, kwargs = handler.handle_message.await_args
    assert args[1:] == ("Renamed", "", "#10", "hello")
    assert args[0].config.name == "discord:1"
    assert kwargs == {"platform": "discord", "actor_id": "42", "channel_id": "10"}

    message.channel.id = 11
    await bot._on_message(message)
    message.guild = None
    await bot._on_message(message)
    assert handler.handle_message.await_count == 1


@pytest.mark.asyncio
async def test_discord_run_command_builds_shared_context_and_delivers_response(
    monkeypatch,
):
    handler = SimpleNamespace(
        _create_bot_functions=Mock(return_value={"existing": True})
    )
    manager = SimpleNamespace(message_handler=handler)
    bot = DiscordBot(manager, {"allowed_channels": ["10"], "admin_user_ids": ["42"]})
    interaction = SimpleNamespace(
        user=SimpleNamespace(id=42, name="renamed", display_name="Renamed", roles=[]),
        guild=SimpleNamespace(id=1),
        channel=SimpleNamespace(id=10),
    )
    respond = AsyncMock()
    monkeypatch.setattr(bot, "_respond", respond)
    monkeypatch.setattr(discord_bot, "ensure_commands_loaded", Mock())

    async def process(raw_message, context, functions):
        assert raw_message == "!weather Helsinki"
        assert context.platform == "discord"
        assert context.actor_id == "42"
        assert context.channel_id == "10"
        assert context.server_name == "discord:1"
        assert isinstance(context.server, discord_bot.DiscordChannelTransport)
        assert functions["existing"] is True
        assert functions["discord_admin"] is True
        return CommandResponse.success_msg("Sunny")

    monkeypatch.setattr(discord_bot, "process_command_message", process)

    await bot._run_command(interaction, "weather", "Helsinki")

    respond.assert_awaited_once_with(interaction, "Sunny")


@pytest.mark.asyncio
async def test_discord_run_command_rejects_disallowed_channel_without_loading_commands(
    monkeypatch,
):
    manager = SimpleNamespace(message_handler=Mock())
    bot = DiscordBot(manager, {"allowed_channels": ["10"]})
    interaction = SimpleNamespace(
        user=SimpleNamespace(id=42, name="user", display_name="User", roles=[]),
        guild=SimpleNamespace(id=1),
        channel=SimpleNamespace(id=11),
    )
    respond = AsyncMock()
    loaded = Mock()
    monkeypatch.setattr(bot, "_respond", respond)
    monkeypatch.setattr(discord_bot, "ensure_commands_loaded", loaded)

    await bot._run_command(interaction, "weather", "Helsinki")

    loaded.assert_not_called()
    respond.assert_awaited_once_with(
        interaction, "This bot is not enabled in this channel.", True
    )


@pytest.mark.asyncio
async def test_discord_ask_honors_feature_flags_and_records_guild_metric(monkeypatch):
    community = SimpleNamespace(
        is_enabled=Mock(side_effect=[True, False]), record_metric=Mock()
    )
    gpt = SimpleNamespace(chat=Mock())
    manager = SimpleNamespace(
        message_handler=SimpleNamespace(
            _get_community_state=Mock(return_value=community)
        ),
        service_manager=SimpleNamespace(get_service=Mock(return_value=gpt)),
    )
    bot = DiscordBot(manager, {"allowed_channels": ["10"]})
    interaction = SimpleNamespace(
        user=SimpleNamespace(id=42, name="user", display_name="User"),
        guild=SimpleNamespace(id=1),
        channel=SimpleNamespace(id=10),
        response=SimpleNamespace(defer=AsyncMock()),
    )
    respond = AsyncMock()
    monkeypatch.setattr(bot, "_respond", respond)
    monkeypatch.setattr(
        discord_bot.asyncio, "to_thread", AsyncMock(return_value="Answer")
    )

    await bot._ask_command(interaction, "Question")

    interaction.response.defer.assert_awaited_once_with(thinking=True)
    assert community.is_enabled.call_args_list[0].args == ("discord:1", "#10", "ai")
    assert community.is_enabled.call_args_list[1].args == (
        "discord:1",
        "#10",
        "gpt_history",
    )
    assert discord_bot.asyncio.to_thread.await_args.args == (
        gpt.chat,
        "Question",
        "User",
        "discord:1",
        None,
    )
    community.record_metric.assert_called_once_with("discord:1", "#10", "commands")
    respond.assert_awaited_once_with(interaction, "Answer")


@pytest.mark.asyncio
async def test_discord_poll_rejects_invalid_create_data(monkeypatch):
    community = Mock()
    manager = SimpleNamespace(
        message_handler=SimpleNamespace(
            _get_community_state=Mock(return_value=community)
        )
    )
    bot = DiscordBot(manager, {"allowed_channels": ["10"]})
    interaction = SimpleNamespace(
        guild=SimpleNamespace(id=1),
        channel=SimpleNamespace(id=10),
        user=SimpleNamespace(id=42, roles=[]),
    )
    respond = AsyncMock()
    monkeypatch.setattr(bot, "_respond", respond)

    await bot._poll_command(interaction, "create", "Question | only one", Mock())

    community.save_discord_poll.assert_not_called()
    respond.assert_awaited_once_with(
        interaction, "Use: question | option | option (up to 10 options).", True
    )


@pytest.mark.asyncio
async def test_discord_poll_results_are_saved_with_channel_scoped_identity(monkeypatch):
    community = SimpleNamespace(
        get_discord_poll=Mock(
            return_value={
                "question": "Lunch?",
                "options": ["Pizza", "Sushi"],
                "creator_id": "42",
            }
        ),
        save_discord_poll=Mock(),
    )
    poll_message = SimpleNamespace(
        poll=SimpleNamespace(
            answers=[SimpleNamespace(votes=3), SimpleNamespace(vote_count=1)]
        )
    )
    interaction = SimpleNamespace(
        guild=SimpleNamespace(id=1),
        channel=SimpleNamespace(
            id=10, fetch_message=AsyncMock(return_value=poll_message)
        ),
        user=SimpleNamespace(id=42, roles=[]),
    )
    manager = SimpleNamespace(
        message_handler=SimpleNamespace(
            _get_community_state=Mock(return_value=community)
        )
    )
    bot = DiscordBot(manager, {"allowed_channels": ["10"]})
    respond = AsyncMock()
    monkeypatch.setattr(bot, "_respond", respond)

    await bot._poll_command(interaction, "results", "123", Mock())

    community.get_discord_poll.assert_called_once_with("discord:1", "#10", "123")
    community.save_discord_poll.assert_called_once_with(
        "discord:1", "#10", "123", "Lunch?", ["Pizza", "Sushi"], "42", [3, 1], False
    )
    respond.assert_awaited_once_with(interaction, "Poll 123: 1. Pizza: 3 | 2. Sushi: 1")


@pytest.mark.asyncio
async def test_discord_poll_close_requires_creator_or_configured_admin(monkeypatch):
    community = SimpleNamespace(
        get_discord_poll=Mock(
            return_value={
                "question": "Lunch?",
                "options": ["Pizza", "Sushi"],
                "creator_id": "42",
            }
        ),
        save_discord_poll=Mock(),
    )
    poll_message = SimpleNamespace(
        poll=SimpleNamespace(answers=[SimpleNamespace(votes=3)]), end_poll=AsyncMock()
    )
    interaction = SimpleNamespace(
        guild=SimpleNamespace(id=1),
        channel=SimpleNamespace(
            id=10, fetch_message=AsyncMock(return_value=poll_message)
        ),
        user=SimpleNamespace(id=99, roles=[]),
    )
    manager = SimpleNamespace(
        message_handler=SimpleNamespace(
            _get_community_state=Mock(return_value=community)
        )
    )
    bot = DiscordBot(manager, {"allowed_channels": ["10"]})
    respond = AsyncMock()
    monkeypatch.setattr(bot, "_respond", respond)

    await bot._poll_command(interaction, "close", "123", Mock())

    poll_message.end_poll.assert_not_awaited()
    community.save_discord_poll.assert_not_called()
    respond.assert_awaited_once_with(
        interaction, "Only the creator or an admin can close this poll.", True
    )


def test_bot_manager_reloads_discord_transport_from_current_config(monkeypatch):
    import bot_manager as bot_manager_module

    instances = []

    class FakeDiscordBot:
        def __init__(self, manager, settings):
            self.settings = settings
            self.token = "token"
            self.started = False
            self.stopped = False
            instances.append(self)

        def start(self):
            self.started = True
            return True

        def stop(self):
            self.stopped = True

    manager = object.__new__(bot_manager_module.BotManager)
    manager.discord_bot = None
    monkeypatch.setenv("DISCORD_TOKEN", "token")
    monkeypatch.setattr(
        bot_manager_module,
        "get_config",
        lambda: SimpleNamespace(discord={"enabled": True, "allowed_channels": ["1"]}),
    )
    monkeypatch.setitem(
        sys.modules, "discord_bot", SimpleNamespace(DiscordBot=FakeDiscordBot)
    )

    assert manager.reload_discord_transport() == "Discord started."
    assert instances[0].started is True

    monkeypatch.setattr(
        bot_manager_module,
        "get_config",
        lambda: SimpleNamespace(discord={"enabled": False}),
    )
    assert manager.reload_discord_transport() == "Discord stopped."
    assert instances[0].stopped is True
