from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from petrucci.adapters.duet import (
    duet_bar_mapping,
    duet_raw_bar_index,
    duet_staff_labels,
    is_duet_score_piece,
)
from petrucci.core.model import ImportedStaff, Piece

if TYPE_CHECKING:
    from oud.editor.core.state import EditorState


@dataclass(frozen=True)
class ViewStaff:
    key: str
    label: str
    source_index: int | None = None


_IMPORTED_LABELS = {
    "note": "Melody",
    "lyrics": "Lyrics",
}


def _has_tablature(piece: Piece) -> bool:
    return any(bar.chords or bar.notes for bar in piece.bars)


def visible_view_staffs(piece: Piece) -> tuple[ViewStaff, ...]:
    if is_duet_score_piece(piece):
        return tuple(
            ViewStaff(key=f"duet-{index}", label=label, source_index=index)
            for index, label in enumerate(duet_staff_labels(piece))
        )

    staffs: list[ViewStaff] = []
    if _has_tablature(piece) or piece.imported_score is None:
        staffs.append(ViewStaff(key="tab", label="Tab"))
    if piece.imported_score is not None:
        staffs.extend(_imported_view_staffs(piece.imported_score.staffs))
    return tuple(staffs) or (ViewStaff(key="score", label="Score"),)


def _imported_view_staffs(imported_staffs: list[ImportedStaff]) -> tuple[ViewStaff, ...]:
    note_count = sum(staff.kind == "note" for staff in imported_staffs)
    lyric_count = sum(staff.kind == "lyrics" for staff in imported_staffs)
    staffs: list[ViewStaff] = []
    for index, imported in enumerate(imported_staffs):
        label = _imported_staff_label(imported, note_count=note_count, lyric_count=lyric_count)
        if label is not None:
            staffs.append(ViewStaff(key=f"{imported.kind}-{index}", label=label, source_index=index))
    return tuple(staffs)


def _imported_staff_label(imported: ImportedStaff, *, note_count: int, lyric_count: int) -> str | None:
    if imported.kind == "note" and note_count == 1:
        return "Melody"
    if imported.kind == "lyrics" and lyric_count == 1:
        return "Lyrics"
    if imported.kind == "lyrics" and imported.label:
        return f"{imported.label} lyrics"
    return imported.label or _IMPORTED_LABELS.get(imported.kind)


def current_view_staff(state: EditorState) -> ViewStaff:
    staffs = visible_view_staffs(state.piece)
    if is_duet_score_piece(state.piece):
        index, _logical = duet_bar_mapping(state.cursor_bar, piece=state.piece)
        return staffs[min(index, len(staffs) - 1)]
    return staffs[state.view_staff_index % len(staffs)]


def cycle_view_staff(state: EditorState, delta: int) -> bool:
    staffs = visible_view_staffs(state.piece)
    if len(staffs) <= 1:
        return False
    if is_duet_score_piece(state.piece):
        current, logical = duet_bar_mapping(state.cursor_bar, piece=state.piece)
        target = (current + delta) % len(staffs)
        state.cursor_bar = duet_raw_bar_index(target, logical, piece=state.piece)
        state.view_staff_index = target
    else:
        state.view_staff_index = (state.view_staff_index + delta) % len(staffs)
    state.cursor_string = 0
    state.message = f"Focus: {current_view_staff(state).label}"
    return True
