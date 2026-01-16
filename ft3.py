from __future__ import annotations

import gzip
import re
from typing import Optional

from model import Bar, Chord, Note, Piece


def read_ft3(path: str) -> bytes:
    with open(path, "rb") as f:
        magic = f.read(2)
        f.seek(0)

        if magic == b"\x1F\x8B":
            with gzip.open(path, "rb") as gz:
                return gz.read()

        return f.read()


def extract_text(data: bytes, marker: bytes) -> tuple[Optional[str], Optional[int]]:
    pos = data.find(marker)
    if pos == -1:
        return None, None
    pos += len(marker)
    length = data[pos]
    text = data[pos + 1 : pos + 1 + length].decode("utf-8", errors="ignore")
    return text, pos + 1 + length


def at_next_note(s: int, f: int) -> bool:
    on_fret = 0x30 <= f <= 0x3E
    on_diapason = 0x61 <= f <= 0x66
    on_string = 0x02 <= s <= 0x08
    return on_string and (on_fret or on_diapason)


def parse_bar(bar_data: bytes) -> Bar:
    bar = Bar()
    bar.time_sig = parse_time_signature(bar_data)
    ptr = 32

    while ptr + 9 <= len(bar_data):
        if not at_next_note(bar_data[ptr + 4], bar_data[ptr + 5]):
            ptr += 1
            continue

        note_type = bar_data[ptr] + 2
        dotted = bool(bar_data[ptr + 1] & 0x10)
        grid = None
        if bar_data[ptr + 1] & 0x02:
            grid = "start"
        elif bar_data[ptr + 1] & 0x04:
            grid = "mid"
        elif bar_data[ptr + 1] & 0x08:
            grid = "end"
        chord = Chord(note_type=note_type, dotted=dotted, grid=grid)
        ptr += 4

        while ptr + 5 <= len(bar_data) and at_next_note(bar_data[ptr], bar_data[ptr + 1]):
            string = None
            fret = None

            if bar_data[ptr] < 8:
                string = bar_data[ptr] - 1
                fret = bar_data[ptr + 1] - 0x30
            elif bar_data[ptr] == 8:
                if bar_data[ptr + 4] == 0x00:
                    string = 7
                    fret = bar_data[ptr + 1] - 0x61
                elif bar_data[ptr + 4] == 0x20:
                    string = bar_data[ptr + 1] - 0x30 + 7
                    fret = 0
                elif bar_data[ptr + 4] == 0x48:
                    string = 8
                    fret = bar_data[ptr + 1] - 0x61

            if string is not None and fret is not None:
                note = Note(string=string, fret=fret, raw_pos=ptr)
                bar.notes.append(note)
                chord.notes.append(note)

            ptr += 5

        if chord.notes:
            bar.chords.append(chord)

    return bar


def load_ft3(path: str) -> Piece:
    data = read_ft3(path)

    title, pos = extract_text(data, b"CPiece")
    author, pos = extract_text(data[pos:], b"") if pos else (None, None)
    composer, _ = extract_text(data[pos:], b"") if pos else (None, None)

    bars = [parse_bar(chunk) for chunk in re.split(b"\x03\x80", data)]
    return Piece(title=title, author=author, composer=composer, bars=bars, strings=6)


def parse_time_signature(bar_data: bytes) -> str | None:
    if len(bar_data) < 10:
        return None
    time_signature = bar_data[0] & 0x7F
    if time_signature == 0x01:
        return "C"
    if time_signature == 0x02:
        return "C|"
    if time_signature == 0x03:
        return "O"
    if time_signature == 0x06:
        beats = bar_data[9]
        beat_type = bar_data[8]
        if beats and beat_type:
            return f"{beats}/{beat_type}"
    return None


def note_type_to_denominator(note_type: int) -> int | None:
    mapping = {
        2: 1,
        3: 2,
        4: 4,
        5: 8,
        6: 16,
        7: 32,
        8: 64,
        9: 128,
        10: 256,
    }
    return mapping.get(note_type)


def build_durations(piece: Piece) -> dict[tuple[int, int, int], int]:
    durations: dict[tuple[int, int, int], int] = {}
    for b_idx, bar in enumerate(piece.bars):
        col = 0
        for chord in bar.chords:
            denom = note_type_to_denominator(chord.note_type)
            if denom is None:
                continue
            durations[(b_idx, 0, col)] = denom
            col += 1
    return durations
