from __future__ import annotations

import pytest

from oud.editor.state import EditorState
from petrucci.model import Bar, Piece
from tests.helpers_keyscript import (
    collect_cursor_cols_after_key,
    find_marker,
    first_flag_and_top_note_x,
    keyscript_state,
    press_keys,
    render_lines,
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
    piece = Piece(title="T", bars=[Bar() for _ in range(4)], strings=6, style="french")
    state = keyscript_state(
        piece=piece,
        width=60,
        height=20,
        bar_width=8,
        settings_override={
            "layout": "auto",
            "justify": justify,
            "beatsnap": beatsnap,
        },
    )
    # Semantic note columns per bar: starts=[2,1,0,3], ends=[5,6,4,7]
    for bar_idx, cols in {0: (2, 5), 1: (1, 6), 2: (0, 4), 3: (3, 7)}.items():
        for col in cols:
            state.durations[(bar_idx, 0, col)] = 4
            state.overrides[(bar_idx, 0, col)] = "a"
    return state


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
        settings_override={"justify": justify, "beatsnap": beatsnap},
    )
    press_keys(state, ["i", "a", "a", "a", "a", 27])
    cols = collect_cursor_cols_after_key(state, "l", 10)
    # The filled bar and following empty bar both retain the configured grid,
    # independent of justification mode.
    assert cols[:8] == [5, 6, 7, 8, 9, 10, 11, 0], (justify, beatsnap)
    assert cols[8:] == [1, 2], (justify, beatsnap)


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
    first_flag_x: int | None = None
    for _ in range(4):
        press_keys(state, ["a"])
        lines = render_lines(state, width=28, height=20)
        flag_x, note_x = first_flag_and_top_note_x(lines)
        assert flag_x is not None
        assert note_x is not None
        if first_flag_x is None:
            first_flag_x = flag_x
        assert flag_x == first_flag_x, (justify, beatsnap)
        assert flag_x == note_x, (justify, beatsnap)


def test_keyscript_french_bass_slash_prefix_commits_before_arrow_move() -> None:
    state = keyscript_state(width=30, height=20, strings=7, style="french", bar_width=12)
    right = state.keycodes.right
    press_keys(state, ["i", "/", right, "a"])
    # Prefix must be canceled by movement; note should insert on current row/column, not bass course.
    assert state.overrides.get((0, 0, 1)) == "a"
    assert not any(key[1] == 6 for key in state.overrides), state.overrides


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
    # ',1' must be canceled by the arrow; next digit inserts plain fret 2 at the new column.
    assert state.overrides.get((0, 0, 1)) == "2"
    assert (0, 0, 0) not in state.overrides
    assert state.insert_prefix == ""


def test_keyscript_movementmode_note_moves_between_notes_not_grid_cells() -> None:
    state = keyscript_state(width=30, height=20, bar_width=12)
    press_keys(state, ["i", "a"])
    state.cursor_col = 3
    press_keys(state, ["a", 27])
    state.cursor_col = 0
    state.settings["movementmode"] = "note"
    press_keys(state, ["l"])
    assert state.cursor_col == 3
    press_keys(state, ["h"])
    assert state.cursor_col == 0


def test_keyscript_replace_mode_hjkl_move_instead_of_inserting_frets() -> None:
    state = keyscript_state(width=24, height=20, bar_width=12)
    press_keys(state, ["i", "a", 27])
    assert state.overrides.get((0, 0, 0)) == "a"
    assert state.cursor_col == 1
    press_keys(state, ["h", "R"])
    assert state.mode == "replace"
    press_keys(state, ["l"])
    assert state.cursor_col == 1
    assert state.overrides.get((0, 0, 0)) == "a"
    assert (0, 0, 1) not in state.overrides


def test_keyscript_replace_mode_replaces_existing_cell_without_auto_advance() -> None:
    state = keyscript_state(width=24, height=20, bar_width=12)
    press_keys(state, ["i", "a", 27, "h", "R", "b"])
    assert state.mode == "replace"
    assert state.cursor_col == 0
    assert state.overrides.get((0, 0, 0)) == "b"


def test_keyscript_replace_mode_rejects_insert_on_empty_cell() -> None:
    state = keyscript_state(width=24, height=20, bar_width=12)
    press_keys(state, ["R", "a"])
    assert state.mode == "replace"
    assert state.cursor_col == 0
    assert state.overrides == {}
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

    # Start at bar 0, then walk by semantic bar motions.
    state.cursor_bar = 0
    state.cursor_col = 0
    press_keys(state, ["w"])
    assert (state.cursor_bar, state.cursor_col) == (1, 1), (justify, beatsnap)

    press_keys(state, ["$"])
    assert (state.cursor_bar, state.cursor_col) == (1, 6), (justify, beatsnap)

    press_keys(state, ["w"])
    assert (state.cursor_bar, state.cursor_col) == (2, 0), (justify, beatsnap)

    press_keys(state, ["b"])
    assert (state.cursor_bar, state.cursor_col) == (1, 1), (justify, beatsnap)

    press_keys(state, ["G"])
    assert (state.cursor_bar, state.cursor_col) == (3, 3), (justify, beatsnap)

    press_keys(state, ["$"])
    assert (state.cursor_bar, state.cursor_col) == (3, 7), (justify, beatsnap)

    press_keys(state, ["g", "g"])
    assert (state.cursor_bar, state.cursor_col) == (0, 2), (justify, beatsnap)
