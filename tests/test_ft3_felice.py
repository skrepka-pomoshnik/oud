import pytest

from oud.importers.ft3 import load_ft3
from petrucci.adapters.vocal import infer_vocal_events
from petrucci.terminal.text.lyrics import piece_for_lyric_display

FELICE = "tests/fixtures/ft3/corpus/01_felice_fu_quel_anon.ft3"


@pytest.mark.ft3_corpus
def test_felice_positioned_lyrics_transpose_into_twelve_verses() -> None:
    piece = load_ft3(FELICE)
    assert piece.imported_score is not None
    lyrics = next(staff for staff in piece.imported_score.staffs if staff.kind == "lyrics")

    assert len(lyrics.bars[0].lyric_event_rows) == 12
    assert [[event.text for event in lyrics.bars[index].lyric_event_rows[0]] for index in range(4)] == [
        ["Fe", "li", "ce"],
        ["fu", "quel", "di"],
        ["fe", "li", "ce_il"],
        ["pon", "to"],
    ]
    assert [event.text for event in lyrics.bars[1].lyric_event_rows[1]] == ["gli_oc", "chi", "miei"]
    assert len(lyrics.bars[4].lyric_event_rows) == 12
    assert [[event.text for event in row] for row in lyrics.bars[4].lyric_event_rows[:2]] == [
        ["ch'io", "mi", "tro"],
        ["per", "cui", "nel"],
    ]
    comments = next(staff for staff in piece.imported_score.staffs if staff.kind == "comment")
    assert next(bar for bar in comments.bars if bar.source_bar_index == 0).editorial_text == [
        "Intro: Ricercars 1,9,12,14,15,16,18,20",
    ]


@pytest.mark.ft3_corpus
def test_felice_coda_keeps_all_syllables_on_the_final_stanza() -> None:
    piece = load_ft3(FELICE)
    assert piece.imported_score is not None
    lyrics = next(staff for staff in piece.imported_score.staffs if staff.kind == "lyrics")

    assert all(len(lyrics.bars[index].lyric_event_rows) == 12 for index in range(12, 16))
    assert all(not row for index in range(12, 16) for row in lyrics.bars[index].lyric_event_rows[:11])
    assert [event.text for index in range(12, 16) for event in lyrics.bars[index].lyric_event_rows[11]] == [
        "ha",
        "vran",
        "suo_in",
        "ten",
        "to_i",
        "dol",
        "ci",
        "pen",
        "sier",
        "mie",
        "i.",
    ]
    assert [event.onset_index for event in lyrics.bars[12].lyric_event_rows[11]] == [1, 2, 3]
    comments = next(staff for staff in piece.imported_score.staffs if staff.kind == "comment")
    assert next(bar for bar in comments.bars if bar.source_bar_index == 12).editorial_text == ["Coda at end only."]


@pytest.mark.ft3_corpus
def test_felice_high_letter_frets_are_not_dropped() -> None:
    piece = load_ft3(FELICE)

    for bar_index in (12, 13, 14, 15):
        assert piece.bars[bar_index].chords, bar_index + 1


@pytest.mark.ft3_corpus
def test_felice_compact_lyric_display_selects_one_stanza_before_layout() -> None:
    piece = load_ft3(FELICE)
    first = piece_for_lyric_display(piece, {"showlyrics": "on", "lyricmode": "first"})
    current = piece_for_lyric_display(
        piece,
        {"showlyrics": "on", "lyricmode": "current", "lyricverse": "2"},
    )
    assert first.imported_score is not None
    assert current.imported_score is not None
    first_lyrics = next(staff for staff in first.imported_score.staffs if staff.kind == "lyrics")
    current_lyrics = next(staff for staff in current.imported_score.staffs if staff.kind == "lyrics")
    assert [event.text for event in first_lyrics.bars[1].lyric_event_rows[0]] == ["fu", "quel", "di"]
    assert [event.text for event in current_lyrics.bars[1].lyric_event_rows[0]] == ["gli_oc", "chi", "miei"]
    assert all(len(bar.lyric_event_rows) <= 1 for bar in first_lyrics.bars)


@pytest.mark.ft3_corpus
def test_felice_third_tactus_keeps_f_minor_flat_pitches() -> None:
    piece = load_ft3(FELICE)
    events = infer_vocal_events(piece.bars[2], tuning_pitches=[])
    assert [event.text for event in events] == ["bb", "ab", "g"]
    assert [event.pitch for event in events] == [70, 68, 67]
