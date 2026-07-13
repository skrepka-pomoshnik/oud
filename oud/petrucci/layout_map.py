from __future__ import annotations


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


def layout_block_rows(
    strings: int,
    include_meta: bool,
    show_dur: bool,
    show_extras: bool,
    show_tuplets: bool,
    show_tactus: bool,
    double_stems: bool,
    show_melody: bool = False,
    melody_rows_count: int = 1,
    show_lyrics: bool = False,
    lyric_rows_count: int = 0,
    vocal_pos: str = "bottom",
) -> dict[str, int | None]:
    _ = strings
    offset = 0
    meta = 0 if include_meta else None
    if include_meta:
        offset += 1
    tactus = offset if show_tactus else None
    if show_tactus:
        offset += 1
    ann = orn = slur = tie = hold = gliss = tuplet = None
    if show_extras or show_tuplets:
        # Local marks (annotations/ornaments/fingerings) are rendered inline; reserve
        # only one shared cue row for spans/tuplet cues.
        if show_extras:
            slur = offset
            tie = offset
            hold = offset
            gliss = offset
        if show_tuplets:
            tuplet = offset
        offset += 1
    actual_lyric_rows = _resolved_lyric_rows(show_lyrics, lyric_rows_count)
    actual_melody_rows = max(1, melody_rows_count) if show_melody else 0
    melody = None
    lyric_rows: tuple[int, ...] = ()
    if vocal_pos == "top":
        offset, melody, lyric_rows = _alloc_top_vocal_rows(
            offset,
            show_melody=show_melody,
            melody_rows=actual_melody_rows,
            lyric_rows=actual_lyric_rows,
        )
    flag = offset
    flag2 = offset + 1 if double_stems else None
    offset += 2 if double_stems else 1
    dur = offset if show_dur else None
    staff = offset + (1 if show_dur else 0)
    if vocal_pos != "top":
        melody, lyric_rows = _alloc_bottom_vocal_rows(
            staff=staff,
            strings=strings,
            show_melody=show_melody,
            melody_rows=actual_melody_rows,
            lyric_rows=actual_lyric_rows,
        )
    lyric = lyric_rows[0] if lyric_rows else None
    return {
        "meta": meta,
        "ann": ann,
        "orn": orn,
        "tactus": tactus,
        "slur": slur,
        "tie": tie,
        "hold": hold,
        "gliss": gliss,
        "tuplet": tuplet,
        "flag": flag,
        "flag2": flag2,
        "dur": dur,
        "staff": staff,
        "melody": melody,
        "lyric": lyric,
    }


def block_height(
    include_meta: bool,
    strings: int,
    show_dur: bool,
    show_extras: bool,
    show_tuplets: bool,
    show_tactus: bool,
    double_stems: bool,
    show_melody: bool = False,
    melody_rows_count: int = 1,
    show_lyrics: bool = False,
    lyric_rows_count: int = 0,
    vocal_pos: str = "bottom",
) -> int:
    _ = vocal_pos
    height = strings
    if include_meta:
        height += 1
    if show_tactus:
        height += 1
    height += 1
    if double_stems:
        height += 1
    if show_dur:
        height += 1
    if show_extras or show_tuplets:
        height += 1
    if show_melody:
        height += max(1, melody_rows_count)
    actual_lyric_rows = _resolved_lyric_rows(show_lyrics, lyric_rows_count)
    height += max(0, actual_lyric_rows)
    return height
