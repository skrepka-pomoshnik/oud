from __future__ import annotations


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
    show_tactus: bool,
    double_stems: bool,
) -> dict[str, int | None]:
    _ = strings
    offset = 0
    meta = 0 if include_meta else None
    if include_meta:
        offset += 1
    tactus = offset if show_tactus else None
    if show_tactus:
        offset += 1
    ann = orn = slur = tie = hold = gliss = None
    if show_extras:
        # Local marks (annotations/ornaments/fingerings) are rendered inline; reserve
        # only one shared cue row for spans (slur/tie/hold/gliss).
        slur = offset
        tie = offset
        hold = offset
        gliss = offset
        offset += 1
    flag = offset
    flag2 = offset + 1 if double_stems else None
    offset += 2 if double_stems else 1
    dur = offset if show_dur else None
    staff = offset + (1 if show_dur else 0)
    return {
        "meta": meta,
        "ann": ann,
        "orn": orn,
        "tactus": tactus,
        "slur": slur,
        "tie": tie,
        "hold": hold,
        "gliss": gliss,
        "flag": flag,
        "flag2": flag2,
        "dur": dur,
        "staff": staff,
    }


def block_height(
    include_meta: bool,
    strings: int,
    show_dur: bool,
    show_extras: bool,
    show_tactus: bool,
    double_stems: bool,
) -> int:
    height = strings + 1
    if include_meta:
        height += 1
    if show_tactus:
        height += 1
    height += 1
    if double_stems:
        height += 1
    if show_dur:
        height += 1
    if show_extras:
        height += 1
    return height
