from __future__ import annotations

import copy
from collections.abc import Callable, Mapping, MutableMapping, MutableSet
from dataclasses import dataclass
from types import MappingProxyType
from typing import TypeVar, cast

from oud.editor.core.state import BarSnapshot, EditorState, UndoAction
from oud.editor.editing.primitives.bars import clear_bar_contents, delete_bar, insert_bar, restore_bar_snapshot
from oud.settings import save_settings
from petrucci.core.model import Piece

_K = TypeVar("_K")
_V = TypeVar("_V")
_CURSOR_COMPONENT_COUNT = 3


def _restore_action_cursor(state: EditorState, action: UndoAction, *, redo: bool) -> None:
    key = "cursor_after" if redo else "cursor_before"
    cursor = action.data.get(key)
    if not isinstance(cursor, tuple) or len(cursor) != _CURSOR_COMPONENT_COUNT:
        return
    if not all(isinstance(value, int) for value in cursor):
        return
    bar, cursor_string, col = cast(tuple[int, int, int], cursor)
    state.cursor_bar = bar
    state.cursor_string = cursor_string
    state.cursor_col = col
    state.clamp()


def _refresh_modified_from_clean_depth(state: EditorState) -> None:
    state.modified = len(state.undo_stack) != state.clean_undo_depth


@dataclass(frozen=True, slots=True)
class _ApplyContext:
    state: EditorState
    action: UndoAction
    redo: bool
    config_path: str

    @property
    def data(self) -> dict[str, object]:
        return self.action.data

    def selected(self, new: str = "new", previous: str = "prev") -> object:
        return self.data[new if self.redo else previous]


def _set_optional(mapping: MutableMapping[_K, _V], key: _K, value: _V | None) -> None:
    if value is None:
        mapping.pop(key, None)
    else:
        mapping[key] = value


def _set_membership(values: MutableSet[_K], key: _K, present: bool) -> None:
    if present:
        values.add(key)
    else:
        values.discard(key)


def _apply_group(context: _ApplyContext) -> None:
    actions = cast(list[UndoAction], context.data.get("actions", []))
    ordered = actions if context.redo else reversed(actions)
    for action in ordered:
        apply_action(context.state, action, redo=context.redo, config_path=context.config_path)


def _apply_override(context: _ApplyContext) -> None:
    key = cast(tuple[int, int, int], context.data["key"])
    _set_optional(context.state.overrides, key, cast(str | None, context.selected()))


def _apply_duration(context: _ApplyContext) -> None:
    key = cast(tuple[int, int, int], context.data["key"])
    _set_optional(context.state.durations, key, cast(int | None, context.selected()))


def _apply_duration_column(context: _ApplyContext) -> None:
    bar = cast(int, context.data["bar"])
    col = cast(int, context.data["col"])
    payload = cast(dict[tuple[int, int, int], int], context.selected())
    for key in [key for key in context.state.durations if key[0] == bar and key[2] == col]:
        context.state.durations.pop(key, None)
    context.state.durations.update(payload)


def _apply_dotted(context: _ApplyContext) -> None:
    key = cast(tuple[int, int], context.data["key"])
    _set_membership(context.state.dotted, key, cast(bool, context.selected()))


def _apply_text_marker(context: _ApplyContext) -> None:
    key = cast(tuple[int, int], context.data["key"])
    target = context.state.ornaments if context.action.kind == "ornament" else context.state.annotations
    _set_optional(target, key, cast(str | None, context.selected()))


def _apply_all_annotations(context: _ApplyContext) -> None:
    context.state.annotations = dict(cast(dict[tuple[int, int], str], context.selected()))


def _apply_highlight(context: _ApplyContext) -> None:
    key = cast(tuple[int, int, int], context.data["key"])
    _set_membership(context.state.highlights, key, cast(bool, context.selected()))


def _apply_bar_attribute(context: _ApplyContext) -> None:
    bar_index = cast(int, context.data["bar"])
    if not 0 <= bar_index < len(context.state.piece.bars):
        return
    bar = context.state.piece.bars[bar_index]
    attribute = {"barline": "barline", "repeat": "repeat", "dynamic": "dynamic"}[context.action.kind]
    value = context.selected()
    setattr(bar, attribute, value if isinstance(value, str) else None)


def _apply_ending(context: _ApplyContext) -> None:
    bar_index = cast(int, context.data["bar"])
    if 0 <= bar_index < len(context.state.piece.bars):
        context.state.piece.bars[bar_index].ending_numbers = tuple(cast(tuple[int, ...], context.selected()))


def _apply_fermata(context: _ApplyContext) -> None:
    bar_index = cast(int, context.data["bar"])
    if 0 <= bar_index < len(context.state.piece.bars):
        context.state.piece.bars[bar_index].fermata = bool(context.selected())


def _apply_time_signature(context: _ApplyContext) -> None:
    bar_index = cast(int, context.data["bar"])
    if not 0 <= bar_index < len(context.state.piece.bars):
        return
    value = context.selected()
    context.state.piece.bars[bar_index].time_sig = value if isinstance(value, str) else None
    setting_key = "setting_new" if context.redo else "setting_prev"
    _set_optional(context.state.settings, "time", cast(str | None, context.data.get(setting_key)))


def _apply_chords(context: _ApplyContext) -> None:
    bar_index = cast(int, context.data["bar"])
    if not 0 <= bar_index < len(context.state.piece.bars):
        return
    bar = context.state.piece.bars[bar_index]
    value = cast(list | None, context.selected())
    bar.chords = copy.deepcopy(value) if value else []
    notes_key = "new_notes" if context.redo else "prev_notes"
    if notes_key in context.data:
        notes = cast(list | None, context.data[notes_key])
        bar.notes = copy.deepcopy(notes) if notes else []


def _selected_breaks(context: _ApplyContext) -> set[int]:
    return cast(set[int], context.selected())


def _apply_bar_insert(context: _ApplyContext) -> None:
    index = cast(int, context.data["index"])
    (insert_bar if context.redo else delete_bar)(context.state, index)
    context.state.stave_breaks = _selected_breaks(context)


def _apply_bar_delete(context: _ApplyContext) -> None:
    index = cast(int, context.data["index"])
    if context.redo:
        delete_bar(context.state, index)
    else:
        insert_bar(context.state, index)
        snapshot = cast(BarSnapshot | None, context.data["snapshot"])
        if snapshot is not None:
            restore_bar_snapshot(context.state, index, snapshot)
    context.state.stave_breaks = _selected_breaks(context)


def _apply_bars_delete(context: _ApplyContext) -> None:
    start = cast(int, context.data["start"])
    if context.redo:
        for _ in range(cast(int, context.data["count"])):
            delete_bar(context.state, start)
    else:
        for offset, snapshot in enumerate(cast(list[BarSnapshot], context.data["snapshots"])):
            insert_bar(context.state, start + offset)
            restore_bar_snapshot(context.state, start + offset, snapshot)
    context.state.stave_breaks = _selected_breaks(context)


def _apply_bars_insert(context: _ApplyContext) -> None:
    start = cast(int, context.data["start"])
    if context.redo:
        for offset, snapshot in enumerate(cast(list[BarSnapshot], context.data["snapshots"])):
            insert_bar(context.state, start + offset)
            restore_bar_snapshot(context.state, start + offset, snapshot)
    else:
        for _ in range(cast(int, context.data["count"])):
            delete_bar(context.state, start)
    context.state.stave_breaks = _selected_breaks(context)


def _apply_bar_clear(context: _ApplyContext) -> None:
    index = cast(int, context.data["index"])
    if context.redo:
        clear_bar_contents(context.state, index)
    else:
        snapshot = cast(BarSnapshot | None, context.data["snapshot"])
        if snapshot is not None:
            restore_bar_snapshot(context.state, index, snapshot)


def _apply_stave_breaks(context: _ApplyContext) -> None:
    context.state.stave_breaks = _selected_breaks(context)


def _apply_setting(context: _ApplyContext) -> None:
    key = context.data["key"]
    if not isinstance(key, str):
        return
    value = context.selected()
    _set_optional(context.state.settings, key, None if value is None else str(value))
    save_settings(context.config_path, context.state.settings)


def _apply_score_transform(context: _ApplyContext) -> None:
    payload = cast(dict[str, object], context.data["after"] if context.redo else context.data["before"])
    piece = cast(Piece | None, payload.get("piece"))
    overrides = payload.get("overrides")
    if piece is not None:
        context.state.piece = copy.deepcopy(piece)
    if overrides is not None:
        context.state.overrides = dict(cast(dict[tuple[int, int, int], str], overrides))
    _set_optional_setting(context.state, "tuning", payload.get("settings_tuning"))
    _set_optional_setting(context.state, "strings", payload.get("settings_strings"))


def _set_optional_setting(state: EditorState, key: str, value: object) -> None:
    _set_optional(state.settings, key, None if value is None else str(value))


_ActionHandler = Callable[[_ApplyContext], None]
_ACTION_HANDLERS: Mapping[str, _ActionHandler] = MappingProxyType(
    {
        "group": _apply_group,
        "override": _apply_override,
        "duration": _apply_duration,
        "duration_col": _apply_duration_column,
        "dotted": _apply_dotted,
        "ornament": _apply_text_marker,
        "annotation": _apply_text_marker,
        "annotations-all": _apply_all_annotations,
        "highlight": _apply_highlight,
        "barline": _apply_bar_attribute,
        "repeat": _apply_bar_attribute,
        "dynamic": _apply_bar_attribute,
        "ending": _apply_ending,
        "fermata": _apply_fermata,
        "timesig": _apply_time_signature,
        "chords": _apply_chords,
        "bar-insert": _apply_bar_insert,
        "bar-delete": _apply_bar_delete,
        "bars-delete": _apply_bars_delete,
        "bars-insert": _apply_bars_insert,
        "bar-clear": _apply_bar_clear,
        "stave-breaks": _apply_stave_breaks,
        "setting": _apply_setting,
        "score-transform": _apply_score_transform,
    },
)


def apply_action(
    state: EditorState,
    action: UndoAction,
    *,
    redo: bool,
    config_path: str,
) -> None:
    handler = _ACTION_HANDLERS.get(action.kind)
    if handler is not None:
        handler(_ApplyContext(state, action, redo, config_path))


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
