from __future__ import annotations

from oud.core.model import Bar, Chord, Note, Piece
from oud.editor.state import EditorState


def regression_state(
    piece: Piece,
    *,
    width: int = 120,
    bar_width: int = 10,
    justify: str = "stretch",
) -> EditorState:
    settings = {
        "style": "french",
        "layout": "auto",
        "justify": justify,
        "barpad": "1",
        "flagredundant": "on",
        "showdur": "on",
        "showextras": "on",
        "showtactus": "on",
        "showmeta": "off",
        "tuninglabels": "relative",
        "basslabels": "tuning",
        "barsperline": "0",
        "maxbars": "0",
        "linelen": "0",
        "measuresstep": "10",
    }
    state = EditorState(piece, settings)
    state.screen_width = width
    state.screen_height = 24
    state.bar_width = bar_width
    return state


def dense_flag_alignment_piece() -> Piece:
    # Synthetic "problem bar" with dense mixed durations and staggered chords.
    bar = Bar(
        chords=[
            Chord(note_type=2, dotted=True, grid=None, notes=[Note(1, 7, 0), Note(4, 3, 0)]),   # 1.
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 6, 0), Note(5, 2, 0)]),  # 4
            Chord(note_type=5, dotted=False, grid=None, notes=[Note(1, 4, 0), Note(2, 2, 0)]),  # 8
            Chord(note_type=6, dotted=False, grid=None, notes=[Note(3, 3, 0)]),                  # 16
            Chord(note_type=6, dotted=False, grid=None, notes=[Note(2, 0, 0), Note(6, 4, 0)]),   # 16
            Chord(note_type=5, dotted=False, grid=None, notes=[Note(1, 2, 0), Note(4, 1, 0)]),   # 8
        ],
        time_sig="C",
    )
    return Piece(title="Dense", bars=[bar], strings=6, style="french")


def piece_with_unused_then_used_bass_rows() -> Piece:
    # First bar has no extra-course notes; second bar has a 7th-course note.
    bar1 = Bar(
        chords=[
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0), Note(3, 2, 0)]),
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 1, 0)]),
        ],
        time_sig="C",
    )
    bar2 = Bar(
        chords=[
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(7, 0, 0), Note(1, 2, 0)]),
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 0, 0)]),
        ],
    )
    return Piece(title="BassRows", bars=[bar1, bar2], strings=7, style="french")


def multi_bar_spacing_piece() -> Piece:
    bars = [
        Bar(
            chords=[
                Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0), Note(3, 0, 0)]),
                Chord(note_type=5, dotted=False, grid=None, notes=[Note(2, 1, 0)]),
                Chord(note_type=6, dotted=False, grid=None, notes=[Note(4, 3, 0)]),
                Chord(note_type=5, dotted=False, grid=None, notes=[Note(1, 0, 0), Note(6, 2, 0)]),
            ],
            time_sig="C",
        ),
        Bar(
            chords=[
                Chord(note_type=5, dotted=True, grid=None, notes=[Note(1, 4, 0)]),
                Chord(note_type=6, dotted=False, grid=None, notes=[Note(2, 2, 0), Note(5, 0, 0)]),
                Chord(note_type=6, dotted=False, grid=None, notes=[Note(3, 1, 0)]),
                Chord(note_type=5, dotted=False, grid=None, notes=[Note(1, 3, 0)]),
            ],
        ),
        Bar(
            chords=[
                Chord(note_type=4, dotted=False, grid=None, notes=[Note(6, 0, 0)]),
                Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 2, 0), Note(1, 0, 0)]),
            ],
        ),
        Bar(
            chords=[
                Chord(note_type=6, dotted=False, grid=None, notes=[Note(1, 1, 0)]),
                Chord(note_type=6, dotted=False, grid=None, notes=[Note(2, 3, 0)]),
                Chord(note_type=6, dotted=False, grid=None, notes=[Note(3, 0, 0)]),
                Chord(note_type=6, dotted=False, grid=None, notes=[Note(4, 2, 0)]),
                Chord(note_type=5, dotted=False, grid=None, notes=[Note(1, 4, 0), Note(5, 1, 0)]),
            ],
        ),
    ]
    return Piece(title="Spacing", bars=bars, strings=6, style="french")


def repeat_and_meter_change_piece() -> Piece:
    bars = [
        Bar(
            time_sig="C",
            repeat=".:",
            chords=[
                Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0), Note(3, 2, 0)]),
                Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 1, 0)]),
            ],
        ),
        Bar(
            time_sig="3/4",
            chords=[
                Chord(note_type=5, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
                Chord(note_type=6, dotted=False, grid=None, notes=[Note(2, 3, 0)]),
                Chord(note_type=6, dotted=False, grid=None, notes=[Note(3, 1, 0)]),
                Chord(note_type=5, dotted=False, grid=None, notes=[Note(4, 0, 0)]),
            ],
        ),
        Bar(
            repeat=":.",
            barline="||",
            chords=[
                Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 4, 0), Note(6, 0, 0)]),
            ],
        ),
    ]
    return Piece(title="RepeatMeter", bars=bars, strings=6, style="french")


def mapped_column_transition_piece() -> Piece:
    # Mimics the Earl-of-Essex type failure: one row with an early 8th -> 16th shift.
    bar = Bar(
        chords=[
            Chord(note_type=5, dotted=False, grid=None, notes=[Note(3, 1, 0)]),
            Chord(note_type=5, dotted=False, grid=None, notes=[Note(2, 2, 0), Note(4, 0, 0)]),
            Chord(note_type=6, dotted=False, grid=None, notes=[Note(3, 3, 0)]),
            Chord(note_type=6, dotted=False, grid=None, notes=[Note(3, 4, 0), Note(5, 1, 0)]),
            Chord(note_type=5, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
        ],
        time_sig="O",
    )
    return Piece(title="MappedCols", bars=[bar], strings=6, style="french")


def stem_alignment_problem_piece() -> Piece:
    # Synthetic bars capturing "Lachrimae-like" stem/flag alignment and density issues.
    bars = [
        Bar(
            time_sig="O",
            chords=[
                Chord(note_type=2, dotted=True, grid=None, notes=[Note(2, 3, 0), Note(6, 0, 0)]),
                Chord(note_type=6, dotted=False, grid=None, notes=[Note(1, 1, 0)]),
                Chord(note_type=5, dotted=False, grid=None, notes=[Note(3, 2, 0)]),
                Chord(note_type=5, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
            ],
        ),
        Bar(
            chords=[
                Chord(note_type=6, dotted=True, grid=None, notes=[Note(1, 4, 0)]),
                Chord(note_type=6, dotted=False, grid=None, notes=[Note(2, 5, 0)]),
                Chord(note_type=5, dotted=False, grid=None, notes=[Note(3, 3, 0)]),
                Chord(note_type=6, dotted=False, grid=None, notes=[Note(4, 2, 0)]),
                Chord(note_type=6, dotted=False, grid=None, notes=[Note(5, 1, 0)]),
            ],
        ),
    ]
    # Extend to many bars to imitate multi-system smart layout checks.
    bars.extend(
        [
            Bar(
                chords=[
                    Chord(note_type=5 if i % 2 else 6, dotted=False, grid=None, notes=[Note(1, (i + 2) % 6, 0)]),
                    Chord(note_type=6, dotted=False, grid=None, notes=[Note(3, (i + 3) % 5, 0), Note(7 if i % 3 == 0 else 6, i % 4, 0)]),
                    Chord(note_type=5, dotted=False, grid=None, notes=[Note(2, (i + 1) % 4, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(4, (i + 2) % 4, 0)]),
                ],
            )
            for i in range(18)
        ],
    )
    return Piece(title="StemAlign", bars=bars, strings=8, style="french")


def long_width_fill_piece(bars_count: int = 32, *, strings: int = 7) -> Piece:
    bars: list[Bar] = [
        Bar(
            time_sig="O" if i == 0 else None,
            chords=[
                Chord(note_type=5, dotted=False, grid=None, notes=[Note(1, (i + 2) % 6, 0)]),
                Chord(note_type=6, dotted=(i % 5 == 0), grid=None, notes=[Note(2, (i + 1) % 5, 0), Note(4, i % 4, 0)]),
                Chord(note_type=6, dotted=False, grid=None, notes=[Note(3, (i + 3) % 5, 0)]),
                Chord(note_type=5, dotted=False, grid=None, notes=[Note(min(strings, 7), i % 3, 0)]),
                Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, (i + 4) % 6, 0)]),
            ],
        )
        for i in range(bars_count)
    ]
    return Piece(title="WidthFill", bars=bars, strings=strings, style="french")
