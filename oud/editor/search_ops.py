from __future__ import annotations

from oud.core.render_utils import bar_cells, bar_cells_from_chords
from oud.editor.controller_utils import string_index
from oud.editor.state import EditorState


def _display_string_for_actual(state: EditorState, actual: int) -> int:
    if (
        state.settings.get("style") == "italian"
        and state.settings.get("italianorient") == "reverse"
    ):
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
    state.cursor_bar = max(0, min(bar, len(state.piece.bars) - 1))
    state.cursor_string = _display_string_for_actual(state, string_actual)
    state.cursor_col = max(0, min(col, state.bar_width - 1))


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


def search_word_under_cursor(state: EditorState, direction: int) -> bool:
    actual_string = string_index(state, state.cursor_string)
    term = _cell_char(state, state.cursor_bar, actual_string, state.cursor_col)
    if not _is_searchable(term):
        state.message = "No word under cursor"
        return False
    if not _search_word(state, term, direction):
        state.message = f"Not found: {term}"
        return False
    state.last_word_search = (term, direction)
    return True


def repeat_word_search(state: EditorState, reverse: bool) -> bool:
    if state.last_word_search is None:
        state.message = "No previous search"
        return False
    term, direction = state.last_word_search
    if reverse:
        direction *= -1
    if not _search_word(state, term, direction):
        state.message = f"Not found: {term}"
        return False
    state.last_word_search = (term, direction)
    return True


def jump_match(state: EditorState) -> bool:  # noqa: C901
    for spans in (state.slurs, state.ties, state.holds):
        for bar, start, end in spans:
            if bar != state.cursor_bar:
                continue
            if state.cursor_col == start:
                state.cursor_col = end
                return True
            if state.cursor_col == end:
                state.cursor_col = start
                return True
    current = state.piece.bars[state.cursor_bar]
    if current.repeat == ".:":
        for idx in range(state.cursor_bar + 1, len(state.piece.bars)):
            if state.piece.bars[idx].repeat == ":.":
                state.cursor_bar = idx
                state.cursor_col = 0
                return True
    elif current.repeat == ":.":
        for idx in range(state.cursor_bar - 1, -1, -1):
            if state.piece.bars[idx].repeat == ".:":
                state.cursor_bar = idx
                state.cursor_col = 0
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
    if mark not in state.marks:
        state.message = f"Mark not found: {mark}"
        return False
    bar, string_actual, col = state.marks[mark]
    _jump_to(state, bar, string_actual, col)
    return True
