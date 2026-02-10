from __future__ import annotations

import importlib
import os
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Callable, Dict, Iterable, List

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

from shared.model_catalog import CANONICAL_MODELS, ModelInfo


def _hf_hub():
    try:
        mod = importlib.import_module("huggingface_hub")
        return mod.HfApi, mod.hf_hub_download
    except Exception as exc:
        raise RuntimeError(
            "huggingface_hub is required for model operations. "
            "Please re-run Setup/Repair to install runtime dependencies."
        ) from exc


@dataclass
class DownloadedModel:
    model_id: str
    local_path: str
    bytes_total: int
    bytes_done: int


def query_models(token: str | None = None) -> List[ModelInfo]:
    HfApi, _ = _hf_hub()
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


def fetch_model_file_manifest(model_id: str, api=None) -> tuple[list[str], int]:
    HfApi, _ = _hf_hub()
    client = api or HfApi()
    info = client.model_info(repo_id=model_id, files_metadata=True)
    files: list[str] = []
    total = 0
    for sibling in info.siblings or []:
        filename = sibling.rfilename
        if not filename:
            continue
        files.append(filename)
        if isinstance(sibling.size, int):
            total += sibling.size
    return files, total


def download_models(
    model_ids: Iterable[str],
    progress_cb: Callable[[str, int, int, str], None] | None = None,
    local_dir: str | None = None,
    cancel_event: Event | None = None,
) -> List[DownloadedModel]:
    HfApi, hf_hub_download = _hf_hub()
    downloaded: List[DownloadedModel] = []
    api = HfApi()

    for model_id in model_ids:
        try:
            if cancel_event and cancel_event.is_set():
                break
            files, total = fetch_model_file_manifest(model_id=model_id, api=api)
            done = 0
            target_dir = local_dir
            if progress_cb:
                progress_cb(model_id, done, max(total, 1), "Preparing download")

            for filename in files:
                if cancel_event and cancel_event.is_set():
                    if progress_cb:
                        progress_cb(model_id, done, max(total, 1), "Cancelled")
                    break
                local_file = hf_hub_download(
                    repo_id=model_id,
                    filename=filename,
                    local_dir=target_dir,
                    local_dir_use_symlinks=False,
                    resume_download=True,
                )
                file_size = Path(local_file).stat().st_size if Path(local_file).exists() else 0
                done = min(done + file_size, max(total, 1))
                if progress_cb:
                    progress_cb(model_id, done, max(total, 1), filename)

            downloaded.append(
                DownloadedModel(
                    model_id=model_id,
                    local_path=str(Path(target_dir) if target_dir else ""),
                    bytes_total=total,
                    bytes_done=done,
                )
            )
            if progress_cb and (not cancel_event or not cancel_event.is_set()):
                progress_cb(model_id, max(total, done), max(total, 1), "Done")
        except Exception as ex:
            if progress_cb:
                progress_cb(model_id, 0, 1, f"ERROR: {ex}")
                progress_cb(model_id, 0, 1, traceback.format_exc())
            raise
    return downloaded
