from __future__ import annotations

import re

from petrucci.render_text_lanes import MELODY_FILLED_NOTEHEAD_GLYPH, MELODY_NOTEHEAD_GLYPH
from petrucci.render_vocal import melody_row_count


def first_melody_row_idx(lines: list[str]) -> int:
    notehead_glyphs = (MELODY_NOTEHEAD_GLYPH, MELODY_FILLED_NOTEHEAD_GLYPH)
    block_rows = melody_row_count()
    for idx in range(len(lines)):
        if not lines[idx].startswith("  |"):
            continue
        if idx > 0 and lines[idx - 1].startswith("  |"):
            continue
        block = lines[idx : idx + block_rows]
        if len(block) < block_rows or not all(line.startswith("  |") for line in block):
            continue
        if any(
            ("\\" in line or any(glyph in line for glyph in notehead_glyphs) or "^" in line or "v" in line)
            for line in block
        ):
            return idx
    anchor = next(
        i
        for i, line in enumerate(lines)
        if line.startswith("  |")
        and ("\\" in line or any(glyph in line for glyph in notehead_glyphs) or "^" in line or "v" in line)
    )
    while anchor > 0 and (lines[anchor - 1].startswith("  |") or not lines[anchor - 1].strip()):
        anchor -= 1
    return anchor


def first_lyric_row(lines: list[str]) -> str:
    melody_start = first_melody_row_idx(lines)
    return next(
        line
        for idx, line in enumerate(lines)
        if idx >= melody_start + melody_row_count() and line.startswith("  |") and re.search(r"[A-Za-z]{2,}", line)
    )
