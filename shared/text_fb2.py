from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path


def extract_text(book_path: Path, skip_toc: bool = True, normalize_ws: bool = True) -> str:
    if book_path.suffix.lower() == ".txt":
        txt = book_path.read_text(encoding="utf-8", errors="ignore")
        return normalize_text(txt) if normalize_ws else txt
    if book_path.suffix.lower() != ".fb2":
        raise ValueError("Supported input only .fb2 and .txt")

    tree = ET.parse(book_path)
    root = tree.getroot()
    texts: list[str] = []
    for el in root.iter():
        if el.text and el.tag.lower().endswith(("p", "v", "subtitle", "title")):
            texts.append(el.text.strip())

    joined = "\n".join(x for x in texts if x)
    if skip_toc:
        joined = remove_toc(joined)
    return normalize_text(joined) if normalize_ws else joined


def remove_toc(text: str) -> str:
    lines = text.splitlines()
    out: list[str] = []
    toc_mode = False
    for ln in lines:
        low = ln.strip().lower()
        if low in {"contents", "table of contents", "оглавление", "содержание"}:
            toc_mode = True
            continue
        if toc_mode and re.search(r"chapter|глава", low):
            continue
        if toc_mode and len(low) > 40:
            toc_mode = False
        if not toc_mode:
            out.append(ln)
    return "\n".join(out)


def normalize_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()
