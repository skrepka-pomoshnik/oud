from __future__ import annotations

from petrucci.model import Bar, Note, Piece
from petrucci.render_utils import (
    bar_cells,
    bar_cells_from_chords,
    chord_positions,
    duration_display,
    duration_flag,
    flag_count,
    flag_positions_from_durations,
    place_duration_cells,
)
from petrucci.tab_policy import (
    gliss_span_chars,
    hold_span_chars,
    slur_span_chars,
    tie_notehead_hidden_cols,
    tie_notehead_parenthesize_cols,
    tie_span_chars,
)
from petrucci.view_width import (
    _bar_compact_width,
    _bar_display_width,
    _bars_fit,
    _infer_time_signature,
    _inline_bass_row,
    _next_system_start,
    _scale_col,
    _scale_row,
    _string_label,
    _tuning_labels,
)

__all__ = [
    "_bar_compact_width",
    "_bar_display_width",
    "_bars_fit",
    "_infer_time_signature",
    "_inline_bass_row",
    "_next_system_start",
    "_scale_col",
    "_scale_row",
    "_string_label",
    "_tuning_labels",
    "build_bar_view",
    "flag_count",
]


def _parse_time_signature(value: str) -> tuple[int, int, str]:
    text = value.strip()
    if text in ("C", "c", "4/4"):
        return 4, 4, "C"
    if text in ("C|", "c|", "2/2"):
        return 2, 2, "C|"
    if text in ("O", "o", "3/4"):
        return 3, 4, "O"
    if "/" in text:
        parts = text.split("/", 1)
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            beats = int(parts[0])
            unit = int(parts[1])
            return max(1, beats), max(1, unit), f"{beats}/{unit}"
    return 0, 0, ""


def _tactus_row(bar_width: int, beats: int) -> list[str]:
    row = [" " for _ in range(bar_width)]
    if beats <= 0:
        return row
    for i in range(beats):
        pos = int(i * bar_width / beats)
        if 0 <= pos < bar_width:
            row[pos] = "|"
    return row


def _filter_redundant_positions(
    positions: list[tuple[int, int, bool]],
    default_duration: int = 4,
) -> list[tuple[int, int, bool]]:
    if not positions:
        return []
    filtered: list[tuple[int, int, bool]] = []
    prev_denom = default_duration
    prev_dot = False
    for idx, (col, denom, dot) in enumerate(positions):
        if idx == 0:
            filtered.append((col, denom, dot))
            prev_denom = denom
            prev_dot = dot
            continue
        if denom != prev_denom or dot != prev_dot:
            filtered.append((col, denom, dot))
            prev_denom = denom
            prev_dot = dot
    return filtered


def _fallback_redundant_positions(
    positions: list[tuple[int, int, bool]],
    *,
    hide_redundant: bool,
    default_duration: int,
) -> list[tuple[int, int, bool]]:
    if hide_redundant:
        return _filter_redundant_positions(positions, default_duration)
    return positions


def _beamified_chord_flag_positions(  # noqa: C901, PLR0912
    bar: Bar,
    positions: list[tuple[int, int, bool]],
    *,
    hide_redundant: bool = True,
    default_duration: int = 4,
) -> list[tuple[int, int, bool]]:
    if not positions:
        return []
    chords = [chord for chord in (bar.chords or []) if chord.notes]
    if not chords or len(chords) != len(positions):
        return _fallback_redundant_positions(
            positions,
            hide_redundant=hide_redundant,
            default_duration=default_duration,
        )
    if not any(chord.grid for chord in chords):
        return _fallback_redundant_positions(
            positions,
            hide_redundant=hide_redundant,
            default_duration=default_duration,
        )

    filtered: list[tuple[int, int, bool]] = []
    prev_global_denom = default_duration
    prev_global_dot = False
    in_group = False
    prev_group_denom: int | None = None
    prev_group_dot: bool | None = None

    for idx, (chord, pos) in enumerate(zip(chords, positions, strict=False)):
        col, denom, dot = pos
        marker = chord.grid
        show = False
        if idx == 0 and not hide_redundant:
            show = True
        if marker == "start":
            in_group = True
            prev_group_denom = None
            prev_group_dot = None
            show = True
        elif marker in {"mid", "end"} and in_group:
            if not hide_redundant or denom != prev_group_denom or dot != prev_group_dot:
                show = True
            if marker == "end":
                in_group = False
        else:
            if in_group:
                in_group = False
            if idx == 0 or not hide_redundant or denom != prev_global_denom or dot != prev_global_dot:
                show = True

        if show:
            filtered.append((col, denom, dot))
        prev_global_denom = denom
        prev_global_dot = dot
        if marker in {"start", "mid", "end"}:
            prev_group_denom = denom
            prev_group_dot = dot
    return filtered


def _bar_number_for_index(  # noqa: C901
    piece: Piece,
    bar_index: int,
    measures: str,
    countdots: str,
    step: int,
    *,
    system_start: bool = False,
) -> str | None:
    extra = 0
    if countdots == "on":
        for idx in range(bar_index + 1):
            if piece.bars[idx].repeat == ".":
                extra += 1
    number = bar_index + 1 + extra
    if measures == "system":
        return str(number) if system_start else None
    if measures == "every":
        if step <= 0:
            step = 1
        if bar_index > 0 and number % step == 0:
            return f"[{number}]"
        return None
    if measures == "five":
        return f"[{number}]" if number % 5 == 0 else None
    if measures == "start":
        return f"[{number}]" if bar_index == 0 else None
    return None


def _bar_durations(  # noqa: C901
    durations: dict[tuple[int, int, int], int],
    bar_index: int,
    strings: int,
    bar_width: int,
    default_duration: int,
    *,
    hide_redundant: bool = True,
    dotted: set[tuple[int, int]] | None = None,
) -> list[str]:
    row = [" " for _ in range(bar_width)]
    last: int | None = None
    last_dot = False
    for col in range(bar_width):
        found = None
        for s_idx in range(strings):
            key = (bar_index, s_idx, col)
            if key in durations:
                denom = durations[key]
                if found is None or denom > found:
                    found = denom
        denom = found if found is not None else default_duration
        if hide_redundant:
            if found is None:
                continue
            is_dotted = dotted is not None and (bar_index, col) in dotted
            if denom != last or is_dotted != last_dot:
                place_duration_cells(row, col, denom, is_dotted)
                last = denom
                last_dot = is_dotted
        else:
            is_dotted = dotted is not None and (bar_index, col) in dotted
            place_duration_cells(row, col, denom, is_dotted)
    return row


def _flag_positions_all(  # noqa: PLR0917 - legacy grid projection pending a typed input record
    durations: dict[tuple[int, int, int], int],
    bar_index: int,
    strings: int,
    bar_width: int,
    default_duration: int,
    dotted: set[tuple[int, int]] | None = None,
) -> list[tuple[int, int, bool]]:
    has_duration = any(b == bar_index for (b, _s, _c) in durations)
    if not has_duration:
        return [(col, default_duration, False) for col in range(bar_width)]
    return flag_positions_from_durations(
        durations,
        bar_index=bar_index,
        strings=strings,
        bar_width=bar_width,
        default_duration=default_duration,
        dotted=dotted,
    )


def _bar_annotations(
    annotations: dict[tuple[int, int], str],
    bar_index: int,
    bar_width: int,
) -> list[str]:
    row = [" " for _ in range(bar_width)]
    for col in range(bar_width):
        key = (bar_index, col)
        if key in annotations:
            text = annotations[key]
            if text:
                row[col] = text[0]
    return row


def _bar_ornaments(
    ornaments: dict[tuple[int, int], str],
    bar_index: int,
    bar_width: int,
) -> list[str]:
    row = [" " for _ in range(bar_width)]
    for col in range(bar_width):
        key = (bar_index, col)
        if key in ornaments:
            row[col] = ornaments[key]
    return row


def _pick_side_value(
    *,
    left: str | None,
    right: str | None,
    mode: str,
) -> str | None:
    if mode == "off":
        return None
    if mode == "left":
        return left
    if mode == "right":
        return right
    return left or right


def _ft3_fingering_glyph(value: str | None) -> str | None:
    if not value:
        return None
    if value == "thumb":
        return "t"
    if value == "dot1":
        return "\u0323"  # combining dot below
    if value == "dot2":
        return "\u0324"  # combining diaeresis below
    if value == "dot3":
        return "\u20e8"  # combining triple underdot
    return value[0]


def _ft3_display_fingering_for_note(note: Note, *, fingering_mode: str) -> str | None:
    left_value = note.left_fingering
    # Sanity rule: LH 1-4 on an open string is usually not a usable fingering cue.
    if note.fret == 0 and left_value in {"1", "2", "3", "4"}:
        left_value = None
    right_value = note.right_fingering
    if fingering_mode == "off":
        return None
    left_enabled = fingering_mode in {"left", "both"}
    right_enabled = fingering_mode in {"right", "both"}
    left_glyph = _ft3_fingering_glyph(left_value) if left_enabled else None
    right_glyph = _ft3_fingering_glyph(right_value) if right_enabled else None
    if right_enabled and right_value in {"dot1", "dot2", "dot3"} and right_glyph is not None:
        if left_glyph:
            # RH dotted-finger cue attaches to the fingering mark itself (e.g. 2̈).
            return left_glyph + right_glyph
        # RH dotted-finger cue with no LH digit attaches directly to the note glyph.
        return right_glyph
    picked = _pick_side_value(left=left_value, right=right_value, mode=fingering_mode)
    return _ft3_fingering_glyph(picked)


def _ft3_ornament_glyph(value: str | None) -> str | None:
    if not value:
        return None
    mapping = {
        "dot-left": "\u0307",
        "brackets": "[",
        "caret": "^",
        "parenthesis": "(",
        "smile": "\u2323",
        "under-v": "\u032c",
        "under-hook": "\u02db",
    }
    return mapping.get(value, value[0])


def _merge_mark_rows(base: list[str], user: list[str]) -> list[str]:
    if len(base) != len(user):
        return user
    out = list(base)
    for idx, ch in enumerate(user):
        if ch != " ":
            out[idx] = ch
    return out


def _place_parenthesize_tie_cues(  # noqa: C901
    *,
    ann_cells: list[str],
    orn_cells: list[str],
    tie_cells: list[str],
    slur_cells: list[str] | None,
    hold_cells: list[str] | None,
    gliss_cells: list[str] | None,
    paren_tie_cols: set[int],
    allow_ann_row: bool = True,
) -> None:
    def _place_open(end_col: int) -> None:
        if allow_ann_row and 0 <= end_col < len(ann_cells) and ann_cells[end_col] == " ":
            ann_cells[end_col] = "("
            return
        for row in (tie_cells, slur_cells or [], hold_cells or [], gliss_cells or []):
            left = end_col - 1
            while 0 <= left < len(row):
                if row[left] == " ":
                    row[left] = "("
                    return
                left -= 1

    def _place_close(end_col: int) -> None:
        for row in (tie_cells, orn_cells, slur_cells or [], hold_cells or [], gliss_cells or []):
            if 0 <= end_col < len(row) and row[end_col] == " ":
                row[end_col] = ")"
                return

    for end_col in paren_tie_cols:
        if not (0 <= end_col < len(tie_cells)):
            continue
        _place_open(end_col)
        _place_close(end_col)


def _bar_imported_ft3_annotations(  # noqa: C901
    bar: Bar,
    *,
    bar_width: int,
    default_duration: int,
    fingering_mode: str = "both",
) -> list[str]:
    row = [" " for _ in range(bar_width)]
    if fingering_mode == "off" or not bar.chords:
        return row
    positions = chord_positions(bar, bar_width, default_duration)
    for idx, chord in enumerate(bar.chords):
        if idx >= len(positions):
            break
        col = positions[idx][0]
        if not (0 <= col < bar_width):
            continue
        glyph = None
        for note in chord.notes:
            glyph = _ft3_display_fingering_for_note(note, fingering_mode=fingering_mode)
            if glyph:
                break
        if glyph is None and any(getattr(note, "barre", False) for note in chord.notes):
            glyph = "["
        if glyph and row[col] == " ":
            row[col] = glyph
    return row


def _bar_imported_ft3_ornaments(  # noqa: C901
    bar: Bar,
    *,
    bar_width: int,
    default_duration: int,
    ornament_mode: str = "both",
) -> list[str]:
    row = [" " for _ in range(bar_width)]
    if ornament_mode == "off" or not bar.chords:
        return row
    positions = chord_positions(bar, bar_width, default_duration)
    for idx, chord in enumerate(bar.chords):
        if idx >= len(positions):
            break
        col = positions[idx][0]
        if not (0 <= col < bar_width):
            continue
        glyph = ":" if any(note.arpeggio for note in chord.notes) else None
        for note in chord.notes:
            if glyph:
                break
            picked = _pick_side_value(
                left=note.left_ornament,
                right=note.right_ornament,
                mode=ornament_mode,
            )
            glyph = _ft3_ornament_glyph(picked)
            if glyph:
                break
        if glyph and row[col] == " ":
            row[col] = glyph
    return row


def _bar_span_row(  # noqa: PLR0917 - span glyphs form one compact rendering operation
    spans: list[tuple[int, int, int]],
    bar_index: int,
    bar_width: int,
    start_char: str,
    end_char: str,
    fill_char: str,
) -> list[str]:
    row = [" " for _ in range(bar_width)]
    for b, start, end in spans:
        if b != bar_index:
            continue
        start_pos = max(0, min(bar_width - 1, start))
        end_pos = max(0, min(bar_width - 1, end))
        if start_pos == end_pos:
            row[start_pos] = start_char
            continue
        if start_pos > end_pos:
            start_pos, end_pos = end_pos, start_pos
        row[start_pos] = start_char
        for col in range(start_pos + 1, end_pos):
            row[col] = fill_char
        row[end_pos] = end_char
    return row


def _bar_flags(
    durations: dict[tuple[int, int, int], int],
    bar_index: int,
    strings: int,
    bar_width: int,
    default_duration: int,
    *,
    hide_redundant: bool = True,
) -> list[str]:
    row = [" " for _ in range(bar_width)]
    for col in range(bar_width):
        found = None
        for s_idx in range(strings):
            key = (bar_index, s_idx, col)
            if key in durations:
                denom = durations[key]
                if found is None or denom > found:
                    found = denom
        denom = found if found is not None else default_duration
        if hide_redundant:
            if found is None:
                continue
            row[col] = duration_flag(denom)
        else:
            row[col] = duration_flag(denom)
    return row


def build_bar_view(  # noqa: C901, PLR0917 - public compatibility; replace options with a typed view request
    bar: Bar,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    ornaments: dict[tuple[int, int], str],
    annotations: dict[tuple[int, int], str],
    slurs: list[tuple[int, int, int]],
    ties: list[tuple[int, int, int]],
    holds: list[tuple[int, int, int]],
    bar_index: int,
    strings: int,
    bar_width: int,
    default_duration: int,
    style: str,
    *,
    french_c: str = "normal",
    slurcuestyle: str = "paren",
    tiecuestyle: str = "bracket",
    tienoteheads: str = "show",
    holdcuestyle: str = "angle",
    glisses: list[tuple[int, int, int]] | None = None,
    glisscuestyle: str = "hide",
    showft3extras: str = "on",
    ft3fingering: str = "both",
    ft3ornaments: str = "both",
    showfingerings: str | None = None,
    showornaments: str | None = None,
) -> dict[str, list[str]]:
    if glisses is None:
        glisses = []
    bar_cells_data = (
        bar_cells_from_chords(
            bar,
            strings,
            bar_width,
            default_duration,
            style,
            french_c=french_c,
        )
        if bar.chords
        else bar_cells(
            bar,
            strings,
            bar_width,
            style,
            french_c=french_c,
        )
    )
    for (b, s, col), ch in overrides.items():
        if b != bar_index:
            continue
        if s >= strings or col >= bar_width:
            continue
        bar_cells_data[s][col] = ch
    hidden_tie_cols = tie_notehead_hidden_cols(ties, bar_index=bar_index, mode=tienoteheads)
    paren_tie_cols = tie_notehead_parenthesize_cols(ties, bar_index=bar_index, mode=tienoteheads)
    for hide_col in hidden_tie_cols:
        if not (0 <= hide_col < bar_width):
            continue
        for row_cells in bar_cells_data:
            if row_cells[hide_col] != "-":
                row_cells[hide_col] = "-"
    flag_cells = _bar_flags(
        durations,
        bar_index,
        strings,
        bar_width,
        default_duration,
    )
    dur_cells = _bar_durations(
        durations,
        bar_index,
        strings,
        bar_width,
        default_duration,
    )
    if not any(b == bar_index for (b, _s, _c) in durations):
        override_cols = {col for (b, _s, col) in overrides if b == bar_index and col < bar_width}
        for col in override_cols:
            dur_cells[col] = duration_display(default_duration)
    imported_ann = [" " for _ in range(bar_width)]
    imported_orn = [" " for _ in range(bar_width)]
    show_fingerings = (showfingerings or showft3extras) == "on"
    show_ornaments_value = (showornaments or showft3extras) == "on"
    if show_fingerings:
        imported_ann = _bar_imported_ft3_annotations(
            bar,
            bar_width=bar_width,
            default_duration=default_duration,
            fingering_mode=ft3fingering,
        )
    if show_ornaments_value:
        imported_orn = _bar_imported_ft3_ornaments(
            bar,
            bar_width=bar_width,
            default_duration=default_duration,
            ornament_mode=ft3ornaments,
        )
    ann_cells = _merge_mark_rows(imported_ann, _bar_annotations(annotations, bar_index, bar_width))
    local_orn_cells = (
        _bar_ornaments(ornaments, bar_index, bar_width) if show_ornaments_value else [" " for _ in range(bar_width)]
    )
    orn_cells = _merge_mark_rows(imported_orn, local_orn_cells)
    slur_chars = slur_span_chars(slurcuestyle)
    slur_cells = (
        [" " for _ in range(bar_width)]
        if slur_chars is None
        else _bar_span_row(slurs, bar_index, bar_width, *slur_chars)
    )
    tie_chars = tie_span_chars(tiecuestyle)
    tie_cells = (
        [" " for _ in range(bar_width)] if tie_chars is None else _bar_span_row(ties, bar_index, bar_width, *tie_chars)
    )
    hold_chars = hold_span_chars(holdcuestyle)
    hold_cells = (
        [" " for _ in range(bar_width)]
        if hold_chars is None
        else _bar_span_row(holds, bar_index, bar_width, *hold_chars)
    )
    gliss_chars = gliss_span_chars(glisscuestyle)
    gliss_cells = (
        [" " for _ in range(bar_width)]
        if gliss_chars is None
        else _bar_span_row(glisses, bar_index, bar_width, *gliss_chars)
    )
    _place_parenthesize_tie_cues(
        ann_cells=ann_cells,
        orn_cells=orn_cells,
        tie_cells=tie_cells,
        slur_cells=slur_cells,
        hold_cells=hold_cells,
        gliss_cells=gliss_cells,
        paren_tie_cols=paren_tie_cols,
    )
    rows = ["".join(bar_cells_data[s_idx]) for s_idx in range(strings)]
    return {
        "ann": ["".join(ann_cells)],
        "orn": ["".join(orn_cells)],
        "slur": ["".join(slur_cells)],
        "tie": ["".join(tie_cells)],
        "hold": ["".join(hold_cells)],
        "gliss": ["".join(gliss_cells)],
        "flag": ["".join(flag_cells)],
        "dur": ["".join(dur_cells)],
        "rows": rows,
    }
