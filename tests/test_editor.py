import pytest

from oud.editor.commands import dispatch as cmd_ops
from oud.editor.core.state import EditorState
from oud.editor.editing.primitives import edits as edit_ops
from oud.editor.editing.primitives import tablature as ops
from oud.editor.editing.primitives import undo as undo_ops
from oud.editor.interaction.dispatch import actions
from oud.editor.interaction.dispatch.controller import handle_key as dispatch_key
from petrucci.core.model import Bar, Chord, Note, Piece
from petrucci.rendering.api import render_piece
from petrucci.terminal.canvas.framebuffer import FrameBuffer


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
        mode=state.mode,
        cmdline=state.cmdline,
        message="",
        status_line="",
        searchline=state.searchline,
        settings=state.settings,
        ascii_lines=None,
        stave_breaks=state.stave_breaks,
        plugin_title=state.plugin_title,
        plugin_items=[],
        plugin_index=state.plugin_index,
        plugin_offset=state.plugin_offset,
        help_offset=state.help_offset,
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


def test_insert_french_duration_alias_letters_insert_frets() -> None:
    for ch in "ehst":
        state = _state()
        state.mode = "insert"
        actions.handle_insert(state, ord(ch))
        assert state.overrides[(0, 0, 0)] == ch
        assert state.current_duration == 4


def test_insert_q_quits_unmodified_buffer() -> None:
    state = _state()
    state.mode = "insert"
    assert _press(state, ord("q")) is False
    assert state.message != "Duration 4"
    assert state.current_duration == 4


def test_insert_fret_snaps_to_chord_slot_when_cursor_in_gap() -> None:
    state = _state()
    chord = Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])
    state.piece.bars[0].chords = [chord]
    state.cursor_col = 1
    state.mode = "insert"
    actions.handle_insert(state, ord("a"))
    assert state.overrides[(0, 0, 0)] == "a"
    assert (0, 0, 1) not in state.overrides


def test_insert_flattens_chords_to_grid() -> None:
    state = _state()
    chord = Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])
    state.piece.bars[0].chords = [chord]
    state.mode = "insert"
    actions.handle_insert(state, ord("a"))
    assert state.piece.bars[0].chords == []
    assert state.overrides[(0, 0, 0)] == "a"


def test_insert_note_records_single_grouped_undo() -> None:
    state = _state()
    state.mode = "insert"
    actions.handle_insert(state, ord("a"))
    assert len(state.undo_stack) == 1
    assert state.undo_stack[-1].kind == "group"
    undo_ops.undo(state, config_path="config.toml")
    assert state.overrides == {}
    assert state.durations == {}


def test_insert_flattened_chord_bar_undo_restores_structured_chords() -> None:
    state = _state()
    chord = Chord(note_type=4, dotted=True, grid=None, notes=[Note(1, 0, 0)])
    state.piece.bars[0].chords = [chord]
    state.piece.bars[0].notes = [Note(1, 0, 0)]
    state.mode = "insert"
    actions.handle_insert(state, ord("b"))
    assert state.piece.bars[0].chords == []
    assert state.overrides
    assert state.durations
    assert state.dotted

    undo_ops.undo(state, config_path="config.toml")

    assert state.piece.bars[0].chords == [chord]
    assert state.piece.bars[0].notes == [Note(1, 0, 0)]
    assert state.overrides == {}
    assert state.durations == {}
    assert state.dotted == set()


def test_insert_note_snaps_to_nearest_chord_slot_left_tie() -> None:
    state = _state()
    state.piece.bars[0].chords = [
        Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
        Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
    ]
    state.mode = "insert"
    state.cursor_col = 2
    actions.handle_insert(state, ord("b"))
    assert state.overrides[(0, 0, 0)] == "b"
    assert (0, 0, 2) not in state.durations


def test_insert_duration_snaps_to_existing_chord_slot() -> None:
    state = _state()
    state.piece.bars[0].chords = [
        Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
        Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
    ]
    state.mode = "insert"
    state.cursor_col = 2
    actions.handle_insert(state, ord("6"))
    assert state.durations[(0, 0, 0)] == 32
    assert (0, 0, 2) not in state.durations


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


def test_insert_italian_multifret_with_comma() -> None:
    state = _state()
    state.settings["style"] = "italian"
    state.settings["italianmultifret"] = "on"
    state.mode = "insert"
    actions.handle_insert(state, ord(","))
    actions.handle_insert(state, ord("1"))
    actions.handle_insert(state, ord("2"))
    assert state.overrides[(0, 0, 0)] == "1"
    assert state.overrides[(0, 0, 1)] == "2"


def test_insert_rest_sets_override_and_duration() -> None:
    state = _state()
    state.mode = "insert"
    actions.handle_insert(state, ord("r"))
    assert state.overrides[(0, 0, 0)] == "r"
    assert state.durations[(0, 0, 0)] == state.current_duration


def test_insert_rest_finishes_replace_once_mode() -> None:
    state = _state()
    state.mode = "insert"
    state.replace_once = True
    actions.handle_insert(state, ord("r"))
    assert state.mode == "normal"
    assert state.replace_once is False


def test_insert_rest_snaps_to_chord_slot_when_cursor_in_gap() -> None:
    state = _state()
    state.piece.bars[0].chords = [
        Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
        Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
    ]
    state.mode = "insert"
    state.cursor_col = 1
    actions.handle_insert(state, ord("r"))
    assert state.overrides[(0, 0, 0)] == "r"
    assert (0, 0, 1) not in state.overrides


@pytest.mark.parametrize(
    ("prefix_count", "expected_string_index"),
    [
        (1, 6),  # /a -> 7th course
        (2, 7),  # //a -> 8th course
        (3, 8),  # ///a -> 9th course
    ],
)
def test_insert_french_bass_slash_shorthand_targets_extra_courses(
    prefix_count: int,
    expected_string_index: int,
) -> None:
    state = _state()
    state.mode = "insert"
    state.piece.strings = 9
    state.settings["strings"] = "9"
    for _ in range(prefix_count):
        actions.handle_insert(state, ord("/"))
    actions.handle_insert(state, ord("a"))
    assert state.overrides[(0, expected_string_index, 0)] == "a"
    assert state.durations[(0, expected_string_index, 0)] == state.current_duration
    assert state.cursor_col == 1


def test_insert_french_bass_slash_shorthand_rejects_missing_course() -> None:
    state = _state()
    state.mode = "insert"
    state.piece.strings = 7
    state.settings["strings"] = "7"
    actions.handle_insert(state, ord("/"))
    actions.handle_insert(state, ord("/"))
    actions.handle_insert(state, ord("a"))
    assert "Bass string not available" in state.message
    assert not any(key[1] >= 6 for key in state.overrides)


def test_row_overflow_advances_to_next_bar() -> None:
    state = _state()
    state.mode = "insert"
    for _ in range(4):
        actions.handle_insert(state, ord("a"))
    state.cursor_string = 1
    actions.handle_insert(state, ord("a"))
    assert (0, 1, 4) in state.overrides


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


def test_insert_duration_on_other_string_snaps_to_same_time_slot() -> None:
    state = _state()
    state.settings["style"] = "french"
    state.mode = "insert"
    actions.handle_insert(state, ord("3"))
    actions.handle_insert(state, ord("a"))
    assert state.cursor_col == 1
    state.cursor_string = 5
    actions.handle_insert(state, ord("2"))
    # Duration change on another row should align to previous onset.
    assert state.cursor_col == 0
    actions.handle_insert(state, ord("b"))
    assert state.overrides[(0, 5, 0)] == "b"
    assert (0, 5, 1) not in state.overrides


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


def test_insert_note_uses_selected_duration_for_overflow_not_other_row_column_duration() -> None:
    state = _state()
    state.mode = "insert"
    state.bar_width = 40
    state.piece.bars.append(Bar())
    # Another row/same column stores a quarter duration.
    state.overrides[(0, 0, 0)] = "a"
    state.durations[(0, 0, 0)] = 4
    # Target row is nearly full with 32nds: 28 * 1/8 quarter-beats = 3.5
    for col in range(1, 29):
        state.overrides[(0, 1, col)] = "a"
        state.durations[(0, 1, col)] = 32
    state.cursor_string = 1
    state.cursor_col = 0
    state.current_duration = 32

    actions.handle_insert(state, ord("b"))

    # 32nd should fit in bar 0; old bug treated it as quarter from row 0 col 0 and advanced.
    assert state.cursor_bar == 0
    assert state.overrides[(0, 1, 0)] == "b"
    assert state.durations[(0, 1, 0)] == 32


def test_insert_note_on_existing_column_does_not_rewrite_duration() -> None:
    state = _state()
    state.mode = "insert"
    state.overrides[(0, 0, 0)] = "a"
    state.durations[(0, 0, 0)] = 4
    state.current_duration = 8
    state.cursor_col = 0
    state.cursor_string = 1

    actions.handle_insert(state, ord("b"))
    assert state.overrides[(0, 1, 0)] == "b"
    assert state.durations[(0, 0, 0)] == 4

    state.cursor_col = 0
    state.cursor_string = 1
    actions.handle_insert(state, ord(" "))
    assert (0, 1, 0) not in state.overrides
    assert state.overrides[(0, 0, 0)] == "a"
    assert state.durations[(0, 0, 0)] == 4


def test_repeated_add_remove_undo_keeps_column_duration_stable() -> None:
    state = _state()
    state.mode = "insert"
    state.overrides[(0, 0, 0)] = "a"
    state.durations[(0, 0, 0)] = 4

    for _ in range(6):
        state.current_duration = 8
        state.cursor_col = 0
        state.cursor_string = 1
        actions.handle_insert(state, ord("b"))
        assert state.durations[(0, 0, 0)] == 4
        assert state.overrides[(0, 1, 0)] == "b"

        state.cursor_col = 0
        state.cursor_string = 1
        actions.handle_insert(state, ord(" "))
        assert (0, 1, 0) not in state.overrides
        assert state.durations[(0, 0, 0)] == 4

        undo_ops.undo(state, config_path="config.toml")
        assert state.overrides[(0, 1, 0)] == "b"
        assert state.durations[(0, 0, 0)] == 4

        undo_ops.undo(state, config_path="config.toml")
        if (0, 1, 0) in state.overrides:
            # With per-cell duration recording, insertion can be two undo steps
            # (duration + override) instead of one.
            undo_ops.undo(state, config_path="config.toml")
        assert (0, 1, 0) not in state.overrides
        assert state.durations[(0, 0, 0)] == 4


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
