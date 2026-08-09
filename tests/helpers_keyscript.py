from __future__ import annotations

from collections.abc import Iterable, Sequence

from oud.editor.core.state import EditorState
from oud.editor.interaction.dispatch import actions
from oud.editor.interaction.dispatch.controller import handle_key as dispatch_key
from oud.settings import DEFAULT_SETTINGS
from petrucci.terminal.canvas.framebuffer import FrameBuffer
from petrucci.core.model import Bar, Piece
from petrucci.rendering.api import render_piece

KeyToken = int | str


def keyscript_state(
    *,
    piece: Piece | None = None,
    width: int = 80,
    height: int = 24,
    strings: int = 6,
    style: str = "french",
    bar_width: int = 12,
    settings_override: dict[str, str] | None = None,
) -> EditorState:
    if piece is None:
        piece = Piece(title="T", bars=[Bar()], strings=strings, style=style)
    settings = dict(DEFAULT_SETTINGS)
    settings.update(
        {
            "style": style,
            "showtuning": "off",
            "showdur": "off",
            "showspans": "off",
            "showfingerings": "off",
            "showornaments": "off",
            "layout": "auto",
            "justify": "smart",
            "beatsnap": "soft",
            "linelen": "0",
            "barsperline": "0",
            "maxbars": "0",
            "barpad": "1",
            "flagredundant": "on",
        },
    )
    if settings_override:
        settings.update(settings_override)
    state = EditorState(piece, settings)
    state.screen_width = width
    state.screen_height = height
    state.bar_width = bar_width
    if not hasattr(state, "glisses"):
        state.glisses = []
    return state


def press_keys(state: EditorState, keys: Sequence[KeyToken]) -> None:
    for token in keys:
        key = token if isinstance(token, int) else ord(token)
        dispatch_key(
            state,
            key,
            handle_insert=actions.handle_insert,
            handle_normal=actions.handle_normal,
            handle_command=lambda _state, _key: True,
            handle_search=lambda _state, _key: True,
        )


def render_lines(state: EditorState, *, width: int | None = None, height: int | None = None) -> list[str]:
    fb = FrameBuffer(height or state.screen_height or 24, width or state.screen_width or 80)
    render_piece(
        fb,
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
        "",
        "",
        state.searchline,
        state.settings,
        None,
        state.stave_breaks,
        state.plugin_title,
        [],
        state.plugin_index,
        state.plugin_offset,
        state.help_offset,
        state.playback_bar,
        state.playback_col,
        getattr(state, "glisses", []),
    )
    return fb.snapshot().lines


def find_marker(lines: Iterable[str], marker: str) -> tuple[int, int] | None:
    for y, line in enumerate(lines):
        x = line.find(marker)
        if x >= 0:
            return (y, x)
    return None


def collect_cursor_cols_after_key(state: EditorState, key: KeyToken, count: int) -> list[int]:
    cols: list[int] = []
    for _ in range(count):
        press_keys(state, [key])
        cols.append(state.cursor_col)
    return cols


def first_flag_and_top_note_x(lines: Iterable[str]) -> tuple[int | None, int | None]:
    rows = list(lines)
    top_g_idx = next((i for i, line in enumerate(rows) if "g|" in line), None)
    if top_g_idx is None:
        return (None, None)
    g_row = rows[top_g_idx]
    note_x = g_row.find("a")
    flag_row = ""
    for line in reversed(rows[:top_g_idx]):
        if any(f"{label}|" in line for label in ("g", "d", "a", "f", "c")):
            continue
        if any(ch in line for ch in ("|", "\\", "=")):
            flag_row = line
            break
    if not flag_row:
        return (None, note_x if note_x >= 0 else None)
    glyph_positions = [i for i, ch in enumerate(flag_row) if ch in ("|", "\\", "=")]
    flag_x = glyph_positions[0] if glyph_positions else None
    return (flag_x, note_x if note_x >= 0 else None)
