from __future__ import annotations

from oud.core.time_utils import parse_time_signature_value
from oud.editor.state import EditorState


def _time_symbol(value: str) -> str:
    parsed = parse_time_signature_value(value)
    if parsed is None:
        return value
    beats, unit = parsed
    if beats == 4 and unit == 4:
        return "C"
    if beats == 3 and unit == 4:
        return "O"
    return f"{beats}/{unit}"


def status_line(state: EditorState) -> str:
    name = state.path.split("/")[-1] if state.path else "[No file]"
    mod = "*" if state.modified else ""
    bar = state.cursor_bar + 1
    string = state.cursor_string + 1
    beat_text = f"col:{state.cursor_col + 1}"
    parsed = parse_time_signature_value(state.settings.get("time", "C"))
    if parsed is not None and state.bar_width > 0:
        beats, _unit = parsed
        beat_index = min(
            beats,
            max(1, int(state.cursor_col * beats / state.bar_width) + 1),
        )
        beat_text = f"beat:{beat_index}/{beats}"
    time_value = state.settings.get("time", "C")
    if 0 <= state.cursor_bar < len(state.piece.bars):
        bar_time = state.piece.bars[state.cursor_bar].time_sig
        if bar_time:
            time_value = bar_time
    style = state.settings.get("style", "french")
    return (
        f"{name}{mod}  bar:{bar} str:{string} {beat_text}  "
        f"dur:{state.current_duration}  style:{style}  time:{_time_symbol(time_value)}"
    )
