"""Unit tests for shared external-service lifecycle behavior."""

import importlib
from types import SimpleNamespace
from unittest.mock import Mock

import service_manager


def _bare_manager() -> service_manager.ServiceManager:
    manager = object.__new__(service_manager.ServiceManager)
    manager.services = {}
    manager._bot_manager = None
    return manager


def test_background_services_continue_when_one_start_fails(monkeypatch):
    manager = _bare_manager()
    fmi = SimpleNamespace(start=Mock(side_effect=RuntimeError("offline")))
    otiedote = SimpleNamespace(start_background=Mock())
    danger = SimpleNamespace(start=Mock())
    manager.services = {
        "fmi_warning": fmi,
        "otiedote": otiedote,
        "danger_announcement": danger,
    }
    warning = Mock()
    monkeypatch.setattr(service_manager.logger, "warning", warning)

    manager.start_background_services()

    fmi.start.assert_called_once()
    otiedote.start_background.assert_called_once()
    danger.start.assert_called_once()
    warning.assert_called_once_with("Could not start FMI warning monitor: offline")


def test_background_services_continue_when_one_stop_fails(monkeypatch):
    manager = _bare_manager()
    fmi = SimpleNamespace(stop=Mock(side_effect=RuntimeError("offline")))
    otiedote = SimpleNamespace(stop_background=Mock())
    danger = SimpleNamespace(stop=Mock())
    manager.services = {
        "fmi_warning": fmi,
        "otiedote": otiedote,
        "danger_announcement": danger,
    }
    warning = Mock()
    monkeypatch.setattr(service_manager.logger, "warning", warning)

    manager.stop_background_services()

    fmi.stop.assert_called_once()
    otiedote.stop_background.assert_called_once()
    danger.stop.assert_called_once()
    warning.assert_called_once_with(
        "Could not stop FMI warning monitor cleanly: offline"
    )


def test_reload_services_reinitializes_every_service_after_stopping_monitors(
    monkeypatch,
):
    manager = _bare_manager()
    manager.services = {"stale": object()}
    events = []
    manager.stop_background_services = Mock(side_effect=lambda: events.append("stop"))
    manager.start_background_services = Mock(side_effect=lambda: events.append("start"))
    names = [
        "weather",
        "gpt",
        "electricity",
        "youtube",
        "crypto",
        "alko",
        "drug",
        "prescription_interaction",
        "leet_detector",
        "fmi_warning",
        "otiedote",
        "danger_announcement",
        "dream",
    ]

    for name in names:
        setattr(
            manager,
            f"_initialize_{name}_service",
            lambda name=name: events.append(name),
        )
    manager._initialize_leet_detector = lambda: events.append("leet_detector")
    manager._initialize_fmi_warning_service = lambda: events.append("fmi_warning")
    manager._initialize_otiedote_service = lambda: events.append("otiedote")
    manager._initialize_danger_announcement_service = lambda: events.append(
        "danger_announcement"
    )
    monkeypatch.setattr(importlib, "reload", Mock())

    results = manager.reload_services()

    assert results == {name: "reloaded" for name in names}
    assert manager.services == {}
    assert events == ["stop", *names, "start"]


def test_service_availability_views_filter_none_values():
    manager = _bare_manager()
    active = object()
    manager.services = {"weather": active, "gpt": None}

    assert manager.get_service("weather") is active
    assert manager.is_service_available("weather") is True
    assert manager.is_service_available("gpt") is False
    assert manager.get_available_services() == {"weather": active}
    assert manager.get_unavailable_services() == ["gpt"]
