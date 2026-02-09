from __future__ import annotations

from dataclasses import dataclass


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
