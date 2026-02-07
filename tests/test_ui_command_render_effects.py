from pathlib import Path

from oud.core.model import Bar, Chord, Note, Piece
from oud.editor.state import EditorState
from oud.settings import DEFAULT_SETTINGS
from oud.tui.commands import apply_command
from oud.ui.framebuffer import FrameBuffer
from oud.ui.render import render_piece


def _state() -> EditorState:
    bar = Bar(
        chords=[
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
            Chord(note_type=8, dotted=False, grid=None, notes=[Note(2, 2, 0)]),
        ],
    )
    piece = Piece(title="T", bars=[bar], strings=6)
    settings = dict(DEFAULT_SETTINGS)
    settings.update(
        {
            "showtuning": "off",
            "showdur": "off",
            "showextras": "off",
            "showtactus": "off",
            "spacingmode": "auto",
            "spacingfill": "compact",
            "linelen": "0",
            "barsperline": "0",
            "maxbars": "0",
            "flagstyle": "standard",
            "barpad": "1",
        },
    )
    state = EditorState(piece, settings)
    state.bar_width = 8
    return state


def _render_lines(state: EditorState) -> list[str]:
    fb = FrameBuffer(80, 100)
    render_piece(
        fb,
        state.piece,
        state.bar_offset,
        state.cursor_bar,
        state.cursor_string,
        state.cursor_col,
        state.bar_width,
        state.overrides,
        state.durations,
        state.ornaments,
        state.annotations,
        state.highlights,
        state.dotted,
        state.slurs,
        state.ties,
        state.holds,
        state.mode,
        state.cmdline,
        "",
        "",
        state.searchline,
        state.settings,
        None,
        state.stave_breaks,
        state.plugin_title,
        [],
        state.plugin_index,
        state.plugin_offset,
        state.help_offset,
        state.playback_bar,
        state.playback_col,
    )
    frame = fb.snapshot()
    return frame.lines[:-2]


def _find_marker(lines: list[str], marker: str) -> tuple[int, int] | None:
    for row_idx, line in enumerate(lines):
        col_idx = line.find(marker)
        if col_idx >= 0:
            return row_idx, col_idx
    return None


def test_set_showdur_changes_rendered_rows(tmp_path: Path) -> None:
    state = _state()
    before = _render_lines(state)
    apply_command(state, "set showdur=on", str(tmp_path / "cfg.toml"))
    state.message = ""
    after = _render_lines(state)
    assert before != after


def test_tool_gridflags_changes_flag_glyph_in_render(tmp_path: Path) -> None:
    state = _state()
    before = _render_lines(state)
    assert any("\\" in line for line in before)
    apply_command(state, "tool gridflags", str(tmp_path / "cfg.toml"))
    state.message = ""
    after = _render_lines(state)
    assert before != after
    assert any("=" in line for line in after)


def test_tool_comments_clears_visible_annotations(tmp_path: Path) -> None:
    state = _state()
    apply_command(state, "set showextras=on", str(tmp_path / "cfg.toml"))
    apply_command(state, "annot X", str(tmp_path / "cfg.toml"))
    state.message = ""
    with_annotation = _render_lines(state)
    assert any("X" in line for line in with_annotation)
    apply_command(state, "tool comments", str(tmp_path / "cfg.toml"))
    state.message = ""
    without_annotation = _render_lines(state)
    assert not any("X" in line for line in without_annotation)


def test_playback_render_with_marker_does_not_crash() -> None:
    state = _state()
    state.playback_bar = 0
    state.playback_col = 0
    after = _render_lines(state)
    assert after


def test_playback_render_updates_for_different_columns() -> None:
    state = _state()
    state.playback_bar = 0
    state.playback_col = 0
    first = _render_lines(state)
    state.playback_col = 5
    second = _render_lines(state)
    assert first
    assert second
