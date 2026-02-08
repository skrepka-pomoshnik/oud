from __future__ import annotations

from oud.core.time_utils import parse_time_signature_value
from oud.editor.state import EditorState


def status_line(state: EditorState) -> str:
    bar = state.cursor_bar + 1
    beat_text = f"col:{state.cursor_col + 1}"
    parsed = parse_time_signature_value(state.settings.get("time", "C"))
    if parsed is not None and state.bar_width > 0:
        beats, _unit = parsed
        beat_index = min(
            beats,
            max(1, int(state.cursor_col * beats / state.bar_width) + 1),
        )
        beat_text = f"beat:{beat_index}/{beats}"
    mod = "*" if state.modified else ""
    return f"{mod}bar:{bar} {beat_text}  dur:{state.current_duration}"
