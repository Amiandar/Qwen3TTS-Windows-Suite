from __future__ import annotations

import os
from pathlib import Path
from typing import Dict

from shared.settings_store import load_json, save_json


def config_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "Qwen3TTS"
    return Path.home() / ".qwen3tts"


def config_path() -> Path:
    return config_dir() / "config.json"


def load_runtime_config() -> Dict[str, str]:
    return load_json(config_path(), default={})


def save_runtime_config(data: Dict[str, str]) -> None:
    cfg = load_runtime_config()
    cfg.update(data)
    save_json(config_path(), cfg)
