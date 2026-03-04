from oud.core.model import Bar, Chord, LyricEvent, MelodyEvent, Note
from oud.ui.render_text_lanes import (
    _MELODY_STAFF_ROWS,
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
    assert sum(1 for line in text_rows if "-" in line) == 5


def test_melody_staff_rows_uses_lyric_anchor_count_for_inferred_vocal_notes() -> None:
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
    assert sum(line.count("o") for line in text_rows) == 3
    assert "|" in text_rows[0]
    assert "\\" in text_rows[0]
    assert sum(1 for line in text_rows if "|" in line or "\\" in line or "." in line) >= 2


def test_melody_staff_rows_ignores_extra_tab_onsets_when_lyrics_have_fewer_events() -> None:
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
    assert sum(line.count("o") for line in text_rows) == 3
    assert "||" not in text_rows[0]


def test_melody_staff_rows_use_fixed_treble_positions_for_d_a_d_prime() -> None:
    rows = melody_staff_rows(
        [MelodyEvent("d", 0), MelodyEvent("a", 1), MelodyEvent("d'", 2)],
        onset_cols=[2, 8, 14],
        width=20,
        left_pad=1,
    )
    text_rows = ["".join(row) for row in rows]
    note_rows = [idx for idx, line in enumerate(text_rows) if "o" in line]
    assert len(text_rows) == _MELODY_STAFF_ROWS
    assert sum(1 for line in text_rows if "-" in line) == 5
    assert len(note_rows) == 3
    assert note_rows == sorted(note_rows)
    assert len(set(note_rows)) == 3
    assert min(note_rows) >= 1
    assert max(note_rows) < _MELODY_STAFF_ROWS
