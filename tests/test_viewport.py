import pytest

from oud.editor.normal_actions import handle_normal
from oud.editor.state import EditorState
from oud.petrucci.model import Bar, Chord, LyricEvent, MelodyEvent, Note, Piece
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


def _duet_halves_state(logical_bars: int = 10) -> EditorState:
    top_bars = [
        Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, idx % 3, 0)])])
        for idx in range(logical_bars)
    ]
    bottom_bars = [
        Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, idx % 4, 0)])])
        for idx in range(logical_bars)
    ]
    piece = Piece(
        title="Duet",
        bars=top_bars + bottom_bars,
        strings=6,
        style="french",
        ensemble="lute 1:6-course, lute 2:6-course",
        part="score",
    )
    settings = {
        "style": "french",
        "layout": "auto",
        "barsperline": "2",
        "bargap": "1",
        "showdur": "off",
        "showextras": "off",
        "showtactus": "off",
        "flagstems": "single",
        "playbackscroll": "on",
        "duetscoreview": "both",
        "scrollmode": "smooth",
    }
    state = EditorState(piece, settings)
    state.screen_width = 80
    state.screen_height = 12
    state.bar_width = 8
    return state


def test_ensure_cursor_visible_smooth_scrolls_minimally() -> None:
    state = _state()
    state.settings["scrollmode"] = "smooth"
    state.bar_offset = 0
    state.cursor_bar = 8  # row index 4 with 2 bars/row
    ensure_cursor_visible(state, state.screen_width, state.screen_height)
    # The renderer always reserves the second stem row, so 3 systems fit at
    # height 40: scroll to row 2 (bar 4) so row 4 becomes the last visible row.
    assert state.bar_offset == 4


def test_ensure_cursor_visible_page_scrolls_by_page_rows() -> None:
    state = _state()
    state.settings["scrollmode"] = "page"
    state.bar_offset = 0
    state.cursor_bar = 8  # row index 4 with 2 bars/row
    ensure_cursor_visible(state, state.screen_width, state.screen_height)
    # In page mode, offset aligns to the page start row (row 3 of 3-row pages).
    assert state.bar_offset == 6


def test_ensure_cursor_visible_can_follow_playback_when_enabled() -> None:
    state = _state()
    state.settings["playbackscroll"] = "on"
    state.bar_offset = 0
    state.cursor_bar = 0
    state.playback_bar = 8
    ensure_cursor_visible(state, state.screen_width, state.screen_height)
    assert state.bar_offset == 4


def test_ensure_cursor_visible_ignores_playback_when_disabled() -> None:
    state = _state()
    state.settings["playbackscroll"] = "off"
    state.bar_offset = 0
    state.cursor_bar = 0
    state.playback_bar = 8
    ensure_cursor_visible(state, state.screen_width, state.screen_height)
    assert state.bar_offset == 0


def test_ensure_cursor_visible_maps_duet_halves_playback_to_logical_rows() -> None:
    state = _duet_halves_state()
    state.bar_offset = 0
    state.cursor_bar = 0
    state.playback_bar = 14  # bottom staff, logical bar 4 in halves storage
    ensure_cursor_visible(state, state.screen_width, state.screen_height)
    assert state.bar_offset == 4


def test_ensure_cursor_visible_duet_single_staff_follows_hidden_staff_playback_logically() -> None:
    state = _duet_halves_state()
    state.settings["duetscoreview"] = "1"
    state.bar_offset = 0
    state.cursor_bar = 0
    state.playback_bar = 16  # hidden bottom staff, logical bar 6
    ensure_cursor_visible(state, state.screen_width, state.screen_height)
    assert state.bar_offset == 6


def test_ensure_cursor_visible_maps_halves_duet_top_staff_without_raw_div2_shortcut() -> None:
    state = _duet_halves_state(logical_bars=20)
    state.bar_offset = 0
    state.cursor_bar = 0
    state.playback_bar = 16
    ensure_cursor_visible(state, state.screen_width, state.screen_height)
    assert state.bar_offset == 16


def test_ensure_cursor_visible_duet_uses_earliest_active_logical_marker() -> None:
    state = _duet_halves_state(logical_bars=20)
    state.bar_offset = 16
    state.cursor_bar = 0
    state.playback_bar = 16
    # Simultaneous playback can span adjacent logical bars across the paired staves.
    # The viewport should keep the earliest logical bar visible so neither note vanishes.
    state.playback.markers = [(16, 0), (23, 3)]  # top logical 16, bottom logical 3
    ensure_cursor_visible(state, state.screen_width, state.screen_height)
    assert state.bar_offset == 2


def test_ensure_cursor_visible_follows_vocal_playback_with_text_lanes_visible() -> None:
    piece = Piece(
        title="Vocal",
        bars=[
            Bar(
                melody_events=[MelodyEvent("d", 0)],
                lyric_event_rows=[[LyricEvent(f"w{idx}", 0)]],
                chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, idx % 4, 0)])],
            )
            for idx in range(10)
        ],
        strings=6,
        style="french",
    )
    settings = {
        "style": "french",
        "layout": "packed",
        "barsperline": "2",
        "bargap": "1",
        "showdur": "off",
        "showextras": "off",
        "showtactus": "off",
        "flagstems": "single",
        "showmelody": "on",
        "showlyrics": "on",
        "playbackscroll": "on",
        "scrollmode": "smooth",
    }
    state = EditorState(piece, settings)
    state.screen_width = 80
    state.screen_height = 14
    state.bar_width = 8
    state.bar_offset = 0
    state.cursor_bar = 0
    state.playback_bar = 8
    ensure_cursor_visible(state, state.screen_width, state.screen_height)
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
        state.cursor_bar = 3  # third auto system row on the same fixture

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


def test_scroll_keys_move_viewport_without_mutating_cursor_bar() -> None:
    state = _state(bars=80)
    state.bar_offset = 0
    state.cursor_bar = 0
    state.cursor_col = 0
    # PgDn is now a scroll-only action in normal mode.
    handle_normal(state, state.keycodes.npage)
    assert state.cursor_bar == 0
    assert state.bar_offset > 0
    moved_offset = state.bar_offset
    # Viewport hold should prevent immediate snap-back to cursor on next ensure call.
    ensure_cursor_visible(state, state.screen_width, state.screen_height)
    assert state.bar_offset == moved_offset
    # The following ensure pass can re-sync if needed.
    ensure_cursor_visible(state, state.screen_width, state.screen_height)
    assert state.bar_offset <= moved_offset


def test_ctrl_u_ctrl_d_scroll_viewport_without_cursor_jump() -> None:
    state = _state(bars=80)
    state.bar_offset = 10
    state.cursor_bar = 12
    state.cursor_col = 0
    # Ctrl-D scrolls down, Ctrl-U scrolls up in the vim profile.
    handle_normal(state, 4)
    down_offset = state.bar_offset
    assert down_offset > 10
    assert state.cursor_bar == 12
    handle_normal(state, 21)
    assert state.bar_offset < down_offset
    assert state.cursor_bar == 12
