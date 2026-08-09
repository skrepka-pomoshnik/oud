from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

ERR_CHANNEL = "truncated MIDI channel event"
ERR_EVENT = "truncated MIDI event"
ERR_HEADER = "missing MIDI header"
ERR_META = "truncated MIDI meta event"
ERR_RUNNING = "MIDI running status has no channel event"
ERR_SMPTE = "SMPTE or zero MIDI division is unsupported"
ERR_TRACK = "missing MIDI track header"
ERR_TRACK_DATA = "truncated MIDI track"
ERR_VLQ = "truncated MIDI variable-length quantity"


class MidiFormatError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class MidiNote:
    onset: Fraction
    channel: int
    pitch: int


@dataclass(frozen=True, slots=True)
class MidiNotes:
    ppq: int
    notes: tuple[MidiNote, ...]


def _read_vlq(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    while offset < len(data):
        byte = data[offset]
        offset += 1
        value = (value << 7) | (byte & 0x7F)
        if byte < 0x80:
            return value, offset
    raise MidiFormatError(ERR_VLQ)


def _track_notes(track: bytes, ppq: int) -> list[MidiNote]:  # noqa: C901
    notes: list[MidiNote] = []
    offset = 0
    tick = 0
    running_status: int | None = None
    while offset < len(track):
        delta, offset = _read_vlq(track, offset)
        tick += delta
        if offset >= len(track):
            raise MidiFormatError(ERR_EVENT)
        status = track[offset]
        if status >= 0x80:
            offset += 1
            if status < 0xF0:
                running_status = status
        elif running_status is not None:
            status = running_status
        else:
            raise MidiFormatError(ERR_RUNNING)
        if status == 0xFF:
            if offset >= len(track):
                raise MidiFormatError(ERR_META)
            offset += 1
            size, offset = _read_vlq(track, offset)
            offset += size
            continue
        if status in {0xF0, 0xF7}:
            size, offset = _read_vlq(track, offset)
            offset += size
            continue
        kind = status & 0xF0
        size = 1 if kind in {0xC0, 0xD0} else 2
        if offset + size > len(track):
            raise MidiFormatError(ERR_CHANNEL)
        first = track[offset]
        second = track[offset + 1] if size == 2 else 0
        offset += size
        if kind == 0x90 and second:
            notes.append(MidiNote(Fraction(tick, ppq), status & 0x0F, first))
    return notes


def read_midi_notes(path: Path) -> MidiNotes:
    data = path.read_bytes()
    if len(data) < 14 or data[:4] != b"MThd":
        raise MidiFormatError(ERR_HEADER)
    header_size = int.from_bytes(data[4:8], "big")
    track_count = int.from_bytes(data[10:12], "big")
    ppq = int.from_bytes(data[12:14], "big")
    if ppq & 0x8000 or ppq == 0:
        raise MidiFormatError(ERR_SMPTE)
    offset = 8 + header_size
    notes: list[MidiNote] = []
    for _ in range(track_count):
        if offset + 8 > len(data) or data[offset : offset + 4] != b"MTrk":
            raise MidiFormatError(ERR_TRACK)
        size = int.from_bytes(data[offset + 4 : offset + 8], "big")
        start = offset + 8
        end = start + size
        if end > len(data):
            raise MidiFormatError(ERR_TRACK_DATA)
        notes.extend(_track_notes(data[start:end], ppq))
        offset = end
    return MidiNotes(ppq=ppq, notes=tuple(sorted(notes, key=lambda note: (note.onset, note.pitch, note.channel))))
