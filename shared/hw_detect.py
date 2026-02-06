from __future__ import annotations

import platform
import subprocess
from dataclasses import dataclass


@dataclass
class HardwareSummary:
    cpu: str
    ram_gb: float | None
    gpu: str
    vram_gb: float | None
    nvidia: bool


def _detect_windows_gpu() -> tuple[str, float | None, bool]:
    try:
        result = subprocess.run(
            ["wmic", "path", "win32_VideoController", "get", "Name,AdapterRAM", "/format:csv"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        lines = [ln.strip() for ln in result.stdout.splitlines() if ln.strip() and "Node" not in ln]
        if not lines:
            return "Unknown", None, False
        first = lines[0].split(",")
        name = first[-2] if len(first) >= 3 else "Unknown"
        ram_raw = first[-1] if len(first) >= 2 else ""
        vram_gb = None
        if ram_raw.isdigit():
            vram_gb = round(int(ram_raw) / (1024**3), 2)
        return name, vram_gb, "nvidia" in name.lower()
    except Exception:
        return "Unknown", None, False


def _detect_ram_gb() -> float | None:
    try:
        import psutil  # type: ignore

        return round(psutil.virtual_memory().total / (1024**3), 2)
    except Exception:
        return None


def detect_hardware() -> HardwareSummary:
    gpu, vram, nvidia = _detect_windows_gpu()
    return HardwareSummary(
        cpu=platform.processor() or platform.machine(),
        ram_gb=_detect_ram_gb(),
        gpu=gpu,
        vram_gb=vram,
        nvidia=nvidia,
    )
