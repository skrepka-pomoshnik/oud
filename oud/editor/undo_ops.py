from __future__ import annotations

import copy
from typing import cast

from oud.editor.bar_ops import clear_bar_contents, delete_bar, insert_bar, restore_bar_snapshot
from oud.editor.state import BarSnapshot, EditorState, UndoAction
from oud.settings import save_settings


def _restore_action_cursor(state: EditorState, action: UndoAction, *, redo: bool) -> None:
    key = "cursor_after" if redo else "cursor_before"
    cursor = action.data.get(key)
    if not isinstance(cursor, tuple) or len(cursor) != 3:
        return
    bar, cursor_string, col = cursor
    if not all(isinstance(value, int) for value in cursor):
        return
    state.cursor_bar = bar
    state.cursor_string = cursor_string
    state.cursor_col = col
    state.clamp()


def _refresh_modified_from_clean_depth(state: EditorState) -> None:
    state.modified = len(state.undo_stack) != state.clean_undo_depth


def apply_action(  # noqa: C901, PLR0911, PLR0912
    state: EditorState,
    action: UndoAction,
    *,
    redo: bool,
    config_path: str,
) -> None:
    kind = action.kind
    data = action.data
    if kind == "group":
        actions = cast(list, data.get("actions", []))
        ordered = actions if redo else list(reversed(actions))
        for sub in ordered:
            apply_action(
                state,
                cast(UndoAction, sub),
                redo=redo,
                config_path=config_path,
            )
        return
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
    if kind == "annotations-all":
        value = cast(dict[tuple[int, int], str], data["new"] if redo else data["prev"])
        state.annotations = dict(value)
        return
    if kind == "highlight":
        key = cast(tuple[int, int, int], data["key"])
        value = cast(bool, data["new"] if redo else data["prev"])
        if value:
            state.highlights.add(key)
        else:
            state.highlights.discard(key)
        return
    if kind in ("barline", "repeat", "ending", "timesig", "dynamic", "fermata"):
        bar_index = cast(int, data["bar"])
        if 0 <= bar_index < len(state.piece.bars):
            bar = state.piece.bars[bar_index]
            if kind == "barline":
                value = cast(str | None, data["new"] if redo else data["prev"])
                bar.barline = value if isinstance(value, str) else None
            elif kind == "repeat":
                value = cast(str | None, data["new"] if redo else data["prev"])
                bar.repeat = value if isinstance(value, str) else None
            elif kind == "ending":
                value = cast(tuple[int, ...], data["new"] if redo else data["prev"])
                bar.ending_numbers = tuple(value)
            elif kind == "dynamic":
                value = cast(str | None, data["new"] if redo else data["prev"])
                bar.dynamic = value if isinstance(value, str) else None
            elif kind == "fermata":
                value = cast(bool, data["new"] if redo else data["prev"])
                bar.fermata = bool(value)
            else:
                value = cast(str | None, data["new"] if redo else data["prev"])
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
            bar = state.piece.bars[bar_index]
            bar.chords = copy.deepcopy(value) if value else []
            notes_key = "new_notes" if redo else "prev_notes"
            if notes_key in data:
                notes = cast(list | None, data[notes_key])
                bar.notes = copy.deepcopy(notes) if notes else []
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
    if kind == "bars-insert":
        start = cast(int, data["start"])
        snapshots = cast(list[BarSnapshot] | None, data["snapshots"] if redo else None)
        breaks = cast(set[int], data["new"] if redo else data["prev"])
        if redo and snapshots is not None:
            for offset, snapshot in enumerate(snapshots):
                insert_bar(state, start + offset)
                restore_bar_snapshot(state, start + offset, snapshot)
        else:
            count = cast(int, data["count"])
            for _ in range(count):
                delete_bar(state, start)
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
    if kind == "score-transform":
        payload = cast(dict[str, object], data["after"] if redo else data["before"])
        piece = payload.get("piece")
        overrides = payload.get("overrides")
        if piece is not None:
            state.piece = copy.deepcopy(piece)
        if overrides is not None:
            state.overrides = dict(cast(dict[tuple[int, int, int], str], overrides))
        tuning_value = payload.get("settings_tuning")
        strings_value = payload.get("settings_strings")
        if tuning_value is None:
            state.settings.pop("tuning", None)
        else:
            state.settings["tuning"] = str(tuning_value)
        if strings_value is None:
            state.settings.pop("strings", None)
        else:
            state.settings["strings"] = str(strings_value)
        return


def undo(state: EditorState, *, config_path: str) -> None:
    if not state.undo_stack:
        state.message = "Nothing to undo"
        return
    action = state.undo_stack.pop()
    apply_action(state, action, redo=False, config_path=config_path)
    state.redo_stack.append(action)
    _restore_action_cursor(state, action, redo=False)
    _refresh_modified_from_clean_depth(state)
    state.message = "Undone"


def redo(state: EditorState, *, config_path: str) -> None:
    if not state.redo_stack:
        state.message = "Nothing to redo"
        return
    action = state.redo_stack.pop()
    apply_action(state, action, redo=True, config_path=config_path)
    state.undo_stack.append(action)
    _restore_action_cursor(state, action, redo=True)
    _refresh_modified_from_clean_depth(state)
    state.message = "Redone"
