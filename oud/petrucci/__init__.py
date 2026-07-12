"""Petrucci: reusable ASCII tablature and staff-note typesetting."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from oud.petrucci.model import (
    Bar,
    Chord,
    ImportedBarContent,
    ImportedScore,
    ImportedSourceRecord,
    ImportedStaff,
    ImportedTextRow,
    LyricEvent,
    MelodyEvent,
    Note,
    Piece,
)

if TYPE_CHECKING:
    from oud.petrucci.typeset import TypesetOptions, TypesetResult

__all__ = [
    "Bar",
    "Chord",
    "ImportedBarContent",
    "ImportedScore",
    "ImportedSourceRecord",
    "ImportedStaff",
    "ImportedTextRow",
    "LyricEvent",
    "MelodyEvent",
    "Note",
    "Piece",
    "TypesetOptions",
    "TypesetResult",
    "typeset_piece",
    "typeset_text",
]


def __getattr__(name: str) -> Any:
    if name in {"TypesetOptions", "TypesetResult"}:
        from oud.petrucci import typeset  # noqa: PLC0415

        return getattr(typeset, name)
    raise AttributeError(name)


def typeset_piece(*args, **kwargs):
    from oud.petrucci.typeset import typeset_piece as _typeset_piece  # noqa: PLC0415

    return _typeset_piece(*args, **kwargs)


def typeset_text(*args, **kwargs):
    from oud.petrucci.typeset import typeset_text as _typeset_text  # noqa: PLC0415

    return _typeset_text(*args, **kwargs)
