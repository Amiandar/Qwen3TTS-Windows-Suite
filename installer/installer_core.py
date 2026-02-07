from __future__ import annotations

import datetime as dt
import json
import shutil
import subprocess
import urllib.request
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from shared.env_paths import apply_runtime_env
from shared.hf_models import download_models, query_models
from shared.hw_detect import HardwareInfo, detect_hardware
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
            "winget",
            "install",
            "Python.Python.3.11",
            "--scope",
            "user",
            "--location",
            str(target_dir),
            "--silent",
            "--accept-package-agreements",
            "--accept-source-agreements",
        ]
        winget = subprocess.run(winget_cmd, capture_output=True, text=True, check=False)
        if winget.returncode != 0:
            status_cb("Winget failed, falling back to python.org installer...")
            py_installer = temp_root / "python-installer.exe"
            urllib.request.urlretrieve("https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe", py_installer)
            cmd = [
                str(py_installer),
                "/quiet",
                "InstallAllUsers=0",
                "PrependPath=0",
                "Include_pip=1",
                f"TargetDir={target_dir}",
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if proc.returncode != 0:
                raise RuntimeError(proc.stderr or "Python install failed")

        py = target_dir / "python.exe"
        if not py.exists():
            raise RuntimeError("Could not resolve installed python.exe in selected folder")

        for check in ([str(py), "-V"], [str(py), "-m", "pip", "-V"]):
            r = subprocess.run(check, capture_output=True, text=True, check=False)
            if r.returncode != 0:
                raise RuntimeError(f"Check failed: {' '.join(check)}")
        self.settings["bootstrap_python"] = str(py)
        save_json(self.settings_path, self.settings)
        return py

    def setup_micromamba_env(self, cache_root: Path, temp_root: Path, status_cb: Callable[[str], None]) -> Path:
        env = apply_runtime_env(cache_root=cache_root, temp_root=temp_root)
        self.log("ENV=" + json.dumps(env, ensure_ascii=False))
        mm_dir = self.install_root / "tools"
        mm_dir.mkdir(parents=True, exist_ok=True)
        mm_exe = mm_dir / "micromamba.exe"
        if not mm_exe.exists():
            status_cb("Downloading micromamba...")
            urllib.request.urlretrieve(
                "https://github.com/mamba-org/micromamba-releases/releases/latest/download/micromamba-win-64",
                mm_exe,
            )
        env_path = self.install_root / "envs" / "qwen3-tts"
        status_cb("Creating/repairing environment...")
        create_cmd = [str(mm_exe), "create", "-y", "-p", str(env_path), "python=3.11", "pip", "ffmpeg", "pyside6", "libsndfile"]
        r = subprocess.run(create_cmd, capture_output=True, text=True, check=False)
        if r.returncode != 0:
            raise RuntimeError(r.stderr or r.stdout)

        pip_install = [
            str(mm_exe),
            "run",
            "-p",
            str(env_path),
            "python",
            "-m",
            "pip",
            "install",
            "--upgrade",
            "pip",
            "huggingface_hub",
            "transformers",
            "soundfile",
            "qwen-tts",
            "psutil",
            "lxml",
        ]
        status_cb("Installing Python packages...")
        p = subprocess.run(pip_install, capture_output=True, text=True, check=False)
        if p.returncode != 0:
            raise RuntimeError(p.stderr or p.stdout)

        self.settings["env_path"] = str(env_path)
        self.settings["cache_root"] = str(cache_root)
        self.settings["temp_root"] = str(temp_root)
        save_json(self.settings_path, self.settings)
        return env_path

    def get_hardware(self) -> HardwareInfo:
        return detect_hardware()

    def get_models(self) -> List[str]:
        return [m.model_id for m in query_models()]

    def download_selected_models(self, model_ids: List[str], status_cb: Callable[[str], None]) -> None:
        def on_progress(model_id: str, text: str) -> None:
            status_cb(f"{model_id}: {text}")

        download_models(model_ids, progress_cb=on_progress)

    def cleanup(self) -> None:
        if shutil.which("taskkill"):
            pass
