from app import (
    EditorState,
    _apply_duration,
    _apply_override,
    _clear_cell,
    _convert_overrides,
    _handle_insert,
    _handle_key,
    _redo,
    _set_annotation,
    _set_barline,
    _set_highlight,
    _set_hold,
    _set_ornament,
    _set_repeat,
    _set_slur,
    _set_tie,
    _undo,
    is_italian_fret,
)
from core.model import Bar, Chord, Note, Piece


def _state() -> EditorState:
    piece = Piece(title="T", bars=[Bar()])
    settings = {
        "style": "french",
        "measures": "start",
        "tuning": "g2c3f3a3d4g4",
        "strings": "6",
        "flagstyle": "standard",
        "time": "C",
        "key": "C",
        "countdots": "off",
        "keys": "vim+arrows",
        "spacing": "10",
        "spacingmode": "packed",
        "maxbars": "0",
        "linelen": "80",
        "grid": "off",
        "showdur": "off",
        "showextras": "off",
        "showtactus": "off",
        "staffthick": "1",
        "fontstyle": "modern",
        "charstyle": "standard",
        "midipatch": "0",
    }
    return EditorState(piece, settings)


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


def test_insert_duration_updates_chord_note_type() -> None:
    state = _state()
    chord = Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])
    state.piece.bars[0].chords = [chord]
    state.mode = "insert"
    _handle_insert(state, ord("8"))
    assert state.piece.bars[0].chords == []
    assert state.durations[(0, 0, 0)] == 8


def test_insert_fret_falls_back_to_override_when_no_chord_at_col() -> None:
    state = _state()
    chord = Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])
    state.piece.bars[0].chords = [chord]
    state.cursor_col = 1
    state.mode = "insert"
    _handle_insert(state, ord("a"))
    assert state.overrides[(0, 0, 1)] == "a"


def test_insert_flattens_chords_to_grid() -> None:
    state = _state()
    chord = Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])
    state.piece.bars[0].chords = [chord]
    state.mode = "insert"
    _handle_insert(state, ord("a"))
    assert state.piece.bars[0].chords == []
    assert state.overrides[(0, 0, 0)] == "a"


def test_insert_duration_does_not_advance_cursor() -> None:
    state = _state()
    state.mode = "insert"
    state.cursor_col = 0
    _handle_insert(state, ord("4"))
    assert state.cursor_col == 0


def test_insert_dot_toggles_dotted() -> None:
    state = _state()
    state.mode = "insert"
    state.cursor_col = 2
    _handle_insert(state, ord("."))
    assert (0, 2) in state.dotted


def test_redo_restores_override() -> None:
    state = _state()
    key = (0, 0, 0)
    _apply_override(state, key, "a")
    _undo(state)
    assert key not in state.overrides
    _redo(state)
    assert state.overrides[key] == "a"


def test_clear_cell_removes_duration_column() -> None:
    state = _state()
    state.durations[(0, 1, 0)] = 8
    _clear_cell(state, 0, 1, 0)
    assert (0, 1, 0) not in state.durations


def test_italian_fret_validation() -> None:
    assert is_italian_fret("0") is True
    assert is_italian_fret("9") is True
    assert is_italian_fret("x") is True
    assert is_italian_fret("a") is False


def test_insert_italian_digit_sets_fret_not_duration() -> None:
    state = _state()
    state.settings["style"] = "italian"
    state.mode = "insert"
    _handle_insert(state, ord("1"))
    assert (0, 0, 0) in state.overrides
    assert state.overrides[(0, 0, 0)] == "1"
    assert state.durations[(0, 0, 0)] == state.current_duration


def test_insert_italian_ctrl_duration_sets_duration() -> None:
    state = _state()
    state.settings["style"] = "italian"
    state.mode = "insert"
    _handle_insert(state, 4)
    assert state.durations[(0, 0, 0)] == 8
    assert (0, 0, 0) not in state.overrides


def test_insert_italian_semicolon_duration_sets_duration() -> None:
    state = _state()
    state.settings["style"] = "italian"
    state.mode = "insert"
    _handle_insert(state, ord(";"))
    _handle_insert(state, ord("4"))
    assert state.durations[(0, 0, 0)] == 8


def test_insert_french_digit_sets_duration() -> None:
    state = _state()
    state.settings["style"] = "french"
    state.mode = "insert"
    _handle_insert(state, ord("4"))
    assert (0, 0, 0) in state.durations
    assert state.durations[(0, 0, 0)] == 4


def test_insert_french_duration_keys() -> None:
    state = _state()
    state.settings["style"] = "french"
    state.mode = "insert"
    _handle_insert(state, ord("8"))
    assert state.durations[(0, 0, 0)] == 8
    state.cursor_col = 1
    _handle_insert(state, ord("6"))
    assert state.durations[(0, 0, 1)] == 16
    state.cursor_col = 2
    _handle_insert(state, ord("3"))
    assert state.durations[(0, 0, 2)] == 32


def test_insert_duration_then_note_uses_same_col() -> None:
    state = _state()
    state.settings["style"] = "french"
    state.mode = "insert"
    _handle_insert(state, ord("6"))
    assert state.cursor_col == 0
    _handle_insert(state, ord("a"))
    assert state.overrides[(0, 0, 0)] == "a"
    assert state.cursor_col == 1


def test_duration_persists_for_new_notes() -> None:
    state = _state()
    state.settings["style"] = "french"
    state.mode = "insert"
    _handle_insert(state, ord("8"))
    assert state.current_duration == 8
    _handle_insert(state, ord("a"))
    assert state.durations[(0, 0, 0)] == 8
    _handle_insert(state, ord("b"))
    assert state.durations[(0, 0, 1)] == 8


def test_invalid_key_does_not_set_duration() -> None:
    state = _state()
    state.settings["style"] = "french"
    state.mode = "insert"
    _handle_insert(state, ord("!"))
    assert state.durations == {}


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
    _set_barline(state, "thin")
    assert state.piece.bars[0].barline == "|"
    _set_repeat(state, "start")
    assert state.piece.bars[0].repeat == ".:"


def test_ornament_annotation_highlight() -> None:
    state = _state()
    _set_ornament(state, "x")
    _set_annotation(state, "note")
    _set_highlight(state, "on")
    assert state.ornaments[(0, 0)] == "x"
    assert state.annotations[(0, 0)] == "note"
    assert (0, 0, 0) in state.highlights


def test_slur_tie_hold_spans() -> None:
    state = _state()
    _set_slur(state, "start")
    state.cursor_col = 2
    _set_slur(state, "end")
    _set_tie(state, "start")
    state.cursor_col = 3
    _set_tie(state, "end")
    _set_hold(state, "start")
    state.cursor_col = 4
    _set_hold(state, "end")
    assert state.slurs == [(0, 0, 2)]
    assert state.ties == [(0, 2, 3)]
    assert state.holds == [(0, 3, 4)]


def test_normal_mode_counts_move() -> None:
    state = _state()
    _handle_key(state, ord("2"))
    _handle_key(state, ord("l"))
    assert state.cursor_col == 2


def test_normal_mode_x_clears_cell() -> None:
    state = _state()
    state.overrides[(0, 0, 0)] = "a"
    _handle_key(state, ord("x"))
    assert (0, 0, 0) not in state.overrides


def test_normal_mode_caret_moves_to_first_note() -> None:
    state = _state()
    state.cursor_col = 5
    state.overrides[(0, 0, 2)] = "a"
    state.overrides[(0, 0, 4)] = "b"
    _handle_key(state, ord("^"))
    assert state.cursor_col == 2


def test_insert_mode_space_clears_cell() -> None:
    state = _state()
    state.overrides[(0, 0, 0)] = "a"
    state.mode = "insert"
    _handle_insert(state, ord(" "))
    assert (0, 0, 0) not in state.overrides


def test_insert_mode_barline_sets_barline() -> None:
    state = _state()
    state.mode = "insert"
    _handle_insert(state, ord("|"))
    assert state.piece.bars[0].barline == "|"


def test_insert_mode_duration_does_not_advance() -> None:
    state = _state()
    state.mode = "insert"
    _handle_insert(state, ord("4"))
    assert state.cursor_col == 0


def test_insert_overflow_moves_to_next_bar() -> None:
    state = _state()
    state.mode = "insert"
    for col in range(4):
        state.durations[(0, 0, col)] = 4
        state.overrides[(0, 0, col)] = "a"
    state.cursor_col = 4
    _handle_insert(state, ord("b"))
    assert state.cursor_bar == 1
    assert (1, 0, 0) in state.overrides


def test_normal_mode_counts_move_right() -> None:
    state = _state()
    _handle_key(state, ord("3"))
    _handle_key(state, ord("l"))
    assert state.cursor_col == 3


def test_gj_adds_bass_string() -> None:
    state = _state()
    start_strings = state.piece.strings
    _handle_key(state, ord("g"))
    _handle_key(state, ord("j"))
    assert state.piece.strings == start_strings + 1
    assert state.cursor_string == state.piece.strings - 1
