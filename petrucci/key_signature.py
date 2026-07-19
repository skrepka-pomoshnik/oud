from __future__ import annotations

import re

# Central key-signature table used for tonal accidentals.
# Positive values mean sharps in the standard order F C G D A E B.
# Negative values mean flats in the standard order B E A D G C F.
MAJOR_KEY_SIGNATURES: dict[str, int] = {
    "C": 0,
    "G": 1,
    "D": 2,
    "A": 3,
    "E": 4,
    "B": 5,
    "F#": 6,
    "C#": 7,
    "F": -1,
    "Bb": -2,
    "Eb": -3,
    "Ab": -4,
    "Db": -5,
    "Gb": -6,
    "Cb": -7,
}

MINOR_KEY_SIGNATURES: dict[str, int] = {
    "A": 0,
    "E": 1,
    "B": 2,
    "F#": 3,
    "C#": 4,
    "G#": 5,
    "D#": 6,
    "A#": 7,
    "D": -1,
    "G": -2,
    "C": -3,
    "F": -4,
    "Bb": -5,
    "Eb": -6,
    "Ab": -7,
}

SHARP_ORDER: tuple[str, ...] = ("f", "c", "g", "d", "a", "e", "b")
FLAT_ORDER: tuple[str, ...] = ("b", "e", "a", "d", "g", "c", "f")


def normalize_key_signature_name(value: str | None) -> tuple[str, str] | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    compact = re.sub(r"\s+", "", text)
    match = re.fullmatch(r"([A-Ga-g])([#b]?)(M|m)?", compact)
    if match:
        tonic = f"{match.group(1).upper()}{match.group(2)}"
        mode = "minor" if match.group(3) == "m" else "major"
        return tonic, mode
    match = re.fullmatch(r"([A-Ga-g])([#b]?)\s*(maj(?:or)?|min(?:or)?)", text, re.I)
    if match:
        tonic = f"{match.group(1).upper()}{match.group(2)}"
        mode = "minor" if match.group(3).lower().startswith("min") else "major"
        return tonic, mode
    return None


def key_signature_count(key: str | None) -> int | None:
    parsed = normalize_key_signature_name(key)
    if parsed is None:
        return None
    tonic, mode = parsed
    table = MINOR_KEY_SIGNATURES if mode == "minor" else MAJOR_KEY_SIGNATURES
    return table.get(tonic)


def key_signature_accidentals(key: str | None) -> dict[str, str]:
    count = key_signature_count(key)
    if count is None or count == 0:
        return {}
    if count > 0:
        return dict.fromkeys(SHARP_ORDER[:count], "#")
    return dict.fromkeys(FLAT_ORDER[:-count], "b")
