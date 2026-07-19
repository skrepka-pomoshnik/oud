from __future__ import annotations

import re
from dataclasses import dataclass, replace

from oud.importers._ft3_text_types import FT3TextRecord, empty_text_record
from petrucci.model import MelodyEvent


def _structured_vocal_row_prefix(row: bytes) -> bytes:
    match = next(iter(re.finditer(rb"[A-Za-z][A-Za-z?'\-]*$", row)), None)
    if match is None:
        return row
    return row[: match.start()]


def _vocal_pitch_token(row_value: int, flags: int) -> str:
    scale = ["d", "e", "f", "g", "a", "b", "c"]
    idx = row_value - 1
    name = scale[idx % len(scale)]
    octave = (idx + 1) // len(scale)
    accidental = ""
    if flags & 0x1000:
        accidental = "b"
    elif flags & 0x0002:
        accidental = "#"
    if octave > 0:
        suffix = "'" * octave
        return f"{name}{accidental}{suffix}"
    if octave < 0:
        suffix = "," * -octave
        return f"{name}{accidental}{suffix}"
    return f"{name}{accidental}"


def _vocal_note_type_from_code(code: int) -> int | None:
    mapping = {
        0x32: 3,
        0x33: 4,
        0x34: 5,
        0x35: 6,
        0x36: 7,
    }
    return mapping.get(code)


def _structured_pitch_row(value: bytes) -> int:
    row = int.from_bytes(value, "little", signed=True)
    return row or 1


_FT3_VOICE_FLAG = 0x0001
_FT3_ACCIDENTAL_FLAGS = 0x2000 | 0x1000 | 0x0002
_FT3_NOTE_DURATION_CODES = frozenset((0x32, 0x33, 0x34, 0x35, 0x36))
_FT3_EVENT_FLAG_MASK = (
    0x8000 | 0x4000 | 0x2000 | 0x1000 | 0x0100 | 0x0040 | 0x0010 | 0x0008 | 0x0004 | 0x0002 | _FT3_VOICE_FLAG
)


@dataclass(frozen=True)
class _FT3EncodedNote:
    duration_code: int
    pitch_row: int
    event_flags: int
    layout_flags: int


@dataclass(frozen=True)
class _FT3NoteRun:
    start: int
    end: int
    groups: tuple[tuple[_FT3EncodedNote, ...], ...]

    @property
    def note_count(self) -> int:
        return sum(len(group) for group in self.groups)


def _ft3_standard_ornament(layout_flags: int) -> str | None:
    # The low 0x0a selector is the printed plus; the other bits retain its
    # source placement/layout variant.
    return "+" if layout_flags & 0x007F == 0x000A else None


def _melody_event_from_ft3(
    *,
    pitch_row: int,
    raw_flags: int,
    layout_flags: int,
    onset_index: int,
    note_type: int | None,
    voice: int | None = None,
) -> MelodyEvent:
    source_voice = int(bool(raw_flags & _FT3_VOICE_FLAG)) if voice is None else voice
    event_flags = raw_flags & ~_FT3_VOICE_FLAG
    is_rest = bool(event_flags & 0x0040)
    return MelodyEvent(
        text="r" if is_rest else _vocal_pitch_token(pitch_row, event_flags),
        onset_index=onset_index,
        src_pos=-1,
        note_type=note_type,
        dotted=bool(event_flags & 0x0010),
        accidental_flags=event_flags,
        is_rest=is_rest,
        fermata=bool(event_flags & 0x0100),
        voice=source_voice,
        ornament=_ft3_standard_ornament(layout_flags),
        courtesy_accidental=bool(event_flags & 0x8000 and event_flags & _FT3_ACCIDENTAL_FLAGS),
        editorial_brackets=bool(event_flags & 0x4000),
        tie_from_previous=bool(event_flags & 0x8000 and not event_flags & _FT3_ACCIDENTAL_FLAGS),
        ft3_layout_flags=layout_flags or None,
    )


def _decode_note_group(data: bytes, start: int) -> tuple[tuple[_FT3EncodedNote, ...], int] | None:
    note_count = data[start]
    end = start + 1 + note_count * 6
    if not 1 <= note_count <= 8 or end > len(data):
        return None
    notes: list[_FT3EncodedNote] = []
    pos = start + 1
    for _ in range(note_count):
        duration_code = data[pos]
        if duration_code not in _FT3_NOTE_DURATION_CODES:
            return None
        event_flags = int.from_bytes(data[pos + 2 : pos + 4], "little")
        if event_flags & ~_FT3_EVENT_FLAG_MASK:
            return None
        notes.append(
            _FT3EncodedNote(
                duration_code=duration_code,
                pitch_row=int.from_bytes(data[pos + 1 : pos + 2], "little", signed=True),
                event_flags=event_flags,
                layout_flags=int.from_bytes(data[pos + 4 : pos + 6], "little"),
            ),
        )
        pos += 6
    return tuple(notes), end


def _decode_note_run_at(data: bytes, start: int) -> _FT3NoteRun | None:
    groups: list[tuple[_FT3EncodedNote, ...]] = []
    pos = start
    while pos + 7 <= len(data):
        decoded = _decode_note_group(data, pos)
        if decoded is None:
            break
        group, pos = decoded
        groups.append(group)
    return _FT3NoteRun(start, pos, tuple(groups)) if groups else None


def _best_ft3_note_run(data: bytes) -> _FT3NoteRun | None:
    candidates = [
        run for start in range(18, max(18, len(data) - 6)) if (run := _decode_note_run_at(data, start)) is not None
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda run: (run.note_count, len(run.groups), run.end - run.start, -run.start))


def ft3_note_record_group_count(data: bytes) -> int:
    run = _best_ft3_note_run(data)
    return len(run.groups) if run is not None else 0


def decode_ft3_note_record(data: bytes, *, voice: int | None = None) -> list[MelodyEvent]:
    run = _best_ft3_note_run(data)
    if run is None:
        return []
    events = [
        _melody_event_from_ft3(
            pitch_row=note.pitch_row,
            raw_flags=note.event_flags,
            layout_flags=note.layout_flags,
            onset_index=onset_index,
            note_type=_vocal_note_type_from_code(note.duration_code),
            voice=voice,
        )
        for onset_index, group in enumerate(run.groups)
        for note in group
    ]
    return _decode_vocal_beams(events)


def _decode_vocal_beams(events: list[MelodyEvent]) -> list[MelodyEvent]:
    beams: list[str | None] = [None] * len(events)
    for end_index, event in enumerate(events):
        if not (event.accidental_flags or 0) & 0x0008:
            continue
        beams[end_index] = "end"
        start_index = end_index - 1
        while start_index >= 0 and (events[start_index].accidental_flags or 0) & 0x0004:
            beams[start_index] = "continue"
            start_index -= 1
        if start_index >= 0:
            beams[start_index] = "start"
    return [replace(event, beam=beam) for event, beam in zip(events, beams, strict=True)]


def _structured_vocal_events(row: bytes) -> list[MelodyEvent]:
    prefix = _structured_vocal_row_prefix(row)
    if len(prefix) < 7:
        return []
    row_value = _structured_pitch_row(prefix[:1])
    first_flags = int.from_bytes(prefix[1:3], "little")
    first_layout = int.from_bytes(prefix[3:5], "little")
    events: list[MelodyEvent] = [
        _melody_event_from_ft3(
            pitch_row=row_value,
            raw_flags=first_flags,
            layout_flags=first_layout,
            onset_index=0,
            note_type=None,
        ),
    ]
    idx = 5
    while idx + 7 <= len(prefix):
        rec = prefix[idx : idx + 7]
        if rec[0] != 0x01 or rec[1] not in (0x32, 0x33, 0x34, 0x35):
            break
        flags = int.from_bytes(rec[3:5], "little")
        layout = int.from_bytes(rec[5:7], "little")
        events.append(
            _melody_event_from_ft3(
                pitch_row=_structured_pitch_row(rec[2:3]),
                raw_flags=flags,
                layout_flags=layout,
                onset_index=len(events),
                note_type=_vocal_note_type_from_code(rec[1]),
            ),
        )
        idx += 7
    if not events:
        return []
    if idx + 2 > len(prefix):
        return []
    count = int.from_bytes(prefix[idx : idx + 2], "little")
    if count != len(events) + 1 and not (count == 0 and first_layout == 0):
        return []
    return _decode_vocal_beams(events)


def decode_ft3_vocal_events(row: bytes) -> list[MelodyEvent]:
    return _structured_vocal_events(row)


def decode_ft3_annotation_group(data: bytes) -> FT3TextRecord:
    texts: list[str] = []
    index = 32
    while index < len(data):
        size = data[index]
        end = index + 1 + size
        if 0 < size <= 64 and end <= len(data):
            raw = data[index + 1 : end]
            if all(32 <= value <= 126 for value in raw):
                text = raw.decode("latin1").strip()
                if any(char.isalpha() for char in text) and text not in texts:
                    texts.append(text)
                index = end
                continue
        index += 1
    return replace(empty_text_record(), editorial_text=texts, parse_mode="structured")
