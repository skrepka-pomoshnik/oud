from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DecodedFT3Extras:
    raw: int
    barre: bool = False
    right_fingering: str | None = None
    left_fingering: str | None = None
    right_ornament: str | None = None
    left_ornament: str | None = None
    arpeggio: str | None = None
    bass_course: int | None = None
    residual: int | None = None


_RIGHT_FINGERING_BITS: tuple[tuple[int, str], ...] = (
    (0x0002, "thumb"),
    (0x0004, "dot1"),
    (0x0008, "dot2"),
    (0x0010, "dot3"),
)
_LEFT_FINGERING_BITS: tuple[tuple[int, str], ...] = (
    (0x0020, "1"),
    (0x0040, "2"),
    (0x0080, "3"),
    (0x0100, "4"),
)
_LEFT_ORNAMENT_HIGH_BYTES = {
    0x0400: "#",
    0x0800: "+",
    0x0C00: "x",
    0x1600: "'",
    0x2200: "caret",
}
_RIGHT_ORNAMENT_HIGH_BYTES = {
    0x0600: "#",
    0x0E00: "x",
    0x1000: ",",
    0x1400: "'",
    0x1800: "smile",
    0x2000: "caret",
}
_ARPEGGIO_HIGH_BYTE_PATTERNS = {
    0x0200: "single",
    0x4A00: "bottom",
    0x4E00: "middle",
    0x5200: "top",
}


def _pick_single_flag(extras: int, flags: tuple[tuple[int, str], ...]) -> tuple[str | None, int]:
    for bit, value in flags:
        if extras & bit:
            return value, bit
    return None, 0


def _decode_ornaments(high_byte: int) -> tuple[str | None, str | None, int]:
    left = _LEFT_ORNAMENT_HIGH_BYTES.get(high_byte)
    right = _RIGHT_ORNAMENT_HIGH_BYTES.get(high_byte)
    return left, right, high_byte if left or right else 0


def decode_ft3_extras(extras: int) -> DecodedFT3Extras:
    if extras <= 0:
        return DecodedFT3Extras(raw=extras)

    consumed = 0
    # The high-byte barre marker composes with low-byte fingering flags.
    barre = (extras & 0xFE00) == 0x3400
    if barre:
        consumed |= 0x3400
    right_fingering, used = _pick_single_flag(extras, _RIGHT_FINGERING_BITS)
    consumed |= used
    left_fingering, used = _pick_single_flag(extras, _LEFT_FINGERING_BITS)
    consumed |= used

    high_byte = extras & 0xFE00
    bass_course = 9 if high_byte == 0x3C00 else None
    if bass_course is not None:
        consumed |= high_byte
    arpeggio = _ARPEGGIO_HIGH_BYTE_PATTERNS.get(high_byte)
    if arpeggio is not None:
        consumed |= high_byte

    left_ornament, right_ornament, used = _decode_ornaments(high_byte)
    consumed |= used

    residual = extras & ~consumed
    return DecodedFT3Extras(
        raw=extras,
        barre=barre,
        right_fingering=right_fingering,
        left_fingering=left_fingering,
        right_ornament=right_ornament,
        left_ornament=left_ornament,
        arpeggio=arpeggio,
        bass_course=bass_course,
        residual=residual or None,
    )
