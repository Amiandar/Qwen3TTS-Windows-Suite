from __future__ import annotations

import json
import tempfile
from pathlib import Path

from installer.uninstall_core import uninstall_from_manifest


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        keep = root / "keep.txt"
        keep.write_text("keep", encoding="utf-8")
        owned = root / "owned"
        owned.mkdir()
        f = owned / "a.txt"
        f.write_text("a", encoding="utf-8")

        manifest = root / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "allowed_roots": [str(root)],
                    "entries": [
                        {"path": str(f), "kind": "file", "preexisted": False},
                        {"path": str(owned), "kind": "dir", "preexisted": False},
                    ],
                }
            ),
            encoding="utf-8",
        )

        dry = uninstall_from_manifest(manifest, dry_run=True)
        assert any("Would remove" in msg for _, msg in dry)
        real = uninstall_from_manifest(manifest, dry_run=False)
        assert not owned.exists()
        assert keep.exists()
        print("uninstall_smoke_ok", len(dry), len(real))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
