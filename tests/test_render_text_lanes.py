from oud.core.model import Bar, Chord, LyricEvent, MelodyEvent, Note
from oud.ui.render_text_lanes import (
    _MELODY_STAFF_ROWS,
    draw_melody_time_signature,
    lyric_event_cells,
    melody_event_cells,
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
    assert len(rows) == _MELODY_STAFF_ROWS
    text_rows = ["".join(row) for row in rows]
    assert any(line[2] == "o" for line in text_rows)
    assert any(line[8] == "o" for line in text_rows)
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
    assert sum(line.count("o") for line in text_rows) == 4
    assert "|" in text_rows[0]
    assert "\\" in text_rows[0]
    assert sum(1 for line in text_rows if "|" in line or "\\" in line or "." in line) >= 2


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
    assert sum(line.count("o") for line in text_rows) == 5
    assert any(line[18] == "o" for line in text_rows)


def test_melody_staff_rows_use_fixed_treble_positions_for_d_a_d_prime() -> None:
    rows = melody_staff_rows(
        [MelodyEvent("d", 0), MelodyEvent("a", 1), MelodyEvent("d'", 2)],
        onset_cols=[2, 8, 14],
        width=20,
        left_pad=1,
    )
    text_rows = ["".join(row) for row in rows]
    assert len(text_rows) == _MELODY_STAFF_ROWS
    assert sum(1 for line in text_rows if "-" in line) == 5
    assert text_rows[4][14] == "o"  # d' on the 4th line
    assert text_rows[7][8] == "o"  # a in a staff space
    assert text_rows[11][2] == "o"  # d below the bottom line


def test_melody_staff_rows_keeps_explicit_onsets_in_tab_columns() -> None:
    rows = melody_staff_rows(
        [MelodyEvent("d", 0), MelodyEvent("a", 1), MelodyEvent("d'", 2)],
        onset_cols=[2, 8, 14, 19, 23],
        width=26,
        left_pad=1,
    )
    text_rows = ["".join(row) for row in rows]
    assert text_rows[11][2] == "o"
    assert text_rows[7][8] == "o"
    assert text_rows[4][14] == "o"
    assert all(line[19] != "o" for line in text_rows)
    assert all(line[23] != "o" for line in text_rows)


def test_melody_staff_rows_draws_ledger_cue_for_note_below_visible_staff() -> None:
    rows = melody_staff_rows(
        [MelodyEvent("c", 0)],
        onset_cols=[4],
        width=12,
        left_pad=1,
    )
    text_rows = ["".join(row) for row in rows]
    assert text_rows[11][4] == "o"
    assert text_rows[11][3] == "-"
    assert text_rows[11][5] == "-"


def test_melody_staff_rows_draws_accidental_next_to_notehead() -> None:
    rows = melody_staff_rows(
        [MelodyEvent("bb", 0, accidental_flags=0x1000)],
        onset_cols=[4],
        width=12,
        left_pad=1,
    )
    text_rows = ["".join(row) for row in rows]
    note_row = next(idx for idx, line in enumerate(text_rows) if line[4] == "o")
    assert text_rows[note_row][3] == "b"


def test_draw_melody_time_signature_places_stacked_meter_digits() -> None:
    rows = melody_staff_rows(
        [MelodyEvent("d", 0)],
        onset_cols=[6],
        width=16,
        left_pad=1,
    )
    draw_melody_time_signature(rows, time_sig="3/4", left_pad=1)
    text_rows = ["".join(row) for row in rows]
    assert text_rows[4][1] == "3"
    assert text_rows[6][1] == "4"
