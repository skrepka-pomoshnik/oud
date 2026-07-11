from oud.petrucci.layout_map import block_height, layout_block_rows


def test_layout_block_rows_show_extras_reserves_single_span_row() -> None:
    rows = layout_block_rows(
        strings=6,
        include_meta=True,
        show_dur=True,
        show_extras=True,
        show_tuplets=False,
        show_tactus=True,
        double_stems=False,
    )
    # Local marks are inline now; no dedicated ann/orn rows.
    assert rows["ann"] is None
    assert rows["orn"] is None
    # Span cues still share a single row.
    assert rows["slur"] is not None
    assert rows["slur"] == rows["tie"] == rows["hold"] == rows["gliss"]
    assert rows["tuplet"] is None


def test_block_height_with_extras_is_reduced_for_inline_local_marks() -> None:
    with_extras = block_height(
        include_meta=True,
        strings=6,
        show_dur=False,
        show_extras=True,
        show_tuplets=False,
        show_tactus=False,
        double_stems=False,
    )
    without_extras = block_height(
        include_meta=True,
        strings=6,
        show_dur=False,
        show_extras=False,
        show_tuplets=False,
        show_tactus=False,
        double_stems=False,
    )
    # Only one extra span row is reserved now.
    assert with_extras == without_extras + 1


def test_layout_block_rows_show_tuplets_reserves_shared_cue_row() -> None:
    rows = layout_block_rows(
        strings=6,
        include_meta=True,
        show_dur=False,
        show_extras=False,
        show_tuplets=True,
        show_tactus=False,
        double_stems=False,
    )
    assert rows["tuplet"] is not None
    assert rows["slur"] is None


def test_block_height_with_tuplets_reserves_one_row() -> None:
    with_tuplets = block_height(
        include_meta=True,
        strings=6,
        show_dur=False,
        show_extras=False,
        show_tuplets=True,
        show_tactus=False,
        double_stems=False,
    )
    without_tuplets = block_height(
        include_meta=True,
        strings=6,
        show_dur=False,
        show_extras=False,
        show_tuplets=False,
        show_tactus=False,
        double_stems=False,
    )
    assert with_tuplets == without_tuplets + 1


def test_layout_block_rows_vocal_top_places_melody_before_flags() -> None:
    rows = layout_block_rows(
        strings=6,
        include_meta=True,
        show_dur=True,
        show_extras=False,
        show_tuplets=False,
        show_tactus=False,
        double_stems=False,
        show_melody=True,
        melody_rows_count=5,
        show_lyrics=True,
        lyric_rows_count=1,
        vocal_pos="top",
    )
    assert rows["melody"] is not None and rows["flag"] is not None
    assert rows["melody"] < rows["flag"]
    assert rows["lyric"] is not None and rows["lyric"] < rows["flag"]


def test_layout_block_rows_vocal_bottom_places_melody_after_staff() -> None:
    rows = layout_block_rows(
        strings=6,
        include_meta=True,
        show_dur=True,
        show_extras=False,
        show_tuplets=False,
        show_tactus=False,
        double_stems=False,
        show_melody=True,
        melody_rows_count=5,
        show_lyrics=True,
        lyric_rows_count=1,
        vocal_pos="bottom",
    )
    assert rows["melody"] is not None and rows["staff"] is not None
    assert rows["melody"] == rows["staff"] + 6


def test_block_height_expands_with_melody_note_staff_rows() -> None:
    text_height = block_height(
        include_meta=True,
        strings=6,
        show_dur=False,
        show_extras=False,
        show_tuplets=False,
        show_tactus=False,
        double_stems=False,
        show_melody=True,
        melody_rows_count=1,
        show_lyrics=False,
    )
    notes_height = block_height(
        include_meta=True,
        strings=6,
        show_dur=False,
        show_extras=False,
        show_tuplets=False,
        show_tactus=False,
        double_stems=False,
        show_melody=True,
        melody_rows_count=5,
        show_lyrics=False,
    )
    assert notes_height == text_height + 4
