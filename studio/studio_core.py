from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Callable

from shared.audio_encode import wav_to_mp3
from shared.chunking import ChunkConfig, build_chunks
from shared.env_paths import EnvPaths
from shared.hf_models import detect_installed, query_hf_qwen3_models
from shared.text_fb2 import extract_text


class StudioCore:
    def __init__(self, install_root: Path, cache_root: Path, temp_root: Path):
        self.paths = EnvPaths(install_root, cache_root, temp_root)
        self.paths.ensure_dirs()
        self.log_file = self.paths.logs_dir / f"studio_{dt.datetime.now():%Y%m%d_%H%M%S}.log"

    def log(self, msg: str):
        with self.log_file.open("a", encoding="utf-8") as f:
            f.write(msg + "\n")

    def list_installed_models(self):
        self.paths.apply_to_process()
        models = query_hf_qwen3_models()
        return detect_installed(models, self.paths.hf_hub_cache)

    def generate_book(
        self,
        model_id: str,
        input_book: Path,
        output_dir: Path,
        ffmpeg_bin: str,
        params: dict,
        progress: Callable[[str, int, int], None],
        cancelled: Callable[[], bool],
    ):
        self.paths.apply_to_process()
        tmp = output_dir.parent / f"{output_dir.name}.tmp"
        tmp.mkdir(parents=True, exist_ok=True)
        text = extract_text(input_book, skip_toc=params.get("skip_toc", True), normalize_ws=params.get("normalize_ws", True))
        chunks = build_chunks(text, ChunkConfig(chunk_chars=params.get("chunk_chars", 1200), max_chunk_chars=params.get("max_chunk_chars", 1600)))

        try:
            from qwen_tts import Qwen3TTSModel  # type: ignore

            model = Qwen3TTSModel.from_pretrained(model_id, device=params.get("device", "cpu"), dtype=params.get("dtype", "fp32"))
            for i, ch in enumerate(chunks, start=1):
                if cancelled():
                    progress("Cancelled", i, len(chunks))
                    break
                wav_path = tmp / f"{i:03d}.wav"
                mp3_path = output_dir / f"{i:03d}.mp3"
                family = params.get("family", "Base")
                if family == "CustomVoice":
                    model.generate_custom_voice(text=ch, speaker=params.get("speaker", "default"), instruct=params.get("instruct", ""), output_path=str(wav_path))
                elif family == "VoiceDesign":
                    model.generate_voice_design(text=ch, instruct=params.get("instruct", ""), output_path=str(wav_path))
                else:
                    model.generate_voice_clone(
                        text=ch,
                        ref_audio=params.get("ref_audio", ""),
                        ref_text=params.get("ref_text", ""),
                        x_vector_only_mode=params.get("x_vector_only_mode", True),
                        output_path=str(wav_path),
                    )
                wav_to_mp3(ffmpeg_bin, wav_path, mp3_path, bitrate_kbps=params.get("bitrate", 128), vbr=params.get("vbr", False))
                progress(f"Chunk {i}/{len(chunks)} ready", i, len(chunks))
        finally:
            if not params.get("keep_temp", False):
                for p in tmp.glob("*"):
                    p.unlink(missing_ok=True)
                tmp.rmdir()
