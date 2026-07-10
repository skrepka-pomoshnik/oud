from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from oud.editor.controller_utils import string_index
from oud.editor.messages import MISSING_LESS
from oud.editor.state import EditorState
from oud.petrucci.help_text import help_lines
from oud.petrucci.time_utils import parse_time_signature_value
from oud.petrucci.tuning_utils import tuning_preset


def row_first_note_col(state: EditorState) -> int:
    bar = state.cursor_bar
    string = string_index(state, min(state.cursor_string, state.piece.strings - 1))
    cols = [col for (b, s, col) in state.overrides if b == bar and s == string]
    if not cols:
        return 0
    return min(cols)


def tuning_preset_value(value: str) -> str | None:
    return tuning_preset(value)


def parse_time_signature(text: str) -> tuple[int, int] | None:
    return parse_time_signature_value(text)


def show_help(
    state: EditorState,
    *,
    which_fn: Callable[[str], str | None] = shutil.which,
    run_fn: Callable[..., object] = subprocess.run,
) -> None:
    viewer = which_fn("less")
    if not viewer:
        state.message = MISSING_LESS
        return
    content = "\n".join(help_lines()) + "\n"
    if state.mode == "plugin" and state.plugin_name:
        root = Path(__file__).resolve().parents[1]
        plugin_help = root / "plugins" / f"{state.plugin_name}.txt"
        if plugin_help.exists():
            content = plugin_help.read_text(encoding="utf-8") + "\n"
    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as temp:
        temp.write(content)
        temp_path = Path(temp.name)
    try:
        if state.suspend_tui:
            state.suspend_tui()
        run_fn([viewer, str(temp_path)], check=False)
    finally:
        if state.resume_tui:
            state.resume_tui()
        temp_path.unlink(missing_ok=True)


def cmd_col(state: EditorState, args: str) -> None:
    token = args.strip()
    if not token.isdigit():
        state.message = "Usage: col <1-based-column>"
        return
    state.cursor_col = max(0, int(token) - 1)
    state.clamp()
    state.message = f"Col {state.cursor_col + 1}"


def cmd_cursor(state: EditorState, args: str) -> None:
    tokens = [part for part in args.replace(",", " ").split() if part]
    if not tokens or len(tokens) > 3 or any(not part.isdigit() for part in tokens):
        state.message = "Usage: cursor <bar> [string] [col]"
        return
    state.cursor_bar = max(0, int(tokens[0]) - 1)
    if len(tokens) >= 2:
        state.cursor_string = max(0, int(tokens[1]) - 1)
    if len(tokens) >= 3:
        state.cursor_col = max(0, int(tokens[2]) - 1)
    state.clamp()
    state.message = (
        f"Cursor {state.cursor_bar + 1}:{state.cursor_string + 1}:{state.cursor_col + 1}"
    )


def cmd_verify(state: EditorState, args: str = "") -> None:
    mode = args.strip().lower()
    if mode in ("", "bar"):
        from oud.editor.verify_ops import verify_bar  # noqa: PLC0415

        state.message = verify_bar(state, state.cursor_bar)
        return
    if mode in ("render", "view", "ui"):
        from oud.editor.verify_ops import verify_render_bar  # noqa: PLC0415

        state.message = verify_render_bar(state, state.cursor_bar)
        return
    state.message = "Verify modes: bar|render"


def cmd_vocal(state: EditorState, args: str) -> None:
    action = args.strip().lower()
    if action not in {"clear", "remove", "rm", "drop"}:
        state.message = "Usage: vocal clear"
        return
    removed = 0
    for bar in state.piece.bars:
        has_lyric_events = any(
            any((ev.text or "").strip() or ev.extender for ev in row)
            for row in bar.lyric_event_rows
        )
        had = (
            (bar.melody_grid or "").strip()
            or any((ev.text or "").strip() for ev in bar.melody_events)
            or any((line or "").strip() for line in bar.lyrics)
            or has_lyric_events
        )
        if not had:
            continue
        bar.melody_grid = None
        bar.melody_events = []
        bar.lyrics = []
        bar.lyric_event_rows = []
        removed += 1
    if removed > 0:
        state.modified = True
    state.message = f"Cleared vocal layer in {removed} bar(s)"
