from __future__ import annotations

from oud.editor.state import EditorState
from oud.petrucci.model import Bar, Chord, Note, Piece


def _flatten_notes(chords: list[Chord]) -> list[Note]:
    return [note for chord in chords for note in chord.notes]


def mk_note(string: int, fret: int, midi_pitch: int = 0) -> Note:
    return Note(string, fret, midi_pitch)


def mk_chord(
    note_type: int,
    notes: list[tuple[int, int]] | list[Note],
    *,
    dotted: bool = False,
    grid: str | None = None,
) -> Chord:
    chord_notes: list[Note] = []
    for item in notes:
        if isinstance(item, Note):
            chord_notes.append(item)
        else:
            string, fret = item
            chord_notes.append(mk_note(string, fret))
    return Chord(note_type=note_type, dotted=dotted, grid=grid, notes=chord_notes)


def mk_bar(
    chords: list[Chord] | None = None,
    *,
    notes: list[Note] | None = None,
    time_sig: str | None = None,
    repeat: str | None = None,
    barline: str | None = None,
    dynamic: str | None = None,
    fermata: bool = False,
) -> Bar:
    return Bar(
        chords=chords or [],
        notes=notes or [],
        time_sig=time_sig,
        repeat=repeat or "",
        barline=barline or "|",
        dynamic=dynamic,
        fermata=fermata,
    )


def mk_piece(
    bars: list[Bar],
    *,
    strings: int = 6,
    title: str = "Synthetic",
    style: str = "french",
    tuning: str | None = None,
) -> Piece:
    return Piece(title=title, bars=bars, strings=strings, style=style, tuning=tuning)


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
    return mk_piece([bar], title="Dense")


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


def dense_auftact_piece(time_sig: str) -> Piece:
    return Piece(
        title="AuftactDense",
        bars=[
            Bar(
                time_sig=time_sig,
                chords=[
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0), Note(3, 2, 0)]),
                    Chord(note_type=6, dotted=False, grid=None, notes=[Note(1, 1, 0)]),
                    Chord(note_type=6, dotted=False, grid=None, notes=[Note(2, 2, 0)]),
                    Chord(note_type=5, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
                ],
            ),
            Bar(
                chords=[
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 0, 0)]),
                ],
            ),
        ],
        strings=6,
        style="french",
    )


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


def import_fixture_extra_courses_piece() -> Piece:
    """Synthetic parsed-piece fixture with fretted 7th/8th-course notes."""
    bar1_chords = [
        Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0), Note(7, 2, 0)]),
        Chord(note_type=5, dotted=False, grid=None, notes=[Note(2, 1, 0), Note(8, 4, 0)]),
    ]
    bar2_chords = [
        Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 2, 0)]),
        Chord(note_type=4, dotted=False, grid=None, notes=[Note(7, 0, 0)]),
    ]
    return Piece(
        title="Import8Course",
        bars=[
            Bar(
                time_sig="C",
                chords=bar1_chords,
                notes=_flatten_notes(bar1_chords),
            ),
            Bar(
                chords=bar2_chords,
                notes=_flatten_notes(bar2_chords),
            ),
        ],
        strings=8,
        style="french",
        tuning="g2c3f3a3d4g4d2c2",
    )


def import_fixture_multisection_tab_piece() -> Piece:
    """Synthetic parsed TAB fixture with section-like metadata and bar markers."""
    bar0_chords = [
        Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
        Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 1, 0)]),
    ]
    bar1_chords = [
        Chord(note_type=5, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
        Chord(note_type=5, dotted=False, grid=None, notes=[Note(2, 3, 0)]),
        Chord(note_type=5, dotted=False, grid=None, notes=[Note(3, 1, 0)]),
    ]
    bar2_chords = [
        Chord(note_type=4, dotted=False, grid=None, notes=[Note(4, 0, 0)]),
        Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 2, 0)]),
    ]
    bar3_chords = [Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 4, 0)])]
    piece = Piece(
        title="MultiSection",
        composer="Anon",
        bars=[
            Bar(
                time_sig="C",
                repeat=".:",
                chords=bar0_chords,
                notes=_flatten_notes(bar0_chords),
            ),
            Bar(
                chords=bar1_chords,
                notes=_flatten_notes(bar1_chords),
            ),
            Bar(
                time_sig="3/4",
                chords=bar2_chords,
                notes=_flatten_notes(bar2_chords),
            ),
            Bar(
                repeat=":.",
                barline="||",
                chords=bar3_chords,
                notes=_flatten_notes(bar3_chords),
            ),
        ],
        strings=6,
        style="french",
    )
    piece.section_annotations = {"2": "Section B", "4": "Fine"}
    return piece


def import_fixture_no_break_header_body_piece() -> Piece:
    """Synthetic parsed result for TAB source that had no blank header/body separator."""
    chords = [
        Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
        Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 1, 0)]),
    ]
    return Piece(
        title="NoSeparator",
        composer="Composer",
        bars=[
            Bar(
                time_sig="C",
                chords=chords,
                notes=_flatten_notes(chords),
            ),
        ],
        strings=6,
        style="french",
    )


def import_fixture_meter_change_mid_system_piece() -> Piece:
    """Synthetic parsed piece with meter changes intended to occur mid rendered system."""
    bar0 = [
        Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
        Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 1, 0)]),
    ]
    bar1 = [
        Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
        Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 0, 0)]),
    ]
    bar2 = [
        Chord(note_type=5, dotted=False, grid=None, notes=[Note(1, 3, 0)]),
        Chord(note_type=5, dotted=False, grid=None, notes=[Note(2, 4, 0)]),
        Chord(note_type=5, dotted=False, grid=None, notes=[Note(3, 2, 0)]),
    ]
    bar3 = [
        Chord(note_type=4, dotted=False, grid=None, notes=[Note(4, 0, 0)]),
        Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 2, 0)]),
    ]
    bars = [
        Bar(
            time_sig="C",
            chords=bar0,
            notes=_flatten_notes(bar0),
        ),
        Bar(
            chords=bar1,
            notes=_flatten_notes(bar1),
        ),
        Bar(
            time_sig="O",
            chords=bar2,
            notes=_flatten_notes(bar2),
        ),
        Bar(
            chords=bar3,
            notes=_flatten_notes(bar3),
        ),
    ]
    return Piece(title="MeterMidSystem", bars=bars, strings=6, style="french")


def polyphony_analogue_piece() -> Piece:
    """Synthetic two-voice-like texture on one tab staff (interleaved rhythms/crossings)."""
    bars = [
        Bar(
            time_sig="C",
            chords=[
                # lower "voice" held-like quarter + upper moving line
                Chord(note_type=4, dotted=False, grid=None, notes=[Note(5, 0, 0), Note(2, 3, 0)]),
                Chord(note_type=6, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
                Chord(note_type=6, dotted=False, grid=None, notes=[Note(2, 1, 0)]),
                Chord(note_type=5, dotted=False, grid=None, notes=[Note(1, 4, 0), Note(4, 2, 0)]),
                Chord(note_type=5, dotted=False, grid=None, notes=[Note(3, 0, 0)]),
            ],
        ),
        Bar(
            chords=[
                # crossing-like texture: upper row rests while middle/lower move, then rejoin
                Chord(note_type=5, dotted=False, grid=None, notes=[Note(3, 2, 0), Note(6, 1, 0)]),
                Chord(note_type=6, dotted=False, grid=None, notes=[Note(2, 4, 0)]),
                Chord(note_type=6, dotted=False, grid=None, notes=[Note(4, 3, 0)]),
                Chord(note_type=5, dotted=False, grid=None, notes=[Note(1, 1, 0), Note(5, 2, 0)]),
                Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 0, 0)]),
            ],
        ),
        Bar(
            chords=[
                Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0), Note(4, 1, 0)]),
                Chord(note_type=5, dotted=False, grid=None, notes=[Note(2, 2, 0)]),
                Chord(note_type=5, dotted=False, grid=None, notes=[Note(3, 3, 0)]),
                Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 4, 0), Note(6, 0, 0)]),
            ],
        ),
    ]
    return Piece(title="PolyphonyAnalogue", bars=bars, strings=6, style="french")


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
