from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from shared.env_paths import apply_runtime_env
from shared.hf_models import download_models, query_models
from shared.hw_detect import HardwareInfo, detect_hardware
from shared.runtime_config import save_runtime_config
from shared.settings_store import load_json, save_json


class InstallerCore:
    def __init__(self, install_root: Path):
        self.install_root = install_root
        self.logs_dir = install_root / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.logs_dir / f"installer_{dt.datetime.now():%Y%m%d_%H%M%S}.log"
        self.settings_path = install_root / "installer_settings.json"
        self.settings = load_json(self.settings_path, default={})

    def log(self, line: str) -> None:
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def _emit(self, status_cb: Callable[[str], None] | None, line: str) -> None:
        self.log(line)
        if status_cb:
            status_cb(line)

    def _run_command(
        self,
        cmd: List[str],
        status_cb: Callable[[str], None] | None = None,
        label: str = "command",
        attempts: int = 1,
    ) -> subprocess.CompletedProcess:
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        last: subprocess.CompletedProcess | None = None
        for attempt in range(1, attempts + 1):
            self._emit(status_cb, f"Attempt {attempt}/{attempts}: {label}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                creationflags=creationflags,
            )
            last = result
            if result.stdout.strip():
                self._emit(status_cb, f"[{label}] stdout:\n{result.stdout.strip()}")
            if result.stderr.strip():
                self._emit(status_cb, f"[{label}] stderr:\n{result.stderr.strip()}")
            if result.returncode == 0:
                return result
            self._emit(status_cb, f"[{label}] failed with code {result.returncode}")
        assert last is not None
        return last

    def resolve_requirements_runtime_path(self) -> Path:
        candidates = [
            Path(__file__).resolve().parent.parent / "requirements_runtime.txt",
            Path(sys.executable).resolve().parent / "requirements_runtime.txt",
            Path(sys.executable).resolve().parent / "_internal" / "requirements_runtime.txt",
        ]
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            base = Path(str(meipass))
            candidates.append(base / "requirements_runtime.txt")
            candidates.append(base / "_internal" / "requirements_runtime.txt")

        for c in candidates:
            if c.exists():
                return c
        raise RuntimeError(
            "Missing requirements_runtime.txt in packaged app. Rebuild Installer (PyInstaller) "
            "with --add-data \"requirements_runtime.txt;.\""
        )

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
        winget_cmd = [
            "winget", "install", "Python.Python.3.11", "--scope", "user", "--location", str(target_dir), "--silent",
            "--accept-package-agreements", "--accept-source-agreements",
        ]
        winget = self._run_command(winget_cmd, status_cb=status_cb, label="winget-python", attempts=1)
        if winget.returncode != 0:
            status_cb("Winget failed, falling back to python.org installer...")
            py_installer = temp_root / "python-installer.exe"
            urllib.request.urlretrieve("https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe", py_installer)
            cmd = [str(py_installer), "/quiet", "InstallAllUsers=0", "PrependPath=0", "Include_pip=1", f"TargetDir={target_dir}"]
            proc = self._run_command(cmd, status_cb=status_cb, label="python-org-installer", attempts=1)
            if proc.returncode != 0:
                raise RuntimeError(proc.stderr or "Python install failed")

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

    def setup_micromamba_env(self, cache_root: Path, temp_root: Path, enable_gpu: bool, status_cb: Callable[[str], None]) -> Path:
        env = apply_runtime_env(cache_root=cache_root, temp_root=temp_root)
        self.log("ENV=" + json.dumps(env, ensure_ascii=False))
        mm_dir = self.install_root / "tools"
        mm_dir.mkdir(parents=True, exist_ok=True)
        mm_exe = mm_dir / "micromamba.exe"
        if not mm_exe.exists():
            status_cb("Downloading micromamba...")
            urllib.request.urlretrieve("https://github.com/mamba-org/micromamba-releases/releases/latest/download/micromamba-win-64", mm_exe)

        runtime_req = self.resolve_requirements_runtime_path()
        self._emit(status_cb, f"Resolved runtime requirements: {runtime_req}")

        env_path = self.install_root / "envs" / "qwen3-tts"
        create_cmd = [str(mm_exe), "create", "-y", "-p", str(env_path), "python=3.11", "pip", "ffmpeg", "pyside6", "libsndfile"]
        create_res = self._run_command(create_cmd, status_cb=status_cb, label="micromamba-create", attempts=3)
        if create_res.returncode != 0:
            raise RuntimeError("Failed to create runtime environment. See installer log for micromamba output.")

        pip_base = [str(mm_exe), "run", "-p", str(env_path), "python", "-m", "pip"]
        p1 = self._run_command(pip_base + ["install", "--upgrade", "pip"], status_cb=status_cb, label="pip-upgrade", attempts=2)
        if p1.returncode != 0:
            raise RuntimeError("Failed to upgrade pip inside runtime environment.")

        p2 = self._run_command(
            pip_base + ["install", "-r", str(runtime_req)],
            status_cb=status_cb,
            label="pip-runtime-req",
            attempts=2,
        )
        if p2.returncode != 0:
            raise RuntimeError("Failed to install requirements_runtime.txt. See installer log for details.")

        status_cb("Installing torch/runtime acceleration packages...")
        if enable_gpu:
            torch_cmd = pip_base + ["install", "torch", "onnxruntime-gpu"]
        else:
            torch_cmd = pip_base + ["install", "torch", "onnxruntime", "--index-url", "https://download.pytorch.org/whl/cpu"]
        t = self._run_command(torch_cmd, status_cb=status_cb, label="pip-torch-optimized", attempts=2)
        if t.returncode != 0:
            status_cb("GPU/CPU optimized package set failed, using generic fallback...")
            fallback = self._run_command(pip_base + ["install", "torch", "onnxruntime"], status_cb=status_cb, label="pip-torch-fallback", attempts=1)
            if fallback.returncode != 0:
                raise RuntimeError("Failed to install torch/onnxruntime runtime packages.")

        self._deploy_backend_script()
        self._write_runtime_config(env_path, cache_root, temp_root)

        self.settings["env_path"] = str(env_path)
        self.settings["cache_root"] = str(cache_root)
        self.settings["temp_root"] = str(temp_root)
        save_json(self.settings_path, self.settings)
        return env_path

    def _deploy_backend_script(self) -> None:
        src = Path(__file__).resolve().parent.parent / "shared" / "runtime_backend.py"
        dst = self.install_root / "app" / "shared" / "runtime_backend.py"
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())

    def _write_runtime_config(self, env_path: Path, cache_root: Path, temp_root: Path) -> None:
        save_runtime_config(
            {
                "install_root": str(self.install_root),
                "python": str(self.install_root / "python" / "python.exe"),
                "venv_python": str(env_path / "python.exe"),
                "cache_root": str(cache_root),
                "temp_root": str(temp_root),
                "version": "0.1.0",
            }
        )

    def get_hardware(self) -> HardwareInfo:
        return detect_hardware()

    def get_models(self) -> List[str]:
        return [m.model_id for m in query_models()]

    def download_selected_models(self, model_ids: List[str], status_cb: Callable[[str], None]) -> None:
        def on_progress(model_id: str, text: str) -> None:
            status_cb(f"{model_id}: {text}")

        download_models(model_ids, progress_cb=on_progress)
