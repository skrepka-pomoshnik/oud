from app import (
    EditorState,
    _apply_duration,
    _apply_override,
    _apply_set_command,
    _convert_overrides,
    _handle_insert,
    _history_next,
    _history_prev,
    _is_italian_fret,
    _main,
    _parse_search,
    _set_annotation,
    _set_barline,
    _set_highlight,
    _set_hold,
    _set_ornament,
    _set_repeat,
    _set_slur,
    _set_tie,
    _status_line,
    _undo,
)
from model import Bar, Piece


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


def test_status_line_includes_path_cursor_and_modified() -> None:
    state = _state()
    state.path = "/tmp/example.ft3"
    state.cursor_bar = 1
    state.cursor_string = 2
    state.cursor_col = 3
    state.modified = True
    line = _status_line(state)
    assert "example.ft3*" in line
    assert "bar:2" in line
    assert "str:3" in line
    assert "col:4" in line


def test_parse_search_one_based() -> None:
    assert _parse_search("1") == 0
    assert _parse_search("10") == 9
    assert _parse_search("0") is None
    assert _parse_search("x") is None


def test_undo_override_removes_cell() -> None:
    state = _state()
    key = (0, 0, 0)
    _apply_override(state, key, "a")
    assert state.overrides[key] == "a"
    _undo(state)
    assert key not in state.overrides


def test_undo_duration_restores_previous() -> None:
    state = _state()
    key = (0, 0, 0)
    _apply_duration(state, key, 4)
    _apply_duration(state, key, 8)
    _undo(state)
    assert state.durations[key] == 4


def test_command_history_navigation() -> None:
    state = _state()
    state.command_history = ["w", "e foo.ft3", "q"]
    assert _history_prev(state) == "q"
    assert _history_prev(state) == "e foo.ft3"
    assert _history_next(state) == "q"
    assert _history_next(state) == ""


def test_set_command_updates_style_and_strings() -> None:
    state = _state()
    _apply_set_command(
        state, "style=italian strings=7 measures=five tuning=renaissance flagstyle=thin"
    )
    assert state.settings["style"] == "italian"
    assert state.settings["measures"] == "five"
    assert state.settings["tuning"] == "C4D4E4F4G4c3f3a2d2g2"
    assert state.settings["strings"] == "7"
    assert state.settings["flagstyle"] == "thin"
    assert state.piece.strings == 7


def test_italian_fret_validation() -> None:
    assert _is_italian_fret("0") is True
    assert _is_italian_fret("9") is True
    assert _is_italian_fret("x") is True
    assert _is_italian_fret("a") is False


def test_insert_italian_digit_sets_fret_not_duration() -> None:
    state = _state()
    state.settings["style"] = "italian"
    state.mode = "insert"
    _handle_insert(state, ord("1"))
    assert (0, 0, 0) in state.overrides
    assert state.overrides[(0, 0, 0)] == "1"
    assert (0, 0, 0) not in state.durations


def test_insert_french_digit_sets_duration() -> None:
    state = _state()
    state.settings["style"] = "french"
    state.mode = "insert"
    _handle_insert(state, ord("3"))
    assert (0, 0, 0) in state.durations
    assert state.durations[(0, 0, 0)] == 4


def test_grid_mode_advances_two_cells() -> None:
    state = _state()
    state.settings["grid"] = "on"
    state.mode = "insert"
    _handle_insert(state, ord("a"))
    assert state.cursor_col == 2


def test_convert_overrides_french_to_italian() -> None:
    state = _state()
    state.overrides[(0, 0, 0)] = "a"
    state.overrides[(0, 0, 1)] = "k"
    _convert_overrides(state, "italian")
    assert state.overrides[(0, 0, 0)] == "0"
    assert state.overrides[(0, 0, 1)] == "x"


def test_convert_overrides_italian_to_french() -> None:
    state = _state()
    state.overrides[(0, 0, 0)] = "0"
    state.overrides[(0, 0, 1)] = "x"
    _convert_overrides(state, "french")
    assert state.overrides[(0, 0, 0)] == "a"
    assert state.overrides[(0, 0, 1)] == "k"


def test_set_barline_and_repeat() -> None:
    state = _state()
    _set_barline(state, "double")
    _set_repeat(state, "start")
    bar = state.piece.bars[0]
    assert bar.barline == "||"
    assert bar.repeat == ".:"


def test_ornament_annotation_highlight() -> None:
    state = _state()
    _set_ornament(state, "#")
    _set_annotation(state, "note")
    _set_highlight(state, "on")
    assert state.ornaments[(0, 0)] == "#"
    assert state.annotations[(0, 0)] == "note"
    assert (0, 0, 0) in state.highlights


def test_slur_tie_hold_spans() -> None:
    state = _state()
    _set_slur(state, "start")
    state.cursor_col = 3
    _set_slur(state, "end")
    _set_tie(state, "start")
    state.cursor_col = 2
    _set_tie(state, "end")
    _set_hold(state, "start")
    state.cursor_col = 1
    _set_hold(state, "end")
    assert state.slurs[0] == (0, 0, 3)
    assert state.ties[0] == (0, 2, 3)
    assert state.holds[0] == (0, 1, 2)


def test_app_main_smoke(monkeypatch) -> None:
    class DummyScreen:
        def keypad(self, _flag: bool) -> None:
            return None

        def timeout(self, _ms: int) -> None:
            return None

        def getmaxyx(self) -> tuple[int, int]:
            return (24, 80)

        def getch(self) -> int:
            return ord("q")

    monkeypatch.setattr("curses.curs_set", lambda _val: None)
    monkeypatch.setattr("app.render_piece", lambda *args, **kwargs: None)
    assert _main(DummyScreen(), None) == 0


def test_app_main_smoke_with_path(monkeypatch) -> None:
    class DummyScreen:
        def keypad(self, _flag: bool) -> None:
            return None

        def timeout(self, _ms: int) -> None:
            return None

        def getmaxyx(self) -> tuple[int, int]:
            return (24, 80)

        def getch(self) -> int:
            return ord("q")

    monkeypatch.setattr("curses.curs_set", lambda _val: None)
    monkeypatch.setattr("app.render_piece", lambda *args, **kwargs: None)
    monkeypatch.setattr("app._load_piece", lambda _path: Piece(title="T", bars=[Bar()]))
    assert _main(DummyScreen(), "example.ft3") == 0
