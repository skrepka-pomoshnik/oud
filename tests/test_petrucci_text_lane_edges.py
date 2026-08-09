from __future__ import annotations

from petrucci.core.model import Bar, Chord, ImportedTextRow, LyricEvent, MelodyEvent, Note
from petrucci.rendering.staff.text import (
    _bar_uses_raw_vocal_fallback,
    _draw_editorial_brackets,
    _draw_vocal_accidental,
    _draw_vocal_beams,
    _draw_vocal_ledger,
    _draw_vocal_ornament,
    _draw_vocal_stem,
    _event_accidental,
    _event_accidental_map,
    _event_accidental_map_for_bar,
    _event_pitch_map,
    _event_region,
    _event_target_col,
    _fallback_vocal_events,
    _fill_unpitched_event_rows,
    _merge_chord_pitch_map,
    _place_text_in_region,
    _place_text_near,
    _resampled_onset_cols,
    draw_melody_key_signature,
    draw_melody_time_signature,
    lyric_event_cells,
    melody_event_cells,
    melody_key_signature_width,
    melody_staff_rows,
    text_bar_cells,
    tokenized_onset_cells,
    visible_lyric_rows,
)


def test_text_lane_tokens_clip_and_resolve_collisions_by_region() -> None:
    assert visible_lyric_rows(None) == []
    assert visible_lyric_rows(["ignored"], max_rows=0) == []
    assert visible_lyric_rows(["", "  first  ", "second", "third"], max_rows=2) == ["  first", "second"]
    assert text_bar_cells("text", 0) == []
    assert text_bar_cells(None, 4) == [" "] * 4
    assert text_bar_cells(" \t ", 4) == [" "] * 4
    assert "ab" in "".join(text_bar_cells("a\t\t ab", 6))

    assert tokenized_onset_cells("la", onset_cols=[], width=4) == [" "] * 4
    assert tokenized_onset_cells("   ", onset_cols=[0], width=4) == [" "] * 4
    token_cells = tokenized_onset_cells("one two three", onset_cols=[1, 6], width=10, left_pad=1)
    assert "one" in "".join(token_cells)
    assert _event_target_col([], 0) is None
    assert _event_target_col([2, 6], 0) == 2
    assert _event_target_col([2, 6], 9) == 6
    assert _event_region([], 0, width=4, floor=0) is None
    assert _event_region([2, 6], 0, width=10, floor=1) == (2, 5)
    assert _event_region([2, 6], 9, width=10, floor=1) == (6, 9)

    cells = [" "] * 5
    assert _place_text_in_region(cells, "", start=0, end=4, after=-1) is None
    assert _place_text_in_region(cells, "x", start=0, end=0, after=0) is None
    assert _place_text_in_region(cells, "long", start=1, end=2, after=-1) == (1, 2)
    assert "".join(cells) == " lo  "

    assert _place_text_near([], "x", 0) is None
    near = [" "] * 5
    assert _place_text_near(near, "ab", 2) == (2, 3)
    shifted_left = [" ", " ", "x", "x"]
    assert _place_text_near(shifted_left, "a", 2) == (1, 1)
    occupied = ["x"] * 4
    assert _place_text_near(occupied, "ab", 1) == (1, 2)
    assert occupied == ["x"] * 4


def test_melody_text_pitch_and_accidental_maps_preserve_source_cues() -> None:
    events = [
        MelodyEvent("c#4", 0),
        MelodyEvent("duplicate", 0),
        MelodyEvent("r", 1, is_rest=True, accidental_flags=0x0002),
        MelodyEvent("db4", 2, courtesy_accidental=True),
        MelodyEvent("c4", 3, accidental_flags=0x2000),
    ]
    pitch_map = _event_pitch_map(events)
    assert 0 in pitch_map and 2 in pitch_map
    assert _event_accidental(events[0]) == "#"
    assert _event_accidental(events[2]) == "#"
    assert _event_accidental(events[3]) == "(b)"
    assert _event_accidental(MelodyEvent("c4", 0)) is None
    assert _event_accidental_map(events) == {0: "#", 2: "(b)", 3: "n"}

    raw_bar = Bar(structured_text_rows=[ImportedTextRow(0, "vocal", "1 source")])
    assert not _bar_uses_raw_vocal_fallback(None)
    assert _bar_uses_raw_vocal_fallback(raw_bar)
    assert _event_accidental_map_for_bar(events, bar=raw_bar) == {0: "#", 2: "(b)"}

    pitches: dict[int, int] = {}
    _merge_chord_pitch_map(pitches, None, [60])
    _merge_chord_pitch_map(pitches, [Chord(4, False, None, [Note(1, 2, 0)])], [60])
    assert pitches == {0: 62}
    _fill_unpitched_event_rows(pitches, [MelodyEvent("text", 1), MelodyEvent("", 2)])
    assert pitches == {0: 62, 1: 64}
    fallback = _fallback_vocal_events([MelodyEvent("text", 1)], None, None)
    assert [(event.onset_index, event.pitch) for event in fallback] == [(1, 64)]

    event_cells = melody_event_cells(events, onset_cols=[1, 4, 7, 9], width=12, left_pad=1)
    assert "c#4" in "".join(event_cells)


def test_vocal_onset_resampling_handles_empty_dense_and_sparse_inputs() -> None:
    assert _resampled_onset_cols(onset_cols=[], event_count=0, width=8, left_pad=1) == []
    assert _resampled_onset_cols(onset_cols=[1, 4], event_count=2, width=8, left_pad=1) == [1, 4]
    assert _resampled_onset_cols(onset_cols=[1], event_count=3, width=8, left_pad=1) == [1, 4, 7]
    assert _resampled_onset_cols(onset_cols=[1, 3, 5], event_count=1, width=8, left_pad=1) == [1]
    assert _resampled_onset_cols(onset_cols=[1, 3, 5, 7], event_count=3, width=8, left_pad=1) == [1, 4, 7]


def test_vocal_staff_draws_rests_beams_accidentals_ledgers_and_marks() -> None:
    events = [
        MelodyEvent(
            "c#''",
            0,
            note_type=8,
            beam="start",
            ornament="t",
            courtesy_accidental=True,
            editorial_brackets=True,
        ),
        MelodyEvent("d''", 1, note_type=8, beam="continue"),
        MelodyEvent("e''", 2, note_type=8, beam="end", dotted=True),
        MelodyEvent("r", 3, note_type=4, is_rest=True),
        MelodyEvent("c,,", 4, note_type=2),
    ]
    bar = Bar(melody_events=events)
    rows = melody_staff_rows(events, onset_cols=[4, 9, 14, 19, 23], width=28, left_pad=2, bar=bar)
    text = "\n".join("".join(row) for row in rows)
    assert "r" in text and "=" in text and "#[" in text and "-◊-" in text

    scratch = [[" "] * 8 for _ in range(6)]
    _draw_vocal_stem([], row=0, col=0, note_type=8, dotted=True)
    _draw_vocal_stem(scratch, row=-1, col=1, note_type=8, dotted=True)
    _draw_vocal_stem(scratch, row=3, col=6, note_type=1, dotted=True)
    _draw_vocal_stem(scratch, row=4, col=6, note_type=8, dotted=True)
    _draw_vocal_beams(scratch, [("continue", 4, 1), ("invalid", 4, 2), ("start", 4, 1), ("end", 4, 5)])
    assert "=" in "".join(scratch[1])

    _draw_vocal_ledger([], raw_row=0, row=0, col=0)
    _draw_vocal_ledger(scratch, raw_row=3, row=3, col=3)
    _draw_vocal_ledger(scratch, raw_row=-2, row=3, col=3)
    _draw_vocal_accidental(scratch, row=3, col=3, accidental="", floor=0)
    _draw_vocal_accidental(scratch, row=3, col=3, accidental="(#)", floor=0)
    _draw_editorial_brackets([], row=0, col=0, floor=0)
    _draw_editorial_brackets(scratch, row=3, col=3, floor=0)
    _draw_vocal_ornament(scratch, row=4, col=7, ornament=None)
    _draw_vocal_ornament(scratch, row=4, col=7, ornament="trill")
    assert any(mark in "".join(scratch[3]) for mark in ("#", "[", "]", "-"))


def test_melody_state_and_lyric_links_fit_inside_the_terminal_lane() -> None:
    rows = [[" "] * 12 for _ in range(11)]
    draw_melody_time_signature([], time_sig="3/4", left_pad=4)
    draw_melody_time_signature(rows, time_sig=None, left_pad=4)
    draw_melody_time_signature(rows, time_sig="bad", left_pad=4)
    draw_melody_time_signature(rows, time_sig="12/8", left_pad=4)
    assert any("12" in "".join(row) for row in rows)

    assert melody_key_signature_width(None) == 0
    assert melody_key_signature_width("C") == 0
    assert melody_key_signature_width("G") == 2
    draw_melody_key_signature([], key="G", left_pad=2)
    draw_melody_key_signature(rows, key="G", left_pad=2)
    draw_melody_key_signature(rows, key="F", left_pad=4)
    assert "#" in "\n".join("".join(row) for row in rows)
    assert "b" in "\n".join("".join(row) for row in rows)

    lyrics = lyric_event_cells(
        [
            LyricEvent("Fe", 0, syllabic="begin"),
            LyricEvent("li", 1, extender=True),
            LyricEvent("", 2, extender=True),
            LyricEvent("ce", 3),
            LyricEvent("overflow", 99),
        ],
        onset_cols=[1, 7, 13, 18],
        width=24,
        left_pad=1,
    )
    lyric_text = "".join(lyrics)
    assert "Fe" in lyric_text and "-" in lyric_text and "_" in lyric_text
