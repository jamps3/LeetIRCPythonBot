import json
from types import SimpleNamespace

from command_loader import load_all_commands, reset_commands_loaded_flag
from command_registry import (
    CommandContext,
    get_command_registry,
    reset_command_registry,
)
from services.community_state_service import CommunityStateService
from state_migrations import SCHEMA_VERSION, migrate_state_file


def test_state_migration_adds_new_sections(tmp_path):
    state_file = tmp_path / "state.json"
    state_file.write_text(
        json.dumps({"config": {"bot_name": "Test"}}), encoding="utf-8"
    )

    assert migrate_state_file(str(state_file))

    data = json.loads(state_file.read_text(encoding="utf-8"))
    state = data["state"]
    assert state["schema_version"] == SCHEMA_VERSION
    assert state["channel_features"] == {}
    assert state["observability"] == {
        "metrics": {},
        "commands_by_platform": {},
        "background_jobs": {},
    }
    assert state["seen"] == {}
    assert state["polls"] == {}


def test_channel_features_default_and_toggle(tmp_path):
    state_file = tmp_path / "state.json"
    state_file.write_text("{}", encoding="utf-8")
    service = CommunityStateService(str(state_file))

    assert service.is_enabled("srv", "#chan", "youtube") is True
    service.set_feature("srv", "#chan", "youtube", False)

    assert service.is_enabled("srv", "#chan", "youtube") is False
    assert service.is_enabled("srv", "#other", "youtube") is True
    assert service.is_enabled("other-srv", "#chan", "youtube") is True


def test_metrics_are_channel_specific(tmp_path):
    state_file = tmp_path / "state.json"
    state_file.write_text("{}", encoding="utf-8")
    service = CommunityStateService(str(state_file))

    service.record_metric("srv", "#chan", "messages")
    service.record_metric("srv", "#chan", "messages")
    service.record_metric("srv", "#other", "commands")
    service.record_metric("other-srv", "#chan", "messages")

    assert service.get_metrics("srv", "#chan")["messages"] == 2
    assert "commands" not in service.get_metrics("srv", "#chan")
    assert service.get_metrics("srv", "#other")["commands"] == 1
    assert service.get_metrics("other-srv", "#chan")["messages"] == 1


def test_seen_is_channel_specific(tmp_path):
    state_file = tmp_path / "state.json"
    state_file.write_text("{}", encoding="utf-8")
    service = CommunityStateService(str(state_file))

    service.record_seen("srv", "#chan", "Alice", "hello", "ident@host")

    entry = service.get_seen("srv", "#chan", "alice")
    assert entry["nick"] == "Alice"
    assert entry["message"] == "hello"
    assert service.get_seen("srv", "#other", "alice") is None
    assert service.get_seen("other-srv", "#chan", "alice") is None


def test_poll_lifecycle_is_channel_specific(tmp_path):
    state_file = tmp_path / "state.json"
    state_file.write_text("{}", encoding="utf-8")
    service = CommunityStateService(str(state_file))

    poll_id = service.create_poll("srv", "#chan", "Alice", "Lunch?", ["pizza", "sushi"])
    assert (
        service.vote_poll("srv", "#chan", poll_id, "Bob", 2)
        == "Vote counted for sushi."
    )
    results = service.poll_results("srv", "#chan", poll_id)
    assert "pizza: 0" in results
    assert "sushi: 1" in results
    assert service.poll_results("srv", "#other", poll_id) == "Poll not found."
    assert service.poll_results("other-srv", "#chan", poll_id) == "Poll not found."
    assert service.close_poll("srv", "#chan", poll_id) == "Poll closed."
    assert service.vote_poll("srv", "#chan", poll_id, "Carol", 1) == "Poll is closed."


def test_history_command_uses_current_channel(tmp_path):
    reset_command_registry()
    reset_commands_loaded_flag()
    load_all_commands()

    calls = []

    class FakeGPT:
        def get_conversation_stats(self, server, channel):
            calls.append((server, channel))
            return {
                "total_messages": 3,
                "user_messages": 2,
                "assistant_messages": 1,
            }

    context = CommandContext(
        command="history",
        args=[],
        raw_message="!history",
        sender="Bob",
        target="#chan",
        server_name="srv",
    )

    import asyncio

    registry = get_command_registry()
    response = asyncio.run(
        registry.execute_command(
            "history",
            context,
            {
                "community_state": CommunityStateService(str(tmp_path / "state.json")),
                "gpt_service": FakeGPT(),
            },
        )
    )

    assert calls == [("srv", "#chan")]
    assert "GPT history for #chan" in response.message


def test_community_commands_are_loaded_and_use_state(tmp_path):
    reset_command_registry()
    reset_commands_loaded_flag()
    load_all_commands()

    registry = get_command_registry()
    assert registry.get_handler("seen")
    assert registry.get_handler("poll")
    assert registry.get_handler("feature")

    state_file = tmp_path / "state.json"
    state_file.write_text("{}", encoding="utf-8")
    service = CommunityStateService(str(state_file))
    service.record_seen("srv", "#chan", "Alice", "hi")
    bot_functions = {
        "community_state": service,
        "gpt_service": SimpleNamespace(
            get_conversation_stats=lambda server, channel: {
                "total_messages": 0,
                "user_messages": 0,
                "assistant_messages": 0,
            }
        ),
    }
    context = CommandContext(
        command="seen",
        args=["alice"],
        raw_message="!seen alice",
        sender="Bob",
        target="#chan",
        server_name="srv",
    )

    import asyncio

    response = asyncio.run(registry.execute_command("seen", context, bot_functions))
    assert "Alice was last seen" in response.message
