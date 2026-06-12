"""Tests for services package import behavior."""

import os
import subprocess
import sys
from pathlib import Path


def _run_import_check(code: str) -> None:
    """Run import checks in a child process to avoid sys.modules test bleed."""
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    src_path = str(repo_root / "src")
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        src_path
        if not existing_pythonpath
        else os.pathsep.join([src_path, existing_pythonpath])
    )
    subprocess.run(  # noqa: S603 - fixed test subprocess, snippets are local constants.
        [sys.executable, "-c", code],
        cwd=repo_root,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def test_otiedote_import_does_not_eagerly_import_feedparser():
    """Importing one service submodule should not import FMI/feedparser."""
    _run_import_check(
        """
import importlib
import sys

importlib.import_module("services.otiedote_json_service")

assert "services.fmi_warning_service" not in sys.modules
assert "feedparser" not in sys.modules
"""
    )


def test_fmi_service_exports_are_lazy_but_available():
    """Package-level FMI exports should import on first access."""
    _run_import_check(
        """
import importlib
import sys

services = importlib.import_module("services")

assert "services.fmi_warning_service" not in sys.modules
assert services.FMIWarningService is not None
assert services.create_fmi_warning_service is not None
assert "services.fmi_warning_service" in sys.modules
"""
    )
