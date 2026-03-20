from __future__ import annotations

from collections.abc import Callable

from oud.editor.edit_ops import record_action
from oud.editor.insert_session import set_mode
from oud.editor.state import EditorState, UndoAction

SaveFn = Callable[[str, dict[str, str]], None]


def cmd_info(state: EditorState) -> None:
    set_mode(state, "info")
    state.info_offset = 0


def cmd_notes(state: EditorState) -> None:
    set_mode(state, "notes")
    state.notes_offset = 0


def cmd_plugins(state: EditorState) -> None:
    from oud.editor.plugin_ops import enter_plugin_mode  # noqa: PLC0415

    enter_plugin_mode(state)


def cmd_tool(
    state: EditorState,
    action: str,
    config_path: str,
    *,
    save_fn: SaveFn,
) -> None:
    value = action.strip() or "reflow"
    if value == "reflow":
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
        state.settings["flagstyle"] = next_value
        save_fn(config_path, state.settings)
        state.message = f"Flagstyle {next_value}"
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
        state.settings["flagstyle"] = next_value
        save_fn(config_path, state.settings)
        state.message = f"Flagstyle {next_value}"
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
