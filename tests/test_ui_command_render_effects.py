from pathlib import Path

import pytest

from oud.editor.core.state import EditorState
from oud.importers.ft3 import load_ft3
from oud.settings import DEFAULT_SETTINGS
from oud.tui.commands import apply_command
from petrucci.framebuffer import FrameBuffer
from petrucci.model import Bar, Chord, Note, Piece
from petrucci.render import render_piece


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
            "layout": "auto",
            "justify": "compact",
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


def test_set_showdur_changes_rendered_rows_in_italian_mode(tmp_path: Path) -> None:
    state = _state()
    apply_command(state, "set style=italian", str(tmp_path / "cfg.toml"))
    state.message = ""
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


def test_forlorne_bar10_playback_marker_does_not_teleport_back() -> None:
    piece = load_ft3("examples/02_forlorne_hope_8C.ft3")
    bar = piece.bars[9]
    state = EditorState(
        Piece(title="forlorne", bars=[bar], strings=piece.strings),
        {
            **DEFAULT_SETTINGS,
            "showtuning": "off",
            "showdur": "off",
            "showextras": "off",
            "showtactus": "off",
            "layout": "auto",
            "justify": "smart",
            "linelen": "0",
            "barsperline": "0",
            "maxbars": "0",
            "flagstyle": "standard",
            "barpad": "1",
            "flagredundant": "on",
        },
    )
    state.bar_width = 12
    state.playback_bar = 0
    cols: list[int] = []
    for playback_col in range(len(bar.chords)):
        state.playback_col = playback_col
        marker = _find_marker(_render_lines(state), "^")
        assert marker is not None
        cols.append(marker[1])
    assert cols == sorted(cols)


@pytest.mark.parametrize("justify", ["smart", "stretch", "compact"])
@pytest.mark.parametrize(
    ("path", "bar_index"),
    [
        ("examples/26_lachrimae_galliard_in_G.ft3", 0),
        ("examples/02_forlorne_hope_8C.ft3", 9),
        ("lutemusic/23a_frogg_galliard_2.ft3", 28),
    ],
)
def test_playback_marker_is_monotonic_on_real_fixture_bars(
    justify: str,
    path: str,
    bar_index: int,
) -> None:
    piece = load_ft3(path)
    bar = piece.bars[bar_index]
    state = EditorState(
        Piece(title="fixture", bars=[bar], strings=piece.strings),
        {
            **DEFAULT_SETTINGS,
            "showtuning": "off",
            "showdur": "off",
            "showextras": "off",
            "showtactus": "off",
            "layout": "auto",
            "justify": justify,
            "linelen": "0",
            "barsperline": "0",
            "maxbars": "0",
            "flagstyle": "standard",
            "barpad": "1",
            "flagredundant": "on",
        },
    )
    state.bar_width = max(10, len(bar.chords))
    state.playback_bar = 0
    cols: list[int] = []
    for playback_col in range(len(bar.chords)):
        state.playback_col = playback_col
        marker = _find_marker(_render_lines(state), "^")
        assert marker is not None
        cols.append(marker[1])
    assert cols == sorted(cols), (path, bar_index, justify, cols)
