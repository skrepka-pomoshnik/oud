"""What a save cannot keep: editor-side marks that neither file format stores yet (TODO C17)."""

from __future__ import annotations

from collections import Counter

from oud.editor.core.state import EditorState
from petrucci.core.model import Note

_PLURALS = {"hammer-on": "hammer-ons", "pull-off": "pull-offs"}
# (singular, plural, attribute of EditorState)
_MARKS = (
    ("slur", "slurs", "slurs"),
    ("tie", "ties", "ties"),
    ("hold", "holds", "holds"),
    ("glissando", "glissandi", "glisses"),
    ("ornament", "ornaments", "ornaments"),
    ("annotation", "annotations", "annotations"),
    ("highlight", "highlights", "highlights"),
)


def _tab_note_marks(state: EditorState) -> list[str]:
    """Marks on notes that MusicXML keeps and TAB has no syntax for, as ``2 ties``."""

    counts: Counter[str] = Counter()
    for bar in state.piece.bars:
        for chord in bar.chords:
            for note in chord.notes:
                counts.update(name for name, present in _note_marks(note) if present)
    return [f"{count} {name if count == 1 else _PLURALS.get(name, name + 's')}" for name, count in counts.items()]


def _note_marks(note: Note) -> tuple[tuple[str, bool], ...]:
    return (
        ("tie", note.tie is not None),
        (note.technique or "technique", note.technique is not None),
        ("bend", note.bend is not None),
        ("harmonic", note.harmonic),
    )


def dropped_marks_text(state: EditorState, *, tab: bool = False) -> str:
    """``2 slurs, 1 ornament`` for the marks a save leaves out; empty when there are none."""

    parts = _tab_note_marks(state) if tab else []
    for singular, plural, attribute in _MARKS:
        count = len(getattr(state, attribute))
        if count:
            parts.append(f"{count} {singular if count == 1 else plural}")
    return ", ".join(parts)
