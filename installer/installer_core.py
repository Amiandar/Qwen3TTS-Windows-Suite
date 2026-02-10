from __future__ import annotations

import datetime as dt
import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from threading import Event
from typing import Callable, List, Optional, Tuple

from shared.app_paths import debug_resource_roots, get_internal_dir, get_shared_dir
from shared.env_paths import apply_runtime_env
from shared.hf_models import download_models, query_models
from shared.hw_detect import HardwareInfo, detect_hardware
from shared.install_manifest import InstallManifest
from shared.runtime_config import save_runtime_config
from shared.settings_store import load_json, save_json

StageCb = Callable[[str, str, int, int, str], None] | None


class InstallerCore:
    def __init__(self, install_root: Path):
        self.install_root = install_root
        self.logs_dir = install_root / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.logs_dir / f"installer_{dt.datetime.now():%Y%m%d_%H%M%S}.log"
        self.settings_path = install_root / "installer_settings.json"
        self.settings = load_json(self.settings_path, default={})
        self.manifest = InstallManifest(install_root)
        self.manifest.load()
        self.cancel_event = Event()
        self._current_proc: subprocess.Popen | None = None

    def log(self, line: str) -> None:
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def _emit(self, status_cb: Callable[[str], None] | None, line: str) -> None:
        self.log(line)
        if status_cb:
            status_cb(line)

    def _stage(self, cb: StageCb, stage_id: str, status: str, current: int = 0, total: int = 100, message: str = "") -> None:
        if cb:
            cb(stage_id, status, current, total, message)

    def request_cancel(self) -> None:
        self.cancel_event.set()
        proc = self._current_proc
        if proc and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    def clear_cancel(self) -> None:
        self.cancel_event.clear()

    def startup_self_check(self) -> None:
        rows = debug_resource_roots()
        for name, path, exists in rows:
            self.log(f"{name}={path} exists={exists}")
        req = self.resolve_requirements_runtime_path()
        backend = self.resolve_runtime_backend_script_path()
        self.log(f"resource_check requirements_runtime={req}")
        self.log(f"resource_check runtime_backend={backend}")

    def _run_command(self, cmd: List[str], status_cb: Callable[[str], None] | None = None, label: str = "command", attempts: int = 1) -> subprocess.CompletedProcess:
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        last = subprocess.CompletedProcess(cmd, 1, "", "")
        for attempt in range(1, attempts + 1):
            if self.cancel_event.is_set():
                raise RuntimeError("Cancelled by user")
            self._emit(status_cb, f"Attempt {attempt}/{attempts}: {label}")
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=creationflags,
            )
            self._current_proc = proc
            out_lines: list[str] = []
            try:
                if proc.stdout is not None:
                    for raw in iter(proc.stdout.readline, ""):
                        if not raw:
                            break
                        line = raw.rstrip("\n")
                        out_lines.append(line)
                        self._emit(status_cb, f"[{label}] {line}")
                        if self.cancel_event.is_set():
                            self._emit(status_cb, f"[{label}] cancellation requested")
                            try:
                                proc.terminate()
                                proc.wait(timeout=2)
                            except Exception:
                                proc.kill()
                            return subprocess.CompletedProcess(cmd, 130, "\n".join(out_lines), "cancelled")
                rc = proc.wait()
            finally:
                self._current_proc = None
            stdout = "\n".join(out_lines)
            last = subprocess.CompletedProcess(cmd, rc, stdout, "")
            if rc == 0:
                return last
            self._emit(status_cb, f"[{label}] failed with code {rc}")
        return last

    def resolve_requirements_runtime_path(self) -> Path:
        internal = get_internal_dir()
        candidates = [
            Path(__file__).resolve().parent.parent / "requirements_runtime.txt",
            Path(sys.executable).resolve().parent / "requirements_runtime.txt",
            Path(sys.executable).resolve().parent / "_internal" / "requirements_runtime.txt",
            internal / "requirements_runtime.txt",
        ]
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            base = Path(str(meipass))
            candidates.append(base / "requirements_runtime.txt")
            candidates.append(base / "_internal" / "requirements_runtime.txt")
        for c in candidates:
            if c.exists():
                return c
        raise RuntimeError("Missing requirements_runtime.txt in packaged app")

    def resolve_runtime_backend_script_path(self) -> Path:
        shared_dir = get_shared_dir()
        candidates = [
            Path(__file__).resolve().parent.parent / "shared" / "runtime_backend.py",
            Path(sys.executable).resolve().parent / "shared" / "runtime_backend.py",
            Path(sys.executable).resolve().parent / "_internal" / "shared" / "runtime_backend.py",
            shared_dir / "runtime_backend.py",
        ]
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            base = Path(str(meipass))
            candidates.append(base / "shared" / "runtime_backend.py")
            candidates.append(base / "_internal" / "shared" / "runtime_backend.py")
        for c in candidates:
            if c.exists():
                return c
        raise RuntimeError("Missing runtime backend script")

    def detect_python(self) -> Tuple[Optional[str], Optional[str]]:
        for cmd in (["py", "-3.11", "-V"], ["py", "-3", "-V"], ["python", "-V"]):
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, check=False)
                version = (r.stdout or r.stderr).strip()
                if r.returncode == 0 and "Python 3." in version:
                    major_minor = version.split()[1].split(".")[:2]
                    if tuple(map(int, major_minor)) >= (3, 11):
                        return " ".join(cmd[:-1]), version
            except Exception:
                continue
        return None, None

    def install_python_per_user(self, target_dir: Path, temp_root: Path, status_cb: Callable[[str], None]) -> Path:
        status_cb("Trying winget Python installation...")
        winget_cmd = ["winget", "install", "Python.Python.3.11", "--scope", "user", "--location", str(target_dir), "--silent", "--accept-package-agreements", "--accept-source-agreements"]
        winget = self._run_command(winget_cmd, status_cb=status_cb, label="winget-python", attempts=1)
        if winget.returncode != 0:
            status_cb("Winget failed, falling back to python.org installer...")
            py_installer = temp_root / "python-installer.exe"
            urllib.request.urlretrieve("https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe", py_installer)
            cmd = [str(py_installer), "/quiet", "InstallAllUsers=0", "PrependPath=0", "Include_pip=1", f"TargetDir={target_dir}"]
            proc = self._run_command(cmd, status_cb=status_cb, label="python-org-installer", attempts=1)
            if proc.returncode != 0:
                raise RuntimeError("Python install failed")

        py = target_dir / "python.exe"
        if not py.exists():
            raise RuntimeError("Could not resolve installed python.exe in selected folder")

        for check in ([str(py), "-V"], [str(py), "-m", "pip", "-V"]):
            r = self._run_command(check, status_cb=status_cb, label="python-check", attempts=1)
            if r.returncode != 0:
                raise RuntimeError(f"Check failed: {' '.join(check)}")
        self.settings["bootstrap_python"] = str(py)
        save_json(self.settings_path, self.settings)
        return py

    def setup_micromamba_env(self, cache_root: Path, temp_root: Path, enable_gpu: bool, status_cb: Callable[[str], None], stage_cb: StageCb = None) -> Path:
        self.clear_cancel()
        self._stage(stage_cb, "B1", "running", 0, 100, "Preparing micromamba")
        env = apply_runtime_env(cache_root=cache_root, temp_root=temp_root)
        self.log("ENV=" + json.dumps(env, ensure_ascii=False))
        mm_dir = self.install_root / "tools"
        mm_dir.mkdir(parents=True, exist_ok=True)
        mm_exe = mm_dir / "micromamba.exe"
        if not mm_exe.exists():
            status_cb("Downloading micromamba...")
            urllib.request.urlretrieve("https://github.com/mamba-org/micromamba-releases/releases/latest/download/micromamba-win-64", mm_exe)
        self._stage(stage_cb, "B1", "done", 100, 100, "Micromamba ready")

        runtime_req = self.resolve_requirements_runtime_path()
        backend_script = self.resolve_runtime_backend_script_path()
        self._emit(status_cb, f"Resolved runtime requirements: {runtime_req}")
        self._emit(status_cb, f"Resolved runtime backend: {backend_script}")

        env_path = self.install_root / "envs" / "qwen3-tts"
        env_pre = env_path.exists()
        self._stage(stage_cb, "B2", "running", 0, 100, "Creating/updating runtime env")
        create_cmd = [str(mm_exe), "create", "-y", "-p", str(env_path), "python=3.11", "pip", "ffmpeg", "pyside6", "libsndfile"]
        create_res = self._run_command(create_cmd, status_cb=status_cb, label="micromamba-create", attempts=2)
        if create_res.returncode != 0:
            self._stage(stage_cb, "B2", "failed", 0, 100, "micromamba create failed")
            if create_res.returncode == 130:
                raise RuntimeError("Cancelled by user")
            raise RuntimeError("Failed to create runtime environment.")
        self._stage(stage_cb, "B2", "done", 100, 100, "Runtime env ready")

        pip_base = [str(mm_exe), "run", "-p", str(env_path), "python", "-m", "pip"]
        self._stage(stage_cb, "C1", "running", 0, 100, "Upgrading pip")
        p1 = self._run_command(pip_base + ["install", "--upgrade", "pip"], status_cb=status_cb, label="pip-upgrade", attempts=2)
        if p1.returncode != 0:
            self._stage(stage_cb, "C1", "failed", 0, 100, "pip upgrade failed")
            raise RuntimeError("Failed to upgrade pip inside runtime environment.")
        self._stage(stage_cb, "C1", "done", 100, 100, "Pip ready")

        self._stage(stage_cb, "C2", "running", 0, 100, "Installing runtime requirements")
        p2 = self._run_command(pip_base + ["install", "-r", str(runtime_req)], status_cb=status_cb, label="pip-runtime-req", attempts=2)
        if p2.returncode != 0:
            self._stage(stage_cb, "C2", "failed", 0, 100, "requirements install failed")
            raise RuntimeError("Failed to install requirements_runtime.txt")
        self._stage(stage_cb, "C2", "done", 100, 100, "Runtime requirements installed")

        status_cb("Installing torch/runtime acceleration packages...")
        torch_cmd = pip_base + (["install", "torch", "onnxruntime-gpu"] if enable_gpu else ["install", "torch", "onnxruntime", "--index-url", "https://download.pytorch.org/whl/cpu"])
        t = self._run_command(torch_cmd, status_cb=status_cb, label="pip-torch-optimized", attempts=2)
        if t.returncode != 0:
            status_cb("GPU/CPU optimized package set failed, using generic fallback...")
            fallback = self._run_command(pip_base + ["install", "torch", "onnxruntime"], status_cb=status_cb, label="pip-torch-fallback", attempts=1)
            if fallback.returncode != 0:
                raise RuntimeError("Failed to install torch/onnxruntime runtime packages.")

        self._stage(stage_cb, "C3", "running", 0, 100, "Smoke imports")
        smoke_cmd = [str(mm_exe), "run", "-p", str(env_path), "python", "-c", "import torch, onnxruntime, huggingface_hub, PySide6"]
        smoke = self._run_command(smoke_cmd, status_cb=status_cb, label="smoke-imports", attempts=1)
        if smoke.returncode != 0:
            self._emit(status_cb, "Smoke imports failed, trying to repair huggingface_hub...")
            self._run_command(pip_base + ["install", "huggingface_hub"], status_cb=status_cb, label="pip-install-hf-hub", attempts=1)
            smoke_retry = self._run_command(smoke_cmd, status_cb=status_cb, label="smoke-imports-retry", attempts=1)
            if smoke_retry.returncode != 0:
                self._stage(stage_cb, "C3", "failed", 0, 100, "Smoke imports failed")
                raise RuntimeError("Runtime import check failed")
        self._stage(stage_cb, "C3", "done", 100, 100, "Smoke imports passed")

        self._stage(stage_cb, "B3", "running", 0, 100, "Writing cache/temp redirects")
        self._deploy_backend_script(backend_script)
        self._write_runtime_config(env_path, cache_root, temp_root)
        self._stage(stage_cb, "B3", "done", 100, 100, "Cache/temp redirects configured")

        self.settings["env_path"] = str(env_path)
        self.settings["cache_root"] = str(cache_root)
        self.settings["temp_root"] = str(temp_root)
        save_json(self.settings_path, self.settings)

        self._stage(stage_cb, "E1", "running", 0, 100, "Writing manifest")
        self.manifest.set_roots(cache_root=cache_root, models_root=cache_root / "huggingface" / "hub", env_prefix=env_path)
        self.manifest.add_path(env_path, kind="owned_root", preexisted=env_pre)
        self.manifest.save()
        self._stage(stage_cb, "E1", "done", 100, 100, "Manifest updated")
        self._stage(stage_cb, "E2", "done", 100, 100, "Finalize")
        return env_path

    def verify_runtime_installation(self, cache_root: Path, temp_root: Path, status_cb: Callable[[str], None]) -> bool:
        self.clear_cancel()
        apply_runtime_env(cache_root=cache_root, temp_root=temp_root)
        mm_exe = self.install_root / "tools" / "micromamba.exe"
        env_path = self.install_root / "envs" / "qwen3-tts"

        ok = True
        status_cb("Verify: checking micromamba binary...")
        if not mm_exe.exists():
            status_cb(f"FAIL: micromamba missing at {mm_exe}")
            return False
        if self._run_command([str(mm_exe), "--version"], status_cb=status_cb, label="verify-micromamba", attempts=1).returncode != 0:
            return False

        status_cb("Verify: checking runtime env...")
        if not env_path.exists():
            status_cb(f"FAIL: runtime env missing at {env_path}")
            ok = False

        verify_cmds = [
            ([str(mm_exe), "run", "-p", str(env_path), "python", "-c", "import sys; print(sys.executable)"], "verify-python"),
            ([str(mm_exe), "run", "-p", str(env_path), "python", "-c", "import torch, onnxruntime, huggingface_hub, PySide6"], "verify-imports"),
            ([str(mm_exe), "run", "-p", str(env_path), "python", "-m", "pip", "--version"], "verify-pip"),
        ]
        for cmd, label in verify_cmds:
            res = self._run_command(cmd, status_cb=status_cb, label=label, attempts=1)
            if res.returncode != 0:
                ok = False

        free_gb = shutil.disk_usage(self.install_root).free / (1024**3)
        status_cb(f"Verify: free disk space {free_gb:.1f} GB")
        if free_gb < 5.0:
            status_cb("WARN: free disk space below 5 GB")
        status_cb("Verify: OK" if ok else "Verify: FAIL")
        return ok

    def _deploy_backend_script(self, src: Path) -> None:
        dst = self.install_root / "app" / "shared" / "runtime_backend.py"
        pre = dst.exists()
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())
        self.manifest.add_path(dst, kind="file", preexisted=pre)
        self.manifest.save()

    def _write_runtime_config(self, env_path: Path, cache_root: Path, temp_root: Path) -> None:
        save_runtime_config({
            "install_root": str(self.install_root),
            "python": str(self.install_root / "python" / "python.exe"),
            "venv_python": str(env_path / "python.exe"),
            "cache_root": str(cache_root),
            "temp_root": str(temp_root),
            "version": "0.1.0",
        })

    def get_hardware(self) -> HardwareInfo:
        return detect_hardware()

    def get_models(self) -> List[str]:
        return [m.model_id for m in query_models()]

    def download_selected_models(self, model_ids: List[str], status_cb: Callable[[str], None], model_progress_cb: Callable[[str, int, int, str], None] | None = None, cancel_event: Event | None = None) -> None:
        cache_raw = str(self.settings.get("cache_root", "")).strip()
        if not cache_raw:
            raise RuntimeError("Cache root is not configured. Run environment setup first.")
        cache_root = Path(cache_raw)
        apply_runtime_env(cache_root=cache_root, temp_root=Path(self.settings.get("temp_root", str(self.install_root / "_tmp"))))
        model_root = cache_root / "models"
        model_root.mkdir(parents=True, exist_ok=True)

        def on_progress(model_id: str, current: int, total: int, text: str) -> None:
            status_cb(f"{model_id}: {text} ({current}/{total})")
            if model_progress_cb:
                model_progress_cb(model_id, current, total, text)

        records = download_models(model_ids, progress_cb=on_progress, local_dir=str(model_root), cancel_event=cancel_event)
        for rec in records:
            path_obj = Path(rec.local_path)
            self.manifest.add_path(path_obj, kind="dir", preexisted=False)
        self.manifest.save()
