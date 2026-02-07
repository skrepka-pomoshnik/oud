from oud.core.model import Bar, Piece
from oud.editor.layout import bars_per_line, jump_system_row
from oud.editor.state import EditorState


def _state(settings: dict[str, str]) -> EditorState:
    piece = Piece(bars=[Bar() for _ in range(8)], strings=6)
    merged = {
        "barsperline": "0",
        "maxbars": "0",
        "bargap": "1",
    }
    merged.update(settings)
    state = EditorState(piece, merged)
    state.bar_width = 10
    return state


def test_bars_per_line_respects_positive_linelen_cap() -> None:
    state = _state({"linelen": "80", "spacingmode": "auto"})
    per_line = bars_per_line(state, width=200)
    assert per_line == 7


def test_bars_per_line_linelen_zero_means_no_cap() -> None:
    state = _state({"linelen": "0", "spacingmode": "auto"})
    per_line = bars_per_line(state, width=200)
    assert per_line == 17, (per_line, state.bar_width, state.settings)


def test_bars_per_line_honors_explicit_barsperline() -> None:
    state = _state({"barsperline": "4", "linelen": "0", "spacingmode": "auto"})
    per_line = bars_per_line(state, width=200)
    assert per_line == 4


def test_bars_per_line_zero_uses_auto_with_maxbars_cap() -> None:
    state = _state(
        {
            "barsperline": "0",
            "maxbars": "3",
            "linelen": "0",
            "spacingmode": "auto",
        },
    )
    per_line = bars_per_line(state, width=200)
    assert per_line == 3


def test_jump_system_row_preserves_offset_between_rows() -> None:
    state = _state({"barsperline": "3"})
    per_line = bars_per_line(state, width=200)
    assert jump_system_row(state, bar_index=1, delta=1, per_line=per_line) == 4
    assert jump_system_row(state, bar_index=4, delta=-1, per_line=per_line) == 1


def test_jump_system_row_clamps_to_target_row_bounds() -> None:
    state = _state({"barsperline": "3"})
    # 8 bars => rows [0,1,2], [3,4,5], [6,7]
    per_line = bars_per_line(state, width=200)
    # offset 2 cannot exist in the last short row, so it clamps to bar 7.
    assert jump_system_row(state, bar_index=2, delta=2, per_line=per_line) == 7
