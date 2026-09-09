from types import SimpleNamespace

from command_registry import (
    CommandContext,
    CommandInfo,
    CommandScope,
    FunctionCommandHandler,
)
from discord_bot import DiscordBot
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
