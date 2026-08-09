from __future__ import annotations

from fractions import Fraction

from petrucci.adapters.duet import (
    duet_bar_mapping,
    duet_logical_bar_count,
    duet_raw_bar_index,
    duet_staff_labels,
    duet_storage_mode,
    duet_view_mode,
    is_duet_score_piece,
    split_duet_pair_map,
    split_duet_pair_set,
    split_duet_piece_staff,
    split_duet_span_list,
    split_duet_triplet_map,
    split_duet_triplet_set,
)
from petrucci.core.model import Bar, Chord, Piece
from petrucci.rendering.primitives.geometry import (
    _anchor_destination,
    _anchor_flag_positions_to_note_cols,
    _event_display_onset_cols,
    _expand_scale_map_from_anchors,
    _grid_display_map,
    _interpolated_anchor_destination,
    _place_duration_cells_aligned,
    _scale_chord_row,
)
from petrucci.terminal.canvas.framebuffer import (
    Frame,
    FrameBuffer,
    draw_frame_rows,
    frame_diff_rows,
    iter_attr_runs,
    overlay_dirty_rows,
    overlay_frame,
)
from petrucci.terminal.canvas.screen import Screen
from petrucci.terminal.view.width import (
    _infer_time_signature,
    _nearest_free_column,
    _parse_pitch_labels,
    _scale_col,
    _scale_row,
    _time_signature_for_duration,
)


class _MemoryScreen(Screen):
    def __init__(self, height: int, width: int) -> None:
        self.height = height
        self.width = width
        self.calls: list[tuple[int, int, str, int]] = []

    def getmaxyx(self) -> tuple[int, int]:
        return self.height, self.width

    def addstr(self, y: int, x: int, text: str, attr: int = 0) -> None:
        self.calls.append((y, x, text, attr))

    def erase(self) -> None:
        self.calls.clear()

    def refresh(self) -> None:
        return None


def test_framebuffer_clips_overlays_and_reports_semantic_row_changes() -> None:
    buffer = FrameBuffer(2, 4)
    buffer.addstr(-1, 0, "ignored", 1)
    buffer.addstr(0, 4, "ignored", 1)
    buffer.addstr(0, -1, "abcde", 7)
    buffer.addstr(1, 0, "a\u0323bc", 3)
    first = buffer.snapshot()

    assert first.lines == ["bcde", "a\u0323bc "]
    assert first.attrs == [(7, 7, 7, 7), (3, 3, 3, 0)]
    assert frame_diff_rows(None, first) == {0, 1}
    assert frame_diff_rows(Frame([first.lines[0]], [first.attrs[0]]), first) == {1}

    overlaid = overlay_frame(first, [(-1, 0, "x", 1), (0, -1, "XY", 9), (1, 3, "ZQ", 5)])
    assert overlaid.lines == ["Ycde", "a\u0323bcZ"]
    assert overlaid.attrs[0][0] == 9
    assert frame_diff_rows(first, overlaid) == {0, 1}

    assert overlay_dirty_rows(overlaid, base_frame=first, ops=[], rows=set()) is overlaid
    restored = overlay_dirty_rows(
        overlaid,
        base_frame=first,
        ops=[(0, 1, "Q", 4)],
        rows={-1, 0, 9},
    )
    assert restored.lines == ["bQde", overlaid.lines[1]]
    assert restored.attrs[0][1] == 4

    buffer.erase()
    assert buffer.snapshot().lines == ["    ", "    "]


def test_frame_attribute_runs_and_screen_bounds_are_deterministic() -> None:
    assert iter_attr_runs("", ()) == []
    assert iter_attr_runs("ab", (2, 2, 3)) == [("ab", 2), (" ", 3)]
    assert iter_attr_runs("abc", (1, 2)) == [("a", 1), ("b", 2)]
    assert iter_attr_runs("a\u0323b", (4, 5)) == [("a\u0323", 4), ("b", 5)]

    zero = _MemoryScreen(1, 0)
    draw_frame_rows(zero, Frame(["abc"], [(0, 0, 0)]), {-1, 0, 2})
    assert zero.calls == []

    screen = _MemoryScreen(1, 2)
    draw_frame_rows(screen, Frame(["abc"], [(1, 1, 1)]), {-1, 0, 2})
    assert screen.calls == [(0, 0, "ab", 1)]


def test_typesetting_anchor_microcases_preserve_order_and_collisions() -> None:
    assert _event_display_onset_cols(positions=None, grid_map=[0], draw_pad=1) == []
    assert _event_display_onset_cols(
        positions=[(-1, 4, False), (0, 4, False), (0, 8, False), (2, 4, False)],
        grid_map=[3, 4, 5],
        draw_pad=1,
    ) == [4, 6]
    assert _anchor_flag_positions_to_note_cols([], [1]) == []
    assert _anchor_flag_positions_to_note_cols(
        [(0, 4, False), (2, 8, True), (5, 4, False)],
        [1, 4],
    ) == [(1, 4, False), (4, 8, True)]

    tight = {0: 0, 10: 1}
    wide = {0: 0, 10: 10}
    assert _interpolated_anchor_destination(5, 0, 10, tight) == 1
    assert _interpolated_anchor_destination(5, 0, 10, wide) == 5
    assert _anchor_destination(0, [0, 10], wide, width_hint=11, content_width=11) == 0
    assert _anchor_destination(5, [0, 10], wide, width_hint=11, content_width=11) == 5
    assert _anchor_destination(12, [0, 10], wide, width_hint=13, content_width=13) == 12
    assert _anchor_destination(-2, [0, 10], wide, width_hint=13, content_width=13) == -2
    assert _anchor_destination(2, [], {}, width_hint=5, content_width=5) == 2

    assert _expand_scale_map_from_anchors([], {}, content_width=4) == {}
    assert _expand_scale_map_from_anchors([(0, 4, False), (4, 4, False)], {}, content_width=5) == {0: 0, 4: 4}
    expanded = _expand_scale_map_from_anchors(
        [(0, 4, False), (2, 8, False), (4, 4, False)],
        {0: 0, 4: 2},
        content_width=3,
    )
    assert list(expanded.values()) == sorted(expanded.values())

    assert _scale_chord_row(
        ["a", "-", "b"],
        fill_char="-",
        src_to_dest={0: 0, 1: 0, 2: 1},
        bar_width=3,
        content_width=2,
    ) == ["a", "b"]
    duration_row = [" "] * 3
    _place_duration_cells_aligned(duration_row, -1, "8")
    _place_duration_cells_aligned(duration_row, 2, "16")
    assert duration_row == [" ", " ", "1"]
    assert _grid_display_map(grid_width=5, content_width=3, src_to_dest={0: 0, 4: 2}) == [0, 0, 1, 1, 2]


def _duet(*, bars: int = 4, ensemble: str | None = "lute 1, lute 2") -> Piece:
    return Piece(part="score", ensemble=ensemble, bars=[Bar() for _ in range(bars)])


def test_duet_projection_covers_halves_legacy_and_filtered_collections() -> None:
    plain = Piece(bars=[Bar()])
    malformed = _duet(ensemble="voice")
    halves = _duet()
    odd = _duet(bars=3)

    assert not is_duet_score_piece(plain)
    assert not is_duet_score_piece(malformed)
    assert duet_storage_mode(plain) == "interleaved"
    assert duet_storage_mode(halves) == "halves"
    assert duet_storage_mode(odd) == "interleaved"
    assert duet_staff_labels(plain) == ("Lute 1", "Lute 2")
    assert duet_staff_labels(halves) == ("Lute 1", "Lute 2")
    assert duet_logical_bar_count(halves) == 2
    assert duet_logical_bar_count(odd) == 2

    assert duet_bar_mapping(0, piece=halves) == (0, 0)
    assert duet_bar_mapping(2, piece=halves) == (1, 0)
    assert duet_bar_mapping(0) == (1, 0)
    assert duet_raw_bar_index(0, 1, piece=halves) == 1
    assert duet_raw_bar_index(1, 1, piece=halves) == 3
    assert duet_raw_bar_index(0, 1) == 3

    triplets = {(0, 1, 2): "top", (2, 3, 4): "bottom"}
    pairs = {(0, 1): "top", (2, 3): "bottom"}
    assert split_duet_triplet_map(triplets, staff_index=0, piece=halves) == {(0, 1, 2): "top"}
    assert split_duet_pair_map(pairs, staff_index=1, piece=halves) == {(0, 3): "bottom"}
    assert split_duet_triplet_set(set(triplets), staff_index=1, piece=halves) == {(0, 3, 4)}
    assert split_duet_pair_set(set(pairs), staff_index=0, piece=halves) == {(0, 1)}
    assert split_duet_span_list([(0, 1, 2), (2, 3, 4)], staff_index=0, piece=halves) == [(0, 1, 2)]

    halves.bars[0].time_sig = "3/4"
    bottom = split_duet_piece_staff(halves, 1)
    assert len(bottom.bars) == 2
    assert bottom.bars[0].time_sig == "3/4"
    assert duet_view_mode({"duetscoreview": "both"}) == "both"
    assert duet_view_mode({"duetscoreview": "invalid"}) == "auto"


def test_terminal_width_planning_handles_meter_and_compression_boundaries() -> None:
    assert _time_signature_for_duration(Fraction(), max_denom=4) is None
    assert _time_signature_for_duration(Fraction(3, 8), max_denom=8) == "3/4"
    assert _time_signature_for_duration(Fraction(1, 3), max_denom=3) is None
    assert _infer_time_signature(Bar()) is None
    assert _infer_time_signature(Bar(chords=[Chord(4, True, None)])) == "3/4"
    assert _infer_time_signature(Bar(chords=[Chord(99, False, None)])) == "1/4"
    assert _parse_pitch_labels(" /g2-c#3", show_octaves=True) == ["g2", "c#3"]

    assert _scale_col(4, 5, 1) == 0
    assert _scale_col(0, 1, 5) == 0
    assert _nearest_free_column(["-", "x", "-"], 0, "-") == 0
    assert _nearest_free_column(["x", "x", "-"], 1, "-") == 2
    assert _nearest_free_column(["-", "x", "x"], 1, "-") == 0
    assert _nearest_free_column(["x", "x"], 0, "-") is None
    assert _scale_row(["a"], 0, "-") == []
    assert _scale_row([], 3, "-") == ["-", "-", "-"]
