from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class EnvPaths:
    install_root: Path
    cache_root: Path
    temp_root: Path

    @property
    def hf_home(self) -> Path:
        return self.cache_root / "huggingface"

    @property
    def hf_hub_cache(self) -> Path:
        return self.hf_home / "hub"

    @property
    def logs_dir(self) -> Path:
        return self.install_root / "logs"

    def ensure_dirs(self) -> None:
        for p in [self.install_root, self.cache_root, self.temp_root, self.hf_home, self.hf_hub_cache, self.logs_dir]:
            p.mkdir(parents=True, exist_ok=True)

    def export_env(self, proxies: dict[str, str] | None = None, hf_endpoint: str | None = None) -> dict[str, str]:
        env = {
            "TEMP": str(self.temp_root),
            "TMP": str(self.temp_root),
            "HF_HOME": str(self.hf_home),
            "HF_HUB_CACHE": str(self.hf_hub_cache),
            "HUGGINGFACE_HUB_CACHE": str(self.hf_hub_cache),
            "TRANSFORMERS_CACHE": str(self.hf_home),
            "TORCH_HOME": str(self.cache_root / "torch"),
            "PIP_CACHE_DIR": str(self.cache_root / "pip"),
            "XDG_CACHE_HOME": str(self.cache_root),
        }
        if hf_endpoint:
            env["HF_ENDPOINT"] = hf_endpoint
        if proxies:
            env.update({k: v for k, v in proxies.items() if v})
        return env

    def apply_to_process(self, proxies: dict[str, str] | None = None, hf_endpoint: str | None = None) -> None:
        env = self.export_env(proxies=proxies, hf_endpoint=hf_endpoint)
        for k, v in env.items():
            os.environ[k] = v
