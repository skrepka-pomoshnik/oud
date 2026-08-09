"""Select lyric stanzas before terminal score layout."""

from __future__ import annotations

from dataclasses import dataclass, replace

from petrucci.model import Bar, ImportedBarContent, LyricEvent, Piece


@dataclass(frozen=True, slots=True)
class LyricDisplay:
    enabled: bool
    mode: str
    verse_index: int | None


def lyric_display(settings: dict[str, str]) -> LyricDisplay:
    """Resolve terminal lyric visibility and the selected zero-based stanza."""

    if settings.get("showlyrics", "on") != "on":
        return LyricDisplay(enabled=False, mode="off", verse_index=None)
    configured = settings.get("lyricmode")
    mode = configured if configured in {"first", "current", "all"} else ("all" if configured is None else "first")
    if mode == "all":
        return LyricDisplay(enabled=True, mode=mode, verse_index=None)
    if mode == "first":
        return LyricDisplay(enabled=True, mode=mode, verse_index=0)
    verse_text = settings.get("lyricverse", "1")
    verse = int(verse_text) if verse_text.isdigit() else 1
    return LyricDisplay(enabled=True, mode=mode, verse_index=max(1, verse) - 1)


def piece_for_lyric_display(piece: Piece, settings: dict[str, str]) -> Piece:
    """Return a shallow display projection containing only selected lyric rows."""

    display = lyric_display(settings)
    if not display.enabled or display.verse_index is None:
        return piece
    bars = [_select_bar_verse(bar, display.verse_index) for bar in piece.bars]
    imported = piece.imported_score
    if imported is None:
        return replace(piece, bars=bars)
    staffs = [
        replace(staff, bars=[_select_bar_verse(bar, display.verse_index) for bar in staff.bars])
        for staff in imported.staffs
    ]
    return replace(piece, bars=bars, imported_score=replace(imported, staffs=staffs))


def _select_bar_verse(bar: Bar | ImportedBarContent, verse_index: int) -> Bar | ImportedBarContent:
    event_rows = _selected_event_rows(bar.lyric_event_rows, verse_index)
    lyrics = [bar.lyrics[verse_index]] if verse_index < len(bar.lyrics) else []
    return replace(bar, lyrics=lyrics, lyric_event_rows=event_rows)


def _selected_event_rows(rows: list[list[LyricEvent]], verse_index: int) -> list[list[LyricEvent]]:
    for row in rows:
        if any(event.verse == verse_index for event in row):
            return [list(row)]
    if verse_index < len(rows):
        return [list(rows[verse_index])]
    return []
