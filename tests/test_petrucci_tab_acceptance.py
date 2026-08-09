from __future__ import annotations

import copy
from fractions import Fraction
from pathlib import Path

import pytest

from oud.editor.controller_utils import string_index
from oud.editor.edit_ops import apply_tab_transaction
from oud.editor.undo_ops import redo, undo
from oud.exports.export_tab import export_tab
from oud.importers.tab import load_tab
from petrucci import (
    Bar,
    EditableTablature,
    Piece,
    TabEdit,
    TabEditIntent,
    TabEditTransaction,
    TabPosition,
    apply_tab_mutation,
)
from tests.helpers_keyscript import keyscript_state, press_keys, render_lines


def _transaction_document(style: str, *, strings: int = 7) -> tuple[Piece, EditableTablature]:
    piece = Piece(title="Transaction", bars=[Bar()], strings=strings, style=style)
    return piece, EditableTablature(piece.bars, strings, 12, {}, {}, set(), style)


@pytest.mark.parametrize(("style", "fret", "symbol"), [("french", 0, "a"), ("italian", 8, "8")])
def test_extra_bass_course_transaction_and_keyscript_per_style(style: str, fret: int, symbol: str) -> None:
    _piece, document = _transaction_document(style)
    apply_tab_mutation(
        document,
        TabEditTransaction((TabEdit(TabPosition(0, Fraction(0), 7), TabEditIntent.NOTE, fret=fret),)),
    )
    assert document.cells == {(0, 6, 0): symbol}

    state = keyscript_state(strings=7, style=style)
    if style == "french":
        press_keys(state, ["i", "/", "a", 27])
    else:
        press_keys(state, ["i"])
        state.cursor_string = next(row for row in range(7) if string_index(state, row) == 6)
        press_keys(state, ["8", 27])
    assert state.overrides[(0, 6, 0)] == symbol
    assert any(line.lstrip().startswith("d|") and symbol in line.split("|", 1)[1] for line in render_lines(state))


@pytest.mark.parametrize(("style", "symbols"), [("french", ("a", "c")), ("italian", ("0", "2"))])
def test_repeated_chord_transaction_round_trips_through_tab(
    style: str,
    symbols: tuple[str, str],
    tmp_path: Path,
) -> None:
    piece, document = _transaction_document(style)
    operations: list[TabEdit] = []
    for onset in (Fraction(0), Fraction(1, 4)):
        operations.extend(
            (
                TabEdit(TabPosition(0, onset, 1), TabEditIntent.NOTE, fret=0),
                TabEdit(TabPosition(0, onset, 3), TabEditIntent.CHORD, fret=2),
            ),
        )
    apply_tab_mutation(document, TabEditTransaction(tuple(operations)))

    assert document.cells == {
        (0, 0, 0): symbols[0],
        (0, 2, 0): symbols[1],
        (0, 0, 3): symbols[0],
        (0, 2, 3): symbols[1],
    }
    text = export_tab(piece, dict(document.cells), dict(document.durations), 12, settings={"style": style})
    path = tmp_path / f"repeated-{style}.tab"
    path.write_text(text, encoding="utf-8")
    reopened = load_tab(str(path), strings=7)
    assert reopened.style == style
    assert [[(note.string, note.fret) for note in chord.notes] for chord in reopened.bars[0].chords] == [
        [(1, 0), (3, 2)],
        [(1, 0), (3, 2)],
    ]


@pytest.mark.parametrize(
    ("style", "before", "replacement"),
    [("french", ("a", "b"), "c"), ("italian", ("0", "1"), "2")],
)
def test_string_movement_replaces_only_the_selected_course(
    style: str,
    before: tuple[str, str],
    replacement: str,
) -> None:
    state = keyscript_state(style=style)
    state.overrides.update({(0, 0, 0): before[0], (0, 1, 0): before[1]})
    state.durations[(0, 0, 0)] = 4

    press_keys(state, ["j", "R", replacement, 27])

    assert state.cursor_string == 1
    assert state.overrides[(0, 0, 0)] == before[0]
    assert state.overrides[(0, 1, 0)] == replacement


def test_replacement_and_partial_deletion_retain_onset_attachments() -> None:
    state = keyscript_state(style="french")
    state.overrides.update({(0, 0, 0): "a", (0, 1, 0): "b"})
    state.durations[(0, 0, 0)] = 8
    state.dotted.add((0, 0))
    state.ornaments[(0, 0)] = "tr"
    state.annotations[(0, 0)] = "dolce"
    position = TabPosition(0, Fraction(0), 1)

    apply_tab_transaction(state, TabEditTransaction((TabEdit(position, TabEditIntent.CHORD, fret=3),)))
    apply_tab_transaction(state, TabEditTransaction((TabEdit(position, TabEditIntent.DELETE),)))

    assert state.overrides == {(0, 1, 0): "b"}
    assert state.durations == {(0, 0, 0): 8}
    assert state.dotted == {(0, 0)}
    assert state.ornaments == {(0, 0): "tr"}
    assert state.annotations == {(0, 0): "dolce"}


def test_mixed_note_chord_and_rest_transaction_is_one_undo_unit() -> None:
    state = keyscript_state(style="french")
    before = (copy.deepcopy(state.piece.bars), dict(state.overrides), dict(state.durations), set(state.dotted))
    transaction = TabEditTransaction(
        (
            TabEdit(TabPosition(0, Fraction(0), 1), TabEditIntent.NOTE, fret=1, duration=4),
            TabEdit(TabPosition(0, Fraction(0), 2), TabEditIntent.CHORD, fret=3, duration=4),
            TabEdit(TabPosition(0, Fraction(1, 4)), TabEditIntent.REST, duration=8),
        ),
    )

    apply_tab_transaction(state, transaction)
    after = (copy.deepcopy(state.piece.bars), dict(state.overrides), dict(state.durations), set(state.dotted))
    assert len(state.undo_stack) == 1
    assert after != before

    undo(state, config_path="config.toml")
    assert (state.piece.bars, state.overrides, state.durations, state.dotted) == before
    redo(state, config_path="config.toml")
    assert (state.piece.bars, state.overrides, state.durations, state.dotted) == after
