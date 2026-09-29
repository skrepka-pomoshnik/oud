from __future__ import annotations

from fractions import Fraction

import pytest

from oud.editor.core.state import EditorState
from petrucci.core.model import Bar, Chord, Note, Piece
from tests.helpers_keyscript import (
    find_marker,
    first_flag_and_top_note_x,
    keyscript_state,
    press_keys,
    render_lines,
    tab_events,
)
from tests.helpers_regression_cases import (
    dense_flag_alignment_piece,
    piece_with_unused_then_used_bass_rows,
)


def _bar_motion_state(
    *,
    justify: str,
    beatsnap: str,
) -> EditorState:
    # Four full 4/4 bars of eighths on course 1.
    bars = [Bar(chords=[Chord(5, False, None, [Note(1, fret, 0)]) for fret in range(8)]) for _ in range(4)]
    return keyscript_state(
        piece=Piece(title="T", bars=bars, strings=6, style="french"),
        width=60,
        height=20,
        bar_width=8,
        settings_override={
            "layout": "auto",
            "justify": justify,
            "beatsnap": beatsnap,
            "time": "4/4",
        },
    )


@pytest.mark.parametrize("justify", ["compact", "smart", "stretch"])
@pytest.mark.parametrize("beatsnap", ["off", "soft"])
def test_keyscript_insert_repeated_notes_visual_l_is_grid_stable_across_spacing_modes(
    justify: str,
    beatsnap: str,
) -> None:
    state = keyscript_state(
        width=18,
        height=20,
        bar_width=12,
        settings_override={"justify": justify, "beatsnap": beatsnap, "time": "4/4"},
    )
    press_keys(state, ["i", "a", "a", "a", "a", 27])
    state.cursor_bar, state.cursor_onset = 0, Fraction(0)
    stops = []
    for _ in range(5):
        press_keys(state, ["l"])
        stops.append((state.cursor_bar, state.cursor_onset))
    # Every press moves one event, independent of justification mode.
    assert stops == [
        (0, Fraction(1, 4)),
        (0, Fraction(1, 2)),
        (0, Fraction(3, 4)),
        (1, Fraction(0)),
        (2, Fraction(0)),
    ], (justify, beatsnap)


@pytest.mark.parametrize("justify", ["compact", "smart", "stretch"])
@pytest.mark.parametrize("beatsnap", ["off", "soft"])
def test_keyscript_insert_repeated_notes_keeps_first_flag_anchored_to_first_note(
    justify: str,
    beatsnap: str,
) -> None:
    state = keyscript_state(
        width=28,
        height=20,
        bar_width=12,
        settings_override={"justify": justify, "beatsnap": beatsnap},
    )
    press_keys(state, ["i"])
    for _ in range(4):
        press_keys(state, ["a"])
        lines = render_lines(state, width=28, height=20)
        flag_x, note_x = first_flag_and_top_note_x(lines)
        assert flag_x is not None
        assert note_x is not None
        # An incomplete bar is laid out against its content, so notes may re-space
        # while typing (TODO follow-up); the first flag always stays on the first note.
        assert flag_x == note_x, (justify, beatsnap)


def test_keyscript_french_bass_slash_prefix_commits_before_arrow_move() -> None:
    state = keyscript_state(width=30, height=20, strings=7, style="french", bar_width=12)
    right = state.keycodes.right
    press_keys(state, ["i", "/", right, "a"])
    # Movement cancels the prefix; the note goes on the cursor course of the next stop, not a bass course.
    assert tab_events(state, 0) == []
    assert tab_events(state, 1) == [("4", [(1, 0)])]


def test_keyscript_italian_multifret_prefix_commits_before_arrow_move() -> None:
    state = keyscript_state(
        width=30,
        height=20,
        style="italian",
        bar_width=12,
        settings_override={"italianmultifret": "on"},
    )
    right = state.keycodes.right
    press_keys(state, ["i", ",", "1", right, "2"])
    # ',1' must be canceled by the arrow; the next digit enters plain fret 2 at the new stop.
    assert tab_events(state, 0) == []
    assert tab_events(state, 1) == [("4", [(1, 2)])]
    assert state.insert_prefix == ""


def test_keyscript_movementmode_note_moves_between_notes_not_grid_cells() -> None:
    state = keyscript_state(width=30, height=20, bar_width=12)
    press_keys(state, ["i", "a", 258, "c", 259, "a", 27])
    state.cursor_onset = Fraction(0)
    state.settings["movementmode"] = "note"
    press_keys(state, ["l"])
    assert state.cursor_onset == Fraction(1, 2)
    press_keys(state, ["h"])
    assert state.cursor_onset == Fraction(0)


def test_keyscript_replace_mode_replaces_existing_cell_without_auto_advance() -> None:
    state = keyscript_state(width=24, height=20, bar_width=12)
    press_keys(state, ["i", "a", 27, "h", "R", "b"])
    assert state.mode == "replace"
    assert state.cursor_onset == Fraction(0)
    assert tab_events(state) == [("4", [(1, 1)])]


def test_keyscript_replace_mode_rejects_insert_on_empty_cell() -> None:
    state = keyscript_state(width=24, height=20, bar_width=12)
    press_keys(state, ["R", "a"])
    assert state.mode == "replace"
    assert state.cursor_onset == Fraction(0)
    assert tab_events(state) == []
    assert state.message == "No note to replace"


def test_keyscript_jk_fullscreen_alternating_bass_rows_keeps_cursor_visible_and_scrolls() -> None:
    base = piece_with_unused_then_used_bass_rows()
    piece = Piece(title="T", bars=base.bars * 10, strings=7, style="french")
    state = keyscript_state(
        piece=piece,
        width=121,
        height=39,
        strings=7,
        style="french",
        bar_width=10,
        settings_override={
            "layout": "auto",
            "justify": "smart",
            "scrollmode": "page",
            "tuning": "g2c3f3a3d4g4d2",
        },
    )
    state.cursor_bar = 1
    state.cursor_string = 6
    state.cursor_col = 0
    start_offset = state.bar_offset

    for _ in range(4):
        press_keys(state, ["J"])
        assert 0 <= state.cursor_bar < len(state.piece.bars)
        assert 0 <= state.cursor_string < state.piece.strings
        assert state.bar_offset >= 0
    assert state.bar_offset >= start_offset

    for _ in range(3):
        press_keys(state, ["K"])
        assert 0 <= state.cursor_bar < len(state.piece.bars)
        assert 0 <= state.cursor_string < state.piece.strings
        assert state.bar_offset >= 0


@pytest.mark.parametrize("justify", ["compact", "smart", "stretch"])
@pytest.mark.parametrize("beatsnap", ["off", "soft"])
def test_keyscript_playback_marker_is_monotonic_across_spacing_modes(
    justify: str,
    beatsnap: str,
) -> None:
    piece = dense_flag_alignment_piece()
    bar = piece.bars[0]
    state = keyscript_state(
        piece=piece,
        width=40,
        height=20,
        style="french",
        bar_width=max(12, len(bar.chords)),
        settings_override={
            "layout": "auto",
            "justify": justify,
            "beatsnap": beatsnap,
            "showdur": "off",
            "showspans": "off",
            "showtactus": "off",
            "showfingerings": "off",
            "showornaments": "off",
            "flagredundant": "on",
        },
    )
    state.playback_bar = 0
    cols: list[int] = []
    for playback_col in range(len(bar.chords)):
        state.playback_col = playback_col
        marker = find_marker(render_lines(state), "^")
        assert marker is not None, (justify, beatsnap, playback_col)
        cols.append(marker[1])
    assert cols == sorted(cols), (justify, beatsnap, cols)


@pytest.mark.parametrize("justify", ["compact", "smart", "stretch"])
@pytest.mark.parametrize("beatsnap", ["off", "soft"])
def test_keyscript_measure_boundary_motions_are_stable_across_spacing_modes(
    justify: str,
    beatsnap: str,
) -> None:
    state = _bar_motion_state(justify=justify, beatsnap=beatsnap)

    # Walk by bar motions: w/b step bars, $ is the last event, G and gg the last and first bar.
    state.cursor_bar = 0
    state.cursor_onset = Fraction(0)
    last = Fraction(7, 8)
    for keys, expected in (
        (["w"], (1, Fraction(0))),
        (["$"], (1, last)),
        (["w"], (2, Fraction(0))),
        (["b"], (1, Fraction(0))),
        (["G"], (3, Fraction(0))),
        (["$"], (3, last)),
        (["g", "g"], (0, Fraction(0))),
    ):
        press_keys(state, keys)
        assert (state.cursor_bar, state.cursor_onset) == expected, (justify, beatsnap, keys)
