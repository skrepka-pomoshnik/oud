from __future__ import annotations

import copy
from fractions import Fraction

import pytest

from petrucci import (
    Bar,
    Chord,
    Note,
    TabDocument,
    TabDuration,
    TabEdit,
    TabEditIntent,
    TabEditTransaction,
    TabMutationError,
    TabPosition,
    apply_tab_mutation,
)
from petrucci.input.tablature.mutation import bar_content_length, bar_meter_length, event_onsets

QUARTER = TabDuration(4)
EIGHTH = TabDuration(8)


def _document(*bars: Bar, style: str = "french", meter: str | None = "4/4") -> TabDocument:
    return TabDocument(list(bars) or [Bar()], 6, style, default_meter=meter)


def _chord(denominator: int, *notes: tuple[int, int], dotted: bool = False, grid: str | None = None) -> Chord:
    note_types = {1: 2, 2: 3, 4: 4, 8: 5, 16: 6}
    return Chord(
        note_types[denominator],
        dotted,
        grid,
        [Note(string=course, fret=fret, raw_pos=0) for course, fret in notes],
    )


def _events(bar: Bar) -> list[tuple[TabDuration, list[tuple[int, int]]]]:
    return [(TabDuration.of(chord), [(note.string, note.fret) for note in chord.notes]) for chord in bar.chords]


def _apply(document: TabDocument, *operations: TabEdit):
    return apply_tab_mutation(document, TabEditTransaction(operations))


def _at(onset: Fraction, course: int | None = None, bar: int = 0) -> TabPosition:
    return TabPosition(bar, onset, course)


def test_typing_appends_events_at_the_end_of_the_bar() -> None:
    document = _document()
    _apply(
        document,
        TabEdit(_at(Fraction(0), 1), TabEditIntent.NOTE, fret=3, duration=QUARTER),
        TabEdit(_at(Fraction(0), 2), TabEditIntent.CHORD, fret=5),
        TabEdit(_at(Fraction(1, 4)), TabEditIntent.REST, duration=TabDuration(2)),
        TabEdit(_at(Fraction(3, 4), 1), TabEditIntent.NOTE, fret=0, duration=EIGHTH),
    )

    assert _events(document.bars[0]) == [
        (QUARTER, [(1, 3), (2, 5)]),
        (TabDuration(2), []),
        (EIGHTH, [(1, 0)]),
    ]
    assert event_onsets(document.bars[0]) == (Fraction(0), Fraction(1, 4), Fraction(3, 4))


def test_onsets_are_whole_notes_in_every_meter() -> None:
    bar = Bar(chords=[_chord(8, (1, 0)), _chord(8, (1, 1)), _chord(8, (1, 2))], time_sig="3/8")
    document = _document(bar)

    _apply(document, TabEdit(_at(Fraction(1, 4), 2), TabEditIntent.CHORD, fret=4))

    assert bar_meter_length(document, 0) == Fraction(3, 8)
    assert _events(bar)[2] == (EIGHTH, [(1, 2), (2, 4)])


def test_note_replaces_the_event_and_keeps_its_duration_unless_given() -> None:
    bar = Bar(chords=[_chord(4, (1, 0), (3, 2)), _chord(4, (1, 1))])
    document = _document(bar)

    _apply(document, TabEdit(_at(Fraction(0), 2), TabEditIntent.NOTE, fret=7))
    assert _events(bar)[0] == (QUARTER, [(2, 7)])

    _apply(document, TabEdit(_at(Fraction(0), 2), TabEditIntent.NOTE, fret=7, duration=EIGHTH))
    assert _events(bar) == [(EIGHTH, [(2, 7)]), (QUARTER, [(1, 1)])]
    assert event_onsets(bar) == (Fraction(0), Fraction(1, 8))


def test_chord_entry_changes_one_course_and_keeps_its_attachments() -> None:
    chord = _chord(4, (1, 0), (3, 2))
    chord.notes[1].left_fingering = "2"
    chord.notes[1].right_ornament = "#"
    document = _document(Bar(chords=[chord]))

    _apply(document, TabEdit(_at(Fraction(0), 3), TabEditIntent.CHORD, fret=4))

    moved = document.bars[0].chords[0].notes[1]
    assert (moved.string, moved.fret, moved.left_fingering, moved.right_ornament) == (3, 4, "2", "#")
    assert document.bars[0].chords[0].notes[0].fret == 0


def test_insert_places_an_event_before_the_one_at_the_onset() -> None:
    bar = Bar(chords=[_chord(4, (1, 0)), _chord(4, (1, 1))])
    document = _document(bar)

    _apply(
        document,
        TabEdit(_at(Fraction(1, 4), 2), TabEditIntent.NOTE, fret=3, duration=EIGHTH, insert=True),
        TabEdit(_at(Fraction(0)), TabEditIntent.REST, duration=EIGHTH, insert=True),
    )

    assert _events(bar) == [
        (EIGHTH, []),
        (QUARTER, [(1, 0)]),
        (EIGHTH, [(2, 3)]),
        (QUARTER, [(1, 1)]),
    ]


def test_delete_removes_a_course_then_the_empty_event() -> None:
    bar = Bar(chords=[_chord(4, (1, 0), (3, 2)), _chord(4, (1, 1)), _chord(4, (2, 2))])
    document = _document(bar)

    _apply(document, TabEdit(_at(Fraction(0), 3), TabEditIntent.DELETE))
    assert _events(bar)[0] == (QUARTER, [(1, 0)])

    _apply(document, TabEdit(_at(Fraction(0), 1), TabEditIntent.DELETE))
    assert _events(bar) == [(QUARTER, [(1, 1)]), (QUARTER, [(2, 2)])]

    _apply(document, TabEdit(_at(Fraction(1, 4)), TabEditIntent.DELETE))
    assert _events(bar) == [(QUARTER, [(1, 1)])]


def test_deleting_an_absent_course_changes_nothing() -> None:
    document = _document(Bar(chords=[_chord(4, (1, 0))]))

    result = _apply(document, TabEdit(_at(Fraction(0), 5), TabEditIntent.DELETE))

    assert not result.changed
    assert result.changes == ()


def test_note_and_rest_replace_each_other_at_one_onset() -> None:
    bar = Bar(chords=[_chord(4, (1, 3))])
    document = _document(bar)

    _apply(document, TabEdit(_at(Fraction(0)), TabEditIntent.REST, duration=TabDuration(2)))
    assert _events(bar) == [(TabDuration(2), [])]

    _apply(document, TabEdit(_at(Fraction(0), 1), TabEditIntent.NOTE, fret=2, duration=EIGHTH))
    assert _events(bar) == [(EIGHTH, [(1, 2)])]


def test_duration_change_dots_the_event_and_drops_the_stale_flag_marker() -> None:
    bar = Bar(chords=[_chord(8, (1, 0), grid="#"), _chord(8, (1, 1), grid="#")])
    document = _document(bar)

    _apply(document, TabEdit(_at(Fraction(0)), TabEditIntent.DURATION, duration=TabDuration(8, dotted=True)))
    assert TabDuration.of(bar.chords[0]) == TabDuration(8, dotted=True)
    assert bar.chords[0].grid is None
    assert bar.chords[1].grid == "#"
    assert event_onsets(bar) == (Fraction(0), Fraction(3, 16))

    _apply(document, TabEdit(_at(Fraction(3, 16), 1), TabEditIntent.CHORD, fret=1))
    assert bar.chords[1].grid == "#"


def test_result_reports_one_delta_per_changed_bar() -> None:
    document = _document(Bar(), Bar(chords=[_chord(4, (1, 0))]))
    before = copy.deepcopy(document.bars[1].chords)

    result = _apply(
        document,
        TabEdit(_at(Fraction(0), 1, bar=1), TabEditIntent.CHORD, fret=2),
        TabEdit(_at(Fraction(0), 2, bar=1), TabEditIntent.CHORD, fret=3),
    )

    assert [delta.bar_index for delta in result.changes] == [1]
    assert list(result.changes[0].before) == before
    assert list(result.changes[0].after) == document.bars[1].chords


def test_edits_may_not_lengthen_a_bar_past_its_meter() -> None:
    bar = Bar(chords=[_chord(2, (1, 0)), _chord(4, (1, 1))])
    document = _document(bar, meter="3/4")

    with pytest.raises(TabMutationError) as caught:
        _apply(document, TabEdit(_at(Fraction(3, 4), 1), TabEditIntent.NOTE, fret=2, duration=QUARTER))
    assert caught.value.code == "bar-overflow"

    _apply(document, TabEdit(_at(Fraction(1, 2)), TabEditIntent.DURATION, duration=EIGHTH))
    assert bar_content_length(bar) == Fraction(5, 8)


def test_an_overfull_source_bar_can_still_be_edited_without_growing() -> None:
    bar = Bar(chords=[_chord(2, (1, 0)), _chord(2, (1, 1)), _chord(2, (1, 2))])
    document = _document(bar)

    _apply(document, TabEdit(_at(Fraction(1, 2), 2), TabEditIntent.CHORD, fret=5))

    assert _events(bar)[1] == (TabDuration(2), [(1, 1), (2, 5)])
    with pytest.raises(TabMutationError, match="longer than its meter"):
        _apply(document, TabEdit(_at(Fraction(0)), TabEditIntent.DURATION, duration=TabDuration(1)))


def test_the_meter_follows_the_last_bar_that_states_one() -> None:
    document = _document(Bar(time_sig="3/4"), Bar(), Bar(time_sig="C"), meter=None)

    assert [bar_meter_length(document, index) for index in range(3)] == [
        Fraction(3, 4),
        Fraction(3, 4),
        Fraction(1),
    ]
    assert bar_meter_length(_document(Bar(), meter=None), 0) is None


def test_unknown_meter_does_not_limit_the_bar() -> None:
    document = _document(meter="auto")

    _apply(
        document,
        *(TabEdit(_at(Fraction(n, 2), 1), TabEditIntent.NOTE, fret=n, duration=TabDuration(2)) for n in range(4)),
    )

    assert bar_content_length(document.bars[0]) == Fraction(2)


@pytest.mark.parametrize(
    ("bars", "operation", "code"),
    [
        ((), TabEdit(_at(Fraction(0), 1, bar=1), TabEditIntent.NOTE, fret=1, duration=QUARTER), "invalid-position"),
        ((), TabEdit(_at(Fraction(0), 7), TabEditIntent.NOTE, fret=1, duration=QUARTER), "invalid-position"),
        ((), TabEdit(_at(Fraction(0), 1), TabEditIntent.NOTE, fret=19, duration=QUARTER), "invalid-fret"),
        ((), TabEdit(_at(Fraction(0), 1), TabEditIntent.NOTE, fret=1), "missing-duration"),
        ((), TabEdit(_at(Fraction(1, 4), 1), TabEditIntent.NOTE, fret=1, duration=QUARTER), "beyond-content"),
        ((), TabEdit(_at(Fraction(0)), TabEditIntent.DELETE), "no-event"),
        ((), TabEdit(_at(Fraction(0)), TabEditIntent.DURATION, duration=EIGHTH), "no-event"),
        (
            (Bar(chords=[_chord(4, (1, 0))]),),
            TabEdit(_at(Fraction(1, 8), 1), TabEditIntent.CHORD, fret=1),
            "not-an-onset",
        ),
        (
            (Bar(chords=[_chord(4, (1, 0)), _chord(4, (1, 1))]),),
            TabEdit(_at(Fraction(1, 8), 1), TabEditIntent.CHORD, fret=1),
            "not-an-onset",
        ),
    ],
)
def test_rejections_carry_stable_codes(bars: tuple[Bar, ...], operation: TabEdit, code: str) -> None:
    with pytest.raises(TabMutationError) as caught:
        _apply(_document(*copy.deepcopy(bars)), operation)
    assert caught.value.code == code
    assert caught.value.operation_index == 0


def test_italian_style_allows_high_frets() -> None:
    document = _document(style="italian")
    _apply(document, TabEdit(_at(Fraction(0), 1), TabEditIntent.NOTE, fret=19, duration=QUARTER))
    assert _events(document.bars[0]) == [(QUARTER, [(1, 19)])]


def test_a_rejected_transaction_leaves_every_bar_unchanged() -> None:
    document = _document(Bar(chords=[_chord(4, (1, 0))]), Bar())
    before = copy.deepcopy([bar.chords for bar in document.bars])

    with pytest.raises(TabMutationError) as caught:
        _apply(
            document,
            TabEdit(_at(Fraction(0), 2), TabEditIntent.CHORD, fret=3),
            TabEdit(_at(Fraction(0), 1, bar=1), TabEditIntent.NOTE, fret=1, duration=QUARTER),
            TabEdit(_at(Fraction(1, 5), 1), TabEditIntent.NOTE, fret=1, duration=QUARTER),
        )

    assert caught.value.operation_index == 2
    assert [bar.chords for bar in document.bars] == before


def test_error_keeps_the_first_operation_index() -> None:
    error = TabMutationError("bad", "failure", operation_index=1)
    assert error.at_operation(2) is error
