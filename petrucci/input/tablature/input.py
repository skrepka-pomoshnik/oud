"""Source-independent decoding for Oud's editable tablature cell grid."""

from __future__ import annotations

from collections.abc import Mapping

CellKey = tuple[int, int, int]
# Grid marker for an entered rest. It must never be a French or Italian fret glyph.
REST_OVERRIDE = "_"


def editor_event_columns(overrides: Mapping[CellKey, str], *, bar_index: int) -> tuple[int, ...]:
    """Return columns containing editor events or multi-cell continuations."""

    return tuple(sorted({col for bar, _string, col in overrides if bar == bar_index}))


def editor_rest_at(overrides: Mapping[CellKey, str], *, bar_index: int, column: int) -> bool:
    """Return whether an editor column holds an entered rest."""

    return any(
        value == REST_OVERRIDE and bar == bar_index and col == column
        for (bar, _string, col), value in overrides.items()
    )


def editor_fret_at(
    overrides: Mapping[CellKey, str],
    durations: Mapping[CellKey, int],
    *,
    bar_index: int,
    string_index: int,
    column: int,
    style: str,
    french_c_shape: str = "normal",
) -> int | None:
    """Decode one fret onset, including the editor's adjacent two-digit form."""

    key = (bar_index, string_index, column)
    text = overrides.get(key)
    if text is None or not text:
        return None
    if style == "italian":
        return _italian_fret_at(overrides, durations, key, text)
    letters = "abcdefghiklmnopqrst"
    if french_c_shape in {"alt", "historical"} and text == "r":
        return 2
    return letters.index(text) if text in letters else None


def _italian_fret_at(
    overrides: Mapping[CellKey, str],
    durations: Mapping[CellKey, int],
    key: CellKey,
    text: str,
) -> int | None:
    if _is_italian_continuation(overrides, durations, key):
        return None
    if text == "x":
        return 10
    if not text.isdigit():
        return None
    bar_index, string_index, column = key
    next_key = (bar_index, string_index, column + 1)
    continuation = overrides.get(next_key)
    if key in durations and continuation is not None and continuation.isdigit() and next_key not in durations:
        return int(text + continuation)
    return int(text)


def _is_italian_continuation(
    overrides: Mapping[CellKey, str],
    durations: Mapping[CellKey, int],
    key: CellKey,
) -> bool:
    bar_index, string_index, column = key
    if column <= 0 or key in durations:
        return False
    text = overrides.get(key)
    previous_key = (bar_index, string_index, column - 1)
    previous = overrides.get(previous_key)
    return bool(text and text.isdigit() and previous and previous.isdigit() and previous_key in durations)


__all__ = ["REST_OVERRIDE", "CellKey", "editor_event_columns", "editor_fret_at", "editor_rest_at"]
