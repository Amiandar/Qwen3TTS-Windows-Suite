from __future__ import annotations

import json
import platform
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class GPUInfo:
    gpu_name: str
    gpu_vendor: str
    vram_bytes: int
    vram_gb: float
    source: str
    gpu_index: int = 0


@dataclass
class HardwareInfo:
    cpu: str
    ram_gb: float
    gpu_vendor: str
    gpu_name: str
    vram_gb: float
    vram_bytes: int
    vram_source: str
    gpu_index: int
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


def _query_video_controllers() -> List[dict]:
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
        return [r for r in rows if isinstance(r, dict)]
    except Exception:
        return []


def _vendor_from_name(name: str) -> str:
    upper = name.upper()
    if "NVIDIA" in upper:
        return "NVIDIA"
    if "AMD" in upper or "RADEON" in upper:
        return "AMD"
    if "INTEL" in upper:
        return "Intel"
    return "Unknown"


def _nvidia_smi_vram(gpu_name_hint: str = "") -> Optional[GPUInfo]:
    cmd = [
        "nvidia-smi",
        "--query-gpu=name,memory.total",
        "--format=csv,noheader,nounits",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return None

    rows = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not rows:
        return None

    selected_idx = 0
    if gpu_name_hint:
        hint = gpu_name_hint.lower()
        for i, row in enumerate(rows):
            if hint and hint.split(" ")[0] in row.lower():
                selected_idx = i
                break

    parts = [p.strip() for p in rows[selected_idx].split(",")]
    if len(parts) < 2:
        return None
    name = parts[0]
    mib = float(parts[1])
    vram_bytes = int(mib * 1024 * 1024)
    return GPUInfo(
        gpu_name=name,
        gpu_vendor="NVIDIA",
        vram_bytes=vram_bytes,
        vram_gb=round(vram_bytes / (1024**3), 2),
        source="nvidia-smi",
        gpu_index=selected_idx,
    )


def _nvml_vram() -> Optional[GPUInfo]:
    try:
        import pynvml  # type: ignore

        pynvml.nvmlInit()
        idx = 0
        handle = pynvml.nvmlDeviceGetHandleByIndex(idx)
        mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
        name_raw = pynvml.nvmlDeviceGetName(handle)
        name = name_raw.decode("utf-8") if isinstance(name_raw, bytes) else str(name_raw)
        vram_bytes = int(mem.total)
        return GPUInfo(
            gpu_name=name,
            gpu_vendor="NVIDIA",
            vram_bytes=vram_bytes,
            vram_gb=round(vram_bytes / (1024**3), 2),
            source="nvml",
            gpu_index=idx,
        )
    except Exception:
        return None


def _dxdiag_vram() -> Optional[GPUInfo]:
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tf:
            out = Path(tf.name)
        run = subprocess.run(["dxdiag", "/t", str(out)], capture_output=True, text=True, check=False)
        if run.returncode != 0 or not out.exists():
            return None
        text = out.read_text(encoding="utf-16", errors="ignore")
        if not text.strip():
            text = out.read_text(encoding="utf-8", errors="ignore")

        name_match = re.search(r"Card name:\s*(.+)", text)
        mem_match = re.search(r"Display Memory:\s*([0-9]+)\s*MB", text)
        if not mem_match:
            mem_match = re.search(r"Dedicated Memory:\s*([0-9]+)\s*MB", text)
        if not mem_match:
            return None

        mb = int(mem_match.group(1))
        vram_bytes = mb * 1024 * 1024
        name = name_match.group(1).strip() if name_match else "Unknown GPU"
        return GPUInfo(
            gpu_name=name,
            gpu_vendor=_vendor_from_name(name),
            vram_bytes=vram_bytes,
            vram_gb=round(vram_bytes / (1024**3), 2),
            source="dxdiag",
            gpu_index=0,
        )
    except Exception:
        return None


def _wmi_gpu() -> Optional[GPUInfo]:
    rows = _query_video_controllers()
    if not rows:
        return None
    row = rows[0]
    name = str(row.get("Name") or "Unknown GPU")
    ram = row.get("AdapterRAM")
    vram_bytes = int(ram) if isinstance(ram, int) else 0
    return GPUInfo(
        gpu_name=name,
        gpu_vendor=_vendor_from_name(name),
        vram_bytes=vram_bytes,
        vram_gb=round(vram_bytes / (1024**3), 2) if vram_bytes else 0.0,
        source="wmi",
        gpu_index=0,
    )


def get_gpu_info() -> GPUInfo:
    wmi = _wmi_gpu()
    gpu_name_hint = wmi.gpu_name if wmi else ""

    if wmi and wmi.gpu_vendor == "NVIDIA":
        nvsmi = _nvidia_smi_vram(gpu_name_hint)
        if nvsmi:
            return nvsmi
        nvml = _nvml_vram()
        if nvml:
            return nvml
        dxg = _dxdiag_vram()
        if dxg:
            return dxg
        return wmi

    dxg = _dxdiag_vram()
    if dxg:
        return dxg
    if wmi:
        return wmi

    return GPUInfo(gpu_name="Unknown GPU", gpu_vendor="Unknown", vram_bytes=0, vram_gb=0.0, source="none", gpu_index=0)


def detect_hardware() -> HardwareInfo:
    cpu = platform.processor() or platform.machine() or "Unknown CPU"
    ram_bytes = _wmic_value("TotalPhysicalMemory")
    ram_gb = round(int(ram_bytes) / (1024**3), 2) if ram_bytes.isdigit() else 0.0

    gpu = get_gpu_info()
    cuda_hint = "cuda:0" if gpu.gpu_vendor == "NVIDIA" else "cpu"

    return HardwareInfo(
        cpu=cpu,
        ram_gb=ram_gb,
        gpu_vendor=gpu.gpu_vendor,
        gpu_name=gpu.gpu_name,
        vram_gb=gpu.vram_gb,
        vram_bytes=gpu.vram_bytes,
        vram_source=gpu.source,
        gpu_index=gpu.gpu_index,
        cuda_hint=cuda_hint,
    )
