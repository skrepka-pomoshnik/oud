from __future__ import annotations

from pathlib import Path

from oud.core.ft3 import load_ft3
from oud.core.model import Piece
from oud.core.tab_parser import load_tab, load_tab_data

LoadResult = tuple[
    Piece,
    dict[tuple[int, int, int], str],
    dict[tuple[int, int, int], int],
    set[tuple[int, int]],
    int | None,
]


def load_piece_data(path: str | None) -> LoadResult:
    overrides: dict[tuple[int, int, int], str] = {}
    durations: dict[tuple[int, int, int], int] = {}
    dotted: set[tuple[int, int]] = set()
    bar_width: int | None = None
    if path and not Path(path).exists():
        title = Path(path).stem if path else "Untitled"
        piece = Piece(title=title, bars=[])
        return piece, overrides, durations, dotted, bar_width
    if path:
        if path.lower().endswith(".tab"):
            parsed = load_tab_data(path)
            if parsed is not None:
                overrides = parsed.overrides
                durations = parsed.durations
                dotted = parsed.dotted
                bar_width = parsed.bar_width
                return parsed.piece, overrides, durations, dotted, bar_width
            return load_tab(path), overrides, durations, dotted, bar_width
        return load_ft3(path), overrides, durations, dotted, bar_width
    return Piece(title="Untitled", bars=[]), overrides, durations, dotted, bar_width


def load_piece(path: str | None) -> Piece:
    piece, _overrides, _durations, _dotted, _bar_width = load_piece_data(path)
    return piece
