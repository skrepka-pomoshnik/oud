from __future__ import annotations

import gzip
import re
from pathlib import Path

from oud.core.model import Bar, Chord, Note, Piece


def _strip_rtf(text: str) -> str:
    if "\\rtf" not in text:
        return text.strip()
    cleaned = re.sub(r"{\\fonttbl.*?}", " ", text, flags=re.S)
    cleaned = re.sub(r"{\\colortbl.*?}", " ", cleaned, flags=re.S)
    cleaned = re.sub(r"\\'[0-9a-fA-F]{2}", "", cleaned)
    cleaned = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", cleaned)
    cleaned = re.sub(r"\\[{}]", "", cleaned)
    cleaned = cleaned.replace("{", " ").replace("}", " ")
    cleaned = re.sub(r"[\x00-\x1f]+", " ", cleaned)
    cleaned = cleaned.replace("~", " ")
    cleaned = re.sub(r"\\+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def read_ft3(path: str) -> bytes:
    with Path(path).open("rb") as f:
        magic = f.read(2)
        f.seek(0)

        if magic == b"\x1F\x8B":
            with gzip.open(path, "rb") as gz:
                return gz.read()

        return f.read()


def extract_text(data: bytes, marker: bytes) -> tuple[str | None, int | None]:
    pos = data.find(marker)
    if pos == -1:
        return None, None
    pos += len(marker)
    if marker == b"CPiece":
        start = data.find(b"{\\rtf", pos)
        if start != -1:
            end = data.find(b"}\r\n~", start)
            if end != -1:
                raw = data[start : end + 1]
                text = raw.decode("utf-8", errors="ignore")
                return text, end + 1
        if pos + 4 <= len(data):
            length = int.from_bytes(data[pos : pos + 4], "little")
            if 0 < length <= len(data) - (pos + 4):
                raw = data[pos + 4 : pos + 4 + length]
                start = raw.find(b"{")
                if start != -1:
                    raw = raw[start:]
                text = raw.decode("utf-8", errors="ignore")
                return text, pos + 4 + length
    length = data[pos]
    text = data[pos + 1 : pos + 1 + length].decode("utf-8", errors="ignore")
    return text, pos + 1 + length


def at_next_note(s: int, f: int) -> bool:
    on_fret = 0x30 <= f <= 0x3E
    on_diapason = 0x61 <= f <= 0x66
    on_string = 0x02 <= s <= 0x08
    return on_string and (on_fret or on_diapason)


def parse_bar(bar_data: bytes) -> Bar:  # noqa: PLR0912, C901
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
                fret_byte = bar_data[ptr + 1]
                fret = fret_byte - 0x61 if 0x61 <= fret_byte <= 0x7A else fret_byte - 0x30
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

    title, _pos = extract_text(data, b"CPiece")
    if title:
        title = _strip_rtf(title)
    author = None
    composer = None

    bars = [parse_bar(chunk) for chunk in re.split(b"\x03\x80", data)]
    max_string = 0
    for bar in bars:
        for note in bar.notes:
            max_string = max(max_string, note.string + 1)
    strings = max(6, max_string) if max_string else 6
    return Piece(title=title, author=author, composer=composer, bars=bars, strings=strings)


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
