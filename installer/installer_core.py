from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Callable

from shared.env_paths import EnvPaths
from shared.hf_models import download_model, query_hf_qwen3_models
from shared.hw_detect import HardwareSummary, detect_hardware


class InstallerCore:
    def __init__(self, install_root: Path, cache_root: Path, temp_root: Path):
        self.paths = EnvPaths(install_root=install_root, cache_root=cache_root, temp_root=temp_root)
        self.paths.ensure_dirs()
        self.log_file = self.paths.logs_dir / f"installer_{dt.datetime.now():%Y%m%d_%H%M%S}.log"

    def log(self, message: str) -> None:
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        with self.log_file.open("a", encoding="utf-8") as f:
            f.write(message + "\n")

    def detect_hw(self) -> HardwareSummary:
        hw = detect_hardware()
        self.log(f"Hardware: {hw}")
        return hw

    def save_install_settings(self, data: dict) -> None:
        p = self.paths.install_root / "installer_settings.json"
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def install_env(self, use_gpu: bool, use_flash: bool, progress: Callable[[str], None]) -> None:
        self.paths.apply_to_process()
        progress("Preparing micromamba...")
        mm = self.paths.install_root / "micromamba.exe"
        if not mm.exists():
            self.log("Micromamba missing. User should place micromamba.exe or installer can fetch it.")
            progress("micromamba.exe not found; please place binary in Install Root.")
            return

        env_prefix = self.paths.install_root / "envs" / "qwen3-tts"
        channels = ["-c", "conda-forge"]
        create_cmd = [str(mm), "create", "-y", "-p", str(env_prefix), "python=3.11", "pip", "ffmpeg", *channels]
        progress("Creating/repairing environment...")
        subprocess.run(create_cmd, check=False)

        pip_bin = env_prefix / ("Scripts" if sys.platform.startswith("win") else "bin") / "pip.exe"
        pkgs = ["qwen-tts", "huggingface_hub", "pyside6", "soundfile", "psutil"]
        torch_pkg = "torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121" if use_gpu else "torch torchvision torchaudio"
        subprocess.run([str(pip_bin), "install", *pkgs], check=False)
        subprocess.run([str(pip_bin), "install", *torch_pkg.split(" ")], check=False)
        if use_flash:
            subprocess.run([str(pip_bin), "install", "flash-attn", "--no-build-isolation"], check=False)
        progress("Environment install finished.")

    def list_models(self):
        self.paths.apply_to_process()
        return query_hf_qwen3_models()

    def download_models(self, repos: list[str], progress: Callable[[str], None]) -> None:
        self.paths.apply_to_process()
        for rid in repos:
            progress(f"Downloading {rid}...")
            try:
                download_model(rid)
                progress(f"Done: {rid}")
            except Exception as e:
                msg = f"Failed {rid}: {e}. Try enabling proxy settings."
                self.log(msg)
                progress(msg)
