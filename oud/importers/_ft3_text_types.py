from __future__ import annotations

from dataclasses import dataclass

from petrucci.model import ImportedTextRow, LyricEvent, MelodyEvent


@dataclass(frozen=True)
class FT3TextRecord:
    melody_grid: str | None
    lyrics: list[str]
    melody_events: list[MelodyEvent]
    lyric_event_rows: list[list[LyricEvent]]
    editorial_text: list[str]
    structured_rows: list[ImportedTextRow]
    parse_mode: str = "ascii"


def empty_text_record() -> FT3TextRecord:
    return FT3TextRecord(
        melody_grid=None,
        lyrics=[],
        melody_events=[],
        lyric_event_rows=[],
        editorial_text=[],
        structured_rows=[],
        parse_mode="ascii",
    )
