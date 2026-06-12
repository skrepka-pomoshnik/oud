from __future__ import annotations

import copy
from typing import TypeVar

from oud.core.model import Bar
from oud.editor.state import BarSnapshot, EditorState

T = TypeVar("T")


def _shift_triplet_dict(
    mapping: dict[tuple[int, int, int], T],
    start: int,
    delta: int,
    remove_index: int | None = None,
) -> dict[tuple[int, int, int], T]:
    updated: dict[tuple[int, int, int], T] = {}
    for (bar, string, col), value in mapping.items():
        if remove_index is not None and bar == remove_index:
            continue
        if bar >= start:
            updated[(bar + delta, string, col)] = value
        else:
            updated[(bar, string, col)] = value
    return updated


def _shift_triplet_set(
    entries: set[tuple[int, int, int]],
    start: int,
    delta: int,
    remove_index: int | None = None,
) -> set[tuple[int, int, int]]:
    updated: set[tuple[int, int, int]] = set()
    for bar, string, col in entries:
        if remove_index is not None and bar == remove_index:
            continue
        if bar >= start:
            updated.add((bar + delta, string, col))
        else:
            updated.add((bar, string, col))
    return updated


def _shift_pair_dict(
    mapping: dict[tuple[int, int], T],
    start: int,
    delta: int,
    remove_index: int | None = None,
) -> dict[tuple[int, int], T]:
    updated: dict[tuple[int, int], T] = {}
    for (bar, col), value in mapping.items():
        if remove_index is not None and bar == remove_index:
            continue
        if bar >= start:
            updated[(bar + delta, col)] = value
        else:
            updated[(bar, col)] = value
    return updated


def _shift_pair_set(
    entries: set[tuple[int, int]],
    start: int,
    delta: int,
    remove_index: int | None = None,
) -> set[tuple[int, int]]:
    updated: set[tuple[int, int]] = set()
    for bar, col in entries:
        if remove_index is not None and bar == remove_index:
            continue
        if bar >= start:
            updated.add((bar + delta, col))
        else:
            updated.add((bar, col))
    return updated


def _shift_spans(
    spans: list[tuple[int, int, int]],
    start: int,
    delta: int,
    remove_index: int | None = None,
) -> list[tuple[int, int, int]]:
    updated: list[tuple[int, int, int]] = []
    for bar, start_col, end_col in spans:
        if remove_index is not None and bar == remove_index:
            continue
        if bar >= start:
            updated.append((bar + delta, start_col, end_col))
        else:
            updated.append((bar, start_col, end_col))
    return updated


def _shift_marks(
    marks: dict[str, tuple[int, int, int]],
    start: int,
    delta: int,
    remove_index: int | None = None,
) -> dict[str, tuple[int, int, int]]:
    updated: dict[str, tuple[int, int, int]] = {}
    for name, (bar, string, col) in marks.items():
        if remove_index is not None and bar == remove_index:
            continue
        if bar >= start:
            updated[name] = (bar + delta, string, col)
        else:
            updated[name] = (bar, string, col)
    return updated


def snapshot_bar(state: EditorState, index: int) -> BarSnapshot:
    bar = copy.deepcopy(state.piece.bars[index])
    overrides = {k: v for k, v in state.overrides.items() if k[0] == index}
    durations = {k: v for k, v in state.durations.items() if k[0] == index}
    annotations = {k: v for k, v in state.annotations.items() if k[0] == index}
    ornaments = {k: v for k, v in state.ornaments.items() if k[0] == index}
    highlights = {k for k in state.highlights if k[0] == index}
    dotted = {k for k in state.dotted if k[0] == index}
    slurs = [s for s in state.slurs if s[0] == index]
    ties = [s for s in state.ties if s[0] == index]
    holds = [s for s in state.holds if s[0] == index]
    glisses = [s for s in state.glisses if s[0] == index]
    marks = {
        name: (0, string, col)
        for name, (bar_idx, string, col) in state.marks.items()
        if bar_idx == index
    }
    return {
        "bar": bar,
        "overrides": overrides,
        "durations": durations,
        "annotations": annotations,
        "ornaments": ornaments,
        "highlights": highlights,
        "dotted": dotted,
        "slurs": slurs,
        "ties": ties,
        "holds": holds,
        "glisses": glisses,
        "marks": marks,
    }


def _remove_bar_entries(state: EditorState, index: int) -> None:
    state.overrides = {k: v for k, v in state.overrides.items() if k[0] != index}
    state.durations = {k: v for k, v in state.durations.items() if k[0] != index}
    state.annotations = {k: v for k, v in state.annotations.items() if k[0] != index}
    state.ornaments = {k: v for k, v in state.ornaments.items() if k[0] != index}
    state.highlights = {k for k in state.highlights if k[0] != index}
    state.dotted = {k for k in state.dotted if k[0] != index}
    state.slurs = [s for s in state.slurs if s[0] != index]
    state.ties = [s for s in state.ties if s[0] != index]
    state.holds = [s for s in state.holds if s[0] != index]
    state.glisses = [s for s in state.glisses if s[0] != index]
    state.marks = {
        name: value for name, value in state.marks.items() if value[0] != index
    }


def clear_bar_contents(state: EditorState, index: int) -> None:
    state.piece.bars[index] = Bar()
    _remove_bar_entries(state, index)


def restore_bar_snapshot(state: EditorState, index: int, snapshot: BarSnapshot) -> None:
    if "bar" in snapshot:
        state.piece.bars[index] = copy.deepcopy(snapshot["bar"])
    _remove_bar_entries(state, index)
    state.overrides.update(snapshot["overrides"])
    state.durations.update(snapshot["durations"])
    state.annotations.update(snapshot["annotations"])
    state.ornaments.update(snapshot["ornaments"])
    state.highlights |= snapshot["highlights"]
    state.dotted |= snapshot["dotted"]
    state.slurs.extend(snapshot["slurs"])
    state.ties.extend(snapshot["ties"])
    state.holds.extend(snapshot["holds"])
    state.glisses.extend(snapshot["glisses"])
    for name, (bar, string, col) in snapshot["marks"].items():
        state.marks[name] = (index + bar, string, col)


def insert_bar(state: EditorState, index: int) -> None:
    index = max(0, min(index, len(state.piece.bars)))
    state.piece.bars.insert(index, Bar())
    state.overrides = _shift_triplet_dict(state.overrides, index, 1)
    state.durations = _shift_triplet_dict(state.durations, index, 1)
    state.highlights = _shift_triplet_set(state.highlights, index, 1)
    state.annotations = _shift_pair_dict(state.annotations, index, 1)
    state.ornaments = _shift_pair_dict(state.ornaments, index, 1)
    state.dotted = _shift_pair_set(state.dotted, index, 1)
    state.slurs = _shift_spans(state.slurs, index, 1)
    state.ties = _shift_spans(state.ties, index, 1)
    state.holds = _shift_spans(state.holds, index, 1)
    state.glisses = _shift_spans(state.glisses, index, 1)
    state.marks = _shift_marks(state.marks, index, 1)
    state.stave_breaks = {b + 1 if b >= index else b for b in state.stave_breaks}
    state.modified = True


def delete_bar(state: EditorState, index: int) -> None:
    if not state.piece.bars:
        state.piece.bars.append(Bar())
        return
    if len(state.piece.bars) == 1:
        state.piece.bars[0] = Bar()
        state.overrides.clear()
        state.durations.clear()
        state.highlights.clear()
        state.annotations.clear()
        state.ornaments.clear()
        state.dotted.clear()
        state.slurs.clear()
        state.ties.clear()
        state.holds.clear()
        state.glisses.clear()
        state.marks.clear()
        state.modified = True
        return
    index = max(0, min(index, len(state.piece.bars) - 1))
    state.piece.bars.pop(index)
    state.overrides = _shift_triplet_dict(state.overrides, index + 1, -1, remove_index=index)
    state.durations = _shift_triplet_dict(state.durations, index + 1, -1, remove_index=index)
    state.highlights = _shift_triplet_set(state.highlights, index + 1, -1, remove_index=index)
    state.annotations = _shift_pair_dict(state.annotations, index + 1, -1, remove_index=index)
    state.ornaments = _shift_pair_dict(state.ornaments, index + 1, -1, remove_index=index)
    state.dotted = _shift_pair_set(state.dotted, index + 1, -1, remove_index=index)
    state.slurs = _shift_spans(state.slurs, index + 1, -1, remove_index=index)
    state.ties = _shift_spans(state.ties, index + 1, -1, remove_index=index)
    state.holds = _shift_spans(state.holds, index + 1, -1, remove_index=index)
    state.glisses = _shift_spans(state.glisses, index + 1, -1, remove_index=index)
    state.marks = _shift_marks(state.marks, index + 1, -1, remove_index=index)
    state.stave_breaks = {b - 1 if b > index else b for b in state.stave_breaks if b != index}
    state.modified = True
