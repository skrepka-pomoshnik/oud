"""Backend-neutral placement of transient score feedback."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import NoReturn

from oud.petrucci.display import display_width
from oud.petrucci.layout import (
    ElementKey,
    ElementRole,
    LayoutElement,
    LayoutError,
    OnsetPosition,
    Rect,
    ScoreLayout,
    ScoreSystem,
    StaffRows,
)


def with_feedback_annotations(layout: ScoreLayout, annotations: Mapping[str, str]) -> ScoreLayout:
    """Place feedback in reserved staff lanes without mutating cached layout."""

    if not annotations:
        return layout
    systems = tuple(_system_with_feedback(system, layout.onsets, annotations) for system in layout.systems)
    return replace(layout, systems=systems)


def _system_with_feedback(
    system: ScoreSystem,
    onsets: tuple[OnsetPosition, ...],
    annotations: Mapping[str, str],
) -> ScoreSystem:
    extras: list[LayoutElement] = []
    clipped = system.clipped
    for rows in system.staff_rows:
        staff_onsets = sorted(
            (
                onset
                for onset in onsets
                if onset.system_index == system.index
                and onset.staff_id == rows.staff_id
                and onset.event_id in annotations
            ),
            key=lambda onset: (onset.x, onset.event_id),
        )
        if not staff_onsets:
            continue
        if rows.feedback_row is None:
            _fail(f"staff {rows.staff_id!r} has feedback without an allocated row")
        left, right = _staff_bounds(system, rows)
        previous_right = left - 2
        for onset in staff_onsets:
            text = annotations[onset.event_id]
            width = display_width(text)
            desired = max(left, onset.x - (width // 2))
            x = max(desired, previous_right + 2)
            if x > right:
                clipped = True
                continue
            placed_width = min(width, right - x + 1)
            extras.append(
                LayoutElement(
                    ElementKey(onset.event_id, ElementRole.FEEDBACK),
                    Rect(x, rows.feedback_row, placed_width),
                    text,
                ),
            )
            previous_right = x + placed_width - 1
            if placed_width < width:
                clipped = True
                extras.append(
                    LayoutElement(
                        ElementKey(onset.event_id, ElementRole.CLIP_MARKER, 1),
                        Rect(right, rows.feedback_row),
                        "right",
                    ),
                )
    return replace(system, elements=(*system.elements, *extras), clipped=clipped)


def _staff_bounds(system: ScoreSystem, rows: StaffRows) -> tuple[int, int]:
    lines = [
        element.rect
        for element in system.elements
        if element.key.source_id == rows.staff_id and element.key.role is ElementRole.STAFF
    ]
    return min(rect.x for rect in lines), max(rect.right for rect in lines)


def _fail(message: str) -> NoReturn:
    raise LayoutError(message)


__all__ = ["with_feedback_annotations"]
