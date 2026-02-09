from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import List, Tuple


def _is_within(path: Path, roots: List[Path]) -> bool:
    rp = path.resolve()
    for r in roots:
        try:
            rp.relative_to(r.resolve())
            return True
        except Exception:
            continue
    return False


def uninstall_from_manifest(manifest_path: Path, dry_run: bool = True) -> List[Tuple[str, str]]:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    allowed = [Path(p) for p in data.get("allowed_roots", [])]
    entries = data.get("entries", [])
    logs: List[Tuple[str, str]] = []

    for e in entries:
        p = Path(e["path"])
        kind = e.get("kind", "file")
        if not _is_within(p, allowed):
            logs.append(("skip", f"Outside allowed roots: {p}"))
            continue
        if not p.exists():
            logs.append(("ok", f"Already removed: {p}"))
            continue
        if dry_run:
            logs.append(("plan", f"Would remove {kind}: {p}"))
            continue
        try:
            if kind in {"dir", "owned_root"}:
                shutil.rmtree(p, ignore_errors=False)
            else:
                p.unlink(missing_ok=True)
            logs.append(("ok", f"Removed {kind}: {p}"))
        except Exception as ex:
            logs.append(("error", f"Failed to remove {p}: {ex}"))
    return logs
