from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


@dataclass
class ManifestEntry:
    path: str
    kind: str
    preexisted: bool


class InstallManifest:
    def __init__(self, install_root: Path):
        self.install_root = install_root
        self.path = install_root / "install_manifest.json"
        self.data = {
            "install_id": str(uuid.uuid4()),
            "created_at": "",
            "installer_version": "0.1.0",
            "install_root": str(install_root),
            "cache_root": "",
            "models_root": "",
            "env_prefix": "",
            "allowed_roots": [str(install_root)],
            "entries": [],
        }

    def load(self) -> None:
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

    def set_roots(self, cache_root: Path, models_root: Path, env_prefix: Path) -> None:
        self.data["cache_root"] = str(cache_root)
        self.data["models_root"] = str(models_root)
        self.data["env_prefix"] = str(env_prefix)
        for r in [cache_root, models_root, env_prefix]:
            if str(r) not in self.data["allowed_roots"]:
                self.data["allowed_roots"].append(str(r))

    def add_path(self, p: Path, kind: str = "file", preexisted: bool | None = None) -> None:
        p = p.resolve()
        if preexisted is None:
            preexisted = p.exists()
        e = {"path": str(p), "kind": kind, "preexisted": preexisted}
        if e not in self.data["entries"]:
            self.data["entries"].append(e)
