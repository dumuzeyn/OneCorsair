"""Small, validated settings file. Stores paths and preferences, never cookies."""

import json
import os
import tempfile
from pathlib import Path

from engine_update import cache_directory


def settings_path():
    return cache_directory().parent / "settings.json"


def load_settings(path=None):
    defaults = {"output": str(Path.home() / "Music"), "quality": "192", "height": "1080",
                "mode": "audio", "language": "ru", "cookies": ""}
    try:
        values = json.loads(Path(path or settings_path()).read_text(encoding="utf-8"))
        if not isinstance(values, dict):
            return defaults
    except (OSError, ValueError, TypeError):
        return defaults
    choices = {"quality": {"128", "192", "256", "320"},
               "height": {"best", "2160", "1440", "1080", "720", "480", "360"},
               "mode": {"audio", "video"}, "language": {"ru", "en"}}
    for key in defaults:
        value = values.get(key)
        if not isinstance(value, str) or len(value) > 4096:
            continue
        if key in choices and value not in choices[key]:
            continue
        if key == "output" and not value.strip():
            continue
        defaults[key] = value
    return defaults


def save_settings(values, path=None):
    destination = Path(path or settings_path())
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=destination.parent,
                                     suffix=".tmp", delete=False) as target:
        temporary = Path(target.name)
        # Allowlist prevents accidental storage of logs, links or cookie contents.
        json.dump({key: values[key] for key in ("output", "quality", "height", "mode", "language", "cookies")},
                  target, ensure_ascii=False)
    try:
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
