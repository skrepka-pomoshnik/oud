from oud.core.model import Bar, Chord, Note
from oud.core.view_model import _bar_display_width, _bars_fit


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
