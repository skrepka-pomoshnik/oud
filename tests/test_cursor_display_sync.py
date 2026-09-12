"""Cursor movement must track the rendered cursor cell.

The renderer publishes per-bar logical-col -> display-col maps
(``cursor_display_maps``); visual h/l movement consumes them so every keypress
moves the drawn cursor. These tests drive the same render/press cycle as the
TUI loop and assert the drawn cursor never stalls.
"""

from __future__ import annotations

from oud.editor.core.state import EditorState
from oud.editor.interaction.dispatch import actions
from oud.editor.interaction.dispatch.controller import handle_key
from oud.editor.navigation.viewport import ensure_cursor_visible
from oud.presentation.tui.commands import apply_command
from petrucci.rendering.api import render_piece
from petrucci.terminal.canvas.framebuffer import FrameBuffer
from petrucci.terminal.canvas.screen import A_REVERSE
from tests.helpers_keyscript import keyscript_state


def _render(state: EditorState) -> FrameBuffer:
    ensure_cursor_visible(state, state.screen_width, state.screen_height)
    state.display_cursor_maps.clear()
    fb = FrameBuffer(state.screen_height, state.screen_width)
    render_piece(
        fb,
        state.piece,
        state.bar_offset,
        state.cursor_bar,
        state.cursor_string,
        cursor_col=state.cursor_col,
        bar_width=state.bar_width,
        overrides=state.overrides,
        durations=state.durations,
        ornaments=state.ornaments,
        annotations=state.annotations,
        highlights=state.highlights,
        dotted=state.dotted,
        slurs=state.slurs,
        ties=state.ties,
        holds=state.holds,
        mode=state.mode,
        cmdline=state.cmdline,
        message="",
        status_line="",
        searchline=state.searchline,
        settings=state.settings,
        ascii_lines=None,
        stave_breaks=state.stave_breaks,
        plugin_title=state.plugin_title,
        plugin_items=[],
        plugin_index=state.plugin_index,
        plugin_offset=state.plugin_offset,
        help_offset=state.help_offset,
        playback_bar=state.playback_bar,
        playback_col=state.playback_col,
        glisses=state.glisses,
        cursor_display_maps=state.display_cursor_maps,
    )
    return fb


def _drawn_cursor(state: EditorState) -> tuple[int, int, int] | None:
    frame = _render(state).snapshot()
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


def test_drawn_cursor_moves_on_every_l_press_in_chord_bars() -> None:
    state = _opened("tests/fixtures/ft3/corpus/examples/02_forlorne_hope_8C.ft3")
    assert _count_stalls(state, "l", 40) == 0


def test_drawn_cursor_moves_on_every_h_press_in_chord_bars() -> None:
    state = _opened("tests/fixtures/ft3/corpus/examples/02_forlorne_hope_8C.ft3")
    for _ in range(40):
        _press(state, "l")
    assert _count_stalls(state, "h", 40) == 0


def test_drawn_cursor_moves_in_tab_grid_bars() -> None:
    state = _opened("examples/triste.tab")
    assert _count_stalls(state, "l", 40) == 0
    assert _count_stalls(state, "h", 40) == 0


def test_drawn_cursor_moves_in_vocal_piece_with_scrolling() -> None:
    state = _opened("tests/fixtures/ft3/corpus/32_passacaglia.ft3")
    assert _count_stalls(state, "l", 60) == 0
    assert _count_stalls(state, "h", 60) == 0


def test_renderer_publishes_cursor_maps_for_rendered_bars() -> None:
    state = _opened("tests/fixtures/ft3/corpus/examples/02_forlorne_hope_8C.ft3")
    assert state.display_cursor_maps
    for bar_index, mapping in state.display_cursor_maps.items():
        assert len(mapping) == state.bar_width, bar_index
        assert all(col >= 0 for col in mapping)
        assert mapping == sorted(mapping)
