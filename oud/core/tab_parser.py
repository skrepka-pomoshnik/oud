from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from oud.core.model import Bar, Chord, Note, Piece

FLAG_TO_NOTE_TYPE = {
    "W": 2,
    "w": 3,
    "B": 2,
    "L": 2,
    "0": 4,
    "1": 5,
    "2": 6,
    "3": 7,
    "4": 8,
    "5": 9,
    "6": 10,
}


@dataclass(slots=True)
class TabData:
    piece: Piece
    overrides: dict[tuple[int, int, int], str]
    durations: dict[tuple[int, int, int], int]
    dotted: set[tuple[int, int]]
    bar_width: int


def _is_fret_char(ch: str) -> bool:
    return ch in "abcdefghiklmnopqrst" or ch.isdigit() or ch in {"x", "r", "E"}


def _fret_from_char(ch: str, prefer_alt_c: bool) -> int | None:
    letters = "abcdefghiklmnopqrst"
    if prefer_alt_c and ch == "r":
        return 2
    if ch in letters:
        return letters.index(ch)
    if ch.isdigit():
        return int(ch)
    return {"x": 10, "r": 2, "E": 4}.get(ch)


def _parse_time_signature(sig: str) -> str | None:
    if sig == "Sc":
        return "C"
    if sig == "Sc|":
        return "C|"
    if sig.startswith("S") and len(sig) >= 2:
        return sig[1:]
    return None


def _note_type_for_flag(flag: str, last: int | None) -> int | None:
    if flag == "x":
        return last
    return FLAG_TO_NOTE_TYPE.get(flag)


def _looks_like_hash_header(line: str) -> bool:
    text = line[1:].strip()
    if not text:
        return True
    if ":" in text:
        return True
    return text.startswith((" ", "\t"))


def _normalize_chord_line(line: str) -> str:
    if not line:
        return line
    if line[0] not in {"Y", "y"}:
        return line
    if len(line) == 1:
        return ""
    second = line[1]
    if second in ".bB":
        return ""
    if second in {"#", "x", "w", "W", "B", "L"} or second.isdigit():
        return line[1:]
    return f"0{line[1:]}"


def _parse_chord_line(  # noqa: C901
    line: str, strings: int, last_note_type: int | None,
) -> tuple[Chord | None, int | None]:
    text = _normalize_chord_line(line)
    if not text:
        return None, last_note_type
    idx = 0
    grid = None
    if text.startswith("#"):
        grid = "start"
        idx += 1
        if idx >= len(text):
            return None, last_note_type
    flag = text[idx]
    if flag.isspace():
        return None, last_note_type
    dotted = False
    rest = text[idx + 1:]
    if rest.startswith("!"):
        rest = rest[1:]
    if rest.startswith("."):
        dotted = True
        rest = rest[1:]
    if rest.startswith("#"):
        grid = "start"
        rest = rest[1:]
    note_type = _note_type_for_flag(flag, last_note_type)
    if note_type is None:
        return None, last_note_type

    text = rest.rstrip("\n")
    if len(text) < strings:
        text = text.ljust(strings)
    prefer_alt_c = not any(ch in text for ch in "qst")

    chord = Chord(note_type=note_type, dotted=dotted, grid=grid)
    for idx, ch in enumerate(text[:strings]):
        if _is_fret_char(ch):
            fret = _fret_from_char(ch, prefer_alt_c)
            if fret is None:
                continue
            note = Note(string=idx + 1, fret=fret, raw_pos=0)
            chord.notes.append(note)
    return chord, note_type


def _apply_title_block(piece: Piece, text: str) -> None:
    if "/" in text and not piece.title and not piece.composer:
        title, composer = text.split("/", 1)
        title = title.strip()
        composer = composer.strip()
        if title:
            piece.title = title
        if composer:
            piece.composer = composer
        return
    if not piece.title:
        piece.title = text
    elif not piece.author:
        piece.author = text


def load_tab_data(path: str, strings: int = 6) -> TabData | None:
    piece = load_tab(path, strings=strings)
    if not piece.bars and not piece.title and not piece.author and not piece.composer:
        return None
    return TabData(
        piece=piece,
        overrides={},
        durations={},
        dotted=set(),
        bar_width=0,
    )


def load_tab(path: str, strings: int = 6) -> Piece:  # noqa: PLR0912, C901
    # Format cues inspired by luteconv tab parsing.
    piece = Piece(title=None, author=None, composer=None, bars=[], strings=strings)
    current_bar = Bar()
    last_note_type: int | None = None
    saw_letters = False
    saw_digits = False
    default_time: str | None = None
    with Path(path).open(encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = raw.rstrip("\n").rstrip("\r")
            if not line:
                continue
            if line.startswith("{") and line.endswith("}"):
                text = line.strip("{}").strip()
                _apply_title_block(piece, text)
                continue
            if line.startswith("#") and _looks_like_hash_header(line):
                header = line[1:].strip()
                if header.lower().startswith("tuning:"):
                    piece.tuning = header.split(":", 1)[1].strip()
                elif header.lower().startswith(("time:", "timesig:", "meter:")):
                    value = header.split(":", 1)[1].strip()
                    parsed = _parse_time_signature(value)
                    default_time = parsed
                    if current_bar.time_sig is None and parsed:
                        current_bar.time_sig = parsed
                elif header.lower().startswith("subtitle:"):
                    piece.subtitle = header.split(":", 1)[1].strip()
                elif header.lower().startswith("footnote:"):
                    piece.footnote = header.split(":", 1)[1].strip()
                continue
            if line.startswith("$"):
                header = line[1:].strip()
                if header.lower().startswith(("time=", "timesig=", "meter=")):
                    value = header.split("=", 1)[1].strip()
                    parsed = _parse_time_signature(value)
                    default_time = parsed
                    if current_bar.time_sig is None and parsed:
                        current_bar.time_sig = parsed
                continue
            if line.startswith("-tuning "):
                piece.tuning = line.split(" ", 1)[1].strip()
                continue
            if line.startswith("-"):
                continue
            if line.startswith("%"):
                continue
            if line.startswith("b"):
                if current_bar.chords or current_bar.notes:
                    piece.bars.append(current_bar)
                current_bar = Bar(time_sig=default_time)
                continue
            if line.startswith("S"):
                current_bar.time_sig = _parse_time_signature(line.strip())
                continue
            if line.strip() == "e":
                if current_bar.chords or current_bar.notes:
                    piece.bars.append(current_bar)
                current_bar = Bar(time_sig=default_time)
                last_note_type = None
                continue
            chord, last_note_type = _parse_chord_line(line, strings, last_note_type)
            if chord and chord.notes:
                current_bar.chords.append(chord)
                current_bar.notes.extend(chord.notes)
                for ch in line[1:]:
                    if "a" <= ch <= "p":
                        saw_letters = True
                    elif ch.isdigit() or ch == "x":
                        saw_digits = True
    if current_bar.chords or current_bar.notes:
        piece.bars.append(current_bar)
    if saw_letters:
        piece.style = "french"
    elif saw_digits:
        piece.style = "italian"
    return piece
