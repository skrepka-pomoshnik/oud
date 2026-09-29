from __future__ import annotations

from fractions import Fraction

from oud.editor.core.coordinates import bar_stops, stop_column
from oud.editor.core.state import EditorState
from oud.editor.navigation.motions import (
    CursorMotionTarget,
    apply_counted_visual_motion,
    apply_motion_target,
    target_advance_next_bar_home,
    target_at_column,
    target_bar_end,
    target_bar_next,
    target_bar_prev,
    target_bar_start,
    target_home_bar,
    target_jump_first_bar,
    target_jump_last_bar,
    target_jump_row_visual,
    target_move_left,
    target_move_left_note,
    target_move_right,
    target_move_right_note,
    target_step_display_row,
)
from petrucci.core.model import Bar, Chord, Note, Piece
from tests.helpers_keyscript import keyscript_state

HALF = Fraction(1, 2)
QUARTER = Fraction(1, 4)


def _chord(note_type: int, *courses: int) -> Chord:
    return Chord(note_type, False, None, [Note(course, 0, 0) for course in courses])


def _state(*bars: Bar) -> EditorState:
    piece = Piece(title="T", bars=list(bars), strings=6)
    return keyscript_state(piece=piece, width=120, settings_override={"time": "4/4"})


def _partial_and_full() -> EditorState:
    """Bar 1 holds two quarters (half full); bar 2 is full with a half and two quarters."""

    return _state(
        Bar(chords=[_chord(4, 1), _chord(4, 2)]),
        Bar(chords=[_chord(3, 1), _chord(4, 3), _chord(4, 1)]),
    )


def _at(state: EditorState, bar: int, onset: Fraction) -> EditorState:
    state.cursor_bar, state.cursor_onset = bar, onset
    return state


def test_stops_are_event_onsets_plus_the_append_slot_of_a_bar_that_is_not_full() -> None:
    state = _partial_and_full()
    assert bar_stops(state, 0) == (Fraction(0), QUARTER, HALF)
    assert bar_stops(state, 1) == (Fraction(0), HALF, Fraction(3, 4))
    assert bar_stops(_state(Bar()), 0) == (Fraction(0),)


def test_left_and_right_step_one_stop_and_cross_bars() -> None:
    state = _partial_and_full()
    assert target_move_right(_at(state, 0, QUARTER)) == CursorMotionTarget(0, HALF)
    assert target_move_right(_at(state, 0, HALF)) == CursorMotionTarget(1, Fraction(0))
    assert target_move_left(_at(state, 1, Fraction(0))) == CursorMotionTarget(0, HALF)
    assert target_move_left(_at(state, 0, Fraction(0))) == CursorMotionTarget(0, Fraction(0))


def test_moving_right_past_the_last_stop_appends_a_bar_unless_read_only() -> None:
    state = _at(_partial_and_full(), 1, Fraction(3, 4))
    assert target_move_right(state) == CursorMotionTarget(2, Fraction(0), append_bar=True)
    apply_motion_target(state, target_move_right(state))
    assert len(state.piece.bars) == 3

    read_only = _at(_partial_and_full(), 1, Fraction(3, 4))
    read_only.read_only = True
    apply_motion_target(read_only, CursorMotionTarget(2, Fraction(0), append_bar=True))
    assert len(read_only.piece.bars) == 2
    assert target_move_right(read_only) == CursorMotionTarget(1, Fraction(3, 4))


def test_counted_motion_stops_after_appending_a_bar() -> None:
    state = _partial_and_full()
    apply_counted_visual_motion(state, 1, 20)
    assert (state.cursor_bar, state.cursor_onset, len(state.piece.bars)) == (2, Fraction(0), 3)

    apply_counted_visual_motion(state, -1, 2)
    assert (state.cursor_bar, state.cursor_onset) == (1, HALF)


def test_bar_motions_land_on_first_and_last_events() -> None:
    state = _at(_partial_and_full(), 1, HALF)
    assert target_bar_start(state) == CursorMotionTarget(1, Fraction(0))
    assert target_bar_end(state) == CursorMotionTarget(1, Fraction(3, 4))
    assert target_bar_end(_at(state, 0, Fraction(0))) == CursorMotionTarget(0, QUARTER)
    assert target_bar_prev(_at(state, 1, HALF)) == CursorMotionTarget(0, Fraction(0))
    assert target_bar_next(state, 5) == CursorMotionTarget(1, Fraction(0))
    assert target_jump_first_bar(state) == CursorMotionTarget(0, Fraction(0))
    assert target_jump_last_bar(state) == CursorMotionTarget(1, Fraction(0))
    assert target_home_bar(state, 9) == CursorMotionTarget(1, Fraction(0))
    assert target_bar_end(_at(_state(Bar()), 0, Fraction(0))) == CursorMotionTarget(0, Fraction(0))


def test_advance_to_next_bar_appends_at_the_end() -> None:
    state = _at(_partial_and_full(), 1, HALF)
    assert target_advance_next_bar_home(state) == CursorMotionTarget(2, Fraction(0), append_bar=True)
    assert target_advance_next_bar_home(_at(state, 0, QUARTER)) == CursorMotionTarget(1, Fraction(0))


def test_note_motions_follow_the_cursor_course() -> None:
    state = _at(_partial_and_full(), 0, Fraction(0))
    assert target_move_right_note(state) == CursorMotionTarget(1, Fraction(0))
    assert target_move_right_note(_at(state, 1, Fraction(0))) == CursorMotionTarget(1, Fraction(3, 4))
    assert target_move_left_note(_at(state, 1, Fraction(0))) == CursorMotionTarget(0, Fraction(0))

    state.cursor_string = 2
    assert target_move_right_note(_at(state, 1, Fraction(0))) == CursorMotionTarget(1, HALF)


def test_display_row_steps_keep_the_onset() -> None:
    state = _at(_partial_and_full(), 1, HALF)
    assert target_step_display_row(state, 1) == CursorMotionTarget(1, HALF, cursor_string=1)


def test_column_targets_snap_to_the_stop_drawn_at_or_before_the_column() -> None:
    state = _partial_and_full()
    second = stop_column(state, 0, QUARTER)
    assert second > 0
    assert target_at_column(state, 0, second) == CursorMotionTarget(0, QUARTER)
    assert target_at_column(state, 0, second - 1) == CursorMotionTarget(0, Fraction(0))
    assert target_at_column(state, 0, 99) == CursorMotionTarget(0, HALF)


def test_row_jumps_land_on_a_stop_of_the_target_system() -> None:
    bars = [Bar(chords=[_chord(4, 1) for _ in range(4)]) for _ in range(12)]
    state = keyscript_state(piece=Piece(title="T", bars=bars, strings=6), width=60, settings_override={"time": "4/4"})
    state.cursor_onset = HALF

    target = target_jump_row_visual(state, 1)

    assert target.bar > 0
    assert target.onset in bar_stops(state, target.bar)
