"""Versioned migrations for shared state.json."""

from __future__ import annotations

from typing import Any

from state_utils import update_json_file

SCHEMA_VERSION = 1


def _ensure_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def migrate_state_data(data: Any) -> dict:
    """Return state data with the current schema sections present."""
    if not isinstance(data, dict):
        data = {}

    config = _ensure_dict(data.get("config"))
    state = _ensure_dict(data.get("state"))

    state.setdefault("schema_version", 0)
    state.setdefault("channel_features", {})
    state.setdefault("observability", {"metrics": {}})
    state.setdefault("seen", {})
    state.setdefault("polls", {})

    data["config"] = config
    data["state"] = state
    state["schema_version"] = SCHEMA_VERSION
    return data


def migrate_state_file(state_file: str) -> bool:
    """Migrate a state file in place using strict atomic persistence."""
    return update_json_file(
        state_file,
        migrate_state_data,
        default=dict,
        strict=True,
    )
