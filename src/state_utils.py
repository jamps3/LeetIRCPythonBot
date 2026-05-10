"""Shared JSON state persistence helpers."""

import json
import os
import shutil
import tempfile
from datetime import datetime
from typing import Any, Callable, Optional


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
) -> bool:
    """Load JSON, apply an updater, and save the result atomically."""
    data = load_json_file(file_path, default=default, encoding=encoding)
    updated = updater(data)
    if updated is not None:
        data = updated

    return save_json_atomic(
        file_path,
        data,
        backup=backup,
        update_timestamp=update_timestamp,
        encoding=encoding,
        ensure_ascii=ensure_ascii,
        indent=indent,
    )
