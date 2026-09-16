"""Versioned migrations for shared state.json."""

from __future__ import annotations

from typing import Any

from state_utils import update_json_file

SCHEMA_VERSION = 2


def _ensure_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _normalize_discord_ids(value: Any) -> list[str]:
    """Return Discord IDs as individually stored strings.

    The configuration editor accepts comma-separated IDs.  Older saves may
    contain the complete comma-separated value as a single list item.
    """
    values = [value] if isinstance(value, str) else value
    if not isinstance(values, list):
        return []
    return [
        item.strip()
        for value in values
        for item in str(value).split(",")
        if item.strip()
    ]


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
    state.setdefault("discord_polls", {})

    discord = _ensure_dict(config.get("discord"))
    discord.setdefault("enabled", False)
    discord["allowed_channels"] = _normalize_discord_ids(
        discord.get("allowed_channels", [])
    )
    discord["admin_user_ids"] = _normalize_discord_ids(
        discord.get("admin_user_ids", [])
    )
    discord["admin_role_ids"] = _normalize_discord_ids(
        discord.get("admin_role_ids", [])
    )
    config["discord"] = discord

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
