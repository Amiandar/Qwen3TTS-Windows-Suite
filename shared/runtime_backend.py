from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from shared.audio_encode import wav_to_mp3
from shared.chunking import sentence_chunks
from shared.env_paths import apply_runtime_env
from shared.text_fb2 import load_book_text


def emit(event: str, **payload) -> None:
    print(json.dumps({"event": event, **payload}, ensure_ascii=False), flush=True)


def run_generate(payload: dict) -> int:
    from qwen_tts import Qwen3TTSModel  # lazy heavy import
    import soundfile as sf  # lazy heavy import

    cache_root = Path(payload["cache_root"])
    temp_root = Path(payload["temp_root"])
    apply_runtime_env(cache_root=cache_root, temp_root=temp_root)

    model_id = payload["model_id"]
    params = payload["params"]
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
            emit("progress", current=idx, total=len(chunks), message=f"Saved {mp3_path.name}")
    finally:
        if not params.get("keep_temp", False):
            shutil.rmtree(temp_work, ignore_errors=True)

    emit("done", ok=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True, help="Path to JSON request file")
    args = parser.parse_args()

    req = Path(args.request)
    payload = json.loads(req.read_text(encoding="utf-8"))
    action = payload.get("action")

    if action == "generate":
        return run_generate(payload)

    emit("done", ok=False, error=f"Unknown action: {action}")
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        emit("done", ok=False, error=str(exc))
        raise
