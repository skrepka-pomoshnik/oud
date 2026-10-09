"""Hammer-ons, pull-offs, slides, bends and harmonics are drawn on the staff row of their note."""

from __future__ import annotations

from oud.editor.services.screen.compose import compose_editor_frame
from petrucci.core.model import Bar, Chord, Note, Piece
from petrucci.rendering.bar.techniques import overlay_technique_marks
from tests.helpers_keyscript import keyscript_state


def _chord(*notes: Note) -> Chord:
    return Chord(5, False, None, list(notes))


def _label(note: Note) -> str:
    return str(note.fret)


def _marked(chords: list[Chord], width: int = 24, style: str = "italian") -> str:
    row = ["-"] * width
    columns = [index * 4 for index in range(len(chords))]
    for chord, column in zip(chords, columns, strict=True):
        for note in chord.notes:
            if note.string == 1:
                row[column + 1] = str(note.fret)  # a one-digit label in the cell after the lead dash
    overlay_technique_marks(
        row,
        bar_chords=chords,
        string=1,
        columns=columns,
        to_display=lambda column: column + 1,
        label_for=_label,
        style=style,
    )
    return "".join(row)


def test_a_hammer_on_and_a_pull_off_show_their_letter_after_the_note() -> None:
    chords = [
        _chord(Note(1, 5, 0, technique="hammer-on")),
        _chord(Note(1, 7, 0, technique="pull-off")),
        _chord(Note(1, 5, 0)),
    ]

    assert _marked(chords).startswith("-5h--7p--5")


def test_a_slide_points_toward_the_next_fret() -> None:
    up = [_chord(Note(1, 5, 0, technique="slide")), _chord(Note(1, 7, 0))]
    down = [_chord(Note(1, 7, 0, technique="slide")), _chord(Note(1, 5, 0))]

    assert _marked(up).startswith("-5/--7")
    assert _marked(down).startswith("-7\\--5")


def test_a_bend_shows_the_fret_it_reaches() -> None:
    chords = [_chord(Note(1, 7, 0, bend=2.0)), _chord(Note(1, 5, 0))]

    assert _marked(chords, width=40).startswith("-7b9-5")


def test_a_bend_that_does_not_fit_keeps_only_its_sign() -> None:
    chords = [_chord(Note(1, 7, 0, bend=2.0)), _chord(Note(1, 5, 0))]
    row = ["-"] * 12
    row[1], row[3] = "7", "5"
    overlay_technique_marks(
        row,
        bar_chords=chords,
        string=1,
        columns=[0, 2],
        to_display=lambda column: column + 1,
        label_for=_label,
    )

    assert "".join(row).startswith("-7b5")


def test_a_harmonic_is_wrapped_in_angle_brackets() -> None:
    chords = [_chord(Note(1, 9, 0, harmonic=True))]

    assert "<9>" in _marked(chords)


def test_a_mark_never_overwrites_a_fret() -> None:
    chords = [_chord(Note(1, 5, 0, technique="hammer-on")), _chord(Note(1, 7, 0))]
    row = ["-"] * 6
    row[1], row[2] = "5", "7"
    overlay_technique_marks(
        row,
        bar_chords=chords,
        string=1,
        columns=[0, 1],
        to_display=lambda column: column + 1,
        label_for=_label,
    )

    assert "".join(row) == "-57---"


def test_french_tablature_avoids_marks_that_are_fret_letters() -> None:
    chords = [_chord(Note(1, 5, 0, technique="hammer-on")), _chord(Note(1, 7, 0, bend=1.0))]

    marked = _marked(chords, width=30, style="french")

    assert "h" not in marked and "p" not in marked and "b" not in marked
    assert "^" in marked


def _frame(**settings: str) -> str:
    chords = [
        _chord(Note(2, 5, 0, technique="hammer-on")),
        _chord(Note(2, 7, 0, bend=1.0)),
        _chord(Note(1, 12, 0, harmonic=True)),
    ]
    piece = Piece(title="T", bars=[Bar(chords=chords, time_sig="4/4")], strings=6, style="italian")
    state = keyscript_state(
        piece=piece,
        width=80,
        height=20,
        settings_override={"style": "italian", "fretlabelmode": "numeric", **settings},
    )
    return "\n".join(compose_editor_frame(state, height=20, width=80).frame.lines)


def test_the_marks_reach_the_rendered_score() -> None:
    frame = _frame()

    assert "5h" in frame and "7b8" in frame and "<12>" in frame


def test_the_marks_can_be_switched_off() -> None:
    frame = _frame(showtechniques="off")

    assert "5h" not in frame and "<12>" not in frame
