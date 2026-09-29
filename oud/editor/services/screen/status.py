from __future__ import annotations

from oud.editor.core.document import display_path, document_status_label
from oud.editor.core.feedback.messages import MessageLevel
from oud.editor.core.input.modes import Mode
from oud.editor.core.state import EditorState
from oud.editor.navigation.view.focus import current_view_staff, visible_view_staffs
from oud.editor.navigation.viewport import viewport_page_label, viewport_section_label, viewport_system_range
from petrucci.adapters.duet import duet_bar_mapping, is_duet_score_piece
from petrucci.core.music.time import parse_time_signature_value
from petrucci.terminal.canvas.screen import A_BOLD, A_DIM, A_REVERSE, A_UNDERLINE

# Modes whose status row stays visible when the bottom panel is off.
ALWAYS_VISIBLE_MODES = frozenset({Mode.COMMAND, Mode.SEARCH, Mode.HELP, Mode.INFO, Mode.NOTES, Mode.PLUGIN})
_PROMPT_MODES = frozenset({Mode.COMMAND, Mode.SEARCH})
_MESSAGE_ATTRS = {
    MessageLevel.SUCCESS: A_REVERSE | A_BOLD,
    MessageLevel.WARNING: A_REVERSE | A_UNDERLINE,
    MessageLevel.ERROR: A_REVERSE | A_BOLD | A_UNDERLINE,
    MessageLevel.CONFIRM: A_REVERSE | A_DIM,
}
HELP_HINT = "help  j/k scroll  q close"


def _compact_name(name: str, width: int) -> str:
    budget = max(12, min(28, width // 3)) if width > 0 else 24
    if len(name) <= budget:
        return name
    head = max(4, budget - 9)
    return f"{name[:head]}...{name[-6:]}"


def status_row_visible(state: EditorState) -> bool:
    return state.settings.get("bottompanel", "on") != "off" or state.mode in ALWAYS_VISIBLE_MODES


def status_row_attr(state: EditorState) -> int:
    if not state.visible_message:
        return A_REVERSE
    return _MESSAGE_ATTRS.get(state.visible_message_level, A_REVERSE)


def _mode_text(state: EditorState) -> str:
    if state.mode == Mode.COMMAND:
        return f":{state.cmdline}"
    if state.mode == Mode.SEARCH:
        return f"/{state.searchline}"
    if state.mode == Mode.HELP:
        return HELP_HINT
    return str(state.mode)


def status_row_text(state: EditorState, *, duration: str | None = None, meter: str | None = None) -> str:
    """Compose the status row: position, meter marker, mode, duration, and message."""

    message = state.visible_message
    text = _mode_text(state)
    if state.mode in _PROMPT_MODES:
        return f"{text}  {message}" if message else text
    if duration and not message:
        text = f"{text}  len:{duration}"
    if message:
        text = f"{text}  {message}"
    position = status_line(state)
    if meter and position:
        position = f"{position} {meter}"
    return f"{position}  {text}".strip() if position else text


def status_line(state: EditorState) -> str:
    if not status_row_visible(state):
        return ""
    name = _compact_name(display_path(state), state.screen_width)
    modified = "*" if state.modified else ""
    identity = f"{name}{modified} [{document_status_label(state)}]"
    if state.mode in {"command", "search"}:
        return identity

    bar = state.cursor_bar + 1
    if state.read_only:
        return _read_only_status(state, identity, bar)
    beat_text = f"col:{state.cursor_col + 1}"
    parsed = parse_time_signature_value(state.settings.get("time", "C"))
    if parsed is not None and state.bar_width > 0:
        beats, _unit = parsed
        beat_index = min(
            beats,
            max(1, int(state.cursor_col * beats / state.bar_width) + 1),
        )
        beat_text = f"beat:{beat_index}/{beats}"
    location = f"str:{state.cursor_string + 1}"
    if is_duet_score_piece(state.piece):
        staff, _logical_bar = duet_bar_mapping(state.cursor_bar, piece=state.piece)
        location = f"staff:{staff + 1}"
    return f"{identity} bar:{bar} {beat_text} {location}"


def _read_only_status(state: EditorState, identity: str, cursor_bar: int) -> str:
    system_start, system_end = viewport_system_range(state, state.screen_width, state.screen_height)
    parts = [identity, f"cur:{cursor_bar}", f"sys:{system_start}-{system_end}"]
    page = viewport_page_label(state)
    if page:
        parts.append(f"page:{page}")
    if len(visible_view_staffs(state.piece)) > 1:
        parts.append(f"focus:{current_view_staff(state).label}")
    section = viewport_section_label(state)
    if section:
        parts.append(f"sec:{_compact_name(section, max(36, state.screen_width))}")
    return " ".join(parts)
