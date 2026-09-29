from __future__ import annotations

import unicodedata

from petrucci.core.model import Piece
from petrucci.input.tablature.input import REST_OVERRIDE
from petrucci.terminal.canvas.screen import CursesError, Screen


def _split_display_clusters(text: str) -> list[str]:
    clusters: list[str] = []
    for ch in text:
        if unicodedata.combining(ch):
            if clusters:
                clusters[-1] += ch
            continue
        clusters.append(ch)
    return clusters


def _clip_display_width(text: str, max_cols: int) -> str:
    if max_cols <= 0 or not text:
        return ""
    clusters = _split_display_clusters(text)
    if len(clusters) <= max_cols:
        return text
    return "".join(clusters[:max_cols])


def _drop_display_cols_left(text: str, skip_cols: int) -> str:
    if skip_cols <= 0 or not text:
        return text
    clusters = _split_display_clusters(text)
    if skip_cols >= len(clusters):
        return ""
    return "".join(clusters[skip_cols:])


def safe_addstr(stdscr: Screen, y: int, x: int, text: str, attr: int = 0) -> None:
    height, width = stdscr.getmaxyx()
    if height <= 0 or width <= 0:
        return
    if y < 0 or y >= height or x >= width:
        return
    if x < 0:
        text = _drop_display_cols_left(text, -x)
        x = 0
    if x >= width:
        return
    clipped = _clip_display_width(text, max(0, width - x))
    try:
        stdscr.addstr(y, x, clipped, attr)
    except CursesError:
        return
    except ValueError:
        return


def clean_text(text: str) -> str:
    return "".join(ch if ord(" ") <= ord(ch) <= ord("~") else " " for ch in text)


def pad_row(row: list[str], width: int, pad: int, *, pad_char: str = " ") -> list[str]:
    if width <= 0:
        return []
    pad = max(0, min(pad, max(0, (width - 1) // 2)))
    if pad == 0:
        if len(row) < width:
            return row + [" "] * (width - len(row))
        return row[:width]
    content_width = max(1, width - pad * 2)
    if len(row) < content_width:
        row = row + [" "] * (content_width - len(row))
    row = row[:content_width]
    return ([pad_char] * pad) + row + ([pad_char] * pad)


def flag_symbols(style: str, flaglean: str = "right") -> tuple[str, str]:
    lean = "left" if (flaglean or "right").strip().lower() == "left" else "right"
    slash_flag = "/" if lean == "left" else "\\"
    symbols = {
        "italian": ("I", slash_flag),
        "thin": ("|", slash_flag),
        "board": ("|", "="),
        "englishgrid": ("|", "-"),
        "continental": ("Γ", "F"),
        "capirola": ("I", "-"),
    }
    return symbols.get(style, ("|", slash_flag))


def _override_bass_strings(overrides: dict[tuple[int, int, int], str]) -> set[int]:
    bass_course_start = 6
    return {string for _bar, string, _column in overrides if string >= bass_course_start}


def _piece_bass_strings(piece: Piece) -> set[int]:
    bass_course_start = 6
    direct = {note.string - 1 for bar in piece.bars for note in bar.notes if note.string - 1 >= bass_course_start}
    chordal = {
        note.string - 1
        for bar in piece.bars
        for chord in bar.chords
        for note in chord.notes
        if note.string - 1 >= bass_course_start
    }
    return direct | chordal


def bass_strings_used(piece: Piece, overrides: dict[tuple[int, int, int], str]) -> set[int]:
    return _override_bass_strings(overrides) | _piece_bass_strings(piece)


def apply_overrides(
    cells: list[list[str]],
    overrides: dict[tuple[int, int, int], str],
    bar_index: int,
    strings: int,
    bar_width: int,
) -> None:
    for s_idx in range(strings):
        for col in range(bar_width):
            key = (bar_index, s_idx, col)
            if key not in overrides:
                continue
            value = overrides[key]
            if value == REST_OVERRIDE:
                cells[s_idx][col] = "_"
                next_col = col + 1
                if (
                    next_col < bar_width
                    and cells[s_idx][next_col] in ("-", " ")
                    and (bar_index, s_idx, next_col) not in overrides
                ):
                    cells[s_idx][next_col] = "."
            else:
                cells[s_idx][col] = value
