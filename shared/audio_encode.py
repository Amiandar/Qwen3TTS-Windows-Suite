from __future__ import annotations

import subprocess
from pathlib import Path


def wav_to_mp3(ffmpeg_bin: str, input_wav: Path, output_mp3: Path, bitrate_kbps: int = 128, vbr: bool = False) -> None:
    cmd = [ffmpeg_bin, "-y", "-i", str(input_wav)]
    if vbr:
        cmd += ["-q:a", "2"]
    else:
        cmd += ["-b:a", f"{bitrate_kbps}k"]
    cmd += [str(output_mp3)]
    subprocess.run(cmd, check=True, capture_output=True)
