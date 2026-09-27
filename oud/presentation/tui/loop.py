from __future__ import annotations

import curses
import os
import signal
from types import FrameType

from oud.editor.commands.help import help_lines
from oud.editor.core.feedback.transient import decay_transient_message
from oud.editor.core.input.modes import Mode
from oud.editor.navigation.view.focus import current_view_staff
from oud.editor.navigation.view.state import view_commit_frame, view_merge_dirty, view_resize
from oud.editor.navigation.viewport import ensure_cursor_visible
from oud.editor.services.bootstrap import init_state
from oud.editor.services.media.jobs import drain_background_messages
from oud.editor.services.media.midi import stop_midi
from oud.editor.services.media.playback import update_playback_animation
from oud.editor.services.status import status_line
from oud.exports.export_tab import export_ascii
from oud.presentation.tui.controller import handle_key as handle_key_impl
from oud.presentation.tui.input import handle_command as handle_command_input
from oud.presentation.tui.input import handle_search as handle_search_input
from oud.presentation.tui.keycodes import keycodes_from_curses
from oud.presentation.ui.adapter import CursesScreen, apply_theme_background, contrast_attr, theme_attr
from petrucci.adapters.duet import is_duet_score_piece
from petrucci.rendering.api import render_piece
from petrucci.terminal.canvas.framebuffer import (
    FrameBuffer,
    draw_frame_rows,
    frame_diff_rows,
    overlay_dirty_rows,
    overlay_frame,
)

_MAX_INPUT_BATCH = 64
CTRL_C = 3


class InterruptLatch:
    """SIGINT handler that records Ctrl-C instead of raising mid-edit or mid-render.

    The key loop turns a latched interrupt into the Ctrl-C key, so it follows the
    editor's quit, cancel and unsaved-changes rules.
    """

    def __init__(self) -> None:
        self.pending = False

    def __call__(self, _signum: int, _frame: FrameType | None) -> None:
        self.pending = True

    def take(self) -> bool:
        pending = self.pending
        self.pending = False
        return pending


def _read_input_batch(stdscr: curses.window, timeout_ms: int, interrupts: InterruptLatch) -> tuple[int, ...]:
    if interrupts.take():
        return (CTRL_C,)
    stdscr.timeout(timeout_ms)
    first = stdscr.getch()
    if first == -1:
        return (CTRL_C,) if interrupts.take() else ()
    keys = [first]
    stdscr.timeout(0)
    for _ in range(_MAX_INPUT_BATCH - 1):
        key = stdscr.getch()
        if key == -1:
            break
        keys.append(key)
    if interrupts.take():
        keys.append(CTRL_C)
    return tuple(keys)


def _handle_input_batch(
    stdscr: curses.window,
    state,
    *,
    handle_insert,
    handle_normal,
    apply_command,
    needs_render: bool,
    interrupts: InterruptLatch,
) -> tuple[bool, bool]:
    running = True
    keys = _read_input_batch(stdscr, 10 if state.midi_proc is not None else 50, interrupts)
    for key in keys:
        running = handle_key_impl(
            state,
            key,
            handle_insert=handle_insert,
            handle_normal=handle_normal,
            handle_command=lambda s, k: handle_command_input(
                s,
                k,
                lambda st, cmd: apply_command(st, cmd, state.config_path),
            ),
            handle_search=handle_search_input,
        )
        needs_render = True
        if not running:
            break
    return running, needs_render


def _try_playback_overlay(state, screen, *, viewport_changed: bool) -> bool:
    if viewport_changed or state.last_base_frame is None or state.playback_overlay_cache is None:
        return False
    prev_key = state.playback_overlay_key or (-1, -1)
    playback_key = (
        state.playback_bar if state.playback_bar is not None else -1,
        state.playback_col if state.playback_col is not None else -1,
    )
    prev_ops = state.playback_overlay_cache.get(prev_key, [])
    next_ops = state.playback_overlay_cache.get(playback_key, [])
    dirty = {y for y, _x, _text, _attr in prev_ops}
    dirty |= {y for y, _x, _text, _attr in next_ops}
    frame = overlay_dirty_rows(
        state.last_frame or state.last_base_frame,
        base_frame=state.last_base_frame,
        ops=next_ops,
        rows=dirty,
    )
    draw_frame_rows(screen, frame, dirty)
    screen.refresh()
    state.playback_overlay_key = playback_key
    view_commit_frame(state, frame)
    return True


def _render_full_frame(state, *, height: int, width: int, screen) -> bool:
    ascii_preview_lines = (
        export_ascii(
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
        ).splitlines()
        if state.ascii_preview
        else None
    )
    frame_buffer = FrameBuffer(height, width)
    focused_staff = current_view_staff(state)
    state.display_cursor_maps.clear()
    playback_cache: dict[tuple[int, int], list[tuple[int, int, str, int]]] | None = (
        {} if not is_duet_score_piece(state.piece) and state.piece.imported_score is None else None
    )
    render_piece(
        frame_buffer,
        state.piece,
        state.bar_offset,
        state.cursor_bar,
        state.cursor_string,
        cursor_col=state.cursor_col,
        bar_width=state.bar_width,
        overrides=state.overrides,
        durations=state.durations,
        ornaments=state.ornaments,
        annotations=state.annotations,
        highlights=state.highlights,
        dotted=state.dotted,
        slurs=state.slurs,
        ties=state.ties,
        holds=state.holds,
        mode=state.mode,
        cmdline=state.cmdline,
        message=state.visible_message,
        status_line=status_line(state),
        searchline=state.searchline,
        settings=state.settings,
        ascii_lines=ascii_preview_lines,
        stave_breaks=state.stave_breaks,
        plugin_title=state.plugin_title,
        plugin_items=[f"{item.title}{'/' if item.is_dir else ''}" for item in state.plugin_items],
        plugin_index=state.plugin_index,
        plugin_offset=state.plugin_offset,
        help_offset=state.info_offset
        if state.mode == "info"
        else state.notes_offset
        if state.mode == "notes"
        else state.help_offset,
        playback_bar=None if playback_cache is not None else state.playback_bar,
        playback_col=None if playback_cache is not None else state.playback_col,
        playback_markers=None if playback_cache is not None else state.playback.markers,
        playback_cache=playback_cache,
        cursor_display_maps=state.display_cursor_maps,
        message_level=state.visible_message_level.value,
        focused_imported_staff_index=(
            focused_staff.source_index if not focused_staff.key.startswith("duet-") else None
        ),
        playback_verse=state.playback.verse,
        help_lines=help_lines(state) if state.mode == Mode.HELP else (),
    )
    base_frame = frame_buffer.snapshot()
    state.last_base_frame = base_frame
    state.playback_overlay_cache = playback_cache
    rerender_for_playback_scroll = False
    if playback_cache is not None:
        playback_resampled = update_playback_animation(state)
        if playback_resampled:
            resampled_bar_offset = state.bar_offset
            ensure_cursor_visible(state, width, height)
            rerender_for_playback_scroll = state.bar_offset != resampled_bar_offset
        playback_key = (
            state.playback_bar if state.playback_bar is not None else -1,
            state.playback_col if state.playback_col is not None else -1,
        )
        frame = overlay_frame(base_frame, playback_cache.get(playback_key, []))
        state.playback_overlay_key = playback_key
    else:
        frame = base_frame
        state.playback_overlay_key = None
    dirty = frame_diff_rows(state.last_frame, frame)
    dirty = view_merge_dirty(state, dirty)
    draw_frame_rows(screen, frame, dirty)
    screen.refresh()
    view_commit_frame(state, frame)
    return rerender_for_playback_scroll


def _render_iteration(stdscr: curses.window, state, needs_render: bool) -> bool:
    background_changed = drain_background_messages(state)
    message_changed = decay_transient_message(state)
    height, width = stdscr.getmaxyx()
    state.screen_height = height
    state.screen_width = width
    state.clamp()
    playback_changed = update_playback_animation(state)
    resized = view_resize(state, height=height, width=width)
    should_render = (
        needs_render or background_changed or message_changed or playback_changed or resized or state.dirty_rows
    )
    if not should_render:
        return needs_render
    prev_bar_offset = state.bar_offset
    ensure_cursor_visible(state, width, height)
    viewport_changed = state.bar_offset != prev_bar_offset
    theme_base = theme_attr(state.settings.get("theme", "auto"))
    apply_theme_background(stdscr, theme_base)
    base_attr = theme_base | contrast_attr(state.settings.get("contrast", "normal"))
    screen = CursesScreen(stdscr, base_attr=base_attr)
    playback_only = (
        playback_changed
        and not needs_render
        and not background_changed
        and not message_changed
        and not resized
        and not state.dirty_rows
    )
    if playback_only and _try_playback_overlay(state, screen, viewport_changed=viewport_changed):
        return False
    return _render_full_frame(state, height=height, width=width, screen=screen)


# ncurses waits 1 s by default to tell Esc from an escape sequence, which makes
# leaving insert mode feel broken. An explicit ESCDELAY in the environment wins.
ESCAPE_DELAY_MS = 25


def configure_terminal(stdscr: curses.window) -> None:
    curses.curs_set(0)
    if "ESCDELAY" not in os.environ:
        curses.set_escdelay(ESCAPE_DELAY_MS)
    stdscr.keypad(True)
    stdscr.timeout(50)


def run_loop(
    stdscr: curses.window,
    path: str | None,
    *,
    config_path: str,
    handle_insert,
    handle_normal,
    apply_command,
    read_only: bool = False,
) -> int:
    configure_terminal(stdscr)

    state = init_state(path, config_path=config_path, read_only=read_only)
    state.keycodes = keycodes_from_curses()

    def suspend_tui() -> None:
        curses.def_prog_mode()
        curses.endwin()

    def resume_tui() -> None:
        curses.reset_prog_mode()
        stdscr.refresh()

    state.suspend_tui = suspend_tui
    state.resume_tui = resume_tui

    needs_render = True
    running = True
    interrupts = InterruptLatch()
    previous_handler = signal.signal(signal.SIGINT, interrupts)
    try:
        while running:
            needs_render = _render_iteration(stdscr, state, needs_render)
            running, needs_render = _handle_input_batch(
                stdscr,
                state,
                handle_insert=handle_insert,
                handle_normal=handle_normal,
                apply_command=apply_command,
                needs_render=needs_render,
                interrupts=interrupts,
            )
    finally:
        signal.signal(signal.SIGINT, previous_handler)
        # `:q` exits through SystemExit and other failures raise; never leave a player running.
        stop_midi(state)
    return 0
