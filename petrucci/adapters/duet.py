from __future__ import annotations

import copy
from dataclasses import replace
from typing import Literal, TypeVar

from petrucci.core.model import Piece

T = TypeVar("T")
DuetStorageMode = Literal["halves", "interleaved"]

# Fallback parity for legacy/synthetic interleaved duet-score ordering.
_TOP_STAFF_RAW_PARITY = 1


def _raw_matches_staff(raw_bar_index: int, staff_index: int) -> bool:
    parity = _TOP_STAFF_RAW_PARITY if staff_index == 0 else 1 - _TOP_STAFF_RAW_PARITY
    return raw_bar_index % 2 == parity


def is_duet_score_piece(piece: Piece) -> bool:
    part = (piece.part or "").strip().lower()
    if part != "score":
        return False
    labels = _ensemble_duet_labels(piece.ensemble)
    minimum_duet_bars = 2
    return labels is not None and len(piece.bars) >= minimum_duet_bars


def duet_storage_mode(piece: Piece) -> DuetStorageMode:
    """Detect duet score raw-bar storage layout.

    Current FT3 score corpus uses sequential halves (all bars for lute 1, then
    all bars for lute 2). Keep an interleaved fallback for synthetic fixtures
    and future score variants.
    """
    if not is_duet_score_piece(piece):
        return "interleaved"
    if len(piece.bars) % 2 == 0:
        return "halves"
    return "interleaved"


def _ensemble_duet_labels(ensemble: str | None) -> tuple[str, str] | None:
    text = (ensemble or "").strip()
    if not text:
        return None
    parts = [p.strip() for p in text.split(",") if p.strip()]
    labels: list[str] = []
    for part in parts:
        label = part.split(":", 1)[0].strip()
        if label:
            labels.append(label)
    minimum_duet_labels = 2
    if len(labels) < minimum_duet_labels:
        return None
    if not all("lute" in label.lower() for label in labels[:2]):
        return None
    return (labels[0], labels[1])


def duet_staff_labels(piece: Piece) -> tuple[str, str]:
    labels = _ensemble_duet_labels(piece.ensemble)
    if labels is not None:
        left, right = labels
        return (left[:1].upper() + left[1:], right[:1].upper() + right[1:])
    return ("Lute 1", "Lute 2")


def duet_logical_bar_count(piece: Piece) -> int:
    if duet_storage_mode(piece) == "halves":
        return len(piece.bars) // 2
    return (len(piece.bars) + 1) // 2


def duet_bar_mapping(
    raw_bar_index: int,
    *,
    piece: Piece | None = None,
) -> tuple[int, int]:
    """Map raw bar index -> (staff_index, logical_bar_index).

    If `piece` is omitted, the legacy interleaved mapping is used.
    """
    if piece is not None and duet_storage_mode(piece) == "halves":
        half = duet_logical_bar_count(piece)
        if raw_bar_index < half:
            return (0, raw_bar_index)
        return (1, max(0, raw_bar_index - half))
    staff_index = 0 if _raw_matches_staff(raw_bar_index, 0) else 1
    return (staff_index, raw_bar_index // 2)


def duet_raw_bar_index(
    staff_index: int,
    logical_bar_index: int,
    *,
    piece: Piece | None = None,
) -> int:
    if piece is not None and duet_storage_mode(piece) == "halves":
        half = duet_logical_bar_count(piece)
        return logical_bar_index if staff_index == 0 else half + logical_bar_index
    parity = _TOP_STAFF_RAW_PARITY if staff_index == 0 else 1 - _TOP_STAFF_RAW_PARITY
    return logical_bar_index * 2 + parity


def _duet_staff_raw_indices(piece: Piece, staff_index: int) -> list[int]:
    if duet_storage_mode(piece) == "halves":
        half = duet_logical_bar_count(piece)
        start = 0 if staff_index == 0 else half
        end = half if staff_index == 0 else len(piece.bars)
        return list(range(start, end))
    start = _TOP_STAFF_RAW_PARITY if staff_index == 0 else 1 - _TOP_STAFF_RAW_PARITY
    return list(range(start, len(piece.bars), 2))


def split_duet_piece_staff(piece: Piece, staff_index: int) -> Piece:
    indices = _duet_staff_raw_indices(piece, staff_index)
    mate_indices = _duet_staff_raw_indices(piece, 1 - staff_index)
    bars = [copy.deepcopy(piece.bars[idx]) for idx in indices]
    mate_bars = [piece.bars[idx] for idx in mate_indices]
    for idx, bar in enumerate(bars):
        mate = mate_bars[idx] if idx < len(mate_bars) else None
        if bar.time_sig is None and mate is not None and mate.time_sig:
            bar.time_sig = mate.time_sig
    return replace(piece, bars=bars)


def split_duet_triplet_map(
    data: dict[tuple[int, int, int], T],
    *,
    staff_index: int,
    piece: Piece | None = None,
) -> dict[tuple[int, int, int], T]:
    out: dict[tuple[int, int, int], T] = {}
    for key, value in data.items():
        raw_bar, a, b = key
        raw_staff, logical = duet_bar_mapping(raw_bar, piece=piece)
        if raw_staff != staff_index:
            continue
        out[(logical, a, b)] = value
    return out


def split_duet_pair_map(
    data: dict[tuple[int, int], T],
    *,
    staff_index: int,
    piece: Piece | None = None,
) -> dict[tuple[int, int], T]:
    out: dict[tuple[int, int], T] = {}
    for (raw_bar, a), value in data.items():
        raw_staff, logical = duet_bar_mapping(raw_bar, piece=piece)
        if raw_staff != staff_index:
            continue
        out[(logical, a)] = value
    return out


def split_duet_triplet_set(
    data: set[tuple[int, int, int]],
    *,
    staff_index: int,
    piece: Piece | None = None,
) -> set[tuple[int, int, int]]:
    out: set[tuple[int, int, int]] = set()
    for raw_bar, a, b in data:
        raw_staff, logical = duet_bar_mapping(raw_bar, piece=piece)
        if raw_staff != staff_index:
            continue
        out.add((logical, a, b))
    return out


def split_duet_pair_set(
    data: set[tuple[int, int]],
    *,
    staff_index: int,
    piece: Piece | None = None,
) -> set[tuple[int, int]]:
    out: set[tuple[int, int]] = set()
    for raw_bar, a in data:
        raw_staff, logical = duet_bar_mapping(raw_bar, piece=piece)
        if raw_staff != staff_index:
            continue
        out.add((logical, a))
    return out


def split_duet_span_list(
    data: list[tuple[int, int, int]],
    *,
    staff_index: int,
    piece: Piece | None = None,
) -> list[tuple[int, int, int]]:
    out: list[tuple[int, int, int]] = []
    for raw_bar, start, end in data:
        raw_staff, logical = duet_bar_mapping(raw_bar, piece=piece)
        if raw_staff != staff_index:
            continue
        out.append((logical, start, end))
    return out


def duet_view_mode(settings: dict[str, str]) -> str:
    mode = settings.get("duetscoreview", "auto")
    if mode in {"both", "1", "2"}:
        return mode
    return "auto"
