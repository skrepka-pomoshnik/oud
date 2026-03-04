from __future__ import annotations

import copy
from contextlib import contextmanager

from oud.editor.ops import chord_index_at_col, set_chord_note
from oud.editor.state import EditorState, UndoAction, UndoGroupFrame


def record_action(state: EditorState, action: UndoAction) -> None:
    if state.undo_group_stack:
        state.undo_group_stack[-1].actions.append(action)
        state.modified = True
        return
    state.undo_stack.append(action)
    state.redo_stack.clear()
    state.modified = True


def begin_undo_group(state: EditorState, *, label: str | None = None) -> None:
    state.undo_group_stack.append(UndoGroupFrame(label=label))


def end_undo_group(state: EditorState) -> bool:
    if not state.undo_group_stack:
        return False
    frame = state.undo_group_stack.pop()
    if not frame.actions:
        return False
    group_action = UndoAction(
        kind="group",
        data={"label": frame.label, "actions": frame.actions},
    )
    if state.undo_group_stack:
        state.undo_group_stack[-1].actions.append(group_action)
        state.modified = True
        return True
    state.undo_stack.append(group_action)
    state.redo_stack.clear()
    state.modified = True
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
    prev = state.overrides.get(key)
    state.overrides[key] = ch
    record_undo(state, "override", key, prev, ch)


def apply_duration(state: EditorState, key: tuple[int, int, int], dur: int) -> None:
    bar, string, col = key
    prev = {k: v for k, v in state.durations.items() if k[0] == bar and k[2] == col}
    state.durations[(bar, string, col)] = dur
    new = dict(prev)
    new[(bar, string, col)] = dur
    record_action(
        state,
        UndoAction(
            kind="duration_col",
            data={"bar": bar, "col": col, "prev": prev, "new": new},
        ),
    )


def clear_cell(state: EditorState, bar: int, string: int, col: int) -> None:
    with undo_group(state, label="clear-cell"):
        if 0 <= bar < len(state.piece.bars):
            bar_obj = state.piece.bars[bar]
            if bar_obj.chords:
                prev_chords = copy.deepcopy(bar_obj.chords)
                if set_chord_note(bar_obj, state.bar_width, col, string + 1, None):
                    new_chords = copy.deepcopy(bar_obj.chords)
                    record_action(
                        state,
                        UndoAction(
                            kind="chords",
                            data={"bar": bar, "prev": prev_chords, "new": new_chords},
                        ),
                    )
                    state.modified = True
        key = (bar, string, col)
        if key in state.overrides:
            prev = state.overrides.get(key)
            state.overrides.pop(key, None)
            record_undo(state, "override", key, prev, None)
        prev_durations = {k: v for k, v in state.durations.items() if k[0] == bar and k[2] == col}
        if prev_durations:
            for prev_key in prev_durations:
                state.durations.pop(prev_key, None)
            record_action(
                state,
                UndoAction(
                    kind="duration_col",
                    data={"bar": bar, "col": col, "prev": prev_durations, "new": {}},
                ),
            )
        dot_key = (bar, col)
        if dot_key in state.dotted:
            record_action(
                state,
                UndoAction(
                    kind="dotted",
                    data={"key": dot_key, "prev": True, "new": False},
                ),
            )
            state.dotted.discard(dot_key)
        state.modified = True


def _column_has_notes(state: EditorState, bar: int, col: int) -> bool:
    for (b, _s, c) in state.overrides:
        if b == bar and c == col:
            return True
    if 0 <= bar < len(state.piece.bars):
        bar_obj = state.piece.bars[bar]
        if bar_obj.chords:
            idx = chord_index_at_col(bar_obj, state.bar_width, col)
            if idx is not None and bar_obj.chords[idx].notes:
                return True
    return False


def clear_cell_note(state: EditorState, bar: int, string: int, col: int) -> None:
    with undo_group(state, label="clear-cell-note"):
        if 0 <= bar < len(state.piece.bars):
            bar_obj = state.piece.bars[bar]
            if bar_obj.chords:
                prev_chords = copy.deepcopy(bar_obj.chords)
                if set_chord_note(bar_obj, state.bar_width, col, string + 1, None):
                    new_chords = copy.deepcopy(bar_obj.chords)
                    record_action(
                        state,
                        UndoAction(
                            kind="chords",
                            data={"bar": bar, "prev": prev_chords, "new": new_chords},
                        ),
                    )
                    state.modified = True
        key = (bar, string, col)
        if key in state.overrides:
            prev = state.overrides.get(key)
            state.overrides.pop(key, None)
            record_undo(state, "override", key, prev, None)
        if not _column_has_notes(state, bar, col):
            prev_durations = {
                k: v for k, v in state.durations.items() if k[0] == bar and k[2] == col
            }
            if prev_durations:
                for prev_key in prev_durations:
                    state.durations.pop(prev_key, None)
                record_action(
                    state,
                    UndoAction(
                        kind="duration_col",
                        data={"bar": bar, "col": col, "prev": prev_durations, "new": {}},
                    ),
                )
            dot_key = (bar, col)
            if dot_key in state.dotted:
                record_action(
                    state,
                    UndoAction(
                        kind="dotted",
                        data={"key": dot_key, "prev": True, "new": False},
                    ),
                )
                state.dotted.discard(dot_key)
        state.modified = True
