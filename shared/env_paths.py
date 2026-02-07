from __future__ import annotations

import os
from pathlib import Path
from typing import Dict


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def build_cache_layout(cache_root: Path) -> Dict[str, Path]:
    hf_home = cache_root / "huggingface"
    hub = hf_home / "hub"
    return {
        "cache_root": cache_root,
        "hf_home": hf_home,
        "hf_hub_cache": hub,
        "transformers_cache": hf_home,
        "torch_home": cache_root / "torch",
        "pip_cache_dir": cache_root / "pip",
        "xdg_cache_home": cache_root,
    }


def apply_runtime_env(cache_root: Path, temp_root: Path, extra: Dict[str, str] | None = None) -> Dict[str, str]:
    cache_root = ensure_dir(cache_root)
    temp_root = ensure_dir(temp_root)
    layout = build_cache_layout(cache_root)

    for value in layout.values():
        ensure_dir(value)

    env_updates = {
        "TEMP": str(temp_root),
        "TMP": str(temp_root),
        "HF_HOME": str(layout["hf_home"]),
        "HF_HUB_CACHE": str(layout["hf_hub_cache"]),
        "HUGGINGFACE_HUB_CACHE": str(layout["hf_hub_cache"]),
        "TRANSFORMERS_CACHE": str(layout["transformers_cache"]),
        "TORCH_HOME": str(layout["torch_home"]),
        "PIP_CACHE_DIR": str(layout["pip_cache_dir"]),
        "XDG_CACHE_HOME": str(layout["xdg_cache_home"]),
    }
    if extra:
        env_updates.update({k: v for k, v in extra.items() if v})

    os.environ.update(env_updates)
    return env_updates
