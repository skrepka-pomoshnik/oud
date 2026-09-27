from __future__ import annotations

from petrucci.input.tablature.mutation import (
    chord_index_at_col,
    delete_chord,
    insert_chord,
    set_chord_note,
)

__all__ = ["chord_index_at_col", "delete_chord", "insert_chord", "set_chord_note"]


def duration_value(key: int, style: str) -> int | None:
    """Map a French duration digit; Italian digits are frets and use the `;` prefix."""
    french_map = {
        ord("1"): 1,
        ord("2"): 2,
        ord("3"): 4,
        ord("4"): 8,
        ord("5"): 16,
        ord("6"): 32,
        ord("7"): 64,
    }
    if style == "italian":
        return None
    return french_map.get(key)


def denom_to_note_type(denom: int) -> int | None:
    mapping = {
        1: 2,
        2: 3,
        4: 4,
        8: 5,
        16: 6,
        32: 7,
        64: 8,
        128: 9,
        256: 10,
    }
    return mapping.get(denom)


def is_french_fret(ch: str) -> bool:
    return ch in "abcdefghiklmnopqrst"


def is_italian_fret(ch: str) -> bool:
    return ch.isdigit() or ch == "x"


def french_to_fret(ch: str) -> int | None:
    letters = "abcdefghiklmnopqrst"
    if ch in letters:
        return letters.index(ch)
    return None


def fret_to_french(fret: int) -> str | None:
    letters = "abcdefghiklmnopqrst"
    if 0 <= fret < len(letters):
        return letters[fret]
    return None


_MIN_FRET = 0
_MAX_SINGLE_DIGIT_FRET = 9
_ITALIAN_X_FRET = 10


def italian_to_fret(ch: str) -> int | None:
    if ch.isdigit():
        return int(ch)
    if ch == "x":
        return 10
    return None


def fret_to_italian(fret: int) -> str | None:
    if _MIN_FRET <= fret <= _MAX_SINGLE_DIGIT_FRET:
        return str(fret)
    if fret == _ITALIAN_X_FRET:
        return "x"
    return None
