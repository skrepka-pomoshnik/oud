from oud.core.model import Bar, Piece
from oud.editor.layout import bars_per_line
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
