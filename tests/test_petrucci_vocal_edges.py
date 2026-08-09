from __future__ import annotations

from petrucci.model import Bar, Chord, ImportedTextRow, LyricEvent, MelodyEvent, Note
from petrucci.render_vocal import (
    _bar_lyric_rows,
    _dedup_lyric_rows,
    _grid_lyric_events,
    _grid_melody_events,
    _is_strong_lyric_token,
    _lyric_row_verse,
    _primary_lyric_events,
    _scaled_onset_cols_from_events,
    _scaled_onset_cols_from_lyrics,
    _spread_onset_cols,
    lyric_rows_for_bar,
    melody_rows_for_bar,
    vocal_onset_cols_for_bar,
)
from petrucci.vocal_line import chord_top_pitch, infer_vocal_events, lyric_anchor_onsets, token_pitch_value


def test_vocal_token_and_chord_pitch_fallbacks_are_explicit() -> None:
    assert token_pitch_value("") is None
    assert token_pitch_value("xyz") is None
    assert token_pitch_value("c#'") == 73
    assert token_pitch_value("db,") == 49
    assert chord_top_pitch(Chord(4, False, None), [60]) is None
    assert chord_top_pitch(Chord(4, False, None, [Note(3, 2, 0)]), [60]) is None
    assert chord_top_pitch(Chord(4, False, None, [Note(1, 2, 0), Note(2, 5, 0)]), [60, 55]) == 62


def test_vocal_event_inference_preserves_explicit_rest_and_expression() -> None:
    explicit = Bar(
        chords=[Chord(4, False, None, [Note(1, 0, 0)])],
        melody_events=[
            MelodyEvent(
                "r",
                0,
                note_type=8,
                dotted=True,
                is_rest=True,
                beam="start",
                fermata=True,
                voice=2,
                ornament="trill",
                courtesy_accidental=True,
                editorial_brackets=True,
                tie_from_previous=True,
            )
        ],
    )
    rest = infer_vocal_events(explicit, tuning_pitches=[60])[0]
    assert rest.is_rest and rest.pitch is None
    assert (rest.note_type, rest.dotted, rest.beam, rest.voice) == (8, True, "start", 2)
    assert rest.fermata and rest.courtesy_accidental and rest.editorial_brackets and rest.tie_from_previous

    fallback = infer_vocal_events(
        Bar(chords=[Chord(4, False, None, [Note(1, 3, 0)]), Chord(8, True, None)]),
        tuning_pitches=[60],
    )
    assert [(event.pitch, event.note_type) for event in fallback] == [(63, 4)]


def test_lyric_anchor_onsets_ignore_empty_and_duplicate_tokens() -> None:
    bar = Bar(
        lyric_event_rows=[
            [LyricEvent("", 0), LyricEvent("la", 2)],
            [LyricEvent("again", 2), LyricEvent("do", 1)],
        ]
    )
    assert lyric_anchor_onsets(bar) == [1, 2]


def test_vocal_grid_and_lyric_selection_microcases() -> None:
    assert _grid_melody_events(None) == []
    melody = _grid_melody_events("c4   d4")
    assert [(event.text, event.src_pos) for event in melody] == [("c4", 0), ("d4", 5)]
    assert _grid_lyric_events(None) == []
    lyrics = _grid_lyric_events("Fe li")
    assert [(event.text, event.src_pos) for event in lyrics] == [("Fe", 0), ("li", 3)]

    assert _scaled_onset_cols_from_lyrics([], event_count=0, width=8, left_pad=1) == []
    assert _scaled_onset_cols_from_lyrics([[LyricEvent("x", 0, src_pos=-1)]], event_count=1, width=8, left_pad=1) == []
    scaled = _scaled_onset_cols_from_lyrics(
        [[LyricEvent("one", 0, src_pos=0), LyricEvent("three", 2, src_pos=8)]],
        event_count=3,
        width=12,
        left_pad=2,
    )
    assert scaled == sorted(scaled) and len(scaled) == 3

    assert not _is_strong_lyric_token(LyricEvent("", 0))
    assert _is_strong_lyric_token(LyricEvent("la", 0))
    assert _is_strong_lyric_token(LyricEvent("i", 0))
    selected = _primary_lyric_events([[LyricEvent("!", 0), LyricEvent("word", 0)], [LyricEvent("", 1, extender=True)]])
    assert [event.text for event in selected] == ["word", ""]
    assert _dedup_lyric_rows([lyrics, lyrics, [LyricEvent("", 0)]]) == [lyrics]
    assert _lyric_row_verse([]) == 0


def test_vocal_rows_cover_raw_fallback_padding_and_structured_events() -> None:
    raw = Bar(
        lyrics=["first verse"],
        structured_text_rows=[ImportedTextRow(0, "vocal", "1 voice")],
    )
    raw_rows = lyric_rows_for_bar(raw, onset_cols=[], width=12, left_pad=2, lyric_rows_count=2)
    assert "first" in "".join(raw_rows[0])
    assert "".join(raw_rows[1]).strip() == ""

    structured = Bar(
        lyric_event_rows=[
            [LyricEvent("alto", 0, verse=1), LyricEvent("line", 1, verse=1)],
            [LyricEvent("sop", 0, verse=0), LyricEvent("line", 1, verse=0)],
        ]
    )
    rows = lyric_rows_for_bar(structured, onset_cols=[2, 8], width=14, left_pad=1, lyric_rows_count=1)
    assert len(rows) == 2
    assert "sop" in "".join(rows[0])
    assert _bar_lyric_rows(Bar(lyrics=["la la"]))


def test_vocal_onset_projection_prefers_source_positions_then_spreads() -> None:
    assert _scaled_onset_cols_from_events([], event_count=1, width=8, left_pad=1) == []
    events = [MelodyEvent("c", 0, src_pos=0), MelodyEvent("d", 1, src_pos=9)]
    scaled = _scaled_onset_cols_from_events(events, event_count=2, width=12, left_pad=2)
    assert scaled == sorted(scaled)
    assert _spread_onset_cols(event_count=0, width=8, left_pad=1) == []
    assert _spread_onset_cols(event_count=3, width=10, left_pad=1) == [1, 5, 9]

    assert vocal_onset_cols_for_bar(Bar(), onset_cols=[], width=10, left_pad=1) == []
    assert vocal_onset_cols_for_bar(Bar(), onset_cols=[1, 4], width=10, left_pad=1) == [1, 4]
    sourced = Bar(melody_events=events)
    assert len(vocal_onset_cols_for_bar(sourced, onset_cols=[1], width=12, left_pad=2)) == 2
    lyric_only = Bar(lyric_event_rows=[[LyricEvent("a", 0, src_pos=0), LyricEvent("b", 1, src_pos=8)]])
    assert len(vocal_onset_cols_for_bar(lyric_only, onset_cols=[1], width=12, left_pad=2)) == 2
    chord_only = Bar(chords=[Chord(4, False, None), Chord(4, False, None)])
    assert vocal_onset_cols_for_bar(chord_only, onset_cols=[1], width=8, left_pad=1) == [1, 7]

    rendered = melody_rows_for_bar(
        Bar(melody_grid="c4 d4"),
        onset_cols=[2, 8],
        width=14,
        left_pad=1,
        tuning_pitches=None,
    )
    assert rendered and all(len(row) == 14 for row in rendered)
