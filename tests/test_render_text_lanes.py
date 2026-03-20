from oud.core.model import Bar, Chord, ImportedTextRow, LyricEvent, MelodyEvent, Note
from oud.ui.render_text_lanes import (
    MELODY_FILLED_NOTEHEAD_GLYPH,
    MELODY_NOTEHEAD_GLYPH,
    draw_melody_key_signature,
    draw_melody_time_signature,
    lyric_event_cells,
    melody_event_cells,
    melody_row_count,
    melody_staff_rows,
    text_bar_cells,
    tokenized_onset_cells,
    visible_lyric_rows,
)


def test_text_bar_cells_preserves_relative_token_spacing() -> None:
    cells = text_bar_cells("a     b", 10)
    text = "".join(cells)
    assert "a" in text and "b" in text
    assert text.index("b") - text.index("a") >= 2


def test_visible_lyric_rows_caps_and_skips_empty() -> None:
    rows = visible_lyric_rows(["", "Can", " ", "Was she", "I"], max_rows=2)
    assert rows == ["Can", "Was she"]


def test_melody_event_cells_aligns_tokens_to_onsets() -> None:
    cells = melody_event_cells(
        [
            MelodyEvent("3", 0),
            MelodyEvent("8", 1),
            MelodyEvent("a", 2),
        ],
        onset_cols=[1, 6, 11],
        width=16,
        left_pad=1,
    )
    text = "".join(cells)
    assert text.index("3") >= 1
    assert text.index("8") > text.index("3")
    assert text.index("a") > text.index("8")


def test_lyric_event_cells_renders_dash_between_syllables() -> None:
    cells = lyric_event_cells(
        [
            LyricEvent("ex", 0, syllabic="begin"),
            LyricEvent("cuse", 1, syllabic="end"),
        ],
        onset_cols=[2, 12],
        width=20,
        left_pad=1,
    )
    text = "".join(cells)
    assert "ex" in text and "cuse" in text
    dash_idx = text.index("-")
    assert text.index("ex") < dash_idx < text.index("cuse")


def test_lyric_event_cells_renders_extender_across_gap() -> None:
    cells = lyric_event_cells(
        [
            LyricEvent("A", 0, verse=0, syllabic="single"),
            LyricEvent("", 1, verse=0, extender=True),
            LyricEvent("men", 2, verse=0, syllabic="single"),
        ],
        onset_cols=[2, 8, 14],
        width=20,
        left_pad=1,
    )
    text = "".join(cells)
    assert "A" in text and "men" in text
    assert "___" in text


def test_lyric_event_cells_respects_left_pad_for_time_cue_lane() -> None:
    cells = lyric_event_cells(
        [LyricEvent("Can", 0)],
        onset_cols=[0],
        width=10,
        left_pad=2,
    )
    text = "".join(cells)
    assert text.index("C") >= 2


def test_melody_event_cells_clips_long_token_to_own_onset_segment() -> None:
    cells = melody_event_cells(
        [
            MelodyEvent("abcdef", 0),
            MelodyEvent("Z", 1),
        ],
        onset_cols=[1, 6],
        width=12,
        left_pad=1,
    )
    text = "".join(cells)
    # First token is clipped to [1..5], second token remains onset-aligned at 6.
    assert text[1:6] == "abcde"
    assert text[6] == "Z"


def test_lyric_event_cells_keeps_next_syllable_on_its_onset_after_long_text() -> None:
    cells = lyric_event_cells(
        [
            LyricEvent("longsyll", 0, syllabic="begin"),
            LyricEvent("me", 1, syllabic="end"),
        ],
        onset_cols=[2, 10],
        width=20,
        left_pad=1,
    )
    text = "".join(cells)
    assert text[2:10] == "longsyll"
    assert "me" in text
    assert text.find("me") >= 10


def test_lyric_event_cells_shifts_next_token_right_when_anchor_overlaps() -> None:
    cells = lyric_event_cells(
        [
            LyricEvent("veryverylong", 0, syllabic="begin"),
            LyricEvent("me", 1, syllabic="end"),
        ],
        onset_cols=[2, 8],
        width=20,
        left_pad=1,
    )
    text = "".join(cells)
    assert "me" in text
    assert text.find("me") >= 8


def test_tokenized_onset_cells_aligns_raw_tokens_to_onset_columns() -> None:
    cells = tokenized_onset_cells(
        "Can she excuse",
        onset_cols=[2, 8, 14],
        width=20,
        left_pad=1,
    )
    text = "".join(cells)
    assert text[2:5] == "Can"
    assert text[8:11] == "she"
    assert text[14:20].startswith("excuse")


def test_melody_staff_rows_uses_chord_pitches_when_tokens_are_non_pitch() -> None:
    rows = melody_staff_rows(
        [MelodyEvent("3", 0), MelodyEvent("8", 1)],
        onset_cols=[2, 8],
        width=12,
        left_pad=1,
        bar_chords=[
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(6, 0, 0)]),
        ],
        tuning_pitches=[67, 62, 57, 53, 48, 43],
    )
    assert len(rows) == melody_row_count()
    text_rows = ["".join(row) for row in rows]
    assert any(line[2] == MELODY_FILLED_NOTEHEAD_GLYPH for line in text_rows)
    assert any(line[8] == MELODY_FILLED_NOTEHEAD_GLYPH for line in text_rows)
    assert sum(1 for line in text_rows if "-" in line) >= 5


def test_melody_staff_rows_inferred_vocal_notes_cover_all_chord_onsets() -> None:
    bar = Bar(
        chords=[
            Chord(note_type=5, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
            Chord(note_type=6, dotted=False, grid=None, notes=[Note(2, 1, 0)]),
            Chord(note_type=6, dotted=False, grid=None, notes=[Note(3, 2, 0)]),
            Chord(note_type=6, dotted=False, grid=None, notes=[Note(4, 3, 0)]),
        ],
        lyric_event_rows=[[LyricEvent("Can", 0), LyricEvent("she", 1), LyricEvent("ex", 2)]],
    )
    rows = melody_staff_rows(
        [],
        onset_cols=[2, 8, 14],
        width=20,
        left_pad=1,
        bar=bar,
        bar_chords=bar.chords,
        tuning_pitches=[67, 62, 57, 53, 48, 43],
    )
    text_rows = ["".join(row) for row in rows]
    assert sum(line.count(MELODY_FILLED_NOTEHEAD_GLYPH) for line in text_rows) == 4
    assert any("|" in line for line in text_rows)
    assert any("\\" in line for line in text_rows)
    assert sum(1 for line in text_rows if any(glyph in line for glyph in ("|", "\\", "."))) >= 2


def test_melody_staff_rows_does_not_clip_inferred_notes_to_lyric_count() -> None:
    bar = Bar(
        chords=[
            Chord(note_type=5, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
            Chord(note_type=6, dotted=False, grid=None, notes=[Note(2, 1, 0)]),
            Chord(note_type=6, dotted=False, grid=None, notes=[Note(3, 2, 0)]),
            Chord(note_type=6, dotted=False, grid=None, notes=[Note(4, 3, 0)]),
            Chord(note_type=6, dotted=False, grid=None, notes=[Note(5, 0, 0)]),
        ],
        lyric_event_rows=[[LyricEvent("Can", 0), LyricEvent("she", 1), LyricEvent("ex", 2)]],
    )
    rows = melody_staff_rows(
        [],
        onset_cols=[1, 2, 3, 12, 18],
        width=24,
        left_pad=1,
        bar=bar,
        bar_chords=bar.chords,
        tuning_pitches=[67, 62, 57, 53, 48, 43],
    )
    text_rows = ["".join(row) for row in rows]
    assert sum(line.count(MELODY_FILLED_NOTEHEAD_GLYPH) for line in text_rows) == 5
    assert any(line[18] == MELODY_FILLED_NOTEHEAD_GLYPH for line in text_rows)


def test_melody_staff_rows_use_fixed_treble_positions_for_d_a_d_prime() -> None:
    rows = melody_staff_rows(
        [MelodyEvent("d", 0), MelodyEvent("a", 1), MelodyEvent("d'", 2)],
        onset_cols=[2, 8, 14],
        width=20,
        left_pad=1,
    )
    text_rows = ["".join(row) for row in rows]
    note_rows = {
        2: next(idx for idx, line in enumerate(text_rows) if line[2] == MELODY_FILLED_NOTEHEAD_GLYPH),
        8: next(idx for idx, line in enumerate(text_rows) if line[8] == MELODY_FILLED_NOTEHEAD_GLYPH),
        14: next(idx for idx, line in enumerate(text_rows) if line[14] == MELODY_FILLED_NOTEHEAD_GLYPH),
    }
    assert note_rows[14] < note_rows[8] < note_rows[2]
    assert sum(1 for line in text_rows if "-" in line) >= 5


def test_melody_staff_rows_keeps_explicit_onsets_in_tab_columns() -> None:
    rows = melody_staff_rows(
        [MelodyEvent("d", 0), MelodyEvent("a", 1), MelodyEvent("d'", 2)],
        onset_cols=[2, 8, 14, 19, 23],
        width=26,
        left_pad=1,
    )
    text_rows = ["".join(row) for row in rows]
    assert any(line[2] == MELODY_FILLED_NOTEHEAD_GLYPH for line in text_rows)
    assert any(line[8] == MELODY_FILLED_NOTEHEAD_GLYPH for line in text_rows)
    assert any(line[14] == MELODY_FILLED_NOTEHEAD_GLYPH for line in text_rows)
    assert all(line[19] != MELODY_FILLED_NOTEHEAD_GLYPH for line in text_rows)
    assert all(line[23] != MELODY_FILLED_NOTEHEAD_GLYPH for line in text_rows)


def test_melody_staff_rows_clamps_left_pad_when_bar_is_narrow() -> None:
    rows = melody_staff_rows(
        [MelodyEvent("g", 0, note_type=4)],
        onset_cols=[9],
        width=4,
        left_pad=9,
    )
    text_rows = ["".join(row) for row in rows]
    assert any(line[-1] == MELODY_FILLED_NOTEHEAD_GLYPH for line in text_rows)


def test_melody_staff_rows_draws_ledger_cue_for_note_below_visible_staff() -> None:
    rows = melody_staff_rows(
        [MelodyEvent("c", 0)],
        onset_cols=[4],
        width=12,
        left_pad=1,
    )
    text_rows = ["".join(row) for row in rows]
    note_row = next(idx for idx, line in enumerate(text_rows) if line[4] == MELODY_FILLED_NOTEHEAD_GLYPH)
    assert text_rows[note_row][3] == "-"
    assert text_rows[note_row][5] == "-"


def test_melody_staff_rows_draws_accidental_next_to_notehead() -> None:
    rows = melody_staff_rows(
        [MelodyEvent("bb", 0, accidental_flags=0x1000)],
        onset_cols=[4],
        width=12,
        left_pad=1,
    )
    text_rows = ["".join(row) for row in rows]
    note_row = next(idx for idx, line in enumerate(text_rows) if line[4] == MELODY_FILLED_NOTEHEAD_GLYPH)
    assert text_rows[note_row][3] == "b"


def test_draw_melody_time_signature_places_numerator_only_left_of_first_stem() -> None:
    rows = melody_staff_rows(
        [MelodyEvent("d", 0)],
        onset_cols=[6],
        width=16,
        left_pad=1,
    )
    draw_melody_time_signature(rows, time_sig="3/4", left_pad=1)
    text_rows = ["".join(row) for row in rows]
    meter_rows = [idx for idx, line in enumerate(text_rows) if line[0] == "3"]
    assert len(meter_rows) == 1
    assert all("4" not in line for line in text_rows)
    assert all(line[6] != "3" for line in text_rows)


def test_draw_melody_time_signature_can_leave_a_gap_before_first_onset() -> None:
    rows = melody_staff_rows(
        [MelodyEvent("d", 0)],
        onset_cols=[3],
        width=12,
        left_pad=3,
    )
    draw_melody_time_signature(rows, time_sig="3/4", left_pad=3)
    text_rows = ["".join(row) for row in rows]
    meter_row = next(idx for idx, line in enumerate(text_rows) if "3" in line)
    assert text_rows[meter_row][0] == "3"
    assert text_rows[meter_row][1] != "3"


def test_draw_melody_key_signature_adds_sharp_for_g_major() -> None:
    rows = melody_staff_rows(
        [MelodyEvent("d", 0)],
        onset_cols=[6],
        width=16,
        left_pad=6,
    )
    draw_melody_key_signature(rows, key="GM", left_pad=4)
    text_rows = ["".join(row) for row in rows]
    assert any("#" in line[:6] for line in text_rows)


def test_melody_staff_rows_draw_full_stems_by_default() -> None:
    rows = melody_staff_rows(
        [MelodyEvent("d", 0)],
        onset_cols=[4],
        width=12,
        left_pad=1,
    )
    text_rows = ["".join(row) for row in rows]
    stem_rows = [row for row in range(len(text_rows)) if text_rows[row][4] == "|"]
    assert len(stem_rows) == 3
    assert stem_rows == list(range(stem_rows[0], stem_rows[0] + 3))


def test_melody_staff_rows_use_consistent_stem_length_for_different_pitches() -> None:
    rows = melody_staff_rows(
        [MelodyEvent("d", 0), MelodyEvent("a", 1), MelodyEvent("d'", 2)],
        onset_cols=[4, 10, 16],
        width=24,
        left_pad=1,
    )
    text_rows = ["".join(row) for row in rows]
    stem_lengths: list[int] = []
    for col in (4, 10, 16):
        note_row = next(
            idx
            for idx, line in enumerate(text_rows)
            if line[col] in (MELODY_NOTEHEAD_GLYPH, MELODY_FILLED_NOTEHEAD_GLYPH)
        )
        stem_rows = [idx for idx, line in enumerate(text_rows[:note_row]) if line[col] == "|"]
        stem_lengths.append(len(stem_rows))
    assert stem_lengths == [3, 3, 3]


def test_melody_staff_rows_uses_hollow_heads_for_long_notes_and_filled_for_short() -> None:
    rows = melody_staff_rows(
        [],
        onset_cols=[3, 9, 15],
        width=20,
        left_pad=1,
        bar=Bar(
            chords=[
                Chord(note_type=1, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
                Chord(note_type=2, dotted=False, grid=None, notes=[Note(2, 1, 0)]),
                Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 2, 0)]),
            ],
        ),
        bar_chords=[
            Chord(note_type=1, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
            Chord(note_type=2, dotted=False, grid=None, notes=[Note(2, 1, 0)]),
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 2, 0)]),
        ],
        tuning_pitches=[67, 62, 57, 53, 48, 43],
    )
    text_rows = ["".join(row) for row in rows]
    assert any(line[3] == MELODY_NOTEHEAD_GLYPH for line in text_rows)
    assert any(line[9] == MELODY_NOTEHEAD_GLYPH for line in text_rows)
    assert any(line[15] == MELODY_FILLED_NOTEHEAD_GLYPH for line in text_rows)


def test_melody_staff_rows_whole_note_has_no_stem_half_note_is_hollow() -> None:
    rows = melody_staff_rows(
        [],
        onset_cols=[3, 9, 15],
        width=20,
        left_pad=1,
        bar=Bar(
            chords=[
                Chord(note_type=1, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
                Chord(note_type=2, dotted=False, grid=None, notes=[Note(2, 1, 0)]),
                Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 2, 0)]),
            ],
        ),
        bar_chords=[
            Chord(note_type=1, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
            Chord(note_type=2, dotted=False, grid=None, notes=[Note(2, 1, 0)]),
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 2, 0)]),
        ],
        tuning_pitches=[67, 62, 57, 53, 48, 43],
    )
    text_rows = ["".join(row) for row in rows]
    whole_row = next(idx for idx, line in enumerate(text_rows) if line[3] == MELODY_NOTEHEAD_GLYPH)
    half_row = next(idx for idx, line in enumerate(text_rows) if line[9] == MELODY_NOTEHEAD_GLYPH)
    quarter_row = next(idx for idx, line in enumerate(text_rows) if line[15] == MELODY_FILLED_NOTEHEAD_GLYPH)
    assert all(text_rows[row][3] != "|" for row in range(whole_row))
    assert any(text_rows[row][9] == "|" for row in range(half_row))
    assert any(text_rows[row][15] == "|" for row in range(quarter_row))


def test_melody_staff_rows_draws_explicit_rest_marker() -> None:
    bar = Bar(
        chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])],
        melody_events=[MelodyEvent("r", 0, note_type=4, is_rest=True)],
    )
    rows = melody_staff_rows(
        bar.melody_events,
        onset_cols=[4],
        width=12,
        left_pad=1,
        bar=bar,
        bar_chords=bar.chords,
        tuning_pitches=[67, 62, 57, 53, 48, 43],
    )
    text_rows = ["".join(row) for row in rows]
    assert any(line[4] == "r" for line in text_rows)
    assert all(line[4] not in {MELODY_NOTEHEAD_GLYPH, MELODY_FILLED_NOTEHEAD_GLYPH} for line in text_rows)


def test_melody_staff_rows_raw_fallback_natural_hint_does_not_draw_n() -> None:
    bar = Bar(
        chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])],
        melody_events=[MelodyEvent("f", 0, note_type=4, accidental_flags=0x2000)],
        structured_text_rows=[ImportedTextRow(0, "vocal", text="3 raw cue", tokens=["raw"])],
    )
    rows = melody_staff_rows(
        bar.melody_events,
        onset_cols=[4],
        width=12,
        left_pad=1,
        bar=bar,
        bar_chords=bar.chords,
        tuning_pitches=[67, 62, 57, 53, 48, 43],
    )
    text_rows = ["".join(row) for row in rows]
    assert all("n" not in line for line in text_rows)
