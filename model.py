from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Note:
    string: int
    fret: int
    raw_pos: int
    duration: int | None = None


@dataclass
class Bar:
    notes: List[Note] = field(default_factory=list)
    barline: str | None = None
    repeat: str | None = None
    time_sig: str | None = None
    chords: List["Chord"] = field(default_factory=list)


@dataclass
class Chord:
    note_type: int
    dotted: bool
    grid: str | None
    notes: List[Note] = field(default_factory=list)


@dataclass
class Piece:
    title: Optional[str] = None
    author: Optional[str] = None
    composer: Optional[str] = None
    bars: List[Bar] = field(default_factory=list)
    strings: int = 6
