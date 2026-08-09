from __future__ import annotations

from oud.editor.core.state import EditorState
from oud.importers.tab import (
    TabData,
    TabParseDelta,
    parse_tab_text_data,
    reparse_tab_text_auto_delta,
    reparse_tab_text_delta,
)


def apply_tab_reparse_delta(
    state: EditorState,
    new_text: str,
    *,
    changed_line_start: int | None = None,
    changed_line_end: int | None = None,
    old_changed_line_start: int | None = None,
    old_changed_line_end: int | None = None,
) -> TabParseDelta:
    previous = state.tab_data
    if previous is None:
        parsed = parse_tab_text_data(new_text, strings=state.piece.strings)
        delta = TabParseDelta(
            data=parsed,
            old_bar_range=(0, 0),
            new_bar_range=(0, len(parsed.piece.bars) if parsed is not None else 0),
            full_reparse=True,
            reason="no_previous_tab_data",
        )
        _apply_tab_delta_to_state(state, delta)
        return delta

    if changed_line_start is None or changed_line_end is None:
        delta = reparse_tab_text_auto_delta(
            previous,
            new_text,
            strings=state.piece.strings,
        )
    else:
        delta = reparse_tab_text_delta(
            previous,
            new_text,
            changed_line_start=changed_line_start,
            changed_line_end=changed_line_end,
            old_changed_line_start=old_changed_line_start,
            old_changed_line_end=old_changed_line_end,
            strings=state.piece.strings,
        )
    _apply_tab_delta_to_state(state, delta)
    return delta


def _apply_tab_delta_to_state(state: EditorState, delta: TabParseDelta) -> None:
    if delta.data is None:
        return
    _apply_tab_data_to_state(state, delta.data)


def _apply_tab_data_to_state(state: EditorState, data: TabData) -> None:
    state.tab_data = data
    state.piece = data.piece
    state.overrides = dict(data.overrides)
    state.durations = dict(data.durations)
    state.dotted = set(data.dotted)
    if data.bar_width:
        state.bar_width = max(4, data.bar_width)
    state.clamp()
