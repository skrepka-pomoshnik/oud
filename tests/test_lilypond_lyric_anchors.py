from oud.exports.lilypond import lilypond_text
from petrucci.core.model import Bar, ImportedBarContent, ImportedScore, ImportedStaff, LyricEvent, MelodyEvent, Piece
from petrucci.engraving.typeset import TypesetOptions, typeset_piece


def _lyrics(text: str) -> list[str]:
    return [block.split("}", 1)[0].strip() for block in text.split('\\lyricsto "melodyVoice" {')[1:]]


def test_late_and_missing_stanzas_keep_their_note_slots_in_plain_scores() -> None:
    piece = Piece(
        bars=[
            Bar(melody_events=[MelodyEvent("c", 0, note_type=4)], lyric_event_rows=[[LyricEvent("One", 0)]]),
            Bar(
                melody_events=[MelodyEvent("d", 0, note_type=4)],
                lyric_event_rows=[[LyricEvent("two", 0)], [LyricEvent("late", 0, verse=1)]],
            ),
            Bar(melody_events=[MelodyEvent("e", 0, note_type=4)], lyric_event_rows=[[LyricEvent("three", 0)]]),
        ],
    )
    assert _lyrics(lilypond_text(piece, {}, {}, 8)) == ['"One" "two" "three"', '_ "late" _']


def test_rest_only_bars_do_not_consume_lyric_slots() -> None:
    notes = [
        ImportedBarContent(source_bar_index=0, melody_events=[MelodyEvent("c", 0, note_type=4)]),
        ImportedBarContent(source_bar_index=1, melody_events=[MelodyEvent("r", 0, note_type=4, is_rest=True)]),
        ImportedBarContent(source_bar_index=2, melody_events=[MelodyEvent("d", 0, note_type=4)]),
    ]
    lyrics = [
        ImportedBarContent(source_bar_index=0, lyric_event_rows=[[LyricEvent("One", 0)]]),
        ImportedBarContent(source_bar_index=2, lyric_event_rows=[[LyricEvent("two", 0)]]),
    ]
    piece = Piece(
        imported_score=ImportedScore(
            source_format="ft3",
            staffs=[
                ImportedStaff(kind="note", bars=notes),
                ImportedStaff(kind="lyrics", bars=lyrics),
            ],
        )
    )
    assert _lyrics(lilypond_text(piece, {}, {}, 8)) == ['"One" "two"']


def test_extenders_consume_one_anchor_and_hyphens_survive_empty_notes() -> None:
    piece = Piece(
        bars=[
            Bar(
                melody_events=[MelodyEvent("c", index, note_type=4) for index in range(5)],
                lyric_event_rows=[
                    [
                        LyricEvent("al", 0, syllabic="begin"),
                        LyricEvent("le", 2, syllabic="end"),
                        LyricEvent("", 3, extender=True),
                        LyricEvent("lu_ia", 4),
                    ]
                ],
            )
        ]
    )
    assert _lyrics(lilypond_text(piece, {}, {}, 8)) == ['"al" -- _ "le" __ _ "lu ia"']


def test_gerbode_vocals_use_readable_scale_and_wrap_identical_footer_once() -> None:
    footer = "Translation: " + "A long passage of source commentary. " * 8
    piece = Piece(
        title="Song",
        source=footer,
        footnote=footer,
        bars=[Bar(melody_events=[MelodyEvent("c", 0, note_type=4)], lyric_event_rows=[[LyricEvent("sing", 0)]])],
    )
    text = lilypond_text(piece, {}, {}, 8, settings={"lyprofile": "gerbode"})

    assert "#(set-global-staff-size 18)" in text
    assert '  source = "' not in text
    assert r'tagline = \markup \wordwrap-string "Translation:' in text
    assert footer.strip() in text


def test_terminal_elision_keeps_one_anchor_without_changing_source_text() -> None:
    syllable = LyricEvent("te_e", 0)
    piece = Piece(bars=[Bar(melody_events=[MelodyEvent("c", 0, note_type=4)], lyric_event_rows=[[syllable]])])

    result = typeset_piece(piece, options=TypesetOptions(width=80, height=24))

    assert "te e" in result.text
    assert "te_e" not in result.text
    assert syllable.text == "te_e"
