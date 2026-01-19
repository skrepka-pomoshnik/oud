from __future__ import annotations

from core.model import Piece
from core.render_utils import (
    bar_cells,
    bar_cells_from_chords,
    chord_positions,
    duration_display,
    duration_flag,
    flag_positions_from_durations,
    flag_row,
)


def _parse_time_signature(value: str) -> tuple[int, int, str]:
    text = value.strip()
    if text in ("C", "c", "4/4"):
        return 4, 4, "C"
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


def _bar_number_for_index(
    piece: Piece, bar_index: int, measures: str, countdots: str
) -> str | None:
    extra = 0
    if countdots == "on":
        for idx in range(bar_index + 1):
            if piece.bars[idx].repeat == ".":
                extra += 1
    if measures == "every":
        return str(bar_index + 1 + extra)
    if measures == "five":
        number = bar_index + 1 + extra
        return str(number) if number % 5 == 0 else None
    if measures == "start":
        return str(bar_index + 1 + extra) if bar_index == 0 else None
    return None


def _bar_durations(
    durations: dict[tuple[int, int, int], int],
    bar_index: int,
    strings: int,
    bar_width: int,
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
        if found is not None:
            row[col] = duration_display(found)
    return row


def _bar_flags(
    durations: dict[tuple[int, int, int], int],
    bar_index: int,
    strings: int,
    bar_width: int,
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
        if found is not None:
            row[col] = duration_flag(found)
    return row


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


def _bar_span_row(
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
        if 0 <= start < bar_width:
            row[start] = start_char
        if 0 <= end < bar_width:
            row[end] = end_char
        for col in range(start + 1, min(end, bar_width - 1)):
            row[col] = fill_char
    return row


def export_tab(  # noqa: PLR0912
    piece: Piece,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    bar_width: int,
    settings: dict[str, str] | None = None,
    ornaments: dict[tuple[int, int], str] | None = None,
    annotations: dict[tuple[int, int], str] | None = None,
    slurs: list[tuple[int, int, int]] | None = None,
    ties: list[tuple[int, int, int]] | None = None,
    holds: list[tuple[int, int, int]] | None = None,
) -> str:
    lines: list[str] = []
    settings_map = settings or {}
    style = settings_map.get("style") or "french"
    french_c = settings_map.get("frenchc") or "normal"
    french_e = settings_map.get("frenche") or "normal"
    lines.append(f"# TITLE: {piece.title or ''}")
    lines.append(f"# SUBTITLE: {piece.subtitle or ''}")
    lines.append(f"# AUTHOR: {piece.author or ''}")
    lines.append(f"# COMPOSER: {piece.composer or ''}")
    lines.append(f"# FOOTNOTE: {piece.footnote or ''}")
    lines.append(f"# STRINGS: {piece.strings}")
    if settings_map:
        if settings_map.get("style"):
            lines.append(f"# STYLE: {settings_map['style']}")
        if settings_map.get("flagstyle"):
            lines.append(f"# FLAGSTYLE: {settings_map['flagstyle']}")
        if settings_map.get("measures"):
            lines.append(f"# MEASURES: {settings_map['measures']}")
        if settings_map.get("tuning"):
            lines.append(f"# TUNING: {settings_map['tuning']}")
        if settings_map.get("time"):
            _beats, _unit, sig_label = _parse_time_signature(settings_map["time"])
            if sig_label:
                lines.append(f"# TIME: {sig_label}")
        if settings_map.get("key"):
            lines.append(f"# KEY: {settings_map['key']}")
        if settings_map.get("countdots"):
            lines.append(f"# COUNTDOTS: {settings_map['countdots']}")
        if settings_map.get("spacing"):
            lines.append(f"# SPACING: {settings_map['spacing']}")
        if settings_map.get("linelen"):
            lines.append(f"# LINELEN: {settings_map['linelen']}")
        if settings_map.get("staffthick"):
            lines.append(f"# STAFFTHICK: {settings_map['staffthick']}")
        if settings_map.get("fontstyle"):
            lines.append(f"# FONTSTYLE: {settings_map['fontstyle']}")
        if settings_map.get("charstyle"):
            lines.append(f"# CHARSTYLE: {settings_map['charstyle']}")
        if settings_map.get("midipatch"):
            lines.append(f"# MIDIPATCH: {settings_map['midipatch']}")
        if settings_map.get("grid"):
            lines.append(f"# GRID: {settings_map['grid']}")
    lines.append("")

    reverse_strings = (
        style == "italian"
        and (settings_map.get("italianorient") or "normal") == "reverse"
    )
    for b_idx, bar in enumerate(piece.bars):
        measures = settings_map.get("measures") or "start"
        countdots = settings_map.get("countdots") or "off"
        number = _bar_number_for_index(piece, b_idx, measures, countdots)
        if number is not None:
            lines.append(f"Bar {number}")
        if bar.barline:
            lines.append(f"Barline: {bar.barline}")
        if bar.repeat:
            lines.append(f"Repeat: {bar.repeat}")
        time_value = settings_map.get("time") or "C"
        beats, _unit, _sig = _parse_time_signature(time_value)
        tactus = _tactus_row(bar_width, beats)
        lines.append("Tactus: " + "".join(tactus))
        if annotations:
            ann_cells = _bar_annotations(annotations, b_idx, bar_width)
            lines.append("Annot: " + "".join(ann_cells))
        if ornaments:
            orn_cells = _bar_ornaments(ornaments, b_idx, bar_width)
            lines.append("Orn: " + "".join(orn_cells))
        if slurs:
            slur_cells = _bar_span_row(slurs, b_idx, bar_width, "(", ")", "~")
            lines.append("Slur: " + "".join(slur_cells))
        if ties:
            tie_cells = _bar_span_row(ties, b_idx, bar_width, "[", "]", "-")
            lines.append("Tie: " + "".join(tie_cells))
        if holds:
            hold_cells = _bar_span_row(holds, b_idx, bar_width, "<", ">", "_")
            lines.append("Hold: " + "".join(hold_cells))
        flag_cells = _bar_flags(durations, b_idx, piece.strings, bar_width)
        lines.append("Flag: " + "".join(flag_cells))
        dur_cells = _bar_durations(durations, b_idx, piece.strings, bar_width)
        lines.append("Dur: " + "".join(dur_cells))

        cells = bar_cells(
            bar,
            piece.strings,
            bar_width,
            style,
            french_c=french_c,
            french_e=french_e,
        )
        for s_idx in range(piece.strings):
            actual = piece.strings - 1 - s_idx if reverse_strings else s_idx
            for col in range(bar_width):
                key = (b_idx, actual, col)
                if key in overrides:
                    cells[actual][col] = overrides[key]
            row_text = "".join(cells[actual])
            label_value = piece.strings - actual
            lines.append(f"{label_value:>2}|{row_text}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def export_ascii(
    piece: Piece,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    bar_width: int,
    settings: dict[str, str] | None = None,
    ornaments: dict[tuple[int, int], str] | None = None,
    annotations: dict[tuple[int, int], str] | None = None,
    slurs: list[tuple[int, int, int]] | None = None,
    ties: list[tuple[int, int, int]] | None = None,
    holds: list[tuple[int, int, int]] | None = None,
) -> str:
    lines: list[str] = []
    default_duration = 4
    settings_map = settings or {}
    style = settings_map.get("style") or "french"
    french_c = settings_map.get("frenchc") or "normal"
    french_e = settings_map.get("frenche") or "normal"
    reverse_strings = (
        style == "italian"
        and (settings_map.get("italianorient") or "normal") == "reverse"
    )
    for b_idx, bar in enumerate(piece.bars):
        cells = (
            bar_cells_from_chords(
                bar,
                piece.strings,
                bar_width,
                default_duration,
                style,
                french_c=french_c,
                french_e=french_e,
            )
            if bar.chords
            else bar_cells(
                bar,
                piece.strings,
                bar_width,
                style,
                french_c=french_c,
                french_e=french_e,
            )
        )
        for s_idx in range(piece.strings):
            actual = piece.strings - 1 - s_idx if reverse_strings else s_idx
            for col in range(bar_width):
                key = (b_idx, actual, col)
                if key in overrides:
                    cells[actual][col] = overrides[key]
        if bar.chords:
            positions = chord_positions(bar, bar_width, default_duration)
            flag_cells = flag_row(positions, bar_width)
            lines.append("".join(flag_cells))
        else:
            flag_positions = flag_positions_from_durations(
                durations,
                b_idx,
                piece.strings,
                bar_width,
                default_duration,
            )
            flag_cells = flag_row(flag_positions, bar_width)
            lines.append("".join(flag_cells))
        for s_idx in range(piece.strings):
            actual = piece.strings - 1 - s_idx if reverse_strings else s_idx
            row = "".join(cells[actual])
            label = f"{piece.strings - actual:>2}|"
            lines.append(label + row)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def export_tab_to_file(
    path: str,
    piece: Piece,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    bar_width: int,
    settings: dict[str, str] | None = None,
    ornaments: dict[tuple[int, int], str] | None = None,
    annotations: dict[tuple[int, int], str] | None = None,
    slurs: list[tuple[int, int, int]] | None = None,
    ties: list[tuple[int, int, int]] | None = None,
    holds: list[tuple[int, int, int]] | None = None,
) -> None:
    content = export_tab(
        piece,
        overrides,
        durations,
        bar_width,
        settings=settings,
        ornaments=ornaments,
        annotations=annotations,
        slurs=slurs,
        ties=ties,
        holds=holds,
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
