import copy
import curses
import subprocess
from fractions import Fraction
from typing import cast

from oud.editor.commands.dispatch import cmd_bar, cmd_stave
from oud.editor.commands.metadata import cmd_footnote, cmd_header_template, cmd_subtitle, cmd_title
from oud.editor.core.document import configure_document
from oud.editor.core.state import EditorState
from oud.editor.interaction.dispatch.actions import handle_insert, handle_normal
from oud.editor.services.screen.status import status_line
from oud.presentation.tui.commands import apply_command, apply_set_command
from oud.presentation.tui.controller import handle_key
from oud.presentation.tui.input import handle_command as handle_command_input
from oud.presentation.tui.input import handle_search as handle_search_input
from oud.presentation.tui.input import history_next, history_prev, parse_search
from oud.presentation.tui.loop import InterruptLatch, _read_input_batch, run_loop
from petrucci.core.model import Bar, Chord, ImportedScore, Piece
from petrucci.terminal.canvas.framebuffer import Frame


def _state() -> EditorState:
    piece = Piece(title="T", bars=[Bar()])
    settings = {
        "style": "french",
        "measures": "start",
        "tuning": "",
        "strings": "6",
        "flagstyle": "standard",
        "key": "C",
        "countdots": "off",
        "keys": "vim+arrows",
        "spacing": "12",
        "linelen": "80",
        "staffthick": "1",
        "fontstyle": "modern",
        "charstyle": "standard",
        "midipatch": "0",
        "grid": "off",
        "showdur": "off",
        "showextras": "off",
        "showtactus": "off",
    }
    return EditorState(piece, settings)


def _patch_curses_smoke(monkeypatch, *, backspace: bool = False) -> None:
    values = {
        "curs_set": lambda *_args: None,
        "set_escdelay": lambda *_args: None,
        "napms": lambda *_args: None,
        "A_REVERSE": 0,
        "A_BOLD": 0,
        "KEY_RESIZE": -1,
        "KEY_EXIT": 27,
        "KEY_LEFT": -1,
        "KEY_RIGHT": -1,
        "KEY_UP": -1,
        "KEY_DOWN": -1,
        "KEY_PPAGE": -1,
        "KEY_NPAGE": -1,
        "KEY_HOME": -1,
        "KEY_END": -1,
        "KEY_IC": -1,
        "KEY_DC": -1,
        "ERR": -1,
    }
    if backspace:
        values["KEY_BACKSPACE"] = 127
    for name, value in values.items():
        monkeypatch.setattr(curses, name, value)


class _SmokeWindow:
    def __init__(self, keys: tuple[int, ...], size: tuple[int, int]) -> None:
        self._keys = iter(keys)
        self._size = size
        self.added = 0

    def getmaxyx(self) -> tuple[int, int]:
        return self._size

    def keypad(self, _flag: bool) -> None:
        return None

    def timeout(self, _delay: int) -> None:
        return None

    def erase(self) -> None:
        return None

    def refresh(self) -> None:
        return None

    def addstr(self, *_args: object, **_kwargs: object) -> None:
        self.added += 1

    def getch(self) -> int:
        return next(self._keys, -1)


def _run_smoke_window(window: _SmokeWindow, path: str | None = None) -> int:
    return run_loop(
        cast(curses.window, window),
        path,
        config_path="config.toml",
        handle_insert=handle_insert,
        handle_normal=handle_normal,
        apply_command=apply_command,
    )


def test_status_line_includes_cursor_and_modified(tmp_path) -> None:
    state = _state()
    configure_document(state, str(tmp_path / "example.ft3"))
    state.cursor_bar = 1
    state.cursor_string = 2
    quarter = Chord(note_type=4, dotted=False, grid=None, notes=[])
    state.piece.bars.append(Bar(chords=[copy.deepcopy(quarter) for _ in range(4)]))
    state.cursor_onset = Fraction(1, 4)
    state.modified = True
    line = status_line(state)
    assert "example.ft3*" in line
    assert "[FT3 EDIT:example.tab]" in line
    assert "bar:2" in line
    assert "beat:2/4" in line
    assert "str:3" in line
    assert "style:" not in line


def test_parse_search_one_based() -> None:
    assert parse_search("1") == 0
    assert parse_search("10") == 9
    assert parse_search("0") is None
    assert parse_search("x") is None


def test_command_history_navigation() -> None:
    state = _state()
    state.command_history = ["first", "second"]
    state.cmdline = history_prev(state) or ""
    assert state.cmdline == "second"
    state.cmdline = history_prev(state) or ""
    assert state.cmdline == "first"
    state.cmdline = history_next(state) or ""
    assert state.cmdline == "second"
    state.cmdline = history_next(state) or ""
    assert state.cmdline == ""


def test_set_command_updates_style_and_strings(tmp_path) -> None:
    state = _state()
    apply_set_command(state, "style=italian strings=7", str(tmp_path / "cfg.toml"))
    assert state.settings["style"] == "italian"
    assert state.settings["strings"] == "7"


def test_hide_command_toggles_bottom_panel(tmp_path) -> None:
    state = _state()
    config = str(tmp_path / "cfg.toml")
    apply_command(state, "hide", config)
    assert state.settings["bottompanel"] == "off"
    assert status_line(state) == ""
    apply_command(state, "hide", config)
    assert state.settings["bottompanel"] == "on"


def test_set_command_supports_vim_style_boolean_tokens(tmp_path) -> None:
    state = _state()
    cfg = str(tmp_path / "cfg.toml")
    apply_set_command(state, "grid", cfg)
    assert state.settings["grid"] == "on"
    apply_set_command(state, "nogrid", cfg)
    assert state.settings["grid"] == "off"
    apply_set_command(state, "invgrid", cfg)
    assert state.settings["grid"] == "on"
    apply_set_command(state, "grid!", cfg)
    assert state.settings["grid"] == "off"


def test_title_command_updates_piece() -> None:
    state = _state()
    cmd_title(state, "Title")
    cmd_subtitle(state, "Subtitle")
    cmd_footnote(state, "Footnote")
    assert state.piece.title == "Title"
    assert state.piece.subtitle == "Subtitle"
    assert state.piece.footnote == "Footnote"


def test_header_template_populates_missing_fields() -> None:
    state = _state()
    cmd_header_template(state, "")
    assert state.piece.title == "Title"
    assert state.piece.author == "Author"
    assert state.piece.composer == "Composer"


def test_bar_insert_shifts_state() -> None:
    state = _state()
    cmd_bar(state, "add")
    assert len(state.piece.bars) == 2
    assert state.cursor_bar == 1


def test_bar_delete_shifts_state() -> None:
    state = _state()
    state.piece.bars.extend([Bar(), Bar()])
    state.cursor_bar = 1
    cmd_bar(state, "del")
    assert len(state.piece.bars) == 2
    assert state.cursor_bar == 1


def _dispatch(state: EditorState, key: int) -> bool:
    return handle_key(
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


def test_vim_gg_moves_to_top() -> None:
    state = _state()
    state.piece.bars.extend([Bar(), Bar()])
    state.cursor_bar = 2
    _dispatch(state, ord("g"))
    _dispatch(state, ord("g"))
    assert state.cursor_bar == 0


def test_vim_dd_deletes_bar() -> None:
    state = _state()
    state.piece.bars.extend([Bar(), Bar()])
    state.cursor_bar = 1
    _dispatch(state, ord("d"))
    _dispatch(state, ord("d"))
    assert len(state.piece.bars) == 2


def test_vim_yy_p_pastes_bar() -> None:
    state = _state()
    state.piece.bars.extend([Bar(), Bar()])
    state.cursor_bar = 1
    _dispatch(state, ord("y"))
    _dispatch(state, ord("y"))
    _dispatch(state, ord("p"))
    assert len(state.piece.bars) == 4


def test_stave_break_and_join() -> None:
    state = _state()
    state.piece.bars.extend([Bar(), Bar(), Bar()])
    cmd_stave(state, "break")
    assert 1 in state.stave_breaks
    cmd_stave(state, "join")
    assert 1 not in state.stave_breaks


def test_stave_new_inserts_break() -> None:
    state = _state()
    state.piece.bars.extend([Bar(), Bar(), Bar()])
    state.cursor_bar = 1
    cmd_stave(state, "new")
    assert 2 in state.stave_breaks


def test_stave_delete_removes_system() -> None:
    state = _state()
    state.piece.bars.extend([Bar(), Bar(), Bar()])
    state.cursor_bar = 2
    state.stave_breaks = {1, 2}
    cmd_stave(state, "delete")
    assert 2 not in state.stave_breaks


def test_app_main_smoke(monkeypatch) -> None:
    _patch_curses_smoke(monkeypatch)
    assert _run_smoke_window(_SmokeWindow((ord("q"),), (1, 1))) == 0


def test_read_input_batch_drains_queued_repeat_keys_before_render() -> None:
    class _QueuedWindow:
        def __init__(self) -> None:
            self.keys = [ord("h"), ord("h"), ord("h"), -1]
            self.timeouts: list[int] = []

        def timeout(self, delay: int) -> None:
            self.timeouts.append(delay)

        def getch(self) -> int:
            return self.keys.pop(0)

    window = _QueuedWindow()
    keys = _read_input_batch(cast(curses.window, window), 50, InterruptLatch())

    assert keys == (ord("h"), ord("h"), ord("h"))
    assert window.timeouts == [50, 0]


def test_app_main_smoke_with_path(monkeypatch) -> None:
    _patch_curses_smoke(monkeypatch)
    window = _SmokeWindow((ord("q"),), (1, 1))
    assert _run_smoke_window(window, "missing.ft3") == 0


def test_app_main_smoke_interactions(monkeypatch) -> None:
    _patch_curses_smoke(monkeypatch, backspace=True)
    window = _SmokeWindow(
        (ord(":"), ord("w"), 127, 27, ord("/"), ord("1"), 10, ord("q")),
        (12, 60),
    )
    assert _run_smoke_window(window) == 0
    assert window.added > 0


class _PlaybackScrollFakeWindow:
    def __init__(self) -> None:
        self._calls = 0

    def getmaxyx(self):
        return (12, 40)

    def keypad(self, _flag):
        return None

    def timeout(self, _delay):
        return None

    def erase(self):
        return None

    def refresh(self):
        return None

    def addstr(self, *_args, **_kwargs):
        return None

    def getch(self):
        if self._calls == 0:
            self._calls += 1
            return -1
        return ord("q")


def _playback_scroll_state() -> EditorState:
    piece = Piece(title="T", bars=[Bar() for _ in range(20)], strings=6)
    state = EditorState(
        piece,
        {
            "style": "french",
            "layout": "packed",
            "barsperline": "2",
            "bargap": "1",
            "showdur": "off",
            "showextras": "off",
            "showtactus": "off",
            "flagstems": "single",
            "playbackscroll": "on",
        },
    )
    state.bar_width = 8
    state.playback_bar = 8
    state.playback_col = 0
    state.last_frame_size = (12, 40)
    blank = Frame(lines=[" " * 40 for _ in range(12)], attrs=[tuple([0] * 40) for _ in range(12)])
    state.last_base_frame = blank
    state.last_frame = blank
    state.playback_overlay_cache = {}
    state.playback_overlay_key = (-1, -1)
    return state


def test_run_loop_forces_full_render_when_playback_scroll_changes_viewport(monkeypatch) -> None:
    monkeypatch.setattr(curses, "curs_set", lambda *_args: None)
    monkeypatch.setattr(curses, "set_escdelay", lambda *_args: None)
    state = _playback_scroll_state()
    render_bar_offsets: list[int] = []

    def _fake_init_state(*_args, **_kwargs):
        return state

    def _fake_update_playback_animation(_state: EditorState) -> bool:
        return True

    def _fake_render_piece(*args, **_kwargs):
        render_bar_offsets.append(args[2])

    monkeypatch.setattr("oud.presentation.tui.loop.init_state", _fake_init_state)
    monkeypatch.setattr("oud.presentation.tui.loop.update_playback_animation", _fake_update_playback_animation)
    monkeypatch.setattr("oud.editor.services.screen.compose.render_piece", _fake_render_piece)

    assert (
        run_loop(
            cast(curses.window, _PlaybackScrollFakeWindow()),
            None,
            config_path="config.toml",
            handle_insert=handle_insert,
            handle_normal=handle_normal,
            apply_command=apply_command,
        )
        == 0
    )
    assert render_bar_offsets
    assert render_bar_offsets[0] > 0


def test_run_loop_follows_playback_advanced_during_full_render(monkeypatch) -> None:
    monkeypatch.setattr(curses, "curs_set", lambda *_args: None)
    monkeypatch.setattr(curses, "set_escdelay", lambda *_args: None)
    state = _playback_scroll_state()
    state.bar_offset = 0
    state.playback_bar = 0
    updates = 0
    render_bar_offsets: list[int] = []

    class _DelayedQuitWindow(_PlaybackScrollFakeWindow):
        def getch(self):
            self._calls += 1
            if self._calls <= 2:
                return -1
            return ord("q")

    def _fake_init_state(*_args, **_kwargs):
        return state

    def _fake_update_playback_animation(updated_state: EditorState) -> bool:
        nonlocal updates
        updates += 1
        if updates != 2:
            return False
        updated_state.playback.bar = 8
        updated_state.playback.col = 0
        updated_state.playback.markers = [(8, 0)]
        return True

    def _fake_render_piece(*args, **_kwargs):
        render_bar_offsets.append(args[2])

    monkeypatch.setattr("oud.presentation.tui.loop.init_state", _fake_init_state)
    monkeypatch.setattr("oud.presentation.tui.loop.update_playback_animation", _fake_update_playback_animation)
    monkeypatch.setattr("oud.editor.services.screen.compose.render_piece", _fake_render_piece)

    assert (
        run_loop(
            cast(curses.window, _DelayedQuitWindow()),
            None,
            config_path="config.toml",
            handle_insert=handle_insert,
            handle_normal=handle_normal,
            apply_command=apply_command,
        )
        == 0
    )
    assert render_bar_offsets[:2] == [0, 8]


def test_run_loop_resamples_playback_after_full_render(monkeypatch) -> None:
    monkeypatch.setattr(curses, "curs_set", lambda *_args: None)
    monkeypatch.setattr(curses, "set_escdelay", lambda *_args: None)
    state = _playback_scroll_state()
    state.settings["playbackscroll"] = "off"

    class _FinishedPlayer:
        def poll(self) -> int:
            return 0

    state.midi_proc = cast(subprocess.Popen[bytes], _FinishedPlayer())
    updates = 0
    rendered_markers: list[object] = []

    class _OneFrameWindow(_PlaybackScrollFakeWindow):
        def getch(self):
            return ord("q")

    def _fake_init_state(*_args, **_kwargs):
        return state

    def _fake_update_playback_animation(updated_state: EditorState) -> bool:
        nonlocal updates
        updates += 1
        updated_state.playback.bar = 0
        updated_state.playback.col = min(1, updates - 1)
        updated_state.playback.markers = [(0, updated_state.playback.col)]
        return True

    def _fake_render_piece(*_args, **kwargs):
        rendered_markers.append(kwargs["playback_markers"])
        cache = kwargs["playback_cache"]
        cache[(0, 0)] = [(2, 2, "a", 1)]
        cache[(0, 1)] = [(2, 3, "b", 1)]

    monkeypatch.setattr("oud.presentation.tui.loop.init_state", _fake_init_state)
    monkeypatch.setattr("oud.presentation.tui.loop.update_playback_animation", _fake_update_playback_animation)
    monkeypatch.setattr("oud.editor.services.screen.compose.render_piece", _fake_render_piece)

    assert (
        run_loop(
            cast(curses.window, _OneFrameWindow()),
            None,
            config_path="config.toml",
            handle_insert=handle_insert,
            handle_normal=lambda *_args: False,
            apply_command=apply_command,
        )
        == 0
    )
    assert updates == 2
    assert rendered_markers == [None]
    assert state.playback_overlay_key == (0, 1)


def test_run_loop_passes_playback_position_to_imported_score_renderer(monkeypatch) -> None:
    monkeypatch.setattr(curses, "curs_set", lambda *_args: None)
    monkeypatch.setattr(curses, "set_escdelay", lambda *_args: None)
    state = _playback_scroll_state()
    state.piece.imported_score = ImportedScore("ft3")
    rendered_positions: list[tuple[object, object, object]] = []

    class _OneFrameWindow(_PlaybackScrollFakeWindow):
        def getch(self):
            return ord("q")

    def _fake_init_state(*_args, **_kwargs):
        return state

    def _fake_render_piece(*_args, **kwargs):
        rendered_positions.append((kwargs["playback_bar"], kwargs["playback_col"], kwargs["playback_cache"]))

    monkeypatch.setattr("oud.presentation.tui.loop.init_state", _fake_init_state)
    monkeypatch.setattr("oud.presentation.tui.loop.update_playback_animation", lambda _state: False)
    monkeypatch.setattr("oud.editor.services.screen.compose.render_piece", _fake_render_piece)

    assert (
        run_loop(
            cast(curses.window, _OneFrameWindow()),
            None,
            config_path="config.toml",
            handle_insert=handle_insert,
            handle_normal=lambda *_args: False,
            apply_command=apply_command,
        )
        == 0
    )
    assert rendered_positions == [(8, 0, None)]
