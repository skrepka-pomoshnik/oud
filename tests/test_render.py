from oud.core.model import Bar, Chord, Note, Piece
from oud.core.render_utils import chord_positions, flag_row
from oud.core.view_model import (
    _bar_durations,
    _bar_flags,
    _bar_number_for_index,
    _bar_span_row,
    _filter_redundant_positions,
    _flag_positions_all,
    _layout_rows,
    _parse_time_signature,
    _tactus_row,
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
        durations={},
        bar_index=0,
        strings=6,
        bar_width=4,
        default_duration=4,
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
    assert flags[0] == "I"
    assert flags[3] == "I"
    assert flags[4] == "\\"


def test_flag_positions_filter_redundant() -> None:
    positions = [(0, 4, False), (1, 4, False), (2, 8, False), (3, 8, True)]
    filtered = _filter_redundant_positions(positions)
    assert filtered == [(0, 4, False), (2, 8, False), (3, 8, True)]


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


def test_bar_number_for_index() -> None:
    b0 = Bar()
    b1 = Bar()
    b1.repeat = "."
    piece = Piece(bars=[b0, b1, Bar(), Bar(), Bar(), Bar()])
    assert _bar_number_for_index(piece, 0, "start", "off", 1) == "[1]"
    assert _bar_number_for_index(piece, 3, "start", "off", 1) is None
    assert _bar_number_for_index(piece, 3, "every", "off", 1) == "[4]"
    assert _bar_number_for_index(piece, 4, "five", "off", 1) == "[5]"
    assert _bar_number_for_index(piece, 5, "five", "off", 1) is None
    assert _bar_number_for_index(piece, 1, "every", "on", 1) == "[3]"
    assert _bar_number_for_index(piece, 4, "every", "off", 2) == "[5]"
    assert _bar_number_for_index(piece, 2, "every", "off", 2) == "[3]"


def test_parse_time_signature() -> None:
    assert _parse_time_signature("C") == (4, 4, "C")
    assert _parse_time_signature("O") == (3, 4, "O")
    assert _parse_time_signature("3/8") == (3, 8, "3/8")


def test_tactus_row_marks_beats() -> None:
    row = _tactus_row(bar_width=8, beats=4)
    assert row[0] == "|"
    assert row[2] == "|"
    assert row[4] == "|"
    assert row[6] == "|"


def test_layout_rows_compacts_when_short() -> None:
    layout = _layout_rows(height=8, strings=6)
    assert layout["staff"] == 0
    assert layout["header"] is None
    layout = _layout_rows(height=20, strings=6)
    assert layout["staff"] is not None
    assert layout["dur"] is not None
