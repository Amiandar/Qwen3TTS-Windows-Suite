from __future__ import annotations

import re
from typing import List


def sentence_chunks(text: str, target_chars: int = 800, max_chars: int = 1200) -> List[str]:
    sentences = re.split(r"(?<=[.!?…])\s+", text)
    out: List[str] = []
    current = ""
    for sentence in sentences:
        if not sentence:
            continue
        if len(current) + len(sentence) + 1 <= target_chars:
            current = f"{current} {sentence}".strip()
            continue
        if current:
            out.append(current)
        if len(sentence) > max_chars:
            for i in range(0, len(sentence), max_chars):
                out.append(sentence[i : i + max_chars])
            current = ""
        else:
            current = sentence
    if current:
        out.append(current)
    return out
