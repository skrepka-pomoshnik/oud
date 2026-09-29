"""Hand-built FT3 payloads for tests.

Bytes follow ``docs/ft3-format.md``: a ``CPiece`` header, ``CBar``, then one
32-byte-header record per tablature bar separated by ``03 80``. The notes are
short original passages, not excerpts from any distributed corpus.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

RECORD_SEPARATOR = b"\x03\x80"
HEADER_SIZE = 32
METER_COMMON = 0x01
METER_EXPLICIT = 0x06
RHYTHM_CODE_OFFSET = 2  # chord header byte 0 is note_type - 2
QUARTER_NOTE_TYPE = 4
DOTTED_FLAG = 0x10
DIGIT_FRET_BASE = 0x30
LETTER_FRET_BASE = 0x61


@dataclass(frozen=True)
class Ft3Chord:
    """A chord of ``(course, fret)`` pairs with a note type (4 = quarter, 6 = sixteenth)."""

    notes: tuple[tuple[int, int], ...]
    note_type: int = QUARTER_NOTE_TYPE
    dotted: bool = False


def chord(*notes: tuple[int, int], note_type: int = QUARTER_NOTE_TYPE, dotted: bool = False) -> Ft3Chord:
    return Ft3Chord(tuple(notes), note_type, dotted)


def _note_bytes(course: int, fret: int) -> bytes:
    # Main courses 1..6 use string bytes 2..7; frets are French letters (a = open).
    return bytes([course + 1, LETTER_FRET_BASE + fret, 0, 0, 0])


def _chord_bytes(item: Ft3Chord) -> bytes:
    item_count = (len(item.notes) + 1).to_bytes(2, "little")
    flags = DOTTED_FLAG if item.dotted else 0
    header = bytes([item.note_type - RHYTHM_CODE_OFFSET, flags, 0, 0])
    return item_count + header + b"".join(_note_bytes(course, fret) for course, fret in item.notes)


def ft3_bar(chords: Sequence[Ft3Chord], *, meter: str | None = None) -> bytes:
    """One tablature bar record; ``meter`` is ``"C"`` or ``"n/d"`` for an explicit meter."""

    header = bytearray(HEADER_SIZE)
    if meter == "C":
        header[0] = METER_COMMON
    elif meter is not None:
        beats, beat_type = (int(part) for part in meter.split("/"))
        header[0] = METER_EXPLICIT
        header[8] = beat_type
        header[9] = beats
    header[28:30] = (len(chords) - 1).to_bytes(2, "little")
    return bytes(header) + b"".join(_chord_bytes(item) for item in chords)


def ft3_payload(title: str, bars: Sequence[bytes]) -> bytes:
    """A plain (not gzip) FT3 file: ``CPiece`` title, ``CBar``, then the bar records."""

    title_bytes = title.encode("latin1")
    head = b"CPiece" + bytes([len(title_bytes)]) + title_bytes
    return head + RECORD_SEPARATOR + b"CBar" + RECORD_SEPARATOR.join(bars) + RECORD_SEPARATOR


def write_ft3(path: Path, title: str, bars: Sequence[bytes]) -> Path:
    path.write_bytes(ft3_payload(title, bars))
    return path


EIGHTH = 5
SIXTEENTH = 6
THIRTY_SECOND = 7


def galliard_bars() -> list[bytes]:
    """Six 4/4 bars in the style of an eight-course galliard: a half-filled pickup, bars of
    eighths, sixteenths and thirty-seconds that stop short of the meter, then full bars."""

    pickup = ft3_bar(
        [chord((1, 0), (5, 2)), chord((2, 1), note_type=EIGHTH), chord((3, 0), note_type=EIGHTH)],
        meter="4/4",
    )
    runs = ft3_bar(
        [
            chord((1, 0), (4, 2), note_type=EIGHTH),
            chord((2, 3), note_type=EIGHTH),
            chord((3, 2), note_type=SIXTEENTH),
            chord((2, 1), note_type=SIXTEENTH),
            chord((1, 0), note_type=SIXTEENTH),
            chord((2, 1), (5, 0), note_type=SIXTEENTH),
        ]
    )
    dense = ft3_bar(
        [chord((1, 3), (4, 0), note_type=SIXTEENTH), chord((2, 0), note_type=SIXTEENTH)]
        + [chord((1 + index % 3, index % 4), note_type=THIRTY_SECOND) for index in range(12)]
    )
    dotted = ft3_bar(
        [
            chord((1, 0), (6, 0), note_type=4, dotted=True),
            chord((2, 1), note_type=EIGHTH),
            chord((3, 2), note_type=4),
            chord((2, 0), (4, 2), note_type=4),
        ]
    )
    full_eighths = ft3_bar([chord((1 + index % 4, index % 3), note_type=EIGHTH) for index in range(8)])
    closing = ft3_bar([chord((1, 0), (3, 0), (6, 0), note_type=2)])
    return [pickup, runs, dense, dotted, full_eighths, closing]


def write_galliard(directory: Path, name: str = "galliard.ft3") -> Path:
    return write_ft3(directory / name, "Short galliard", galliard_bars())
