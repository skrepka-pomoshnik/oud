from __future__ import annotations

from dataclasses import dataclass

from core.model import Bar, Chord, Note, Piece

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

DUR_CHAR_TO_DENOM = {
    "1": 1,
    "2": 2,
    "4": 4,
    "8": 8,
    "6": 16,
    "3": 32,
}


@dataclass(slots=True)
class TabData:
    piece: Piece
    overrides: dict[tuple[int, int, int], str]
    durations: dict[tuple[int, int, int], int]
    dotted: set[tuple[int, int]]
    bar_width: int


def _is_fret_char(ch: str) -> bool:
    return ("a" <= ch <= "p") or ch.isdigit() or ch == "x"


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


def _parse_chord_line(
    line: str, strings: int, last_note_type: int | None
) -> tuple[Chord | None, int | None]:
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


def _parse_export_header(piece: Piece, header: str) -> None:
    lower = header.lower()
    if lower.startswith("title:"):
        piece.title = header.split(":", 1)[1].strip()
    elif lower.startswith("subtitle:"):
        piece.subtitle = header.split(":", 1)[1].strip()
    elif lower.startswith("author:"):
        piece.author = header.split(":", 1)[1].strip()
    elif lower.startswith("composer:"):
        piece.composer = header.split(":", 1)[1].strip()
    elif lower.startswith("footnote:"):
        piece.footnote = header.split(":", 1)[1].strip()
    elif lower.startswith("tuning:"):
        piece.tuning = header.split(":", 1)[1].strip()
    elif lower.startswith("strings:"):
        value = header.split(":", 1)[1].strip()
        if value.isdigit():
            piece.strings = int(value)


def _parse_export_bar(  # noqa: PLR0912
    bar_index: int,
    rows: dict[int, str],
    durations_row: str | None,
    flag_row: str | None,
    strings: int,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    dotted: set[tuple[int, int]],
) -> None:
    if not rows and durations_row is None and flag_row is None:
        return
    bar_width = 0
    for row_text in rows.values():
        bar_width = max(bar_width, len(row_text))
    if durations_row:
        bar_width = max(bar_width, len(durations_row))
    if flag_row:
        bar_width = max(bar_width, len(flag_row))

    for label, row_text in rows.items():
        if not row_text:
            continue
        padded = row_text.ljust(bar_width, "-")
        string_idx = strings - label
        if string_idx < 0 or string_idx >= strings:
            continue
        for col, ch in enumerate(padded):
            if ch in ("-", " "):
                continue
            overrides[(bar_index, string_idx, col)] = ch
    if durations_row:
        padded = durations_row.ljust(bar_width)
        for col, ch in enumerate(padded):
            denom = DUR_CHAR_TO_DENOM.get(ch)
            if denom is not None:
                durations[(bar_index, 0, col)] = denom
    if flag_row:
        padded = flag_row.ljust(bar_width)
        for col, ch in enumerate(padded):
            if ch == ".":
                dotted.add((bar_index, col))


def load_tab_data(path: str, strings: int = 6) -> TabData | None:  # noqa: PLR0912
    piece = Piece(title=None, author=None, composer=None, bars=[], strings=strings)
    overrides: dict[tuple[int, int, int], str] = {}
    durations: dict[tuple[int, int, int], int] = {}
    dotted: set[tuple[int, int]] = set()
    bar_width = 0
    rows: dict[int, str] = {}
    durations_row: str | None = None
    flag_row: str | None = None
    saw_export = False
    saw_letters = False
    saw_digits = False
    max_label = 0

    def flush_bar(bar_index: int) -> None:
        nonlocal bar_width, rows, durations_row, flag_row, max_label
        if rows or durations_row or flag_row:
            if rows:
                label_max = max(rows)
                max_label = max(max_label, label_max)
                piece.strings = max(piece.strings, max_label)
            piece.bars.append(Bar())
            _parse_export_bar(
                bar_index,
                rows,
                durations_row,
                flag_row,
                piece.strings,
                overrides,
                durations,
                dotted,
            )
            if rows:
                row_width = max(len(text) for text in rows.values())
                bar_width = max(bar_width, row_width)
            if durations_row:
                bar_width = max(bar_width, len(durations_row))
            if flag_row:
                bar_width = max(bar_width, len(flag_row))
        rows = {}
        durations_row = None
        flag_row = None

    with open(path, encoding="utf-8", errors="ignore") as f:
        bar_index = 0
        for raw in f:
            line = raw.rstrip("\n")
            if not line:
                if rows or durations_row or flag_row:
                    flush_bar(bar_index)
                    bar_index += 1
                continue
            if line.startswith("#"):
                saw_export = True
                _parse_export_header(piece, line[1:].strip())
                continue
            if line.lower().startswith("flag:"):
                saw_export = True
                flag_row = line.split(":", 1)[1].lstrip()
                continue
            if line.lower().startswith("dur:"):
                saw_export = True
                durations_row = line.split(":", 1)[1].lstrip()
                continue
            if line.lower().startswith("bar ") or line.lower().startswith("barline"):
                saw_export = True
                continue
            if line.startswith("{") and line.endswith("}"):
                text = line.strip("{}").strip()
                if not piece.title:
                    piece.title = text
                elif not piece.author:
                    piece.author = text
                continue
            if "|" in line:
                left, row_text = line.split("|", 1)
                if left.strip().isdigit():
                    saw_export = True
                    label = int(left.strip())
                    rows[label] = row_text.rstrip()
                    for ch in row_text:
                        if "a" <= ch <= "p":
                            saw_letters = True
                        elif ch.isdigit() or ch == "x":
                            saw_digits = True
                continue
            # Unknown non-export content -> bail out and use legacy parser
            if saw_export and ":" in line:
                continue
            if saw_export:
                continue
            return None
        if rows or durations_row or flag_row:
            flush_bar(bar_index)

    if not saw_export:
        return None
    if max_label:
        piece.strings = max(piece.strings, max_label)
    if saw_letters:
        piece.style = "french"
    elif saw_digits:
        piece.style = "italian"
    if not piece.bars:
        piece.bars.append(Bar())
    return TabData(
        piece=piece,
        overrides=overrides,
        durations=durations,
        dotted=dotted,
        bar_width=max(4, bar_width or 0),
    )


def load_tab(path: str, strings: int = 6) -> Piece:  # noqa: PLR0912
    parsed = load_tab_data(path, strings=strings)
    if parsed is not None:
        return parsed.piece
    piece = Piece(title=None, author=None, composer=None, bars=[], strings=strings)
    current_bar = Bar()
    last_note_type: int | None = None
    saw_letters = False
    saw_digits = False
    with open(path, encoding="utf-8", errors="ignore") as f:
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
            if line.startswith("#"):
                header = line[1:].strip()
                if header.lower().startswith("tuning:"):
                    piece.tuning = header.split(":", 1)[1].strip()
                elif header.lower().startswith("subtitle:"):
                    piece.subtitle = header.split(":", 1)[1].strip()
                elif header.lower().startswith("footnote:"):
                    piece.footnote = header.split(":", 1)[1].strip()
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
