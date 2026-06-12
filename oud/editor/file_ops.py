from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

from oud.editor.messages import MISSING_LESS, NO_SOURCE_PATH
from oud.editor.state import EditorState
from oud.exports.export_tab import export_ascii, export_tab_to_file

RunFn = Callable[..., subprocess.CompletedProcess[str]]
WhichFn = Callable[[str], str | None]


def cmd_write(state: EditorState, path: str) -> None:
    export_tab_to_file(
        path,
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
    state.modified = False
    state.clean_undo_depth = len(state.undo_stack)
    state.pending_quit = False
    state.message = f"Wrote {path}"


def cmd_write_default(state: EditorState, args: str) -> None:
    path = args.strip()
    if not path and state.path:
        path = state.path if state.path.endswith(".tab") else state.path + ".tab"
    if not path:
        state.message = "No path for write"
        return
    cmd_write(state, path)


def cmd_write_ascii(state: EditorState, path: str) -> None:
    content = render_ascii_snapshot(state)
    with Path(path).open("w", encoding="utf-8") as handle:
        handle.write(content)
    state.modified = False
    state.clean_undo_depth = len(state.undo_stack)
    state.pending_quit = False
    state.message = f"Wrote {path}"


def render_ascii_snapshot(state: EditorState) -> str:
    content = ""
    if state.screen_width > 0 and state.screen_height > 0:
        from oud.editor.status import status_line  # noqa: PLC0415
        from oud.ui.framebuffer import FrameBuffer  # noqa: PLC0415
        from oud.ui.render import render_piece  # noqa: PLC0415

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
            state.message,
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
            else state.notes_offset if state.mode == "notes" else state.help_offset,
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
