# Auto-loaded by pytest to add diagnostics for flaky command_loader imports.
# This helps identify which test breaks the import or mutates sys.modules.

import datetime as _dt
import importlib as _importlib
import importlib as _il
import os as _os
import sys as _sys
import traceback as _tb
from types import ModuleType as _ModuleType

import pytest as _pytest

_LOG_PATH = _os.path.join(_os.getcwd(), ".pytest_import_diag.log")


def _log(line: str) -> None:
    try:
        ts = _dt.datetime.now().isoformat()
        cur = _os.environ.get("PYTEST_CURRENT_TEST", "<unknown>")
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [{cur}] {line}\n")
    except Exception:
        # Never break test run due to diagnostics
        pass


def _check_and_repair_command_loader() -> None:
    """Ensure command_loader module is importable and has required attributes.

    If the module is missing or corrupted in sys.modules, attempt to repair
    by removing the bad entry and re-importing from source. Log all events.
    """
    try:
        mod = _sys.modules.get("command_loader")

        def _has_required(m) -> bool:
            return hasattr(m, "process_console_command") and hasattr(
                m, "enhanced_process_irc_message"
            )

        if mod is not None and not _has_required(mod):
            _log(
                "command_loader present but missing required attributes; "
                f"has_console={hasattr(mod, 'process_console_command')} "
                f"has_irc={hasattr(mod, 'enhanced_process_irc_message')} "
                f"type={type(mod)} repr={repr(mod)[:120]}"
            )
            try:
                del _sys.modules["command_loader"]
                _importlib.invalidate_caches()
                mod = _importlib.import_module("command_loader")
                _log(
                    "command_loader repaired via re-import; has_console="
                    + str(hasattr(mod, "process_console_command"))
                    + " has_irc="
                    + str(hasattr(mod, "enhanced_process_irc_message"))
                )
            except Exception:
                _log("command_loader repair failed:\n" + _tb.format_exc())
                return

        # If not in sys.modules or first-time import, ensure it loads and has attributes
        if mod is None:
            try:
                mod = _importlib.import_module("command_loader")
                _log(
                    "command_loader imported; has_console="
                    + str(hasattr(mod, "process_console_command"))
                    + " has_irc="
                    + str(hasattr(mod, "enhanced_process_irc_message"))
                )
            except Exception:
                _log("command_loader import failed:\n" + _tb.format_exc())
                return

        # Final sanity
        if not _has_required(mod):
            _log(
                "command_loader still missing required attributes after repair: "
                f"has_console={hasattr(mod, 'process_console_command')} "
                f"has_irc={hasattr(mod, 'enhanced_process_irc_message')}"
            )
    except Exception:
        _log("_check_and_repair_command_loader exception:\n" + _tb.format_exc())


# Pytest hooks


def pytest_runtest_setup(item):
    _check_and_repair_command_loader()


def pytest_sessionstart(session):
    # Start of session marker
    _log("=== pytest session start ===")


def pytest_sessionfinish(session, exitstatus):
    _log(f"=== pytest session finish: {exitstatus} ===")


# ---------------------------------------------------------------------------
# Isolation fixture to restore commonly patched modules between tests
# ---------------------------------------------------------------------------


def _ensure_real_module(module_name: str):
    mod = _sys.modules.get(module_name)
    if not isinstance(mod, _ModuleType) or getattr(mod, "__spec__", None) is None:
        _log(f"Restoring real module for {module_name} (was {type(mod)})")
        _sys.modules.pop(module_name, None)
        try:
            mod = _il.import_module(module_name)
        except Exception:
            _log(f"Failed to import real module: {module_name}\n" + _tb.format_exc())
            mod = None
    return mod


@_pytest.fixture(autouse=True)
def _restore_external_modules_between_tests():
    # Ensure requests module is the real one
    real_requests = _ensure_real_module("requests")
    # Ensure our IPFS service module is real (some tests replace it)
    _ensure_real_module("services.ipfs_service")

    yield

    # Restore again after each test
    if real_requests is not None:
        _sys.modules["requests"] = real_requests
    else:
        _ensure_real_module("requests")
    _ensure_real_module("services.ipfs_service")
