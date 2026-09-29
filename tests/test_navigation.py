from pathlib import Path

from oud.editor.core.coordinates import cursor_event
from oud.editor.core.state import EditorState
from oud.editor.interaction.normal.actions import handle_normal
from oud.editor.navigation.cursor_map import (
    bar_content_width_for_cursor,
    cursor_display_map_for_bar,
)
from oud.editor.navigation.layout import auto_system_bar_plan_with_gaps, dynamic_system_starts
from oud.editor.navigation.steps import (
    jump_row_visual,
    move_left_note,
    move_right_note,
    move_right_visual,
)
from oud.editor.services.bootstrap import init_state
from petrucci.core.model import Bar, Chord, Note, Piece
from tests.helpers_ft3 import write_galliard
from tests.helpers_regression_cases import multi_bar_spacing_piece, regression_state


def _state() -> EditorState:
    piece = Piece(title="T", bars=[Bar(), Bar()], strings=6)
    state = EditorState(piece, {"style": "french"})
    state.bar_width = 4
    return state


def test_note_movement_uses_chord_positions() -> None:
    state = _state()
    state.bar_width = 8
    state.piece.bars[0] = Bar(
        chords=[
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
            Chord(note_type=6, dotted=False, grid=None, notes=[Note(1, 1, 0)]),
            Chord(note_type=5, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
        ],
    )
    state.cursor_bar = 0
    state.cursor_col = 5
    move_left_note(state)
    assert state.cursor_col == 4
    move_left_note(state)
    assert state.cursor_col == 0
    move_right_note(state)
    assert state.cursor_col == 4


def test_note_movement_prefers_notes_on_current_string() -> None:
    state = _state()
    state.bar_width = 8
    state.piece.bars[0] = Bar(
        chords=[
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 1, 0)]),
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
        ],
    )
    state.cursor_bar = 0
    state.cursor_string = 0
    state.cursor_col = 0
    move_right_note(state)
    assert state.cursor_col == 4


def test_visual_move_right_skips_duplicate_render_column_in_dense_bar(tmp_path: Path) -> None:
    state = init_state(str(write_galliard(tmp_path)), config_path="config.toml")
    state.settings["layout"] = "auto"
    state.settings["justify"] = "packed"
    state.settings["beatsnap"] = "off"
    state.settings["barpad"] = "1"
    state.screen_width = 20  # a narrow, packed terminal draws neighbouring columns in one cell
    state.cursor_bar = 1
    content = bar_content_width_for_cursor(state, 1)
    mapping = cursor_display_map_for_bar(state, 1, content)
    dup = next((idx for idx in range(len(mapping) - 1) if mapping[idx] == mapping[idx + 1]), None)
    assert dup is not None
    state.cursor_col = dup
    move_right_visual(state)
    assert state.cursor_bar == 1
    assert mapping[state.cursor_col] != mapping[dup]


def test_four_l_presses_step_four_events(tmp_path: Path) -> None:
    state = init_state(str(write_galliard(tmp_path)), config_path="config.toml")
    state.settings["layout"] = "auto"
    state.settings["justify"] = "stretch"
    state.settings["beatsnap"] = "off"
    state.settings["barpad"] = "1"
    state.screen_width = 120
    state.cursor_bar = 1
    state.cursor_string = 1
    state.cursor_col = 0
    for _ in range(4):
        handle_normal(state, ord("l"))
    assert cursor_event(state) == 4


def test_jump_row_visual_keeps_nearest_visual_anchor_in_auto_mode(tmp_path: Path) -> None:
    state = init_state(str(write_galliard(tmp_path)), config_path="config.toml")
    state.settings["layout"] = "auto"
    state.settings["justify"] = "smart"
    state.settings["barpad"] = "1"
    state.screen_width = 120
    state.cursor_bar = 1
    state.cursor_col = 5
    prev_content = bar_content_width_for_cursor(state, state.cursor_bar)
    prev_map = cursor_display_map_for_bar(state, state.cursor_bar, prev_content)
    anchor = prev_map[state.cursor_col]

    jump_row_visual(state, 1)

    target_content = bar_content_width_for_cursor(state, state.cursor_bar)
    target_map = cursor_display_map_for_bar(state, state.cursor_bar, target_content)
    current = target_map[state.cursor_col]
    best = min(abs(value - anchor) for value in target_map)
    assert abs(current - anchor) == best


def test_jump_row_visual_auto_uses_cursor_visual_x_for_target_bar_selection_synthetic() -> None:
    state = regression_state(multi_bar_spacing_piece(), justify="stretch", width=36, bar_width=12)
    state.settings["layout"] = "auto"
    state.settings["barpad"] = "1"
    state.cursor_bar = 1
    state.cursor_col = 10
    prev_bar = state.cursor_bar
    prev_content = bar_content_width_for_cursor(state, prev_bar)
    prev_map = cursor_display_map_for_bar(state, prev_bar, prev_content)
    prev_anchor = prev_map[state.cursor_col]

    jump_row_visual(state, 1)

    assert state.cursor_bar != prev_bar
    target_content = bar_content_width_for_cursor(state, state.cursor_bar)
    target_map = cursor_display_map_for_bar(state, state.cursor_bar, target_content)
    current = target_map[state.cursor_col]
    best = min(abs(value - prev_anchor) for value in target_map)
    assert abs(current - prev_anchor) == best


def test_dynamic_system_starts_matches_final_auto_plan_sequence_synthetic() -> None:
    state = regression_state(multi_bar_spacing_piece(), justify="smart", width=64, bar_width=12)
    starts = dynamic_system_starts(state, state.screen_width)
    expected = [0]
    current = 0
    while current < len(state.piece.bars):
        inds, _widths, _gaps = auto_system_bar_plan_with_gaps(state, current, state.screen_width)
        if not inds:
            break
        nxt = inds[-1] + 1
        if nxt >= len(state.piece.bars):
            break
        expected.append(nxt)
        current = nxt
    assert starts == expected


def test_jump_row_visual_uses_same_target_bar_with_beatsnap_off_and_soft() -> None:
    outcomes: list[tuple[str, int, int]] = []
    for mode in ("off", "soft"):
        state = regression_state(multi_bar_spacing_piece(), width=64, bar_width=12, justify="smart")
        state.settings["layout"] = "auto"
        state.settings["beatsnap"] = mode
        state.cursor_bar = 1
        state.cursor_col = 5
        state.cursor_string = 0
        jump_row_visual(state, 1)
        outcomes.append((mode, state.cursor_bar, state.cursor_col))

    off_bar = outcomes[0][1]
    soft_bar = outcomes[1][1]
    assert off_bar == soft_bar == 3
    # Column may differ slightly, but both should land on valid cells.
    assert all(0 <= col < 12 for _mode, _bar, col in outcomes)


def test_cursor_display_map_for_bar_is_monotonic_with_beatsnap_off_and_soft() -> None:
    checks: list[tuple[str, list[int]]] = []
    for mode in ("off", "soft"):
        state = regression_state(multi_bar_spacing_piece(), width=64, bar_width=12, justify="smart")
        state.settings["layout"] = "auto"
        state.settings["beatsnap"] = mode
        content = bar_content_width_for_cursor(state, 1)
        mapping = cursor_display_map_for_bar(state, 1, content)
        checks.append((mode, mapping))

    for _mode, mapping in checks:
        assert len(mapping) == 12
        assert mapping == sorted(mapping)
        assert mapping[0] >= 0
        assert mapping[-1] >= mapping[0]
    # Beat snapping should not collapse the entire map to one column.
    assert len(set(checks[0][1])) > 1
    assert len(set(checks[1][1])) > 1
