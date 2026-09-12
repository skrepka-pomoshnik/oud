from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

_MIDI_DATA_BYTE_LIMIT = 0x80
_MIDI_STATUS_BYTE_LIMIT = 0xF0
_MIDI_META_STATUS = 0xFF
_MIDI_NOTE_ON_STATUS = 0x90
_TWO_BYTE_MESSAGE_SIZE = 2
_MIDI_HEADER_SIZE = 14

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
        if byte < _MIDI_DATA_BYTE_LIMIT:
            return value, offset
    raise MidiFormatError(ERR_VLQ)


def _read_track_status(track: bytes, offset: int, running_status: int | None) -> tuple[int, int, int | None]:
    status = track[offset]
    if status >= _MIDI_DATA_BYTE_LIMIT:
        offset += 1
        if status < _MIDI_STATUS_BYTE_LIMIT:
            running_status = status
    elif running_status is not None:
        status = running_status
    else:
        raise MidiFormatError(ERR_RUNNING)
    return status, offset, running_status


def _consume_system_event(track: bytes, status: int, offset: int) -> tuple[int, bool]:
    if status == _MIDI_META_STATUS:
        if offset >= len(track):
            raise MidiFormatError(ERR_META)
        offset += 1
        size, offset = _read_vlq(track, offset)
        offset += size
        return offset, True
    if status in {0xF0, 0xF7}:
        size, offset = _read_vlq(track, offset)
        return offset + size, True
    return offset, False


def _read_channel_event(track: bytes, status: int, offset: int) -> tuple[int, int | None]:
    kind = status & 0xF0
    size = 1 if kind in {0xC0, 0xD0} else 2
    if offset + size > len(track):
        raise MidiFormatError(ERR_CHANNEL)
    first = track[offset]
    second = track[offset + 1] if size == _TWO_BYTE_MESSAGE_SIZE else 0
    offset += size
    pitch = first if kind == _MIDI_NOTE_ON_STATUS and second else None
    return offset, pitch


def _track_notes(track: bytes, ppq: int) -> list[MidiNote]:
    notes: list[MidiNote] = []
    offset = 0
    tick = 0
    running_status: int | None = None
    while offset < len(track):
        delta, offset = _read_vlq(track, offset)
        tick += delta
        if offset >= len(track):
            raise MidiFormatError(ERR_EVENT)
        status, offset, running_status = _read_track_status(track, offset, running_status)
        offset, is_system = _consume_system_event(track, status, offset)
        if is_system:
            continue
        offset, pitch = _read_channel_event(track, status, offset)
        if pitch is not None:
            notes.append(MidiNote(Fraction(tick, ppq), status & 0x0F, pitch))
    return notes


def read_midi_notes(path: Path) -> MidiNotes:
    data = path.read_bytes()
    if len(data) < _MIDI_HEADER_SIZE or data[:4] != b"MThd":
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
