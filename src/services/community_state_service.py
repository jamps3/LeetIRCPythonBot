"""State-backed community features: channel flags, metrics, seen, and polls."""

from __future__ import annotations

import re
import secrets
from datetime import datetime, timezone
from typing import Any

from state_migrations import migrate_state_data
from state_utils import load_json_file, update_json_file

DEFAULT_FEATURES = {
    "ai": True,
    "gpt_history": True,
    "tamagotchi": True,
    "youtube": True,
    "url_titles": True,
    "word_tracking": True,
    "420": True,
}

_random = secrets.SystemRandom()


def _channel_key(server_name: str, channel: str) -> str:
    return f"{server_name.lower()}:{channel.lower()}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_section(data: Any) -> dict:
    data = migrate_state_data(data)
    return data["state"]


class CommunityStateService:
    """Small facade over state.json for user-facing community features."""

    def __init__(self, state_file: str):
        self.state_file = state_file

    def get_channel_features(self, server_name: str, channel: str) -> dict[str, bool]:
        data = load_json_file(self.state_file, default=dict)
        state = _state_section(data)
        configured = state.get("channel_features", {}).get(
            _channel_key(server_name, channel), {}
        )
        if not isinstance(configured, dict):
            configured = {}
        features = DEFAULT_FEATURES.copy()
        features.update(
            {
                name: bool(value)
                for name, value in configured.items()
                if name in DEFAULT_FEATURES
            }
        )
        return features

    def is_enabled(self, server_name: str, channel: str, feature: str) -> bool:
        return self.get_channel_features(server_name, channel).get(feature, True)

    def set_feature(
        self, server_name: str, channel: str, feature: str, enabled: bool
    ) -> bool:
        if feature not in DEFAULT_FEATURES:
            raise ValueError(f"Unknown feature: {feature}")

        def updater(data):
            state = _state_section(data)
            features = state.setdefault("channel_features", {})
            channel_features = features.setdefault(
                _channel_key(server_name, channel), {}
            )
            channel_features[feature] = enabled
            return data

        return update_json_file(self.state_file, updater, default=dict, strict=True)

    def record_metric(
        self, server_name: str, channel: str, metric: str, amount: int = 1
    ) -> bool:
        def updater(data):
            state = _state_section(data)
            metrics = state.setdefault("observability", {}).setdefault("metrics", {})
            scoped = metrics.setdefault(_channel_key(server_name, channel), {})
            scoped[metric] = int(scoped.get(metric, 0)) + amount
            scoped["last_event_at"] = _now()
            return data

        return update_json_file(self.state_file, updater, default=dict, strict=True)

    def get_metrics(self, server_name: str | None = None, channel: str | None = None):
        data = load_json_file(self.state_file, default=dict)
        metrics = _state_section(data).get("observability", {}).get("metrics", {})
        if server_name and channel:
            return metrics.get(_channel_key(server_name, channel), {})
        return metrics

    def record_seen(
        self,
        server_name: str,
        channel: str,
        nick: str,
        message: str,
        ident_host: str = "",
    ) -> bool:
        if not channel.startswith("#"):
            return False

        def updater(data):
            state = _state_section(data)
            seen = state.setdefault("seen", {})
            scoped = seen.setdefault(_channel_key(server_name, channel), {})
            scoped[nick.lower()] = {
                "nick": nick,
                "ident_host": ident_host,
                "last_seen": _now(),
                "message": message[:300],
            }
            return data

        return update_json_file(self.state_file, updater, default=dict, strict=True)

    def get_seen(self, server_name: str, channel: str, nick: str) -> dict | None:
        data = load_json_file(self.state_file, default=dict)
        scoped = (
            _state_section(data)
            .get("seen", {})
            .get(_channel_key(server_name, channel), {})
        )
        entry = scoped.get(nick.lower())
        return entry if isinstance(entry, dict) else None

    def create_poll(
        self,
        server_name: str,
        channel: str,
        creator: str,
        question: str,
        options: list[str],
    ) -> str:
        poll_id = str(_random.randrange(1000, 10000))

        def updater(data):
            state = _state_section(data)
            polls = state.setdefault("polls", {})
            scoped = polls.setdefault(_channel_key(server_name, channel), {})
            while poll_id in scoped:
                raise ValueError("Poll id collision, try again")
            scoped[poll_id] = {
                "id": poll_id,
                "question": question,
                "options": options,
                "creator": creator,
                "created_at": _now(),
                "open": True,
                "votes": {},
            }
            return data

        update_json_file(self.state_file, updater, default=dict, strict=True)
        return poll_id

    def vote_poll(
        self,
        server_name: str,
        channel: str,
        poll_id: str,
        nick: str,
        option_number: int,
    ) -> str:
        result = "Poll not found."

        def updater(data):
            nonlocal result
            state = _state_section(data)
            poll = (
                state.setdefault("polls", {})
                .setdefault(_channel_key(server_name, channel), {})
                .get(poll_id)
            )
            if not isinstance(poll, dict):
                return data
            if not poll.get("open", True):
                result = "Poll is closed."
                return data
            options = poll.get("options", [])
            if option_number < 1 or option_number > len(options):
                result = f"Choose 1-{len(options)}."
                return data
            poll.setdefault("votes", {})[nick.lower()] = option_number - 1
            result = f"Vote counted for {options[option_number - 1]}."
            return data

        update_json_file(self.state_file, updater, default=dict, strict=True)
        return result

    def close_poll(self, server_name: str, channel: str, poll_id: str) -> str:
        result = "Poll not found."

        def updater(data):
            nonlocal result
            state = _state_section(data)
            poll = (
                state.setdefault("polls", {})
                .setdefault(_channel_key(server_name, channel), {})
                .get(poll_id)
            )
            if isinstance(poll, dict):
                poll["open"] = False
                result = "Poll closed."
            return data

        update_json_file(self.state_file, updater, default=dict, strict=True)
        return result

    def poll_results(self, server_name: str, channel: str, poll_id: str) -> str:
        poll = self._get_poll(server_name, channel, poll_id)
        if not poll:
            return "Poll not found."
        options = poll.get("options", [])
        votes = poll.get("votes", {})
        counts = [0 for _ in options]
        for index in votes.values():
            if isinstance(index, int) and 0 <= index < len(counts):
                counts[index] += 1
        status = "open" if poll.get("open", True) else "closed"
        parts = [f"{i + 1}. {option}: {counts[i]}" for i, option in enumerate(options)]
        return f"Poll {poll_id} ({status}): {poll.get('question', '')} | " + " | ".join(
            parts
        )

    def _get_poll(self, server_name: str, channel: str, poll_id: str) -> dict | None:
        data = load_json_file(self.state_file, default=dict)
        poll = (
            _state_section(data)
            .get("polls", {})
            .get(_channel_key(server_name, channel), {})
            .get(poll_id)
        )
        return poll if isinstance(poll, dict) else None


def parse_poll_create(text: str) -> tuple[str, list[str]] | None:
    parts = [part.strip() for part in re.split(r"\s+\|\s+", text) if part.strip()]
    if len(parts) < 3:
        return None
    return parts[0], parts[1:]
