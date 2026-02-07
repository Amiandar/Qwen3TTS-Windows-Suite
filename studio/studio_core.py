from __future__ import annotations

import datetime as dt
import json
import subprocess
from pathlib import Path
from typing import Callable, Dict, List

from shared.hf_models import CANONICAL_MODELS
from shared.runtime_config import load_runtime_config, save_runtime_config
from shared.settings_store import load_json, save_json


class StudioCore:
    def __init__(self):
        self.runtime_cfg = load_runtime_config()
        self.install_root = Path(self.runtime_cfg.get("install_root") or Path.cwd())

        self.logs_dir = self.install_root / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.logs_dir / f"studio_{dt.datetime.now():%Y%m%d_%H%M%S}.log"
        self.settings_path = self.install_root / "studio_settings.json"
        self.settings = load_json(self.settings_path, default={})

    def set_install_root(self, install_root: Path) -> None:
        self.install_root = install_root
        cfg = load_runtime_config()
        cfg.setdefault("version", "0.1.0")
        cfg["install_root"] = str(install_root)
        if "venv_python" not in cfg:
            cfg["venv_python"] = str(install_root / "envs" / "qwen3-tts" / "python.exe")
        save_runtime_config(cfg)
        self.runtime_cfg = cfg

    def log(self, line: str) -> None:
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def save_settings(self, data: Dict):
        self.settings.update(data)
        save_json(self.settings_path, self.settings)

    def installed_models(self) -> List[str]:
        cache_root = Path(self.runtime_cfg.get("cache_root") or (self.install_root / "cache"))
        hub = cache_root / "huggingface" / "hub"
        if not hub.exists():
            return []
        names = []
        for m in CANONICAL_MODELS:
            tag = "models--" + m.model_id.replace("/", "--")
            if any(p.name.startswith(tag) for p in hub.iterdir()):
                names.append(m.model_id)
        return names

    def resolve_runtime_python(self) -> Path:
        cfg = load_runtime_config()
        py = Path(cfg.get("venv_python", ""))
        if py.exists():
            return py
        fallback = Path(cfg.get("install_root", "")) / "envs" / "qwen3-tts" / "python.exe"
        if fallback.exists():
            return fallback
        raise FileNotFoundError("Runtime python not found. Run Installer or select install root.")

    def backend_script(self) -> Path:
        cfg = load_runtime_config()
        install_root = Path(cfg.get("install_root", self.install_root))
        script = install_root / "app" / "shared" / "runtime_backend.py"
        if script.exists():
            return script
        local = Path(__file__).resolve().parent.parent / "shared" / "runtime_backend.py"
        if local.exists():
            return local
        raise FileNotFoundError("runtime_backend.py not found")

    def generate_book(self, model_id: str, params: Dict, progress_cb: Callable[[int, int, str], None]) -> None:
        cfg = load_runtime_config()
        request = {
            "action": "generate",
            "model_id": model_id,
            "cache_root": cfg.get("cache_root", str(Path(cfg.get("install_root", self.install_root)) / "cache")),
            "temp_root": cfg.get("temp_root", str(Path(cfg.get("install_root", self.install_root)) / "_tmp")),
            "params": params,
        }
        req_path = self.install_root / "_tmp" / "studio_request.json"
        req_path.parent.mkdir(parents=True, exist_ok=True)
        req_path.write_text(json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8")

        cmd = [str(self.resolve_runtime_python()), str(self.backend_script()), "--request", str(req_path)]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        total = 1
        while True:
            line = proc.stdout.readline() if proc.stdout else ""
            if not line:
                if proc.poll() is not None:
                    break
                continue
            line = line.strip()
            self.log(line)
            try:
                msg = json.loads(line)
            except Exception:
                progress_cb(0, total, line)
                continue
            if msg.get("event") == "progress":
                total = int(msg.get("total", total))
                progress_cb(int(msg.get("current", 0)), total, msg.get("message", ""))
            elif msg.get("event") == "done" and not msg.get("ok", False):
                raise RuntimeError(msg.get("error", "Backend failed"))

        if proc.returncode not in (0, None):
            raise RuntimeError(f"Backend exit code {proc.returncode}")
