#!/usr/bin/env python3
"""
Pytest tests for word tracking functionality.
"""

import json
import os
import tempfile
from types import SimpleNamespace

import pytest

# Import command and word tracking classes
import commands as cmds
from word_tracking import DataManager, GeneralWords


@pytest.fixture()
def temp_dm_and_words(monkeypatch):
    """Provide isolated DataManager and GeneralWords with a temporary data dir.
    Monkeypatch commands_extended to use these instances so command handlers
    operate on test data only.
    """
    tmpdir = tempfile.mkdtemp()
    dm = DataManager(tmpdir)
    gw = GeneralWords(dm)

    # Point commands module singletons to our temp instances
    monkeypatch.setattr(cmds, "data_manager", dm, raising=True)
    monkeypatch.setattr(cmds, "general_words", gw, raising=True)

    yield SimpleNamespace(tmpdir=tmpdir, dm=dm, gw=gw)

    # Cleanup temp files
    for name in (
        "general_words.json",
        "drink_tracking.json",
        "tamagotchi_state.json",
        "privacy_settings.json",
    ):
        path = os.path.join(tmpdir, name)
        if os.path.exists(path):
            os.unlink(path)
    try:
        os.rmdir(tmpdir)
    except OSError:
        pass


def _write_general_words(dm: DataManager, data: dict):
    dm.save_general_words_data(data)


def test_get_all_servers(temp_dm_and_words):
    dm = temp_dm_and_words.dm
    data = {
        "servers": {
            "srv1": {"nicks": {}},
            "srv2": {"nicks": {}},
        },
        "last_updated": "",
        "version": "1.0.0",
    }
    _write_general_words(dm, data)
    assert sorted(dm.get_all_servers()) == ["srv1", "srv2"]


def test_general_words_process_and_stats(temp_dm_and_words):
    gw = temp_dm_and_words.gw

    # Process a couple messages
    gw.process_message("srv", "alice", "Hello world world", target="#ch")
    gw.process_message("srv", "alice", "hello there")

    stats = gw.get_user_stats("srv", "alice")
    assert stats["total_words"] == 5
    top = gw.get_user_top_words("srv", "alice", limit=2)
    # world:2, hello:2, there:1 (order by count desc). Tie acceptable either way for hello/world.
    words = {w["word"]: w["count"] for w in top}
    assert words.get("hello") in (1, 2) or words.get("world") in (1, 2)


def test_topwords_with_nick_found(temp_dm_and_words):
    dm = temp_dm_and_words.dm
    gw = temp_dm_and_words.gw

    # Seed data so that alice exists on srv1 with some words
    data = {
        "servers": {
            "srv1": {
                "nicks": {
                    "alice": {
                        "general_words": {"hello": 3, "world": 1, "beer": 2},
                        "first_seen": "",
                        "last_activity": "",
                        "total_words": 6,
                        "channels": {},
                    }
                }
            }
        },
        "last_updated": "",
        "version": "1.0.0",
    }
    _write_general_words(dm, data)

    ctx = SimpleNamespace(args=["alice"], args_text="alice")
    result = cmds.command_topwords(ctx, None)
    # Expect format: alice@srv1: word: count, ...
    assert result.startswith("alice@srv1:"), result
    assert "hello: 3" in result
    assert "beer: 2" in result


def test_topwords_nick_not_found(temp_dm_and_words):
    ctx = SimpleNamespace(args=["missing"], args_text="missing")
    result = cmds.command_topwords(ctx, None)
    assert "Käyttäjää 'missing' ei löydy" in result


def test_topwords_global(temp_dm_and_words):
    dm = temp_dm_and_words.dm
    # Two servers, aggregate top words
    data = {
        "servers": {
            "srv1": {
                "nicks": {
                    "alice": {
                        "general_words": {"hello": 2, "beer": 1},
                        "first_seen": "",
                        "last_activity": "",
                        "total_words": 3,
                        "channels": {},
                    }
                }
            },
            "srv2": {
                "nicks": {
                    "bob": {
                        "general_words": {"hello": 1, "world": 4},
                        "first_seen": "",
                        "last_activity": "",
                        "total_words": 5,
                        "channels": {},
                    }
                }
            },
        },
        "last_updated": "",
        "version": "1.0.0",
    }
    _write_general_words(dm, data)

    # No args -> global top words
    ctx = SimpleNamespace(args=[], args_text="")
    res = cmds.command_topwords(ctx, None)
    assert res.startswith("Käytetyimmät sanat (globaali):"), res
    # Aggregates hello=3, world=4, beer=1
    assert "hello: 3" in res
    assert "world: 4" in res
