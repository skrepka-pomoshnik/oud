from pathlib import Path

import oud.editor.navigation as nav
from oud.core.model import Bar, Chord, Note, Piece
from oud.editor.init import init_state
from oud.editor.layout import auto_system_bar_plan_with_gaps, dynamic_system_starts
from oud.editor.navigation import (
    _bar_content_width_for_cursor,
    _cursor_display_map_for_bar,
    jump_row_visual,
    move_left,
    move_left_note,
    move_right,
    move_right_note,
    move_right_visual,
)
from oud.editor.normal_actions import handle_normal
from oud.editor.state import EditorState
from tests.helpers_regression_cases import multi_bar_spacing_piece, regression_state


def _state() -> EditorState:
    piece = Piece(title="T", bars=[Bar(), Bar()], strings=6)
    state = EditorState(piece, {"style": "french"})
    state.bar_width = 4
    return state


def test_move_left_across_bars() -> None:
    state = _state()
    state.cursor_bar = 0
    state.cursor_col = 0
    move_left(state)
    assert state.cursor_bar == 0
    state.cursor_col = 2
    move_left(state)
    assert state.cursor_col == 1
    state.cursor_bar = 1
    state.cursor_col = 0
    move_left(state)
    assert state.cursor_bar == 0
    assert state.cursor_col == 3


def test_move_right_across_bars_and_extend() -> None:
    state = _state()
    state.cursor_bar = 0
    state.cursor_col = 2
    move_right(state)
    assert state.cursor_col == 3
    move_right(state)
    assert state.cursor_bar == 1
    assert state.cursor_col == 0
    state.cursor_col = 3
    move_right(state)
    assert state.cursor_bar == 2
    assert state.modified is True


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
    assert state.cursor_col == 3
    move_left_note(state)
    assert state.cursor_col == 0
    move_right_note(state)
    assert state.cursor_col == 3


def test_note_movement_uses_grid_onset_columns() -> None:
    state = _state()
    state.bar_width = 8
    state.durations[(0, 0, 0)] = 4
    state.durations[(0, 0, 2)] = 16
    state.durations[(0, 0, 4)] = 8
    state.cursor_bar = 0
    state.cursor_col = 0
    move_right_note(state)
    assert state.cursor_col == 2
    move_right_note(state)
    assert state.cursor_col == 4


def test_note_movement_crosses_bars_by_onset() -> None:
    state = _state()
    state.bar_width = 8
    state.durations[(0, 0, 6)] = 8
    state.durations[(1, 0, 1)] = 4
    state.cursor_bar = 0
    state.cursor_col = 6
    move_right_note(state)
    assert state.cursor_bar == 1
    assert state.cursor_col == 1
    move_left_note(state)
    assert state.cursor_bar == 0
    assert state.cursor_col == 6


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


def test_visual_move_right_skips_duplicate_render_column_in_lachrimae() -> None:
    root = Path(__file__).resolve().parents[1]
    state = init_state(
        str(root / "examples" / "26_lachrimae_galliard_in_G.ft3"),
        config_path="config.toml",
    )
    state.settings["layout"] = "auto"
    state.settings["justify"] = "stretch"
    state.settings["beatsnap"] = "off"
    state.settings["barpad"] = "1"
    state.screen_width = 90
    state.cursor_bar = 3
    content = _bar_content_width_for_cursor(state, 3)
    mapping = _cursor_display_map_for_bar(state, 3, content)
    dup = next((idx for idx in range(len(mapping) - 1) if mapping[idx] == mapping[idx + 1]), None)
    if dup is None:
        return
    state.cursor_col = dup
    move_right_visual(state)
    assert state.cursor_bar == 3
    assert mapping[state.cursor_col] != mapping[dup]


def test_visual_move_right_stops_on_note_inside_duplicate_render_column(
    monkeypatch,
) -> None:
    state = _state()
    state.cursor_bar = 0
    state.cursor_string = 0
    state.cursor_col = 0
    state.bar_width = 6
    state.overrides[(0, 0, 1)] = "a"

    monkeypatch.setattr(nav, "_bar_content_width_for_cursor", lambda _s, _b: 4)
    monkeypatch.setattr(nav, "_cursor_display_map_for_bar", lambda _s, _b, _c: [0, 0, 1, 2, 3, 4])

    move_right_visual(state)

    assert state.cursor_col == 1


def test_lachrimae_bar1_second_string_reaches_b_in_four_l_presses() -> None:
    root = Path(__file__).resolve().parents[1]
    state = init_state(
        str(root / "examples" / "26_lachrimae_galliard_in_G.ft3"),
        config_path="config.toml",
    )
    state.settings["layout"] = "auto"
    state.settings["justify"] = "stretch"
    state.settings["beatsnap"] = "off"
    state.settings["barpad"] = "1"
    state.screen_width = 120
    state.cursor_bar = 0
    state.cursor_string = 1
    state.cursor_col = 0
    for _ in range(4):
        handle_normal(state, ord("l"))
    # Visual movement may stop on a real note inside a duplicate render column.
    # Both raw cols 4 and 5 map to the same visible slot in this layout variant.
    assert state.cursor_col in (4, 5)


def test_jump_row_visual_keeps_nearest_visual_anchor_in_auto_mode() -> None:
    root = Path(__file__).resolve().parents[1]
    state = init_state(
        str(root / "examples" / "26_lachrimae_galliard_in_G.ft3"),
        config_path="config.toml",
    )
    state.settings["layout"] = "auto"
    state.settings["justify"] = "smart"
    state.settings["barpad"] = "1"
    state.screen_width = 120
    state.cursor_bar = 1
    state.cursor_col = 5
    prev_content = _bar_content_width_for_cursor(state, state.cursor_bar)
    prev_map = _cursor_display_map_for_bar(state, state.cursor_bar, prev_content)
    anchor = prev_map[state.cursor_col]

    jump_row_visual(state, 1)

    target_content = _bar_content_width_for_cursor(state, state.cursor_bar)
    target_map = _cursor_display_map_for_bar(state, state.cursor_bar, target_content)
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
    prev_content = _bar_content_width_for_cursor(state, prev_bar)
    prev_map = _cursor_display_map_for_bar(state, prev_bar, prev_content)
    prev_anchor = prev_map[state.cursor_col]

    jump_row_visual(state, 1)

    assert state.cursor_bar != prev_bar
    target_content = _bar_content_width_for_cursor(state, state.cursor_bar)
    target_map = _cursor_display_map_for_bar(state, state.cursor_bar, target_content)
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
