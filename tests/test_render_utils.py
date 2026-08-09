from petrucci.core.model import Bar, Chord, Note
from petrucci.rendering.primitives.utils import (
    bar_cells,
    bar_cells_from_chords,
    duration_display,
    flag_count,
    flag_positions_from_durations,
    flag_row,
    flag_row_style,
    format_fret,
    soft_beat_snap_map,
    spread_flag_positions,
    stem_row_style,
    trim_right_slack_for_onsets,
)


def test_format_fret_french_excludes_j() -> None:
    assert format_fret("french", 9) == "k"


def test_format_fret_french_alt_c() -> None:
    assert format_fret("french", 2, french_c="alt") == "r"


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


def test_flag_positions_use_sparse_coordinates_without_scanning_the_coordinate_space() -> None:
    positions = flag_positions_from_durations(
        {(0, 1_000_000_000, 2): 8},
        bar_index=0,
        strings=1_000_000_001,
        bar_width=1_000_000_000,
        default_duration=4,
    )

    assert positions == [(0, 4, False), (2, 8, False), (3, 4, False)]


def test_flag_row_marks_stems_flags_and_dots() -> None:
    row = flag_row(
        [
            (0, 8, False),
            (2, 16, True),
        ],
        bar_width=6,
    )
    # 8th and 16th cues overlap at the synthetic columns; ensure both stems survive
    # and the denser 16th contributes multiple tails.
    assert row[0] == "|"
    assert row[2] == "|"  # second stem anchor
    assert row.count("\\") >= 3


def test_flag_row_style_supports_alt_flags() -> None:
    row = flag_row_style([(0, 8, False)], 4, stem="|", flag="/")
    assert row == ["|", "/", "/", " "]


def test_flag_row_style_supports_stem_width() -> None:
    row = flag_row_style([(0, 8, False)], 6, stem="|", flag="-", stem_width=2)
    assert row == ["|", "|", "-", "-", " ", " "]


def test_stem_row_style_draws_stems_only() -> None:
    row = stem_row_style([(1, 8, False)], 4, stem="|")
    assert row == [" ", "|", " ", " "]


def test_flag_row_style_places_dot_after_flags_when_space() -> None:
    row = flag_row_style([(0, 16, True)], 6, stem="|", flag="\\")
    # 16th = three flags in this tablature cue mapping; dot follows stem+flags.
    assert row == ["|", "\\", "\\", "\\", ".", " "]


def test_flag_row_style_supports_afterstem_dot_placement() -> None:
    row = flag_row_style(
        [(0, 16, True)],
        7,
        stem="|",
        flag="\\",
        dotplacement="afterstem",
    )
    assert row == ["|", ".", "\\", "\\", "\\", " ", " "]


def test_stem_row_style_supports_double_stem_width() -> None:
    row = stem_row_style([(1, 8, False)], 5, stem="|", stem_width=2)
    assert row == [" ", "|", "|", " ", " "]


def test_flag_count_distinguishes_half_and_quarter() -> None:
    assert flag_count(2) == 0
    assert flag_count(4) == 1
    assert flag_count(8) == 2


def test_duration_display_uses_full_denominators() -> None:
    assert duration_display(16) == "16"
    assert duration_display(32, dotted=True) == "32."


def test_spread_flag_positions_preserves_tail_space_at_right_edge() -> None:
    # Regression: last 8th at right edge must keep room for its tails.
    positions = [(0, 4, True), (3, 16, False), (4, 8, False)]
    spread = spread_flag_positions(positions, 8, min_gap=1)
    assert spread[-1][0] <= 6
    row = flag_row_style(spread, 8, stem="|", flag="\\")
    assert row[6] in {"|", "\\"}
    assert row[7] == "\\"


def test_flag_row_style_frog_galliard_bar13_spacing() -> None:
    positions = [
        (0, 16, True),
        (2, 32, False),
        (3, 16, False),
        (5, 16, False),
        (7, 16, False),
        (9, 16, False),
    ]
    row = flag_row_style(spread_flag_positions(positions, 40), 40, stem="|", flag="\\")
    text = "".join(row)
    # Dotted 16th should still emit a dot after its stem/tails when space allows.
    assert "." in text
    # Ensure at least one space between visible groups.
    groups = [idx for idx, ch in enumerate(text) if ch == "|"]
    assert len(groups) >= 3
    assert groups[1] - groups[0] >= 5
    assert groups[2] - groups[1] >= 4


def test_dense_dotted_16th_32nd_group_keeps_dot_and_tail_visibility() -> None:
    positions = [
        (0, 16, True),
        (1, 32, False),
        (2, 16, False),
    ]
    spread = spread_flag_positions(positions, 20, min_gap=1)
    row = flag_row_style(spread, 20, stem="|", flag="\\")
    text = "".join(row)
    assert text.count(".") == 1
    stem_cols = [idx for idx, ch in enumerate(text) if ch == "|"]
    dot_idx = text.index(".")
    assert len(stem_cols) == 3
    assert stem_cols[0] < dot_idx < stem_cols[1]
    # 32nd cue contributes more tails than 16th (current mapping: 4 vs 3).
    mid_span = text[stem_cols[1] : stem_cols[2]]
    assert mid_span.count("\\") >= 4


def test_dotted_fast_groups_keep_dot_after_tails_in_dense_sequence() -> None:
    # Geometry regression: dotted fast groups near neighbors must keep the dot
    # after the tail cluster, not inside/overlapping it.
    positions = [
        (0, 16, True),
        (1, 16, False),
        (2, 32, False),
        (3, 16, False),
        (5, 32, True),
        (6, 16, False),
    ]
    spread = spread_flag_positions(positions, 32, min_gap=1)
    row = flag_row_style(spread, 32, stem="|", flag="\\")
    text = "".join(row)
    assert text.count(".") == 2
    for col, denom, dotted in spread:
        if not dotted:
            continue
        tails = flag_count(denom)
        segment = text[col : col + 1 + tails + 3]
        assert "." in segment
        dot_idx = text.index(".", col)
        assert dot_idx > col + tails


def test_dotted_32nd_near_right_edge_keeps_dot_and_tail_after_spread() -> None:
    positions = [(0, 8, False), (2, 16, False), (3, 32, True)]
    spread = spread_flag_positions(positions, 12, min_gap=1)
    row = flag_row_style(spread, 12, stem="|", flag="\\")
    text = "".join(row)
    assert "." in text
    last_stem = max(idx for idx, ch in enumerate(text) if ch == "|")
    dot_idx = text.index(".")
    assert dot_idx > last_stem
    # Last visible cell should be used by the dense dotted group (tail or dot), not blank.
    assert text.rstrip()[-1] in {"\\", "."}


def test_spread_flag_positions_avoids_overlap_in_dense_groups() -> None:
    positions = [(0, 16, True), (2, 32, False), (3, 16, False)]
    spread = spread_flag_positions(positions, 16)
    assert [col for col, _den, _dot in spread] == [0, 5, 10]


def test_spread_flag_positions_with_min_gap_adds_separator() -> None:
    positions = [(0, 16, True), (2, 32, False), (3, 16, False)]
    spread = spread_flag_positions(positions, 24, min_gap=1)
    assert [col for col, _den, _dot in spread] == [0, 6, 12]


def test_soft_beat_snap_map_groups_onsets_by_equal_beats() -> None:
    # Four onsets compressed toward the left should be redistributed across beats.
    positions = [
        (0, 4, False),
        (2, 8, False),
        (4, 8, False),
        (6, 4, False),
    ]
    mapping = soft_beat_snap_map(
        positions,
        grid_width=8,
        content_width=16,
        beats=4,
        min_gap=0,
    )
    cols = [mapping[p[0]] for p in positions]
    assert cols == sorted(cols)
    # Expect one onset landing in each quarter bucket (0-3, 4-7, 8-11, 12-15).
    assert [min(3, col // 4) for col in cols] == [0, 1, 2, 3]


def test_soft_beat_snap_map_does_not_reserve_trailing_empty_beat() -> None:
    # Onsets only in beats 1-3 of a 4-beat bar should not leave a fake empty beat-4 gap.
    positions = [
        (0, 4, False),
        (2, 8, False),
        (4, 8, False),
    ]
    mapping = soft_beat_snap_map(
        positions,
        grid_width=8,
        content_width=16,
        beats=4,
        min_gap=0,
    )
    cols = [mapping[p[0]] for p in positions]
    assert cols == sorted(cols)
    # Last onset should reach into the right half, not be stuck in beat-3 area.
    assert cols[-1] >= 10


def test_trim_right_slack_for_onsets_uses_visible_flags_not_hidden_redundant() -> None:
    # Last onset is hidden-redundant (no visible tail), so only one trailing dash is needed.
    all_positions = [(0, 16, False), (4, 16, False), (8, 16, False)]
    visible_positions = [(0, 16, False)]
    mapping = {0: 0, 4: 4, 8: 8}
    trimmed = trim_right_slack_for_onsets(
        mapping,
        all_positions=all_positions,
        visible_positions=visible_positions,
        content_width=12,
    )
    assert trimmed[8] == 10


def test_trim_right_slack_preserves_left_anchor_for_beat_aligned_bar() -> None:
    mapping = {0: 0, 1: 1, 2: 2, 4: 4, 5: 5, 6: 6, 8: 8, 9: 9}
    all_positions = [(c, 16, False) for c in [0, 1, 2, 4, 5, 6, 8, 9]]
    visible_positions = [(0, 16, False)]
    trimmed = trim_right_slack_for_onsets(
        mapping,
        all_positions=all_positions,
        visible_positions=visible_positions,
        content_width=16,
    )
    assert trimmed[0] == 0
    assert trimmed[9] == 14


def test_bar_cells_string_mapping() -> None:
    bar = Bar(notes=[Note(string=1, fret=0, raw_pos=0), Note(string=6, fret=1, raw_pos=0)])
    cells = bar_cells(bar, strings=6, bar_width=4, style="french")
    assert cells[0][0] == "a"
    assert cells[5][0] == "b"


def test_bar_cells_multidigit_frets_preserve_spacing_in_italian_and_letters_in_french() -> None:
    bar = Bar(notes=[Note(1, 10, 0), Note(1, 11, 1), Note(1, 12, 2)])
    italian = "".join(bar_cells(bar, strings=6, bar_width=12, style="italian")[0])
    french = "".join(bar_cells(bar, strings=6, bar_width=12, style="french")[0])
    assert "x-11-12" in italian
    assert "l-m-n" in french


def test_bar_cells_from_chords_multidigit_italian_tokens_do_not_merge() -> None:
    bar = Bar(
        chords=[
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 10, 0)]),
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 11, 0)]),
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 12, 0)]),
        ],
    )
    row = bar_cells_from_chords(bar, strings=6, bar_width=12, default_duration=4, style="italian")[0]
    text = "".join(str(ch) for ch in row)
    assert "11" in text and "12" in text
    # Collision-safe separation: token starts are staggered, not glued into one long number.
    assert "x11" not in text
    assert "1112" not in text


def test_bar_cells_from_chords_multidigit_french_tokens_do_not_merge() -> None:
    bar = Bar(
        chords=[
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 10, 0)]),
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 11, 0)]),
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 12, 0)]),
        ],
    )
    row = bar_cells_from_chords(bar, strings=6, bar_width=12, default_duration=4, style="french")[0]
    text = "".join(str(ch) for ch in row)
    assert "l" in text and "m" in text and "n" in text
    # Letter-style multi-fret tokens should remain separated by filler cells.
    assert "lm" not in text
    assert "mn" not in text
