from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import pytest

from oud.editor.editing.primitives.edits import apply_tab_transaction
from oud.exports.export_tab import export_tab
from oud.exports.lilypond import export_lilypond
from oud.exports.midi import export_midi
from oud.importers.tab import load_tab
from petrucci import TabEdit, TabEditIntent, TabEditTransaction, TabPosition
from petrucci.input.tablature.input import editor_fret_at
from tests.helpers_keyscript import keyscript_state, render_lines

EventSignature = tuple[tuple[tuple[int, int], ...], ...]


@dataclass(frozen=True)
class _SequenceArtifacts:
    cells: tuple[tuple[tuple[int, int, int], str], ...]
    durations: tuple[tuple[tuple[int, int, int], int], ...]
    decoded_events: EventSignature
    rendered_rows: tuple[str, ...]
    tab_events: EventSignature
    tab_text: str
    lilypond_text: str
    midi_bytes: bytes


def _operation_sequence() -> TabEditTransaction:
    return TabEditTransaction(
        (
            TabEdit(TabPosition(0, Fraction(0), 1), TabEditIntent.NOTE, fret=0, duration=4),
            TabEdit(TabPosition(0, Fraction(0), 3), TabEditIntent.CHORD, fret=2, duration=4),
            TabEdit(TabPosition(0, Fraction(1, 4), 7), TabEditIntent.NOTE, fret=1, duration=4),
            TabEdit(TabPosition(0, Fraction(1, 2), 2), TabEditIntent.NOTE, fret=3, duration=4),
            TabEdit(TabPosition(0, Fraction(3, 4), 1), TabEditIntent.NOTE, fret=5, duration=4),
        ),
    )


def _decoded_editor_events(state) -> EventSignature:
    events: list[tuple[tuple[int, int], ...]] = []
    columns = sorted({column for bar, _string, column in state.durations if bar == 0})
    for column in columns:
        notes: list[tuple[int, int]] = []
        for string in range(state.piece.strings):
            fret = editor_fret_at(
                state.overrides,
                state.durations,
                bar_index=0,
                string_index=string,
                column=column,
                style=state.settings["style"],
            )
            if fret is not None:
                notes.append((string + 1, fret))
        events.append(tuple(notes))
    return tuple(events)


def _piece_events(piece) -> EventSignature:
    return tuple(
        tuple(sorted((note.string, note.fret) for note in chord.notes)) for bar in piece.bars for chord in bar.chords
    )


def _run_sequence(style: str, directory: Path) -> _SequenceArtifacts:
    directory.mkdir()
    tuning = "g2c3f3a3d4g4d2"
    state = keyscript_state(
        strings=7,
        style=style,
        bar_width=12,
        settings_override={"tuning": tuning, "time": "4/4", "key": "C"},
    )
    apply_tab_transaction(state, _operation_sequence())
    export_settings = {"style": style, "tuning": tuning, "time": "4/4", "key": "C"}

    tab_text = export_tab(
        state.piece,
        state.overrides,
        state.durations,
        state.bar_width,
        settings=export_settings,
        dotted=state.dotted,
    )
    tab_path = directory / "sequence.tab"
    tab_path.write_text(tab_text, encoding="utf-8")
    reopened = load_tab(str(tab_path), strings=7)

    lilypond_path = directory / "sequence.ly"
    export_lilypond(
        str(lilypond_path),
        state.piece,
        state.overrides,
        state.durations,
        state.bar_width,
        settings=export_settings,
    )
    midi_path = directory / "sequence.mid"
    export_midi(
        str(midi_path),
        state.piece,
        state.overrides,
        state.durations,
        state.bar_width,
        settings=export_settings,
        dotted=state.dotted,
    )

    rendered = tuple(line.rstrip() for line in render_lines(state, width=72, height=22) if "|" in line)
    return _SequenceArtifacts(
        cells=tuple(sorted(state.overrides.items())),
        durations=tuple(sorted(state.durations.items())),
        decoded_events=_decoded_editor_events(state),
        rendered_rows=rendered,
        tab_events=_piece_events(reopened),
        tab_text=tab_text,
        lilypond_text=lilypond_path.read_text(encoding="utf-8"),
        midi_bytes=midi_path.read_bytes(),
    )


@pytest.mark.parametrize("style", ["french", "italian"])
def test_operation_sequence_is_deterministic_across_render_and_exports(style: str, tmp_path: Path) -> None:
    first = _run_sequence(style, tmp_path / "first")
    second = _run_sequence(style, tmp_path / "second")
    expected = (((1, 0), (3, 2)), ((7, 1),), ((2, 3),), ((1, 5),))

    assert first == second
    assert first.decoded_events == expected
    assert first.tab_events == expected
    assert first.rendered_rows
    assert "\\new TabStaff" in first.lilypond_text
    assert first.midi_bytes.startswith(b"MThd")
    assert first.midi_bytes[14:18] == b"MTrk"
