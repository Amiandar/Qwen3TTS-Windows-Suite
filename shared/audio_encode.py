from __future__ import annotations

import subprocess
from pathlib import Path


def wav_to_mp3(ffmpeg_bin: Path, wav_path: Path, mp3_path: Path, bitrate_kbps: int = 128, vbr: bool = False) -> None:
    cmd = [str(ffmpeg_bin), "-y", "-i", str(wav_path)]
    if vbr:
        cmd += ["-q:a", "2"]
    else:
        cmd += ["-b:a", f"{bitrate_kbps}k"]
    cmd += [str(mp3_path)]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffmpeg encoding failed")
