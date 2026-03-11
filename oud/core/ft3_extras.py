from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DecodedFT3Extras:
    raw: int
    right_fingering: str | None = None
    left_fingering: str | None = None
    right_ornament: str | None = None
    left_ornament: str | None = None
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
_ORNAMENT_PATTERNS: tuple[tuple[int, str, str], ...] = (
    # Patterns are adapted from luteconv's FT3 reverse-engineering, but decoded
    # compositionally here so they can coexist with fingering bits.
    (0x4A00, "left_ornament", "dot-left"),
    (0x3400, "left_ornament", "brackets"),
    (0x0600, "right_ornament", "#"),
    (0x0C00, "left_ornament", "x"),
    (0x0800, "left_ornament", "+"),
    (0x0400, "left_ornament", "#"),
)


def _pick_single_flag(extras: int, flags: tuple[tuple[int, str], ...]) -> tuple[str | None, int]:
    for bit, value in flags:
        if extras & bit:
            return value, bit
    return None, 0


def decode_ft3_extras(extras: int) -> DecodedFT3Extras:
    if extras <= 0:
        return DecodedFT3Extras(raw=extras)

    consumed = 0
    right_fingering, used = _pick_single_flag(extras, _RIGHT_FINGERING_BITS)
    consumed |= used
    left_fingering, used = _pick_single_flag(extras, _LEFT_FINGERING_BITS)
    consumed |= used

    right_ornament: str | None = None
    left_ornament: str | None = None
    for mask, target, value in _ORNAMENT_PATTERNS:
        if extras & mask != mask:
            continue
        consumed |= mask
        if target == "right_ornament":
            right_ornament = value
        else:
            left_ornament = value
        break

    residual = extras & ~consumed
    return DecodedFT3Extras(
        raw=extras,
        right_fingering=right_fingering,
        left_fingering=left_fingering,
        right_ornament=right_ornament,
        left_ornament=left_ornament,
        residual=residual or None,
    )
