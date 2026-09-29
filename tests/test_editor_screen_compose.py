from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from oud.editor.core.feedback.messages import MessageLevel
from oud.editor.core.input.modes import Mode
from oud.editor.core.state import EditorState
from oud.editor.services.bootstrap import init_state
from oud.editor.services.io.files import render_ascii_snapshot
from oud.editor.services.screen.compose import compose_editor_frame
from oud.services.plugins.model import RemoteTab
from petrucci.core.model import Bar, MelodyEvent, Piece
from petrucci.rendering.api import render_piece
from petrucci.terminal.canvas.screen import A_BOLD, A_REVERSE, A_UNDERLINE

EDITOR_ONLY_ARGUMENTS = {
    "mode",
    "cmdline",
    "searchline",
    "message",
    "message_level",
    "status_line",
    "ascii_lines",
    "plugin_title",
    "plugin_items",
    "plugin_index",
    "plugin_offset",
    "help_offset",
    "help_lines",
}


@pytest.fixture
def state(tmp_path: Path) -> EditorState:
    return init_state("examples/triste.tab", config_path=str(tmp_path / "config.toml"))


def _lines(state: EditorState, *, height: int = 24, width: int = 80) -> list[str]:
    return [line.rstrip() for line in compose_editor_frame(state, height=height, width=width).frame.lines]


def test_petrucci_render_piece_takes_no_editor_chrome() -> None:
    assert EDITOR_ONLY_ARGUMENTS.isdisjoint(inspect.signature(render_piece).parameters)


def test_tablature_status_row_shows_position_mode_and_duration(state: EditorState) -> None:
    lines = _lines(state)
    assert lines[-1].startswith("triste.tab [TAB] bar:1 beat:1/6 str:1 ")
    assert lines[-1].endswith("len:2  normal")
    assert any("|" in line and "-" in line for line in lines[:-1])


def test_status_row_carries_the_message_severity(state: EditorState) -> None:
    state.notify("Write failed", MessageLevel.ERROR)
    composed = compose_editor_frame(state, height=24, width=80)
    assert "str:1  Write failed " in composed.frame.lines[-1]
    assert composed.frame.attrs[-1][0] == A_REVERSE | A_BOLD | A_UNDERLINE


def test_notation_view_status_row_has_no_tablature_duration(tmp_path: Path) -> None:
    state = init_state(None, config_path=str(tmp_path / "config.toml"))
    events = [MelodyEvent(step, onset, note_type=4) for onset, step in enumerate("cdef")]
    state.piece = Piece(title="Melody", strings=6, bars=[Bar(melody_events=events, time_sig="4/4")])
    status = _lines(state)[-1]
    assert status.endswith("normal")
    assert "len:" not in status


def test_hidden_bottom_panel_gives_the_score_every_row(state: EditorState) -> None:
    assert "[TAB]" in _lines(state)[-1]
    state.settings["bottompanel"] = "off"
    assert "[TAB]" not in _lines(state)[-1]
    state.mode = Mode.COMMAND
    state.cmdline = "set"
    assert _lines(state)[-1] == ":set"


def test_help_page_shows_the_generated_key_table(state: EditorState) -> None:
    state.mode = Mode.HELP
    lines = _lines(state)
    assert lines[0].startswith("HELP  keys=")
    assert lines[-1].endswith("help  j/k scroll  q close")


def test_info_and_notes_pages_describe_the_document(state: EditorState) -> None:
    state.mode = Mode.INFO
    info = _lines(state, height=60, width=100)
    assert info[0] == "INFO"
    assert "Terminal:     100x60" in info
    assert info[-1].startswith("triste.tab [TAB] bar:1 beat:1/6 str:1 ")
    assert info[-1].endswith("info")
    state.mode = Mode.NOTES
    notes = _lines(state)
    assert notes[0] == "NOTES"


def test_plugin_browser_marks_the_selected_item(state: EditorState) -> None:
    state.mode = Mode.PLUGIN
    state.plugins.items = [RemoteTab("folder", "u", is_dir=True), RemoteTab("piece", "v")]
    state.plugins.index = 1
    lines = _lines(state)
    assert lines[:3] == ["Plugins", "  folder/", "> piece"]
    assert lines[-1].endswith("plugin  j/k move  h back  l/enter open  d download  q close")


def test_ascii_preview_shows_the_export_above_the_status_row(state: EditorState) -> None:
    state.ascii_preview = True
    lines = _lines(state)
    assert lines[1].startswith(" 6|")
    assert lines[-1].startswith("triste.tab [TAB] bar:1 beat:1/6 str:1 ")
    assert lines[-1].endswith("normal  ascii preview")


def test_ascii_snapshot_is_the_composed_screen(state: EditorState) -> None:
    state.screen_height, state.screen_width = 24, 80
    composed = compose_editor_frame(state, height=24, width=80)
    assert render_ascii_snapshot(state) == "\n".join(composed.frame.lines) + "\n"


def test_tablature_playback_uses_an_overlay_cache(state: EditorState) -> None:
    assert compose_editor_frame(state, height=24, width=80).playback_cache is not None
    state.piece.part = "score"
    state.piece.ensemble = "lute 1, lute 2"
    assert compose_editor_frame(state, height=24, width=80).playback_cache is None


def test_status_row_uses_reverse_video_without_a_message(state: EditorState) -> None:
    assert set(compose_editor_frame(state, height=24, width=80).frame.attrs[-1][:79]) == {A_REVERSE}
    state.notify("careful", MessageLevel.WARNING)
    assert compose_editor_frame(state, height=24, width=80).frame.attrs[-1][0] == A_REVERSE | A_UNDERLINE
