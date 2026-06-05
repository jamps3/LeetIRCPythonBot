"""Focused compatibility coverage for BotManager delegates."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def bare_manager():
    from bot_manager import BotManager

    manager = object.__new__(BotManager)
    manager.bot_name = "Bot"
    manager.message_handler = Mock()
    manager.console_manager = Mock()
    manager.server_manager = Mock()
    manager.service_manager = Mock()
    manager.service_manager.services = {}
    manager.logger = Mock()
    manager._servers = {}
    return manager


def test_server_manager_delegates(bare_manager):
    bare_manager.get_server("srv")
    bare_manager.get_all_servers()
    bare_manager.connect_to_servers(["srv"])
    bare_manager.disconnect_from_servers(["srv"], "bye")
    bare_manager.add_server_and_connect("srv", "host")
    bare_manager.wait_for_shutdown()
    bare_manager.load_configurations()
    bare_manager.register_callbacks()
    bare_manager.send_to_all_servers("hello")
    bare_manager.send_notice_to_all_servers("hello")
    assert bare_manager.server_manager.method_calls


def test_message_and_console_delegates(bare_manager):
    message_methods = [
        "_wrap_irc_message_utf8_bytes",
        "_update_env_file",
        "_send_response",
        "_load_leet_winners",
        "_save_leet_winners",
        "_measure_latency",
        "_handle_ipfs_command",
        "_fetch_title",
        "_process_leet_winner_summary",
        "toggle_tamagotchi",
        "_send_youtube_info",
        "_send_imdb_info",
        "_search_youtube",
        "_handle_youtube_urls",
        "_get_subscriptions_module",
        "_send_latest_otiedote",
        "_console_weather",
        "_send_scheduled_message",
        "_get_eurojackpot_numbers",
        "_get_eurojackpot_results",
        "_get_alko_product",
        "_send_weather",
        "_format_counts",
        "_get_drink_words",
        "_create_bot_functions",
        "_track_words",
        "_check_nanoleet_achievement",
        "_send_drink_word_notifications",
        "_send_drink_word_notifications_to_user",
        "_process_ekavika_winner_summary",
        "_handle_join",
        "_handle_part",
        "_handle_quit",
        "_handle_numeric",
        "_is_url_blacklisted",
        "_send_electricity_price",
        "_handle_otiedote_release",
        "_handle_danger_announcements",
        "_handle_fmi_warnings",
    ]
    for name in message_methods:
        getattr(bare_manager, name)("x")
    console_methods = [
        "_listen_for_console_commands",
        "_create_console_bot_functions",
        "_setup_readline_history",
        "_save_command_history",
        "_protected_print",
        "_protected_stdout_write",
        "_protected_stderr_write",
        "_is_interactive_terminal",
        "_console_connect",
        "_console_disconnect",
    ]
    for name in console_methods:
        getattr(bare_manager, name)("x")
    bare_manager._get_channel_status()


def test_properties_and_models(bare_manager):
    handler = bare_manager.message_handler
    handler.data_manager = "dm"
    handler.drink_tracker = "drink"
    handler.bac_tracker = "bac"
    handler.general_words = "words"
    handler.tamagotchi = "pet"
    handler.tamagotchi_enabled = False
    handler.use_notices = False
    assert bare_manager.data_manager == "dm"
    assert bare_manager.drink_tracker == "drink"
    assert bare_manager.bac_tracker == "bac"
    assert bare_manager.general_words == "words"
    assert bare_manager.tamagotchi == "pet"
    bare_manager.tamagotchi_enabled = True
    bare_manager.use_notices = True
    assert handler.tamagotchi_enabled and handler.use_notices

    gpt = SimpleNamespace(model="old")
    bare_manager.service_manager.get_service.side_effect = lambda name: (
        gpt if name == "gpt" else None
    )
    bare_manager._update_env_file = Mock()
    assert bare_manager.set_openai_model("new") == "Model set"
    assert bare_manager.get_openai_model() == "new"
    bare_manager.service_manager.get_service.return_value = None
    bare_manager.service_manager.get_service.side_effect = None
    assert bare_manager.set_openai_model("new") == "No GPT service"


def test_console_send_and_join_part_paths(bare_manager):
    server = Mock(connected=True)
    bare_manager._servers = {"srv": server}
    bare_manager.active_channel = None
    assert bare_manager._console_send_to_channel("hello") == "No active channel"
    bare_manager.active_channel = "#chat"
    bare_manager.active_server = "missing"
    assert bare_manager._console_send_to_channel("hello") == "No active server"
    bare_manager.active_server = "srv"
    assert "Sent to srv:#chat" in bare_manager._console_send_to_channel("hello")

    bare_manager.server_threads = {"srv": Mock(is_alive=lambda: True)}
    bare_manager.joined_channels = {}
    assert bare_manager._console_join_or_part_channel("chat") == "Joined #chat"
    assert bare_manager._console_join_or_part_channel("#chat") == "Parted #chat"
