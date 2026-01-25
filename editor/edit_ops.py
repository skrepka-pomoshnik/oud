from __future__ import annotations

import copy

from editor.ops import set_chord_note
from editor.state import EditorState, UndoAction


def record_action(state: EditorState, action: UndoAction) -> None:
    state.undo_stack.append(action)
    state.redo_stack.clear()
    state.modified = True


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
    bar, _string, col = key
    prev = {k: v for k, v in state.durations.items() if k[0] == bar and k[2] == col}
    for prev_key in prev:
        state.durations.pop(prev_key, None)
    new_key = (bar, 0, col)
    state.durations[new_key] = dur
    record_action(
        state,
        UndoAction(
            kind="duration_col",
            data={"bar": bar, "col": col, "prev": prev, "new": {new_key: dur}},
        ),
    )


def clear_cell(state: EditorState, bar: int, string: int, col: int) -> None:
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
