"""The status row: a typed model rendered into fixed left and right segments.

Identity and position start at the left edge; pending keys, duration, and mode end
at the right edge; the message sits between them. When the row is too narrow,
whole segments are dropped in a fixed priority order before the message is cut,
and the mode is never dropped.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from oud.editor.core.document import display_path, document_status_label
from oud.editor.core.feedback.messages import MessageLevel
from oud.editor.core.input.modes import INSERT_MODES, Mode
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
GROUP_GAP = "  "
# Segments removed first when the row is too narrow. The message is cut only after
# all of these are gone; the mode always stays.
DROP_ORDER = ("identity", "duration", "pending", "meter", "position")
_PRINTABLE = range(ord(" "), ord("~") + 1)


@dataclass(frozen=True)
class StatusModel:
    identity: str = ""
    position: str = ""
    meter: str = ""
    message: str = ""
    level: MessageLevel = MessageLevel.INFO
    pending: str = ""
    duration: str = ""
    mode: str = ""


def _join(parts: tuple[str, ...], separator: str) -> str:
    return separator.join(part for part in parts if part)


def _groups(model: StatusModel) -> tuple[str, str, str]:
    left = _join((model.identity, model.position, model.meter), " ")
    right = _join((model.pending, model.duration, model.mode), GROUP_GAP)
    return left, model.message, right


def _natural(model: StatusModel) -> str:
    return _join(_groups(model), GROUP_GAP)


def _fit(model: StatusModel, width: int) -> StatusModel:
    for name in DROP_ORDER:
        if len(_natural(model)) <= width:
            return model
        model = replace(model, **{name: ""})
    overflow = len(_natural(model)) - width
    if overflow > 0 and model.message:
        model = replace(model, message=model.message[: max(0, len(model.message) - overflow)].rstrip())
    return model


def render_status(model: StatusModel, width: int) -> str:
    """Lay out ``model`` in ``width`` columns; ``width <= 0`` returns the natural text."""

    if width <= 0:
        return _natural(model)
    # Leave the bottom-right cell empty: curses reports an error when it is written.
    usable = width - 1
    model = _fit(model, usable)
    left, message, right = _groups(model)
    head = _join((left, message), GROUP_GAP)
    if not right:
        return head[:usable]
    gap = max(len(GROUP_GAP) if head else 0, usable - len(head) - len(right))
    return f"{head}{' ' * gap}{right}"[:usable]


def status_row_visible(state: EditorState) -> bool:
    return state.settings.get("bottompanel", "on") != "off" or state.mode in ALWAYS_VISIBLE_MODES


def status_attr(model: StatusModel) -> int:
    """Reverse video, marked by the message level while a message is shown."""

    return _MESSAGE_ATTRS.get(model.level, A_REVERSE) if model.message else A_REVERSE


def status_row_attr(state: EditorState) -> int:
    return status_attr(StatusModel(message=state.visible_message, level=state.visible_message_level))


def _pending_text(state: EditorState) -> str:
    keys = "".join(chr(key) if key in _PRINTABLE else "?" for key in state.pending_keys)
    prefix = state.insert_prefix if state.mode in INSERT_MODES else ""
    return f"{state.count_prefix}{keys}{prefix}"


def _mode_label(state: EditorState) -> str:
    return HELP_HINT if state.mode == Mode.HELP else str(state.mode)


def status_model(
    state: EditorState,
    *,
    duration: str | None = None,
    meter: str | None = None,
    mode: str | None = None,
) -> StatusModel:
    """The status row for ``state``; ``mode`` replaces the mode label on pages."""

    visible = status_row_visible(state)
    return StatusModel(
        identity=_identity(state) if visible else "",
        position=_position(state) if visible else "",
        meter=meter or "",
        message=state.visible_message,
        level=state.visible_message_level,
        pending=_pending_text(state),
        duration=f"len:{duration}" if duration else "",
        mode=_mode_label(state) if mode is None else mode,
    )


def prompt_text(state: EditorState) -> str:
    prompt = f":{state.cmdline}" if state.mode == Mode.COMMAND else f"/{state.searchline}"
    return _join((prompt, state.visible_message), GROUP_GAP)


def status_row_text(
    state: EditorState,
    *,
    duration: str | None = None,
    meter: str | None = None,
    width: int | None = None,
) -> str:
    """The status row as text; the command and search prompts replace it while active."""

    if state.mode in _PROMPT_MODES:
        return prompt_text(state)
    model = status_model(state, duration=duration, meter=meter)
    return render_status(model, state.screen_width if width is None else width)


def status_line(state: EditorState) -> str:
    """Identity and cursor position: the left segments of the status row."""

    if not status_row_visible(state):
        return ""
    if state.mode in _PROMPT_MODES:
        return _identity(state)
    return _join((_identity(state), _position(state)), " ")


def _compact_name(name: str, width: int) -> str:
    budget = max(12, min(28, width // 3)) if width > 0 else 24
    if len(name) <= budget:
        return name
    head = max(4, budget - 9)
    return f"{name[:head]}...{name[-6:]}"


def _identity(state: EditorState) -> str:
    name = _compact_name(display_path(state), state.screen_width)
    modified = "*" if state.modified else ""
    return f"{name}{modified} [{document_status_label(state)}]"


def _position(state: EditorState) -> str:
    if state.read_only:
        return _read_only_position(state)
    beat_text = f"col:{state.cursor_col + 1}"
    parsed = parse_time_signature_value(state.settings.get("time", "C"))
    if parsed is not None and state.bar_width > 0:
        beats, _unit = parsed
        beat_index = min(beats, max(1, int(state.cursor_col * beats / state.bar_width) + 1))
        beat_text = f"beat:{beat_index}/{beats}"
    location = f"str:{state.cursor_string + 1}"
    if is_duet_score_piece(state.piece):
        staff, _logical_bar = duet_bar_mapping(state.cursor_bar, piece=state.piece)
        location = f"staff:{staff + 1}"
    return f"bar:{state.cursor_bar + 1} {beat_text} {location}"


def _read_only_position(state: EditorState) -> str:
    system_start, system_end = viewport_system_range(state, state.screen_width, state.screen_height)
    parts = [f"cur:{state.cursor_bar + 1}", f"sys:{system_start}-{system_end}"]
    page = viewport_page_label(state)
    if page:
        parts.append(f"page:{page}")
    if len(visible_view_staffs(state.piece)) > 1:
        parts.append(f"focus:{current_view_staff(state).label}")
    section = viewport_section_label(state)
    if section:
        parts.append(f"sec:{_compact_name(section, max(36, state.screen_width))}")
    return " ".join(parts)


__all__ = [
    "ALWAYS_VISIBLE_MODES",
    "DROP_ORDER",
    "HELP_HINT",
    "StatusModel",
    "prompt_text",
    "render_status",
    "status_attr",
    "status_line",
    "status_model",
    "status_row_attr",
    "status_row_text",
    "status_row_visible",
]
