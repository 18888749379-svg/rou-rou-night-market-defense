from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from settings import BASE_DIR


SAVE_PATH = BASE_DIR / "save_data.json"


def _backup_path() -> Path:
    return SAVE_PATH.with_suffix(".json.bak")


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("save root must be a JSON object")
    return data


def load_save() -> dict[str, Any]:
    for path in (SAVE_PATH, _backup_path()):
        if not path.exists():
            continue
        try:
            return _read_json(path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    return {}


def write_save(data: dict[str, Any]) -> None:
    temp_path = SAVE_PATH.with_suffix(".json.tmp")
    try:
        temp_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if SAVE_PATH.exists():
            try:
                if _read_json(SAVE_PATH):
                    shutil.copy2(SAVE_PATH, _backup_path())
            except (OSError, ValueError, json.JSONDecodeError):
                pass
        temp_path.replace(SAVE_PATH)
    except OSError:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)


def clear_save() -> None:
    SAVE_PATH.unlink(missing_ok=True)
    SAVE_PATH.with_suffix(".json.tmp").unlink(missing_ok=True)
    _backup_path().unlink(missing_ok=True)
