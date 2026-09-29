from __future__ import annotations

from fractions import Fraction
from typing import TYPE_CHECKING

from petrucci.input.tablature.mutation import TabDocument, bar_content_length, bar_meter_length, event_onsets
from petrucci.rendering.primitives.utils import chord_positions

if TYPE_CHECKING:
    from oud.editor.core.state import EditorState


MAX_KEY_COUNT = 999
_COUNT_LIMIT_MESSAGE = f"Count limited to {MAX_KEY_COUNT}"
_BASS_STRING_INDEX = 6


def allow_arrows(state: EditorState) -> bool:
    return state.settings.get("keys", "vim+arrows") != "vim"


def is_casual(state: EditorState) -> bool:
    return state.settings.get("keys", "vim+arrows") in ("casual", "casual+arrows")


def _bass_override_strings(state: EditorState) -> set[int]:
    return {
        string for bar, string, _col in state.overrides if bar < len(state.piece.bars) and string >= _BASS_STRING_INDEX
    }


def _bass_note_strings(state: EditorState) -> set[int]:
    used: set[int] = set()
    for bar in state.piece.bars:
        used.update(note.string - 1 for note in bar.notes if note.string - 1 >= _BASS_STRING_INDEX)
        used.update(
            note.string - 1 for chord in bar.chords for note in chord.notes if note.string - 1 >= _BASS_STRING_INDEX
        )
    return used


def _bass_strings_used(state: EditorState) -> set[int]:
    return _bass_override_strings(state) | _bass_note_strings(state)


def visible_string_indices(state: EditorState) -> list[int]:
    total = state.piece.strings
    if state.mode in {"insert", "replace"}:
        return list(range(total))
    base = min(6, total)
    indices = list(range(base))
    bass = sorted(idx for idx in _bass_strings_used(state) if base <= idx < total)
    indices.extend(bass)
    if not indices:
        return list(range(total))
    return indices


def _reverse_view(state: EditorState) -> bool:
    return state.settings.get("viewinvert", "off") == "on" or (
        state.settings.get("style") == "italian" and state.settings.get("italianorient") == "reverse"
    )


def string_index(state: EditorState, display_index: int) -> int:
    indices = visible_string_indices(state)
    if not indices:
        return 0
    display_index = max(0, min(display_index, len(indices) - 1))
    if _reverse_view(state):
        return indices[len(indices) - 1 - display_index]
    return indices[display_index]


def cursor_key(state: EditorState) -> tuple[int, int, int]:
    return (state.cursor_bar, string_index(state, state.cursor_string), state.cursor_col)


def clamp_cursor(state: EditorState) -> None:
    bar_count = max(1, len(state.piece.bars))
    state.cursor_bar = max(0, min(state.cursor_bar, bar_count - 1))
    display_count = max(1, len(visible_string_indices(state)))
    state.cursor_string = max(0, min(state.cursor_string, display_count - 1))
    state.cursor_onset = nearest_stop(state, state.cursor_bar, state.cursor_onset)


# Cursor stops: the cursor rests on an event onset or on the append slot after the
# last event. The append slot exists while the bar is not full (or its meter is
# unknown), so an empty bar has one stop at onset 0.


def tab_document(state: EditorState) -> TabDocument:
    style = state.settings.get("style") or state.piece.style or "french"
    return TabDocument(
        state.piece.bars,
        max(1, state.piece.strings),
        style if style in {"french", "italian"} else "french",
        default_meter=state.settings.get("time"),
    )


def effective_time_signature(state: EditorState, bar_index: int) -> str:
    """The last time signature stated at or before the bar, else the document's."""

    meter = state.settings.get("time", "C")
    for bar in state.piece.bars[: bar_index + 1]:
        meter = bar.time_sig or meter
    return meter


def bar_meter(state: EditorState, bar_index: int) -> Fraction | None:
    if not 0 <= bar_index < len(state.piece.bars):
        return None
    return bar_meter_length(tab_document(state), bar_index)


def bar_is_full(state: EditorState, bar_index: int) -> bool:
    meter = bar_meter(state, bar_index)
    bar = state.piece.bars[bar_index]
    return bool(bar.chords) and meter is not None and bar_content_length(bar) >= meter


def bar_stops(state: EditorState, bar_index: int) -> tuple[Fraction, ...]:
    if not 0 <= bar_index < len(state.piece.bars):
        return (Fraction(0),)
    bar = state.piece.bars[bar_index]
    onsets = event_onsets(bar)
    if bar_is_full(state, bar_index):
        return onsets
    return (*onsets, bar_content_length(bar))


def nearest_stop(state: EditorState, bar_index: int, onset: Fraction) -> Fraction:
    """The last stop at or before ``onset``, or the first stop."""

    stops = bar_stops(state, bar_index)
    earlier = [stop for stop in stops if stop <= onset]
    return earlier[-1] if earlier else stops[0]


def cursor_event(state: EditorState) -> int:
    """Index of the event under the cursor; ``len(bar.chords)`` is the append slot."""

    if not 0 <= state.cursor_bar < len(state.piece.bars):
        return 0
    onsets = event_onsets(state.piece.bars[state.cursor_bar])
    return onsets.index(state.cursor_onset) if state.cursor_onset in onsets else len(onsets)


def at_append_slot(state: EditorState) -> bool:
    if not 0 <= state.cursor_bar < len(state.piece.bars):
        return True
    return cursor_event(state) == len(state.piece.bars[state.cursor_bar].chords)


def stop_column(state: EditorState, bar_index: int, onset: Fraction) -> int:
    """Display-grid column (``0 .. bar_width - 1``) drawn for a stop."""

    if not 0 <= bar_index < len(state.piece.bars):
        return 0
    bar = state.piece.bars[bar_index]
    columns = [column for column, _denom, _dot in chord_positions(bar, state.bar_width, 4)]
    onsets = event_onsets(bar)
    if onset in onsets:
        return columns[onsets.index(onset)]
    if not columns:
        return 0
    return min(columns[-1] + 1, max(0, state.bar_width - 1))


def stop_at_column(state: EditorState, bar_index: int, column: int) -> Fraction:
    """The last stop drawn at or before ``column``, or the first stop."""

    stops = bar_stops(state, bar_index)
    earlier = [stop for stop in stops if stop_column(state, bar_index, stop) <= column]
    return earlier[-1] if earlier else stops[0]


def consume_count(state: EditorState) -> int:
    if not state.count_prefix:
        return 1
    value = _bounded_count(state.count_prefix)
    if value == MAX_KEY_COUNT and state.count_prefix != str(MAX_KEY_COUNT):
        state.message = _COUNT_LIMIT_MESSAGE
    state.count_prefix = ""
    return value


def normalize_count_prefix(state: EditorState) -> None:
    if not state.count_prefix:
        return
    value = _bounded_count(state.count_prefix)
    normalized = str(value)
    if normalized != state.count_prefix:
        state.message = _COUNT_LIMIT_MESSAGE
        state.count_prefix = normalized


def append_count_digit(state: EditorState, digit: str) -> None:
    candidate = f"{state.count_prefix}{digit}"
    value = _bounded_count(candidate)
    state.count_prefix = str(value)
    if value == MAX_KEY_COUNT and candidate != str(MAX_KEY_COUNT):
        state.message = _COUNT_LIMIT_MESSAGE


def _bounded_count(text: str) -> int:
    normalized = text.lstrip("0") or "0"
    limit = str(MAX_KEY_COUNT)
    if not normalized.isdigit():
        return 1
    if len(normalized) > len(limit) or (len(normalized) == len(limit) and normalized > limit):
        return MAX_KEY_COUNT
    return max(1, int(normalized))
