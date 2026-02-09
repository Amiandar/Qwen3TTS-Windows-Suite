from __future__ import annotations

import os
import sys
import traceback
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

from huggingface_hub import HfApi, snapshot_download


@dataclass
class ModelInfo:
    model_id: str
    family: str
    size: str


CANONICAL_MODELS = [
    ModelInfo("Qwen/Qwen3-TTS-12Hz-0.6B-Base", "Base", "0.6B"),
    ModelInfo("Qwen/Qwen3-TTS-12Hz-1.7B-Base", "Base", "1.7B"),
    ModelInfo("Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice", "CustomVoice", "0.6B"),
    ModelInfo("Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice", "CustomVoice", "1.7B"),
    ModelInfo("Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign", "VoiceDesign", "1.7B"),
]


def query_models(token: str | None = None) -> List[ModelInfo]:
    api = HfApi(token=token)
    known: Dict[str, ModelInfo] = {m.model_id: m for m in CANONICAL_MODELS}
    for model in api.list_models(author="Qwen", search="Qwen3-TTS-12Hz"):
        model_id = model.id
        if model_id in known:
            continue
        if "VoiceDesign" in model_id:
            family = "VoiceDesign"
        elif "CustomVoice" in model_id:
            family = "CustomVoice"
        else:
            family = "Base"
        size = "1.7B" if "1.7B" in model_id else "0.6B" if "0.6B" in model_id else "?"
        known[model_id] = ModelInfo(model_id=model_id, family=family, size=size)
    return sorted(known.values(), key=lambda x: x.model_id)


def download_models(
    model_ids: Iterable[str],
    progress_cb: Callable[[str, str], None] | None = None,
    local_dir: str | None = None,
) -> List[str]:
    downloaded: List[str] = []
    for model_id in model_ids:
        try:
            if progress_cb:
                progress_cb(model_id, "Starting download")
            p = snapshot_download(
                repo_id=model_id,
                resume_download=True,
                local_dir=local_dir,
                local_dir_use_symlinks=False,
            )
            downloaded.append(str(p))
            if progress_cb:
                progress_cb(model_id, f"Done: {p}")
        except Exception as ex:
            if progress_cb:
                progress_cb(model_id, f"ERROR: {ex}")
                progress_cb(model_id, traceback.format_exc())
            raise
    return downloaded
