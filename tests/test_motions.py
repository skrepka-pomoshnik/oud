from oud.editor.core.state import EditorState
from oud.editor.navigation.motions import (
    CursorMotionTarget,
    apply_counted_visual_motion,
    apply_motion_target,
    target_advance_next_bar_home,
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
    target_move_left_visual,
    target_move_right,
    target_move_right_note,
    target_move_right_visual,
    target_snap_previous_time_slot_if_needed,
    target_snap_to_chord_slot,
    target_step_display_row,
)
from oud.editor.navigation.steps import jump_row_visual, move_left_note, move_right_note
from petrucci.core.model import Bar, Piece
from tests.helpers_regression_cases import multi_bar_spacing_piece, regression_state


def _state() -> EditorState:
    piece = Piece(title="T", bars=[Bar(), Bar()], strings=6)
    state = EditorState(piece, {"style": "french"})
    state.bar_width = 4
    return state


def test_target_move_left_within_bar() -> None:
    state = _state()
    state.cursor_bar = 1
    state.cursor_col = 2
    target = target_move_left(state)
    assert (target.bar, target.col, target.append_bar) == (1, 1, False)


def test_target_move_left_wraps_to_previous_bar() -> None:
    state = _state()
    state.cursor_bar = 1
    state.cursor_col = 0
    target = target_move_left(state)
    assert (target.bar, target.col, target.append_bar) == (0, 3, False)


def test_target_move_left_stays_at_origin() -> None:
    state = _state()
    state.cursor_bar = 0
    state.cursor_col = 0
    target = target_move_left(state)
    assert (target.bar, target.col, target.append_bar) == (0, 0, False)


def test_target_move_right_within_bar() -> None:
    state = _state()
    state.cursor_bar = 0
    state.cursor_col = 1
    target = target_move_right(state)
    assert (target.bar, target.col, target.append_bar) == (0, 2, False)


def test_target_move_right_wraps_to_next_bar() -> None:
    state = _state()
    state.cursor_bar = 0
    state.cursor_col = 3
    target = target_move_right(state)
    assert (target.bar, target.col, target.append_bar) == (1, 0, False)


def test_target_move_right_requests_append_at_end() -> None:
    state = _state()
    state.cursor_bar = 1
    state.cursor_col = 3
    target = target_move_right(state)
    assert (target.bar, target.col, target.append_bar) == (2, 0, True)


def test_read_only_motion_cannot_append_a_bar() -> None:
    state = _state()
    state.read_only = True
    state.cursor_bar = 1
    state.cursor_col = 3

    target = target_move_right(state)
    apply_motion_target(state, CursorMotionTarget(2, 0, append_bar=True))

    assert target == CursorMotionTarget(1, 3)
    assert len(state.piece.bars) == 2
    assert (state.cursor_bar, state.cursor_col) == (1, 3)
    assert state.modified is False


def test_counted_visual_motion_reuses_bar_geometry(monkeypatch) -> None:
    state = _state()
    state.cursor_col = 0
    calls = 0

    def content_width(_state: EditorState, _bar_index: int) -> int:
        nonlocal calls
        calls += 1
        return 4

    monkeypatch.setattr("oud.editor.navigation.motions.bar_content_width_for_cursor", content_width)
    monkeypatch.setattr(
        "oud.editor.navigation.motions.cursor_display_map_for_bar",
        lambda _state, _bar_index, _content_width: [0, 1, 2, 3],
    )

    apply_counted_visual_motion(state, 1, 3)

    assert calls == 1
    assert (state.cursor_bar, state.cursor_col) == (0, 3)


def test_target_home_bar_clamps_and_homes_column() -> None:
    state = _state()
    state.cursor_col = 3
    target = target_home_bar(state, 99)
    assert (target.bar, target.col, target.append_bar) == (1, 0, False)


def test_target_advance_next_bar_home_requests_append_at_end() -> None:
    state = _state()
    state.cursor_bar = 1
    state.cursor_col = 3
    target = target_advance_next_bar_home(state)
    assert (target.bar, target.col, target.append_bar) == (2, 0, True)


def test_target_bar_navigation_uses_semantic_first_and_last_note_cols() -> None:
    state = _state()
    state.piece.bars = [Bar(), Bar(), Bar(), Bar()]
    state.bar_width = 8
    # Bar starts/ends should use actual note onset columns when present.
    state.durations[(0, 0, 2)] = 4
    state.overrides[(0, 0, 2)] = "a"
    state.durations[(0, 0, 5)] = 4
    state.overrides[(0, 0, 5)] = "b"
    state.durations[(1, 0, 1)] = 4
    state.overrides[(1, 0, 1)] = "a"
    state.durations[(1, 0, 6)] = 4
    state.overrides[(1, 0, 6)] = "b"
    state.durations[(2, 0, 0)] = 4
    state.overrides[(2, 0, 0)] = "a"
    state.durations[(2, 0, 4)] = 4
    state.overrides[(2, 0, 4)] = "b"
    state.durations[(3, 0, 3)] = 4
    state.overrides[(3, 0, 3)] = "a"
    state.durations[(3, 0, 7)] = 4
    state.overrides[(3, 0, 7)] = "b"

    state.cursor_bar = 0
    state.cursor_col = 0
    assert (target_bar_next(state).bar, target_bar_next(state).col) == (1, 1)

    state.cursor_bar = 2
    state.cursor_col = 7
    assert (target_bar_prev(state).bar, target_bar_prev(state).col) == (1, 1)

    state.cursor_bar = 1
    state.cursor_col = 4
    assert (target_bar_start(state).bar, target_bar_start(state).col) == (1, 1)
    assert (target_bar_end(state).bar, target_bar_end(state).col) == (1, 6)

    assert (target_jump_first_bar(state).bar, target_jump_first_bar(state).col) == (0, 2)
    assert (target_jump_last_bar(state).bar, target_jump_last_bar(state).col) == (3, 3)


def test_target_bar_navigation_falls_back_when_bar_has_no_notes() -> None:
    state = _state()
    state.piece.bars = [Bar(), Bar()]
    state.bar_width = 8
    state.cursor_bar = 1
    state.cursor_col = 4
    assert (target_bar_start(state).bar, target_bar_start(state).col) == (1, 0)
    assert (target_bar_end(state).bar, target_bar_end(state).col) == (1, 7)


def test_target_jump_row_visual_matches_wrapper_on_synthetic_auto_case() -> None:
    state1 = regression_state(multi_bar_spacing_piece(), width=64, bar_width=12, justify="smart")
    state1.settings["layout"] = "auto"
    state1.settings["beatsnap"] = "soft"
    state1.cursor_bar = 1
    state1.cursor_col = 5
    state1.cursor_string = 0
    state2 = regression_state(multi_bar_spacing_piece(), width=64, bar_width=12, justify="smart")
    state2.settings["layout"] = "auto"
    state2.settings["beatsnap"] = "soft"
    state2.cursor_bar = 1
    state2.cursor_col = 5
    state2.cursor_string = 0

    target = target_jump_row_visual(state1, 1)
    jump_row_visual(state2, 1)

    assert (target.bar, target.col, target.cursor_string) == (
        state2.cursor_bar,
        state2.cursor_col,
        state2.cursor_string,
    )


def test_target_move_right_visual_matches_wrapper_duplicate_column_case(
    monkeypatch,
) -> None:
    state1 = _state()
    state1.cursor_bar = 0
    state1.cursor_string = 0
    state1.cursor_col = 0
    state1.bar_width = 6
    state1.overrides[(0, 0, 1)] = "a"
    state2 = _state()
    state2.cursor_bar = 0
    state2.cursor_string = 0
    state2.cursor_col = 0
    state2.bar_width = 6
    state2.overrides[(0, 0, 1)] = "a"

    monkeypatch.setattr("oud.editor.navigation.motions.bar_content_width_for_cursor", lambda _s, _b: 4)
    monkeypatch.setattr(
        "oud.editor.navigation.motions.cursor_display_map_for_bar",
        lambda _s, _b, _c: [0, 0, 1, 2, 3, 4],
    )

    target = target_move_right_visual(state1)
    from oud.editor.navigation.steps import move_right_visual  # noqa: PLC0415

    move_right_visual(state2)

    assert (target.bar, target.col, target.append_bar) == (state2.cursor_bar, state2.cursor_col, False)


def test_target_move_left_visual_matches_wrapper_on_duplicate_column_case(
    monkeypatch,
) -> None:
    state1 = _state()
    state1.cursor_bar = 0
    state1.cursor_string = 0
    state1.cursor_col = 2
    state1.bar_width = 6
    state2 = _state()
    state2.cursor_bar = 0
    state2.cursor_string = 0
    state2.cursor_col = 2
    state2.bar_width = 6

    monkeypatch.setattr("oud.editor.navigation.motions.bar_content_width_for_cursor", lambda _s, _b: 4)
    monkeypatch.setattr(
        "oud.editor.navigation.motions.cursor_display_map_for_bar",
        lambda _s, _b, _c: [0, 0, 1, 2, 3, 4],
    )

    target = target_move_left_visual(state1)
    from oud.editor.navigation.steps import move_left_visual  # noqa: PLC0415

    move_left_visual(state2)

    assert (target.bar, target.col, target.append_bar) == (state2.cursor_bar, state2.cursor_col, False)


def test_target_move_right_note_matches_wrapper_on_grid_onsets() -> None:
    state1 = _state()
    state1.bar_width = 8
    state1.durations[(0, 0, 0)] = 4
    state1.durations[(0, 0, 2)] = 16
    state1.durations[(0, 0, 4)] = 8
    state1.cursor_bar = 0
    state1.cursor_col = 0
    state2 = _state()
    state2.bar_width = 8
    state2.durations[(0, 0, 0)] = 4
    state2.durations[(0, 0, 2)] = 16
    state2.durations[(0, 0, 4)] = 8
    state2.cursor_bar = 0
    state2.cursor_col = 0

    target = target_move_right_note(state1)
    move_right_note(state2)

    assert (target.bar, target.col, target.append_bar) == (state2.cursor_bar, state2.cursor_col, False)


def test_target_move_left_note_matches_wrapper_across_bar_boundary() -> None:
    state1 = _state()
    state1.bar_width = 8
    state1.durations[(0, 0, 6)] = 8
    state1.durations[(1, 0, 1)] = 4
    state1.cursor_bar = 1
    state1.cursor_col = 1
    state2 = _state()
    state2.bar_width = 8
    state2.durations[(0, 0, 6)] = 8
    state2.durations[(1, 0, 1)] = 4
    state2.cursor_bar = 1
    state2.cursor_col = 1

    target = target_move_left_note(state1)
    move_left_note(state2)

    assert (target.bar, target.col, target.append_bar) == (state2.cursor_bar, state2.cursor_col, False)


def test_target_step_display_row_changes_only_display_row() -> None:
    state = _state()
    state.cursor_bar = 1
    state.cursor_col = 2
    state.cursor_string = 3
    target = target_step_display_row(state, -1)
    assert (target.bar, target.col, target.cursor_string, target.append_bar) == (1, 2, 2, False)


def test_target_snap_previous_time_slot_if_needed_moves_left_only_for_layering() -> None:
    state = _state()
    state.piece.strings = 6
    state.bar_width = 8
    state.cursor_bar = 0
    state.cursor_col = 3
    state.cursor_string = 1
    state.overrides[(0, 0, 2)] = "a"
    state.durations[(0, 0, 2)] = 4
    target = target_snap_previous_time_slot_if_needed(state)
    assert (target.bar, target.col) == (0, 2)

    # Same-string previous event should keep normal left-to-right typing.
    state.cursor_string = 0
    target_same_string = target_snap_previous_time_slot_if_needed(state)
    assert (target_same_string.bar, target_same_string.col) == (0, 3)


def test_target_snap_to_chord_slot_chooses_nearest_chord_position() -> None:
    state = _state()
    state.bar_width = 8
    bar = Bar()
    # Three chord onsets; cursor starts between them.
    from petrucci.core.model import Chord, Note  # noqa: PLC0415

    bar.chords = [
        Chord(note_type=6, dotted=False, grid="", notes=[Note(raw_pos=0, string=1, fret=0)]),
        Chord(note_type=6, dotted=False, grid="", notes=[Note(raw_pos=0, string=1, fret=1)]),
        Chord(note_type=6, dotted=False, grid="", notes=[Note(raw_pos=0, string=1, fret=2)]),
    ]
    state.piece.bars[0] = bar
    from petrucci.rendering.primitives.utils import chord_positions  # noqa: PLC0415

    slots = [col for (col, _denom, _dot) in chord_positions(bar, state.bar_width, default_duration=4)]
    between = next((c for c in range(state.bar_width) if c not in slots), None)
    assert between is not None
    state.cursor_bar = 0
    state.cursor_col = between
    target = target_snap_to_chord_slot(state)
    assert target.bar == 0
    assert target.col in set(slots)
    assert target.col != between
