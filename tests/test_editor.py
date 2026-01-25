from core.model import Bar, Chord, Note, Piece
from editor import actions, edit_ops, ops, undo_ops
from editor import command_ops as cmd_ops
from editor.controller import handle_key as dispatch_key
from editor.state import EditorState


def _state() -> EditorState:
    piece = Piece(title="T", bars=[Bar()])
    settings = {
        "style": "french",
        "measures": "start",
        "tuning": "g2c3f3a3d4g4",
        "bassstrings": "d2",
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
    edit_ops.apply_override(state, key, "a")
    assert state.overrides[key] == "a"
    undo_ops.undo(state, config_path="config.toml")
    assert key not in state.overrides


def test_undo_duration_restores_previous() -> None:
    state = _state()
    key = (0, 0, 0)
    edit_ops.apply_duration(state, key, 4)
    edit_ops.apply_duration(state, key, 8)
    undo_ops.undo(state, config_path="config.toml")
    assert state.durations[key] == 4


def test_insert_duration_updates_chord_note_type() -> None:
    state = _state()
    chord = Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])
    state.piece.bars[0].chords = [chord]
    state.mode = "insert"
    actions.handle_insert(state, ord("4"))
    assert state.piece.bars[0].chords == []
    assert state.durations[(0, 0, 0)] == 8


def test_insert_duration_digits_map_in_french() -> None:
    state = _state()
    state.mode = "insert"
    actions.handle_insert(state, ord("1"))
    assert state.current_duration == 1
    actions.handle_insert(state, ord("2"))
    assert state.current_duration == 2
    actions.handle_insert(state, ord("3"))
    assert state.current_duration == 4
    actions.handle_insert(state, ord("4"))
    assert state.current_duration == 8
    actions.handle_insert(state, ord("5"))
    assert state.current_duration == 16
    actions.handle_insert(state, ord("6"))
    assert state.current_duration == 32
    actions.handle_insert(state, ord("7"))
    assert state.current_duration == 64


def test_insert_fret_falls_back_to_override_when_no_chord_at_col() -> None:
    state = _state()
    chord = Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])
    state.piece.bars[0].chords = [chord]
    state.cursor_col = 1
    state.mode = "insert"
    actions.handle_insert(state, ord("a"))
    assert state.overrides[(0, 0, 1)] == "a"


def test_insert_flattens_chords_to_grid() -> None:
    state = _state()
    chord = Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])
    state.piece.bars[0].chords = [chord]
    state.mode = "insert"
    actions.handle_insert(state, ord("a"))
    assert state.piece.bars[0].chords == []
    assert state.overrides[(0, 0, 0)] == "a"


def test_confirm_quit_when_modified() -> None:
    state = _state()
    state.modified = True
    assert dispatch_key(
        state,
        ord("q"),
        handle_insert=actions.handle_insert,
        handle_normal=actions.handle_normal,
        handle_command=lambda _state, _key: True,
        handle_search=lambda _state, _key: True,
    )
    assert state.pending_quit is True
    assert (
        dispatch_key(
            state,
            ord("q"),
                handle_insert=actions.handle_insert,
            handle_normal=actions.handle_normal,
            handle_command=lambda _state, _key: True,
            handle_search=lambda _state, _key: True,
        )
        is False
    )


def test_insert_duration_does_not_advance_cursor() -> None:
    state = _state()
    state.mode = "insert"
    state.cursor_col = 0
    actions.handle_insert(state, ord("4"))
    assert state.cursor_col == 0


def test_insert_dot_toggles_dotted() -> None:
    state = _state()
    state.mode = "insert"
    state.cursor_col = 2
    actions.handle_insert(state, ord("."))
    assert (0, 2) in state.dotted


def test_redo_restores_override() -> None:
    state = _state()
    key = (0, 0, 0)
    edit_ops.apply_override(state, key, "a")
    undo_ops.undo(state, config_path="config.toml")
    assert key not in state.overrides
    undo_ops.redo(state, config_path="config.toml")
    assert state.overrides[key] == "a"


def test_clear_cell_removes_duration_column() -> None:
    state = _state()
    state.durations[(0, 1, 0)] = 8
    edit_ops.clear_cell(state, 0, 1, 0)
    assert (0, 1, 0) not in state.durations


def test_italian_fret_validation() -> None:
    assert ops.is_italian_fret("0") is True
    assert ops.is_italian_fret("9") is True
    assert ops.is_italian_fret("x") is True
    assert ops.is_italian_fret("a") is False


def test_insert_italian_digit_sets_fret_not_duration() -> None:
    state = _state()
    state.settings["style"] = "italian"
    state.mode = "insert"
    actions.handle_insert(state, ord("1"))
    assert (0, 0, 0) in state.overrides
    assert state.overrides[(0, 0, 0)] == "1"
    assert state.durations[(0, 0, 0)] == state.current_duration


def test_insert_italian_ctrl_duration_sets_duration() -> None:
    state = _state()
    state.settings["style"] = "italian"
    state.mode = "insert"
    actions.handle_insert(state, 4)
    assert state.durations[(0, 0, 0)] == 8
    assert (0, 0, 0) not in state.overrides


def test_insert_italian_semicolon_duration_sets_duration() -> None:
    state = _state()
    state.settings["style"] = "italian"
    state.mode = "insert"
    actions.handle_insert(state, ord(";"))
    actions.handle_insert(state, ord("4"))
    assert state.durations[(0, 0, 0)] == 8


def test_insert_rest_sets_override_and_duration() -> None:
    state = _state()
    state.mode = "insert"
    actions.handle_insert(state, ord("r"))
    assert state.overrides[(0, 0, 0)] == "r"
    assert state.durations[(0, 0, 0)] == state.current_duration


def test_row_overflow_advances_to_next_bar() -> None:
    state = _state()
    state.mode = "insert"
    for _ in range(4):
        actions.handle_insert(state, ord("a"))
    state.cursor_string = 1
    actions.handle_insert(state, ord("a"))
    assert (0, 1, 0) not in state.overrides
    assert (1, 1, 0) in state.overrides


def test_insert_french_digit_sets_duration() -> None:
    state = _state()
    state.settings["style"] = "french"
    state.mode = "insert"
    actions.handle_insert(state, ord("3"))
    assert (0, 0, 0) in state.durations
    assert state.durations[(0, 0, 0)] == 4


def test_insert_french_duration_keys() -> None:
    state = _state()
    state.settings["style"] = "french"
    state.mode = "insert"
    actions.handle_insert(state, ord("4"))
    assert state.durations[(0, 0, 0)] == 8
    state.cursor_col = 1
    actions.handle_insert(state, ord("5"))
    assert state.durations[(0, 0, 1)] == 16
    state.cursor_col = 2
    actions.handle_insert(state, ord("6"))
    assert state.durations[(0, 0, 2)] == 32


def test_insert_duration_then_note_uses_same_col() -> None:
    state = _state()
    state.settings["style"] = "french"
    state.mode = "insert"
    actions.handle_insert(state, ord("6"))
    assert state.cursor_col == 0
    actions.handle_insert(state, ord("a"))
    assert state.overrides[(0, 0, 0)] == "a"
    assert state.cursor_col == 1


def test_duration_persists_for_new_notes() -> None:
    state = _state()
    state.settings["style"] = "french"
    state.mode = "insert"
    actions.handle_insert(state, ord("4"))
    assert state.current_duration == 8
    actions.handle_insert(state, ord("a"))
    assert state.durations[(0, 0, 0)] == 8
    actions.handle_insert(state, ord("b"))
    assert state.durations[(0, 0, 1)] == 8


def test_invalid_key_does_not_set_duration() -> None:
    state = _state()
    state.settings["style"] = "french"
    state.mode = "insert"
    actions.handle_insert(state, ord("!"))
    assert state.durations == {}


def test_grid_mode_advances_two_cells() -> None:
    state = _state()
    state.settings["grid"] = "on"
    state.mode = "insert"
    actions.handle_insert(state, ord("a"))
    assert state.cursor_col == 2


def test_convert_overrides_french_to_italian() -> None:
    state = _state()
    state.overrides[(0, 0, 0)] = "a"
    state.overrides[(0, 0, 1)] = "k"
    cmd_ops.convert_overrides(state, "italian")
    assert state.overrides[(0, 0, 0)] == "0"
    assert state.overrides[(0, 0, 1)] == "x"


def test_convert_overrides_italian_to_french() -> None:
    state = _state()
    state.overrides[(0, 0, 0)] = "0"
    state.overrides[(0, 0, 1)] = "x"
    cmd_ops.convert_overrides(state, "french")
    assert state.overrides[(0, 0, 0)] == "a"
    assert state.overrides[(0, 0, 1)] == "k"


def test_set_barline_and_repeat() -> None:
    state = _state()
    cmd_ops.set_barline(state, "thin")
    assert state.piece.bars[0].barline == "|"
    cmd_ops.set_repeat(state, "start")
    assert state.piece.bars[0].repeat == ".:"


def test_ornament_annotation_highlight() -> None:
    state = _state()
    cmd_ops.set_ornament(state, "x")
    cmd_ops.set_annotation(state, "note")
    cmd_ops.set_highlight(state, "on")
    assert state.ornaments[(0, 0)] == "x"
    assert state.annotations[(0, 0)] == "note"
    assert (0, 0, 0) in state.highlights


def test_slur_tie_hold_spans() -> None:
    state = _state()
    cmd_ops.set_slur(state, "start")
    state.cursor_col = 2
    cmd_ops.set_slur(state, "end")
    cmd_ops.set_tie(state, "start")
    state.cursor_col = 3
    cmd_ops.set_tie(state, "end")
    cmd_ops.set_hold(state, "start")
    state.cursor_col = 4
    cmd_ops.set_hold(state, "end")
    assert state.slurs == [(0, 0, 2)]
    assert state.ties == [(0, 2, 3)]
    assert state.holds == [(0, 3, 4)]


def test_normal_mode_counts_move() -> None:
    state = _state()
    dispatch_key(
        state,
        ord("2"),
        handle_insert=actions.handle_insert,
        handle_normal=actions.handle_normal,
        handle_command=lambda _state, _key: True,
        handle_search=lambda _state, _key: True,
    )
    dispatch_key(
        state,
        ord("l"),
        handle_insert=actions.handle_insert,
        handle_normal=actions.handle_normal,
        handle_command=lambda _state, _key: True,
        handle_search=lambda _state, _key: True,
    )
    assert state.cursor_col == 2


def test_normal_mode_x_clears_cell() -> None:
    state = _state()
    state.overrides[(0, 0, 0)] = "a"
    dispatch_key(
        state,
        ord("x"),
        handle_insert=actions.handle_insert,
        handle_normal=actions.handle_normal,
        handle_command=lambda _state, _key: True,
        handle_search=lambda _state, _key: True,
    )
    assert (0, 0, 0) not in state.overrides


def test_normal_mode_caret_moves_to_first_note() -> None:
    state = _state()
    state.cursor_col = 5
    state.overrides[(0, 0, 2)] = "a"
    state.overrides[(0, 0, 4)] = "b"
    dispatch_key(
        state,
        ord("^"),
        handle_insert=actions.handle_insert,
        handle_normal=actions.handle_normal,
        handle_command=lambda _state, _key: True,
        handle_search=lambda _state, _key: True,
    )
    assert state.cursor_col == 2


def test_insert_mode_space_clears_cell() -> None:
    state = _state()
    state.overrides[(0, 0, 0)] = "a"
    state.mode = "insert"
    actions.handle_insert(state, ord(" "))
    assert (0, 0, 0) not in state.overrides


def test_insert_mode_barline_sets_barline() -> None:
    state = _state()
    state.mode = "insert"
    actions.handle_insert(state, ord("|"))
    assert state.piece.bars[0].barline == "|"


def test_insert_mode_duration_does_not_advance() -> None:
    state = _state()
    state.mode = "insert"
    actions.handle_insert(state, ord("4"))
    assert state.cursor_col == 0


def test_insert_overflow_moves_to_next_bar() -> None:
    state = _state()
    state.mode = "insert"
    for col in range(4):
        state.durations[(0, 0, col)] = 4
        state.overrides[(0, 0, col)] = "a"
    state.cursor_col = 4
    actions.handle_insert(state, ord("b"))
    assert state.cursor_bar == 1
    assert (1, 0, 0) in state.overrides


def test_normal_mode_counts_move_right() -> None:
    state = _state()
    dispatch_key(
        state,
        ord("3"),
        handle_insert=actions.handle_insert,
        handle_normal=actions.handle_normal,
        handle_command=lambda _state, _key: True,
        handle_search=lambda _state, _key: True,
    )
    dispatch_key(
        state,
        ord("l"),
        handle_insert=actions.handle_insert,
        handle_normal=actions.handle_normal,
        handle_command=lambda _state, _key: True,
        handle_search=lambda _state, _key: True,
    )
    assert state.cursor_col == 3


def test_gj_adds_bass_string() -> None:
    state = _state()
    start_strings = state.piece.strings
    dispatch_key(
        state,
        ord("g"),
        handle_insert=actions.handle_insert,
        handle_normal=actions.handle_normal,
        handle_command=lambda _state, _key: True,
        handle_search=lambda _state, _key: True,
    )
    dispatch_key(
        state,
        ord("j"),
        handle_insert=actions.handle_insert,
        handle_normal=actions.handle_normal,
        handle_command=lambda _state, _key: True,
        handle_search=lambda _state, _key: True,
    )
    assert state.piece.strings == start_strings + 1
    assert state.cursor_string == state.piece.strings - 1
