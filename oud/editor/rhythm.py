from __future__ import annotations

from oud.core.render_utils import chord_slot_positions, note_type_to_denom
from oud.editor.motions import apply_motion_target, target_advance_next_bar_home
from oud.editor.state import EditorState


def expected_beats(state: EditorState) -> float | None:
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


def column_duration(state: EditorState, bar_index: int, col: int) -> float | None:
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


def column_denom(state: EditorState, bar_index: int, col: int) -> int:
    found = None
    for s_idx in range(state.piece.strings):
        key = (bar_index, s_idx, col)
        if key in state.durations:
            denom = state.durations[key]
            if found is None or denom > found:
                found = denom
    return found or 4


def column_has_duration(state: EditorState, bar_index: int, col: int) -> bool:
    return any(
        (bar_index, s_idx, col) in state.durations
        for s_idx in range(state.piece.strings)
    )


def cell_has_duration(state: EditorState, bar_index: int, string: int, col: int) -> bool:
    return (bar_index, string, col) in state.durations


def _row_has_note(state: EditorState, bar_index: int, string: int, col: int) -> bool:
    if (bar_index, string, col) in state.overrides:
        return True
    bar = state.piece.bars[bar_index]
    if not bar.chords:
        return False
    positions = chord_slot_positions(bar, state.bar_width, default_duration=4)
    for chord, (pos, _denom, _dot) in zip(bar.chords, positions, strict=False):
        if pos != col:
            continue
        for note in chord.notes:
            if note.string == string + 1:
                return True
    return False


def row_duration_sum(state: EditorState, bar_index: int, string: int) -> float:
    if bar_index < 0 or bar_index >= len(state.piece.bars):
        return 0.0
    bar = state.piece.bars[bar_index]
    if bar.chords:
        total = 0.0
        for chord in bar.chords:
            if not any(note.string == string + 1 for note in chord.notes):
                continue
            denom = note_type_to_denom(chord.note_type) or 4
            duration = 4.0 / denom
            if chord.dotted:
                duration *= 1.5
            total += duration
        return total
    total = 0.0
    for col in range(state.bar_width):
        if not _row_has_note(state, bar_index, string, col):
            continue
        denom = column_denom(state, bar_index, col)
        duration = 4.0 / denom
        if (bar_index, col) in state.dotted:
            duration *= 1.5
        total += duration
    return total


def bar_duration_sum_by_col(state: EditorState, bar_index: int) -> float:  # noqa: C901
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


def advance_to_next_bar(state: EditorState) -> None:
    apply_motion_target(state, target_advance_next_bar_home(state))


def advance_if_bar_full(state: EditorState) -> None:
    expected = expected_beats(state)
    if expected is None:
        return
    for string in range(state.piece.strings):
        total = row_duration_sum(state, state.cursor_bar, string)
        if total >= expected:
            advance_to_next_bar(state)
            return


def advance_if_overflow(state: EditorState, denom: int, string: int) -> None:
    expected = expected_beats(state)
    if expected is None:
        return
    bar = state.cursor_bar
    col = state.cursor_col
    if _row_has_note(state, bar, string, col):
        return
    total = row_duration_sum(state, bar, string)
    duration = 4.0 / denom
    if (bar, col) in state.dotted:
        duration *= 1.5
    if total + duration > expected:
        advance_to_next_bar(state)
