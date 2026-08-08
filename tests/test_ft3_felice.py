from oud.importers.ft3 import load_ft3

FELICE = "lutemusic/01_felice_fu_quel_anon.ft3"


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
    comments = next(staff for staff in piece.imported_score.staffs if staff.kind == "comment")
    assert len(comments.bars) == 1
    assert comments.bars[0].editorial_text == ["Intro: Ricercars 1,9,12,14,15,16,18,20"]


def test_felice_high_letter_frets_are_not_dropped() -> None:
    piece = load_ft3(FELICE)

    for bar_index in (12, 13, 14, 15):
        assert piece.bars[bar_index].chords, bar_index + 1
