from oud.core.model import Bar, Chord, Note, Piece
from oud.editor.layout import (
    auto_system_bar_plan_with_gaps,
    bars_per_line,
    dynamic_system_starts,
    jump_system_row,
    jump_system_row_dynamic,
)
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
    state = _state({"linelen": "80", "layout": "auto"})
    per_line = bars_per_line(state, width=200)
    assert per_line == 6


def test_bars_per_line_linelen_zero_means_no_cap() -> None:
    state = _state({"linelen": "0", "layout": "auto"})
    per_line = bars_per_line(state, width=200)
    assert per_line == 17, (per_line, state.bar_width, state.settings)


def test_bars_per_line_honors_explicit_barsperline() -> None:
    state = _state({"barsperline": "4", "linelen": "0", "layout": "auto"})
    per_line = bars_per_line(state, width=200)
    assert per_line == 4


def test_bars_per_line_zero_uses_auto_with_maxbars_cap() -> None:
    state = _state(
        {
            "barsperline": "0",
            "maxbars": "3",
            "linelen": "0",
            "layout": "auto",
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


def test_jump_system_row_dynamic_uses_rendered_row_starts() -> None:
    state = _state({"layout": "auto", "barsperline": "0", "linelen": "40"})
    starts = dynamic_system_starts(state, width=120)
    assert starts
    if len(starts) < 2:
        return
    bar_index = starts[0] + 1
    target = jump_system_row_dynamic(state, bar_index=bar_index, delta=1, width=120)
    next_start = starts[1]
    next_end = starts[2] if len(starts) > 2 else len(state.piece.bars)
    expected = min(next_end - 1, next_start + 1)
    assert target == expected


def test_dynamic_system_starts_respect_chordwrap_threshold() -> None:
    bars = [
        Bar(
            chords=[
                Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
                Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
                Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 4, 0)]),
            ],
        )
        for _ in range(4)
    ]
    state = EditorState(
        Piece(bars=bars, strings=6),
        {
            "layout": "auto",
            "justify": "compact",
            "barsperline": "0",
            "maxbars": "0",
            "bargap": "1",
            "linelen": "0",
            "chordwrap": "4",
        },
    )
    state.bar_width = 16
    starts = dynamic_system_starts(state, width=200)
    assert starts == [0, 1, 2, 3]


def test_dynamic_system_starts_respect_imported_system_break_hint() -> None:
    bars = [Bar() for _ in range(5)]
    bars[1].system_break = True
    state = EditorState(
        Piece(bars=bars, strings=6),
        {
            "layout": "packed",
            "barsperline": "4",
            "maxbars": "0",
            "bargap": "1",
            "linelen": "0",
        },
    )
    state.bar_width = 10
    assert dynamic_system_starts(state, width=200) == [0, 2]


def test_jump_system_row_dynamic_prefers_visual_x_alignment() -> None:
    bars = [Bar() for _ in range(6)]
    bars[0] = Bar(
        chords=[
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])
            for _ in range(20)
        ],
    )
    state = EditorState(
        Piece(bars=bars, strings=6),
        {
            "layout": "auto",
            "justify": "compact",
            "barsperline": "3",
            "maxbars": "0",
            "bargap": "1",
            "linelen": "0",
        },
    )
    state.bar_width = 12
    starts = dynamic_system_starts(state, width=200)
    assert starts[:2] == [0, 3]
    current_indices, current_widths, current_gaps = auto_system_bar_plan_with_gaps(state, 0, 200)
    target_indices, target_widths, target_gaps = auto_system_bar_plan_with_gaps(state, 3, 200)
    assert current_indices == [0, 1, 2]
    assert target_indices == [3, 4, 5]
    # Bar 1 on first row is shifted far right by a very wide bar 0, so the
    # nearest bar directly below is the last bar on row 2, not offset bar 4.
    target = jump_system_row_dynamic(state, bar_index=1, delta=1, width=200)
    assert target == 5
    assert sum(current_widths) + sum(current_gaps) > sum(target_widths) + sum(target_gaps)
