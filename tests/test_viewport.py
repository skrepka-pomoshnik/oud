import pytest

from oud.core.model import Bar, Piece
from oud.editor.normal_actions import handle_normal
from oud.editor.state import EditorState
from oud.tui.viewport import ensure_cursor_visible
from tests.helpers_regression_cases import (
    multi_bar_spacing_piece,
    piece_with_unused_then_used_bass_rows,
    regression_state,
)


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


def test_scrollmode_smooth_vs_page_use_same_fixture_with_different_offsets() -> None:
    smooth = regression_state(multi_bar_spacing_piece(), width=36, bar_width=12, justify="smart")
    page = regression_state(multi_bar_spacing_piece(), width=36, bar_width=12, justify="smart")
    for state, mode in ((smooth, "smooth"), (page, "page")):
        state.settings["layout"] = "auto"
        state.settings["scrollmode"] = mode
        for key in ("showdur", "showextras", "showtactus"):
            state.settings[key] = "off"
        state.screen_height = 24  # 2 rows on this fixture
        state.bar_offset = 0
        state.cursor_bar = 3      # third auto system row on the same fixture

    ensure_cursor_visible(smooth, smooth.screen_width, smooth.screen_height)
    ensure_cursor_visible(page, page.screen_width, page.screen_height)

    assert smooth.bar_offset == 1
    assert page.bar_offset == 3
    assert page.bar_offset > smooth.bar_offset


def test_jk_fullscreen_alternating_bass_rows_keeps_cursor_visible_and_scrolls() -> None:
    base = piece_with_unused_then_used_bass_rows()
    piece = Piece(title="T", bars=base.bars * 10, strings=7, style="french")
    state = regression_state(piece, width=121, bar_width=10, justify="smart")
    state.settings["layout"] = "auto"
    state.settings["scrollmode"] = "page"
    state.settings["tuning"] = "g2c3f3a3d4g4d2"
    state.screen_height = 39
    state.cursor_bar = 1
    state.cursor_string = 6
    state.cursor_col = 0
    ensure_cursor_visible(state, state.screen_width, state.screen_height)
    start_offset = state.bar_offset

    # Move across alternating systems several times; cursor must remain on-screen.
    for _ in range(4):
        handle_normal(state, ord("J"))
        ensure_cursor_visible(state, state.screen_width, state.screen_height)
        assert 0 <= state.cursor_string < state.piece.strings
        assert state.bar_offset >= 0
    assert state.bar_offset >= start_offset

    # And back up; hidden bass-row systems should clamp but not lose cursor.
    for _ in range(3):
        handle_normal(state, ord("K"))
        ensure_cursor_visible(state, state.screen_width, state.screen_height)
        assert 0 <= state.cursor_string < state.piece.strings


@pytest.mark.parametrize("justify", ["compact", "smart", "stretch", "edge"])
@pytest.mark.parametrize("beatsnap", ["off", "soft"])
def test_jk_mixed_spacing_modes_with_hidden_bass_rows_keep_cursor_visible(
    justify: str,
    beatsnap: str,
) -> None:
    base = piece_with_unused_then_used_bass_rows()
    piece = Piece(title="T", bars=base.bars * 8, strings=7, style="french")
    state = regression_state(piece, width=96, bar_width=10, justify=justify)
    state.settings["layout"] = "auto"
    state.settings["justify"] = justify
    state.settings["beatsnap"] = beatsnap
    state.settings["scrollmode"] = "smooth"
    state.settings["tuning"] = "g2c3f3a3d4g4d2"
    state.screen_height = 24
    state.cursor_bar = 1
    state.cursor_string = 6  # visible only in every second system
    state.cursor_col = 0
    ensure_cursor_visible(state, state.screen_width, state.screen_height)

    # Move down then up across alternating systems; cursor must remain visible/clamped.
    for key in (ord("J"), ord("J"), ord("K"), ord("K")):
        handle_normal(state, key)
        ensure_cursor_visible(state, state.screen_width, state.screen_height)
        assert 0 <= state.cursor_bar < len(state.piece.bars), (justify, beatsnap)
        assert 0 <= state.cursor_string < state.piece.strings, (justify, beatsnap)
        assert state.bar_offset >= 0, (justify, beatsnap)
