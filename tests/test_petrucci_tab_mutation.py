from __future__ import annotations

from fractions import Fraction

import pytest

from petrucci import (
    Bar,
    EditableTablature,
    TabEdit,
    TabEditIntent,
    TabEditTransaction,
    TabMutationError,
    TabPosition,
    apply_tab_mutation,
)


def _document(*, style: str = "french") -> EditableTablature:
    return EditableTablature([Bar()], 6, 12, {}, {}, set(), style)


def test_public_tab_transaction_enters_note_chord_rest_and_delete() -> None:
    document = _document()
    result = apply_tab_mutation(
        document,
        TabEditTransaction(
            (
                TabEdit(TabPosition(0, Fraction(0), 1), TabEditIntent.NOTE, fret=3, duration=4),
                TabEdit(TabPosition(0, Fraction(0), 2), TabEditIntent.CHORD, fret=5, duration=4),
                TabEdit(TabPosition(0, Fraction(1, 2)), TabEditIntent.REST, duration=2),
                TabEdit(TabPosition(0, Fraction(0), 1), TabEditIntent.DELETE),
            ),
        ),
    )

    assert result.changed
    assert document.cells == {(0, 1, 0): "f"}
    assert document.durations == {(0, 0, 0): 4, (0, 0, 6): 2}


def test_public_tab_transaction_supports_two_digit_italian_frets() -> None:
    document = _document(style="italian")

    apply_tab_mutation(
        document,
        TabEditTransaction(
            (TabEdit(TabPosition(0, Fraction(1, 4), 3), TabEditIntent.NOTE, fret=12, duration=8),),
        ),
    )

    assert document.cells == {(0, 2, 3): "1", (0, 2, 4): "2"}
    assert document.durations == {(0, 2, 3): 8}


def test_two_digit_italian_fret_delete_removes_continuation() -> None:
    document = _document(style="italian")
    position = TabPosition(0, Fraction(1, 4), 3)
    apply_tab_mutation(
        document,
        TabEditTransaction((TabEdit(position, TabEditIntent.NOTE, fret=12, duration=8),)),
    )

    apply_tab_mutation(document, TabEditTransaction((TabEdit(position, TabEditIntent.DELETE),)))

    assert document.cells == {}
    assert document.durations == {}


def test_two_digit_italian_fret_replacement_removes_continuation() -> None:
    document = _document(style="italian")
    position = TabPosition(0, Fraction(1, 4), 3)
    apply_tab_mutation(
        document,
        TabEditTransaction((TabEdit(position, TabEditIntent.NOTE, fret=12, duration=8),)),
    )

    apply_tab_mutation(
        document,
        TabEditTransaction((TabEdit(position, TabEditIntent.CHORD, fret=4, duration=8),)),
    )

    assert document.cells == {(0, 2, 3): "4"}
    assert document.durations == {(0, 2, 3): 8}


def test_note_to_rest_replaces_the_complete_onset() -> None:
    document = _document()
    apply_tab_mutation(
        document,
        TabEditTransaction((TabEdit(TabPosition(0, Fraction(0), 1), TabEditIntent.NOTE, fret=3),)),
    )

    apply_tab_mutation(
        document,
        TabEditTransaction((TabEdit(TabPosition(0, Fraction(0)), TabEditIntent.REST, duration=2),)),
    )

    assert document.cells == {}
    assert document.durations == {(0, 0, 0): 2}


def test_rest_to_note_replaces_rest_rhythm() -> None:
    document = _document()
    apply_tab_mutation(
        document,
        TabEditTransaction((TabEdit(TabPosition(0, Fraction(0)), TabEditIntent.REST, duration=2),)),
    )

    apply_tab_mutation(
        document,
        TabEditTransaction((TabEdit(TabPosition(0, Fraction(0), 1), TabEditIntent.NOTE, fret=2, duration=8),)),
    )

    assert document.cells == {(0, 0, 0): "c"}
    assert document.durations == {(0, 0, 0): 8}


@pytest.mark.parametrize(
    ("document", "operation", "code"),
    [
        (_document(), TabEdit(TabPosition(0, Fraction(0), 7), TabEditIntent.NOTE, fret=1), "invalid-position"),
        (_document(), TabEdit(TabPosition(0, Fraction(0), 1), TabEditIntent.NOTE, fret=99), "invalid-fret"),
        (
            _document(style="italian"),
            TabEdit(TabPosition(0, Fraction(11, 12), 1), TabEditIntent.NOTE, fret=12),
            "bar-overflow",
        ),
    ],
)
def test_public_tab_transaction_rejects_invalid_boundaries(
    document: EditableTablature,
    operation: TabEdit,
    code: str,
) -> None:
    with pytest.raises(TabMutationError) as caught:
        apply_tab_mutation(document, TabEditTransaction((operation,)))

    assert caught.value.code == code


def test_public_tab_transaction_reports_operation_index() -> None:
    document = _document()
    transaction = TabEditTransaction(
        (
            TabEdit(TabPosition(0, Fraction(0), 1), TabEditIntent.NOTE, fret=3),
            TabEdit(TabPosition(0, Fraction(1, 5), 1), TabEditIntent.NOTE, fret=1),
        ),
    )

    with pytest.raises(TabMutationError) as caught:
        apply_tab_mutation(document, transaction)

    assert caught.value.code == "unrepresentable-onset"
    assert caught.value.operation_index == 1
    assert document.cells == {}
    assert document.durations == {}
