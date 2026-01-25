from __future__ import annotations

import copy
from typing import cast

from editor.bar_ops import clear_bar_contents, delete_bar, insert_bar, restore_bar_snapshot
from editor.state import BarSnapshot, EditorState, UndoAction
from settings import save_settings


def apply_action(  # noqa: C901, PLR0911, PLR0912
    state: EditorState,
    action: UndoAction,
    *,
    redo: bool,
    config_path: str,
) -> None:
    kind = action.kind
    data = action.data
    if kind == "override":
        key = cast(tuple[int, int, int], data["key"])
        value = cast(str | None, data["new"] if redo else data["prev"])
        if value is None:
            state.overrides.pop(key, None)
        else:
            state.overrides[key] = value
        return
    if kind == "duration":
        key = cast(tuple[int, int, int], data["key"])
        value = cast(int | None, data["new"] if redo else data["prev"])
        if value is None:
            state.durations.pop(key, None)
        else:
            state.durations[key] = value
        return
    if kind == "duration_col":
        bar = cast(int, data["bar"])
        col = cast(int, data["col"])
        payload = cast(dict[tuple[int, int, int], int], data["new"] if redo else data["prev"])
        for existing in [k for k in state.durations if k[0] == bar and k[2] == col]:
            state.durations.pop(existing, None)
        state.durations.update(payload)
        return
    if kind == "dotted":
        key = cast(tuple[int, int], data["key"])
        value = cast(bool, data["new"] if redo else data["prev"])
        if value:
            state.dotted.add(key)
        else:
            state.dotted.discard(key)
        return
    if kind in ("ornament", "annotation"):
        key = cast(tuple[int, int], data["key"])
        value = cast(str | None, data["new"] if redo else data["prev"])
        target = state.ornaments if kind == "ornament" else state.annotations
        if value is None:
            target.pop(key, None)
        else:
            target[key] = value
        return
    if kind == "highlight":
        key = cast(tuple[int, int, int], data["key"])
        value = cast(bool, data["new"] if redo else data["prev"])
        if value:
            state.highlights.add(key)
        else:
            state.highlights.discard(key)
        return
    if kind in ("barline", "repeat", "timesig"):
        bar_index = cast(int, data["bar"])
        value = cast(str | None, data["new"] if redo else data["prev"])
        if 0 <= bar_index < len(state.piece.bars):
            bar = state.piece.bars[bar_index]
            if kind == "barline":
                bar.barline = value if isinstance(value, str) else None
            elif kind == "repeat":
                bar.repeat = value if isinstance(value, str) else None
            else:
                bar.time_sig = value if isinstance(value, str) else None
                setting_value = cast(
                    str | None,
                    data.get("setting_new") if redo else data.get("setting_prev"),
                )
                if setting_value is None:
                    state.settings.pop("time", None)
                else:
                    state.settings["time"] = setting_value
        return
    if kind == "chords":
        bar_index = cast(int, data["bar"])
        value = cast(list | None, data["new"] if redo else data["prev"])
        if 0 <= bar_index < len(state.piece.bars):
            state.piece.bars[bar_index].chords = copy.deepcopy(value) if value else []
        return
    if kind == "bar-insert":
        index = cast(int, data["index"])
        breaks = cast(set[int], data["new"] if redo else data["prev"])
        if redo:
            insert_bar(state, index)
        else:
            delete_bar(state, index)
        state.stave_breaks = breaks
        return
    if kind == "bar-delete":
        index = cast(int, data["index"])
        snapshot = cast(BarSnapshot | None, data["snapshot"] if not redo else None)
        breaks = cast(set[int], data["new"] if redo else data["prev"])
        if redo:
            delete_bar(state, index)
        else:
            insert_bar(state, index)
            if snapshot is not None:
                restore_bar_snapshot(state, index, snapshot)
        state.stave_breaks = breaks
        return
    if kind == "bars-delete":
        start = cast(int, data["start"])
        snapshots = cast(list[BarSnapshot] | None, data["snapshots"] if not redo else None)
        breaks = cast(set[int], data["new"] if redo else data["prev"])
        if redo:
            count = cast(int, data["count"])
            for _ in range(count):
                delete_bar(state, start)
        elif snapshots is not None:
            for offset, snapshot in enumerate(snapshots):
                insert_bar(state, start + offset)
                restore_bar_snapshot(state, start + offset, snapshot)
        state.stave_breaks = breaks
        return
    if kind == "bar-clear":
        index = cast(int, data["index"])
        snapshot = cast(BarSnapshot | None, data["snapshot"] if not redo else None)
        if redo:
            clear_bar_contents(state, index)
        elif snapshot is not None:
            restore_bar_snapshot(state, index, snapshot)
        return
    if kind == "stave-breaks":
        breaks = cast(set[int], data["new"] if redo else data["prev"])
        state.stave_breaks = breaks
        return
    if kind == "setting":
        key = data["key"]
        value = data["new"] if redo else data["prev"]
        if isinstance(key, str):
            if value is None:
                state.settings.pop(key, None)
            else:
                state.settings[key] = str(value)
            save_settings(config_path, state.settings)
        return


def undo(state: EditorState, *, config_path: str) -> None:
    if not state.undo_stack:
        state.message = "Nothing to undo"
        return
    action = state.undo_stack.pop()
    apply_action(state, action, redo=False, config_path=config_path)
    state.redo_stack.append(action)
    state.modified = True
    state.message = "Undone"


def redo(state: EditorState, *, config_path: str) -> None:
    if not state.redo_stack:
        state.message = "Nothing to redo"
        return
    action = state.redo_stack.pop()
    apply_action(state, action, redo=True, config_path=config_path)
    state.undo_stack.append(action)
    state.modified = True
    state.message = "Redone"
