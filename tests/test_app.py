import curses
from typing import cast

from oud.editor.actions import handle_insert, handle_normal
from oud.editor.command_ops import cmd_bar, cmd_stave
from oud.editor.commands import cmd_footnote, cmd_header_template, cmd_subtitle, cmd_title
from oud.editor.document import configure_document
from oud.editor.state import EditorState
from oud.editor.status import status_line
from oud.petrucci.framebuffer import Frame
from oud.petrucci.model import Bar, Piece
from oud.tui.commands import apply_command, apply_set_command
from oud.tui.controller import handle_key
from oud.tui.input import handle_command as handle_command_input
from oud.tui.input import handle_search as handle_search_input
from oud.tui.input import history_next, history_prev, parse_search
from oud.tui.loop import run_loop


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


def test_status_line_includes_cursor_and_modified(tmp_path) -> None:
    state = _state()
    configure_document(state, str(tmp_path / "example.ft3"))
    state.cursor_bar = 1
    state.cursor_string = 2
    state.cursor_col = 3
    state.modified = True
    line = status_line(state)
    assert "example.ft3*" in line
    assert "[FT3->TAB?]" in line
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
    monkeypatch.setattr(curses, "curs_set", lambda *_args: None)
    monkeypatch.setattr(curses, "napms", lambda *_args: None)
    monkeypatch.setattr(curses, "A_REVERSE", 0)
    monkeypatch.setattr(curses, "A_BOLD", 0)
    monkeypatch.setattr(curses, "KEY_RESIZE", -1)
    monkeypatch.setattr(curses, "KEY_EXIT", 27)
    monkeypatch.setattr(curses, "KEY_LEFT", -1)
    monkeypatch.setattr(curses, "KEY_RIGHT", -1)
    monkeypatch.setattr(curses, "KEY_UP", -1)
    monkeypatch.setattr(curses, "KEY_DOWN", -1)
    monkeypatch.setattr(curses, "KEY_PPAGE", -1)
    monkeypatch.setattr(curses, "KEY_NPAGE", -1)
    monkeypatch.setattr(curses, "KEY_HOME", -1)
    monkeypatch.setattr(curses, "KEY_END", -1)
    monkeypatch.setattr(curses, "KEY_IC", -1)
    monkeypatch.setattr(curses, "KEY_DC", -1)
    monkeypatch.setattr(curses, "ERR", -1)

    class FakeWindow:
        def __init__(self) -> None:
            self._calls = 0

        def getmaxyx(self):
            return (1, 1)

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
                return ord("q")
            return -1

    assert (
        run_loop(
            cast(curses.window, FakeWindow()),
            None,
            config_path="config.toml",
            handle_insert=handle_insert,
            handle_normal=handle_normal,
            apply_command=apply_command,
        )
        == 0
    )


def test_app_main_smoke_with_path(monkeypatch) -> None:
    monkeypatch.setattr(curses, "curs_set", lambda *_args: None)
    monkeypatch.setattr(curses, "napms", lambda *_args: None)
    monkeypatch.setattr(curses, "A_REVERSE", 0)
    monkeypatch.setattr(curses, "A_BOLD", 0)
    monkeypatch.setattr(curses, "KEY_RESIZE", -1)
    monkeypatch.setattr(curses, "KEY_EXIT", 27)
    monkeypatch.setattr(curses, "KEY_LEFT", -1)
    monkeypatch.setattr(curses, "KEY_RIGHT", -1)
    monkeypatch.setattr(curses, "KEY_UP", -1)
    monkeypatch.setattr(curses, "KEY_DOWN", -1)
    monkeypatch.setattr(curses, "KEY_PPAGE", -1)
    monkeypatch.setattr(curses, "KEY_NPAGE", -1)
    monkeypatch.setattr(curses, "KEY_HOME", -1)
    monkeypatch.setattr(curses, "KEY_END", -1)
    monkeypatch.setattr(curses, "KEY_IC", -1)
    monkeypatch.setattr(curses, "KEY_DC", -1)
    monkeypatch.setattr(curses, "ERR", -1)

    class FakeWindow:
        def __init__(self) -> None:
            self._calls = 0

        def getmaxyx(self):
            return (1, 1)

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
                return ord("q")
            return -1

    assert (
        run_loop(
            cast(curses.window, FakeWindow()),
            "missing.ft3",
            config_path="config.toml",
            handle_insert=handle_insert,
            handle_normal=handle_normal,
            apply_command=apply_command,
        )
        == 0
    )


def test_app_main_smoke_interactions(monkeypatch) -> None:
    monkeypatch.setattr(curses, "curs_set", lambda *_args: None)
    monkeypatch.setattr(curses, "napms", lambda *_args: None)
    monkeypatch.setattr(curses, "A_REVERSE", 0)
    monkeypatch.setattr(curses, "A_BOLD", 0)
    monkeypatch.setattr(curses, "KEY_RESIZE", -1)
    monkeypatch.setattr(curses, "KEY_EXIT", 27)
    monkeypatch.setattr(curses, "KEY_LEFT", -1)
    monkeypatch.setattr(curses, "KEY_RIGHT", -1)
    monkeypatch.setattr(curses, "KEY_UP", -1)
    monkeypatch.setattr(curses, "KEY_DOWN", -1)
    monkeypatch.setattr(curses, "KEY_PPAGE", -1)
    monkeypatch.setattr(curses, "KEY_NPAGE", -1)
    monkeypatch.setattr(curses, "KEY_HOME", -1)
    monkeypatch.setattr(curses, "KEY_END", -1)
    monkeypatch.setattr(curses, "KEY_IC", -1)
    monkeypatch.setattr(curses, "KEY_DC", -1)
    monkeypatch.setattr(curses, "KEY_BACKSPACE", 127)
    monkeypatch.setattr(curses, "ERR", -1)

    class FakeWindow:
        def __init__(self) -> None:
            self._calls = 0
            self.added = 0
            self._keys = [
                ord(":"),
                ord("w"),
                127,
                27,
                ord("/"),
                ord("1"),
                10,
                ord("q"),
            ]

        def getmaxyx(self):
            return (12, 60)

        def keypad(self, _flag):
            return None

        def timeout(self, _delay):
            return None

        def erase(self):
            return None

        def refresh(self):
            return None

        def addstr(self, *_args, **_kwargs):
            self.added += 1

        def getch(self):
            if self._calls < len(self._keys):
                key = self._keys[self._calls]
                self._calls += 1
                return key
            return -1

    window = FakeWindow()
    assert (
        run_loop(
            cast(curses.window, window),
            None,
            config_path="config.toml",
            handle_insert=handle_insert,
            handle_normal=handle_normal,
            apply_command=apply_command,
        )
        == 0
    )
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
    state = _playback_scroll_state()
    render_bar_offsets: list[int] = []

    def _fake_init_state(*_args, **_kwargs):
        return state

    def _fake_update_playback_animation(_state: EditorState) -> bool:
        return True

    def _fake_render_piece(*args, **_kwargs):
        render_bar_offsets.append(args[2])

    monkeypatch.setattr("oud.tui.loop.init_state", _fake_init_state)
    monkeypatch.setattr("oud.tui.loop.update_playback_animation", _fake_update_playback_animation)
    monkeypatch.setattr("oud.tui.loop.render_piece", _fake_render_piece)

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
