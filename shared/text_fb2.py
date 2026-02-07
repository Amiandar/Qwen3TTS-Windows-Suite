from __future__ import annotations

import re
from pathlib import Path
import xml.etree.ElementTree as ET


def load_book_text(path: Path, skip_toc: bool = True, normalize_ws: bool = True) -> str:
    if path.suffix.lower() == ".txt":
        text = path.read_text(encoding="utf-8", errors="ignore")
    elif path.suffix.lower() == ".fb2":
        text = _extract_fb2(path, skip_toc=skip_toc)
    else:
        raise ValueError("Unsupported input format")

    if normalize_ws:
        text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_fb2(path: Path, skip_toc: bool = True) -> str:
    tree = ET.parse(path)
    root = tree.getroot()
    paragraphs = []
    for elem in root.iter():
        tag = elem.tag.split("}")[-1].lower()
        if tag in {"p", "subtitle", "title"} and elem.text:
            t = elem.text.strip()
            if not t:
                continue
            if skip_toc and re.search(r"^(оглавление|contents?)$", t, re.IGNORECASE):
                continue
            paragraphs.append(t)
    return "\n".join(paragraphs)
