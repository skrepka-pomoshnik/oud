from pathlib import Path

import pytest

from oud.exports.lilypond import export_lilypond
from oud.importers.ft3 import build_durations, load_ft3
from petrucci.model import (
    Bar,
    Chord,
    ImportedBarContent,
    ImportedScore,
    ImportedStaff,
    LyricEvent,
    MelodyEvent,
    Note,
    Piece,
)


def test_export_lilypond_emits_vocal_staff_and_lyrics_when_enabled(tmp_path) -> None:
    bar = Bar(
        chords=[
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 3, 0)]),
        ],
        melody_events=[
            MelodyEvent("d", 0, note_type=4),
            MelodyEvent("a", 1, note_type=4),
            MelodyEvent("d'", 2, note_type=4),
        ],
        lyric_event_rows=[
            [
                LyricEvent("Can", 0, syllabic="single"),
                LyricEvent("she", 1, syllabic="single"),
                LyricEvent("ex-", 2, syllabic="begin"),
            ],
        ],
        time_sig="O",
    )
    piece = Piece(title="Can she excuse?", composer="John Dowland", bars=[bar], strings=6)
    path = tmp_path / "vocal.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={
            "tuning": "g2c3f3a3d4g4",
            "style": "french",
            "showmelody": "on",
            "showlyrics": "on",
            "vocalpos": "top",
        },
    )
    text = path.read_text(encoding="utf-8")
    assert "\\new StaffGroup <<" in text
    assert '\\new Staff = "melodyStaff"' in text
    assert '\\new Lyrics \\lyricsto "melodyVoice" {' in text
    assert '"Can" "she" "ex-"' in text
    assert '"ex-" --' not in text
    assert "\\new TabStaff" in text
    assert "\\time 3/4" in text


def test_export_lilypond_emits_imported_vocal_only_staffgroup(tmp_path) -> None:
    piece = Piece(
        title="Now O now",
        key="GM",
        imported_score=ImportedScore(
            source_format="ft3",
            staffs=[
                ImportedStaff(
                    kind="note",
                    bars=[
                        ImportedBarContent(
                            source_bar_index=0,
                            time_sig="3/4",
                            melody_events=[
                                MelodyEvent("b", 0, note_type=3, ornament="+"),
                                MelodyEvent("a", 1, note_type=4),
                            ],
                        ),
                        ImportedBarContent(
                            source_bar_index=1,
                            melody_events=[
                                MelodyEvent("g", 0, note_type=3),
                                MelodyEvent("f#", 1, note_type=4),
                            ],
                            system_break=True,
                        ),
                    ],
                ),
                ImportedStaff(
                    kind="lyrics",
                    bars=[
                        ImportedBarContent(
                            source_bar_index=0,
                            lyric_event_rows=[[LyricEvent("Now", 0), LyricEvent("O", 1)]],
                        ),
                        ImportedBarContent(
                            source_bar_index=1,
                            lyric_event_rows=[[LyricEvent("now", 0), LyricEvent("I", 1)]],
                        ),
                    ],
                ),
            ],
        ),
    )
    path = tmp_path / "imported_vocal_only.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"showmelody": "on", "showlyrics": "on", "vocalpos": "top"},
    )
    text = path.read_text(encoding="utf-8")
    assert "\\new TabStaff" not in text
    assert '\\new Staff = "melodyStaff"' in text
    assert '"Now" "O"' in text
    assert "\\key g \\major" in text
    assert "\\break" in text
    assert '\\tiny "+"' in text


def test_export_lilypond_emits_every_imported_polyphonic_staff(tmp_path) -> None:
    piece = load_ft3("lutemusic/05_can_she_excuse/can_she_excuse_4_part.ft3")
    path = tmp_path / "four_part.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"showmelody": "on", "showlyrics": "on"},
    )
    text = path.read_text(encoding="utf-8")
    assert text.count('\\new Staff = "melody') == 4
    for label in ("soprano", "alto", "tenor", "bass"):
        assert f'instrumentName = "{label}"' in text
    for clef in ("alto", "tenor", "bass"):
        assert f'\\clef "{clef}"' in text


def test_export_lilypond_preserves_ft3_metadata_and_editorial_comments(tmp_path) -> None:
    piece = Piece(
        title="Title",
        subtitle="Subtitle",
        author="Poet",
        composer="Composer",
        arranger="Arranger",
        footnote="Footnote",
        source="Source Book",
        publisher="Publisher",
        volume="Volume I",
        page="12v",
        piece_type="fantasia",
        part="score",
        ensemble="8-course, alto",
        section_annotations={"section": "Performance"},
        bars=[Bar()],
        imported_score=ImportedScore(
            source_format="ft3",
            staffs=[
                ImportedStaff(
                    kind="comment",
                    label="editorial",
                    bars=[ImportedBarContent(source_bar_index=0, editorial_text=["Source comment"])],
                ),
            ],
        ),
    )
    path = tmp_path / "metadata.ly"
    export_lilypond(str(path), piece, overrides={}, durations={}, bar_width=8, settings={})
    text = path.read_text(encoding="utf-8")
    assert 'subtitle = "Subtitle"' in text
    assert 'poet = "Poet"' in text
    assert 'arranger = "Arranger"' in text
    assert 'piece = "fantasia | score"' in text
    assert 'opus = "Volume I"' in text
    assert 'source = "Source Book, page 12v"' in text
    assert 'copyright = "Publisher"' in text
    assert 'tagline = "Footnote"' in text
    assert "% oud metadata section: Performance" in text
    assert "% oud staff 1: comment | editorial | 1 bars" in text
    assert "% oud bar 1 comment: Source comment" in text


def test_export_lilypond_preserves_imported_beams_and_fermata(tmp_path) -> None:
    piece = Piece(
        imported_score=ImportedScore(
            source_format="ft3",
            staffs=[
                ImportedStaff(
                    kind="note",
                    bars=[
                        ImportedBarContent(
                            source_bar_index=0,
                            melody_events=[
                                MelodyEvent("c", 0, note_type=5, beam="start"),
                                MelodyEvent("d", 1, note_type=5, beam="end", fermata=True),
                            ],
                            fermata=True,
                        ),
                    ],
                ),
            ],
        ),
    )
    path = tmp_path / "beam_fermata.ly"
    export_lilypond(str(path), piece, overrides={}, durations={}, bar_width=8, settings={})
    text = path.read_text(encoding="utf-8")
    assert "c8[" in text
    assert "d8]\\fermata" in text


def test_export_lilypond_uses_imported_vocal_staff_over_bar_fallback_when_present(tmp_path) -> None:
    piece = Piece(
        title="Mixed",
        bars=[Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])])],
        strings=6,
        imported_score=ImportedScore(
            source_format="ft3",
            staffs=[
                ImportedStaff(
                    kind="note",
                    bars=[
                        ImportedBarContent(
                            source_bar_index=0,
                            melody_events=[
                                MelodyEvent("r", 0, note_type=4, is_rest=True),
                                MelodyEvent("f#", 1, note_type=4),
                            ],
                        ),
                    ],
                ),
                ImportedStaff(
                    kind="lyrics",
                    bars=[ImportedBarContent(source_bar_index=0, lyrics=["Rest sharp"])],
                ),
            ],
        ),
    )
    path = tmp_path / "mixed_imported.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={
            "tuning": "g2c3f3a3d4g4",
            "showmelody": "on",
            "showlyrics": "on",
            "vocalpos": "bottom",
        },
    )
    text = path.read_text(encoding="utf-8")
    assert "\\new TabStaff" in text
    assert "  r4" in text
    assert "fis4" in text
    assert '"Rest" "sharp"' in text


def test_export_lilypond_aligns_sparse_imported_lyrics_by_source_bar(tmp_path) -> None:
    piece = Piece(
        title="Sparse imported vocal",
        bars=[Bar(), Bar(), Bar()],
        imported_score=ImportedScore(
            source_format="ft3",
            staffs=[
                ImportedStaff(
                    kind="note",
                    bars=[
                        ImportedBarContent(
                            source_bar_index=0,
                            melody_events=[MelodyEvent("c", 0, note_type=4)],
                        ),
                        ImportedBarContent(
                            source_bar_index=0,
                            melody_events=[
                                MelodyEvent("b", 0, note_type=4),
                                MelodyEvent("a", 1, note_type=4),
                            ],
                        ),
                        ImportedBarContent(
                            source_bar_index=2,
                            melody_events=[MelodyEvent("g", 0, note_type=4)],
                        ),
                    ],
                ),
                ImportedStaff(
                    kind="lyrics",
                    bars=[
                        ImportedBarContent(
                            source_bar_index=2,
                            lyric_event_rows=[[LyricEvent("late", 0)]],
                        ),
                    ],
                ),
            ],
        ),
    )
    path = tmp_path / "sparse_imported.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"showmelody": "on", "showlyrics": "on"},
    )
    text = path.read_text(encoding="utf-8")
    assert "  c4" not in text
    assert text.count("  b4") == 1
    assert text.count("  a4") == 1
    assert '_ _ _ "late"' in text


def test_export_lilypond_emits_barline_only_imported_score(tmp_path) -> None:
    piece = Piece(
        title="Barlines",
        imported_score=ImportedScore(
            source_format="ft3",
            staffs=[
                ImportedStaff(
                    kind="barline",
                    bars=[
                        ImportedBarContent(source_bar_index=0, repeat=".:", time_sig="3/4"),
                        ImportedBarContent(
                            source_bar_index=1,
                            barline="||",
                            system_break=True,
                        ),
                    ],
                ),
            ],
        ),
    )
    path = tmp_path / "barline_only.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"showmelody": "on"},
    )
    text = path.read_text(encoding="utf-8")
    assert "\\new TabStaff" not in text
    assert text.count("  r4") == 2
    assert '\\bar ".|:"' in text
    assert '\\bar "||"' in text
    assert "\\break" in text


def test_export_lilypond_preserves_ft3_tab_system_break(tmp_path) -> None:
    piece = Piece(
        title="Break",
        bars=[
            Bar(
                chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])],
                system_break=True,
            ),
        ],
        strings=6,
    )
    path = tmp_path / "tab_break.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"tuning": "g2c3f3a3d4g4"},
    )
    assert "\\break" in path.read_text(encoding="utf-8")


def test_export_lilypond_respects_vocalpos_bottom_order(tmp_path) -> None:
    bar = Bar(
        chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])],
        melody_events=[MelodyEvent("d", 0, note_type=4)],
        lyric_event_rows=[[LyricEvent("Can", 0)]],
    )
    piece = Piece(title="Order", bars=[bar], strings=6)
    path = tmp_path / "vocal_order.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={
            "tuning": "g2c3f3a3d4g4",
            "showmelody": "on",
            "showlyrics": "on",
            "vocalpos": "bottom",
        },
    )
    text = path.read_text(encoding="utf-8")
    assert text.index("\\new TabStaff") < text.index('\\new Staff = "melodyStaff"')


def test_export_lilypond_emits_duet_staffgroup_with_labels(tmp_path) -> None:
    top_bar_1 = Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])], time_sig="C")
    top_bar_2 = Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 1, 0)])])
    bottom_bar_1 = Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 2, 0)])])
    bottom_bar_2 = Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(4, 3, 0)])])
    piece = Piece(
        title="Duet",
        bars=[top_bar_1, top_bar_2, bottom_bar_1, bottom_bar_2],
        strings=6,
        part="score",
        ensemble="lute 1: prime,lute 2: bass",
    )
    path = tmp_path / "duet.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"tuning": "g2c3f3a3d4g4", "duetscoreview": "both"},
    )
    text = path.read_text(encoding="utf-8")
    assert "\\new StaffGroup <<" in text
    assert text.count("\\new TabStaff") == 2
    assert 'instrumentName = "Lute 1"' in text
    assert 'instrumentName = "Lute 2"' in text
    assert text.count("stringTunings = \\stringTuning") == 2


def test_export_lilypond_ft3_meter_mapping_and_midpiece_changes_synthetic(tmp_path) -> None:
    piece = Piece(
        title="Meters",
        strings=6,
        bars=[
            Bar(time_sig="O", chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])]),
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 1, 0)])]),
            Bar(time_sig="C|", chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)])]),
            Bar(time_sig="6/8", chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 3, 0)])]),
        ],
    )
    path = tmp_path / "meters.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"tuning": "g4d4a3f3c3g2", "timesigstyle": "symbol"},
    )
    text = path.read_text(encoding="utf-8")
    assert "\\defaultTimeSignature" in text
    assert "\\time 3/4" in text
    assert "\\time 2/2" in text
    assert "\\time 6/8" in text
    # no duplicate \time for bar 2 with inherited meter
    assert text.count("\\time 3/4") == 1

    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"tuning": "g4d4a3f3c3g2", "timesigstyle": "fraction"},
    )
    text = path.read_text(encoding="utf-8")
    assert "\\numericTimeSignature" in text


def test_export_lilypond_emits_midpiece_time_changes_for_real_ft3_if_available(tmp_path) -> None:
    src = Path("lutemusic/ich_bin_eine_blume_zu_saron_T.ft3")
    if not src.exists():
        pytest.skip("local FT3 corpus file not available")

    piece = load_ft3(str(src))
    path = tmp_path / "ichbin.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations=build_durations(piece),
        bar_width=12,
        settings={"tuning": "g2c3f3a3d4g4", "style": "french", "key": piece.key or "C"},
    )
    text = path.read_text(encoding="utf-8")
    assert text.count("\\time ") >= 3
    assert "\\time 3/4" in text
    assert "\\time 2/2" in text
    assert "\\time 6/8" in text


def test_export_lilypond_keeps_ft3_repeat_barlines_from_real_file_if_available(tmp_path) -> None:
    src = Path("lutemusic/wu_sol_ich_mich_hin_keren.ft3")
    if not src.exists():
        pytest.skip("local FT3 corpus file not available")

    piece = load_ft3(str(src))
    path = tmp_path / "wusol.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations=build_durations(piece),
        bar_width=12,
        settings={"tuning": "g2c3f3a3d4g4", "style": "french", "key": piece.key or "C"},
    )
    text = path.read_text(encoding="utf-8")
    assert '\\bar ".|:"' in text
    assert '\\bar ":|."' in text


@pytest.mark.parametrize(
    ("src_name", "expected_tokens"),
    [
        ("wu_sol_ich_mich_hin_keren.ft3", ('\\bar ".|:"', '\\bar ":|."')),
        ("czarna_krowa.ft3", ('\\bar ".|:"', '\\bar ":|."', '\\bar "||"')),
        ("can_she_excuse.ft3", ('\\bar ".|:"', '\\bar ":|."', '\\bar "||"')),
    ],
)
def test_export_lilypond_real_ft3_repeat_barline_matrix_if_available(
    tmp_path,
    src_name: str,
    expected_tokens: tuple[str, ...],
) -> None:
    src = Path("lutemusic") / src_name
    if not src.exists():
        pytest.skip("local FT3 corpus file not available")
    piece = load_ft3(str(src))
    path = tmp_path / f"{src.stem}.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations=build_durations(piece),
        bar_width=12,
        settings={"tuning": "g2c3f3a3d4g4", "style": "french", "key": piece.key or "C"},
    )
    text = path.read_text(encoding="utf-8")
    for token in expected_tokens:
        assert token in text


@pytest.mark.parametrize(
    "src_name",
    [
        "wu_sol_ich_mich_hin_keren.ft3",
        "czarna_krowa.ft3",
        "can_she_excuse.ft3",
        "05_a_fancy.ft3",
        "23a_frogg_galliard_2.ft3",
    ],
)
def test_export_lilypond_real_ft3_smoke_matrix_if_available(tmp_path, src_name: str) -> None:
    src = Path("lutemusic") / src_name
    if not src.exists():
        pytest.skip("local FT3 corpus file not available")
    piece = load_ft3(str(src))
    path = tmp_path / f"{src.stem}.ly"
    msg = export_lilypond(
        str(path),
        piece,
        overrides={},
        durations=build_durations(piece),
        bar_width=12,
        settings={
            "tuning": "g2c3f3a3d4g4",
            "style": "french",
            "key": piece.key or "C",
        },
    )
    assert msg.startswith("Wrote ")
    text = path.read_text(encoding="utf-8")
    assert "\\new TabStaff" in text
    assert "stringTunings" in text
    assert "\\bar " in text
