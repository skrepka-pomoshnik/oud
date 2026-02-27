from oud.core.model import Bar, Piece
from oud.editor.normal_actions import handle_normal
from oud.editor.state import EditorState
from oud.editor.undo_ops import undo


def _state() -> EditorState:
    piece = Piece(title="T", bars=[Bar() for _ in range(8)], strings=6)
    settings = {
        "style": "french",
        "keys": "vim+arrows",
        "barsperline": "3",
        "maxbars": "0",
        "linelen": "0",
        "bargap": "1",
        "layout": "packed",
    }
    state = EditorState(piece, settings)
    state.screen_width = 120
    state.bar_width = 8
    return state


def test_upper_jumps_to_same_offset_in_next_system() -> None:
    state = _state()
    state.cursor_bar = 1
    state.cursor_col = 5
    handle_normal(state, ord("J"))
    assert state.cursor_bar == 4
    assert state.cursor_col == 5


def test_upper_k_jumps_to_same_offset_in_previous_system() -> None:
    state = _state()
    state.cursor_bar = 4
    state.cursor_col = 3
    handle_normal(state, ord("K"))
    assert state.cursor_bar == 1
    assert state.cursor_col == 3


def test_upper_j_clamps_on_short_last_system() -> None:
    state = _state()
    state.cursor_bar = 2
    handle_normal(state, ord("J"))
    handle_normal(state, ord("J"))
    # 8 bars with 3-per-line => rows [0,1,2],[3,4,5],[6,7].
    assert state.cursor_bar == 7


def test_hl_moves_cell_by_cell_not_note_onset() -> None:
    state = _state()
    state.cursor_bar = 0
    state.cursor_col = 0
    state.durations[(0, 0, 2)] = 16
    state.overrides[(0, 0, 2)] = "a"
    handle_normal(state, ord("l"))
    assert state.cursor_col == 1
    handle_normal(state, ord("h"))
    assert state.cursor_col == 0


def test_hl_skips_only_barline_between_bars() -> None:
    state = _state()
    state.cursor_bar = 0
    state.cursor_col = state.bar_width - 1
    handle_normal(state, ord("l"))
    assert state.cursor_bar == 1
    assert state.cursor_col == 0
    handle_normal(state, ord("h"))
    assert state.cursor_bar == 0
    assert state.cursor_col == state.bar_width - 1


def test_hl_auto_mode_advances_visible_step_without_double_press() -> None:
    state = _state()
    state.settings["layout"] = "auto"
    state.settings["justify"] = "compact"
    state.settings["barpad"] = "1"
    state.bar_width = 12
    state.cursor_bar = 0
    state.cursor_col = 0
    start = (state.cursor_bar, state.cursor_col)
    handle_normal(state, ord("l"))
    first = (state.cursor_bar, state.cursor_col)
    assert first != start
    handle_normal(state, ord("l"))
    second = (state.cursor_bar, state.cursor_col)
    assert second != first


def test_jk_clamp_to_visible_string_bounds() -> None:
    state = _state()
    state.cursor_string = 0
    handle_normal(state, ord("k"))
    assert state.cursor_string == 0
    state.cursor_string = state.piece.strings - 1
    handle_normal(state, ord("j"))
    assert state.cursor_string == state.piece.strings - 1


def test_gi_opens_info_mode() -> None:
    state = _state()
    state.mode = "insert"
    state.insert_prefix = "/"
    state.replace_once = True
    handle_normal(state, ord("g"))
    assert state.pending_key == "g"
    handle_normal(state, ord("i"))
    assert state.mode == "info"
    assert state.insert_prefix == ""
    assert state.replace_once is False


def test_gh_opens_help_mode() -> None:
    state = _state()
    state.mode = "insert"
    state.insert_prefix = ","
    state.replace_once = True
    handle_normal(state, ord("g"))
    handle_normal(state, ord("h"))
    assert state.mode == "help"
    assert state.insert_prefix == ""
    assert state.replace_once is False


def test_gr_reports_when_no_file_or_unsaved() -> None:
    state = _state()
    handle_normal(state, ord("g"))
    handle_normal(state, ord("r"))
    assert state.message == "No file to reload"

    state = _state()
    state.path = "x.ft3"
    state.modified = True
    handle_normal(state, ord("g"))
    handle_normal(state, ord("r"))
    assert "Unsaved changes" in state.message


def test_counted_yy_and_p_pastes_multiple_bars() -> None:
    state = _state()
    state.overrides[(0, 0, 0)] = "a"
    state.overrides[(1, 0, 1)] = "b"
    state.overrides[(2, 0, 2)] = "c"

    handle_normal(state, ord("3"))
    handle_normal(state, ord("y"))
    handle_normal(state, ord("y"))
    assert state.message == "Bars yanked: 3"
    assert state.yanked_bars is not None
    assert len(state.yanked_bars) == 3

    handle_normal(state, ord("p"))
    assert len(state.piece.bars) == 11
    assert state.overrides[(1, 0, 0)] == "a"
    assert state.overrides[(2, 0, 1)] == "b"
    assert state.overrides[(3, 0, 2)] == "c"


def test_counted_x_is_single_grouped_undo() -> None:
    state = _state()
    state.overrides[(0, 0, 0)] = "a"
    state.overrides[(0, 0, 1)] = "b"
    state.overrides[(0, 0, 2)] = "c"
    state.durations[(0, 0, 0)] = 4
    state.durations[(0, 0, 1)] = 4
    state.durations[(0, 0, 2)] = 4
    handle_normal(state, ord("3"))
    handle_normal(state, ord("x"))
    assert (0, 0, 0) not in state.overrides
    assert (0, 0, 1) not in state.overrides
    assert (0, 0, 2) not in state.overrides
    assert len(state.undo_stack) == 1
    assert state.undo_stack[-1].kind == "group"
    undo(state, config_path=state.config_path)
    assert state.overrides[(0, 0, 0)] == "a"
    assert state.overrides[(0, 0, 1)] == "b"
    assert state.overrides[(0, 0, 2)] == "c"


def test_read_only_blocks_insert_and_delete() -> None:
    state = _state()
    state.read_only = True
    state.overrides[(0, 0, 0)] = "a"
    handle_normal(state, ord("i"))
    assert state.mode == "normal"
    assert "Read-only" in state.message
    handle_normal(state, ord("x"))
    assert state.overrides[(0, 0, 0)] == "a"


def test_visual_mode_yanks_selected_rows_slice_with_v() -> None:
    state = _state()
    state.bar_width = 8
    state.cursor_bar = 0
    state.cursor_string = 0
    state.cursor_col = 1
    state.overrides[(0, 0, 1)] = "a"
    state.overrides[(0, 1, 2)] = "b"

    handle_normal(state, ord("v"))
    assert state.mode == "visual"
    handle_normal(state, ord("j"))
    handle_normal(state, ord("l"))
    handle_normal(state, ord("y"))

    assert state.mode == "normal"
    assert state.yanked_rows is not None
    assert len(state.yanked_rows) == 2
    snippets = [snippet for (_bar, _row, snippet) in state.yanked_rows]
    assert any("a" in snippet for snippet in snippets)
    assert any("b" in snippet for snippet in snippets)


def test_visual_line_mode_yanks_full_row_block_with_V() -> None:
    state = _state()
    state.bar_width = 8
    state.cursor_bar = 0
    state.cursor_string = 0
    state.cursor_col = 1
    state.overrides[(0, 0, 1)] = "a"
    state.overrides[(0, 1, 2)] = "b"
    state.overrides[(0, 2, 3)] = "c"

    handle_normal(state, ord("V"))
    assert state.mode == "visual_line"
    handle_normal(state, ord("j"))
    handle_normal(state, ord("j"))
    handle_normal(state, ord("y"))

    assert state.mode == "normal"
    assert state.yanked_rows is not None
    assert len(state.yanked_rows) == 3
    assert all(len(snippet) == state.bar_width for (_bar, _row, snippet) in state.yanked_rows)
