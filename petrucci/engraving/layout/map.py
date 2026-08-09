from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class _LeadingRows:
    offset: int
    meta: int | None
    tactus: int | None
    slur: int | None
    tie: int | None
    hold: int | None
    gliss: int | None
    tuplet: int | None


@dataclass(frozen=True)
class LayoutBlockPolicy:
    strings: int
    include_meta: bool
    show_dur: bool
    show_extras: bool
    show_tuplets: bool
    show_tactus: bool
    double_stems: bool
    show_melody: bool = False
    melody_rows_count: int = 1
    show_lyrics: bool = False
    lyric_rows_count: int = 0
    vocal_pos: str = "bottom"


def _alloc_leading_rows(
    include_meta: bool,
    show_tactus: bool,
    show_extras: bool,
    show_tuplets: bool,
) -> _LeadingRows:
    offset = int(include_meta)
    meta = 0 if include_meta else None
    tactus = offset if show_tactus else None
    offset += int(show_tactus)
    cue = offset if show_extras or show_tuplets else None
    offset += int(cue is not None)
    span = cue if show_extras else None
    tuplet = cue if show_tuplets else None
    return _LeadingRows(offset, meta, tactus, span, span, span, span, tuplet)


def _resolved_lyric_rows(show_lyrics: bool, lyric_rows_count: int) -> int:
    return lyric_rows_count if lyric_rows_count > 0 else (1 if show_lyrics else 0)


def _alloc_top_vocal_rows(
    offset: int,
    *,
    show_melody: bool,
    melody_rows: int,
    lyric_rows: int,
) -> tuple[int, int | None, tuple[int, ...]]:
    melody = None
    lyric = ()
    next_offset = offset
    if show_melody:
        melody = next_offset
        next_offset += max(1, melody_rows)
    if lyric_rows > 0:
        lyric = tuple(next_offset + idx for idx in range(lyric_rows))
        next_offset += lyric_rows
    return next_offset, melody, lyric


def _alloc_bottom_vocal_rows(
    *,
    staff: int,
    strings: int,
    show_melody: bool,
    melody_rows: int,
    lyric_rows: int,
) -> tuple[int | None, tuple[int, ...]]:
    melody = None
    lyric = ()
    text_base = staff + strings
    if show_melody:
        melody = text_base
    if lyric_rows > 0:
        lyric_start = text_base + (max(1, melody_rows) if show_melody else 0)
        lyric = tuple(lyric_start + idx for idx in range(lyric_rows))
    return melody, lyric


def layout_rows(height: int, strings: int) -> dict[str, int | None]:
    if height <= 0:
        return {"header": None, "flag": None, "dur": None, "staff": None, "status": None}
    status_row = height - 1
    compact_needed = height < strings + 4
    if compact_needed:
        return {
            "header": None,
            "flag": None,
            "dur": None,
            "staff": 0,
            "status": status_row,
        }
    header_row = 1
    flag_row = header_row + 1
    dur_row = flag_row + 1
    staff_row = dur_row + 1
    return {
        "header": header_row,
        "flag": flag_row,
        "dur": dur_row,
        "staff": staff_row,
        "status": status_row,
    }


def layout_block_rows(policy: LayoutBlockPolicy) -> dict[str, int | None]:
    leading = _alloc_leading_rows(
        policy.include_meta,
        policy.show_tactus,
        policy.show_extras,
        policy.show_tuplets,
    )
    offset = leading.offset
    ann = orn = None
    actual_lyric_rows = _resolved_lyric_rows(policy.show_lyrics, policy.lyric_rows_count)
    actual_melody_rows = max(1, policy.melody_rows_count) if policy.show_melody else 0
    melody = None
    lyric_rows: tuple[int, ...] = ()
    if policy.vocal_pos == "top":
        offset, melody, lyric_rows = _alloc_top_vocal_rows(
            offset,
            show_melody=policy.show_melody,
            melody_rows=actual_melody_rows,
            lyric_rows=actual_lyric_rows,
        )
    flag = offset
    flag2 = offset + 1 if policy.double_stems else None
    offset += 2 if policy.double_stems else 1
    dur = offset if policy.show_dur else None
    staff = offset + (1 if policy.show_dur else 0)
    if policy.vocal_pos != "top":
        melody, lyric_rows = _alloc_bottom_vocal_rows(
            staff=staff,
            strings=policy.strings,
            show_melody=policy.show_melody,
            melody_rows=actual_melody_rows,
            lyric_rows=actual_lyric_rows,
        )
    lyric = lyric_rows[0] if lyric_rows else None
    return {
        "meta": leading.meta,
        "ann": ann,
        "orn": orn,
        "tactus": leading.tactus,
        "slur": leading.slur,
        "tie": leading.tie,
        "hold": leading.hold,
        "gliss": leading.gliss,
        "tuplet": leading.tuplet,
        "flag": flag,
        "flag2": flag2,
        "dur": dur,
        "staff": staff,
        "melody": melody,
        "lyric": lyric,
    }


def block_height(policy: LayoutBlockPolicy) -> int:
    height = policy.strings
    if policy.include_meta:
        height += 1
    if policy.show_tactus:
        height += 1
    height += 1
    if policy.double_stems:
        height += 1
    if policy.show_dur:
        height += 1
    if policy.show_extras or policy.show_tuplets:
        height += 1
    if policy.show_melody:
        height += max(1, policy.melody_rows_count)
    actual_lyric_rows = _resolved_lyric_rows(policy.show_lyrics, policy.lyric_rows_count)
    height += max(0, actual_lyric_rows)
    return height
