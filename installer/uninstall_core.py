from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Callable, List, Tuple


def _is_within(path: Path, roots: List[Path]) -> bool:
    rp = path.resolve()
    for r in roots:
        try:
            rp.relative_to(r.resolve())
            return True
        except Exception:
            continue
    return False


def uninstall_from_manifest(manifest_path: Path, dry_run: bool = True, delete_caches: bool = False, stage_cb: Callable[[str, int, int, str], None] | None = None) -> List[Tuple[str, str]]:
    if stage_cb:
        stage_cb("manifest_load", 0, 100, "Loading manifest")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if stage_cb:
        stage_cb("manifest_load", 100, 100, "Manifest loaded")
    allowed = [Path(p) for p in data.get("allowed_roots", [])]
    entries = data.get("entries", [])
    logs: List[Tuple[str, str]] = []

    if stage_cb:
        stage_cb("stop_processes", 100, 100, "No process manager configured")

    if stage_cb:
        stage_cb("delete_env", 0, 100, "Deleting tracked paths")
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
    if stage_cb:
        stage_cb("delete_env", 100, 100, "Tracked paths processed")

    if stage_cb:
        stage_cb("delete_caches_optional", 0, 100, "Cache cleanup")
    if delete_caches:
        for key in ("cache_root", "models_root"):
            p = Path(data.get(key, ""))
            if p.exists() and _is_within(p, allowed):
                if dry_run:
                    logs.append(("plan", f"Would remove cache root: {p}"))
                else:
                    shutil.rmtree(p, ignore_errors=True)
                    logs.append(("ok", f"Removed cache root: {p}"))
    if stage_cb:
        stage_cb("delete_caches_optional", 100, 100, "Cache stage completed")
        stage_cb("cleanup", 100, 100, "Cleanup done")
    return logs
