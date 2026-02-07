from __future__ import annotations

import datetime as dt
import shutil
from pathlib import Path
from typing import Callable, Dict, List

import soundfile as sf
from qwen_tts import Qwen3TTSModel

from shared.audio_encode import wav_to_mp3
from shared.chunking import sentence_chunks
from shared.env_paths import apply_runtime_env
from shared.hf_models import CANONICAL_MODELS
from shared.settings_store import load_json, save_json
from shared.text_fb2 import load_book_text


class StudioCore:
    def __init__(self, install_root: Path, cache_root: Path, temp_root: Path):
        self.install_root = install_root
        self.cache_root = cache_root
        self.temp_root = temp_root
        apply_runtime_env(cache_root=cache_root, temp_root=temp_root)

        self.logs_dir = install_root / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.logs_dir / f"studio_{dt.datetime.now():%Y%m%d_%H%M%S}.log"
        self.settings_path = install_root / "studio_settings.json"
        self.settings = load_json(self.settings_path, default={})

    def log(self, line: str) -> None:
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def save_settings(self, data: Dict):
        self.settings.update(data)
        save_json(self.settings_path, self.settings)

    def installed_models(self) -> List[str]:
        hub = self.cache_root / "huggingface" / "hub"
        if not hub.exists():
            return []
        names = []
        for m in CANONICAL_MODELS:
            tag = "models--" + m.model_id.replace("/", "--")
            if any(p.name.startswith(tag) for p in hub.iterdir()):
                names.append(m.model_id)
        return names

    def generate_book(self, model_id: str, params: Dict, progress_cb: Callable[[int, int, str], None]) -> None:
        output_dir = Path(params["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        temp_work = output_dir.parent / f"{output_dir.name}.tmp"
        if temp_work.exists():
            shutil.rmtree(temp_work, ignore_errors=True)
        temp_work.mkdir(parents=True, exist_ok=True)

        try:
            text = load_book_text(Path(params["book_file"]), skip_toc=params.get("skip_toc", True), normalize_ws=params.get("normalize_ws", True))
            chunks = sentence_chunks(text, target_chars=int(params.get("chunk_chars", 800)), max_chars=int(params.get("max_chunk_chars", 1200)))
            model = Qwen3TTSModel(model_name=model_id, device=params.get("device", "cpu"), dtype=params.get("dtype", "fp16"))
            ffmpeg_bin = Path(params.get("ffmpeg_bin") or "ffmpeg")

            for idx, chunk in enumerate(chunks, start=1):
                wav_path = temp_work / f"{idx:03d}.wav"
                mp3_path = output_dir / f"{idx:03d}.mp3"
                family = "VoiceDesign" if "VoiceDesign" in model_id else "CustomVoice" if "CustomVoice" in model_id else "Base"
                if family == "Base":
                    audio = model.generate_voice_clone(
                        text=chunk,
                        ref_audio_path=params.get("ref_audio"),
                        ref_text=params.get("ref_text") if not params.get("x_vector_only_mode") else None,
                        x_vector_only_mode=params.get("x_vector_only_mode", True),
                        language=params.get("language", "Russian"),
                        max_new_tokens=int(params.get("max_new_tokens", 1024)),
                        temperature=float(params.get("temperature", 0.7)),
                        top_k=int(params.get("top_k", 50)),
                        top_p=float(params.get("top_p", 0.95)),
                        repetition_penalty=float(params.get("repetition_penalty", 1.1)),
                    )
                elif family == "CustomVoice":
                    audio = model.generate_custom_voice(
                        text=chunk,
                        speaker=params.get("speaker"),
                        instruct=params.get("instruct", ""),
                        language=params.get("language", "Russian"),
                    )
                else:
                    audio = model.generate_voice_design(text=chunk, instruct=params.get("instruct", ""), language=params.get("language", "Russian"))
                sf.write(wav_path, audio, samplerate=24000)
                wav_to_mp3(ffmpeg_bin, wav_path, mp3_path, bitrate_kbps=int(params.get("bitrate", 128)), vbr=params.get("vbr", False))
                progress_cb(idx, len(chunks), f"Saved {mp3_path.name}")
        finally:
            if not params.get("keep_temp", False):
                shutil.rmtree(temp_work, ignore_errors=True)
