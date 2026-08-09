from __future__ import annotations

from dataclasses import dataclass

from petrucci.core.model import Bar, Note, Piece
from petrucci.engraving.layout.placement import place_parenthesize_tie_cues as _place_parenthesize_tie_cues
from petrucci.input.tablature.policy import (
    gliss_span_chars,
    hold_span_chars,
    slur_span_chars,
    tie_notehead_hidden_cols,
    tie_notehead_parenthesize_cols,
    tie_span_chars,
)
from petrucci.rendering.primitives.utils import (
    bar_cells,
    bar_cells_from_chords,
    chord_positions,
    duration_display,
    duration_flag,
    flag_count,
    flag_positions_from_durations,
    place_duration_cells,
)
from petrucci.terminal.view.width import (
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


@dataclass
class _BeamFlagState:
    global_denom: int
    global_dot: bool = False
    in_group: bool = False
    group_denom: int | None = None
    group_dot: bool | None = None


@dataclass(frozen=True)
class FlagPositionRequest:
    durations: dict[tuple[int, int, int], int]
    bar_index: int
    strings: int
    bar_width: int
    default_duration: int
    dotted: set[tuple[int, int]] | None = None


def _beam_flag_visible(
    marker: str | None,
    index: int,
    denom: int,
    dot: bool,
    *,
    hide_redundant: bool,
    state: _BeamFlagState,
) -> bool:
    if marker == "start":
        state.in_group = True
        state.group_denom = None
        state.group_dot = None
        return True
    if marker in {"mid", "end"} and state.in_group:
        visible = not hide_redundant or denom != state.group_denom or dot != state.group_dot
        if marker == "end":
            state.in_group = False
        return visible
    state.in_group = False
    return index == 0 or not hide_redundant or denom != state.global_denom or dot != state.global_dot


def _update_beam_flag_state(state: _BeamFlagState, marker: str | None, denom: int, dot: bool) -> None:
    state.global_denom = denom
    state.global_dot = dot
    if marker in {"start", "mid", "end"}:
        state.group_denom = denom
        state.group_dot = dot


def _beamified_chord_flag_positions(
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
    state = _BeamFlagState(global_denom=default_duration)

    for idx, (chord, pos) in enumerate(zip(chords, positions, strict=False)):
        col, denom, dot = pos
        marker = chord.grid
        if _beam_flag_visible(marker, idx, denom, dot, hide_redundant=hide_redundant, state=state):
            filtered.append((col, denom, dot))
        _update_beam_flag_state(state, marker, denom, dot)
    return filtered


def _bar_number_value(piece: Piece, bar_index: int, countdots: str) -> int:
    if countdots != "on":
        return bar_index + 1
    repeats = sum(piece.bars[index].repeat == "." for index in range(bar_index + 1))
    return bar_index + 1 + repeats


def _periodic_bar_number(number: int, bar_index: int, step: int) -> str | None:
    interval = max(1, step)
    return f"[{number}]" if bar_index > 0 and number % interval == 0 else None


def _multiple_bar_number(number: int, interval: int) -> str | None:
    return f"[{number}]" if number % interval == 0 else None


def _bar_number_for_index(
    piece: Piece,
    bar_index: int,
    measures: str,
    countdots: str,
    step: int,
    *,
    system_start: bool = False,
) -> str | None:
    number = _bar_number_value(piece, bar_index, countdots)
    if measures == "system":
        return str(number) if system_start else None
    if measures == "every":
        return _periodic_bar_number(number, bar_index, step)
    if measures == "five":
        return _multiple_bar_number(number, 5)
    if measures == "start":
        return f"[{number}]" if bar_index == 0 else None
    return None


def _duration_at_column(
    durations: dict[tuple[int, int, int], int],
    *,
    bar_index: int,
    strings: int,
    col: int,
) -> int | None:
    values = (
        durations[(bar_index, string_index, col)]
        for string_index in range(strings)
        if (bar_index, string_index, col) in durations
    )
    return max(values, default=None)


def _place_bar_duration(
    row: list[str],
    col: int,
    found: int | None,
    *,
    default_duration: int,
    is_dotted: bool,
    hide_redundant: bool,
    previous: tuple[int | None, bool],
) -> tuple[int | None, bool]:
    if hide_redundant and found is None:
        return previous
    denominator = found if found is not None else default_duration
    if not hide_redundant or (denominator, is_dotted) != previous:
        place_duration_cells(row, col, denominator, is_dotted)
        return denominator, is_dotted
    return previous


def _bar_durations(
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
        found = _duration_at_column(durations, bar_index=bar_index, strings=strings, col=col)
        last, last_dot = _place_bar_duration(
            row,
            col,
            found,
            default_duration=default_duration,
            is_dotted=dotted is not None and (bar_index, col) in dotted,
            hide_redundant=hide_redundant,
            previous=(last, last_dot),
        )
    return row


def _flag_positions_all(request: FlagPositionRequest) -> list[tuple[int, int, bool]]:
    has_duration = any(b == request.bar_index for (b, _s, _c) in request.durations)
    if not has_duration:
        return [(col, request.default_duration, False) for col in range(request.bar_width)]
    return flag_positions_from_durations(
        request.durations,
        bar_index=request.bar_index,
        strings=request.strings,
        bar_width=request.bar_width,
        default_duration=request.default_duration,
        dotted=request.dotted,
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


def _chord_fingering(chord, *, fingering_mode: str) -> str | None:
    glyph = next(
        (
            glyph
            for note in chord.notes
            if (glyph := _ft3_display_fingering_for_note(note, fingering_mode=fingering_mode))
        ),
        None,
    )
    if glyph is None and any(
        getattr(note, "barre", False) or getattr(note, "editorial_brackets", False) for note in chord.notes
    ):
        return "["
    return glyph


def _bar_imported_ft3_annotations(
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
    for chord, (col, _denominator, _dotted) in zip(bar.chords, positions, strict=False):
        if not (0 <= col < bar_width):
            continue
        glyph = _chord_fingering(chord, fingering_mode=fingering_mode)
        if glyph and row[col] == " ":
            row[col] = glyph
    return row


def _chord_ornament(chord, *, ornament_mode: str) -> str | None:
    if any(note.arpeggio for note in chord.notes):
        return ":"
    for note in chord.notes:
        picked = _pick_side_value(left=note.left_ornament, right=note.right_ornament, mode=ornament_mode)
        glyph = _ft3_ornament_glyph(picked)
        if glyph:
            return glyph
    return None


def _bar_imported_ft3_ornaments(
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
    for chord, (col, _denominator, _dotted) in zip(bar.chords, positions, strict=False):
        if not (0 <= col < bar_width):
            continue
        glyph = _chord_ornament(chord, ornament_mode=ornament_mode)
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


@dataclass(frozen=True)
class _BarViewRequest:
    bar: Bar
    overrides: dict[tuple[int, int, int], str]
    durations: dict[tuple[int, int, int], int]
    ornaments: dict[tuple[int, int], str]
    annotations: dict[tuple[int, int], str]
    slurs: list[tuple[int, int, int]]
    ties: list[tuple[int, int, int]]
    holds: list[tuple[int, int, int]]
    glisses: list[tuple[int, int, int]]
    bar_index: int
    strings: int
    bar_width: int
    default_duration: int
    style: str
    french_c: str
    slurcuestyle: str
    tiecuestyle: str
    tienoteheads: str
    holdcuestyle: str
    glisscuestyle: str
    showft3extras: str
    ft3fingering: str
    ft3ornaments: str
    showfingerings: str | None
    showornaments: str | None


def _apply_bar_overrides(cells: list[list[str]], request: _BarViewRequest) -> None:
    for (bar_index, string, column), char in request.overrides.items():
        if bar_index != request.bar_index:
            continue
        if string >= request.strings or column >= request.bar_width:
            continue
        cells[string][column] = char


def _hide_tied_noteheads(cells: list[list[str]], request: _BarViewRequest) -> None:
    hidden_columns = tie_notehead_hidden_cols(request.ties, bar_index=request.bar_index, mode=request.tienoteheads)
    for column in hidden_columns:
        if not 0 <= column < request.bar_width:
            continue
        for row in cells:
            if row[column] != "-":
                row[column] = "-"


def _bar_view_cells(request: _BarViewRequest) -> list[list[str]]:
    cells = (
        bar_cells_from_chords(
            request.bar,
            request.strings,
            request.bar_width,
            request.default_duration,
            request.style,
            french_c=request.french_c,
        )
        if request.bar.chords
        else bar_cells(
            request.bar,
            request.strings,
            request.bar_width,
            request.style,
            french_c=request.french_c,
        )
    )
    _apply_bar_overrides(cells, request)
    _hide_tied_noteheads(cells, request)
    return cells


def _bar_view_rhythm(request: _BarViewRequest) -> tuple[list[str], list[str]]:
    flag_cells = _bar_flags(
        request.durations,
        request.bar_index,
        request.strings,
        request.bar_width,
        request.default_duration,
    )
    duration_cells = _bar_durations(
        request.durations,
        request.bar_index,
        request.strings,
        request.bar_width,
        request.default_duration,
    )
    if not any(bar_index == request.bar_index for bar_index, _string, _column in request.durations):
        columns = {
            column
            for bar_index, _string, column in request.overrides
            if bar_index == request.bar_index and column < request.bar_width
        }
        for column in columns:
            duration_cells[column] = duration_display(request.default_duration)
    return flag_cells, duration_cells


def _bar_view_marks(request: _BarViewRequest) -> tuple[list[str], list[str]]:
    show_fingerings = (request.showfingerings or request.showft3extras) == "on"
    show_ornaments = (request.showornaments or request.showft3extras) == "on"
    imported_annotations = (
        _bar_imported_ft3_annotations(
            request.bar,
            bar_width=request.bar_width,
            default_duration=request.default_duration,
            fingering_mode=request.ft3fingering,
        )
        if show_fingerings
        else [" " for _ in range(request.bar_width)]
    )
    imported_ornaments = (
        _bar_imported_ft3_ornaments(
            request.bar,
            bar_width=request.bar_width,
            default_duration=request.default_duration,
            ornament_mode=request.ft3ornaments,
        )
        if show_ornaments
        else [" " for _ in range(request.bar_width)]
    )
    annotation_cells = _merge_mark_rows(
        imported_annotations,
        _bar_annotations(request.annotations, request.bar_index, request.bar_width),
    )
    local_ornaments = (
        _bar_ornaments(request.ornaments, request.bar_index, request.bar_width)
        if show_ornaments
        else [" " for _ in range(request.bar_width)]
    )
    return annotation_cells, _merge_mark_rows(imported_ornaments, local_ornaments)


def _bar_view_span_row(
    spans: list[tuple[int, int, int]],
    chars: tuple[str, str, str] | None,
    request: _BarViewRequest,
) -> list[str]:
    if chars is None:
        return [" " for _ in range(request.bar_width)]
    return _bar_span_row(spans, request.bar_index, request.bar_width, *chars)


def _bar_view_spans(request: _BarViewRequest) -> tuple[list[str], list[str], list[str], list[str]]:
    return (
        _bar_view_span_row(request.slurs, slur_span_chars(request.slurcuestyle), request),
        _bar_view_span_row(request.ties, tie_span_chars(request.tiecuestyle), request),
        _bar_view_span_row(request.holds, hold_span_chars(request.holdcuestyle), request),
        _bar_view_span_row(request.glisses, gliss_span_chars(request.glisscuestyle), request),
    )


def _build_bar_view(request: _BarViewRequest) -> dict[str, list[str]]:
    cells = _bar_view_cells(request)
    flag_cells, duration_cells = _bar_view_rhythm(request)
    annotation_cells, ornament_cells = _bar_view_marks(request)
    slur_cells, tie_cells, hold_cells, gliss_cells = _bar_view_spans(request)
    parenthesized_columns = tie_notehead_parenthesize_cols(
        request.ties,
        bar_index=request.bar_index,
        mode=request.tienoteheads,
    )
    _place_parenthesize_tie_cues(
        ann_cells=annotation_cells,
        orn_cells=ornament_cells,
        tie_cells=tie_cells,
        slur_cells=slur_cells,
        hold_cells=hold_cells,
        gliss_cells=gliss_cells,
        paren_tie_cols=parenthesized_columns,
    )
    return {
        "ann": ["".join(annotation_cells)],
        "orn": ["".join(ornament_cells)],
        "slur": ["".join(slur_cells)],
        "tie": ["".join(tie_cells)],
        "hold": ["".join(hold_cells)],
        "gliss": ["".join(gliss_cells)],
        "flag": ["".join(flag_cells)],
        "dur": ["".join(duration_cells)],
        "rows": ["".join(cells[string]) for string in range(request.strings)],
    }


def build_bar_view(  # noqa: PLR0917 - public compatibility; options are captured in a typed view request
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
    return _build_bar_view(
        _BarViewRequest(
            bar=bar,
            overrides=overrides,
            durations=durations,
            ornaments=ornaments,
            annotations=annotations,
            slurs=slurs,
            ties=ties,
            holds=holds,
            glisses=glisses or [],
            bar_index=bar_index,
            strings=strings,
            bar_width=bar_width,
            default_duration=default_duration,
            style=style,
            french_c=french_c,
            slurcuestyle=slurcuestyle,
            tiecuestyle=tiecuestyle,
            tienoteheads=tienoteheads,
            holdcuestyle=holdcuestyle,
            glisscuestyle=glisscuestyle,
            showft3extras=showft3extras,
            ft3fingering=ft3fingering,
            ft3ornaments=ft3ornaments,
            showfingerings=showfingerings,
            showornaments=showornaments,
        )
    )
