"""What a save cannot keep: editor-side marks that neither file format stores yet (TODO C17)."""

from __future__ import annotations

from oud.editor.core.state import EditorState

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


def dropped_marks_text(state: EditorState) -> str:
    """``2 slurs, 1 ornament`` for the marks a save leaves out; empty when there are none."""

    parts = []
    for singular, plural, attribute in _MARKS:
        count = len(getattr(state, attribute))
        if count:
            parts.append(f"{count} {singular if count == 1 else plural}")
    return ", ".join(parts)
