"""Cursor duration and bar-meter diagnostics for the tablature status row.

These read the editor grid maps (``overrides``, ``durations``, ``dotted``) and the
bar's chords. They move to exact onsets when the grid maps are retired.
"""

from __future__ import annotations

from oud.editor.core.coordinates import string_index
from oud.editor.core.state import EditorState
from petrucci.core.music.time import parse_time_signature_value
from petrucci.rendering.primitives.utils import note_type_to_denom
from petrucci.terminal.view.model import chord_positions

DEFAULT_DURATION = 4
METER_MISMATCH_MARKER = "M"
_BEAT_TOLERANCE = 0.01

GridKey = tuple[int, int, int]


def _manual_duration_at(state: EditorState, *, preferred_string: int) -> int | None:
    bar, col = state.cursor_bar, state.cursor_col
    preferred = state.durations.get((bar, preferred_string, col))
    if preferred is not None:
        return preferred
    return next(
        (
            state.durations[(bar, string, col)]
            for string in range(state.piece.strings)
            if (bar, string, col) in state.durations
        ),
        None,
    )


def _chord_duration_at(state: EditorState) -> int | None:
    bar_index = state.cursor_bar
    if not 0 <= bar_index < len(state.piece.bars) or not state.piece.bars[bar_index].chords:
        return None
    positions = chord_positions(state.piece.bars[bar_index], state.bar_width, DEFAULT_DURATION)
    return next((denominator for column, denominator, _dot in positions if column == state.cursor_col), None)


def cursor_duration_text(state: EditorState) -> str | None:
    """Written duration under the cursor, such as ``4`` or ``8.``."""

    manual = _manual_duration_at(state, preferred_string=string_index(state, state.cursor_string))
    if manual is not None:
        dotted = (state.cursor_bar, state.cursor_col) in state.dotted
        return f"{manual}." if dotted else str(manual)
    chord = _chord_duration_at(state)
    return str(chord) if chord is not None else None


def _quarter_beats(denominator: int, *, dotted: bool) -> float:
    beats = 4.0 / denominator
    return beats * 1.5 if dotted else beats


def _chord_bar_quarter_beats(state: EditorState, bar_index: int) -> float:
    bar = state.piece.bars[bar_index]
    positions = chord_positions(bar, state.bar_width, DEFAULT_DURATION)
    total = 0.0
    for index, chord in enumerate(bar.chords):
        denominator = note_type_to_denom(chord.note_type) or DEFAULT_DURATION
        dotted = chord.dotted
        if index < len(positions) and (bar_index, positions[index][0]) in state.dotted:
            dotted = True
        total += _quarter_beats(denominator, dotted=dotted)
    return total


def _column_duration(durations: dict[GridKey, int], *, bar_index: int, strings: int, col: int) -> int | None:
    values = (durations[(bar_index, string, col)] for string in range(strings) if (bar_index, string, col) in durations)
    return max(values, default=None)


def _grid_bar_quarter_beats(state: EditorState, bar_index: int) -> float:
    total = 0.0
    last: tuple[int, bool] | None = None
    for col in range(state.bar_width):
        found = _column_duration(state.durations, bar_index=bar_index, strings=state.piece.strings, col=col)
        if found is None:
            continue
        current = (found, (bar_index, col) in state.dotted)
        # Consecutive columns with the same duration belong to one sustained event.
        if current == last:
            continue
        total += _quarter_beats(found, dotted=current[1])
        last = current
    return total


def _bar_has_grid_entries(state: EditorState, bar_index: int) -> bool:
    return any(bar == bar_index for bar, _string, _col in state.overrides) or any(
        bar == bar_index for bar, _string, _col in state.durations
    )


def bar_meter_marker(state: EditorState) -> str | None:
    """``M`` when the cursor bar's durations do not fill its meter, otherwise ``None``."""

    bar_index = state.cursor_bar
    if not 0 <= bar_index < len(state.piece.bars):
        return None
    bar = state.piece.bars[bar_index]
    if not (bar.chords or bar.notes or _bar_has_grid_entries(state, bar_index)):
        return None
    parsed = parse_time_signature_value(bar.time_sig or state.settings.get("time", "C"))
    if parsed is None:
        return None
    beats, unit = parsed
    expected = beats * (4.0 / unit)
    total = _chord_bar_quarter_beats(state, bar_index) if bar.chords else _grid_bar_quarter_beats(state, bar_index)
    return None if abs(total - expected) < _BEAT_TOLERANCE else METER_MISMATCH_MARKER
