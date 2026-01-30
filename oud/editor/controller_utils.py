from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oud.editor.state import EditorState


def allow_arrows(state: EditorState) -> bool:
    return state.settings.get("keys", "vim+arrows") != "vim"


def is_casual(state: EditorState) -> bool:
    return state.settings.get("keys", "vim+arrows") in ("casual", "casual+arrows")


def string_index(state: EditorState, display_index: int) -> int:
    if (
        state.settings.get("style") == "italian"
        and state.settings.get("italianorient") == "reverse"
    ):
        return state.piece.strings - 1 - display_index
    return display_index


def cursor_key(state: EditorState) -> tuple[int, int, int]:
    return (state.cursor_bar, string_index(state, state.cursor_string), state.cursor_col)


def clamp_cursor(state: EditorState) -> None:
    bar_count = max(1, len(state.piece.bars))
    state.cursor_bar = max(0, min(state.cursor_bar, bar_count - 1))
    state.cursor_string = max(0, min(state.cursor_string, state.piece.strings - 1))
    state.cursor_col = max(0, min(state.cursor_col, state.bar_width - 1))


def consume_count(state: EditorState) -> int:
    if not state.count_prefix:
        return 1
    try:
        value = int(state.count_prefix)
    except ValueError:
        value = 1
    state.count_prefix = ""
    return value
