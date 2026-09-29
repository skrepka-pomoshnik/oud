from fractions import Fraction

from oud.editor.core.coordinates import cursor_event
from oud.editor.core.input.modes import Mode
from oud.editor.core.state import EditorState
from oud.editor.interaction.dispatch import actions
from oud.editor.interaction.dispatch.controller import handle_key as dispatch_key
from petrucci.core.model import Bar, Chord, Note, Piece
from petrucci.rendering.api import render_piece
from petrucci.terminal.canvas.framebuffer import FrameBuffer
from tests.helpers_keyscript import tab_events

QUARTER = Fraction(1, 4)


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


def _bar(*notes: tuple[int, int] | list[tuple[int, int]], note_type: int = 4) -> Bar:
    """One event per argument; an argument is a (course, fret) note or a list of them."""

    chords = []
    for event in notes:
        pairs = event if isinstance(event, list) else [event]
        chords.append(Chord(note_type, False, None, [Note(course, fret, 0) for course, fret in pairs]))
    return Bar(chords=chords)


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


def _press(state: EditorState, *keys: int | str) -> None:
    for key in keys:
        dispatch_key(
            state,
            key if isinstance(key, int) else ord(key),
            handle_insert=actions.handle_insert,
            handle_normal=actions.handle_normal,
            handle_command=lambda _state, _key: True,
            handle_search=lambda _state, _key: True,
        )


def _four_quarters() -> Bar:
    return _bar((1, 0), (1, 1), (1, 2), (1, 3))


def test_normal_mode_counts_move() -> None:
    state = _state()
    state.piece.bars = [_four_quarters()]
    _press(state, "2", "l")
    assert state.cursor_onset == Fraction(1, 2)


def test_normal_find_forward_and_repeat() -> None:
    state = _state()
    state.piece.bars = [_bar((1, 1), (1, 0), (1, 1), (1, 0))]
    _press(state, "f", "a")
    assert state.cursor_onset == QUARTER
    _press(state, ";")
    assert state.cursor_onset == Fraction(3, 4)


def test_normal_find_backward_and_reverse_repeat() -> None:
    state = _state()
    state.piece.bars = [_bar((1, 1), (1, 0), (1, 1), (1, 0), (1, 1), (1, 0), (1, 0), (1, 1), note_type=5)]
    state.cursor_onset = Fraction(6, 8)
    _press(state, "F", "a")
    assert cursor_event(state) == 5
    _press(state, ",")
    assert cursor_event(state) == 6


def test_normal_word_search_and_repeat() -> None:
    state = _state()
    state.piece.bars = [_bar((1, 1), (1, 0), (1, 1), (1, 0)), _bar((1, 0))]
    state.cursor_onset = QUARTER
    _press(state, "*")
    assert (state.cursor_bar, state.cursor_onset) == (0, Fraction(3, 4))
    _press(state, "n")
    assert (state.cursor_bar, state.cursor_onset) == (1, Fraction(0))
    _press(state, "N")
    assert (state.cursor_bar, state.cursor_onset) == (0, Fraction(3, 4))


def test_normal_percent_jump_between_repeats() -> None:
    state = _state()
    state.piece.bars = [Bar(), Bar(), Bar()]
    state.piece.bars[0].repeat = ".:"
    state.piece.bars[2].repeat = ":."
    state.cursor_bar = 0
    _press(state, "%")
    assert state.cursor_bar == 2


def test_normal_marks_set_and_jump() -> None:
    state = _state()
    state.piece.bars = [_four_quarters(), _four_quarters()]
    state.cursor_onset = Fraction(1, 2)
    _press(state, "m", "a")
    assert state.marks["a"] == (0, 0, state.cursor_col)
    state.cursor_bar = 1
    state.cursor_onset = Fraction(0)
    _press(state, "'", "a")
    assert (state.cursor_bar, state.cursor_onset) == (0, Fraction(1, 2))


def test_normal_mode_x_clears_cell() -> None:
    state = _state()
    state.piece.bars = [_bar([(1, 0), (2, 1)])]
    _press(state, "x")
    assert tab_events(state) == [("4", [(2, 1)])]


def test_normal_mode_caret_moves_to_first_note() -> None:
    state = _state()
    state.piece.bars = [_bar((2, 0), (2, 1), (1, 0), (1, 1))]
    state.cursor_onset = Fraction(3, 4)
    _press(state, "^")
    assert state.cursor_onset == Fraction(1, 2)


def test_insert_mode_space_clears_cell() -> None:
    state = _state()
    state.piece.bars = [_bar([(1, 0), (2, 2)])]
    state.mode = Mode.INSERT
    actions.handle_insert(state, ord(" "))
    assert tab_events(state) == [("4", [(2, 2)])]


def test_insert_mode_barline_sets_barline() -> None:
    state = _state()
    state.mode = Mode.INSERT
    actions.handle_insert(state, ord("|"))
    assert state.piece.bars[0].barline == "|"


def test_insert_mode_duration_does_not_advance() -> None:
    state = _state()
    state.mode = Mode.INSERT
    actions.handle_insert(state, ord("4"))
    assert (state.cursor_bar, state.cursor_onset) == (0, Fraction(0))
    assert state.current_duration == 8


def test_insert_overflow_moves_to_next_bar() -> None:
    state = _state()
    state.mode = Mode.INSERT
    for ch in "abcdb":
        actions.handle_insert(state, ord(ch))
    assert state.cursor_bar == 1
    assert tab_events(state, 1) == [("4", [(1, 1)])]


def test_insert_mode_notes_insert_and_arrows_move() -> None:
    state = _state()
    state.mode = Mode.INSERT
    for ch in "abcdnf":
        actions.handle_insert(state, ord(ch))
    assert [notes for _duration, notes in tab_events(state, 0)] == [[(1, 0)], [(1, 1)], [(1, 2)], [(1, 3)]]
    assert [notes for _duration, notes in tab_events(state, 1)] == [[(1, 12)], [(1, 5)]]
    assert (state.cursor_bar, state.cursor_onset) == (1, Fraction(1, 2))
    actions.handle_insert(state, state.keycodes.left)
    assert state.cursor_onset == QUARTER
    actions.handle_insert(state, state.keycodes.right)
    assert state.cursor_onset == Fraction(1, 2)
    actions.handle_insert(state, state.keycodes.up)
    assert state.cursor_string == -1
    actions.handle_insert(state, state.keycodes.down)
    assert state.cursor_string == 0


def test_insert_mode_arrow_movement_clears_bass_slash_prefix() -> None:
    state = _state()
    state.mode = Mode.INSERT
    state.piece.strings = 8
    actions.handle_insert(state, ord("/"))
    assert state.insert_prefix == "/"
    actions.handle_insert(state, state.keycodes.right)
    assert state.insert_prefix == ""
    actions.handle_insert(state, ord("a"))
    assert tab_events(state, state.cursor_bar) == [("4", [(1, 0)])]


def test_insert_mode_arrow_movement_clears_italian_multifret_prefix() -> None:
    state = _state()
    state.mode = Mode.INSERT
    state.settings["style"] = "italian"
    state.settings["italianmultifret"] = "on"
    actions.handle_insert(state, ord(","))
    assert state.insert_prefix == ","
    actions.handle_insert(state, state.keycodes.left)
    assert state.insert_prefix == ""


def test_insert_mode_backspace_clears_note() -> None:
    state = _state()
    state.mode = Mode.INSERT
    actions.handle_insert(state, ord("a"))
    actions.handle_insert(state, ord("b"))
    state.cursor_onset = QUARTER
    actions.handle_insert(state, 127)
    assert tab_events(state) == [("4", [(1, 0)])]
    assert state.cursor_onset == Fraction(0)


def test_insert_mode_delete_removes_the_event_and_keeps_the_cursor() -> None:
    state = _state()
    state.mode = Mode.INSERT
    actions.handle_insert(state, ord("a"))
    actions.handle_insert(state, ord("b"))
    state.cursor_onset = Fraction(0)
    actions.handle_insert(state, state.keycodes.dc)
    assert tab_events(state) == [("4", [(1, 1)])]
    assert state.cursor_onset == Fraction(0)


def test_insert_duration_key_changes_the_event_on_every_course() -> None:
    state = _state()
    state.mode = Mode.INSERT
    actions.handle_insert(state, ord("4"))
    actions.handle_insert(state, ord("a"))
    state.cursor_string = 1
    state.cursor_onset = Fraction(0)
    actions.handle_insert(state, ord("5"))
    actions.handle_insert(state, ord("b"))
    assert tab_events(state) == [("16", [(1, 0), (2, 1)])]


def test_insert_after_row_full_advances_and_allows_next_bar() -> None:
    state = _state()
    state.mode = Mode.INSERT
    for ch in "abcd":
        actions.handle_insert(state, ord(ch))
    actions.handle_insert(state, state.keycodes.down)
    actions.handle_insert(state, ord("5"))
    actions.handle_insert(state, ord("a"))
    assert state.cursor_bar == 1
    assert tab_events(state, 1) == [("16", [(2, 0)])]


def test_insert_other_row_when_first_full_stays_in_bar() -> None:
    state = _state()
    state.mode = Mode.INSERT
    for ch in "abcd":
        actions.handle_insert(state, ord(ch))
    actions.handle_insert(state, state.keycodes.down)
    for _ in range(4):
        actions.handle_insert(state, state.keycodes.left)
    actions.handle_insert(state, ord("a"))
    assert state.cursor_bar == 0
    assert tab_events(state)[0] == ("4", [(1, 0), (2, 0)])


def test_normal_mode_counts_move_right() -> None:
    state = _state()
    state.piece.bars = [_four_quarters()]
    _press(state, "3", "l")
    assert state.cursor_onset == Fraction(3, 4)


def test_gb_adds_bass_string() -> None:
    state = _state()
    start_strings = state.piece.strings
    state.settings["bassstrings"] = "d2"
    _press(state, "g", "b")
    assert state.piece.strings == start_strings + 1
    assert state.cursor_string == state.piece.strings - 1


def test_gb_requires_bass_strings_setting() -> None:
    state = _state()
    state.settings["bassstrings"] = ""
    _press(state, "g", "b")
    assert state.message == "No bass strings configured"


def test_insert_bass_slash_shorthand() -> None:
    state = _state()
    state.settings["style"] = "french"
    state.piece.strings = 7
    state.mode = Mode.INSERT
    actions.handle_insert(state, ord("/"))
    actions.handle_insert(state, ord("a"))
    assert tab_events(state) == [("4", [(7, 0)])]


def _first_flag_row(lines: list[str], top_g_idx: int) -> str:
    for line in reversed(lines[:top_g_idx]):
        if any(f"{label}|" in line for label in ("g", "d", "a", "f", "c")):
            continue
        if any(ch in line for ch in ("|", "\\", "=")):
            return line
    return ""


def _flag_and_note_x(lines: list[str], top_g_idx: int) -> tuple[int, int]:
    top_g_row = lines[top_g_idx]
    note_x = top_g_row.find("a")
    assert note_x >= 0
    flag_row = _first_flag_row(lines, top_g_idx)
    assert flag_row
    glyph_positions = [i for i, ch in enumerate(flag_row) if ch in ("|", "\\", "=")]
    assert glyph_positions
    return glyph_positions[0], note_x


def _assert_time_cue_is_clear(lines: list[str], flag_row: str) -> None:
    time_rows = [line for line in lines if "|-C" in line or " C" in line]
    if not time_rows:
        return
    time_x = time_rows[0].find("C")
    if time_x >= 0:
        assert flag_row[time_x] == " "


def _typing_state(width: int) -> EditorState:
    state = _state()
    state.screen_width = width
    state.screen_height = 20
    state.settings.update(
        {
            "layout": "auto",
            "justify": "smart",
            "beatsnap": "soft",
            "showtuning": "off",
            "showdur": "off",
            "showspans": "off",
            "showfingerings": "off",
            "showornaments": "off",
            "linelen": "0",
            "barsperline": "0",
            "maxbars": "0",
            "barpad": "1",
            "flagredundant": "on",
        },
    )
    state.glisses = getattr(state, "glisses", [])
    return state


def test_keypress_insert_aaaa_keeps_first_flag_on_the_note_and_off_time_cue() -> None:
    state = _typing_state(28)
    _press(state, "i")
    for _ in range(4):
        _press(state, "a")
        lines = _render_lines(state, width=state.screen_width, height=state.screen_height)
        top_g_idx = next(i for i, line in enumerate(lines) if "g|" in line)
        flag_x, note_x = _flag_and_note_x(lines, top_g_idx)
        assert flag_x == note_x
        _assert_time_cue_is_clear(lines, _first_flag_row(lines, top_g_idx))


def test_keypress_insert_aaaa_then_l_moves_one_event_per_press() -> None:
    state = _typing_state(18)
    _press(state, "i", "a", "a", "a", "a", 27)
    state.cursor_bar, state.cursor_onset = 0, Fraction(0)
    stops = []
    for _ in range(5):
        _press(state, "l")
        stops.append((state.cursor_bar, state.cursor_onset))
    assert stops == [(0, QUARTER), (0, Fraction(1, 2)), (0, Fraction(3, 4)), (1, Fraction(0)), (2, Fraction(0))]
