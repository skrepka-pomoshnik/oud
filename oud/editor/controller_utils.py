from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oud.editor.state import EditorState


MAX_KEY_COUNT = 999
_COUNT_LIMIT_MESSAGE = f"Count limited to {MAX_KEY_COUNT}"


def allow_arrows(state: EditorState) -> bool:
    return state.settings.get("keys", "vim+arrows") != "vim"


def is_casual(state: EditorState) -> bool:
    return state.settings.get("keys", "vim+arrows") in ("casual", "casual+arrows")


def _bass_strings_used(state: EditorState) -> set[int]:  # noqa: C901
    used: set[int] = set()
    for bar, string, _col in state.overrides:
        if bar < len(state.piece.bars) and string >= 6:
            used.add(string)
    for bar in state.piece.bars:
        for note in bar.notes:
            idx = note.string - 1
            if idx >= 6:
                used.add(idx)
        for chord in bar.chords:
            for note in chord.notes:
                idx = note.string - 1
                if idx >= 6:
                    used.add(idx)
    return used


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
    state.cursor_col = max(0, min(state.cursor_col, state.bar_width - 1))


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
