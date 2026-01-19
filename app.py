from __future__ import annotations

import copy
import curses
import shutil
import subprocess
import sys
from pathlib import Path
from typing import cast

import tui.commands as command_mod
from core.ft3 import build_durations, load_ft3
from core.model import Bar, Chord, Piece
from core.render_utils import chord_positions, format_fret, note_type_to_denom
from core.tab_parser import load_tab, load_tab_data
from editor.commands import (
    cmd_author,
    cmd_composer,
    cmd_footnote,
    cmd_header_template,
    cmd_subtitle,
    cmd_title,
)
from editor.ops import (
    chord_index_at_col,
    delete_chord,
    denom_to_note_type,
    duration_value,
    french_to_fret,
    fret_to_french,
    fret_to_italian,
    insert_chord,
    is_french_fret,
    is_italian_fret,
    italian_to_fret,
    set_chord_note,
)
from editor.state import BarSnapshot, EditorState, UndoAction, YankedBar
from exports.export_tab import export_ascii, export_tab_to_file
from exports.lilypond import export_lilypond, print_lilypond_pdf
from exports.midi import _midi_command, export_midi, play_midi
from settings import DEFAULT_SETTINGS, load_settings, save_settings
from tui.input import (
    handle_command as handle_command_input,
)
from tui.input import (
    handle_search as handle_search_input,
)
from ui.render import _block_height, render_piece

LoadResult = tuple[
    Piece,
    dict[tuple[int, int, int], str],
    dict[tuple[int, int, int], int],
    set[tuple[int, int]],
    int | None,
]

DEFAULT_BAR_WIDTH = 12
CONFIG_PATH = "config.toml"




def _bars_per_line(state: EditorState, width: int) -> int:
    left_margin = 3
    bar_gap = _bar_gap(state)
    max_width = width
    linelen = state.settings.get("linelen", "")
    if linelen.isdigit():
        max_width = min(max_width, max(1, int(linelen)))
    usable_width = max(0, max_width - left_margin)
    bars_per_line = max(1, usable_width // (state.bar_width + bar_gap))
    maxbars = state.settings.get("maxbars", "")
    if maxbars.isdigit():
        limit = int(maxbars)
        if limit > 0:
            bars_per_line = min(bars_per_line, limit)
    return bars_per_line


def _sorted_breaks(state: EditorState, bars: int) -> list[int]:
    breaks = [idx for idx in state.stave_breaks if 0 < idx < bars]
    return sorted(set(breaks))


def _system_start_indices(
    state: EditorState, bars: int, bars_per_line: int
) -> list[int]:
    starts = [0]
    breaks = _sorted_breaks(state, bars)
    idx = 0
    while idx < bars:
        next_break = next((b for b in breaks if b > idx), bars)
        limit = min(next_break, idx + bars_per_line)
        if limit >= bars:
            break
        starts.append(limit)
        idx = limit
    return starts


def _system_index(state: EditorState, bar_index: int, bars_per_line: int) -> int:
    starts = _system_start_indices(state, len(state.piece.bars), bars_per_line)
    for idx, _start in enumerate(starts):
        if idx + 1 < len(starts) and bar_index >= starts[idx + 1]:
            continue
        return idx
    return max(0, len(starts) - 1)


def _system_start_index(
    state: EditorState, system_index: int, bars_per_line: int
) -> int:
    starts = _system_start_indices(state, len(state.piece.bars), bars_per_line)
    if system_index < 0:
        return 0
    if system_index >= len(starts):
        return starts[-1]
    return starts[system_index]


def _system_range(
    state: EditorState, bar_index: int, bars_per_line: int
) -> tuple[int, int]:
    starts = _system_start_indices(state, len(state.piece.bars), bars_per_line)
    for idx, start in enumerate(starts):
        end = starts[idx + 1] if idx + 1 < len(starts) else len(state.piece.bars)
        if start <= bar_index < end:
            return start, end
    return 0, len(state.piece.bars)

def _bar_gap(state: EditorState) -> int:
    gap = state.settings.get("bargap", "")
    if gap.isdigit():
        return max(0, int(gap))
    mode = state.settings.get("spacingmode", "packed")
    return 1 if mode in ("packed", "auto") else 3


def _rows_per_screen(state: EditorState, height: int) -> int:
    include_meta = True
    show_dur = state.settings.get("showdur", "off") == "on"
    show_extras = state.settings.get("showextras", "off") == "on"
    show_tactus = state.settings.get("showtactus", "off") == "on"
    block_h = _block_height(include_meta, state.piece.strings, show_dur, show_extras, show_tactus)
    available = max(0, height - 2 - 1)
    return max(1, available // block_h)


def _ensure_cursor_visible(state: EditorState, width: int, height: int) -> None:
    bars_per_line = _bars_per_line(state, width)
    rows_per_screen = _rows_per_screen(state, height)
    cursor_row = _system_index(state, state.cursor_bar, bars_per_line)
    first_row = _system_index(state, state.bar_offset, bars_per_line)
    if cursor_row < first_row:
        state.bar_offset = _system_start_index(state, cursor_row, bars_per_line)
    if cursor_row >= first_row + rows_per_screen:
        state.bar_offset = _system_start_index(
            state,
            cursor_row - rows_per_screen + 1,
            bars_per_line,
        )

def _allow_arrows(state: EditorState) -> bool:
    return state.settings.get("keys", "vim+arrows") != "vim"


def _is_casual(state: EditorState) -> bool:
    return state.settings.get("keys", "vim+arrows") in ("casual", "casual+arrows")


def _string_index(state: EditorState, display_index: int) -> int:
    if (
        state.settings.get("style") == "italian"
        and state.settings.get("italianorient") == "reverse"
    ):
        return state.piece.strings - 1 - display_index
    return display_index


def _cursor_key(state: EditorState) -> tuple[int, int, int]:
    return (state.cursor_bar, _string_index(state, state.cursor_string), state.cursor_col)


def _consume_count(state: EditorState) -> int:
    if not state.count_prefix:
        return 1
    try:
        value = int(state.count_prefix)
    except ValueError:
        value = 1
    state.count_prefix = ""
    return max(1, value)


def _row_first_note_col(state: EditorState) -> int:
    bar = state.cursor_bar
    string = _string_index(state, state.cursor_string)
    cols = [col for (b, s, col) in state.overrides if b == bar and s == string]
    if not cols:
        return 0
    return min(cols)


def _clear_cell(state: EditorState, bar: int, string: int, col: int) -> None:
    if 0 <= bar < len(state.piece.bars):
        bar_obj = state.piece.bars[bar]
        if bar_obj.chords:
            prev_chords = copy.deepcopy(bar_obj.chords)
            if _set_chord_note(bar_obj, state.bar_width, col, string + 1, None):
                new_chords = copy.deepcopy(bar_obj.chords)
                _record_action(
                    state,
                    UndoAction(
                        kind="chords",
                        data={"bar": bar, "prev": prev_chords, "new": new_chords},
                    ),
                )
                state.modified = True
    key = (bar, string, col)
    if key in state.overrides:
        prev = state.overrides.get(key)
        state.overrides.pop(key, None)
        _record_undo(state, "override", key, prev, None)
    prev_durations = {
        k: v for k, v in state.durations.items() if k[0] == bar and k[2] == col
    }
    if prev_durations:
        for prev_key in prev_durations:
            state.durations.pop(prev_key, None)
        _record_action(
            state,
            UndoAction(
                kind="duration_col",
                data={"bar": bar, "col": col, "prev": prev_durations, "new": {}},
            ),
        )
    dot_key = (bar, col)
    if dot_key in state.dotted:
        _record_action(
            state,
            UndoAction(
                kind="dotted",
                data={"key": dot_key, "prev": True, "new": False},
            ),
        )
        state.dotted.discard(dot_key)
    state.modified = True


def _flatten_chords_to_grid(state: EditorState, bar_index: int) -> None:
    if bar_index < 0 or bar_index >= len(state.piece.bars):
        return
    bar = state.piece.bars[bar_index]
    if not bar.chords:
        return
    style = state.settings.get("style", "french")
    french_c = state.settings.get("frenchc", "normal")
    french_e = state.settings.get("frenche", "normal")
    positions = chord_positions(bar, state.bar_width, default_duration=4)
    for chord, (col, _denom, _dot) in zip(bar.chords, positions, strict=False):
        for note in chord.notes:
            s_idx = note.string - 1
            if s_idx < 0 or s_idx >= state.piece.strings:
                continue
            key = (bar_index, s_idx, col)
            state.overrides[key] = format_fret(
                style,
                note.fret,
                french_c=french_c,
                french_e=french_e,
            )
        denom = note_type_to_denom(chord.note_type) or 4
        state.durations[(bar_index, 0, col)] = denom
        if chord.dotted:
            state.dotted.add((bar_index, col))
    bar.chords = []
    bar.notes = []
    state.modified = True


def _yank_bar(state: EditorState, index: int) -> None:
    if index < 0 or index >= len(state.piece.bars):
        return
    bar_copy = copy.deepcopy(state.piece.bars[index])
    overrides = {
        (0, s, c): value
        for (b, s, c), value in state.overrides.items()
        if b == index
    }
    durations = {
        (0, s, c): value
        for (b, s, c), value in state.durations.items()
        if b == index
    }
    annotations = {(0, c): value for (b, c), value in state.annotations.items() if b == index}
    ornaments = {(0, c): value for (b, c), value in state.ornaments.items() if b == index}
    dotted = {(0, c) for (b, c) in state.dotted if b == index}
    slurs = [(0, start, end) for (b, start, end) in state.slurs if b == index]
    ties = [(0, start, end) for (b, start, end) in state.ties if b == index]
    holds = [(0, start, end) for (b, start, end) in state.holds if b == index]
    state.yanked_bar = YankedBar(
        bar=bar_copy,
        overrides=overrides,
        durations=durations,
        annotations=annotations,
        ornaments=ornaments,
        dotted=dotted,
        slurs=slurs,
        ties=ties,
        holds=holds,
    )


def _paste_bar(state: EditorState, index: int) -> None:
    if state.yanked_bar is None:
        state.message = "No yanked bar"
        return
    _insert_bar(state, index)
    bar_copy = copy.deepcopy(state.yanked_bar.bar)
    state.piece.bars[index] = bar_copy
    for (b, s, c), value in state.yanked_bar.overrides.items():
        state.overrides[(index + b, s, c)] = value
    for (b, s, c), value in state.yanked_bar.durations.items():
        state.durations[(index + b, s, c)] = value
    for (b, c), value in state.yanked_bar.annotations.items():
        state.annotations[(index + b, c)] = value
    for (b, c), value in state.yanked_bar.ornaments.items():
        state.ornaments[(index + b, c)] = value
    for (b, c) in state.yanked_bar.dotted:
        state.dotted.add((index + b, c))
    for b, start, end in state.yanked_bar.slurs:
        state.slurs.append((index + b, start, end))
    for b, start, end in state.yanked_bar.ties:
        state.ties.append((index + b, start, end))
    for b, start, end in state.yanked_bar.holds:
        state.holds.append((index + b, start, end))
    state.modified = True


def _tuning_count(tuning: str) -> int:
    count = 0
    idx = 0
    while idx < len(tuning):
        ch = tuning[idx]
        if ch.isalpha():
            count += 1
            idx += 1
            if idx < len(tuning) and tuning[idx] in "+-#b":
                idx += 1
            while idx < len(tuning) and tuning[idx].isdigit():
                idx += 1
        else:
            idx += 1
    return count


def _set_chord_note(
    bar: Bar,
    bar_width: int,
    col: int,
    string: int,
    fret: int | None,
) -> bool:
    return set_chord_note(bar, bar_width, col, string, fret)


def _insert_chord(bar: Bar, bar_width: int, col: int) -> None:
    insert_chord(bar, bar_width, col)


def _delete_chord(bar: Bar, bar_width: int, col: int) -> bool:
    return delete_chord(bar, bar_width, col)


def _shift_triplet_dict[T](
    mapping: dict[tuple[int, int, int], T],
    start: int,
    delta: int,
    remove_index: int | None = None,
) -> dict[tuple[int, int, int], T]:
    updated: dict[tuple[int, int, int], T] = {}
    for (bar, string, col), value in mapping.items():
        if remove_index is not None and bar == remove_index:
            continue
        if bar >= start:
            updated[(bar + delta, string, col)] = value
        else:
            updated[(bar, string, col)] = value
    return updated


def _shift_triplet_set(
    entries: set[tuple[int, int, int]],
    start: int,
    delta: int,
    remove_index: int | None = None,
) -> set[tuple[int, int, int]]:
    updated: set[tuple[int, int, int]] = set()
    for bar, string, col in entries:
        if remove_index is not None and bar == remove_index:
            continue
        if bar >= start:
            updated.add((bar + delta, string, col))
        else:
            updated.add((bar, string, col))
    return updated


def _shift_pair_dict[T](
    mapping: dict[tuple[int, int], T],
    start: int,
    delta: int,
    remove_index: int | None = None,
) -> dict[tuple[int, int], T]:
    updated: dict[tuple[int, int], T] = {}
    for (bar, col), value in mapping.items():
        if remove_index is not None and bar == remove_index:
            continue
        if bar >= start:
            updated[(bar + delta, col)] = value
        else:
            updated[(bar, col)] = value
    return updated


def _shift_pair_set(
    entries: set[tuple[int, int]],
    start: int,
    delta: int,
    remove_index: int | None = None,
) -> set[tuple[int, int]]:
    updated: set[tuple[int, int]] = set()
    for bar, col in entries:
        if remove_index is not None and bar == remove_index:
            continue
        if bar >= start:
            updated.add((bar + delta, col))
        else:
            updated.add((bar, col))
    return updated


def _shift_spans(
    spans: list[tuple[int, int, int]],
    start: int,
    delta: int,
    remove_index: int | None = None,
) -> list[tuple[int, int, int]]:
    updated: list[tuple[int, int, int]] = []
    for bar, start_col, end_col in spans:
        if remove_index is not None and bar == remove_index:
            continue
        if bar >= start:
            updated.append((bar + delta, start_col, end_col))
        else:
            updated.append((bar, start_col, end_col))
    return updated


def _snapshot_bar(state: EditorState, index: int) -> BarSnapshot:
    bar = copy.deepcopy(state.piece.bars[index])
    overrides = {k: v for k, v in state.overrides.items() if k[0] == index}
    durations = {k: v for k, v in state.durations.items() if k[0] == index}
    annotations = {k: v for k, v in state.annotations.items() if k[0] == index}
    ornaments = {k: v for k, v in state.ornaments.items() if k[0] == index}
    highlights = {k for k in state.highlights if k[0] == index}
    dotted = {k for k in state.dotted if k[0] == index}
    slurs = [s for s in state.slurs if s[0] == index]
    ties = [s for s in state.ties if s[0] == index]
    holds = [s for s in state.holds if s[0] == index]
    return {
        "bar": bar,
        "overrides": overrides,
        "durations": durations,
        "annotations": annotations,
        "ornaments": ornaments,
        "highlights": highlights,
        "dotted": dotted,
        "slurs": slurs,
        "ties": ties,
        "holds": holds,
    }


def _remove_bar_entries(state: EditorState, index: int) -> None:
    state.overrides = {k: v for k, v in state.overrides.items() if k[0] != index}
    state.durations = {k: v for k, v in state.durations.items() if k[0] != index}
    state.annotations = {k: v for k, v in state.annotations.items() if k[0] != index}
    state.ornaments = {k: v for k, v in state.ornaments.items() if k[0] != index}
    state.highlights = {k for k in state.highlights if k[0] != index}
    state.dotted = {k for k in state.dotted if k[0] != index}
    state.slurs = [s for s in state.slurs if s[0] != index]
    state.ties = [s for s in state.ties if s[0] != index]
    state.holds = [s for s in state.holds if s[0] != index]


def _clear_bar_contents(state: EditorState, index: int) -> None:
    state.piece.bars[index] = Bar()
    _remove_bar_entries(state, index)


def _restore_bar_snapshot(state: EditorState, index: int, snapshot: BarSnapshot) -> None:
    if "bar" in snapshot:
        state.piece.bars[index] = copy.deepcopy(snapshot["bar"])
    _remove_bar_entries(state, index)
    state.overrides.update(snapshot["overrides"])
    state.durations.update(snapshot["durations"])
    state.annotations.update(snapshot["annotations"])
    state.ornaments.update(snapshot["ornaments"])
    state.highlights |= snapshot["highlights"]
    state.dotted |= snapshot["dotted"]
    state.slurs.extend(snapshot["slurs"])
    state.ties.extend(snapshot["ties"])
    state.holds.extend(snapshot["holds"])


def _insert_bar(state: EditorState, index: int) -> None:
    index = max(0, min(index, len(state.piece.bars)))
    state.piece.bars.insert(index, Bar())
    state.overrides = _shift_triplet_dict(state.overrides, index, 1)
    state.durations = _shift_triplet_dict(state.durations, index, 1)
    state.highlights = _shift_triplet_set(state.highlights, index, 1)
    state.annotations = _shift_pair_dict(state.annotations, index, 1)
    state.ornaments = _shift_pair_dict(state.ornaments, index, 1)
    state.dotted = _shift_pair_set(state.dotted, index, 1)
    state.slurs = _shift_spans(state.slurs, index, 1)
    state.ties = _shift_spans(state.ties, index, 1)
    state.holds = _shift_spans(state.holds, index, 1)
    state.stave_breaks = {b + 1 if b >= index else b for b in state.stave_breaks}
    state.modified = True


def _delete_bar(state: EditorState, index: int) -> None:
    if not state.piece.bars:
        state.piece.bars.append(Bar())
        return
    if len(state.piece.bars) == 1:
        state.piece.bars[0] = Bar()
        state.overrides.clear()
        state.durations.clear()
        state.highlights.clear()
        state.annotations.clear()
        state.ornaments.clear()
        state.dotted.clear()
        state.slurs.clear()
        state.ties.clear()
        state.holds.clear()
        state.modified = True
        return
    index = max(0, min(index, len(state.piece.bars) - 1))
    state.piece.bars.pop(index)
    state.overrides = _shift_triplet_dict(state.overrides, index + 1, -1, remove_index=index)
    state.durations = _shift_triplet_dict(state.durations, index + 1, -1, remove_index=index)
    state.highlights = _shift_triplet_set(state.highlights, index + 1, -1, remove_index=index)
    state.annotations = _shift_pair_dict(state.annotations, index + 1, -1, remove_index=index)
    state.ornaments = _shift_pair_dict(state.ornaments, index + 1, -1, remove_index=index)
    state.dotted = _shift_pair_set(state.dotted, index + 1, -1, remove_index=index)
    state.slurs = _shift_spans(state.slurs, index + 1, -1, remove_index=index)
    state.ties = _shift_spans(state.ties, index + 1, -1, remove_index=index)
    state.holds = _shift_spans(state.holds, index + 1, -1, remove_index=index)
    state.stave_breaks = {b - 1 if b > index else b for b in state.stave_breaks if b != index}
    state.modified = True


def _move_left(state: EditorState) -> None:
    if state.cursor_col > 0:
        state.cursor_col -= 1
    elif state.cursor_bar > 0:
        state.cursor_bar -= 1
        state.cursor_col = state.bar_width - 1


def _move_right(state: EditorState) -> None:
    if state.cursor_col < state.bar_width - 1:
        state.cursor_col += 1
    elif state.cursor_bar < len(state.piece.bars) - 1:
        state.cursor_bar += 1
        state.cursor_col = 0
    else:
        state.piece.bars.append(Bar())
        state.cursor_bar += 1
        state.cursor_col = 0
        state.modified = True


def _tuning_preset(value: str) -> str | None:
    presets = {
        "renaissance": "g2c3f3a3d4g4",
        "guitar": "e4a3d3f+3b2e2",
        "dminor": "a4b-4c4d4e4f4g4a3d3f3a2d2f2",
        "sharp": "c4d4e4f+4g4a3d3g3b2d2f+2",
        "flat": "c4d4e-4f4g4a3d3g3a+2d2f2",
    }
    return presets.get(value)

def _convert_overrides(state: EditorState, target_style: str) -> None:
    converted = 0
    skipped = 0
    items = list(state.overrides.items())
    for key, ch in items:
        if target_style == "italian":
            fret = french_to_fret(ch)
            out = fret_to_italian(fret) if fret is not None else None
        else:
            fret = italian_to_fret(ch)
            out = fret_to_french(fret) if fret is not None else None
        if out is None:
            skipped += 1
            continue
        _apply_override(state, key, out)
        converted += 1
    state.message = f"Converted {converted}, skipped {skipped}"

def _record_action(state: EditorState, action: UndoAction) -> None:
    state.undo_stack.append(action)
    state.redo_stack.clear()
    state.modified = True


def _record_undo(
    state: EditorState,
    kind: str,
    key: tuple[int, int, int],
    prev: object | None,
    new: object | None,
) -> None:
    _record_action(
        state,
        UndoAction(
            kind=kind,
            data={"key": key, "prev": prev, "new": new},
        ),
    )


def _apply_override(state: EditorState, key: tuple[int, int, int], ch: str) -> None:
    prev = state.overrides.get(key)
    state.overrides[key] = ch
    _record_undo(state, "override", key, prev, ch)


def _apply_duration(state: EditorState, key: tuple[int, int, int], dur: int) -> None:
    bar, _string, col = key
    prev = {k: v for k, v in state.durations.items() if k[0] == bar and k[2] == col}
    for prev_key in prev:
        state.durations.pop(prev_key, None)
    new_key = (bar, 0, col)
    state.durations[new_key] = dur
    _record_action(
        state,
        UndoAction(
            kind="duration_col",
            data={"bar": bar, "col": col, "prev": prev, "new": {new_key: dur}},
        ),
    )


def _expected_beats(state: EditorState) -> float | None:
    value = state.settings.get("time", "C")
    if value in ("C", "c"):
        return 4.0
    if value in ("O", "o"):
        return 3.0
    if "/" in value:
        parts = value.split("/", 1)
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            beats = int(parts[0])
            unit = int(parts[1])
            if beats > 0 and unit > 0:
                return beats * (4.0 / unit)
    return None


def _column_duration(state: EditorState, bar_index: int, col: int) -> float | None:
    has_note = any(
        (bar_index, s_idx, col) in state.overrides
        for s_idx in range(state.piece.strings)
    )
    has_duration = any(
        (bar_index, s_idx, col) in state.durations
        for s_idx in range(state.piece.strings)
    )
    if not (has_note or has_duration):
        return None
    found = None
    for s_idx in range(state.piece.strings):
        key = (bar_index, s_idx, col)
        if key in state.durations:
            denom = state.durations[key]
            if found is None or denom > found:
                found = denom
    if found is None:
        found = 4
    duration = 4.0 / found
    if (bar_index, col) in state.dotted:
        duration *= 1.5
    return duration


def _column_denom(state: EditorState, bar_index: int, col: int) -> int:
    found = None
    for s_idx in range(state.piece.strings):
        key = (bar_index, s_idx, col)
        if key in state.durations:
            denom = state.durations[key]
            if found is None or denom > found:
                found = denom
    return found or 4


def _column_has_duration(state: EditorState, bar_index: int, col: int) -> bool:
    return any(
        (bar_index, s_idx, col) in state.durations
        for s_idx in range(state.piece.strings)
    )


def _bar_duration_sum_by_col(state: EditorState, bar_index: int) -> float:
    if bar_index < 0 or bar_index >= len(state.piece.bars):
        return 0.0
    bar = state.piece.bars[bar_index]
    if bar.chords:
        total = 0.0
        for chord in bar.chords:
            denom = note_type_to_denom(chord.note_type) or 4
            duration = 4.0 / denom
            if chord.dotted:
                duration *= 1.5
            total += duration
        return total
    total = 0.0
    for col in range(state.bar_width):
        has_note = any(
            (bar_index, s_idx, col) in state.overrides
            for s_idx in range(state.piece.strings)
        )
        has_duration = any(
            (bar_index, s_idx, col) in state.durations
            for s_idx in range(state.piece.strings)
        )
        if not (has_note or has_duration):
            continue
        found = None
        for s_idx in range(state.piece.strings):
            key = (bar_index, s_idx, col)
            if key in state.durations:
                denom = state.durations[key]
                if found is None or denom > found:
                    found = denom
        if found is None:
            found = 4
        duration = 4.0 / found
        if (bar_index, col) in state.dotted:
            duration *= 1.5
        total += duration
    return total


def _advance_to_next_bar(state: EditorState) -> None:
    if state.cursor_bar >= len(state.piece.bars) - 1:
        state.piece.bars.append(Bar())
        state.modified = True
    state.cursor_bar = min(state.cursor_bar + 1, len(state.piece.bars) - 1)
    state.cursor_col = 0


def _advance_if_bar_full(state: EditorState) -> None:
    expected = _expected_beats(state)
    if expected is None:
        return
    total = _bar_duration_sum_by_col(state, state.cursor_bar)
    if total < expected:
        return
    _advance_to_next_bar(state)


def _advance_if_overflow(state: EditorState, denom: int) -> None:
    expected = _expected_beats(state)
    if expected is None:
        return
    bar = state.cursor_bar
    col = state.cursor_col
    if _column_duration(state, bar, col) is not None:
        return
    total = _bar_duration_sum_by_col(state, bar)
    duration = 4.0 / denom
    if (bar, col) in state.dotted:
        duration *= 1.5
    if total + duration > expected:
        _advance_to_next_bar(state)

def _apply_action(state: EditorState, action: UndoAction, *, redo: bool) -> None:  # noqa: PLR0911, PLR0912
    kind = action.kind
    data = action.data
    if kind == "override":
        key = cast(tuple[int, int, int], data["key"])
        value = cast(str | None, data["new"] if redo else data["prev"])
        if value is None:
            state.overrides.pop(key, None)
        else:
            state.overrides[key] = value
        return
    if kind == "duration":
        key = cast(tuple[int, int, int], data["key"])
        value = cast(int | None, data["new"] if redo else data["prev"])
        if value is None:
            state.durations.pop(key, None)
        else:
            state.durations[key] = value
        return
    if kind == "duration_col":
        bar = cast(int, data["bar"])
        col = cast(int, data["col"])
        payload = cast(dict[tuple[int, int, int], int], data["new"] if redo else data["prev"])
        for existing in [k for k in state.durations if k[0] == bar and k[2] == col]:
            state.durations.pop(existing, None)
        state.durations.update(payload)
        return
    if kind == "dotted":
        key = cast(tuple[int, int], data["key"])
        value = cast(bool, data["new"] if redo else data["prev"])
        if value:
            state.dotted.add(key)
        else:
            state.dotted.discard(key)
        return
    if kind in ("ornament", "annotation"):
        key = cast(tuple[int, int], data["key"])
        value = cast(str | None, data["new"] if redo else data["prev"])
        target = state.ornaments if kind == "ornament" else state.annotations
        if value is None:
            target.pop(key, None)
        else:
            target[key] = value
        return
    if kind == "annotations-all":
        value = cast(dict[tuple[int, int], str], data["new"] if redo else data["prev"])
        state.annotations = dict(value)
        return
    if kind == "highlight":
        key = cast(tuple[int, int, int], data["key"])
        value = cast(bool, data["new"] if redo else data["prev"])
        if value:
            state.highlights.add(key)
        else:
            state.highlights.discard(key)
        return
    if kind in ("slurs", "ties", "holds"):
        value = cast(list[tuple[int, int, int]] | None, data["new"] if redo else data["prev"])
        items = list(value) if value is not None else []
        if kind == "slurs":
            state.slurs = items
        elif kind == "ties":
            state.ties = items
        else:
            state.holds = items
        return
    if kind in ("barline", "repeat", "timesig"):
        bar_index = cast(int, data["bar"])
        value = cast(str | None, data["new"] if redo else data["prev"])
        if 0 <= bar_index < len(state.piece.bars):
            bar = state.piece.bars[bar_index]
            if kind == "barline":
                bar.barline = value if isinstance(value, str) else None
            elif kind == "repeat":
                bar.repeat = value if isinstance(value, str) else None
            else:
                bar.time_sig = value if isinstance(value, str) else None
                setting_value = cast(
                    str | None,
                    data.get("setting_new") if redo else data.get("setting_prev"),
                )
                if setting_value is None:
                    state.settings.pop("time", None)
                else:
                    state.settings["time"] = setting_value
        return
    if kind == "chords":
        bar_index = cast(int, data["bar"])
        value = cast(list[Chord] | None, data["new"] if redo else data["prev"])
        if 0 <= bar_index < len(state.piece.bars):
            state.piece.bars[bar_index].chords = copy.deepcopy(value) if value else []
        return
    if kind == "bar-insert":
        index = cast(int, data["index"])
        breaks = cast(set[int], data["new"] if redo else data["prev"])
        if redo:
            _insert_bar(state, index)
        else:
            _delete_bar(state, index)
        state.stave_breaks = breaks
        return
    if kind == "bar-delete":
        index = cast(int, data["index"])
        snapshot = cast(BarSnapshot | None, data["snapshot"] if not redo else None)
        breaks = cast(set[int], data["new"] if redo else data["prev"])
        if redo:
            _delete_bar(state, index)
        else:
            _insert_bar(state, index)
            if snapshot is not None:
                _restore_bar_snapshot(state, index, snapshot)
        state.stave_breaks = breaks
        return
    if kind == "bars-delete":
        start = cast(int, data["start"])
        snapshots = cast(list[BarSnapshot] | None, data["snapshots"] if not redo else None)
        breaks = cast(set[int], data["new"] if redo else data["prev"])
        if redo:
            count = cast(int, data["count"])
            for _ in range(count):
                _delete_bar(state, start)
        elif snapshots is not None:
            for offset, snapshot in enumerate(snapshots):
                _insert_bar(state, start + offset)
                _restore_bar_snapshot(state, start + offset, snapshot)
        state.stave_breaks = breaks
        return
    if kind == "bar-clear":
        index = cast(int, data["index"])
        snapshot = cast(BarSnapshot | None, data["snapshot"] if not redo else None)
        if redo:
            _clear_bar_contents(state, index)
        elif snapshot is not None:
            _restore_bar_snapshot(state, index, snapshot)
        return
    if kind == "stave-breaks":
        breaks = cast(set[int], data["new"] if redo else data["prev"])
        state.stave_breaks = breaks
        return
    if kind == "setting":
        key = data["key"]
        value = data["new"] if redo else data["prev"]
        if isinstance(key, str):
            if value is None:
                state.settings.pop(key, None)
            else:
                state.settings[key] = str(value)
            save_settings(CONFIG_PATH, state.settings)
        return


def _undo(state: EditorState) -> None:
    if not state.undo_stack:
        state.message = "Nothing to undo"
        return
    action = state.undo_stack.pop()
    _apply_action(state, action, redo=False)
    state.redo_stack.append(action)
    state.modified = True
    state.message = "Undone"


def _redo(state: EditorState) -> None:
    if not state.redo_stack:
        state.message = "Nothing to redo"
        return
    action = state.redo_stack.pop()
    _apply_action(state, action, redo=True)
    state.undo_stack.append(action)
    state.modified = True
    state.message = "Redone"

def _handle_insert(state: EditorState, key: int) -> bool:  # noqa: PLR0911, PLR0912
    if key == ord(" "):
        if 0 <= state.cursor_bar < len(state.piece.bars):
            _flatten_chords_to_grid(state, state.cursor_bar)
        _clear_cell(
            state,
            state.cursor_bar,
            _string_index(state, state.cursor_string),
            state.cursor_col,
        )
        return True
    if key == ord("|"):
        _set_barline(state, "thin")
        return True
    if key == ord("."):
        bar_col = (state.cursor_bar, state.cursor_col)
        if 0 <= state.cursor_bar < len(state.piece.bars):
            _flatten_chords_to_grid(state, state.cursor_bar)
        bar = state.cursor_bar
        if 0 <= bar < len(state.piece.bars) and state.piece.bars[bar].chords:
            bar_obj = state.piece.bars[bar]
            idx = chord_index_at_col(bar_obj, state.bar_width, state.cursor_col)
            if idx is not None:
                prev_chords = copy.deepcopy(bar_obj.chords)
                bar_obj.chords[idx].dotted = not bar_obj.chords[idx].dotted
                _record_action(
                    state,
                    UndoAction(
                        kind="chords",
                        data={"bar": bar, "prev": prev_chords, "new": bar_obj.chords},
                    ),
                )
                state.modified = True
                state.message = "Dot on" if bar_obj.chords[idx].dotted else "Dot off"
                return True
        if bar_col in state.dotted:
            _record_action(
                state,
                UndoAction(
                    kind="dotted",
                    data={"key": bar_col, "prev": True, "new": False},
                ),
            )
            state.dotted.discard(bar_col)
            state.message = "Dot off"
        else:
            _record_action(
                state,
                UndoAction(
                    kind="dotted",
                    data={"key": bar_col, "prev": False, "new": True},
                ),
            )
            state.dotted.add(bar_col)
            state.message = "Dot on"
        state.modified = True
        return True
    if key in (27, curses.KEY_EXIT):  # ESC
        state.mode = "normal"
        state.replace_once = False
        return True
    if key in (ord("q"), ord("Q")):
        return False
    if key in (ord("h"),) or (key == curses.KEY_LEFT and _allow_arrows(state)):
        _move_left(state)
        return True
    if key in (ord("l"),) or (key == curses.KEY_RIGHT and _allow_arrows(state)):
        _move_right(state)
        return True
    if key in (ord("k"),) or (key == curses.KEY_UP and _allow_arrows(state)):
        state.cursor_string -= 1
        return True
    if key in (ord("j"),) or (key == curses.KEY_DOWN and _allow_arrows(state)):
        state.cursor_string += 1
        return True

    style = state.settings.get("style", "french")
    dur = duration_value(key, style)
    if dur is not None:
        state.current_duration = dur
        _advance_if_overflow(state, dur)
        if 0 <= state.cursor_bar < len(state.piece.bars):
            _flatten_chords_to_grid(state, state.cursor_bar)
        bar = state.cursor_bar
        if 0 <= bar < len(state.piece.bars) and state.piece.bars[bar].chords:
            bar_obj = state.piece.bars[bar]
            idx = chord_index_at_col(bar_obj, state.bar_width, state.cursor_col)
            note_type = denom_to_note_type(dur)
            if idx is not None and note_type is not None:
                prev_chords = copy.deepcopy(bar_obj.chords)
                bar_obj.chords[idx].note_type = note_type
                _record_action(
                    state,
                    UndoAction(
                        kind="chords",
                        data={"bar": bar, "prev": prev_chords, "new": bar_obj.chords},
                    ),
                )
                state.modified = True
            else:
                cell = _cursor_key(state)
                _apply_duration(state, cell, dur)
        else:
            cell = _cursor_key(state)
            _apply_duration(state, cell, dur)
        state.message = f"Duration {dur}"
        return True

    if 32 <= key <= 126:
        ch = chr(key).lower()
        valid = is_french_fret(ch) if style == "french" else is_italian_fret(ch)
        if valid:
            _advance_if_overflow(state, _column_denom(state, state.cursor_bar, state.cursor_col))
            if 0 <= state.cursor_bar < len(state.piece.bars):
                _flatten_chords_to_grid(state, state.cursor_bar)
            bar = state.cursor_bar
            string = _string_index(state, state.cursor_string)
            fret = french_to_fret(ch) if style == "french" else italian_to_fret(ch)
            if 0 <= bar < len(state.piece.bars) and state.piece.bars[bar].chords:
                if fret is not None:
                    prev_chords = copy.deepcopy(state.piece.bars[bar].chords)
                    if state.current_duration:
                        idx = chord_index_at_col(
                            state.piece.bars[bar], state.bar_width, state.cursor_col
                        )
                        note_type = denom_to_note_type(state.current_duration)
                        if idx is not None and note_type is not None:
                            state.piece.bars[bar].chords[idx].note_type = note_type
                    if _set_chord_note(
                        state.piece.bars[bar],
                        state.bar_width,
                        state.cursor_col,
                        string + 1,
                        fret,
                    ):
                        new_chords = copy.deepcopy(state.piece.bars[bar].chords)
                        _record_action(
                            state,
                            UndoAction(
                                kind="chords",
                                data={"bar": bar, "prev": prev_chords, "new": new_chords},
                            ),
                        )
                        state.modified = True
                    else:
                        cell = _cursor_key(state)
                        _apply_override(state, cell, ch)
                else:
                    cell = _cursor_key(state)
                    _apply_override(state, cell, ch)
            else:
                cell = _cursor_key(state)
                _apply_override(state, cell, ch)
            if not _column_has_duration(state, bar, state.cursor_col):
                cell = _cursor_key(state)
                _apply_duration(state, cell, state.current_duration)
            if state.replace_once:
                state.replace_once = False
                state.mode = "normal"
            else:
                steps = 2 if state.settings.get("grid") == "on" else 1
                for _ in range(steps):
                    _move_right(state)
        else:
            state.message = "Invalid fret for current style"
    return True


def _status_line(state: EditorState) -> str:
    name = state.path.split("/")[-1] if state.path else "[No file]"
    mod = "*" if state.modified else ""
    bar = state.cursor_bar + 1
    string = state.cursor_string + 1
    beat_text = f"col:{state.cursor_col + 1}"
    parsed = _parse_time_sig_value(state.settings.get("time", "C"))
    if parsed is not None and state.bar_width > 0:
        beats, _unit = parsed
        beat_index = min(
            beats,
            max(1, int(state.cursor_col * beats / state.bar_width) + 1),
        )
        beat_text = f"beat:{beat_index}/{beats}"
    style = state.settings.get("style", "french")
    flagstyle = state.settings.get("flagstyle", "standard")
    return (
        f"{name}{mod}  bar:{bar} str:{string} {beat_text}  "
        f"dur:{state.current_duration}  style:{style} flag:{flagstyle}"
    )


def _cmd_open(state: EditorState, args: str) -> None:
    path = args.strip()
    if not path:
        state.message = "No path"
        return
    overrides: dict[tuple[int, int, int], str] = {}
    durations: dict[tuple[int, int, int], int] = {}
    dotted: set[tuple[int, int]] = set()
    bar_width: int | None = None
    if path.lower().endswith(".tab"):
        parsed = load_tab_data(path)
        if parsed is not None:
            state.piece = parsed.piece
            overrides = parsed.overrides
            durations = parsed.durations
            dotted = parsed.dotted
            bar_width = parsed.bar_width
        else:
            state.piece = load_tab(path)
    else:
        state.piece = load_ft3(path)
    state.path = path
    state.overrides = overrides
    state.durations = durations
    state.dotted = dotted
    if bar_width:
        state.bar_width = max(4, bar_width)
    state.cursor_bar = 0
    state.cursor_string = 0
    state.cursor_col = 0
    state.bar_offset = 0
    state.mode = "normal"
    if not state.durations:
        state.durations = build_durations(state.piece)
    state.message = f"Opened {path}"


def _cmd_set(state: EditorState, args: str) -> None:
    _apply_set_command(state, args.strip())


def _cmd_convert(state: EditorState, args: str) -> None:
    target = args.strip()
    if target not in ("french", "italian"):
        state.message = "Convert target must be french or italian"
        return
    _convert_overrides(state, target)
    state.settings["style"] = target
    save_settings(CONFIG_PATH, state.settings)


def _cmd_ascii(state: EditorState, args: str) -> None:
    value = args.strip()
    if value not in ("on", "off"):
        state.message = "Ascii must be on/off"
        return
    state.ascii_preview = value == "on"
    state.message = f"Ascii preview {value}"


def _cmd_midi(state: EditorState, args: str) -> None:
    path = args.strip() or "out.mid"
    try:
        bpm = int(state.settings.get("tempo", "90") or "90")
    except ValueError:
        bpm = 90
    state.message = export_midi(
        path,
        state.piece,
        state.overrides,
        state.durations,
        state.bar_width,
        settings=state.settings,
        bpm=bpm,
        dotted=state.dotted,
    )


def _cmd_lilypond(state: EditorState, args: str) -> None:
    path = args.strip() or "out.ly"
    state.message = export_lilypond(
        path,
        state.piece,
        state.overrides,
        state.durations,
        state.bar_width,
        settings=state.settings,
        ornaments=state.ornaments,
        annotations=state.annotations,
        slurs=state.slurs,
        ties=state.ties,
        holds=state.holds,
    )


def _cmd_pdf(state: EditorState, _args: str) -> None:
    _print_pdf(state)


def _cmd_play(state: EditorState, args: str) -> None:
    tokens = [token for token in args.strip().split() if token]
    start_bar = None
    bpm = None
    path = ""
    for token in tokens:
        if token.isdigit() and start_bar is None:
            start_bar = max(0, int(token) - 1)
            continue
        if token.isdigit() and bpm is None:
            bpm = int(token)
            continue
        if token.startswith("tempo=") and token.split("=", 1)[1].isdigit():
            bpm = int(token.split("=", 1)[1])
            continue
        path = token
    if not path:
        path = _midi_output_path(state)
    _start_midi(state, start_bar=start_bar, path=path, bpm=bpm)


def _cmd_orn(state: EditorState, args: str) -> None:
    _set_ornament(state, args.strip())


def _cmd_annot(state: EditorState, args: str) -> None:
    _set_annotation(state, args.strip())


def _cmd_highlight(state: EditorState, args: str) -> None:
    _set_highlight(state, args.strip())


def _cmd_chord(state: EditorState, args: str) -> None:
    action = args.strip() or "add"
    if not state.piece.bars:
        state.message = "No bars"
        return
    bar = state.piece.bars[state.cursor_bar]
    if action in ("add", "insert"):
        prev = copy.deepcopy(bar.chords)
        _insert_chord(bar, state.bar_width, state.cursor_col)
        _record_action(
            state,
            UndoAction(
                kind="chords",
                data={"bar": state.cursor_bar, "prev": prev, "new": bar.chords},
            ),
        )
        state.modified = True
        state.message = "Chord added"
        return
    if action in ("del", "delete", "remove"):
        prev = copy.deepcopy(bar.chords)
        if _delete_chord(bar, state.bar_width, state.cursor_col):
            _record_action(
                state,
                UndoAction(
                    kind="chords",
                    data={"bar": state.cursor_bar, "prev": prev, "new": bar.chords},
                ),
            )
            state.modified = True
            state.message = "Chord deleted"
        else:
            state.message = "No chord at cursor"
        return
    state.message = "Chord action: add/del"


def _cmd_midicmd(state: EditorState, args: str) -> None:
    target = args.strip() or _midi_output_path(state)
    soundfont = state.settings.get("soundfont", "") or None
    cmd = _midi_command(
        path=target,
        soundfont=soundfont,
        platform=sys.platform,
        fluidsynth=shutil.which("fluidsynth"),
        timidity=shutil.which("timidity"),
        opener=shutil.which("open") if sys.platform == "darwin" else None,
    )
    if cmd is None:
        state.message = "No MIDI player found"
        return
    state.message = " ".join(cmd)


def _cmd_source(state: EditorState, args: str) -> None:
    target = args.strip() or state.path
    if not target:
        state.message = "No source path"
        return
    viewer = shutil.which("less")
    if not viewer:
        state.message = "less not found"
        return
    curses.endwin()
    try:
        subprocess.run([viewer, target], check=False)  # noqa: S603
    except OSError as exc:
        state.message = f"Failed to open source: {exc}"
        return
    curses.curs_set(0)
    state.message = f"Viewed {target}"


def _cmd_bar(state: EditorState, args: str) -> None:
    action = args.strip() or "add"
    if action in ("add", "after"):
        prev_breaks = set(state.stave_breaks)
        _insert_bar(state, state.cursor_bar + 1)
        new_breaks = set(state.stave_breaks)
        _record_action(
            state,
            UndoAction(
                kind="bar-insert",
                data={"index": state.cursor_bar + 1, "prev": prev_breaks, "new": new_breaks},
            ),
        )
        state.cursor_bar = min(state.cursor_bar + 1, len(state.piece.bars) - 1)
        state.cursor_col = 0
        state.message = "Bar added"
        return
    if action in ("before", "insert"):
        prev_breaks = set(state.stave_breaks)
        _insert_bar(state, state.cursor_bar)
        new_breaks = set(state.stave_breaks)
        _record_action(
            state,
            UndoAction(
                kind="bar-insert",
                data={"index": state.cursor_bar, "prev": prev_breaks, "new": new_breaks},
            ),
        )
        state.cursor_col = 0
        state.message = "Bar inserted"
        return
    if action in ("del", "delete", "remove"):
        if not state.piece.bars:
            state.message = "No bars"
            return
        index = state.cursor_bar
        if len(state.piece.bars) == 1:
            snapshot = _snapshot_bar(state, index)
            _clear_bar_contents(state, index)
            _record_action(
                state,
                UndoAction(
                    kind="bar-clear",
                    data={"index": index, "snapshot": snapshot},
                ),
            )
        else:
            snapshot = _snapshot_bar(state, index)
            prev_breaks = set(state.stave_breaks)
            _delete_bar(state, state.cursor_bar)
            new_breaks = set(state.stave_breaks)
            _record_action(
                state,
                UndoAction(
                    kind="bar-delete",
                    data={
                        "index": index,
                        "snapshot": snapshot,
                        "prev": prev_breaks,
                        "new": new_breaks,
                    },
                ),
            )
        state.cursor_bar = min(state.cursor_bar, len(state.piece.bars) - 1)
        state.cursor_col = 0
        state.message = "Bar deleted"
        return
    state.message = "Bar action: add/after/before/insert/del"


def _cmd_stave(state: EditorState, args: str) -> None:
    action = args.strip() or "break"
    bars_per_line = _bars_per_line(state, state.screen_width or 80)
    start, end = _system_range(state, state.cursor_bar, bars_per_line)
    if action in ("break", "split"):
        idx = state.cursor_bar + 1
        if idx < len(state.piece.bars):
            prev = set(state.stave_breaks)
            state.stave_breaks.add(idx)
            _record_action(
                state,
                UndoAction(
                    kind="stave-breaks",
                    data={"prev": prev, "new": set(state.stave_breaks)},
                ),
            )
            state.message = "Stave break added"
        else:
            state.message = "No bar to break after"
        return
    if action in ("join", "merge"):
        idx = state.cursor_bar + 1
        if idx in state.stave_breaks:
            prev = set(state.stave_breaks)
            state.stave_breaks.discard(idx)
            _record_action(
                state,
                UndoAction(
                    kind="stave-breaks",
                    data={"prev": prev, "new": set(state.stave_breaks)},
                ),
            )
            state.message = "Stave break removed"
        else:
            state.message = "No break at cursor"
        return
    if action in ("new", "insert"):
        idx = state.cursor_bar + 1
        prev_breaks = set(state.stave_breaks)
        _insert_bar(state, idx)
        state.stave_breaks.add(idx)
        _record_action(
            state,
            UndoAction(
                kind="bar-insert",
                data={"index": idx, "prev": prev_breaks, "new": set(state.stave_breaks)},
            ),
        )
        state.message = "Stave inserted"
        return
    if action in ("del", "delete", "remove"):
        if start >= end:
            state.message = "No stave to delete"
            return
        snapshots = [_snapshot_bar(state, idx) for idx in range(start, end)]
        prev_breaks = set(state.stave_breaks)
        for _ in range(end - start):
            _delete_bar(state, start)
        state.stave_breaks = {
            b - (end - start) if b >= end else b
            for b in state.stave_breaks
            if b < start or b >= end
        }
        _record_action(
            state,
            UndoAction(
                kind="bars-delete",
                data={
                    "start": start,
                    "count": end - start,
                    "snapshots": snapshots,
                    "prev": prev_breaks,
                    "new": set(state.stave_breaks),
                },
            ),
        )
        state.cursor_bar = max(0, min(start, len(state.piece.bars) - 1))
        state.cursor_col = 0
        state.message = "Stave deleted"
        return
    state.message = "Stave action: break/join/new/del"


def _cmd_slur(state: EditorState, args: str) -> None:
    _set_slur(state, args.strip())


def _cmd_tie(state: EditorState, args: str) -> None:
    _set_tie(state, args.strip())


def _cmd_hold(state: EditorState, args: str) -> None:
    _set_hold(state, args.strip())


def _cmd_barline(state: EditorState, args: str) -> None:
    value = args.strip()
    if value not in ("thin", "thick", "double", "hidden", "pale"):
        state.message = "Barline must be thin/thick/double/hidden/pale"
        return
    _set_barline(state, value)


def _cmd_repeat(state: EditorState, args: str) -> None:
    value = args.strip()
    if value not in ("none", "start", "end", "dots"):
        state.message = "Repeat must be none/start/end/dots"
        return
    _set_repeat(state, value)


def _parse_time_sig_value(text: str) -> tuple[int, int] | None:
    value = text.strip()
    if value in ("C", "c"):
        return 4, 4
    if value in ("O", "o"):
        return 3, 4
    if "/" in value:
        parts = value.split("/", 1)
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            beats = int(parts[0])
            unit = int(parts[1])
            if beats > 0 and unit > 0:
                return beats, unit
    return None


def _cmd_time(state: EditorState, args: str) -> None:
    parsed = _parse_time_sig_value(args)
    if parsed is None:
        state.message = "Invalid time signature"
        return
    beats, unit = parsed
    value = f"{beats}/{unit}"
    prev_setting = state.settings.get("time")
    prev_bar = None
    state.settings["time"] = value
    if state.piece.bars:
        prev_bar = state.piece.bars[state.cursor_bar].time_sig
        state.piece.bars[state.cursor_bar].time_sig = value
    _record_action(
        state,
        UndoAction(
            kind="timesig",
            data={
                "bar": state.cursor_bar,
                "prev": prev_bar,
                "new": value,
                "setting_prev": prev_setting,
                "setting_new": value,
            },
        ),
    )
    state.modified = True
    state.message = f"Time {value}"


def _bar_duration_sum(
    state: EditorState,
    bar_index: int,
    default_duration: int,
) -> float:
    if bar_index < 0 or bar_index >= len(state.piece.bars):
        return 0.0
    bar = state.piece.bars[bar_index]
    total = 0.0
    if bar.chords:
        for chord in bar.chords:
            denom = note_type_to_denom(chord.note_type) or default_duration
            duration = 4.0 / denom
            if chord.dotted:
                duration *= 1.5
            total += duration
        return total
    last = None
    for col in range(state.bar_width):
        found = None
        for s_idx in range(state.piece.strings):
            key = (bar_index, s_idx, col)
            if key in state.durations:
                denom = state.durations[key]
                if found is None or denom > found:
                    found = denom
        if found is None:
            found = default_duration
        if found != last:
            duration = 4.0 / found
            if (bar_index, col) in state.dotted:
                duration *= 1.5
            total += duration
            last = found
    return total


def _cmd_verify(state: EditorState, _args: str) -> None:
    parsed = _parse_time_sig_value(state.settings.get("time", "C"))
    if parsed is None:
        state.message = "No valid time signature"
        return
    beats, unit = parsed
    expected = beats * (4.0 / unit)
    total = _bar_duration_sum(state, state.cursor_bar, default_duration=4)
    delta = total - expected
    if abs(delta) < 0.01:
        state.message = "Measure ok"
        return
    if delta > 0:
        state.message = f"Overfull by {delta:.2f} beats"
    else:
        state.message = f"Underfull by {abs(delta):.2f} beats"


_cmd_title = cmd_title
_cmd_author = cmd_author
_cmd_composer = cmd_composer
_cmd_subtitle = cmd_subtitle
_cmd_footnote = cmd_footnote
_cmd_header = cmd_header_template


def _cmd_undo(state: EditorState, _args: str) -> None:
    _undo(state)


def _cmd_redo(state: EditorState, _args: str) -> None:
    _redo(state)


def _cmd_write(state: EditorState, args: str) -> None:
    path = args.strip()
    if not path and state.path:
        path = state.path if state.path.endswith(".tab") else state.path + ".tab"
    if not path:
        state.message = "No path for write"
        return
    export_tab_to_file(
        path,
        state.piece,
        state.overrides,
        state.durations,
        state.bar_width,
        settings=state.settings,
        ornaments=state.ornaments,
        annotations=state.annotations,
        slurs=state.slurs,
        ties=state.ties,
        holds=state.holds,
    )
    state.modified = False
    state.message = f"Wrote {path}"


def _cmd_write_ascii(state: EditorState, args: str) -> None:
    path = args.strip()
    if not path and state.path:
        path = state.path if state.path.endswith(".txt") else state.path + ".txt"
    if not path:
        state.message = "No path for wa"
        return
    content = export_ascii(
        state.piece,
        state.overrides,
        state.durations,
        state.bar_width,
        settings=state.settings,
        ornaments=state.ornaments,
        annotations=state.annotations,
        slurs=state.slurs,
        ties=state.ties,
        holds=state.holds,
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    state.modified = False
    state.message = f"Wrote {path}"


def _apply_command(state: EditorState, cmdline: str) -> None:
    command_mod.apply_command(state, cmdline, CONFIG_PATH)


def _apply_set_command(state: EditorState, args: str) -> None:
    command_mod.apply_set_command(state, args, CONFIG_PATH)


def _set_ornament(state: EditorState, value: str) -> None:
    key = (state.cursor_bar, state.cursor_col)
    prev = state.ornaments.get(key)
    if value == "clear":
        _record_action(
            state,
            UndoAction(
                kind="ornament",
                data={"key": key, "prev": prev, "new": None},
            ),
        )
        state.ornaments.pop(key, None)
        state.modified = True
        state.message = "Ornament cleared"
        return
    if len(value) != 1:
        state.message = "Ornament must be 1 char or clear"
        return
    _record_action(
        state,
        UndoAction(
            kind="ornament",
            data={"key": key, "prev": prev, "new": value},
        ),
    )
    state.ornaments[key] = value
    state.modified = True
    state.message = f"Ornament {value}"


def _set_annotation(state: EditorState, value: str) -> None:
    key = (state.cursor_bar, state.cursor_col)
    prev = state.annotations.get(key)
    if value == "clear":
        _record_action(
            state,
            UndoAction(
                kind="annotation",
                data={"key": key, "prev": prev, "new": None},
            ),
        )
        state.annotations.pop(key, None)
        state.modified = True
        state.message = "Annotation cleared"
        return
    new_value = value[:8]
    _record_action(
        state,
        UndoAction(
            kind="annotation",
            data={"key": key, "prev": prev, "new": new_value},
        ),
    )
    state.annotations[key] = new_value
    state.modified = True
    state.message = "Annotation set"


def _set_highlight(state: EditorState, value: str) -> None:
    key = _cursor_key(state)
    prev = key in state.highlights
    if value == "on":
        _record_action(
            state,
            UndoAction(
                kind="highlight",
                data={"key": key, "prev": prev, "new": True},
            ),
        )
        state.highlights.add(key)
        state.modified = True
        state.message = "Highlight on"
        return
    if value == "off":
        _record_action(
            state,
            UndoAction(
                kind="highlight",
                data={"key": key, "prev": prev, "new": False},
            ),
        )
        state.highlights.discard(key)
        state.modified = True
        state.message = "Highlight off"
        return
    state.message = "Highlight must be on/off"


def _set_slur(state: EditorState, value: str) -> None:
    pos = (state.cursor_bar, state.cursor_col)
    if value == "start":
        state._slur_start = pos
        state.message = "Slur start"
        return
    if value == "end":
        if state._slur_start and state._slur_start[0] == pos[0]:
            start_col = state._slur_start[1]
            end_col = pos[1]
            if start_col > end_col:
                start_col, end_col = end_col, start_col
            prev = list(state.slurs)
            state.slurs.append((pos[0], start_col, end_col))
            _record_action(
                state,
                UndoAction(
                    kind="slurs",
                    data={"prev": prev, "new": list(state.slurs)},
                ),
            )
            state._slur_start = None
            state.modified = True
            state.message = "Slur set"
            return
        state.message = "Slur start not set"
        return
    if value == "clear":
        prev = list(state.slurs)
        state.slurs = [s for s in state.slurs if s[0] != state.cursor_bar]
        _record_action(
            state,
            UndoAction(
                kind="slurs",
                data={"prev": prev, "new": list(state.slurs)},
            ),
        )
        state.modified = True
        state.message = "Slur cleared"
        return
    state.message = "Slur must be start/end/clear"


def _set_tie(state: EditorState, value: str) -> None:
    pos = (state.cursor_bar, state.cursor_col)
    if value == "start":
        state._tie_start = pos
        state.message = "Tie start"
        return
    if value == "end":
        if state._tie_start and state._tie_start[0] == pos[0]:
            start_col = state._tie_start[1]
            end_col = pos[1]
            if start_col > end_col:
                start_col, end_col = end_col, start_col
            prev = list(state.ties)
            state.ties.append((pos[0], start_col, end_col))
            _record_action(
                state,
                UndoAction(
                    kind="ties",
                    data={"prev": prev, "new": list(state.ties)},
                ),
            )
            state._tie_start = None
            state.modified = True
            state.message = "Tie set"
            return
        state.message = "Tie start not set"
        return
    if value == "clear":
        prev = list(state.ties)
        state.ties = [s for s in state.ties if s[0] != state.cursor_bar]
        _record_action(
            state,
            UndoAction(
                kind="ties",
                data={"prev": prev, "new": list(state.ties)},
            ),
        )
        state.modified = True
        state.message = "Tie cleared"
        return
    state.message = "Tie must be start/end/clear"


def _set_hold(state: EditorState, value: str) -> None:
    pos = (state.cursor_bar, state.cursor_col)
    if value == "start":
        state._hold_start = pos
        state.message = "Hold start"
        return
    if value == "end":
        if state._hold_start and state._hold_start[0] == pos[0]:
            start_col = state._hold_start[1]
            end_col = pos[1]
            if start_col > end_col:
                start_col, end_col = end_col, start_col
            prev = list(state.holds)
            state.holds.append((pos[0], start_col, end_col))
            _record_action(
                state,
                UndoAction(
                    kind="holds",
                    data={"prev": prev, "new": list(state.holds)},
                ),
            )
            state._hold_start = None
            state.modified = True
            state.message = "Hold set"
            return
        state.message = "Hold start not set"
        return
    if value == "clear":
        prev = list(state.holds)
        state.holds = [s for s in state.holds if s[0] != state.cursor_bar]
        _record_action(
            state,
            UndoAction(
                kind="holds",
                data={"prev": prev, "new": list(state.holds)},
            ),
        )
        state.modified = True
        state.message = "Hold cleared"
        return
    state.message = "Hold must be start/end/clear"


def _set_barline(state: EditorState, value: str) -> None:
    if not state.piece.bars:
        state.message = "No bars"
        return
    bar = state.piece.bars[state.cursor_bar]
    prev = bar.barline
    mapping = {
        "thin": "|",
        "thick": "||",
        "double": "||",
        "hidden": " ",
        "pale": ":",
    }
    new = mapping.get(value, "|")
    _record_action(
        state,
        UndoAction(
            kind="barline",
            data={"bar": state.cursor_bar, "prev": prev, "new": new},
        ),
    )
    bar.barline = new
    state.modified = True
    state.message = f"Barline {value}"


def _set_repeat(state: EditorState, value: str) -> None:
    if not state.piece.bars:
        state.message = "No bars"
        return
    bar = state.piece.bars[state.cursor_bar]
    prev = bar.repeat
    mapping = {
        "none": "",
        "start": ".:",
        "end": ":.",
        "dots": ".",
    }
    new = mapping.get(value, "")
    _record_action(
        state,
        UndoAction(
            kind="repeat",
            data={"bar": state.cursor_bar, "prev": prev, "new": new},
        ),
    )
    bar.repeat = new
    state.modified = True
    state.message = f"Repeat {value}"


def _handle_normal(state: EditorState, key: int) -> bool:  # noqa: PLR0911, PLR0912
    if ord("0") <= key <= ord("9"):
        digit = chr(key)
        if digit == "0" and not state.count_prefix:
            state.cursor_col = 0
            return True
        state.count_prefix += digit
        return True
    if state.pending_key:
        if state.pending_key == "g" and key == ord("g"):
            state.cursor_bar = 0
            state.cursor_col = 0
            state.pending_key = ""
            return True
        if state.pending_key == "d" and key == ord("d"):
            _yank_bar(state, state.cursor_bar)
            _delete_bar(state, state.cursor_bar)
            state.cursor_bar = min(state.cursor_bar, len(state.piece.bars) - 1)
            state.cursor_col = 0
            state.message = "Bar deleted"
            state.pending_key = ""
            return True
        if state.pending_key == "y" and key == ord("y"):
            _yank_bar(state, state.cursor_bar)
            state.message = "Bar yanked"
            state.pending_key = ""
            return True
        state.pending_key = ""
    if key in (ord("q"), ord("Q")):
        _stop_midi(state)
        return False
    if key == ord(":"):
        state.mode = "command"
        state.cmdline = ""
        return True
    if key == ord("?"):
        state.mode = "help"
        state.help_offset = 0
        state.count_prefix = ""
        state.pending_key = ""
        return True
    if key == curses.KEY_F1 and _is_casual(state):
        state.mode = "help"
        state.help_offset = 0
        state.count_prefix = ""
        state.pending_key = ""
        return True
    if key == ord("P"):
        _print_pdf(state)
        state.count_prefix = ""
        state.pending_key = ""
        return True
    if key in (ord("m"), ord("M")):
        if state.midi_proc is not None and state.midi_proc.poll() is None:
            _stop_midi(state)
        else:
            _start_midi(state)
        state.count_prefix = ""
        state.pending_key = ""
        return True
    if key == ord("/"):
        state.mode = "search"
        state.searchline = ""
        state.count_prefix = ""
        state.pending_key = ""
        return True
    if key in (ord("i"), curses.KEY_ENTER, 10, 13):
        state.mode = "insert"
        state.count_prefix = ""
        state.pending_key = ""
        return True
    if key == ord("r"):
        state.mode = "insert"
        state.replace_once = True
        state.count_prefix = ""
        state.pending_key = ""
        return True
    if key in (ord("o"), ord("+")):
        _cmd_bar(state, "after")
        state.count_prefix = ""
        state.pending_key = ""
        return True
    if key == ord("O"):
        _cmd_bar(state, "before")
        state.count_prefix = ""
        state.pending_key = ""
        return True
    if key in (ord("X"), ord("-")):
        _cmd_bar(state, "del")
        state.count_prefix = ""
        state.pending_key = ""
        return True
    if key == curses.KEY_IC and _is_casual(state):
        _cmd_bar(state, "after")
        state.count_prefix = ""
        state.pending_key = ""
        return True
    if key == curses.KEY_DC and _is_casual(state):
        _cmd_bar(state, "del")
        state.count_prefix = ""
        state.pending_key = ""
        return True
    if key == ord("u"):
        _undo(state)
        state.count_prefix = ""
        state.pending_key = ""
        return True
    if key == 18:  # Ctrl-R
        _redo(state)
        state.count_prefix = ""
        state.pending_key = ""
        return True
    if key == ord("^"):
        state.cursor_col = _row_first_note_col(state)
        state.count_prefix = ""
        state.pending_key = ""
        return True
    if key == ord("x"):
        count = _consume_count(state)
        for _ in range(count):
            _clear_cell(
                state,
                state.cursor_bar,
                _string_index(state, state.cursor_string),
                state.cursor_col,
            )
            if count > 1:
                _move_right(state)
        state.pending_key = ""
        return True
    if key == ord("f"):
        cycle = ["standard", "thin", "italian", "board", "capirola"]
        current = state.settings.get("flagstyle", "standard")
        if current not in cycle:
            current = "standard"
        next_value = cycle[(cycle.index(current) + 1) % len(cycle)]
        state.settings["flagstyle"] = next_value
        save_settings(CONFIG_PATH, state.settings)
        state.message = f"Flagstyle {next_value}"
        state.count_prefix = ""
        state.pending_key = ""
        return True
    if key == ord("F"):
        if state.settings.get("style", "french") == "french":
            current = state.settings.get("frenchc", "normal")
            next_value = "alt" if current == "normal" else "normal"
            state.settings["frenchc"] = next_value
            save_settings(CONFIG_PATH, state.settings)
            state.message = f"French c {next_value}"
        else:
            state.message = "French letters only"
        state.count_prefix = ""
        state.pending_key = ""
        return True
    if key == ord("E"):
        if state.settings.get("style", "french") == "french":
            current = state.settings.get("frenche", "normal")
            next_value = "tail" if current == "normal" else "normal"
            state.settings["frenche"] = next_value
            save_settings(CONFIG_PATH, state.settings)
            state.message = f"French e {next_value}"
        else:
            state.message = "French letters only"
        state.count_prefix = ""
        state.pending_key = ""
        return True
    if key == ord("p"):
        _paste_bar(state, state.cursor_bar + 1)
        state.pending_key = ""
        return True
    if key == ord("]"):
        bar = state.piece.bars[state.cursor_bar]
        prev = copy.deepcopy(bar.chords)
        _insert_chord(bar, state.bar_width, state.cursor_col)
        _record_action(
            state,
            UndoAction(
                kind="chords",
                data={"bar": state.cursor_bar, "prev": prev, "new": bar.chords},
            ),
        )
        state.modified = True
        return True
    if key == ord("["):
        bar = state.piece.bars[state.cursor_bar]
        prev = copy.deepcopy(bar.chords)
        if _delete_chord(bar, state.bar_width, state.cursor_col):
            _record_action(
                state,
                UndoAction(
                    kind="chords",
                    data={"bar": state.cursor_bar, "prev": prev, "new": bar.chords},
                ),
            )
            state.modified = True
        return True
    if key in (ord("g"), ord("d"), ord("y")):
        state.pending_key = chr(key)
        return True
    if _is_casual(state):
        count = _consume_count(state)
        if key in (ord("a"),) or (key == curses.KEY_LEFT and _allow_arrows(state)):
            for _ in range(count):
                _move_left(state)
            return True
        if key in (ord("d"),) or (key == curses.KEY_RIGHT and _allow_arrows(state)):
            for _ in range(count):
                _move_right(state)
            return True
        if key in (ord("w"),) or (key == curses.KEY_UP and _allow_arrows(state)):
            state.cursor_string -= count
            return True
        if key in (ord("s"),) or (key == curses.KEY_DOWN and _allow_arrows(state)):
            state.cursor_string += count
            return True
        if key in (ord("."),):
            state.cursor_bar = min(len(state.piece.bars) - 1, state.cursor_bar + count)
            state.cursor_col = 0
            return True
        if key in (ord(","),):
            state.cursor_bar = max(0, state.cursor_bar - count)
            state.cursor_col = 0
            return True
        if key in (curses.KEY_PPAGE,):
            bars_per_line = _bars_per_line(state, state.screen_width)
            state.cursor_bar = max(0, state.cursor_bar - bars_per_line * count)
            state.cursor_col = 0
            return True
        if key in (curses.KEY_NPAGE,):
            bars_per_line = _bars_per_line(state, state.screen_width)
            state.cursor_bar = min(
                len(state.piece.bars) - 1,
                state.cursor_bar + bars_per_line * count,
            )
            state.cursor_col = 0
            return True
        if key in (curses.KEY_HOME,):
            state.cursor_col = 0
            return True
        if key in (curses.KEY_END,):
            state.cursor_col = state.bar_width - 1
            return True
    count = _consume_count(state)
    if key in (ord("h"),) or (key == curses.KEY_LEFT and _allow_arrows(state)):
        for _ in range(count):
            _move_left(state)
    elif key in (ord("l"),) or (key == curses.KEY_RIGHT and _allow_arrows(state)):
        for _ in range(count):
            _move_right(state)
    elif key in (ord("k"),) or (key == curses.KEY_UP and _allow_arrows(state)):
        state.cursor_string -= count
    elif key in (ord("j"),) or (key == curses.KEY_DOWN and _allow_arrows(state)):
        state.cursor_string += count
    elif key == ord("K"):
        bars_per_line = _bars_per_line(state, state.screen_width)
        state.cursor_bar = max(0, state.cursor_bar - bars_per_line * count)
        state.cursor_col = 0
    elif key == ord("J"):
        bars_per_line = _bars_per_line(state, state.screen_width)
        state.cursor_bar = min(len(state.piece.bars) - 1, state.cursor_bar + bars_per_line * count)
        state.cursor_col = 0
    elif key == ord("w"):
        state.cursor_bar = min(len(state.piece.bars) - 1, state.cursor_bar + count)
        state.cursor_col = 0
    elif key == ord("b"):
        state.cursor_bar = max(0, state.cursor_bar - count)
        state.cursor_col = 0
    elif key == ord("e"):
        state.cursor_col = state.bar_width - 1
    elif key == ord("{"):
        bars_per_line = _bars_per_line(state, state.screen_width)
        state.cursor_bar = max(0, state.cursor_bar - bars_per_line * count)
        state.cursor_col = 0
    elif key == ord("}"):
        bars_per_line = _bars_per_line(state, state.screen_width)
        state.cursor_bar = min(len(state.piece.bars) - 1, state.cursor_bar + bars_per_line * count)
        state.cursor_col = 0
    elif key == ord("g"):
        state.cursor_bar = 0
        state.cursor_col = 0
    elif key == ord("G"):
        state.cursor_bar = max(0, len(state.piece.bars) - 1)
        state.cursor_col = 0
    elif key == ord("$"):
        state.cursor_col = state.bar_width - 1
    return True


def _midi_output_path(state: EditorState) -> str:
    base = "out"
    if state.path:
        base = str(Path(state.path).with_suffix(""))
    return base + ".mid"


def _print_pdf(state: EditorState) -> None:
    base = "out"
    if state.path:
        base = str(Path(state.path).with_suffix(""))
    ly_path = base + ".ly"
    state.message = export_lilypond(
        ly_path,
        state.piece,
        state.overrides,
        state.durations,
        state.bar_width,
        settings=state.settings,
        ornaments=state.ornaments,
        annotations=state.annotations,
        slurs=state.slurs,
        ties=state.ties,
        holds=state.holds,
    )
    state.message = print_lilypond_pdf(ly_path, output_base=base)


def _stop_midi(state: EditorState) -> None:
    if state.midi_proc is None:
        return
    proc = state.midi_proc
    state.midi_proc = None
    if proc.poll() is None:
        proc.terminate()
    state.message = "MIDI stopped"


def _start_midi(
    state: EditorState,
    start_bar: int | None = None,
    path: str | None = None,
    bpm: int | None = None,
) -> None:
    if state.midi_proc is not None and state.midi_proc.poll() is None:
        _stop_midi(state)
    path = path or _midi_output_path(state)
    start_bar = state.cursor_bar if start_bar is None else start_bar
    if bpm is None:
        try:
            bpm = int(state.settings.get("tempo", "90") or "90")
        except ValueError:
            bpm = 90
    state.message = export_midi(
        path,
        state.piece,
        state.overrides,
        state.durations,
        state.bar_width,
        settings=state.settings,
        bpm=bpm,
        start_bar=start_bar,
        dotted=state.dotted,
    )
    soundfont = state.settings.get("soundfont", "") or None
    state.message, state.midi_proc = play_midi(path, soundfont=soundfont)


def _handle_key(state: EditorState, key: int) -> bool:  # noqa: PLR0911
    if state.mode == "insert":
        return _handle_insert(state, key)
    if state.mode == "command":
        return handle_command_input(state, key, _apply_command)
    if state.mode == "search":
        return handle_search_input(state, key)
    if state.mode == "help":
        if key in (ord("q"), ord("Q"), 27):
            state.mode = "normal"
            return True
        if key in (ord("j"), curses.KEY_DOWN):
            state.help_offset += 1
            return True
        if key in (ord("k"), curses.KEY_UP):
            state.help_offset = max(0, state.help_offset - 1)
            return True
        return True
    return _handle_normal(state, key)


def _load_piece_data(path: str | None) -> LoadResult:
    overrides: dict[tuple[int, int, int], str] = {}
    durations: dict[tuple[int, int, int], int] = {}
    dotted: set[tuple[int, int]] = set()
    bar_width: int | None = None
    if path and not Path(path).exists():
        title = Path(path).stem if path else "Untitled"
        piece = Piece(title=title, bars=[])
        return piece, overrides, durations, dotted, bar_width
    if path:
        if path.lower().endswith(".tab"):
            parsed = load_tab_data(path)
            if parsed is not None:
                overrides = parsed.overrides
                durations = parsed.durations
                dotted = parsed.dotted
                bar_width = parsed.bar_width
                return parsed.piece, overrides, durations, dotted, bar_width
            return load_tab(path), overrides, durations, dotted, bar_width
        return load_ft3(path), overrides, durations, dotted, bar_width
    return Piece(title="Untitled", bars=[]), overrides, durations, dotted, bar_width


def _load_piece(path: str | None) -> Piece:
    piece, _overrides, _durations, _dotted, _bar_width = _load_piece_data(path)
    return piece


def _main(stdscr: curses.window, path: str | None) -> int:  # noqa: PLR0912
    curses.curs_set(0)
    stdscr.keypad(True)
    stdscr.timeout(50)

    settings = load_settings(CONFIG_PATH)
    piece, overrides, durations, dotted, bar_width = _load_piece_data(path)
    if not piece.bars:
        piece.bars = [Bar()]

    state = EditorState(piece, settings)
    state.overrides = overrides
    state.durations = durations
    state.dotted = dotted
    state.path = path
    is_tab = bool(path and path.lower().endswith(".tab"))
    if piece.style:
        state.settings["style"] = piece.style
    if piece.tuning:
        tuned_strings = _tuning_count(piece.tuning)
        if tuned_strings:
            state.piece.strings = tuned_strings
            state.settings["tuning"] = piece.tuning
    if not is_tab and path is None:
        try:
            strings = int(settings.get("strings", DEFAULT_SETTINGS["strings"]))
        except ValueError:
            strings = int(DEFAULT_SETTINGS["strings"])
        if 4 <= strings <= 7:
            state.piece.strings = strings
    elif not piece.tuning:
        state.piece.strings = int(DEFAULT_SETTINGS["strings"])
        if not state.settings.get("tuning"):
            state.settings["tuning"] = "g2c3f3a3d4g4"
    try:
        spacing = int(settings.get("spacing", DEFAULT_SETTINGS["spacing"]))
    except ValueError:
        spacing = int(DEFAULT_SETTINGS["spacing"])
    if bar_width:
        state.bar_width = max(4, bar_width)
    else:
        state.bar_width = max(4, spacing)
    if piece.bars and piece.bars[0].time_sig:
        state.settings["time"] = piece.bars[0].time_sig or state.settings.get("time", "C")
    if piece.tuning:
        state.settings["tuning"] = piece.tuning
    if not state.durations:
        state.durations = build_durations(piece)

    running = True
    while running:
        height, width = stdscr.getmaxyx()
        state.screen_height = height
        state.screen_width = width
        state.clamp()
        _ensure_cursor_visible(state, width, height)
        render_piece(
            stdscr,
            state.piece,
            state.bar_offset,
            state.cursor_bar,
            state.cursor_string,
            state.cursor_col,
            state.bar_width,
            state.overrides,
            state.durations,
            state.ornaments,
            state.annotations,
            state.highlights,
            state.dotted,
            state.slurs,
            state.ties,
            state.holds,
            state.mode,
            state.cmdline,
            state.message,
            _status_line(state),
            state.searchline,
            state.settings,
            export_ascii(
                state.piece,
                state.overrides,
                state.durations,
                state.bar_width,
                settings=state.settings,
                ornaments=state.ornaments,
                annotations=state.annotations,
                slurs=state.slurs,
                ties=state.ties,
                holds=state.holds,
            ).splitlines()
            if state.ascii_preview
            else None,
            state.stave_breaks,
            state.help_offset,
        )

        key = stdscr.getch()
        if key != -1:
            running = _handle_key(state, key)

    return 0


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else None
    return curses.wrapper(_main, path)


if __name__ == "__main__":
    raise SystemExit(main())
