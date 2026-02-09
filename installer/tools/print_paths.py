from __future__ import annotations

from pathlib import Path

from shared.app_paths import debug_resource_roots


def main() -> int:
    rows = debug_resource_roots()
    for name, path, exists in rows:
        print(f"{name}: {path} exists={exists}")

    checks = [
        ("requirements_runtime", Path(rows[1][1]) / "requirements_runtime.txt"),
        ("runtime_backend", Path(rows[1][1]) / "shared" / "runtime_backend.py"),
    ]
    ok = True
    for name, p in checks:
        ex = p.exists()
        print(f"{name}: {p} exists={ex}")
        ok = ok and ex
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
