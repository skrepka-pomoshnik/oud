from oud.core.model import Bar, Piece
from oud.editor.normal_actions import handle_normal
from oud.editor.state import EditorState
from oud.tui.viewport import ensure_cursor_visible
from tests.helpers_regression_cases import multi_bar_spacing_piece, piece_with_unused_then_used_bass_rows, regression_state


def _state(bars: int = 40) -> EditorState:
    piece = Piece(title="T", bars=[Bar() for _ in range(bars)], strings=6)
    settings = {
        "style": "french",
        "layout": "packed",
        "barsperline": "2",
        "bargap": "1",
        "showdur": "off",
        "showextras": "off",
        "showtactus": "off",
        "flagstems": "single",
    }
    state = EditorState(piece, settings)
    state.screen_width = 80
    state.screen_height = 40
    state.bar_width = 8
    return state


def test_ensure_cursor_visible_smooth_scrolls_minimally() -> None:
    state = _state()
    state.settings["scrollmode"] = "smooth"
    state.bar_offset = 0
    state.cursor_bar = 8  # row index 4 with 2 bars/row
    ensure_cursor_visible(state, state.screen_width, state.screen_height)
    assert state.bar_offset == 2


def test_ensure_cursor_visible_page_scrolls_by_page_rows() -> None:
    state = _state()
    state.settings["scrollmode"] = "page"
    state.bar_offset = 0
    state.cursor_bar = 8  # row index 4 with 2 bars/row
    ensure_cursor_visible(state, state.screen_width, state.screen_height)
    # In page mode, offset aligns to the page start row, not a minimal one-row shift.
    assert state.bar_offset == 8


def test_jk_auto_clamps_cursor_to_system_visible_rows_and_scrolls() -> None:
    base = piece_with_unused_then_used_bass_rows()
    # Repeat to create multiple systems with alternating hidden/visible bass rows.
    piece = Piece(title="T", bars=base.bars * 4, strings=7, style="french")
    state = regression_state(piece, width=70, bar_width=10, justify="stretch")
    state.settings["barsperline"] = "1"
    state.settings["scrollmode"] = "smooth"
    state.screen_height = 20
    state.settings["tuning"] = "g2c3f3a3d4g4d2"

    # Start on a bar that shows the extra bass row; place cursor on that row.
    state.cursor_bar = 1
    state.cursor_string = 6
    state.cursor_col = 0
    ensure_cursor_visible(state, state.screen_width, state.screen_height)
    assert state.cursor_string == 6

    # Jump to previous system/bar without extra bass; cursor must stay visible (clamped).
    handle_normal(state, ord("K"))
    ensure_cursor_visible(state, state.screen_width, state.screen_height)
    assert state.cursor_bar == 0
    assert state.cursor_string <= 5

    # Jump down beyond the currently visible screen and ensure viewport scrolls.
    state.bar_offset = 0
    handle_normal(state, ord("J"))
    handle_normal(state, ord("J"))
    ensure_cursor_visible(state, state.screen_width, state.screen_height)
    assert state.bar_offset > 0


def test_ensure_cursor_visible_uses_dynamic_auto_system_rows() -> None:
    state = regression_state(multi_bar_spacing_piece(), width=36, bar_width=12, justify="smart")
    state.settings["layout"] = "auto"
    state.screen_height = 20
    state.bar_offset = 0
    # Place cursor in a later auto-computed system row.
    state.cursor_bar = 3
    ensure_cursor_visible(state, state.screen_width, state.screen_height)
    # Must scroll according to dynamic starts, not fixed per-line heuristic.
    assert state.bar_offset > 0
