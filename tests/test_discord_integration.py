import inspect
import sys
from types import SimpleNamespace

from command_registry import (
    CommandContext,
    CommandInfo,
    CommandScope,
    FunctionCommandHandler,
)
from discord_bot import CORE_COMMANDS, DiscordBot
from services.community_state_service import CommunityStateService
from state_migrations import migrate_state_data


def test_discord_migration_initializes_configuration_and_poll_state():
    data = migrate_state_data({})

    assert data["config"]["discord"]["enabled"] is False
    assert data["config"]["discord"]["allowed_channels"] == []
    assert data["state"]["discord_polls"] == {}


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


def test_discord_core_commands_include_community_feature_alias():
    assert CORE_COMMANDS["features"] == "feature"


def test_discord_generated_callback_has_only_typed_slash_arguments():
    bot = DiscordBot(SimpleNamespace(), {})

    callback = bot._make_command_callback("weather")
    parameters = inspect.signature(callback).parameters

    assert list(parameters) == ["interaction", "arguments"]
    assert parameters["arguments"].annotation == "str"


def test_discord_status_distinguishes_dm_and_allowed_guild_channel():
    bot = DiscordBot(SimpleNamespace(), {"enabled": True, "allowed_channels": ["2"]})
    dm = SimpleNamespace(guild=None)
    guild = SimpleNamespace(guild=SimpleNamespace(id=1), channel=SimpleNamespace(id=2))

    assert (
        bot._status_message(dm)
        == "Discord status: online. DMs support slash commands only."
    )
    assert "Guild 1, channel 2 is enabled." in bot._status_message(guild)


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
