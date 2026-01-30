from oud.core.model import Bar, Note
from oud.core.render_utils import (
    bar_cells,
    flag_positions_from_durations,
    flag_row,
    flag_row_style,
    format_fret,
    stem_row_style,
)


def test_format_fret_french_excludes_j() -> None:
    assert format_fret("french", 9) == "k"


def test_format_fret_french_alt_c() -> None:
    assert format_fret("french", 2, french_c="alt") == "r"


def test_format_fret_french_tail_e() -> None:
    assert format_fret("french", 4, french_e="tail") == "E"


def test_flag_positions_shortest_note_per_column() -> None:
    durations = {
        (0, 0, 0): 4,
        (0, 1, 0): 16,
        (0, 0, 2): 8,
    }
    positions = flag_positions_from_durations(
        durations,
        bar_index=0,
        strings=6,
        bar_width=4,
        default_duration=4,
    )
    assert positions[0][:2] == (0, 16)
    assert positions[1][:2] == (1, 4)
    assert positions[2][:2] == (2, 8)
    assert positions[3][:2] == (3, 4)
    dotted = {(0, 1)}
    positions = flag_positions_from_durations(
        durations,
        bar_index=0,
        strings=6,
        bar_width=4,
        default_duration=4,
        dotted=dotted,
    )
    assert positions[1][2] is True


def test_flag_row_marks_stems_flags_and_dots() -> None:
    row = flag_row(
        [
            (0, 8, False),
            (2, 16, True),
        ],
        bar_width=6,
    )
    assert row == ["I", "\\", "I", "\\", "\\", "."]


def test_flag_row_style_supports_alt_flags() -> None:
    row = flag_row_style([(0, 8, False)], 4, stem="|", flag="/")
    assert row == ["|", "/", " ", " "]


def test_flag_row_style_supports_stem_width() -> None:
    row = flag_row_style([(0, 8, False)], 6, stem="|", flag="-", stem_width=2)
    assert row == ["|", "|", "-", " ", " ", " "]


def test_stem_row_style_draws_stems_only() -> None:
    row = stem_row_style([(1, 8, False)], 4, stem="|")
    assert row == [" ", "|", " ", " "]


def test_bar_cells_string_mapping() -> None:
    bar = Bar(notes=[Note(string=1, fret=0, raw_pos=0), Note(string=6, fret=1, raw_pos=0)])
    cells = bar_cells(bar, strings=6, bar_width=4, style="french")
    assert cells[0][0] == "a"
    assert cells[5][0] == "b"
