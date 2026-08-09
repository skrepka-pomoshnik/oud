from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

from oud.editor.core.document import set_write_target
from oud.editor.core.feedback.messages import MISSING_LESS, NO_SOURCE_PATH, MessageLevel
from oud.editor.core.session import set_mode
from oud.editor.core.state import EditorState
from oud.exports.export_tab import TabExportError, export_ascii, export_tab_to_file

RunFn = Callable[..., subprocess.CompletedProcess[str]]
WhichFn = Callable[[str], str | None]


def _normalized_path(path: str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _confirm_new_target(state: EditorState, path: str) -> bool:
    target = _normalized_path(path)
    established = state.write_path and _normalized_path(state.write_path) == target
    if not target.exists() or established:
        state.pending_overwrite_path = None
        return True
    if state.pending_overwrite_path == str(target):
        state.pending_overwrite_path = None
        return True
    state.pending_overwrite_path = str(target)
    state.message = f"File exists; repeat write to replace {target.name}"
    return False


def request_save_as(state: EditorState, command: str = "w") -> None:
    set_mode(state, "command")
    state.cmdline = f"{command} "
    state.message = "Save As .tab; source unchanged"


def cmd_write(state: EditorState, path: str) -> bool:
    target = path.strip()
    if state.read_only:
        state.message = "Read-only imported score: TAB write disabled"
        return False
    if Path(target).suffix.lower() != ".tab":
        state.notify("TAB destination must end in .tab", MessageLevel.ERROR)
        return False
    if not _confirm_new_target(state, target):
        return False
    try:
        export_tab_to_file(
            target,
            state.piece,
            state.overrides,
            state.durations,
            state.bar_width,
            settings=state.settings,
            dotted=state.dotted,
            ornaments=state.ornaments,
            annotations=state.annotations,
            slurs=state.slurs,
            ties=state.ties,
            holds=state.holds,
        )
    except (OSError, TabExportError) as exc:
        state.message = f"Write failed: {exc}"
        return False
    set_write_target(state, target)
    state.modified = False
    state.clean_undo_depth = len(state.undo_stack)
    state.pending_quit = False
    state.message = f"Wrote TAB {target}"
    return True


def cmd_write_default(state: EditorState, args: str, *, prompt_command: str = "w") -> bool:
    path = args.strip()
    if not path and state.write_path:
        path = state.write_path
    if not path:
        request_save_as(state, prompt_command)
        return False
    return cmd_write(state, path)


def cmd_write_ascii(state: EditorState, path: str) -> None:
    content = render_ascii_snapshot(state)
    with Path(path).open("w", encoding="utf-8") as handle:
        handle.write(content)
    state.message = f"Exported ASCII {path}"


def render_ascii_snapshot(state: EditorState) -> str:
    content = ""
    if state.screen_width > 0 and state.screen_height > 0:
        from oud.editor.services.status import status_line  # noqa: PLC0415
        from petrucci.framebuffer import FrameBuffer  # noqa: PLC0415
        from petrucci.render import render_piece  # noqa: PLC0415

        frame = FrameBuffer(state.screen_height, state.screen_width)
        render_piece(
            frame,
            state.piece,
            state.bar_offset,
            state.cursor_bar,
            state.cursor_string,
            state.cursor_col,
            state.bar_width,
            state.overrides,
            state.durations,
            state.ornaments,
            state.annotations,
            state.highlights,
            state.dotted,
            state.slurs,
            state.ties,
            state.holds,
            state.mode,
            state.cmdline,
            state.visible_message,
            status_line(state),
            state.searchline,
            state.settings,
            None,
            state.stave_breaks,
            state.plugin_title,
            [f"{item.title}{'/' if item.is_dir else ''}" for item in state.plugin_items],
            state.plugin_index,
            state.plugin_offset,
            state.info_offset
            if state.mode == "info"
            else state.notes_offset
            if state.mode == "notes"
            else state.help_offset,
            message_level=state.visible_message_level.value,
        )
        content = "\n".join(frame.snapshot().lines) + "\n"
    else:
        content = export_ascii(
            state.piece,
            state.overrides,
            state.durations,
            state.bar_width,
            settings=state.settings,
            ornaments=state.ornaments,
            annotations=state.annotations,
            slurs=state.slurs,
            ties=state.ties,
            holds=state.holds,
        )
    return content


def cmd_write_ascii_default(state: EditorState, args: str) -> None:
    path = args.strip()
    if not path and state.path:
        path = state.path if state.path.endswith(".txt") else state.path + ".txt"
    if not path:
        state.message = "No path for wa"
        return
    cmd_write_ascii(state, path)


def cmd_source(
    state: EditorState,
    target: str,
    *,
    which_fn: WhichFn,
    run_fn: RunFn,
) -> None:
    path = target.strip() or state.path
    if not path:
        state.message = NO_SOURCE_PATH
        return
    viewer = which_fn("less")
    if not viewer:
        state.message = MISSING_LESS
        return
    run_fn([viewer, path], check=False)
