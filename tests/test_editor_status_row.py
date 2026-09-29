from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import pytest

from oud.editor.core.feedback.messages import MessageLevel
from oud.editor.core.input.modes import Mode
from oud.editor.core.state import EditorState
from oud.editor.services.bootstrap import init_state
from oud.editor.services.screen.rhythm import bar_meter_marker, cursor_duration_text
from oud.editor.services.screen.status import (
    DROP_ORDER,
    StatusModel,
    render_status,
    status_attr,
    status_row_attr,
    status_row_text,
)
from petrucci.core.model import Bar, Chord, Note, Piece
from petrucci.terminal.canvas.screen import A_BOLD, A_DIM, A_REVERSE, A_UNDERLINE


@pytest.fixture
def state(tmp_path: Path) -> EditorState:
    state = init_state(None, config_path=str(tmp_path / "config.toml"))
    state.screen_width = 80
    state.message = ""
    state.bar_width = 8
    return state


def _quarters(count: int) -> Bar:
    return Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, fret, 0)]) for fret in range(count)])


def test_cursor_duration_is_the_event_duration_or_the_typing_duration(state: EditorState) -> None:
    state.piece = Piece(title="T", bars=[Bar(chords=[Chord(note_type=5, dotted=True, grid=None, notes=[])])], strings=6)
    assert cursor_duration_text(state) == "8."
    state.cursor_onset = Fraction(3, 16)
    state.current_duration = 16
    assert cursor_duration_text(state) == "16"


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


def test_status_row_anchors_identity_left_and_mode_right(state: EditorState) -> None:
    row = status_row_text(state, duration="4", width=80)
    assert len(row) == 79
    assert row.startswith("[No Name] [NEW:untitled.musicxml] bar:1 beat:1/4 str:1 ")
    assert row.endswith("len:4  normal")


def test_moving_the_cursor_does_not_move_the_right_segments(state: EditorState) -> None:
    first = status_row_text(state, duration="4", width=80)
    state.cursor_bar = 11
    state.cursor_string = 5
    moved = status_row_text(state, duration="16.", width=80)
    assert first.index("normal") == moved.index("normal")


def test_message_sits_between_the_groups_and_keeps_the_duration(state: EditorState) -> None:
    state.message = "msg"
    row = status_row_text(state, duration="4", width=80)
    assert "str:1  msg " in row
    assert row.endswith("len:4  normal")


def test_meter_marker_follows_the_position(state: EditorState) -> None:
    state.notify("warn", MessageLevel.WARNING)
    assert "bar:1 beat:1/4 str:1 M  warn" in status_row_text(state, meter="M", width=80)


def test_pending_count_and_keys_show_before_the_duration(state: EditorState) -> None:
    state.count_prefix = "3"
    state.pending_keys = (ord("d"),)
    assert status_row_text(state, duration="4", width=80).endswith("3d  len:4  normal")


def test_insert_prefix_shows_only_while_inserting(state: EditorState) -> None:
    state.insert_prefix = "/"
    assert not status_row_text(state, width=80).endswith("/  normal")
    state.mode = Mode.INSERT
    assert status_row_text(state, width=80).endswith("/  insert")


def test_hidden_bottom_panel_leaves_only_mode_and_message(state: EditorState) -> None:
    state.settings["bottompanel"] = "off"
    assert status_row_text(state, duration="4", width=0) == "len:4  normal"


def test_render_status_drops_whole_segments_in_priority_order() -> None:
    model = StatusModel(
        identity="piece.tab [TAB]",
        position="bar:1 beat:1/4 str:1",
        meter="M",
        pending="3d",
        duration="len:4",
        mode="normal",
    )
    assert render_status(model, 0) == "piece.tab [TAB] bar:1 beat:1/4 str:1 M  3d  len:4  normal"
    assert render_status(model, 60) == "piece.tab [TAB] bar:1 beat:1/4 str:1 M    3d  len:4  normal"
    assert render_status(model, 45) == "bar:1 beat:1/4 str:1 M     3d  len:4  normal"
    assert render_status(model, 40) == "bar:1 beat:1/4 str:1 M       3d  normal"
    assert render_status(model, 31) == "bar:1 beat:1/4 str:1 M  normal"
    assert render_status(model, 30) == "bar:1 beat:1/4 str:1   normal"
    assert render_status(model, 12) == "     normal"
    assert render_status(model, 3) == "no"
    assert DROP_ORDER == ("identity", "duration", "pending", "meter", "position")


def test_render_status_cuts_the_message_only_after_every_other_segment() -> None:
    model = StatusModel(identity="piece.tab [TAB]", position="bar:1", message="x" * 100, mode="normal")
    row = render_status(model, 40)
    assert len(row) == 39
    assert row == "x" * 31 + "  normal"


def test_status_attr_marks_the_level_only_while_a_message_shows() -> None:
    assert status_attr(StatusModel(level=MessageLevel.ERROR)) == A_REVERSE
    assert status_attr(StatusModel(message="x", level=MessageLevel.ERROR)) == A_REVERSE | A_BOLD | A_UNDERLINE


def test_render_status_never_writes_the_last_column() -> None:
    model = StatusModel(identity="i", position="p", mode="normal")
    for width in range(1, 30):
        assert len(render_status(model, width)) <= width - 1


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


def test_a_long_command_keeps_its_end_visible(state: EditorState) -> None:
    state.mode = Mode.COMMAND
    state.cmdline = "w " + "d" * 60 + "0123456789" + "x" * 48
    row = status_row_text(state)

    assert len(row) == 80
    assert row == "<" + state.cmdline[-79:]

    state.cmdline += "!"
    assert status_row_text(state).endswith("x!")
    assert len(status_row_text(state)) == 80


def test_a_long_search_keeps_its_end_visible_and_a_short_command_is_unchanged(state: EditorState) -> None:
    state.mode = Mode.SEARCH
    state.searchline = "s" * 100
    assert status_row_text(state) == "<" + "s" * 79

    state.mode = Mode.COMMAND
    state.cmdline = "w short"
    assert status_row_text(state) == ":w short"
