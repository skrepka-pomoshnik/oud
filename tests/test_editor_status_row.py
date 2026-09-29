from __future__ import annotations

from pathlib import Path

import pytest

from oud.editor.core.feedback.messages import MessageLevel
from oud.editor.core.input.modes import Mode
from oud.editor.core.state import EditorState
from oud.editor.services.bootstrap import init_state
from oud.editor.services.screen.rhythm import bar_meter_marker, cursor_duration_text
from oud.editor.services.screen.status import status_row_attr, status_row_text
from petrucci.core.model import Bar, Chord, Note, Piece
from petrucci.terminal.canvas.screen import A_BOLD, A_DIM, A_REVERSE, A_UNDERLINE


@pytest.fixture
def state(tmp_path: Path) -> EditorState:
    state = init_state(None, config_path=str(tmp_path / "config.toml"))
    state.screen_width = 80
    state.bar_width = 8
    return state


def _quarters(count: int) -> Bar:
    return Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, fret, 0)]) for fret in range(count)])


def test_cursor_duration_prefers_grid_duration_and_marks_dots(state: EditorState) -> None:
    state.durations = {(0, 0, 2): 8}
    state.dotted = {(0, 2)}
    state.cursor_col = 2
    assert cursor_duration_text(state) == "8."


def test_cursor_duration_falls_back_to_the_chord_at_the_cursor(state: EditorState) -> None:
    state.piece = Piece(title="T", bars=[_quarters(1)], strings=6)
    assert cursor_duration_text(state) == "4"
    state.cursor_col = 5
    assert cursor_duration_text(state) is None


def test_bar_meter_marker_flags_only_bars_that_do_not_fill_their_meter(state: EditorState) -> None:
    state.settings["time"] = "C"
    state.piece = Piece(title="T", bars=[_quarters(1), _quarters(4), Bar()], strings=6)
    assert bar_meter_marker(state) == "M"
    state.cursor_bar = 1
    assert bar_meter_marker(state) is None
    state.cursor_bar = 2
    assert bar_meter_marker(state) is None


def test_prompt_modes_show_only_the_prompt_and_message(state: EditorState) -> None:
    state.mode = Mode.COMMAND
    state.cmdline = "w"
    state.message = "ok"
    assert status_row_text(state, duration="8") == ":w  ok"
    state.cmdline = "e ex"
    state.message = "Matches: examples/ examples2/"
    assert status_row_text(state).startswith(":e ex  Matches:")
    state.mode = Mode.SEARCH
    state.searchline = "12"
    state.message = ""
    assert status_row_text(state) == "/12"


def test_status_row_shows_duration_until_a_message_replaces_it(state: EditorState) -> None:
    quiet = status_row_text(state, duration="4")
    assert quiet.startswith("[No Name]")
    assert quiet.endswith("normal  len:4")
    state.message = "msg"
    loud = status_row_text(state, duration="4")
    assert "len:4" not in loud
    assert loud.endswith("normal  msg")


def test_meter_marker_follows_the_position_and_stays_apart_from_the_message(state: EditorState) -> None:
    state.notify("warn", MessageLevel.WARNING)
    line = status_row_text(state, meter="M")
    assert "bar:1 beat:1/4 str:1 M  normal  warn" in line


def test_hidden_bottom_panel_leaves_only_mode_and_message(state: EditorState) -> None:
    state.settings["bottompanel"] = "off"
    assert status_row_text(state, duration="4") == "normal  len:4"


def test_status_message_levels_have_distinct_portable_attributes(state: EditorState) -> None:
    assert status_row_attr(state) == A_REVERSE
    attrs = {}
    for level in MessageLevel:
        state.notify(f"{level.value} message", level)
        attrs[level] = status_row_attr(state)
    assert attrs == {
        MessageLevel.INFO: A_REVERSE,
        MessageLevel.SUCCESS: A_REVERSE | A_BOLD,
        MessageLevel.WARNING: A_REVERSE | A_UNDERLINE,
        MessageLevel.ERROR: A_REVERSE | A_BOLD | A_UNDERLINE,
        MessageLevel.CONFIRM: A_REVERSE | A_DIM,
    }
