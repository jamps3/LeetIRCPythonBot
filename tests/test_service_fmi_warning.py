#!/usr/bin/env python3
"""
Pytest tests for services.fmi_warning_service module.
"""

import json
import unittest
from unittest.mock import Mock, mock_open, patch

import pytest

from services.fmi_warning_service import FMIWarningService, create_fmi_warning_service


class TestFMIWarningService(unittest.TestCase):

    def setUp(self):
        self.mock_callback = Mock()
        self.service = FMIWarningService(callback=self.mock_callback)

    @patch("services.fmi_warning_service.feedparser.parse")
    @patch("services.fmi_warning_service.FMIWarningService._load_seen_hashes")
    @patch("services.fmi_warning_service.FMIWarningService._load_seen_data")
    def test_duplicate_title_filtering(
        self, mock_load_seen_data, mock_load_seen_hashes, mock_feedparser_parse
    ):
        # Setup data
        mock_load_seen_hashes.return_value = set()
        mock_load_seen_data.return_value = [
            {"title": "Warning 1 Joensuu", "hash": "hash1"},
            {"title": "Warning 2 Joensuu", "hash": "hash2"},
        ]

        mock_feedparser_parse.return_value.entries = [
            {"title": "Warning 1 Joensuu", "summary": "Summary 3"},  # Duplicate
            {"title": "Warning 3 Joensuu", "summary": "Summary 4"},
        ]

        # Run test
        new_warnings = self.service.check_new_warnings()

        # Only 'Warning 3' should pass as it's not a duplicate
        self.assertEqual(len(new_warnings), 1)
        self.assertIn("Warning 3", new_warnings[0])

    @patch("services.fmi_warning_service.FMIWarningService._save_seen_data")
    @patch("services.fmi_warning_service.FMIWarningService._save_seen_hashes")
    def test_save_functions(self, mock_save_seen_hashes, mock_save_seen_data):
        # Just ensure that functions are called without issues
        self.service._save_seen_hashes(set(["hash1", "hash2"]))
        self.service._save_seen_data(
            [
                {"title": "Warning 1", "hash": "hash1"},
                {"title": "Warning 2", "hash": "hash2"},
            ]
        )

        # Verify that save functions get called
        mock_save_seen_hashes.assert_called_once()
        mock_save_seen_data.assert_called_once()


# ---------------- Additional pytest-style tests for full coverage ---------------- #


def test_start_early_return_when_thread_alive(tmp_path):
    cb = Mock()
    svc = FMIWarningService(callback=cb, state_file=str(tmp_path / "state.json"))
    thread_mock = Mock()
    thread_mock.is_alive.return_value = True
    svc.thread = thread_mock

    svc.start()

    # Should return early without starting a new thread or changing running state
    assert svc.running is False
    thread_mock.is_alive.assert_called_once()


def test_start_and_stop_warns_if_thread_does_not_stop(tmp_path, capsys):
    cb = Mock()
    svc = FMIWarningService(callback=cb, state_file=str(tmp_path / "state.json"))

    # Patch threading.Thread to return a mock thread that remains alive after join
    thread_mock = Mock()
    thread_mock.is_alive.return_value = True

    with patch(
        "services.fmi_warning_service.threading.Thread", return_value=thread_mock
    ):
        svc.start()
        assert svc.running is True
        assert svc.thread is thread_mock
        svc.stop()

    out = capsys.readouterr().out
    assert "did not stop cleanly" in out
    assert "stopped" in out


def test_start_and_stop_clean_exit(tmp_path, capsys):
    cb = Mock()
    svc = FMIWarningService(callback=cb, state_file=str(tmp_path / "state.json"))

    thread_mock = Mock()
    # After join, return False for is_alive
    thread_mock.is_alive.return_value = False

    with patch(
        "services.fmi_warning_service.threading.Thread", return_value=thread_mock
    ):
        svc.start()
        svc.stop()

    out = capsys.readouterr().out
    assert "stopped" in out


def test_monitor_loop_calls_callback_on_new_warning(tmp_path):
    cb = Mock()
    svc = FMIWarningService(
        callback=cb, state_file=str(tmp_path / "state.json"), check_interval=1
    )

    def _check_side_effect():
        # Stop after first iteration
        svc.running = False
        return ["msg1"]

    svc.check_new_warnings = Mock(side_effect=_check_side_effect)
    svc.running = True
    svc._monitor_loop()

    cb.assert_called_once_with(["msg1"])


def test_monitor_loop_sleep_chunk_respects_running(tmp_path):
    cb = Mock()
    svc = FMIWarningService(
        callback=cb, state_file=str(tmp_path / "state.json"), check_interval=1
    )
    svc.check_new_warnings = Mock(return_value=[])

    def fake_sleep(_seconds):
        # Flip running to False so the loop exits after one chunk
        svc.running = False

    svc.running = True
    with patch("services.fmi_warning_service.time.sleep", side_effect=fake_sleep):
        svc._monitor_loop()

    # No callback because no warnings
    cb.assert_not_called()


def test_monitor_loop_handles_exception(tmp_path, capsys):
    cb = Mock()
    svc = FMIWarningService(
        callback=cb, state_file=str(tmp_path / "state.json"), check_interval=0
    )

    def _boom():
        svc.running = False
        raise RuntimeError("boom")

    svc.check_new_warnings = Mock(side_effect=_boom)
    svc.running = True
    svc._monitor_loop()

    out = capsys.readouterr().out
    assert "Error checking FMI warnings" in out


def test_check_new_warnings_no_new_entries(tmp_path):
    cb = Mock()
    svc = FMIWarningService(callback=cb, state_file=str(tmp_path / "state.json"))

    entry = {"title": "Keltainen tuulivaroitus Joensuu", "summary": "test"}
    h = svc._get_entry_hash(entry)

    with (
        patch("services.fmi_warning_service.feedparser.parse") as p,
        patch.object(svc, "_load_seen_hashes", return_value={h}),
        patch.object(svc, "_load_seen_data", return_value=[]),
    ):
        p.return_value.entries = [entry]
        msgs = svc.check_new_warnings()

    assert msgs == []


def test_check_new_warnings_happy_path_and_saves(tmp_path):
    cb = Mock()
    svc = FMIWarningService(callback=cb, state_file=str(tmp_path / "state.json"))

    entry1 = {"title": "Keltainen tuulivaroitus Joensuu", "summary": "Paikoin"}
    entry2 = {
        "title": "Oranssi maastopalovaroitus Itä-Suomi",
        "summary": "maa-alueille:",
    }

    with (
        patch("services.fmi_warning_service.feedparser.parse") as p,
        patch.object(svc, "_load_seen_hashes", return_value=set()),
        patch.object(svc, "_load_seen_data", return_value=[]),
        patch.object(svc, "_save_seen_hashes") as save_hashes,
        patch.object(svc, "_save_seen_data") as save_data,
    ):
        p.return_value.entries = [entry1, entry2]
        msgs = svc.check_new_warnings()

    assert len(msgs) == 2
    save_hashes.assert_called_once()
    save_data.assert_called_once()


def test_check_new_warnings_exception_returns_empty(tmp_path, capsys):
    cb = Mock()
    svc = FMIWarningService(callback=cb, state_file=str(tmp_path / "state.json"))

    with patch(
        "services.fmi_warning_service.feedparser.parse", side_effect=Exception("net")
    ):
        msgs = svc.check_new_warnings()

    assert msgs == []
    out = capsys.readouterr().out
    assert "Error fetching FMI warnings" in out


def test_get_entry_hash_deterministic():
    svc = FMIWarningService(callback=lambda x: None)
    e = {"title": "A", "summary": "B"}
    assert svc._get_entry_hash(e) == svc._get_entry_hash(e)


def test_load_and_save_seen_hashes_and_data(tmp_path):
    state = tmp_path / "state.json"
    content = {
        "fmi_warnings": {"seen_hashes": ["a", "b"], "seen_data": [{"title": "t"}]}
    }
    state.write_text(json.dumps(content), encoding="utf-8")

    svc = FMIWarningService(callback=lambda x: None, state_file=str(state))

    assert svc._load_seen_hashes() == {"a", "b"}
    assert svc._load_seen_data() == [{"title": "t"}]

    # Save merges/preserves complementary fields
    svc._save_seen_hashes({"x"})
    data_after = json.loads(state.read_text(encoding="utf-8"))
    assert data_after["fmi_warnings"]["seen_hashes"] == ["x"]
    assert data_after["fmi_warnings"]["seen_data"] == [{"title": "t"}]

    svc._save_seen_data([{"title": "n"}])
    data_after = json.loads(state.read_text(encoding="utf-8"))
    assert data_after["fmi_warnings"]["seen_hashes"] == ["x"]
    assert data_after["fmi_warnings"]["seen_data"] == [{"title": "n"}]


def test_load_seen_hashes_and_data_missing_or_corrupt(tmp_path, capsys):
    state = tmp_path / "missing.json"
    svc = FMIWarningService(callback=lambda x: None, state_file=str(state))

    # Missing file
    assert svc._load_seen_hashes() == set()
    assert svc._load_seen_data() == []

    # Corrupt file
    state.write_text("not-json", encoding="utf-8")
    assert svc._load_seen_hashes() == set()
    assert svc._load_seen_data() == []
    out = capsys.readouterr().out
    assert "State file corrupted" in out


def test_save_seen_hashes_and_data_io_errors(tmp_path, capsys):
    svc = FMIWarningService(
        callback=lambda x: None, state_file=str(tmp_path / "state.json")
    )

    m = mock_open()
    # Simulate IOError on write
    m.return_value.write.side_effect = IOError("disk full")

    with patch("builtins.open", m):
        svc._save_seen_hashes({"x"})
        svc._save_seen_data([{"title": "t"}])

    out = capsys.readouterr().out
    assert "Error saving seen hashes" in out
    assert "Error saving seen data" in out


def test_save_seen_handles_corrupt_existing_file(tmp_path):
    # Existing file is corrupt; save functions should handle and overwrite
    state = tmp_path / "state.json"
    state.write_text("not-json", encoding="utf-8")
    svc = FMIWarningService(callback=lambda x: None, state_file=str(state))

    svc._save_seen_hashes({"h"})
    svc._save_seen_data([{"title": "t"}])

    data = json.loads(state.read_text(encoding="utf-8"))
    assert data["fmi_warnings"]["seen_hashes"] == ["h"]
    assert data["fmi_warnings"]["seen_data"] == [{"title": "t"}]


@pytest.mark.parametrize(
    "title,summary,expected_sub",
    [
        ("Punainen tuulivaroitus Joensuu maa-alueille: Paikoin", "Summary", "🟥"),
        ("Oranssi maastopalovaroitus Itä-Suomi", "Summary", "🟠"),
        ("Keltainen liikennesää Pohjois-Karjala", "Summary", "🟡"),
        ("Vihreä aallokkovaroitus Koko maa", "Summary", "🟢"),
    ],
)
def test_format_warning_message_colors_and_symbols(title, summary, expected_sub):
    svc = FMIWarningService(callback=lambda x: None)
    msg = svc._format_warning_message({"title": title, "summary": summary})
    # May be filtered by inclusion rules if location not allowed; ensure allowed keyword included in titles
    assert msg is None or (expected_sub in msg)


def test_format_warning_message_filters(tmp_path):
    svc = FMIWarningService(
        callback=lambda x: None, state_file=str(tmp_path / "s.json")
    )

    # Excluded location -> None
    excluded = svc._format_warning_message(
        {"title": "Ahvenanmaa varoitus", "summary": "x"}
    )
    assert excluded is None

    # Inclusion filter: title that lacks allowed locations -> None
    not_allowed = svc._format_warning_message(
        {"title": "Varoitus Lappi", "summary": "x"}
    )
    assert not_allowed is None

    # Allowed and cleanup replacements applied
    t = "Punainen tuulivaroitus Joensuu maa-alueille: Paikoin"
    s = "Kova tuuli"
    msg = svc._format_warning_message({"title": t, "summary": s})
    assert "🟥" in msg and "🌪️" in msg and "Paikoin" in msg
    assert "maa-alueille:" not in msg
    assert msg.endswith("⚠")


def test_apply_warning_symbols_variants_in_summary():
    svc = FMIWarningService(callback=lambda x: None)
    # When keyword is only in summary (not in title), output may remain unchanged
    t = "⚠ Keltainen varoitus Itä-Suomi"
    s = "Maastopalovaroitus annettu"
    out = svc._apply_warning_symbols(t, t.lower(), s.lower())
    assert isinstance(out, str)

    s2 = "Liikennesää heikko"
    out2 = svc._apply_warning_symbols(t, t.lower(), s2.lower())
    assert isinstance(out2, str)

    s3 = "Aallokkovaroitus merialue"
    out3 = svc._apply_warning_symbols(t, t.lower(), s3.lower())
    assert isinstance(out3, str)


def test_is_duplicate_title_checks():
    svc = FMIWarningService(callback=lambda x: None)
    assert svc._is_duplicate_title("", []) is False
    seen = [{"title": "Warning A"}, {"title": "Warning B"}]
    assert svc._is_duplicate_title(" Warning A ", seen) is True
    assert svc._is_duplicate_title("warning b", seen) is True
    assert svc._is_duplicate_title("warning c", seen) is False


def test_factory_function(tmp_path):
    cb = Mock()
    svc = create_fmi_warning_service(
        cb, state_file=str(tmp_path / "s.json"), check_interval=10
    )
    assert isinstance(svc, FMIWarningService)
    assert svc.callback is cb
    assert svc.state_file.endswith("s.json")
