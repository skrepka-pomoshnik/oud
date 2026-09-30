from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

from oud.editor.core.document import default_write_path, set_write_target
from oud.editor.core.feedback.messages import MISSING_LESS, NO_SOURCE_PATH, MessageLevel
from oud.editor.core.input.modes import Mode
from oud.editor.core.session import set_mode
from oud.editor.core.state import EditorState
from oud.editor.services.io.dropped import dropped_marks_text
from oud.editor.services.screen.compose import compose_editor_frame
from oud.exports.export_tab import TabExportError, export_ascii, export_tab_to_file
from oud.exports.musicxml import export_musicxml
from oud.exports.musicxml_staffs import notation_parts

TAB_SUFFIX = ".tab"
MUSICXML_SUFFIXES = (".musicxml", ".xml")
SAVE_SUFFIX_ERROR = "Save destination must end in .musicxml, .xml or .tab"

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
    set_mode(state, Mode.COMMAND)
    state.cmdline = f"{command} {default_write_path(state)}"
    state.message = "Confirm or edit the destination (.musicxml or .tab)"


def cmd_write(state: EditorState, path: str) -> bool:
    target = path.strip()
    if state.read_only:
        state.message = "Read-only imported score: TAB write disabled"
        return False
    suffix = Path(target).suffix.lower()
    if suffix != TAB_SUFFIX and suffix not in MUSICXML_SUFFIXES:
        state.notify(SAVE_SUFFIX_ERROR, MessageLevel.ERROR)
        return False
    staff_count = len(notation_parts(state.piece))
    if suffix == TAB_SUFFIX and staff_count:
        # C15 will write these to a sidecar; until then refuse rather than drop them.
        state.message = f"Write failed: TAB cannot hold {_staff_text(staff_count)}; save as .musicxml"
        return False
    if not _confirm_new_target(state, target):
        return False
    try:
        _write_document(state, target, tab=suffix == TAB_SUFFIX)
    except (OSError, TabExportError) as exc:
        state.message = f"Write failed: {exc}"
        return False
    set_write_target(state, target)
    state.modified = False
    state.clean_undo_depth = len(state.undo_stack)
    state.pending_quit = False
    state.message = _written_message(state, target, tab=suffix == TAB_SUFFIX, staff_count=staff_count)
    return True


def _written_message(state: EditorState, target: str, *, tab: bool, staff_count: int) -> str:
    message = f"Wrote {'TAB' if tab else 'MusicXML'} {target}"
    if staff_count:
        message += f" (tablature and {_staff_text(staff_count)})"
    dropped = dropped_marks_text(state, tab=tab)
    return f"{message} (not saved: {dropped})" if dropped else message


def _staff_text(count: int) -> str:
    return f"{count} notation staff" + ("s" if count != 1 else "")


def _write_document(state: EditorState, target: str, *, tab: bool) -> None:
    if not tab:
        export_musicxml(
            target,
            state.piece,
            state.overrides,
            state.durations,
            state.bar_width,
            settings=state.settings,
            dotted=state.dotted,
        )
        return
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
    """The editor screen as text, or the plain ASCII export when no screen size is known."""

    if state.screen_width > 0 and state.screen_height > 0:
        composed = compose_editor_frame(state, height=state.screen_height, width=state.screen_width)
        return "\n".join(composed.frame.lines) + "\n"
    return export_ascii(
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
