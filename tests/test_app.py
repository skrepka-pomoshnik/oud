import curses
from typing import cast

from app import (
    EditorState,
    _apply_set_command,
    _cmd_bar,
    _cmd_footnote,
    _cmd_header,
    _cmd_stave,
    _cmd_subtitle,
    _cmd_title,
    _handle_key,
    _main,
    _status_line,
)
from core.model import Bar, Piece
from tui.input import history_next, history_prev, parse_search


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


def test_status_line_includes_path_cursor_and_modified(tmp_path) -> None:
    state = _state()
    state.path = str(tmp_path / "example.ft3")
    state.cursor_bar = 1
    state.cursor_string = 2
    state.cursor_col = 3
    state.modified = True
    line = _status_line(state)
    assert "example.ft3*" in line
    assert "bar:2" in line
    assert "str:3" in line
    assert "beat:2/4" in line


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


def test_set_command_updates_style_and_strings() -> None:
    state = _state()
    _apply_set_command(state, "style=italian strings=7")
    assert state.settings["style"] == "italian"
    assert state.settings["strings"] == "7"


def test_title_command_updates_piece() -> None:
    state = _state()
    _cmd_title(state, "Title")
    _cmd_subtitle(state, "Subtitle")
    _cmd_footnote(state, "Footnote")
    assert state.piece.title == "Title"
    assert state.piece.subtitle == "Subtitle"
    assert state.piece.footnote == "Footnote"


def test_header_template_populates_missing_fields() -> None:
    state = _state()
    _cmd_header(state, "")
    assert state.piece.title == "Title"
    assert state.piece.author == "Author"
    assert state.piece.composer == "Composer"


def test_bar_insert_shifts_state() -> None:
    state = _state()
    _cmd_bar(state, "add")
    assert len(state.piece.bars) == 2
    assert state.cursor_bar == 1


def test_bar_delete_shifts_state() -> None:
    state = _state()
    state.piece.bars.extend([Bar(), Bar()])
    state.cursor_bar = 1
    _cmd_bar(state, "del")
    assert len(state.piece.bars) == 2
    assert state.cursor_bar == 1


def test_vim_gg_moves_to_top() -> None:
    state = _state()
    state.piece.bars.extend([Bar(), Bar()])
    state.cursor_bar = 2
    _handle_key(state, ord("g"))
    _handle_key(state, ord("g"))
    assert state.cursor_bar == 0


def test_vim_dd_deletes_bar() -> None:
    state = _state()
    state.piece.bars.extend([Bar(), Bar()])
    state.cursor_bar = 1
    _handle_key(state, ord("d"))
    _handle_key(state, ord("d"))
    assert len(state.piece.bars) == 2


def test_vim_yy_p_pastes_bar() -> None:
    state = _state()
    state.piece.bars.extend([Bar(), Bar()])
    state.cursor_bar = 1
    _handle_key(state, ord("y"))
    _handle_key(state, ord("y"))
    _handle_key(state, ord("p"))
    assert len(state.piece.bars) == 4


def test_stave_break_and_join() -> None:
    state = _state()
    state.piece.bars.extend([Bar(), Bar(), Bar()])
    _cmd_stave(state, "break")
    assert 1 in state.stave_breaks
    _cmd_stave(state, "join")
    assert 1 not in state.stave_breaks


def test_stave_new_inserts_break() -> None:
    state = _state()
    state.piece.bars.extend([Bar(), Bar(), Bar()])
    state.cursor_bar = 1
    _cmd_stave(state, "new")
    assert 2 in state.stave_breaks


def test_stave_delete_removes_system() -> None:
    state = _state()
    state.piece.bars.extend([Bar(), Bar(), Bar()])
    state.cursor_bar = 2
    state.stave_breaks = {1, 2}
    _cmd_stave(state, "delete")
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

    assert _main(cast(curses.window, FakeWindow()), None) == 0


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

    assert _main(cast(curses.window, FakeWindow()), "missing.ft3") == 0
