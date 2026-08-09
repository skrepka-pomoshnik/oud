from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Note:
    string: int
    fret: int
    raw_pos: int
    duration: int | None = None
    barre: bool = False
    right_fingering: str | None = None
    left_fingering: str | None = None
    right_ornament: str | None = None
    left_ornament: str | None = None
    arpeggio: str | None = None
    ft3_extras: int | None = None
    ft3_extra_residual: int | None = None


@dataclass
class ImportedTextRow:
    row_index: int
    kind: str
    text: str = ""
    tokens: list[str] = field(default_factory=list)


@dataclass
class ImportedBarContent:
    source_bar_index: int
    melody_grid: str | None = None
    time_sig: str | None = None
    barline: str | None = None
    repeat: str | None = None
    ending_numbers: tuple[int, ...] = ()
    system_break: bool = False
    dynamic: str | None = None
    fermata: bool = False
    clef: str | None = None
    key_signature: str | None = None
    lyrics: list[str] = field(default_factory=list)
    melody_events: list[MelodyEvent] = field(default_factory=list)
    lyric_event_rows: list[list[LyricEvent]] = field(default_factory=list)
    editorial_text: list[str] = field(default_factory=list)
    text_rows: list[ImportedTextRow] = field(default_factory=list)


@dataclass
class ImportedStaff:
    kind: str
    label: str | None = None
    bars: list[ImportedBarContent] = field(default_factory=list)


@dataclass(frozen=True)
class ImportedSourceRecord:
    source_bar_index: int
    source_staff_index: int
    kind: str
    size: int
    source_voice_index: int = 0


@dataclass
class ImportedScore:
    source_format: str
    staffs: list[ImportedStaff] = field(default_factory=list)
    source_records: list[ImportedSourceRecord] = field(default_factory=list)


@dataclass(frozen=True)
class MelodyEvent:
    text: str
    onset_index: int
    src_pos: int = 0
    note_type: int | None = None
    dotted: bool = False
    accidental_flags: int | None = None
    is_rest: bool = False
    beam: str | None = None
    fermata: bool = False
    voice: int = 0
    ornament: str | None = None
    courtesy_accidental: bool = False
    editorial_brackets: bool = False
    tie_from_previous: bool = False
    ft3_layout_flags: int | None = None
    tuplet_actual: int | None = None
    tuplet_normal: int | None = None
    slur_start: bool = False
    slur_end: bool = False
    grace: bool = False
    source_id: str | None = None


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
    ending_numbers: tuple[int, ...] = ()
    time_sig: str | None = None
    system_break: bool = False
    page_break_before: bool = False
    section_title: str | None = None
    section_subtitle: str | None = None
    dynamic: str | None = None
    fermata: bool = False
    clef: str | None = None
    key_signature: str | None = None
    chords: list[Chord] = field(default_factory=list)
    melody_grid: str | None = None
    lyrics: list[str] = field(default_factory=list)
    melody_events: list[MelodyEvent] = field(default_factory=list)
    lyric_event_rows: list[list[LyricEvent]] = field(default_factory=list)
    editorial_text: list[str] = field(default_factory=list)
    structured_text_rows: list[ImportedTextRow] = field(default_factory=list)


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
    notes: list[str] = field(default_factory=list)
    publisher: str | None = None
    volume: str | None = None
    page: str | None = None
    section_annotations: dict[str, str] = field(default_factory=dict)
    raw_metadata: dict[str, str] = field(default_factory=dict)
    imported_score: ImportedScore | None = None
    import_warnings: list[str] = field(default_factory=list)
    tuning: str | None = None
    style: str | None = None
    bars: list[Bar] = field(default_factory=list)
    strings: int = 6
