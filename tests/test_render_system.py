from __future__ import annotations

from oud.ui.render_system import _build_chord_scale_map, _scale_chord_row


def test_build_chord_scale_map_keeps_ordered_columns() -> None:
    positions = [(0, 4, True), (2, 16, False), (3, 16, False), (5, 8, False)]
    scaled, mapping = _build_chord_scale_map(positions, bar_width=8, content_width=10)
    assert len(scaled) == len(positions)
    assert mapping[0] < mapping[2] < mapping[3] < mapping[5]


def test_build_chord_scale_map_separates_duration_groups() -> None:
    positions = [(0, 4, True), (2, 16, False), (3, 16, False), (5, 8, False)]
    _scaled, mapping = _build_chord_scale_map(positions, bar_width=8, content_width=10)
    assert mapping[3] - mapping[2] >= 1
    assert mapping[5] - mapping[3] >= 2


def test_scale_chord_row_aligns_notes_to_shared_columns() -> None:
    positions = [(0, 4, True), (2, 16, False), (3, 16, False), (5, 8, False)]
    _scaled, mapping = _build_chord_scale_map(positions, bar_width=8, content_width=10)

    row_a = list("--e-f-e-")
    row_b = list("--a-b---")
    scaled_a = _scale_chord_row(
        row_a,
        fill_char="-",
        src_to_dest=mapping,
        bar_width=8,
        content_width=10,
    )
    scaled_b = _scale_chord_row(
        row_b,
        fill_char="-",
        src_to_dest=mapping,
        bar_width=8,
        content_width=10,
    )
    assert scaled_a[mapping[2]] == "e"
    assert scaled_b[mapping[2]] == "a"
    assert scaled_a[mapping[3]] == "f"
    assert scaled_b[mapping[3]] == "b"
