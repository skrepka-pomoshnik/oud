from oud.core.key_signature import (
    key_signature_accidentals,
    key_signature_count,
    normalize_key_signature_name,
)


def test_normalize_key_signature_name_accepts_short_and_long_forms() -> None:
    assert normalize_key_signature_name("GM") == ("G", "major")
    assert normalize_key_signature_name("dm") == ("D", "minor")
    assert normalize_key_signature_name("Bb major") == ("Bb", "major")
    assert normalize_key_signature_name("f# minor") == ("F#", "minor")


def test_key_signature_count_uses_standard_circle_values() -> None:
    assert key_signature_count("C") == 0
    assert key_signature_count("GM") == 1
    assert key_signature_count("DM") == 2
    assert key_signature_count("Fm") == -4


def test_key_signature_accidentals_returns_expected_pitch_classes() -> None:
    assert key_signature_accidentals("GM") == {"f": "#"}
    assert key_signature_accidentals("DM") == {"f": "#", "c": "#"}
    assert key_signature_accidentals("Fm") == {
        "b": "b",
        "e": "b",
        "a": "b",
        "d": "b",
    }
