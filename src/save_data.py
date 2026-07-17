from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from settings import BASE_DIR


SAVE_PATH = BASE_DIR / "save_data.json"
WEB_STORAGE_KEY = "rou_rou_night_market_save_v1"


def _web_storage():
    if sys.platform != "emscripten":
        return None
    try:
        import platform

        return platform.window.localStorage
    except (AttributeError, ImportError):
        return None


def _backup_path() -> Path:
    return SAVE_PATH.with_suffix(".json.bak")


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("save root must be a JSON object")
    return data


def load_save() -> dict[str, Any]:
    storage = _web_storage()
    if storage is not None:
        try:
            raw = storage.getItem(WEB_STORAGE_KEY)
            if raw:
                data = json.loads(str(raw))
                return data if isinstance(data, dict) else {}
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
    for path in (SAVE_PATH, _backup_path()):
        if not path.exists():
            continue
        try:
            return _read_json(path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    return {}


def write_save(data: dict[str, Any]) -> None:
    storage = _web_storage()
    if storage is not None:
        try:
            storage.setItem(WEB_STORAGE_KEY, json.dumps(data, ensure_ascii=False))
        except (TypeError, ValueError):
            pass
        return
    temp_path = SAVE_PATH.with_suffix(".json.tmp")
    try:
        temp_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if SAVE_PATH.exists():
            try:
                if _read_json(SAVE_PATH):
                    _backup_path().write_text(SAVE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
            except (OSError, ValueError, json.JSONDecodeError):
                pass
        temp_path.replace(SAVE_PATH)
    except OSError:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)


def clear_save() -> None:
    storage = _web_storage()
    if storage is not None:
        try:
            storage.removeItem(WEB_STORAGE_KEY)
        except (TypeError, ValueError):
            pass
        return
    SAVE_PATH.unlink(missing_ok=True)
    SAVE_PATH.with_suffix(".json.tmp").unlink(missing_ok=True)
    _backup_path().unlink(missing_ok=True)
