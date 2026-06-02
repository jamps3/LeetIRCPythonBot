"""Behavioral tests for IRC protocol commands."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from cmd_modules import irc as irc_commands
from command_registry import CommandContext


def make_context(command, *args):
    return CommandContext(
        command=command,
        args=list(args),
        raw_message=" ".join((f"!{command}", *args)),
        sender="TestUser",
        target="#test",
        server_name="TestServer",
    )


@pytest.fixture
def irc_client():
    return Mock()


@pytest.fixture
def bot_functions(irc_client):
    server = SimpleNamespace(irc_client=irc_client)
    return {"server_manager": SimpleNamespace(servers={"test": server})}


def test_get_irc_connection_handles_missing_and_inactive_servers(irc_client):
    assert irc_commands.get_irc_connection({}) is None
    assert (
        irc_commands.get_irc_connection(
            {"server_manager": SimpleNamespace(servers={"test": None})}
        )
        is None
    )
    assert (
        irc_commands.get_irc_connection(
            {"server_manager": SimpleNamespace(servers={"test": SimpleNamespace()})}
        )
        is None
    )


@pytest.mark.parametrize(
    ("handler", "command", "args", "raw_call", "response"),
    [
        (
            irc_commands.irc_join_command,
            "join",
            ("general",),
            "JOIN #general",
            "Joining",
        ),
        (
            irc_commands.irc_join_command,
            "join",
            ("#general", "secret"),
            "JOIN #general secret",
            "Joining",
        ),
        (
            irc_commands.irc_part_command,
            "part",
            ("general", "Bye", "now"),
            "PART #general :Bye now",
            "Leaving",
        ),
        (
            irc_commands.irc_nick_command,
            "nick",
            ("NewNick",),
            "NICK NewNick",
            "Changing",
        ),
        (irc_commands.irc_whois_command, "whois", ("Nick",), "WHOIS Nick", "WHOIS"),
        (irc_commands.irc_whowas_command, "whowas", ("Nick",), "WHOWAS Nick", "WHOWAS"),
        (
            irc_commands.irc_names_command,
            "names",
            ("general",),
            "NAMES #general",
            "NAMES",
        ),
        (irc_commands.irc_list_command, "list", (), "LIST", "channel list"),
        (
            irc_commands.irc_list_command,
            "list",
            ("general",),
            "LIST #general",
            "channel list",
        ),
        (
            irc_commands.irc_topic_command,
            "topic",
            ("general",),
            "TOPIC #general",
            "topic",
        ),
        (
            irc_commands.irc_topic_command,
            "topic",
            ("general", "New", "topic"),
            "TOPIC #general :New topic",
            "topic",
        ),
        (irc_commands.irc_mode_command, "mode", ("Nick",), "MODE Nick", "modes"),
        (
            irc_commands.irc_mode_command,
            "mode",
            ("#general", "+o", "Nick"),
            "MODE #general +o Nick",
            "mode",
        ),
        (
            irc_commands.irc_invite_command,
            "invite",
            ("Nick", "general"),
            "INVITE Nick #general",
            "Inviting",
        ),
        (
            irc_commands.irc_kick_command,
            "kick",
            ("general", "Nick", "Reason"),
            "KICK #general Nick :Reason",
            "Kicking",
        ),
        (irc_commands.irc_away_command, "away", (), "AWAY", "back"),
        (irc_commands.irc_away_command, "away", ("Lunch",), "AWAY :Lunch", "away"),
        (irc_commands.irc_motd_command, "motd", (), "MOTD", "MOTD"),
        (irc_commands.irc_time_command, "time", (), "TIME", "time"),
        (irc_commands.irc_time_command, "time", ("irc.test",), "TIME irc.test", "time"),
        (irc_commands.irc_version_command, "ircversion", (), "VERSION", "version"),
        (
            irc_commands.irc_admin_command,
            "ircadmin",
            ("irc.test",),
            "ADMIN irc.test",
            "admin",
        ),
        (
            irc_commands.irc_raw_command,
            "raw",
            ("PRIVMSG", "#general", ":hello"),
            "PRIVMSG #general :hello",
            "raw command",
        ),
    ],
)
def test_raw_protocol_commands(
    handler, command, args, raw_call, response, bot_functions, irc_client
):
    result = handler(make_context(command, *args), bot_functions)

    irc_client.send_raw.assert_called_once_with(raw_call)
    assert response.lower() in result.lower()


@pytest.mark.parametrize(
    ("handler", "command", "args", "method", "expected"),
    [
        (
            irc_commands.irc_msg_command,
            "msg",
            ("Nick", "hello", "there"),
            "send_message",
            ("Nick", "hello there"),
        ),
        (
            irc_commands.irc_notice_command,
            "notice",
            ("Nick", "hello"),
            "send_notice",
            ("Nick", "hello"),
        ),
    ],
)
def test_message_commands(
    handler, command, args, method, expected, bot_functions, irc_client
):
    result = handler(make_context(command, *args), bot_functions)

    getattr(irc_client, method).assert_called_once_with(*expected)
    assert "Nick" in result


@pytest.mark.parametrize(
    ("handler", "command", "args"),
    [
        (irc_commands.irc_join_command, "join", ()),
        (irc_commands.irc_part_command, "part", ()),
        (irc_commands.irc_nick_command, "nick", ()),
        (irc_commands.irc_msg_command, "msg", ("Nick",)),
        (irc_commands.irc_notice_command, "notice", ("Nick",)),
        (irc_commands.irc_whois_command, "whois", ()),
        (irc_commands.irc_whowas_command, "whowas", ()),
        (irc_commands.irc_names_command, "names", ()),
        (irc_commands.irc_topic_command, "topic", ()),
        (irc_commands.irc_mode_command, "mode", ()),
        (irc_commands.irc_invite_command, "invite", ("Nick",)),
        (irc_commands.irc_kick_command, "kick", ("#general",)),
        (irc_commands.irc_raw_command, "raw", ()),
    ],
)
def test_commands_validate_required_arguments(handler, command, args):
    assert handler(make_context(command, *args), {}).startswith("Usage:")


def test_commands_report_disconnected_server():
    assert (
        irc_commands.irc_motd_command(make_context("motd"), {})
        == "Not connected to any IRC server"
    )


def test_ircping_uses_current_timestamp(bot_functions, irc_client):
    with patch("time.time", return_value=123.9):
        result = irc_commands.irc_ping_command(make_context("ircping"), bot_functions)

    irc_client.send_raw.assert_called_once_with("PING :123")
    assert result == "Sent PING to irc.example.com"
