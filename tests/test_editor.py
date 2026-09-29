import copy
from fractions import Fraction

import pytest

from oud.editor.commands import dispatch as cmd_ops
from oud.editor.core.input.modes import Mode
from oud.editor.core.state import EditorState
from oud.editor.editing.primitives import edits as edit_ops
from oud.editor.editing.primitives import tablature as ops
from oud.editor.editing.primitives import undo as undo_ops
from oud.editor.interaction.dispatch import actions
from oud.editor.interaction.dispatch.controller import handle_key as dispatch_key
from petrucci.core.model import Bar, Chord, Note, Piece
from petrucci.rendering.api import render_piece
from petrucci.terminal.canvas.framebuffer import FrameBuffer
from tests.helpers_keyscript import tab_events


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
        "layout": "packed",
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


def _render_lines(state: EditorState, *, width: int = 80, height: int = 24) -> list[str]:
    fb = FrameBuffer(height, width)
    render_piece(
        fb,
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
        settings=state.settings,
        stave_breaks=state.stave_breaks,
        playback_bar=state.playback_bar,
        playback_col=state.playback_col,
        glisses=getattr(state, "glisses", []),
    )
    return fb.snapshot().lines


def _press(state: EditorState, key: int) -> bool:
    return dispatch_key(
        state,
        key,
        handle_insert=actions.handle_insert,
        handle_normal=actions.handle_normal,
        handle_command=lambda _state, _key: True,
        handle_search=lambda _state, _key: True,
    )


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
    state.mode = Mode.INSERT
    actions.handle_insert(state, ord("4"))
    assert tab_events(state) == [("8", [(1, 0)])]


def test_insert_duration_digits_map_in_french() -> None:
    state = _state()
    state.mode = Mode.INSERT
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


def test_insert_french_duration_alias_letters_insert_frets() -> None:
    for ch, fret in zip("ehst", (4, 7, 17, 18), strict=True):
        state = _state()
        state.mode = Mode.INSERT
        actions.handle_insert(state, ord(ch))
        assert tab_events(state) == [("4", [(1, fret)])]
        assert state.current_duration == 4


def test_insert_fret_on_an_event_sets_that_course_and_advances() -> None:
    state = _state()
    state.piece.bars[0].chords = [Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 0, 0)])]
    state.mode = Mode.INSERT
    actions.handle_insert(state, ord("a"))
    assert tab_events(state) == [("4", [(2, 0), (1, 0)])]
    assert state.cursor_onset == Fraction(1, 4)


def test_insert_keeps_imported_chords() -> None:
    state = _state()
    chord = Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])
    state.piece.bars[0].chords = [chord]
    state.mode = Mode.INSERT
    actions.handle_insert(state, ord("b"))
    assert tab_events(state) == [("4", [(1, 1)])]
    assert state.overrides == {}


def test_insert_note_records_single_grouped_undo() -> None:
    state = _state()
    state.mode = Mode.INSERT
    actions.handle_insert(state, ord("a"))
    assert len(state.undo_stack) == 1
    assert state.undo_stack[-1].kind == "group"
    undo_ops.undo(state, config_path="config.toml")
    assert tab_events(state) == []


def test_insert_into_imported_chord_undo_restores_the_chords() -> None:
    state = _state()
    chord = Chord(note_type=4, dotted=True, grid=None, notes=[Note(1, 0, 0)])
    state.piece.bars[0].chords = [copy.deepcopy(chord)]
    state.piece.bars[0].notes = [Note(1, 0, 0)]
    state.mode = Mode.INSERT
    actions.handle_insert(state, ord("b"))
    assert tab_events(state) == [("4.", [(1, 1)])]
    assert state.piece.bars[0].notes == [Note(1, 1, 0)]

    undo_ops.undo(state, config_path="config.toml")

    assert state.piece.bars[0].chords == [chord]
    assert state.piece.bars[0].notes == [Note(1, 0, 0)]
    assert state.overrides == {}


def test_insert_duration_on_the_append_slot_changes_the_last_event() -> None:
    state = _state()
    state.piece.bars[0].chords = [
        Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
        Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
    ]
    state.mode = Mode.INSERT
    state.cursor_onset = Fraction(1, 2)
    actions.handle_insert(state, ord("6"))
    assert tab_events(state) == [("4", [(1, 0)]), ("32", [(1, 2)])]
    assert state.cursor_onset == Fraction(9, 32)


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
    state.mode = Mode.INSERT
    actions.handle_insert(state, ord("4"))
    assert state.cursor_onset == Fraction(0)


def test_insert_dot_toggles_dotted() -> None:
    state = _state()
    state.mode = Mode.INSERT
    actions.handle_insert(state, ord("."))
    assert state.message == "No event here"
    actions.handle_insert(state, ord("a"))
    actions.handle_insert(state, ord("."))
    assert tab_events(state) == [("4.", [(1, 0)])]
    actions.handle_insert(state, ord("."))
    assert tab_events(state) == [("4", [(1, 0)])]


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


def test_clear_cell_empty_gap_does_not_delete_nearest_chord_note() -> None:
    state = _state()
    state.piece.bars[0].chords = [
        Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
    ]
    edit_ops.clear_cell(state, 0, 0, 1)
    assert state.piece.bars[0].chords[0].notes == [Note(1, 0, 0)]
    assert state.undo_stack == []


def test_clear_cell_note_records_single_grouped_undo() -> None:
    state = _state()
    state.overrides[(0, 0, 0)] = "a"
    state.durations[(0, 0, 0)] = 4
    state.dotted.add((0, 0))
    edit_ops.clear_cell_note(state, 0, 0, 0)
    assert (0, 0, 0) not in state.overrides
    assert (0, 0, 0) not in state.durations
    assert (0, 0) not in state.dotted
    assert len(state.undo_stack) == 1
    assert state.undo_stack[-1].kind == "group"
    undo_ops.undo(state, config_path="config.toml")
    assert state.overrides[(0, 0, 0)] == "a"
    assert state.durations[(0, 0, 0)] == 4
    assert (0, 0) in state.dotted


def test_italian_fret_validation() -> None:
    assert ops.is_italian_fret("0") is True
    assert ops.is_italian_fret("9") is True
    assert ops.is_italian_fret("x") is True
    assert ops.is_italian_fret("a") is False


def test_insert_italian_digit_sets_fret_not_duration() -> None:
    state = _state()
    state.settings["style"] = "italian"
    state.mode = Mode.INSERT
    actions.handle_insert(state, ord("1"))
    assert tab_events(state) == [(str(state.current_duration), [(1, 1)])]


def test_insert_italian_semicolon_duration_sets_duration() -> None:
    state = _state()
    state.settings["style"] = "italian"
    state.mode = Mode.INSERT
    actions.handle_insert(state, ord(";"))
    actions.handle_insert(state, ord("4"))
    assert state.current_duration == 8
    assert tab_events(state) == []


def test_insert_italian_multifret_with_comma() -> None:
    state = _state()
    state.settings["style"] = "italian"
    state.settings["italianmultifret"] = "on"
    state.mode = Mode.INSERT
    actions.handle_insert(state, ord(","))
    actions.handle_insert(state, ord("1"))
    actions.handle_insert(state, ord("2"))
    assert tab_events(state) == [("4", [(1, 12)])]


def test_insert_rest_appends_a_rest_with_the_current_duration() -> None:
    state = _state()
    state.mode = Mode.INSERT
    actions.handle_insert(state, ord("z"))
    assert tab_events(state) == [(str(state.current_duration), [])]


def test_insert_rest_finishes_replace_once_mode() -> None:
    state = _state()
    state.mode = Mode.INSERT
    state.replace_once = True
    actions.handle_insert(state, ord("z"))
    assert state.mode == "normal"
    assert state.replace_once is False


@pytest.mark.parametrize(
    ("prefix_count", "expected_course"),
    [
        (1, 7),  # /a -> 7th course
        (2, 8),  # //a -> 8th course
        (3, 9),  # ///a -> 9th course
    ],
)
def test_insert_french_bass_slash_shorthand_targets_extra_courses(
    prefix_count: int,
    expected_course: int,
) -> None:
    state = _state()
    state.mode = Mode.INSERT
    state.piece.strings = 9
    state.settings["strings"] = "9"
    for _ in range(prefix_count):
        actions.handle_insert(state, ord("/"))
    actions.handle_insert(state, ord("a"))
    assert tab_events(state) == [(str(state.current_duration), [(expected_course, 0)])]
    assert state.cursor_onset == Fraction(1, 4)


def test_insert_french_bass_slash_shorthand_rejects_missing_course() -> None:
    state = _state()
    state.mode = Mode.INSERT
    state.piece.strings = 7
    state.settings["strings"] = "7"
    actions.handle_insert(state, ord("/"))
    actions.handle_insert(state, ord("/"))
    actions.handle_insert(state, ord("a"))
    assert "Bass string not available" in state.message
    assert tab_events(state) == []


def test_row_overflow_advances_to_next_bar() -> None:
    state = _state()
    state.mode = Mode.INSERT
    for _ in range(4):
        actions.handle_insert(state, ord("a"))
    state.cursor_string = 1
    actions.handle_insert(state, ord("a"))
    assert tab_events(state, 1) == [("4", [(2, 0)])]


def test_insert_french_digit_sets_duration() -> None:
    state = _state()
    state.settings["style"] = "french"
    state.mode = Mode.INSERT
    actions.handle_insert(state, ord("3"))
    assert state.current_duration == 4
    assert tab_events(state) == []


def test_insert_french_duration_keys() -> None:
    state = _state()
    state.settings["style"] = "french"
    state.mode = Mode.INSERT
    actions.handle_insert(state, ord("a"))
    for key, expected in (("4", "8"), ("5", "16"), ("6", "32")):
        actions.handle_insert(state, ord(key))
        assert tab_events(state) == [(expected, [(1, 0)])]


def test_insert_duration_then_note_uses_the_new_duration() -> None:
    state = _state()
    state.settings["style"] = "french"
    state.mode = Mode.INSERT
    actions.handle_insert(state, ord("6"))
    assert state.cursor_onset == Fraction(0)
    actions.handle_insert(state, ord("a"))
    assert tab_events(state) == [("32", [(1, 0)])]
    assert state.cursor_onset == Fraction(1, 32)


def test_insert_duration_on_other_string_changes_the_typed_note_and_appends_after_it() -> None:
    state = _state()
    state.settings["style"] = "french"
    state.mode = Mode.INSERT
    actions.handle_insert(state, ord("3"))
    actions.handle_insert(state, ord("a"))
    state.cursor_string = 5
    actions.handle_insert(state, ord("2"))
    assert state.cursor_onset == Fraction(1, 2)
    actions.handle_insert(state, ord("b"))
    assert tab_events(state) == [("2", [(1, 0)]), ("2", [(6, 1)])]


def test_duration_persists_for_new_notes() -> None:
    state = _state()
    state.settings["style"] = "french"
    state.mode = Mode.INSERT
    actions.handle_insert(state, ord("4"))
    assert state.current_duration == 8
    actions.handle_insert(state, ord("a"))
    actions.handle_insert(state, ord("b"))
    assert tab_events(state) == [("8", [(1, 0)]), ("8", [(1, 1)])]


def test_insert_note_fits_when_the_bar_has_room_for_its_duration() -> None:
    state = _state()
    state.mode = Mode.INSERT
    state.piece.bars[0].chords = [Chord(7, False, None, [Note(1, 0, 0)]) for _ in range(31)]
    state.cursor_onset = Fraction(31, 32)
    state.current_duration = 32
    state.cursor_string = 1

    actions.handle_insert(state, ord("b"))

    assert tab_events(state)[-1] == ("32", [(2, 1)])
    assert len(state.piece.bars) == 2


def test_insert_note_on_existing_event_does_not_rewrite_duration() -> None:
    state = _state()
    state.mode = Mode.INSERT
    state.piece.bars[0].chords = [Chord(4, False, None, [Note(1, 0, 0)])]
    state.current_duration = 8
    state.cursor_string = 1

    actions.handle_insert(state, ord("b"))
    assert tab_events(state) == [("4", [(1, 0), (2, 1)])]

    state.cursor_onset = Fraction(0)
    state.cursor_string = 1
    actions.handle_insert(state, ord(" "))
    assert tab_events(state) == [("4", [(1, 0)])]


def test_repeated_add_remove_undo_keeps_the_event_duration_stable() -> None:
    state = _state()
    state.mode = Mode.INSERT
    state.piece.bars[0].chords = [Chord(4, False, None, [Note(1, 0, 0)])]

    for _ in range(6):
        state.current_duration = 8
        state.cursor_onset = Fraction(0)
        state.cursor_string = 1
        actions.handle_insert(state, ord("b"))
        assert tab_events(state) == [("4", [(1, 0), (2, 1)])]

        state.cursor_onset = Fraction(0)
        actions.handle_insert(state, ord(" "))
        assert tab_events(state) == [("4", [(1, 0)])]

        undo_ops.undo(state, config_path="config.toml")
        assert tab_events(state) == [("4", [(1, 0), (2, 1)])]
        undo_ops.undo(state, config_path="config.toml")
        assert tab_events(state) == [("4", [(1, 0)])]


def test_invalid_key_does_not_set_duration() -> None:
    state = _state()
    state.settings["style"] = "french"
    state.mode = Mode.INSERT
    actions.handle_insert(state, ord("!"))
    assert tab_events(state) == []


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
    state.piece.bars[0].chords = [Chord(5, False, None, [Note(1, 0, 0)]) for _ in range(8)]

    def at(eighth: int) -> int:
        state.cursor_onset = Fraction(eighth, 8)
        return state.cursor_col

    columns = [at(0), at(2), at(3), at(4)]
    state.cursor_onset = Fraction(0)
    cmd_ops.set_slur(state, "start")
    at(2)
    cmd_ops.set_slur(state, "end")
    cmd_ops.set_tie(state, "start")
    at(3)
    cmd_ops.set_tie(state, "end")
    cmd_ops.set_hold(state, "start")
    at(4)
    cmd_ops.set_hold(state, "end")
    assert state.slurs == [(0, columns[0], columns[1])]
    assert state.ties == [(0, columns[1], columns[2])]
    assert state.holds == [(0, columns[2], columns[3])]
