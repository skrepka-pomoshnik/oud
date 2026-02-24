from __future__ import annotations

from oud.core.model import Bar, Chord, Note, Piece
from oud.ui.render_status import build_status_lines, resolve_duration_text


def test_resolve_duration_text_manual_and_dotted() -> None:
    piece = Piece(title="T", bars=[Bar()], strings=6)
    durations = {(0, 1, 2): 8}
    dotted = {(0, 2)}
    text = resolve_duration_text(
        piece=piece,
        durations=durations,
        dotted=dotted,
        cursor_bar=0,
        cursor_col=2,
        actual_cursor_string=1,
        bar_width=8,
    )
    assert text == "8."


def test_resolve_duration_text_from_chord_positions() -> None:
    piece = Piece(
        title="T",
        bars=[Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])])],
        strings=6,
    )
    text = resolve_duration_text(
        piece=piece,
        durations={},
        dotted=set(),
        cursor_bar=0,
        cursor_col=0,
        actual_cursor_string=0,
        bar_width=8,
    )
    assert text is not None


def test_build_status_lines_modes() -> None:
    line = build_status_lines(
        mode="command",
        cmdline="w",
        searchline="",
        message="ok",
        status_line="base",
        dur_text="8",
    )
    assert line == ":w"
    line = build_status_lines(
        mode="command",
        cmdline="e ex",
        searchline="",
        message="Matches: examples/ examples2/",
        status_line="base",
        dur_text=None,
    )
    assert line.startswith(":e ex  Matches:")
    line = build_status_lines(
        mode="normal",
        cmdline="",
        searchline="",
        message="msg",
        status_line="base",
        dur_text="4",
    )
    assert "len:4" in line
    assert "msg" in line
    assert "base" in line
