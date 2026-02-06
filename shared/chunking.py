from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ChunkConfig:
    chunk_chars: int = 1200
    max_chunk_chars: int = 1600


def split_sentences(text: str) -> list[str]:
    return [x.strip() for x in re.split(r"(?<=[.!?…])\s+", text) if x.strip()]


def build_chunks(text: str, cfg: ChunkConfig) -> list[str]:
    sentences = split_sentences(text)
    chunks: list[str] = []
    cur = ""
    for s in sentences:
        if len(s) > cfg.max_chunk_chars:
            if cur:
                chunks.append(cur)
                cur = ""
            for i in range(0, len(s), cfg.max_chunk_chars):
                chunks.append(s[i : i + cfg.max_chunk_chars])
            continue
        candidate = (cur + " " + s).strip()
        if len(candidate) <= cfg.chunk_chars:
            cur = candidate
        else:
            if cur:
                chunks.append(cur)
            cur = s
    if cur:
        chunks.append(cur)
    return chunks
