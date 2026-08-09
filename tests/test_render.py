from petrucci.core.model import Bar, Chord, Note, Piece
from petrucci.engraving.layout.map import layout_rows as _layout_rows
from petrucci.rendering.api import render_piece
from petrucci.rendering.primitives.utils import chord_positions, flag_row
from petrucci.terminal.canvas.framebuffer import FrameBuffer
from petrucci.terminal.view.model import (
    FlagPositionRequest,
    _bar_durations,
    _bar_flags,
    _bar_number_for_index,
    _bar_span_row,
    _beamified_chord_flag_positions,
    _filter_redundant_positions,
    _flag_positions_all,
    build_bar_view,
)


def test_bar_durations_prefers_smallest_division() -> None:
    durations = {
        (0, 0, 0): 2,
        (0, 1, 0): 4,
        (0, 2, 1): 8,
    }
    row = _bar_durations(durations, bar_index=0, strings=6, bar_width=4, default_duration=4)
    assert row[0] == "4"
    assert row[1] == "8"


def test_bar_durations_show_all_when_redundant_disabled() -> None:
    row = _bar_durations(
        durations={},
        bar_index=0,
        strings=6,
        bar_width=4,
        default_duration=4,
        hide_redundant=False,
    )
    assert row == ["4", "4", "4", "4"]


def test_bar_durations_are_fixed_width_cells() -> None:
    row = _bar_durations(
        durations={(0, 0, 0): 16, (0, 0, 2): 8},
        bar_index=0,
        strings=6,
        bar_width=6,
        default_duration=4,
        hide_redundant=True,
    )
    assert len("".join(row)) == 6
    text = "".join(row)
    assert text.startswith("16")
    assert "8" in text


def test_bar_flags_mapping() -> None:
    durations = {
        (0, 0, 0): 4,
        (0, 1, 1): 2,
        (0, 2, 2): 1,
    }
    row = _bar_flags(durations, bar_index=0, strings=6, bar_width=4, default_duration=4)
    assert row[0] == "0"
    assert row[1] == "w"
    assert row[2] == "W"


def test_bar_flags_show_all_when_redundant_disabled() -> None:
    row = _bar_flags(
        durations={},
        bar_index=0,
        strings=6,
        bar_width=4,
        default_duration=4,
        hide_redundant=False,
    )
    assert row == ["0", "0", "0", "0"]


def test_flag_positions_all_returns_each_column() -> None:
    positions = _flag_positions_all(
        FlagPositionRequest(
            durations={},
            bar_index=0,
            strings=6,
            bar_width=4,
            default_duration=4,
        )
    )
    assert positions == [(0, 4, False), (1, 4, False), (2, 4, False), (3, 4, False)]


def test_build_bar_view_shows_override_on_string() -> None:
    overrides = {(0, 0, 0): "1"}
    bar = Bar()
    view = build_bar_view(
        bar=bar,
        overrides=overrides,
        durations={},
        ornaments={},
        annotations={},
        slurs=[],
        ties=[],
        holds=[],
        bar_index=0,
        strings=6,
        bar_width=4,
        default_duration=4,
        style="french",
    )
    assert view["rows"][0].startswith("1")
    assert view["dur"][0].strip().startswith("4")


def test_build_bar_view_shows_flags_and_durations() -> None:
    bar = Bar()
    view = build_bar_view(
        bar=bar,
        overrides={},
        durations={(0, 0, 0): 4},
        ornaments={},
        annotations={},
        slurs=[],
        ties=[],
        holds=[],
        bar_index=0,
        strings=6,
        bar_width=4,
        default_duration=4,
        style="french",
    )
    assert view["flag"][0].startswith("0")
    assert view["dur"][0].startswith("4")


def test_bar_durations_hide_redundant_until_change() -> None:
    durations = {(0, 0, 0): 4, (0, 0, 1): 4, (0, 0, 2): 8}
    row = _bar_durations(
        durations,
        bar_index=0,
        strings=6,
        bar_width=4,
        default_duration=4,
        hide_redundant=True,
    )
    assert row[0] == "4"
    assert row[1] == " "
    assert row[2] == "8"


def test_chord_positions_spread() -> None:
    bar = Bar()
    chord1 = Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])
    chord2 = Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)])
    bar.chords = [chord1, chord2]
    positions = chord_positions(bar, bar_width=8, default_duration=4)
    assert positions[0][0] == 0
    assert positions[1][0] > positions[0][0]


def test_flag_row_marks_positions() -> None:
    positions = [(0, 4, False), (3, 8, False)]
    flags = flag_row(positions, bar_width=6)
    assert flags[0] == "|"
    assert flags[3] == "|"
    assert flags[4] == "\\"


def test_flag_positions_filter_redundant() -> None:
    positions = [(0, 4, False), (1, 4, False), (2, 8, False), (3, 8, True)]
    filtered = _filter_redundant_positions(positions)
    assert filtered == [(0, 4, False), (2, 8, False), (3, 8, True)]


def test_flag_positions_filter_redundant_tracks_dot_state_changes() -> None:
    positions = [(0, 16, True), (1, 16, False), (2, 16, False)]
    filtered = _filter_redundant_positions(positions)
    assert filtered == [(0, 16, True), (1, 16, False)]


def test_beamified_chord_flag_positions_suppresses_equal_flags_inside_grid_group() -> None:
    bar = Bar(
        chords=[
            Chord(note_type=6, dotted=False, grid="start", notes=[Note(1, 0, 0)]),
            Chord(note_type=6, dotted=False, grid="mid", notes=[Note(1, 1, 0)]),
            Chord(note_type=6, dotted=False, grid="end", notes=[Note(1, 2, 0)]),
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 3, 0)]),
        ],
    )
    positions = chord_positions(bar, bar_width=8, default_duration=4)
    filtered = _beamified_chord_flag_positions(bar, positions, hide_redundant=True, default_duration=4)
    assert [den for _col, den, _dot in filtered] == [16, 4]


def test_beamified_chord_flag_positions_keeps_partial_beam_changes_inside_group() -> None:
    bar = Bar(
        chords=[
            Chord(note_type=6, dotted=False, grid="start", notes=[Note(1, 0, 0)]),
            Chord(note_type=7, dotted=False, grid="mid", notes=[Note(1, 1, 0)]),
            Chord(note_type=6, dotted=False, grid="end", notes=[Note(1, 2, 0)]),
        ],
    )
    positions = chord_positions(bar, bar_width=8, default_duration=4)
    filtered = _beamified_chord_flag_positions(bar, positions, hide_redundant=True, default_duration=4)
    assert [den for _col, den, _dot in filtered] == [16, 32, 16]


def test_bar_durations_reveals_dot_state_reset() -> None:
    row = _bar_durations(
        durations={(0, 0, 0): 16, (0, 0, 3): 16},
        bar_index=0,
        strings=6,
        bar_width=6,
        default_duration=4,
        hide_redundant=True,
        dotted={(0, 0)},
    )
    text = "".join(row)
    assert "16." in text
    assert text.count("16") >= 2


def test_bar_span_row_marks_spans() -> None:
    row = _bar_span_row([(0, 1, 3)], bar_index=0, bar_width=5, start_char="(", end_char=")", fill_char="~")
    assert row == [" ", "(", "~", ")", " "]


def test_build_bar_view_shows_annotations_and_ornaments() -> None:
    bar = Bar()
    view = build_bar_view(
        bar=bar,
        overrides={},
        durations={},
        ornaments={(0, 1): "#"},
        annotations={(0, 2): "x"},
        slurs=[],
        ties=[],
        holds=[],
        bar_index=0,
        strings=6,
        bar_width=4,
        default_duration=4,
        style="french",
    )
    assert view["orn"][0][1] == "#"
    assert view["ann"][0][2] == "x"


def test_build_bar_view_shows_imported_ft3_extras_and_user_overrides_win() -> None:
    bar = Bar(
        chords=[
            Chord(
                note_type=4,
                dotted=False,
                grid=None,
                notes=[
                    Note(
                        1,
                        0,
                        0,
                        left_fingering="2",
                        right_fingering="thumb",
                        left_ornament="#",
                    ),
                ],
            ),
        ],
    )
    view = build_bar_view(
        bar=bar,
        overrides={},
        durations={},
        ornaments={(0, 0): "*"},
        annotations={(0, 0): "x"},
        slurs=[],
        ties=[],
        holds=[],
        bar_index=0,
        strings=6,
        bar_width=4,
        default_duration=4,
        style="french",
        showft3extras="on",
        ft3fingering="both",
        ft3ornaments="both",
    )
    assert "x" in view["ann"][0]
    assert "*" in view["orn"][0]


def test_build_bar_view_can_hide_imported_ft3_extras() -> None:
    bar = Bar(
        chords=[
            Chord(
                note_type=4,
                dotted=False,
                grid=None,
                notes=[Note(1, 1, 0, left_fingering="1", left_ornament="#")],
            ),
        ],
    )
    shown = build_bar_view(
        bar=bar,
        overrides={},
        durations={},
        ornaments={},
        annotations={},
        slurs=[],
        ties=[],
        holds=[],
        bar_index=0,
        strings=6,
        bar_width=4,
        default_duration=4,
        style="french",
        showft3extras="on",
    )
    hidden = build_bar_view(
        bar=bar,
        overrides={},
        durations={},
        ornaments={},
        annotations={},
        slurs=[],
        ties=[],
        holds=[],
        bar_index=0,
        strings=6,
        bar_width=4,
        default_duration=4,
        style="french",
        showft3extras="off",
    )
    assert any(ch != " " for ch in shown["ann"][0])
    assert any(ch != " " for ch in shown["orn"][0])
    assert hidden["ann"][0].strip() == ""
    assert hidden["orn"][0].strip() == ""


def test_build_bar_view_shows_slur_tie_hold() -> None:
    bar = Bar()
    view = build_bar_view(
        bar=bar,
        overrides={},
        durations={},
        ornaments={},
        annotations={},
        slurs=[(0, 0, 2)],
        ties=[(0, 1, 3)],
        holds=[(0, 0, 3)],
        bar_index=0,
        strings=6,
        bar_width=4,
        default_duration=4,
        style="french",
    )
    assert view["slur"][0].startswith("(")
    assert view["tie"][0][1] == "["
    assert view["hold"][0].startswith("<")


def test_build_bar_view_tie_cue_style_variants() -> None:
    bar = Bar()
    paren = build_bar_view(
        bar=bar,
        overrides={},
        durations={},
        ornaments={},
        annotations={},
        slurs=[],
        ties=[(0, 1, 3)],
        holds=[],
        bar_index=0,
        strings=6,
        bar_width=4,
        default_duration=4,
        style="french",
        tiecuestyle="paren",
    )
    hidden = build_bar_view(
        bar=bar,
        overrides={},
        durations={},
        ornaments={},
        annotations={},
        slurs=[],
        ties=[(0, 1, 3)],
        holds=[],
        bar_index=0,
        strings=6,
        bar_width=4,
        default_duration=4,
        style="french",
        tiecuestyle="hide",
    )
    assert paren["tie"][0][1] == "("
    assert paren["tie"][0][3] == ")"
    assert hidden["tie"][0].strip() == ""


def test_build_bar_view_tie_noteheads_hide_hides_continued_column_noteheads() -> None:
    bar = Bar(
        chords=[
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 1, 0)]),
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 2, 0)]),
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
        ],
    )
    shown = build_bar_view(
        bar=bar,
        overrides={},
        durations={},
        ornaments={},
        annotations={},
        slurs=[],
        ties=[(0, 1, 3)],
        holds=[],
        bar_index=0,
        strings=6,
        bar_width=4,
        default_duration=4,
        style="french",
        tienoteheads="show",
    )
    hidden = build_bar_view(
        bar=bar,
        overrides={},
        durations={},
        ornaments={},
        annotations={},
        slurs=[],
        ties=[(0, 1, 3)],
        holds=[],
        bar_index=0,
        strings=6,
        bar_width=4,
        default_duration=4,
        style="french",
        tienoteheads="hide",
    )
    # Column 3 has a notehead in show mode and is blanked in hide mode.
    assert any(row[3] != "-" for row in shown["rows"])
    assert all(row[3] == "-" for row in hidden["rows"])


def test_build_bar_view_tie_noteheads_parenthesize_marks_cue_rows_keeps_width() -> None:
    bar = Bar(
        chords=[
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 1, 0)]),
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 2, 0)]),
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
        ],
    )
    paren = build_bar_view(
        bar=bar,
        overrides={},
        durations={},
        ornaments={},
        annotations={},
        slurs=[],
        ties=[(0, 1, 3)],
        holds=[],
        bar_index=0,
        strings=6,
        bar_width=4,
        default_duration=4,
        style="french",
        tiecuestyle="hide",
        tienoteheads="parenthesize",
    )
    assert any(row[3] != "-" for row in paren["rows"])
    assert all(len(row) == 4 for row in paren["rows"])
    assert paren["ann"][0][3] == "("
    assert ")" in paren["tie"][0]


def test_build_bar_view_tie_noteheads_parenthesize_falls_back_on_cue_collisions() -> None:
    bar = Bar(
        chords=[
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 1, 0)]),
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 2, 0)]),
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
        ],
    )
    view = build_bar_view(
        bar=bar,
        overrides={},
        durations={},
        ornaments={},
        annotations={(0, 3): "x"},  # occupy preferred opening-cue slot
        slurs=[],
        ties=[(0, 1, 3)],
        holds=[],
        bar_index=0,
        strings=6,
        bar_width=4,
        default_duration=4,
        style="french",
        tiecuestyle="bracket",  # occupy preferred closing-cue slot
        tienoteheads="parenthesize",
    )
    # Opening cue falls back to left side of tie row.
    assert "(" in view["tie"][0]
    # Closing cue falls back to ornament row when tie row end already has ']'.
    assert view["orn"][0][3] == ")"
    assert view["ann"][0][3] == "x"


def test_build_bar_view_tie_parenthesize_uses_slur_hold_rows_when_tie_row_busy() -> None:
    bar = Bar(
        chords=[
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 1, 0)]),
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 2, 0)]),
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
        ],
    )
    view = build_bar_view(
        bar=bar,
        overrides={},
        durations={},
        ornaments={(0, 3): "*"},  # occupy ornament fallback for close cue
        annotations={(0, 3): "x"},  # occupy annotation preferred open slot
        slurs=[(0, 0, 3)],  # fills slur row end with ')' when paren style
        ties=[(0, 1, 3)],
        holds=[(0, 0, 3)],  # provides another fallback row
        bar_index=0,
        strings=6,
        bar_width=4,
        default_duration=4,
        style="french",
        tiecuestyle="bracket",
        slurcuestyle="paren",
        holdcuestyle="paren",
        tienoteheads="parenthesize",
    )
    # Opening cue should still appear somewhere despite annotation+tierow pressure.
    assert any("(" in view[key][0] for key in ("tie", "slur", "hold"))
    # Closing cue should still appear despite tie+ornament pressure.
    assert any(")" in view[key][0] for key in ("tie", "slur", "hold"))


def test_build_bar_view_slur_and_hold_cue_style_variants() -> None:
    bar = Bar()
    alt = build_bar_view(
        bar=bar,
        overrides={},
        durations={},
        ornaments={},
        annotations={},
        slurs=[(0, 0, 2)],
        ties=[],
        holds=[(0, 0, 3)],
        bar_index=0,
        strings=6,
        bar_width=4,
        default_duration=4,
        style="french",
        slurcuestyle="bracket",
        holdcuestyle="paren",
    )
    hidden = build_bar_view(
        bar=bar,
        overrides={},
        durations={},
        ornaments={},
        annotations={},
        slurs=[(0, 0, 2)],
        ties=[],
        holds=[(0, 0, 3)],
        bar_index=0,
        strings=6,
        bar_width=4,
        default_duration=4,
        style="french",
        slurcuestyle="hide",
        holdcuestyle="hide",
    )
    assert alt["slur"][0][0] == "["
    assert alt["slur"][0][2] == "]"
    assert alt["hold"][0][0] == "("
    assert alt["hold"][0][3] == ")"
    assert hidden["slur"][0].strip() == ""
    assert hidden["hold"][0].strip() == ""


def test_build_bar_view_gliss_cue_style_variants_and_tie_parenthesize_fallback() -> None:
    bar = Bar(
        chords=[
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 1, 0)]),
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 3, 0)]),
        ],
    )
    shown = build_bar_view(
        bar=bar,
        overrides={},
        durations={},
        ornaments={(0, 3): "*"},
        annotations={(0, 3): "x"},
        slurs=[],
        ties=[(0, 1, 3)],
        holds=[],
        bar_index=0,
        strings=6,
        bar_width=4,
        default_duration=4,
        style="french",
        glisses=[(0, 0, 3)],
        tiecuestyle="bracket",
        tienoteheads="parenthesize",
        glisscuestyle="slash",
    )
    hidden = build_bar_view(
        bar=bar,
        overrides={},
        durations={},
        ornaments={},
        annotations={},
        slurs=[],
        ties=[],
        holds=[],
        bar_index=0,
        strings=6,
        bar_width=4,
        default_duration=4,
        style="french",
        glisses=[(0, 0, 3)],
        glisscuestyle="hide",
    )
    assert shown["gliss"][0][0] == "/"
    assert shown["gliss"][0][3] == "\\"
    assert any("(" in shown[key][0] for key in ("tie", "gliss"))
    assert hidden["gliss"][0].strip() == ""


def test_bar_number_for_index() -> None:
    b0 = Bar()
    b1 = Bar()
    b1.repeat = "."
    piece = Piece(bars=[b0, b1, Bar(), Bar(), Bar(), Bar()])
    assert _bar_number_for_index(piece, 0, "start", "off", 1) == "[1]"
    assert _bar_number_for_index(piece, 3, "start", "off", 1) is None
    assert _bar_number_for_index(piece, 0, "every", "off", 1) is None
    assert _bar_number_for_index(piece, 3, "every", "off", 1) == "[4]"
    assert _bar_number_for_index(piece, 4, "five", "off", 1) == "[5]"
    assert _bar_number_for_index(piece, 5, "five", "off", 1) is None
    assert _bar_number_for_index(piece, 1, "every", "on", 1) == "[3]"
    assert _bar_number_for_index(piece, 3, "every", "off", 2) == "[4]"
    assert _bar_number_for_index(piece, 2, "every", "off", 2) is None
    assert _bar_number_for_index(piece, 3, "system", "off", 1, system_start=True) == "4"
    assert _bar_number_for_index(piece, 3, "system", "off", 1) is None


def test_layout_rows_compacts_when_short() -> None:
    layout = _layout_rows(height=8, strings=6)
    assert layout["staff"] == 0
    assert layout["header"] is None
    layout = _layout_rows(height=20, strings=6)
    assert layout["staff"] is not None
    assert layout["dur"] is not None


def test_render_auto_mode_not_forced_to_one_bar_per_row() -> None:
    piece = Piece(
        title="T",
        bars=[Bar(notes=[Note(1, 0, 0)]) for _ in range(4)],
        strings=6,
    )
    settings = {
        "layout": "auto",
        "justify": "compact",
        "style": "french",
        "linelen": "0",
        "bargap": "1",
        "barpad": "1",
        "barsperline": "0",
        "maxbars": "0",
        "showdur": "off",
        "showextras": "off",
        "showtactus": "off",
        "flagredundant": "on",
        "flagstems": "single",
        "tuning": "g2c3f3a3d4g4",
        "showtuning": "on",
        "tuninglabels": "relative",
        "bassstrings": "",
        "basslabels": "tuning",
        "measures": "start",
        "countdots": "off",
        "time": "C",
        "key": "C",
        "flagstyle": "standard",
    }
    fb = FrameBuffer(24, 120)
    render_piece(
        fb,
        piece,
        0,
        0,
        0,
        0,
        10,
        {},
        {},
        {},
        {},
        set(),
        set(),
        [],
        [],
        [],
        "normal",
        "",
        "",
        "",
        "",
        settings,
        None,
        set(),
        "",
        [],
        0,
        0,
    )
    frame = fb.snapshot()
    note_line = next(line for line in frame.lines if "-a-" in line)
    assert note_line.count("|") >= 3


def test_render_shows_imported_ft3_extras_rows_by_default() -> None:
    piece = Piece(
        title="T",
        bars=[
            Bar(
                chords=[
                    Chord(
                        note_type=4,
                        dotted=False,
                        grid=None,
                        notes=[Note(1, 0, 0, left_fingering="2", left_ornament="#")],
                    ),
                ],
            ),
        ],
        strings=6,
    )
    settings = {
        "layout": "auto",
        "justify": "compact",
        "style": "french",
        "linelen": "0",
        "bargap": "1",
        "barpad": "1",
        "barsperline": "0",
        "maxbars": "0",
        "showdur": "off",
        "showextras": "off",
        "showft3extras": "on",
        "ft3fingering": "both",
        "ft3ornaments": "both",
        "showtactus": "off",
        "flagredundant": "on",
        "flagstems": "single",
        "tuning": "g2c3f3a3d4g4",
        "showtuning": "on",
        "tuninglabels": "relative",
        "bassstrings": "",
        "basslabels": "tuning",
        "measures": "start",
        "countdots": "off",
        "time": "C",
        "timesigstyle": "symbol",
        "key": "C",
        "flagstyle": "standard",
    }
    fb = FrameBuffer(20, 80)
    render_piece(
        fb,
        piece,
        0,
        0,
        0,
        0,
        10,
        {},
        {},
        {},
        {},
        set(),
        set(),
        [],
        [],
        [],
        "normal",
        "",
        "",
        "",
        "",
        settings,
        None,
        set(),
        "",
        [],
        0,
        0,
    )
    lines = fb.snapshot().lines
    assert any("#" in line for line in lines)


def test_render_meta_row_shows_dynamic_and_fermata_signs() -> None:
    piece = Piece(
        title="T",
        bars=[
            Bar(
                dynamic="mf",
                fermata=True,
                chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])],
            ),
        ],
        strings=6,
    )
    settings = {
        "layout": "auto",
        "justify": "compact",
        "style": "french",
        "linelen": "0",
        "bargap": "1",
        "barpad": "1",
        "barsperline": "0",
        "maxbars": "0",
        "showdur": "off",
        "showextras": "off",
        "showft3extras": "off",
        "showtactus": "off",
        "flagredundant": "on",
        "flagstems": "single",
        "tuning": "g2c3f3a3d4g4",
        "showtuning": "on",
        "tuninglabels": "relative",
        "bassstrings": "",
        "basslabels": "tuning",
        "measures": "start",
        "countdots": "off",
        "time": "C",
        "timesigstyle": "symbol",
        "key": "C",
        "flagstyle": "standard",
    }
    fb = FrameBuffer(16, 80)
    render_piece(
        fb,
        piece,
        0,
        0,
        0,
        0,
        8,
        {},
        {},
        {},
        {},
        set(),
        set(),
        [],
        [],
        [],
        "normal",
        "",
        "",
        "",
        "",
        settings,
        None,
        set(),
        "",
        [],
        0,
        0,
    )
    assert any("^ mf" in line or "mf ^" in line for line in fb.snapshot().lines)
