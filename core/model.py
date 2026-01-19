from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Note:
    string: int
    fret: int
    raw_pos: int
    duration: int | None = None


@dataclass
class Bar:
    notes: list[Note] = field(default_factory=list)
    barline: str | None = None
    repeat: str | None = None
    time_sig: str | None = None
    chords: list[Chord] = field(default_factory=list)


@dataclass
class Chord:
    note_type: int
    dotted: bool
    grid: str | None
    notes: list[Note] = field(default_factory=list)


@dataclass
class Piece:
    title: str | None = None
    subtitle: str | None = None
    author: str | None = None
    composer: str | None = None
    footnote: str | None = None
    tuning: str | None = None
    style: str | None = None
    bars: list[Bar] = field(default_factory=list)
    strings: int = 6
