from oud.importers.ft3.source_profiles import apply_ft3_source_tuning
from petrucci.core.model import Piece


def _leaves_be_green(*, tuning: str | None = None) -> Piece:
    return Piece(
        title="21. Mrs. Anne Green, her leaves be green",
        composer="John Danyel",
        key="Bbm",
        strings=9,
        tuning=tuning,
    )


def test_documented_danyel_scordatura_fills_missing_ft3_tuning() -> None:
    piece = _leaves_be_green()

    apply_ft3_source_tuning(piece)

    assert piece.tuning == "d-2e-2f2a-2b-2f3b-3d4g4"
    assert piece.tuning_source == "Danyel 1606 scordatura; Gerbode sounding pitch"


def test_explicit_ft3_tuning_precedes_source_profile() -> None:
    piece = _leaves_be_green(tuning="g2c3f3a3d4g4")

    apply_ft3_source_tuning(piece)

    assert piece.tuning == "g2c3f3a3d4g4"
    assert piece.tuning_source is None


def test_extended_course_ensemble_gets_diatonic_bass_default() -> None:
    piece = Piece(ensemble="10-course", strings=10)

    apply_ft3_source_tuning(piece)

    assert piece.tuning == "c2d2e2f2g2c3f3a3d4g4"
    assert piece.tuning_source == "FT3 ensemble default; diatonic extended basses"


def test_companion_pitch_profile_is_matched_by_musical_identity() -> None:
    piece = Piece(
        title="7. Fantasy 4",
        composer="Robert White",
        key="Fm",
        strings=6,
    )

    apply_ft3_source_tuning(piece)

    assert piece.tuning == "a2d3g3b3e4a4"
    assert piece.tuning_source == "Gerbode companion MIDI sounding pitch"


def test_extended_companion_pitch_profile_precedes_ensemble_default() -> None:
    piece = Piece(
        title="Sonata in C Major",
        subtitle="1. Moderato",
        composer="Karl Friedrich Abel",
        key="CM",
        ensemble="archlute, 6-course bass viol",
        part="archlute",
        strings=9,
    )

    apply_ft3_source_tuning(piece)

    assert piece.tuning == "d-2e-2e2f+2b2e3g+3c+4f+4"
    assert piece.tuning_source == "Gerbode companion MIDI sounding pitch"
