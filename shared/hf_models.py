from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable


OFFICIAL_GROUPS = {
    "Base": [
        "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
        "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
    ],
    "CustomVoice": [
        "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
        "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
    ],
    "VoiceDesign": ["Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"],
}


@dataclass
class ModelInfo:
    repo_id: str
    family: str
    size_hint: str
    installed: bool = False
    bytes_hint: int | None = None


def family_for_repo(repo_id: str) -> str:
    rid = repo_id.lower()
    if "customvoice" in rid:
        return "CustomVoice"
    if "voicedesign" in rid:
        return "VoiceDesign"
    return "Base"


def size_for_repo(repo_id: str) -> str:
    return "1.7B" if "1.7b" in repo_id.lower() else "0.6B"


def list_official_default() -> list[ModelInfo]:
    out: list[ModelInfo] = []
    for family, models in OFFICIAL_GROUPS.items():
        for repo in models:
            out.append(ModelInfo(repo_id=repo, family=family, size_hint=size_for_repo(repo)))
    return out


def query_hf_qwen3_models() -> list[ModelInfo]:
    try:
        from huggingface_hub import HfApi  # type: ignore

        api = HfApi()
        models = api.list_models(author="Qwen", search="Qwen3-TTS-12Hz")
        out = [
            ModelInfo(
                repo_id=m.id,
                family=family_for_repo(m.id),
                size_hint=size_for_repo(m.id),
                bytes_hint=getattr(m, "usedStorage", None),
            )
            for m in models
            if "qwen3-tts" in m.id.lower()
        ]
        return sorted(out, key=lambda x: x.repo_id.lower()) or list_official_default()
    except Exception:
        return list_official_default()


def detect_installed(models: list[ModelInfo], hf_hub_cache: Path) -> list[ModelInfo]:
    for m in models:
        repo_dir = "models--" + m.repo_id.replace("/", "--")
        snapshots = hf_hub_cache / repo_dir / "snapshots"
        m.installed = snapshots.exists() and any(snapshots.iterdir())
    return models


def download_model(
    repo_id: str,
    progress: Callable[[int, int], None] | None = None,
) -> str:
    from huggingface_hub import snapshot_download  # type: ignore

    if progress:
        progress(0, 1)
    path = snapshot_download(repo_id=repo_id, resume_download=True)
    if progress:
        progress(1, 1)
    return path
