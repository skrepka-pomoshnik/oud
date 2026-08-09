from fractions import Fraction

from petrucci.core.model import Bar, ImportedScore, ImportedSourceRecord, Piece
from petrucci.core.source import DiplomaticSignKind, MensurationMeaning, build_source_document


def _historical_piece() -> Piece:
    return Piece(
        bars=[Bar(time_sig="C|", proportion=(3, 2))],
        imported_score=ImportedScore(
            source_format="ft3",
            source_records=[ImportedSourceRecord(0, 1, "barline-raw", 12, source_voice_index=2)],
        ),
    )


def test_source_document_separates_written_signs_from_meaning() -> None:
    document = build_source_document(_historical_piece(), document_id="fixture")

    assert [sign.kind for sign in document.signs] == [
        DiplomaticSignKind.MENSURATION,
        DiplomaticSignKind.PROPORTION,
    ]
    assert [sign.written_value for sign in document.signs] == ["C|", "3:2"]
    assert document.decisions[0].effective_mensuration == MensurationMeaning(2, 2)
    assert document.decisions[1].effective_proportion == Fraction(3, 2)
    assert document.signs[0].written_value == "C|"


def test_source_document_identity_and_coordinates_are_stable() -> None:
    first = build_source_document(_historical_piece(), document_id="fixture")
    second = build_source_document(_historical_piece(), document_id="fixture")

    assert first == second
    assert first.signs[0].id == "fixture:1:2:0:mensuration"
    assert first.signs[0].location.source_record_index == 0
    assert first.signs[0].location.staff_index == 1
    assert first.signs[0].location.voice_index == 2


def test_source_document_deduplicates_inherited_bar_signs() -> None:
    piece = _historical_piece()
    assert piece.imported_score is not None
    piece.imported_score.source_records.append(ImportedSourceRecord(0, 1, "notes-raw", 8, source_voice_index=2))

    document = build_source_document(piece, document_id="fixture")

    assert len(document.signs) == 2
    assert len(document.decisions) == 2
