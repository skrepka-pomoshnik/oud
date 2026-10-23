"""Decode counted lyric cells in notation records before applying text heuristics."""

from __future__ import annotations

import re

from oud.importers.ft3.musical.note_records import _best_ft3_note_run, decode_ft3_note_record
from oud.importers.ft3.text.types import FT3TextRecord
from petrucci.core.model import ImportedTextRow, LyricEvent

_TRAILER = bytes(6)
_MAX_CELLS = 4096
_FONT_NAMES = frozenset(("arial", "times new roman", "new roman"))
_NOTATION_RECORD_PREFIX = b"\x04\x11\x00\x00\xff"


def _read_cells(data: bytes, start: int, count: int) -> list[str] | None:
    cells: list[str] = []
    cursor = start
    for _ in range(count):
        if cursor >= len(data):
            return None
        size = data[cursor]
        cursor += 1
        end = cursor + size
        if end > len(data):
            return None
        raw = data[cursor:end]
        if any(byte < ord(" ") for byte in raw.replace(b"\r\n", b"")):
            return None
        try:
            cells.append(raw.decode("cp1252"))
        except UnicodeDecodeError:
            return None
        cursor = end
    return cells if cursor == len(data) else None


def _counted_cells(data: bytes, start: int, count: int) -> list[str] | None:
    closing = re.search(rb"\x00{6}C>95.{0,48}$", data, flags=re.DOTALL)
    if closing is not None:
        data = data[: closing.start() + len(_TRAILER)]
    if not 0 < count <= _MAX_CELLS or not data.endswith(_TRAILER):
        return None
    payload = data[: -len(_TRAILER)]
    marker = count.to_bytes(2, "little")
    candidates: list[list[str]] = []
    cursor = payload.find(marker, start)
    while cursor >= 0:
        cells = _read_cells(payload, cursor + len(marker), count)
        if cells is not None:
            candidates.append(cells)
        if len(candidates) > 1:
            return None
        cursor = payload.find(marker, cursor + 1)
    return candidates[0] if candidates else None


def _cell_event(text: str, onset: int, verse: int, *, chain_open: bool) -> LyricEvent:
    source = text.strip()
    extender = bool(source) and set(source) <= {"_"}
    starts = source.startswith("-") or chain_open
    ends = source.endswith("-")
    syllabic = ("middle" if ends else "end") if starts else ("begin" if ends else "single")
    return LyricEvent(
        "" if extender else source.strip("-").strip(),
        onset,
        verse=verse,
        syllabic=syllabic,
        src_pos=onset,
        extender=extender,
    )


def _music_font_cells(chunk: bytes, start: int) -> list[str] | None:
    """Recognize non-alphabetic source cells when note grouping is only partial."""
    if not chunk.endswith(_TRAILER):
        return None
    payload = chunk[: -len(_TRAILER)]
    candidates: list[list[str]] = []
    for cursor in range(start, len(payload) - 2):
        count = int.from_bytes(payload[cursor : cursor + 2], "little")
        if not 0 < count <= min(_MAX_CELLS, len(payload) - cursor - 2):
            continue
        cells = _read_cells(payload, cursor + 2, count)
        if cells and any(cells) and not any(char.isalpha() or char == "_" for cell in cells for char in cell):
            candidates.append(cells)
    return candidates[0] if len(candidates) == 1 else None


def _verse_rows(cells: list[str]) -> tuple[list[str], list[list[LyricEvent]]]:
    # Numeric music-font cells occur in instrumental notation records. Keep
    # them as source controls rather than promoting them into sung syllables.
    if any(cells) and not any(char.isalpha() or char == "_" for cell in cells for char in cell):
        return [], []
    columns = [cell.split("\r\n") for cell in cells]
    lines: list[str] = []
    rows: list[list[LyricEvent]] = []
    for verse in range(max(map(len, columns))):
        source = [column[verse] if verse < len(column) else "" for column in columns]
        lines.append(" ".join(source).strip())
        events: list[LyricEvent] = []
        chain_open = False
        for onset, text in enumerate(source):
            if not text.strip():
                continue
            event = _cell_event(text, onset, verse, chain_open=chain_open)
            events.append(event)
            if not event.extender:
                chain_open = event.syllabic in {"begin", "middle"}
        rows.append(events)
    return lines, rows


def _editorial_text(prefix: bytes) -> list[str]:
    """Retain explicitly framed annotations before the notation run, not geometry."""
    texts: list[str] = []
    for marker in re.finditer(rb"\x01\x00([\x01-\xfe])", prefix):
        end = marker.end() + marker.group(1)[0]
        cells = _read_cells(prefix[marker.end() - 1 : end], 0, 1)
        if not cells:
            continue
        text = cells[0].strip()
        if text.casefold() not in _FONT_NAMES and any(char.isalpha() for char in text):
            texts.append(text)
    return list(dict.fromkeys(texts))


def decode_packed_lyrics(chunk: bytes) -> FT3TextRecord | None:
    """Recognize an exact counted tail; leave ambiguous/unknown layouts untouched.

    The notation decoder owns note-run boundaries. Reusing its internal run
    reader keeps text decoding out of musical attributes and avoids a second
    competing scanner for the same binary note groups.
    """
    run = _best_ft3_note_run(chunk)
    count = int.from_bytes(chunk[28:30], "little") + 1 if chunk[2:7] == _NOTATION_RECORD_PREFIX else 0
    start = 32
    if run is not None:
        count = count or len(run.groups)
        start = run.end
    if not count:
        return None
    cells = _counted_cells(chunk, start, count)
    cells = cells or (_counted_cells(chunk, start, len(run.groups)) if run is not None else None)
    cells = cells or (_music_font_cells(chunk, start) if chunk[2:7] == _NOTATION_RECORD_PREFIX else None)
    if cells is None:
        return None
    lines, rows = _verse_rows(cells)
    editorial = _editorial_text(chunk[: run.start if run is not None else 30])
    text_rows = [
        ImportedTextRow(row_index=index, kind="editorial", text=text, tokens=text.split())
        for index, text in enumerate(editorial)
    ]
    text_rows.extend(
        ImportedTextRow(row_index=len(editorial) + index, kind="lyrics", text=line, tokens=line.split())
        for index, line in enumerate(lines)
    )
    if not lines:
        text_rows.append(
            ImportedTextRow(row_index=len(text_rows), kind="control", text="\r\n".join(cells), tokens=cells)
        )
    return FT3TextRecord(
        melody_grid=None,
        lyrics=lines,
        melody_events=decode_ft3_note_record(chunk),
        lyric_event_rows=rows,
        editorial_text=editorial,
        structured_rows=text_rows,
        parse_mode="structured",
    )
