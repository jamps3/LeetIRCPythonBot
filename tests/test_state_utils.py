import json
import threading

import pytest

from src.state_utils import backup_json_atomic, update_json_file


def test_strict_update_preserves_invalid_file(tmp_path):
    state = tmp_path / "state.json"
    state.write_text("{", encoding="utf-8")

    with pytest.raises(ValueError, match="Refusing to overwrite invalid JSON"):
        update_json_file(str(state), lambda data: {"changed": True}, strict=True)

    assert state.read_text(encoding="utf-8") == "{"


def test_concurrent_updates_preserve_both_sections(tmp_path):
    state = tmp_path / "state.json"
    state.write_text("{}", encoding="utf-8")
    barrier = threading.Barrier(2)

    def update(key):
        barrier.wait()
        update_json_file(
            str(state),
            lambda data: {**data, key: True},
            strict=True,
        )

    threads = [threading.Thread(target=update, args=(key,)) for key in ("a", "b")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    data = json.loads(state.read_text(encoding="utf-8"))
    assert data.pop("last_updated")
    assert data == {"a": True, "b": True}


def test_backup_json_atomic_overwrites_fixed_backup(tmp_path):
    state = tmp_path / "state.json"
    state.write_text('{"version": 1}', encoding="utf-8")
    backup_json_atomic(str(state), "start.bak")

    state.write_text('{"version": 2}', encoding="utf-8")
    backup_json_atomic(str(state), "start.bak")

    assert json.loads((tmp_path / "state.json.start.bak").read_text()) == {"version": 2}


def test_backup_json_atomic_preserves_previous_backup_if_state_invalid(tmp_path):
    state = tmp_path / "state.json"
    backup = tmp_path / "state.json.end.bak"
    state.write_text("{", encoding="utf-8")
    backup.write_text('{"valid": true}', encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        backup_json_atomic(str(state), "end.bak")

    assert json.loads(backup.read_text()) == {"valid": True}
