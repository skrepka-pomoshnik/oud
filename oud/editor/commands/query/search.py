from __future__ import annotations

from oud.editor.core.coordinates import string_index
from oud.editor.core.state import EditorState
from oud.editor.navigation.motions import CursorMotionTarget, apply_motion_target
from petrucci.rendering.primitives.utils import bar_cells, bar_cells_from_chords


def _display_string_for_actual(state: EditorState, actual: int) -> int:
    if state.settings.get("style") == "italian" and state.settings.get("italianorient") == "reverse":
        return max(0, state.piece.strings - 1 - actual)
    return actual


def _bar_rows(state: EditorState, bar_index: int) -> list[list[str]]:
    bar = state.piece.bars[bar_index]
    style = state.settings.get("style", "french")
    french_c = state.settings.get("frenchc", "normal")
    cells = (
        bar_cells_from_chords(
            bar,
            state.piece.strings,
            state.bar_width,
            4,
            style,
            french_c=french_c,
        )
        if bar.chords
        else bar_cells(
            bar,
            state.piece.strings,
            state.bar_width,
            style,
            french_c=french_c,
        )
    )
    for (b_idx, s_idx, col), value in state.overrides.items():
        if b_idx != bar_index or not (0 <= s_idx < len(cells)) or not (0 <= col < state.bar_width):
            continue
        cells[s_idx][col] = value[0] if value else "-"
    return cells


def _cell_char(state: EditorState, bar_index: int, string_actual: int, col: int) -> str:
    if bar_index < 0 or bar_index >= len(state.piece.bars):
        return "-"
    rows = _bar_rows(state, bar_index)
    if not (0 <= string_actual < len(rows)) or not (0 <= col < state.bar_width):
        return "-"
    return rows[string_actual][col]


def _linear_total(state: EditorState) -> int:
    return max(1, len(state.piece.bars) * max(1, state.piece.strings) * max(1, state.bar_width))


def _to_linear(state: EditorState, bar: int, string_actual: int, col: int) -> int:
    strings = max(1, state.piece.strings)
    return (bar * strings * state.bar_width) + (string_actual * state.bar_width) + col


def _from_linear(state: EditorState, value: int) -> tuple[int, int, int]:
    strings = max(1, state.piece.strings)
    per_bar = strings * state.bar_width
    bar = value // per_bar
    rest = value % per_bar
    string_actual = rest // state.bar_width
    col = rest % state.bar_width
    return bar, string_actual, col


def _is_searchable(ch: str) -> bool:
    return bool(ch and ch not in ("-", " ", "|", "."))


def _jump_to(state: EditorState, bar: int, string_actual: int, col: int) -> None:
    apply_motion_target(
        state,
        CursorMotionTarget(
            max(0, min(bar, len(state.piece.bars) - 1)),
            max(0, min(col, state.bar_width - 1)),
            cursor_string=_display_string_for_actual(state, string_actual),
        ),
    )


def _search_word(state: EditorState, term: str, direction: int) -> bool:
    total = _linear_total(state)
    actual_string = string_index(state, state.cursor_string)
    start = _to_linear(state, state.cursor_bar, actual_string, state.cursor_col)
    for step in range(1, total):
        idx = (start + (direction * step)) % total
        bar, s_actual, col = _from_linear(state, idx)
        if _cell_char(state, bar, s_actual, col) == term:
            _jump_to(state, bar, s_actual, col)
            return True
    return False


def target_search_word_under_cursor(
    state: EditorState,
    direction: int,
) -> tuple[str, int, tuple[int, int, int]] | None:
    actual_string = string_index(state, state.cursor_string)
    term = _cell_char(state, state.cursor_bar, actual_string, state.cursor_col)
    if not _is_searchable(term):
        return None
    total = _linear_total(state)
    start = _to_linear(state, state.cursor_bar, actual_string, state.cursor_col)
    for step in range(1, total):
        idx = (start + (direction * step)) % total
        bar, s_actual, col = _from_linear(state, idx)
        if _cell_char(state, bar, s_actual, col) == term:
            return (term, direction, (bar, s_actual, col))
    return None


def target_repeat_word_search(
    state: EditorState,
    *,
    reverse: bool,
) -> tuple[str, int, tuple[int, int, int]] | None:
    if state.last_word_search is None:
        return None
    term, direction = state.last_word_search
    if reverse:
        direction *= -1
    total = _linear_total(state)
    actual_string = string_index(state, state.cursor_string)
    start = _to_linear(state, state.cursor_bar, actual_string, state.cursor_col)
    for step in range(1, total):
        idx = (start + (direction * step)) % total
        bar, s_actual, col = _from_linear(state, idx)
        if _cell_char(state, bar, s_actual, col) == term:
            return (term, direction, (bar, s_actual, col))
    return None


def _span_jump_target(state: EditorState) -> tuple[int, int] | None:
    for spans in (state.slurs, state.ties, state.holds):
        for bar, start, end in spans:
            if bar != state.cursor_bar:
                continue
            if state.cursor_col == start:
                return (bar, end)
            if state.cursor_col == end:
                return (bar, start)
    return None


def _repeat_jump_target(state: EditorState) -> tuple[int, int] | None:
    current = state.piece.bars[state.cursor_bar]
    if current.repeat == ".:":
        for idx in range(state.cursor_bar + 1, len(state.piece.bars)):
            if state.piece.bars[idx].repeat == ":.":
                return (idx, 0)
    elif current.repeat == ":.":
        for idx in range(state.cursor_bar - 1, -1, -1):
            if state.piece.bars[idx].repeat == ".:":
                return (idx, 0)
    return None


def target_jump_match(state: EditorState) -> tuple[int, int] | None:
    return _span_jump_target(state) or _repeat_jump_target(state)


def target_jump_mark(state: EditorState, name: str) -> tuple[int, int, int] | None:
    return state.marks.get(name.lower())


def search_word_under_cursor(state: EditorState, direction: int) -> bool:
    target = target_search_word_under_cursor(state, direction)
    if target is None:
        actual_string = string_index(state, state.cursor_string)
        term = _cell_char(state, state.cursor_bar, actual_string, state.cursor_col)
        state.message = "No word under cursor" if not _is_searchable(term) else f"Not found: {term}"
        return False
    term, direction, (bar, s_actual, col) = target
    _jump_to(state, bar, s_actual, col)
    state.last_word_search = (term, direction)
    return True


def repeat_word_search(state: EditorState, reverse: bool) -> bool:
    target = target_repeat_word_search(state, reverse=reverse)
    if target is None:
        if state.last_word_search is None:
            state.message = "No previous search"
            return False
        term, _direction = state.last_word_search
        state.message = f"Not found: {term}"
        return False
    term, direction, (bar, s_actual, col) = target
    _jump_to(state, bar, s_actual, col)
    state.last_word_search = (term, direction)
    return True


def jump_match(state: EditorState) -> bool:
    target = target_jump_match(state)
    if target is not None:
        apply_motion_target(state, CursorMotionTarget(target[0], target[1]))
        return True
    state.message = "No match"
    return False


def set_mark(state: EditorState, name: str) -> bool:
    if not name.isalpha():
        state.message = "Invalid mark"
        return False
    mark = name.lower()
    actual_string = string_index(state, state.cursor_string)
    state.marks[mark] = (state.cursor_bar, actual_string, state.cursor_col)
    state.annotations[(state.cursor_bar, state.cursor_col)] = mark
    state.message = f"Mark set: {mark}"
    state.modified = True
    return True


def jump_mark(state: EditorState, name: str) -> bool:
    mark = name.lower()
    target = target_jump_mark(state, mark)
    if target is None:
        state.message = f"Mark not found: {mark}"
        return False
    bar, string_actual, col = target
    _jump_to(state, bar, string_actual, col)
    return True
