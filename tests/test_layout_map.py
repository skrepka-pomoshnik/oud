from oud.ui.layout_map import block_height, layout_block_rows


def test_layout_block_rows_show_extras_reserves_single_span_row() -> None:
    rows = layout_block_rows(
        strings=6,
        include_meta=True,
        show_dur=True,
        show_extras=True,
        show_tactus=True,
        double_stems=False,
    )
    # Local marks are inline now; no dedicated ann/orn rows.
    assert rows["ann"] is None
    assert rows["orn"] is None
    # Span cues still share a single row.
    assert rows["slur"] is not None
    assert rows["slur"] == rows["tie"] == rows["hold"] == rows["gliss"]


def test_block_height_with_extras_is_reduced_for_inline_local_marks() -> None:
    with_extras = block_height(
        include_meta=True,
        strings=6,
        show_dur=False,
        show_extras=True,
        show_tactus=False,
        double_stems=False,
    )
    without_extras = block_height(
        include_meta=True,
        strings=6,
        show_dur=False,
        show_extras=False,
        show_tactus=False,
        double_stems=False,
    )
    # Only one extra span row is reserved now.
    assert with_extras == without_extras + 1
