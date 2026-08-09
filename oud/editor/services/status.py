from __future__ import annotations

from oud.editor.core.document import display_path, document_status_label
from oud.editor.core.state import EditorState
from oud.editor.navigation.view.focus import current_view_staff, visible_view_staffs
from oud.editor.navigation.viewport import viewport_page_label, viewport_section_label, viewport_system_range
from petrucci.adapters.duet import duet_bar_mapping, is_duet_score_piece
from petrucci.core.music.time import parse_time_signature_value


def _compact_name(name: str, width: int) -> str:
    budget = max(12, min(28, width // 3)) if width > 0 else 24
    if len(name) <= budget:
        return name
    head = max(4, budget - 9)
    return f"{name[:head]}...{name[-6:]}"


def status_line(state: EditorState) -> str:
    if state.settings.get("bottompanel", "on") == "off" and state.mode not in {
        "command",
        "search",
        "help",
        "info",
        "notes",
        "plugin",
    }:
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
