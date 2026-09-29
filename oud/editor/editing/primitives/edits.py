from __future__ import annotations

import copy
from contextlib import contextmanager
from fractions import Fraction

from oud.editor.core.state import EditorState, UndoAction, UndoGroupFrame
from petrucci.input.tablature.grid import (
    EditableTablature,
    TabMutation,
    clear_tab_cell,
    clear_tab_note,
    set_tab_cell,
    set_tab_duration,
)
from petrucci.input.tablature.mutation import (
    TabDocument,
    TabEditTransaction,
    TabMutationResult,
    apply_tab_mutation,
)


def _cursor_snapshot(state: EditorState) -> tuple[int, int, Fraction]:
    return (state.cursor_bar, state.cursor_string, state.cursor_onset)


def _mark_modified_from_clean_depth(state: EditorState) -> None:
    state.modified = len(state.undo_stack) != state.clean_undo_depth


def _annotate_action_cursor(
    state: EditorState,
    action: UndoAction,
    *,
    cursor_before: tuple[int, int, int] | None = None,
) -> None:
    cursor = _cursor_snapshot(state)
    action.data.setdefault("cursor_before", cursor_before or cursor)
    action.data.setdefault("cursor_after", cursor)


def record_action(state: EditorState, action: UndoAction) -> None:
    if state.undo_group_stack:
        _annotate_action_cursor(state, action)
        state.undo_group_stack[-1].actions.append(action)
        state.modified = True
        return
    _annotate_action_cursor(state, action)
    state.undo_stack.append(action)
    state.redo_stack.clear()
    _mark_modified_from_clean_depth(state)


def begin_undo_group(state: EditorState, *, label: str | None = None) -> None:
    state.undo_group_stack.append(
        UndoGroupFrame(label=label, cursor_before=_cursor_snapshot(state)),
    )


def end_undo_group(state: EditorState) -> bool:
    if not state.undo_group_stack:
        return False
    frame = state.undo_group_stack.pop()
    if not frame.actions:
        return False
    group_action = UndoAction(
        kind="group",
        data={
            "label": frame.label,
            "actions": frame.actions,
            "cursor_before": frame.cursor_before,
            "cursor_after": _cursor_snapshot(state),
        },
    )
    if state.undo_group_stack:
        state.undo_group_stack[-1].actions.append(group_action)
        state.modified = True
        return True
    state.undo_stack.append(group_action)
    state.redo_stack.clear()
    _mark_modified_from_clean_depth(state)
    return True


@contextmanager
def undo_group(state: EditorState, *, label: str | None = None):
    begin_undo_group(state, label=label)
    try:
        yield
    finally:
        end_undo_group(state)


def record_undo(
    state: EditorState,
    kind: str,
    key: tuple[int, int, int],
    prev: object | None,
    new: object | None,
) -> None:
    record_action(
        state,
        UndoAction(
            kind=kind,
            data={"key": key, "prev": prev, "new": new},
        ),
    )


def apply_override(state: EditorState, key: tuple[int, int, int], ch: str) -> None:
    _record_tab_mutation(state, set_tab_cell(_editable_tablature(state), key, ch))


def apply_duration(state: EditorState, key: tuple[int, int, int], dur: int) -> None:
    _record_tab_mutation(state, set_tab_duration(_editable_tablature(state), key, dur))


def apply_tab_transaction(state: EditorState, transaction: TabEditTransaction) -> TabMutationResult:
    """Apply an onset transaction to the bar chords as one undo step."""

    document = TabDocument(
        state.piece.bars,
        state.piece.strings,
        state.settings.get("style") or state.piece.style or "french",
        default_meter=state.settings.get("time"),
    )
    result = apply_tab_mutation(document, transaction)
    with undo_group(state, label="tab-transaction"):
        for delta in result.changes:
            record_action(
                state,
                UndoAction(
                    kind="chords",
                    data={
                        "bar": delta.bar_index,
                        "prev": list(delta.before),
                        "new": copy.deepcopy(list(delta.after)),
                        "mirror_notes": True,
                    },
                ),
            )
    return result


def clear_cell(state: EditorState, bar: int, string: int, col: int) -> None:
    with undo_group(state, label="clear-cell"):
        _record_tab_mutation(state, clear_tab_cell(_editable_tablature(state), (bar, string, col)))


def clear_cell_note(state: EditorState, bar: int, string: int, col: int) -> None:
    with undo_group(state, label="clear-cell-note"):
        _record_tab_mutation(state, clear_tab_note(_editable_tablature(state), (bar, string, col)))


def _editable_tablature(state: EditorState) -> EditableTablature:
    return EditableTablature(
        state.piece.bars,
        state.piece.strings,
        state.bar_width,
        state.overrides,
        state.durations,
        state.dotted,
        state.settings.get("style") or state.piece.style or "french",
    )


def _record_tab_mutation(state: EditorState, mutation: TabMutation) -> None:
    for delta in mutation.chords:
        record_action(
            state,
            UndoAction(
                kind="chords",
                data={
                    "bar": delta.bar_index,
                    "prev": copy.deepcopy(list(delta.before)),
                    "new": copy.deepcopy(list(delta.after)),
                },
            ),
        )
    for delta in mutation.cells:
        record_undo(state, "override", delta.key, delta.before, delta.after)
    for delta in mutation.rhythms:
        record_action(
            state,
            UndoAction(
                kind="duration_col",
                data={
                    "bar": delta.bar_index,
                    "col": delta.column,
                    "prev": dict(delta.before),
                    "new": dict(delta.after),
                },
            ),
        )
    for delta in mutation.dots:
        record_action(
            state,
            UndoAction(
                kind="dotted",
                data={"key": delta.key, "prev": delta.before, "new": delta.after},
            ),
        )
