from __future__ import annotations

from typing import Optional

from model import Bar, Chord, Note, Piece

FLAG_TO_NOTE_TYPE = {
    "W": 2,
    "w": 3,
    "0": 4,
    "1": 5,
    "2": 6,
    "3": 7,
    "4": 8,
    "5": 9,
}


def _is_fret_char(ch: str) -> bool:
    return ("a" <= ch <= "p") or ch.isdigit() or ch == "x"


def _parse_time_signature(token: str) -> Optional[str]:
    if token == "Sc":
        return "C"
    if token == "Sc|":
        return "C|"
    if token.startswith("S") and len(token) >= 2:
        return token[1:]
    return None


def _note_type_for_flag(flag: str, last: Optional[int]) -> Optional[int]:
    if flag == "x":
        return last
    return FLAG_TO_NOTE_TYPE.get(flag)


def _parse_chord_line(
    line: str, strings: int, last_note_type: Optional[int]
) -> tuple[Optional[Chord], Optional[int]]:
    if not line:
        return None, last_note_type
    flag = line[0]
    if flag.isspace():
        return None, last_note_type
    dotted = False
    rest = line[1:]
    if rest.startswith("."):
        dotted = True
        rest = rest[1:]
    note_type = _note_type_for_flag(flag, last_note_type)
    if note_type is None:
        return None, last_note_type

    text = rest.rstrip("\n")
    if len(text) < strings:
        text = text.ljust(strings)

    chord = Chord(note_type=note_type, dotted=dotted, grid=None)
    for idx, ch in enumerate(text[:strings]):
        if _is_fret_char(ch):
            fret = ord(ch) - ord("a") if "a" <= ch <= "p" else 0
            if ch.isdigit():
                fret = int(ch)
            elif ch == "x":
                fret = 10
            note = Note(string=idx + 1, fret=fret, raw_pos=0)
            chord.notes.append(note)
    return chord, note_type


def load_tab(path: str, strings: int = 6) -> Piece:
    piece = Piece(title=None, author=None, composer=None, bars=[], strings=strings)
    current_bar = Bar()
    last_note_type: Optional[int] = None
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if not line:
                continue
            if line.startswith("{") and line.endswith("}"):
                text = line.strip("{}").strip()
                if not piece.title:
                    piece.title = text
                elif not piece.author:
                    piece.author = text
                continue
            if line.startswith("%"):
                continue
            if line.startswith("b"):
                if current_bar.chords or current_bar.notes:
                    piece.bars.append(current_bar)
                current_bar = Bar()
                continue
            if line.startswith("S"):
                current_bar.time_sig = _parse_time_signature(line.strip())
                continue
            chord, last_note_type = _parse_chord_line(line, strings, last_note_type)
            if chord and chord.notes:
                current_bar.chords.append(chord)
                current_bar.notes.extend(chord.notes)
    if current_bar.chords or current_bar.notes:
        piece.bars.append(current_bar)
    return piece
