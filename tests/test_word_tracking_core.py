"""Isolated branch coverage for word tracking helpers."""

from unittest.mock import Mock

from word_tracking import DataManager, DrinkTracker, GeneralWords, WordAssociations


def test_general_words_skips_commands_and_empty_messages(tmp_path):
    manager = DataManager(str(tmp_path))
    words = GeneralWords(manager)

    words.process_message("srv", "alice", "!ignored command")
    words.process_message("srv", "alice", "---")

    assert words.get_user_stats("srv", "alice")["total_words"] == 0


def test_general_words_tracks_channels_and_calls_lemmatizer(tmp_path):
    manager = DataManager(str(tmp_path))
    lemmatizer = Mock()
    words = GeneralWords(manager, lemmatizer)

    words.process_message("srv", "alice", "Hello hello world", target="#chat")

    stats = words.get_user_stats("srv", "alice")
    assert stats["total_words"] == 3
    assert stats["channels"] == {"#chat": {"word_count": 3}}
    lemmatizer.process_message.assert_called_once_with(
        "Hello hello world", server_name="srv", source_id="#chat"
    )


def test_general_words_ignores_lemmatizer_errors(tmp_path):
    manager = DataManager(str(tmp_path))
    lemmatizer = Mock()
    lemmatizer.process_message.side_effect = RuntimeError("no analyzer")
    words = GeneralWords(manager, lemmatizer)

    words.process_message("srv", "alice", "hello")

    assert words.get_user_stats("srv", "alice")["total_words"] == 1


def test_general_words_repairs_legacy_user_channel_structure(tmp_path):
    manager = DataManager(str(tmp_path))
    manager.save_general_words_data(
        {
            "servers": {
                "srv": {
                    "nicks": {
                        "alice": {
                            "general_words": {},
                            "total_words": 0,
                        }
                    }
                }
            }
        }
    )
    words = GeneralWords(manager)

    words.process_message("srv", "alice", "hello", target="#chat")

    assert words.get_user_stats("srv", "alice")["channels"] == {
        "#chat": {"word_count": 1}
    }
    manager.save_general_words_data({})
    words.process_message("srv", "alice", "hello")
    manager.save_general_words_data({"servers": {"srv": {}}})
    words.process_message("srv", "alice", "hello")


def test_general_words_server_stats_search_leaderboards_and_compatibility(tmp_path):
    manager = DataManager(str(tmp_path))
    words = GeneralWords(manager)
    words.process_message("srv1", "alice", "hello hello world")
    words.process_message("srv1", "bob", "world")
    words.process_message("srv2", "carol", "hello")
    words.record_word("HELLO", "alice", "srv1")

    assert words.get_server_stats("missing") == {
        "server": "missing",
        "total_users": 0,
        "total_words": 0,
        "top_users": [],
        "top_words": [],
    }
    stats = words.get_server_stats("srv1")
    assert stats["total_users"] == 2
    assert stats["total_words"] == 5
    assert stats["top_words"][0] == ("hello", 3)

    search = words.search_word("HELLO")
    assert search["total_occurrences"] == 4
    assert search["servers"]["srv1"]["total"] == 3
    assert search["users"][0]["nick"] == "alice"
    assert words.get_word_stats("srv1", "hello") == {"count": 4, "top_user": "alice"}
    assert words.get_word_stats("srv1", "missing") is None

    assert words.get_leaderboard("srv1", limit=1)[0]["nick"] == "alice"
    assert words.get_leaderboard(limit=2)[0]["nick"] == "alice"
    assert words.get_leaderboard("missing") == []


def test_word_associations_process_search_delete_and_stats(tmp_path):
    manager = DataManager(str(tmp_path))
    associations = WordAssociations(manager)

    assert associations.process_message("srv", "!sauna (ignored)") == []
    assert associations.process_message("srv", "nothing here") == []
    assert associations.process_message("srv", "blank (   )") == []
    assert associations.process_message("srv", "Sauna (Harvia Vega)") == [
        ("sauna", "Harvia Vega")
    ]
    assert associations.process_message("srv", "sauna (Harvia Vega)") == []
    assert associations.add_association("sauna", "Wood stove")
    assert associations.add_association("lake", "Saimaa")
    assert not associations.add_association("", "invalid")

    assert associations.get_association(" SAUNA ") == ["Harvia Vega", "Wood stove"]
    assert associations.get_association("missing") is None
    assert associations.search_associations("sau") == {
        "sauna": ["Harvia Vega", "Wood stove"]
    }
    assert associations.search_associations("wood") == {"sauna": ["Wood stove"]}
    assert associations.get_stats()["words_with_multiple"] == 1

    assert associations.delete_association("missing") is False
    assert associations.delete_association("lake", "missing")
    assert associations.delete_association("sauna", "Harvia Vega")
    assert associations.get_association("sauna") == ["Wood stove"]
    assert associations.delete_association("lake", "Saimaa")
    assert associations.get_association("lake") is None
    assert associations.delete_association("sauna")
    assert "sauna" not in associations.get_all_associations()


def test_word_associations_load_failure_returns_empty_data(tmp_path):
    manager = DataManager(str(tmp_path))
    associations = WordAssociations(manager)
    manager.load_json = Mock(side_effect=RuntimeError("broken"))

    assert associations.get_all_associations() == {}


def test_drink_tracker_records_parses_and_reports_stats(tmp_path):
    manager = DataManager(str(tmp_path))
    tracker = DrinkTracker(manager)

    assert tracker.process_message("srv", "alice", "hello") == []
    assert tracker.process_message("srv", "alice", "krak") == [
        ("krak", "unspecified", tracker.STANDARD_DRINK_GRAMS, None)
    ]
    parsed = tracker.process_message("srv", "alice", "krak (Karhu 5,0% 0.5L) @ 02:15")
    assert parsed == [("krak", "Karhu 5,0% 0.5L", 19.73, "02:15")]
    tracker.process_message("srv", "bob", "narsk (Cider 4.7% 33dL)")

    assert tracker._parse_abv("beer 4,7%") == 4.7
    assert tracker._parse_abv("beer") == tracker.DEFAULT_ABV
    assert tracker._parse_volume("beer 12oz") == 12 * 0.0295735
    assert tracker._parse_volume("beer") == tracker.DEFAULT_VOLUME_L
    assert tracker._parse_opened_time("") is None
    assert tracker._parse_opened_time("02:15").hour == 2
    assert tracker._parse_opened_time("bad") is None

    assert tracker.get_user_stats("srv", "alice")["total_drink_words"] == 2
    assert tracker.get_user_stats("missing", "alice")["total_drink_words"] == 0
    assert tracker.get_server_stats("missing")["total_users"] == 0
    assert tracker.get_server_stats("srv")["total_users"] == 2
    assert tracker.get_global_stats()["total_drink_words"] == 3
    assert tracker.search_drink_word("KRAK")["total_occurrences"] == 2
    assert tracker.search_drink_word("krak", "missing")["total_occurrences"] == 0
    assert tracker.search_specific_drink("kar*", "srv")["total_occurrences"] == 1
    assert tracker.get_user_top_drinks("srv", "alice")[0]["drink_word"] == "krak"
    assert tracker.get_drink_word_breakdown("missing") == []
    assert tracker.get_drink_word_breakdown("srv")[0] == ("krak", 2, "alice")


def test_drink_tracker_alko_lookup_opt_out_and_reset(tmp_path):
    manager = DataManager(str(tmp_path))
    alko = Mock()
    alko.get_product_info.return_value = {"alcohol_grams": "15.5"}
    tracker = DrinkTracker(manager, alko)

    assert tracker._parse_alcohol_content("known") == 15.5
    tracker.set_alko_service(None)
    assert tracker.alko_service is None

    assert "poissa" in tracker.handle_opt_out("srv", "alice")
    assert tracker.process_message("srv", "alice", "krak") == []
    assert "takaisin" in tracker.handle_opt_out("srv", "alice")
    tracker.process_message("srv", "alice", "krak")
    assert tracker.reset_user_stats("srv", "alice")
    assert not tracker.reset_user_stats("srv", "alice")


def test_drink_tracker_repairs_structures_caps_history_and_falls_back_from_alko(
    tmp_path,
):
    manager = DataManager(str(tmp_path))
    tracker = DrinkTracker(manager)
    manager.save_drink_data({})
    tracker._record_drink_word("srv", "alice", "krak", "beer")
    manager.save_drink_data({"servers": {"srv": {}}})
    tracker._record_drink_word("srv", "alice", "krak", "beer")

    data = manager.load_drink_data()
    drink = data["servers"]["srv"]["nicks"]["alice"]["drink_words"]["krak"]
    drink["timestamps"] = [{}] * 100
    manager.save_drink_data(data)
    tracker._record_drink_word("srv", "alice", "krak", "beer")
    assert (
        len(
            manager.load_drink_data()["servers"]["srv"]["nicks"]["alice"][
                "drink_words"
            ]["krak"]["timestamps"]
        )
        == 100
    )

    alko = Mock()
    alko.get_product_info.return_value = None
    alko.get_stats.return_value = {"products": 0}
    tracker.set_alko_service(alko)
    assert tracker._parse_alcohol_content("beer 5% 0.5L") == 19.73
    alko.get_stats.side_effect = RuntimeError("no stats")
    assert tracker._parse_alcohol_content("beer 5% 0.5L") == 19.73
    alko.get_product_info.side_effect = RuntimeError("lookup failed")
    assert tracker._parse_alcohol_content("beer 5% 0.5L") == 19.73

    manager.load_drink_data = Mock(return_value={"servers": None})
    assert not tracker.reset_user_stats("srv", "alice")
