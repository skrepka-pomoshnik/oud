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
    editorial_brackets: bool = False
    layout_flags: int | None = None
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
    0x1C00: "parenthesis",
    0x2200: "caret",
}
_RIGHT_ORNAMENT_HIGH_BYTES = {
    0x0600: "#",
    0x0A00: "+",
    0x0E00: "x",
    0x1000: ",",
    0x1400: "'",
    0x1800: "smile",
    0x2000: "caret",
    0x2400: "under-v",
    0x2800: "under-hook",
    0x4000: "*",
}
_ARPEGGIO_HIGH_BYTE_PATTERNS = {
    0x0200: "single",
    0x4A00: "bottom",
    0x4E00: "middle",
    0x5200: "top",
}
_HIGH_RIGHT_FINGERING_PATTERNS = {
    0x4800: "dot1",
    0x5A00: "dot2",
}
_LAYOUT_HIGH_BYTE_PATTERNS = frozenset((0x5800, 0x8000))


def _pick_single_flag(extras: int, flags: tuple[tuple[int, str], ...]) -> tuple[str | None, int]:
    for bit, value in flags:
        if extras & bit:
            return value, bit
    return None, 0


def _pick_fingering_flags(extras: int, flags: tuple[tuple[int, str], ...]) -> tuple[str | None, int]:
    selected = [(bit, value) for bit, value in flags if extras & bit]
    if not selected:
        return None, 0
    return "+".join(value for _bit, value in selected), sum(bit for bit, _value in selected)


def _decode_ornaments(high_byte: int) -> tuple[str | None, str | None, int]:
    left = _LEFT_ORNAMENT_HIGH_BYTES.get(high_byte)
    right = _RIGHT_ORNAMENT_HIGH_BYTES.get(high_byte)
    return left, right, high_byte if left or right else 0


def decode_ft3_extras(extras: int) -> DecodedFT3Extras:
    if extras <= 0:
        return DecodedFT3Extras(raw=extras)

    consumed = 0
    high_byte = extras & 0xFE00
    # Barre and bracket placement variants compose with low-byte fingering flags.
    barre = high_byte in {0x3400, 0x3A00}
    if barre:
        consumed |= high_byte
    right_fingering, used = _pick_single_flag(extras, _RIGHT_FINGERING_BITS)
    consumed |= used
    left_fingering, used = _pick_fingering_flags(extras, _LEFT_FINGERING_BITS)
    consumed |= used

    high_right_fingering = _HIGH_RIGHT_FINGERING_PATTERNS.get(high_byte)
    if right_fingering is None and high_right_fingering is not None:
        right_fingering = high_right_fingering
        consumed |= high_byte
    layout_flags = high_byte if high_byte in _LAYOUT_HIGH_BYTE_PATTERNS else 0
    consumed |= layout_flags
    editorial_brackets = high_byte == 0x3600
    if editorial_brackets:
        consumed |= high_byte
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
        editorial_brackets=editorial_brackets,
        layout_flags=layout_flags or None,
        residual=residual or None,
    )
