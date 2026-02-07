from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def load_json(path: Path, default: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if not path.exists():
        return default.copy() if default else {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default.copy() if default else {}


def save_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
