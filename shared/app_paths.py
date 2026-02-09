from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Tuple


def get_app_root() -> Path:
    meipass = getattr(sys, "_MEIPASS", "")
    if meipass:
        return Path(str(meipass)).resolve()
    return Path(__file__).resolve().parent.parent


def get_internal_dir() -> Path:
    app_root = get_app_root()
    if app_root.name.lower() == "_internal":
        return app_root
    candidate = app_root / "_internal"
    if candidate.exists():
        return candidate
    # dev fallback: resources at repo root
    return app_root


def get_shared_dir() -> Path:
    internal = get_internal_dir()
    cand = internal / "shared"
    if cand.exists():
        return cand
    return get_app_root() / "shared"


def debug_resource_roots() -> List[Tuple[str, Path, bool]]:
    app_root = get_app_root()
    internal = get_internal_dir()
    shared = get_shared_dir()
    return [
        ("app_root", app_root, app_root.exists()),
        ("internal_dir", internal, internal.exists()),
        ("shared_dir", shared, shared.exists()),
    ]
