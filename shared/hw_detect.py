from __future__ import annotations

import json
import platform
import subprocess
from dataclasses import dataclass


@dataclass
class HardwareInfo:
    cpu: str
    ram_gb: float
    gpu_vendor: str
    gpu_name: str
    vram_gb: float
    cuda_hint: str


def _wmic_value(name: str) -> str:
    try:
        result = subprocess.run(
            ["wmic", "computersystem", "get", name, "/value"],
            capture_output=True,
            text=True,
            check=False,
        )
        for line in result.stdout.splitlines():
            if "=" in line and line.split("=", 1)[0].strip().lower() == name.lower():
                return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return ""


def detect_hardware() -> HardwareInfo:
    cpu = platform.processor() or platform.machine() or "Unknown CPU"
    ram_bytes = _wmic_value("TotalPhysicalMemory")
    ram_gb = round(int(ram_bytes) / (1024**3), 2) if ram_bytes.isdigit() else 0.0

    gpu_vendor = "Unknown"
    gpu_name = "Unknown GPU"
    vram_gb = 0.0
    cuda_hint = "cpu"

    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM | ConvertTo-Json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        parsed = json.loads(result.stdout) if result.stdout.strip() else []
        rows = parsed if isinstance(parsed, list) else [parsed]
        if rows:
            row = rows[0]
            gpu_name = row.get("Name") or gpu_name
            ram = row.get("AdapterRAM")
            if isinstance(ram, int):
                vram_gb = round(ram / (1024**3), 2)
            if "NVIDIA" in gpu_name.upper():
                gpu_vendor = "NVIDIA"
                cuda_hint = "cuda:0"
            elif "AMD" in gpu_name.upper() or "RADEON" in gpu_name.upper():
                gpu_vendor = "AMD"
            elif "INTEL" in gpu_name.upper():
                gpu_vendor = "Intel"
    except Exception:
        pass

    return HardwareInfo(cpu=cpu, ram_gb=ram_gb, gpu_vendor=gpu_vendor, gpu_name=gpu_name, vram_gb=vram_gb, cuda_hint=cuda_hint)
