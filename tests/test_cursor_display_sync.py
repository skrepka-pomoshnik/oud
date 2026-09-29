"""Cursor movement must track the rendered cursor cell.

The renderer publishes per-bar logical-col -> display-col maps
(``cursor_display_maps``); visual h/l movement consumes them so every keypress
moves the drawn cursor. These tests drive the same render/press cycle as the
TUI loop and assert the drawn cursor never stalls.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from oud.editor.core.state import EditorState
from oud.editor.interaction.dispatch import actions
from oud.editor.interaction.dispatch.controller import handle_key
from oud.editor.navigation.viewport import ensure_cursor_visible
from oud.editor.services.screen.compose import compose_editor_frame
from oud.presentation.tui.commands import apply_command
from petrucci.terminal.canvas.framebuffer import Frame
from petrucci.terminal.canvas.screen import A_REVERSE
from tests.helpers_ft3 import write_galliard
from tests.helpers_keyscript import keyscript_state


def _render(state: EditorState) -> Frame:
    ensure_cursor_visible(state, state.screen_width, state.screen_height)
    return compose_editor_frame(state, height=state.screen_height, width=state.screen_width).frame


def _drawn_cursor(state: EditorState) -> tuple[int, int, int] | None:
    frame = _render(state)
    for y, row in enumerate(frame.attrs):
        reverse_cells = [x for x, attr in enumerate(row) if attr & A_REVERSE]
        # The status bar is fully reversed; the cursor is a single cell.
        if reverse_cells and len(reverse_cells) < 20:
            return (y, reverse_cells[0], state.bar_offset)
    return None


def _press(state: EditorState, char: str) -> None:
    handle_key(
        state,
        ord(char),
        handle_insert=actions.handle_insert,
        handle_normal=actions.handle_normal,
        handle_command=lambda _state, _key: True,
        handle_search=lambda _state, _key: True,
    )


def _count_stalls(state: EditorState, char: str, presses: int) -> int:
    stalls = 0
    prev = _drawn_cursor(state)
    for _ in range(presses):
        _press(state, char)
        pos = _drawn_cursor(state)
        if pos == prev:
            stalls += 1
        prev = pos
    return stalls


def _opened(path: str) -> EditorState:
    state = keyscript_state(width=100, height=30)
    apply_command(state, f"e {path}", "config.toml")
    _render(state)
    return state


def test_drawn_cursor_moves_on_every_l_press_in_chord_bars(tmp_path: Path) -> None:
    state = _opened(str(write_galliard(tmp_path)))
    assert _count_stalls(state, "l", 40) == 0


def test_drawn_cursor_moves_on_every_h_press_in_chord_bars(tmp_path: Path) -> None:
    state = _opened(str(write_galliard(tmp_path)))
    for _ in range(40):
        _press(state, "l")
    assert _count_stalls(state, "h", 40) == 0


def test_drawn_cursor_moves_in_tab_grid_bars() -> None:
    state = _opened("examples/triste.tab")
    assert _count_stalls(state, "l", 40) == 0
    assert _count_stalls(state, "h", 40) == 0


@pytest.mark.ft3_corpus
def test_drawn_cursor_moves_in_vocal_piece_with_scrolling() -> None:
    state = _opened("tests/fixtures/ft3/corpus/32_passacaglia.ft3")
    assert _count_stalls(state, "l", 60) == 0
    assert _count_stalls(state, "h", 60) == 0


def test_renderer_publishes_cursor_maps_for_rendered_bars(tmp_path: Path) -> None:
    state = _opened(str(write_galliard(tmp_path)))
    assert state.display_cursor_maps
    for bar_index, mapping in state.display_cursor_maps.items():
        assert len(mapping) == state.bar_width, bar_index
        assert all(col >= 0 for col in mapping)
        assert mapping == sorted(mapping)
