"""Shared JSON state persistence helpers."""

import json
import os
import shutil
import tempfile
import threading
from datetime import datetime
from typing import Any, Callable, Optional

_locks_guard = threading.Lock()
_file_locks: dict[str, threading.RLock] = {}


def _get_file_lock(file_path: str) -> threading.RLock:
    normalized = os.path.abspath(os.path.normpath(file_path))
    with _locks_guard:
        return _file_locks.setdefault(normalized, threading.RLock())


def _make_default(default: Any) -> Any:
    return default() if callable(default) else default


def load_json_file(
    file_path: str,
    default: Any = None,
    *,
    encoding: str = "utf-8",
) -> Any:
    """Load a JSON file, returning default if the file is missing or invalid."""
    if not os.path.exists(file_path):
        return _make_default(default)

    try:
        with open(file_path, "r", encoding=encoding) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError):
        return _make_default(default)


def save_json_atomic(
    file_path: str,
    data: Any,
    *,
    backup: bool = False,
    update_timestamp: bool = True,
    timestamp_key: str = "last_updated",
    encoding: str = "utf-8",
    ensure_ascii: bool = False,
    indent: int = 2,
) -> bool:
    """Write JSON through a same-directory temp file and atomic replace."""
    with _get_file_lock(file_path):
        return _save_json_atomic_unlocked(
            file_path,
            data,
            backup=backup,
            update_timestamp=update_timestamp,
            timestamp_key=timestamp_key,
            encoding=encoding,
            ensure_ascii=ensure_ascii,
            indent=indent,
        )


def _save_json_atomic_unlocked(
    file_path: str,
    data: Any,
    *,
    backup: bool = False,
    update_timestamp: bool = True,
    timestamp_key: str = "last_updated",
    encoding: str = "utf-8",
    ensure_ascii: bool = False,
    indent: int = 2,
) -> bool:
    temp_path: Optional[str] = None
    try:
        target_dir = os.path.dirname(file_path) or "."
        os.makedirs(target_dir, exist_ok=True)

        if backup and os.path.exists(file_path):
            shutil.copy2(file_path, f"{file_path}.backup")

        if update_timestamp and isinstance(data, dict):
            data[timestamp_key] = datetime.now().isoformat()

        with tempfile.NamedTemporaryFile(
            "w",
            delete=False,
            dir=target_dir,
            suffix=".tmp",
            encoding=encoding,
        ) as tmp:
            temp_path = tmp.name
            json.dump(data, tmp, ensure_ascii=ensure_ascii, indent=indent)
            tmp.flush()
            os.fsync(tmp.fileno())

        os.replace(temp_path, file_path)
        temp_path = None
        return True
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


def update_json_file(
    file_path: str,
    updater: Callable[[Any], Optional[Any]],
    *,
    default: Any = None,
    backup: bool = False,
    update_timestamp: bool = True,
    encoding: str = "utf-8",
    ensure_ascii: bool = False,
    indent: int = 2,
    strict: bool = False,
) -> bool:
    """Load JSON, apply an updater, and save the result atomically."""
    with _get_file_lock(file_path):
        if strict and os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError, ValueError) as exc:
                raise ValueError(
                    f"Refusing to overwrite invalid JSON: {file_path}"
                ) from exc
        else:
            data = load_json_file(file_path, default=default, encoding=encoding)

        updated = updater(data)
        if updated is not None:
            data = updated

        return _save_json_atomic_unlocked(
            file_path,
            data,
            backup=backup,
            update_timestamp=update_timestamp,
            encoding=encoding,
            ensure_ascii=ensure_ascii,
            indent=indent,
        )


def backup_json_atomic(file_path: str, suffix: str, *, encoding: str = "utf-8") -> bool:
    """Copy a valid JSON file to a sibling backup using atomic replacement."""
    with _get_file_lock(file_path):
        with open(file_path, "r", encoding=encoding) as f:
            json.load(f)
        target = f"{file_path}.{suffix}"
        target_dir = os.path.dirname(target) or "."
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                "wb", delete=False, dir=target_dir, suffix=".tmp"
            ) as tmp:
                temp_path = tmp.name
                with open(file_path, "rb") as source:
                    shutil.copyfileobj(source, tmp)
                tmp.flush()
                os.fsync(tmp.fileno())
            os.replace(temp_path, target)
            temp_path = None
            return True
        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
