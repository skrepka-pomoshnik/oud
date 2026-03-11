from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Note:
    string: int
    fret: int
    raw_pos: int
    duration: int | None = None
    right_fingering: str | None = None
    left_fingering: str | None = None
    right_ornament: str | None = None
    left_ornament: str | None = None
    ft3_extras: int | None = None


@dataclass(frozen=True)
class MelodyEvent:
    text: str
    onset_index: int
    src_pos: int = 0
    note_type: int | None = None
    dotted: bool = False


@dataclass(frozen=True)
class LyricEvent:
    text: str
    onset_index: int
    verse: int = 0
    syllabic: str = "single"  # single|begin|middle|end
    src_pos: int = 0
    extender: bool = False


@dataclass
class Bar:
    notes: list[Note] = field(default_factory=list)
    barline: str | None = None
    repeat: str | None = None
    time_sig: str | None = None
    dynamic: str | None = None
    fermata: bool = False
    chords: list[Chord] = field(default_factory=list)
    melody_grid: str | None = None
    lyrics: list[str] = field(default_factory=list)
    melody_events: list[MelodyEvent] = field(default_factory=list)
    lyric_event_rows: list[list[LyricEvent]] = field(default_factory=list)


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
    arranger: str | None = None
    footnote: str | None = None
    footnote_source: str | None = None
    footnote_editor: str | None = None
    footnote_comment: str | None = None
    key: str | None = None
    piece_type: str | None = None
    difficulty: str | None = None
    ensemble: str | None = None
    part: str | None = None
    instrumentation: str | None = None
    source: str | None = None
    editor: str | None = None
    comment: str | None = None
    publisher: str | None = None
    volume: str | None = None
    page: str | None = None
    section_annotations: dict[str, str] = field(default_factory=dict)
    import_warnings: list[str] = field(default_factory=list)
    tuning: str | None = None
    style: str | None = None
    bars: list[Bar] = field(default_factory=list)
    strings: int = 6
