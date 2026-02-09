from __future__ import annotations

import io
import sys
from typing import Callable, Optional


class GuiLogStream(io.TextIOBase):
    def __init__(self):
        super().__init__()
        self._buffer: list[str] = []
        self._cb: Optional[Callable[[str], None]] = None

    def set_callback(self, cb: Callable[[str], None]) -> None:
        self._cb = cb
        if self._buffer:
            for item in self._buffer:
                cb(item)
            self._buffer.clear()

    def write(self, s: str) -> int:
        if not s:
            return 0
        if self._cb:
            self._cb(s.rstrip("\n"))
        else:
            self._buffer.append(s.rstrip("\n"))
        return len(s)

    def flush(self) -> None:
        return


def ensure_streams() -> GuiLogStream:
    stream = GuiLogStream()
    if sys.stdout is None:
        sys.stdout = stream
    if sys.stderr is None:
        sys.stderr = stream
    return stream
