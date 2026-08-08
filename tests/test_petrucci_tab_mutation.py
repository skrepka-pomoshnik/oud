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
    assert document.durations == {(0, 0, 0): 4, (0, 1, 0): 4, (0, 0, 6): 2}


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
