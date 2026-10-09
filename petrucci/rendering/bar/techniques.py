"""Guitar tab technique marks drawn on the staff row of the note that starts them.

``h`` hammer-on, ``p`` pull-off, ``/`` and ``\\`` slides up and down, ``b`` a bend with the fret it
reaches, ``<fret>`` a natural harmonic. A mark takes only free cells (``-`` or a space) between its
note and the next note of the string, so it never overwrites a fret.
"""

from __future__ import annotations

from collections.abc import Callable

from petrucci.core.model import Chord, Note

_FREE = frozenset({"-", " "})
# French tablature spells frets with letters (h is fret 7, p is fret 11, b is fret 1), so there the
# hammer-on and pull-off are shown by their slur only and a bend by ^.
_ITALIAN_TECHNIQUES = {"hammer-on": "h", "pull-off": "p"}
_BEND = {"italian": "b", "french": "^"}


def _is_free(row: list[str], index: int, limit: int) -> bool:
    return 0 <= index < min(limit, len(row)) and row[index] in _FREE


def _put_all(row: list[str], index: int, text: str, limit: int) -> int:
    """Write ``text`` into the free cells from ``index`` or leave the row alone; returns the next cell."""

    if not text or not all(_is_free(row, index + offset, limit) for offset in range(len(text))):
        return index
    for offset, char in enumerate(text):
        row[index + offset] = char
    return index + len(text)


def _label_cells(row: list[str], start: int, label: str) -> int:
    """Cells a fret label takes: one when a scaled bar keeps it whole, else one per character."""

    if 0 <= start < len(row) and row[start] == label:
        return 1
    return len(label)


def _note_on(chord: Chord, string: int) -> Note | None:
    return next((note for note in chord.notes if note.string == string), None)


def _slide_char(note: Note, following: Note | None) -> str:
    return "\\" if following is not None and following.fret < note.fret else "/"


def _technique_text(note: Note, following: Note | None, style: str) -> str:
    if note.technique == "slide":
        return _slide_char(note, following)
    return _ITALIAN_TECHNIQUES.get(note.technique or "", "") if style != "french" else ""


def _bend_texts(note: Note, label_for: Callable[[Note], str], style: str) -> list[str]:
    """What follows a bent note: the bend sign with the fret it reaches when it fits, else the sign alone."""

    if note.bend is None:
        return []
    sign = _BEND["french" if style == "french" else "italian"]
    if style == "french":
        return [sign]
    return [sign + label_for(Note(note.string, note.fret + round(note.bend), 0)), sign]


def overlay_technique_marks(
    row: list[str],
    *,
    bar_chords: list[Chord],
    string: int,
    columns: list[int],
    to_display: Callable[[int], int],
    label_for: Callable[[Note], str],
    style: str = "italian",
) -> None:
    """Draw the marks of the notes on course ``string`` (1 is the highest) into one display row."""

    notes = [
        (index, note)
        for index, chord in enumerate(bar_chords[: len(columns)])
        if (note := _note_on(chord, string)) is not None
    ]
    for position, (index, note) in enumerate(notes):
        following = notes[position + 1][1] if position + 1 < len(notes) else None
        start = to_display(columns[index])
        end = start + _label_cells(row, start, label_for(note))
        limit = to_display(columns[notes[position + 1][0]]) if following is not None else len(row)
        if note.harmonic and _is_free(row, start - 1, len(row)) and _is_free(row, end, len(row)):
            row[start - 1], row[end] = "<", ">"
            end += 1
        end = _put_all(row, end, _technique_text(note, following, style), limit)
        for text in _bend_texts(note, label_for, style):
            if _put_all(row, end, text, limit) != end:
                break
