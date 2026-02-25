from __future__ import annotations

from tests.helpers_regression_cases import (
    import_fixture_extra_courses_piece,
    import_fixture_meter_change_mid_system_piece,
    import_fixture_multisection_tab_piece,
    import_fixture_no_break_header_body_piece,
    mk_bar,
    mk_chord,
    mk_note,
    mk_piece,
)


def test_synthetic_factory_builders_create_piece_bar_chord_graph() -> None:
    piece = mk_piece(
        [
            mk_bar(
                [
                    mk_chord(4, [(1, 0), (3, 2)]),
                    mk_chord(5, [mk_note(2, 1), mk_note(4, 0)]),
                ],
                time_sig="C",
                repeat=".:",
                barline="||",
                dynamic="mf",
                fermata=True,
            ),
        ],
        strings=7,
        title="Factory",
    )
    assert piece.title == "Factory"
    assert piece.strings == 7
    assert len(piece.bars) == 1
    bar = piece.bars[0]
    assert bar.time_sig == "C"
    assert bar.repeat == ".:"
    assert bar.barline == "||"
    assert bar.dynamic == "mf"
    assert bar.fermata is True
    assert len(bar.chords) == 2
    assert [note.string for note in bar.chords[0].notes] == [1, 3]


def test_import_fixture_extra_courses_piece_contains_fretted_7th_and_8th_courses() -> None:
    piece = import_fixture_extra_courses_piece()
    assert piece.strings == 8
    extra_notes = [note for bar in piece.bars for note in bar.notes if note.string >= 7]
    assert extra_notes
    assert any(note.string == 7 and note.fret > 0 for note in extra_notes)
    assert any(note.string == 8 and note.fret > 0 for note in extra_notes)


def test_import_fixture_multisection_piece_has_markers_and_section_annotations() -> None:
    piece = import_fixture_multisection_tab_piece()
    assert len(piece.bars) >= 4
    assert piece.bars[0].repeat == ".:"
    assert piece.bars[2].time_sig == "3/4"
    assert piece.bars[3].repeat == ":."
    assert piece.bars[3].barline == "||"
    assert piece.section_annotations == {"2": "Section B", "4": "Fine"}


def test_import_fixture_no_break_header_body_piece_looks_like_parsed_tab_result() -> None:
    piece = import_fixture_no_break_header_body_piece()
    assert piece.title == "NoSeparator"
    assert piece.composer == "Composer"
    assert len(piece.bars) == 1
    assert len(piece.bars[0].chords) == 2


def test_import_fixture_meter_change_mid_system_piece_contains_meter_transition() -> None:
    piece = import_fixture_meter_change_mid_system_piece()
    assert piece.bars[0].time_sig == "C"
    assert piece.bars[2].time_sig == "O"
    assert piece.bars[1].time_sig is None
    assert piece.bars[3].time_sig is None
