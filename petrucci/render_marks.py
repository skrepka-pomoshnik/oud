from __future__ import annotations

import unicodedata

from petrucci.model import Bar, Chord, Note
from petrucci.render_helpers import safe_addstr
from petrucci.screen import Screen
from petrucci.view_model import (
    _ft3_display_fingering_for_note,
    _ft3_ornament_glyph,
    chord_positions,
)

_TUPLET_CUE_GLYPHS = {"²", "³", "⁴", "⁵", "⁶", "⁷", "⁸", "⁹"}


def _merge_mark_rows(base: list[str], user: list[str]) -> list[str]:
    if len(base) != len(user):
        return user
    out = list(base)
    for idx, ch in enumerate(user):
        if ch != " ":
            out[idx] = ch
    return out


def _repeat_dot_display_rows(display_strings: int) -> set[int]:
    if display_strings <= 0:
        return set()
    if display_strings == 1:
        return {0}
    hi = min(display_strings - 1, display_strings // 2)
    lo = max(0, hi - 1)
    return {lo, hi}


def _overlay_sparse_mark_chars(
    stdscr: Screen,
    *,
    y: int,
    bar_x: int,
    draw_pad: int,
    grid_map: list[int],
    row_cells: list[str],
    keep: set[str],
) -> None:
    if not row_cells or not grid_map:
        return
    for src_col, ch in enumerate(row_cells):
        if ch not in keep:
            continue
        if not (0 <= src_col < len(grid_map)):
            continue
        dst_col = grid_map[src_col]
        safe_addstr(stdscr, y, bar_x + draw_pad + dst_col, ch)


def _place_parenthesize_tie_cues(  # noqa: C901
    *,
    ann_cells: list[str],
    orn_cells: list[str],
    tie_cells: list[str],
    slur_cells: list[str] | None,
    hold_cells: list[str] | None,
    gliss_cells: list[str] | None,
    paren_tie_cols: set[int],
    allow_ann_row: bool = True,
) -> None:
    def _place_open(end_col: int) -> None:
        if allow_ann_row and 0 <= end_col < len(ann_cells) and ann_cells[end_col] == " ":
            ann_cells[end_col] = "("
            return
        for row in (tie_cells, slur_cells or [], hold_cells or [], gliss_cells or []):
            left = end_col - 1
            while 0 <= left < len(row):
                if row[left] == " ":
                    row[left] = "("
                    return
                left -= 1

    def _place_close(end_col: int) -> None:
        for row in (tie_cells, orn_cells, slur_cells or [], hold_cells or [], gliss_cells or []):
            if 0 <= end_col < len(row) and row[end_col] == " ":
                row[end_col] = ")"
                return

    for end_col in paren_tie_cols:
        if not (0 <= end_col < len(tie_cells)):
            continue
        _place_open(end_col)
        _place_close(end_col)


def _merge_nonspace_rows(*rows: list[str]) -> list[str]:
    if not rows:
        return []
    width = len(rows[0])
    out = [" " for _ in range(width)]
    for row in rows:
        if len(row) != width:
            continue
        for idx, ch in enumerate(row):
            if ch != " ":
                out[idx] = ch
    return out


def _inline_fingering_glyph(ch: str, *, style: str = "french") -> str:
    supers = {
        "0": "⁰",
        "1": "¹",
        "2": "²",
        "3": "³",
        "4": "⁴",
        "5": "⁵",
        "6": "⁶",
        "7": "⁷",
        "8": "⁸",
        "9": "⁹",
        "t": "ᵗ",
        "T": "ᵀ",
    }
    subs = {
        "0": "₀",
        "1": "₁",
        "2": "₂",
        "3": "₃",
        "4": "₄",
        "5": "₅",
        "6": "₆",
        "7": "₇",
        "8": "₈",
        "9": "₉",
        "t": "ₜ",
        "T": "ₜ",
    }
    out: list[str] = []
    for part in ch:
        if unicodedata.combining(part):
            out.append(part)
            continue
        if style == "italian":
            out.append(supers.get(part, part))
        else:
            out.append(subs.get(part, part))
    return "".join(out)


def _combining_only_mark(text: str) -> bool:
    return bool(text) and all(unicodedata.combining(ch) for ch in text)


def _mapped_mark_column(grid_map: dict[int, int] | list[int], column: int) -> int:
    if isinstance(grid_map, dict):
        return grid_map.get(column, column)
    return grid_map[column] if 0 <= column < len(grid_map) else column


def _mark_for_source_row(
    mark: str,
    column: int,
    target_rows: list[int] | None,
    source_row_index: int | None,
) -> str:
    if mark == " " or target_rows is None or source_row_index is None:
        return mark
    if column >= len(target_rows) or target_rows[column] != source_row_index:
        return " "
    return mark


def _place_inline_mark(display_row_cells: list[str], column: int, mark: str) -> None:
    if mark == " ":
        return
    if _combining_only_mark(mark):
        display_row_cells[column] += mark
        return
    right = column + 1
    if right < len(display_row_cells) and display_row_cells[right] in ("-", " "):
        display_row_cells[right] = mark


def _inline_fingering_mark(annotation: str, *, style: str) -> str:
    return " " if annotation == " " else _inline_fingering_glyph(annotation, style=style)


def _overlay_inline_local_marks_on_display_row(
    *,
    display_row_cells: list[str],
    source_row_cells: list[str],
    ann_cells: list[str],
    orn_cells: list[str],
    draw_pad: int,
    grid_map: dict[int, int] | list[int],
    style: str = "french",
    source_row_index: int | None = None,
    ann_target_rows: list[int] | None = None,
    orn_target_rows: list[int] | None = None,
) -> None:
    width = len(source_row_cells)
    for col in range(min(width, len(ann_cells), len(orn_cells))):
        if source_row_cells[col] == "-":
            continue
        disp_col = draw_pad + _mapped_mark_column(grid_map, col)
        if not (0 <= disp_col < len(display_row_cells)):
            continue
        ornament = _mark_for_source_row(orn_cells[col], col, orn_target_rows, source_row_index)
        _place_inline_mark(display_row_cells, disp_col, ornament)
        annotation = _mark_for_source_row(ann_cells[col], col, ann_target_rows, source_row_index)
        _place_inline_mark(display_row_cells, disp_col, _inline_fingering_mark(annotation, style=style))


def _merge_span_rows_with_cue_priority(  # noqa: C901
    *,
    slur_row: list[str] | None,
    hold_row: list[str] | None,
    gliss_row: list[str] | None,
    tie_row: list[str] | None,
    tuplet_row: list[str] | None = None,
) -> list[str]:
    source_rows = (slur_row, hold_row, gliss_row, tie_row, tuplet_row)
    base_rows = [row for row in source_rows if row is not None]
    if not base_rows:
        return []
    width = len(base_rows[0])
    out = [" " for _ in range(width)]
    for idx in range(width):
        chars = [
            row[idx]
            for row in (slur_row, hold_row, tie_row, tuplet_row)
            if row is not None and idx < len(row) and row[idx] != " "
        ]
        if not chars:
            continue
        if ")" in chars:
            out[idx] = ")"
            continue
        if "(" in chars:
            out[idx] = "("
            continue
        if tuplet_row is not None and idx < len(tuplet_row) and tuplet_row[idx] != " ":
            out[idx] = tuplet_row[idx]
            continue
        if tie_row is not None and idx < len(tie_row) and tie_row[idx] != " ":
            out[idx] = tie_row[idx]
            continue
        if gliss_row is not None and idx < len(gliss_row) and gliss_row[idx] != " ":
            out[idx] = gliss_row[idx]
            continue
        if hold_row is not None and idx < len(hold_row) and hold_row[idx] != " ":
            out[idx] = hold_row[idx]
            continue
        if slur_row is not None and idx < len(slur_row) and slur_row[idx] != " ":
            out[idx] = slur_row[idx]
    return out


def _split_tuplet_cues_from_annotations(
    ann_cells: list[str],
    *,
    show_tuplets: bool,
) -> tuple[list[str], list[str]]:
    inline = list(ann_cells)
    tuplet = [" " for _ in ann_cells]
    for idx, ch in enumerate(ann_cells):
        if ch not in _TUPLET_CUE_GLYPHS:
            continue
        inline[idx] = " "
        if show_tuplets:
            tuplet[idx] = ch
    return inline, tuplet


def _target_note_rows_by_col(cells: list[list[str]]) -> list[int]:
    if not cells:
        return []
    width = len(cells[0])
    targets = [-1 for _ in range(width)]
    for col in range(width):
        for row_idx, row in enumerate(cells):
            if col < len(row) and row[col] != "-":
                targets[col] = row_idx
                break
    return targets


def _fingering_target(chord: Chord, total_strings: int, fingering_mode: str) -> int:
    for note in chord.notes:
        if 1 <= note.string <= total_strings and _ft3_display_fingering_for_note(
            note,
            fingering_mode=fingering_mode,
        ):
            return note.string - 1
    return -1


def _selected_ornament(note: Note, ornament_mode: str) -> str | None:
    return {
        "left": note.left_ornament,
        "right": note.right_ornament,
        "both": note.left_ornament or note.right_ornament,
    }.get(ornament_mode)


def _ornament_target(chord: Chord, total_strings: int, ornament_mode: str) -> int:
    for note in chord.notes:
        if not 1 <= note.string <= total_strings:
            continue
        if note.arpeggio or _ft3_ornament_glyph(_selected_ornament(note, ornament_mode)):
            return note.string - 1
    return -1


def _imported_ft3_mark_target_rows(
    *,
    bar: Bar,
    total_strings: int,
    grid_width: int,
    default_duration: int,
    fingering_mode: str,
    ornament_mode: str,
) -> tuple[list[int], list[int]]:
    ann_targets = [-1 for _ in range(grid_width)]
    orn_targets = [-1 for _ in range(grid_width)]
    if not getattr(bar, "chords", None):
        return ann_targets, orn_targets
    positions = chord_positions(bar, grid_width, default_duration)
    for chord, position in zip(bar.chords, positions, strict=False):
        col = position[0]
        if not (0 <= col < grid_width):
            continue
        if ann_targets[col] < 0:
            ann_targets[col] = _fingering_target(chord, total_strings, fingering_mode)
        if orn_targets[col] < 0:
            orn_targets[col] = _ornament_target(chord, total_strings, ornament_mode)
    return ann_targets, orn_targets
