from oud.editor.core.input.modes import Mode
from oud.editor.core.state import EditorState
from oud.editor.interaction.dispatch import actions
from oud.editor.interaction.dispatch.controller import handle_key as dispatch_key
from petrucci.core.model import Bar, Piece
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


def test_normal_find_forward_and_repeat() -> None:
    state = _state()
    state.overrides[(0, 0, 1)] = "a"
    state.overrides[(0, 0, 3)] = "a"
    dispatch_key(
        state,
        ord("f"),
        handle_insert=actions.handle_insert,
        handle_normal=actions.handle_normal,
        handle_command=lambda _state, _key: True,
        handle_search=lambda _state, _key: True,
    )
    dispatch_key(
        state,
        ord("a"),
        handle_insert=actions.handle_insert,
        handle_normal=actions.handle_normal,
        handle_command=lambda _state, _key: True,
        handle_search=lambda _state, _key: True,
    )
    assert state.cursor_col == 1
    dispatch_key(
        state,
        ord(";"),
        handle_insert=actions.handle_insert,
        handle_normal=actions.handle_normal,
        handle_command=lambda _state, _key: True,
        handle_search=lambda _state, _key: True,
    )
    assert state.cursor_col == 3


def test_normal_find_backward_and_reverse_repeat() -> None:
    state = _state()
    state.cursor_col = 6
    state.overrides[(0, 0, 1)] = "a"
    state.overrides[(0, 0, 3)] = "a"
    state.overrides[(0, 0, 5)] = "a"
    state.overrides[(0, 0, 6)] = "a"
    dispatch_key(
        state,
        ord("F"),
        handle_insert=actions.handle_insert,
        handle_normal=actions.handle_normal,
        handle_command=lambda _state, _key: True,
        handle_search=lambda _state, _key: True,
    )
    dispatch_key(
        state,
        ord("a"),
        handle_insert=actions.handle_insert,
        handle_normal=actions.handle_normal,
        handle_command=lambda _state, _key: True,
        handle_search=lambda _state, _key: True,
    )
    assert state.cursor_col == 5
    dispatch_key(
        state,
        ord(","),
        handle_insert=actions.handle_insert,
        handle_normal=actions.handle_normal,
        handle_command=lambda _state, _key: True,
        handle_search=lambda _state, _key: True,
    )
    assert state.cursor_col == 6


def test_normal_word_search_and_repeat() -> None:
    state = _state()
    state.piece.bars.append(Bar())
    state.overrides[(0, 0, 1)] = "a"
    state.overrides[(0, 0, 3)] = "a"
    state.overrides[(1, 0, 0)] = "a"
    state.cursor_bar = 0
    state.cursor_col = 1
    dispatch_key(
        state,
        ord("*"),
        handle_insert=actions.handle_insert,
        handle_normal=actions.handle_normal,
        handle_command=lambda _state, _key: True,
        handle_search=lambda _state, _key: True,
    )
    assert (state.cursor_bar, state.cursor_col) == (0, 3)
    dispatch_key(
        state,
        ord("n"),
        handle_insert=actions.handle_insert,
        handle_normal=actions.handle_normal,
        handle_command=lambda _state, _key: True,
        handle_search=lambda _state, _key: True,
    )
    assert (state.cursor_bar, state.cursor_col) == (1, 0)
    dispatch_key(
        state,
        ord("N"),
        handle_insert=actions.handle_insert,
        handle_normal=actions.handle_normal,
        handle_command=lambda _state, _key: True,
        handle_search=lambda _state, _key: True,
    )
    assert (state.cursor_bar, state.cursor_col) == (0, 3)


def test_normal_percent_jump_between_repeats() -> None:
    state = _state()
    state.piece.bars = [Bar(), Bar(), Bar()]
    state.piece.bars[0].repeat = ".:"
    state.piece.bars[2].repeat = ":."
    state.cursor_bar = 0
    dispatch_key(
        state,
        ord("%"),
        handle_insert=actions.handle_insert,
        handle_normal=actions.handle_normal,
        handle_command=lambda _state, _key: True,
        handle_search=lambda _state, _key: True,
    )
    assert state.cursor_bar == 2


def test_normal_marks_set_and_jump() -> None:
    state = _state()
    state.cursor_bar = 0
    state.cursor_col = 2
    dispatch_key(
        state,
        ord("m"),
        handle_insert=actions.handle_insert,
        handle_normal=actions.handle_normal,
        handle_command=lambda _state, _key: True,
        handle_search=lambda _state, _key: True,
    )
    dispatch_key(
        state,
        ord("a"),
        handle_insert=actions.handle_insert,
        handle_normal=actions.handle_normal,
        handle_command=lambda _state, _key: True,
        handle_search=lambda _state, _key: True,
    )
    assert state.marks["a"] == (0, 0, 2)
    state.cursor_bar = 1
    state.cursor_col = 0
    dispatch_key(
        state,
        ord("'"),
        handle_insert=actions.handle_insert,
        handle_normal=actions.handle_normal,
        handle_command=lambda _state, _key: True,
        handle_search=lambda _state, _key: True,
    )
    dispatch_key(
        state,
        ord("a"),
        handle_insert=actions.handle_insert,
        handle_normal=actions.handle_normal,
        handle_command=lambda _state, _key: True,
        handle_search=lambda _state, _key: True,
    )
    assert (state.cursor_bar, state.cursor_col) == (0, 2)


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
    state.mode = Mode.INSERT
    actions.handle_insert(state, ord(" "))
    assert (0, 0, 0) not in state.overrides


def test_insert_mode_barline_sets_barline() -> None:
    state = _state()
    state.mode = Mode.INSERT
    actions.handle_insert(state, ord("|"))
    assert state.piece.bars[0].barline == "|"


def test_insert_mode_duration_does_not_advance() -> None:
    state = _state()
    state.mode = Mode.INSERT
    actions.handle_insert(state, ord("4"))
    assert state.cursor_col == 0


def test_insert_overflow_moves_to_next_bar() -> None:
    state = _state()
    state.mode = Mode.INSERT
    for col in range(4):
        state.durations[(0, 0, col)] = 4
        state.overrides[(0, 0, col)] = "a"
    state.cursor_col = 4
    actions.handle_insert(state, ord("b"))
    assert state.cursor_bar == 1
    assert (1, 0, 0) in state.overrides


def test_insert_mode_notes_insert_and_arrows_move() -> None:
    state = _state()
    state.mode = Mode.INSERT
    for idx, ch in enumerate("abcdnf"):
        actions.handle_insert(state, ord(ch))
        if idx < 4:
            assert state.overrides[(0, 0, idx)] == ch
        else:
            assert state.overrides[(1, 0, idx - 4)] == ch
    assert state.cursor_bar == 1
    assert state.cursor_col == 2
    actions.handle_insert(state, state.keycodes.left)
    assert state.cursor_col == 1
    actions.handle_insert(state, state.keycodes.right)
    assert state.cursor_col == 2
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
    assert (0, 0, 1) in state.overrides
    assert (0, 6, 1) not in state.overrides


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
    assert (0, 0, 0) in state.overrides
    assert (0, 0, 1) in state.overrides
    state.cursor_col = 1
    actions.handle_insert(state, 127)
    assert (0, 0, 1) not in state.overrides
    assert state.cursor_col == 0


def test_insert_mode_delete_clears_forward() -> None:
    state = _state()
    state.mode = Mode.INSERT
    actions.handle_insert(state, ord("a"))
    actions.handle_insert(state, ord("b"))
    state.cursor_col = 0
    actions.handle_insert(state, state.keycodes.dc)
    assert (0, 0, 0) not in state.overrides
    assert state.cursor_col == 1


def test_insert_duration_after_other_row_duration() -> None:
    state = _state()
    state.mode = Mode.INSERT
    actions.handle_insert(state, ord("4"))
    actions.handle_insert(state, ord("a"))
    state.cursor_string = 1
    state.cursor_col = 0
    actions.handle_insert(state, ord("5"))
    actions.handle_insert(state, ord("b"))
    assert state.durations[(0, 1, 0)] == 16


def test_insert_after_row_full_advances_and_allows_next_bar() -> None:
    state = _state()
    state.mode = Mode.INSERT
    for ch in "abcd":
        actions.handle_insert(state, ord(ch))
    actions.handle_insert(state, state.keycodes.down)
    actions.handle_insert(state, ord("5"))
    actions.handle_insert(state, ord("a"))
    for _ in range(state.bar_width):
        actions.handle_insert(state, state.keycodes.right)
    actions.handle_insert(state, ord("b"))
    assert (state.cursor_bar, 1, state.cursor_col - 1) in state.overrides


def test_insert_other_row_when_first_full_stays_in_bar() -> None:
    state = _state()
    state.mode = Mode.INSERT
    for ch in "abcd":
        actions.handle_insert(state, ord(ch))
    actions.handle_insert(state, state.keycodes.down)
    for _ in range(4):
        actions.handle_insert(state, state.keycodes.left)
    actions.handle_insert(state, ord("5"))
    actions.handle_insert(state, ord("a"))
    assert state.cursor_bar == 0
    assert state.overrides[(0, 1, 0)] == "a"


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


def test_gb_adds_bass_string() -> None:
    state = _state()
    start_strings = state.piece.strings
    state.settings["bassstrings"] = "d2"
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
        ord("b"),
        handle_insert=actions.handle_insert,
        handle_normal=actions.handle_normal,
        handle_command=lambda _state, _key: True,
        handle_search=lambda _state, _key: True,
    )
    assert state.piece.strings == start_strings + 1
    assert state.cursor_string == state.piece.strings - 1


def test_gb_requires_bass_strings_setting() -> None:
    state = _state()
    state.settings["bassstrings"] = ""
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
        ord("b"),
        handle_insert=actions.handle_insert,
        handle_normal=actions.handle_normal,
        handle_command=lambda _state, _key: True,
        handle_search=lambda _state, _key: True,
    )
    assert state.message == "No bass strings configured"


def test_insert_bass_slash_shorthand() -> None:
    state = _state()
    state.settings["style"] = "french"
    state.piece.strings = 7
    state.mode = Mode.INSERT
    actions.handle_insert(state, ord("/"))
    actions.handle_insert(state, ord("a"))
    assert state.overrides[(0, 6, 0)] == "a"


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


def _assert_inserted_a_alignment(lines: list[str], expected_flag_x: int | None) -> int:
    top_g_idx = next(i for i, line in enumerate(lines) if "g|" in line)
    flag_x, note_x = _flag_and_note_x(lines, top_g_idx)
    if expected_flag_x is None:
        expected_flag_x = flag_x
    assert flag_x == expected_flag_x
    assert flag_x == note_x
    _assert_time_cue_is_clear(lines, _first_flag_row(lines, top_g_idx))
    return expected_flag_x


def test_keypress_insert_aaaa_keeps_first_flag_aligned_and_off_time_cue() -> None:
    state = _state()
    state.screen_width = 28
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
    _press(state, ord("i"))
    first_flag_x: int | None = None
    for _ in range(4):
        _press(state, ord("a"))
        lines = _render_lines(state, width=state.screen_width, height=state.screen_height)
        first_flag_x = _assert_inserted_a_alignment(lines, first_flag_x)


def test_keypress_insert_aaaa_then_l_moves_one_cell_per_press_on_grid_bar() -> None:
    state = _state()
    state.screen_width = 18
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
    for key in ("i", "a", "a", "a", "a"):
        _press(state, ord(key))
    _press(state, 27)
    cols: list[int] = []
    for _ in range(10):
        _press(state, ord("l"))
        cols.append(state.cursor_col)
    # One press per rendered cell. Short systems retain the configured grid width
    # instead of collapsing an empty bar or stretching it to the full terminal.
    assert cols == [5, 6, 7, 8, 9, 10, 11, 0, 1, 2]
