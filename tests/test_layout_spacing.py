from oud.core.ft3 import build_durations, load_ft3
from oud.core.model import Bar, Chord, Note
from oud.core.view_model import _bar_compact_width, _bar_display_width, _bars_fit


def test_bar_display_width_accounts_for_flags_and_dots() -> None:
    bar = Bar()
    overrides = {(0, 0, 0): "a", (0, 1, 2): "b"}
    durations = {(0, 0, 0): 16, (0, 1, 2): 16}
    dotted = {(0, 0)}
    width = _bar_display_width(
        bar,
        bar_index=0,
        bar_width=8,
        overrides=overrides,
        durations=durations,
        default_duration=4,
        dotted=dotted,
    )
    assert width >= 5


def test_bar_display_width_scales_with_chords() -> None:
    bar = Bar()
    bar.chords = [
        Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
        Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
        Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 4, 0)]),
    ]
    width = _bar_display_width(
        bar,
        bar_index=0,
        bar_width=8,
        overrides={},
        durations={},
        default_duration=4,
        dotted=set(),
    )
    assert width >= 7


def test_bars_fit_respects_usable_width_and_gap() -> None:
    bars = [Bar(), Bar(), Bar()]
    overrides = {(0, 0, 0): "a", (1, 0, 0): "b", (2, 0, 0): "c"}
    durations = {(0, 0, 0): 4, (1, 0, 0): 4, (2, 0, 0): 4}
    count = _bars_fit(
        bars,
        bar_offset=0,
        bar_gap=1,
        usable_width=9,
        bar_width=8,
        overrides=overrides,
        durations=durations,
        default_duration=4,
        dotted=set(),
        compact=False,
    )
    assert count == 2


def test_bars_fit_max_chords_min_width() -> None:
    bars = [Bar(), Bar()]
    count = _bars_fit(
        bars,
        bar_offset=0,
        bar_gap=1,
        usable_width=9,
        bar_width=4,
        overrides={},
        durations={},
        default_duration=4,
        dotted=set(),
        max_chords=4,
        compact=False,
    )
    assert count == 1


def test_bars_fit_respects_chord_wrap_threshold() -> None:
    bars = [
        Bar(
            chords=[
                Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
                Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
                Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 4, 0)]),
            ],
        ),
        Bar(
            chords=[
                Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 1, 0)]),
                Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 3, 0)]),
                Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 5, 0)]),
            ],
        ),
    ]
    count = _bars_fit(
        bars,
        bar_offset=0,
        bar_gap=1,
        usable_width=120,
        bar_width=16,
        overrides={},
        durations={},
        default_duration=4,
        dotted=set(),
        compact=True,
        chord_wrap_limit=4,
    )
    assert count == 1


def test_compact_width_for_frog_galliard_bars_stays_tight() -> None:
    piece = load_ft3("lutemusic/23a_frogg_galliard_2.ft3")
    durations = build_durations(piece)
    bar7_width = _bar_compact_width(
        piece.bars[6],
        bar_index=6,
        bar_width=16,
        overrides={},
        durations=durations,
        default_duration=4,
        dotted=set(),
    )
    bar21_width = _bar_compact_width(
        piece.bars[20],
        bar_index=20,
        bar_width=16,
        overrides={},
        durations=durations,
        default_duration=4,
        dotted=set(),
    )
    assert bar7_width <= 18
    assert bar21_width <= 20
