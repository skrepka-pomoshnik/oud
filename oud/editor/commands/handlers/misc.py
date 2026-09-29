from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path

from oud.editor.core.coordinates import bar_stops, string_index
from oud.editor.core.feedback.messages import MISSING_LESS
from oud.editor.core.input.help import help_lines
from oud.editor.core.state import EditorState
from petrucci.core.music.time import parse_time_signature_value
from petrucci.core.music.tuning import tuning_preset
from petrucci.input.tablature.mutation import event_onsets


def row_first_note_onset(state: EditorState) -> Fraction:
    """Onset of the cursor bar's first event with a note on the cursor course, else 0."""

    if not 0 <= state.cursor_bar < len(state.piece.bars):
        return Fraction(0)
    course = string_index(state, min(state.cursor_string, state.piece.strings - 1)) + 1
    bar = state.piece.bars[state.cursor_bar]
    return next(
        (
            onset
            for onset, chord in zip(event_onsets(bar), bar.chords, strict=True)
            if any(note.string == course for note in chord.notes)
        ),
        Fraction(0),
    )


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
    content = "\n".join(help_lines(state)) + "\n"
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


def _move_to_stop(state: EditorState, number: int) -> None:
    """Move to the 1-based cursor stop of the cursor bar; past the end means the last stop."""

    state.clamp()
    stops = bar_stops(state, state.cursor_bar)
    state.cursor_onset = stops[max(0, min(number, len(stops)) - 1)]


def _stop_number(state: EditorState) -> int:
    return bar_stops(state, state.cursor_bar).index(state.cursor_onset) + 1


def cmd_col(state: EditorState, args: str) -> None:
    token = args.strip()
    if not token.isdigit():
        state.message = "Usage: col <1-based event>"
        return
    _move_to_stop(state, int(token))
    state.message = f"Event {_stop_number(state)}"


_MAX_CURSOR_PARTS = 3
_STRING_PART_INDEX = 2
_COLUMN_PART_INDEX = 3


def cmd_cursor(state: EditorState, args: str) -> None:
    tokens = [part for part in args.replace(",", " ").split() if part]
    if not tokens or len(tokens) > _MAX_CURSOR_PARTS or any(not part.isdigit() for part in tokens):
        state.message = "Usage: cursor <bar> [string] [event]"
        return
    state.cursor_bar = max(0, int(tokens[0]) - 1)
    if len(tokens) >= _STRING_PART_INDEX:
        state.cursor_string = max(0, int(tokens[1]) - 1)
    _move_to_stop(state, int(tokens[2]) if len(tokens) >= _COLUMN_PART_INDEX else 1)
    state.message = f"Cursor {state.cursor_bar + 1}:{state.cursor_string + 1}:{_stop_number(state)}"


def cmd_verify(state: EditorState, args: str = "") -> None:
    mode = args.strip().lower()
    if mode in ("", "bar"):
        from oud.editor.services.validation.verify import verify_bar  # noqa: PLC0415

        state.message = verify_bar(state, state.cursor_bar)
        return
    if mode in ("render", "view", "ui"):
        from oud.editor.services.validation.verify import verify_render_bar  # noqa: PLC0415

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
            any((ev.text or "").strip() or ev.extender for ev in row) for row in bar.lyric_event_rows
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
