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
