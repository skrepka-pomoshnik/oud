from __future__ import annotations

from collections.abc import Callable

from oud.editor.core.input.modes import Mode
from oud.editor.core.session import set_mode
from oud.editor.core.state import EditorState, UndoAction
from oud.editor.editing.primitives.edits import record_action, undo_group

SaveFn = Callable[[str, dict[str, str]], None]


def cmd_info(state: EditorState) -> None:
    set_mode(state, Mode.INFO)
    state.info_offset = 0


def cmd_notes(state: EditorState) -> None:
    set_mode(state, Mode.NOTES)
    state.notes_offset = 0


def cmd_plugins(state: EditorState) -> None:
    from oud.editor.commands.plugins.operations import enter_plugin_mode  # noqa: PLC0415

    enter_plugin_mode(state)


def _set_flagstyle(state: EditorState, value: str, config_path: str, save_fn: SaveFn) -> None:
    state.settings["flagstyle"] = value
    state.message = f"Flagstyle {value}"
    try:
        save_fn(config_path, {"flagstyle": value})
    except OSError as exc:
        state.message = f"Flagstyle {value} applied but not saved: {exc}"


def cmd_tool(
    state: EditorState,
    action: str,
    config_path: str,
    *,
    save_fn: SaveFn,
) -> None:
    value = action.strip() or "reflow"
    if value == "reflow":
        with undo_group(state, label="reflow"):
            prev = set(state.stave_breaks)
            state.stave_breaks.clear()
            record_action(
                state,
                UndoAction(
                    kind="stave-breaks",
                    data={"prev": prev, "new": set(state.stave_breaks)},
                ),
            )
        state.message = "Reflowed (breaks cleared)"
        return
    if value == "gridflags":
        current = state.settings.get("flagstyle", "standard")
        next_value = "board" if current != "board" else "standard"
        _set_flagstyle(state, next_value, config_path, save_fn)
        return
    if value in ("flagstyle", "flagstyles", "flagcycle"):
        styles = [
            "standard",
            "thin",
            "board",
            "italian",
            "capirola",
            "englishgrid",
            "continental",
        ]
        current = state.settings.get("flagstyle", "standard")
        try:
            idx = styles.index(current)
        except ValueError:
            idx = -1
        next_value = styles[(idx + 1) % len(styles)]
        _set_flagstyle(state, next_value, config_path, save_fn)
        return
    if value == "comments":
        prev = dict(state.annotations)
        state.annotations.clear()
        record_action(
            state,
            UndoAction(
                kind="annotations-all",
                data={"prev": prev, "new": dict(state.annotations)},
            ),
        )
        state.message = "Annotations cleared"
        return
    state.message = "Tool: reflow|gridflags|flagstyle|comments"
