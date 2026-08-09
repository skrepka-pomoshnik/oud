from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from petrucci.core.model import Bar, Piece
from petrucci.input.tablature.input import editor_event_columns, editor_fret_at
from petrucci.rendering.primitives.utils import (
    bar_cells,
    bar_cells_from_chords,
    chord_positions,
    flag_positions_from_durations,
    flag_row,
    format_fret,
    note_type_to_denom,
)


class TabExportError(ValueError):
    """Raised when the legacy TAB format cannot preserve an edit."""

    def __init__(self, fret: int) -> None:
        super().__init__(f"TAB cannot preserve Italian fret {fret}; export LilyPond, MIDI, or MusicXML")


@dataclass(frozen=True, slots=True)
class _TabExportContext:
    piece: Piece
    overrides: dict[tuple[int, int, int], str]
    durations: dict[tuple[int, int, int], int]
    bar_width: int
    settings: dict[str, str]
    dotted: set[tuple[int, int]]
    style: str
    french_c: str
    default_duration: int = 4


def _time_signature_line(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    if text == "C":
        return "Sc"
    if text == "C|":
        return "Sc|"
    return f"S{text}"


def _french_to_fret(ch: str) -> int | None:
    if ch == "r":
        return 2
    if "a" <= ch <= "p":
        return ord(ch) - ord("a")
    return None


def _denom_for_column(context: _TabExportContext, bar_index: int, column: int) -> int:
    found = None
    for string_index in range(context.piece.strings):
        duration = context.durations.get((bar_index, string_index, column))
        if duration is not None and (found is None or duration > found):
            found = duration
    return found if found is not None else context.default_duration


def _denom_to_flag(denom: int) -> str:
    return {
        1: "W",
        2: "w",
        4: "0",
        8: "1",
        16: "2",
        32: "3",
        64: "4",
        128: "5",
    }.get(denom, "0")


def _format_fret_char(context: _TabExportContext, fret: int) -> str:
    if context.style == "italian" and fret > 10:
        raise TabExportError(fret)
    if context.style == "italian" and fret == 10:
        return "x"
    text = format_fret(context.style, fret, french_c=context.french_c)
    return text[0] if text else "-"


def _chord_notes_for_column(
    context: _TabExportContext,
    bar_index: int,
    column: int,
) -> list[tuple[int, int]]:
    notes: list[tuple[int, int]] = []
    for string_index in range(context.piece.strings):
        key = (bar_index, string_index, column)
        fret = editor_fret_at(
            context.overrides,
            context.durations,
            bar_index=bar_index,
            string_index=string_index,
            column=column,
            style=context.style,
            french_c_shape=context.french_c,
        )
        if fret is None and context.style not in {"french", "italian"}:
            fret = _french_to_fret(context.overrides.get(key, ""))
        if fret is not None:
            notes.append((string_index + 1, fret))
    return notes


def _source_chords(context: _TabExportContext, bar: Bar) -> list[tuple[int, bool, list[tuple[int, int]]]]:
    chords: list[tuple[int, bool, list[tuple[int, int]]]] = []
    for chord in bar.chords:
        denom = note_type_to_denom(chord.note_type) or context.default_duration
        notes = [(note.string, note.fret) for note in chord.notes]
        chords.append((denom, bool(chord.dotted), notes))
    return chords


def _edited_chords(
    context: _TabExportContext,
    bar_index: int,
) -> list[tuple[int, bool, list[tuple[int, int]]]]:
    chords: list[tuple[int, bool, list[tuple[int, int]]]] = []
    for column in editor_event_columns(context.overrides, bar_index=bar_index):
        if column >= context.bar_width:
            continue
        notes = _chord_notes_for_column(context, bar_index, column)
        if notes:
            chords.append(
                (
                    _denom_for_column(context, bar_index, column),
                    (bar_index, column) in context.dotted,
                    notes,
                ),
            )
    return chords


def _serialize_chord(
    context: _TabExportContext,
    denom: int,
    dotted: bool,
    notes: list[tuple[int, int]],
) -> str:
    row = ["-" for _ in range(context.piece.strings)]
    for string, fret in notes:
        if 1 <= string <= context.piece.strings:
            row[string - 1] = _format_fret_char(context, fret)
    return _denom_to_flag(denom) + ("." if dotted else "") + "".join(row)


def _bar_lines(context: _TabExportContext, bar_index: int, bar: Bar) -> list[str]:
    lines = ["b"]
    signature = _time_signature_line(bar.time_sig or context.settings.get("time"))
    if signature:
        lines.append(signature)
    chords = _source_chords(context, bar) if bar.chords else _edited_chords(context, bar_index)
    lines.extend(_serialize_chord(context, denom, dotted, notes) for denom, dotted, notes in chords)
    lines.append("")
    return lines


def _header_lines(context: _TabExportContext) -> list[str]:
    lines = ["% Generated by oud", "-C"]
    tuning = context.piece.tuning or context.settings.get("tuning")
    if tuning:
        lines.append(f"-tuning {tuning}")
    tempo = context.piece.tempo or context.settings.get("tempo")
    if tempo:
        lines.append(f"# tempo: {tempo}")
    title = context.piece.title or ""
    composer = context.piece.composer or ""
    if title and composer:
        lines.append(f"{{{title}/{composer}}}")
    elif title:
        lines.append(f"{{{title}}}")
    elif composer:
        lines.append(f"{{{composer}}}")
    if context.piece.author:
        lines.append(f"{{{context.piece.author}}}")
    lines.append("")
    return lines


def export_tab(  # noqa: PLR0917 - public compatibility; replace options with a typed request
    piece: Piece,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    bar_width: int,
    settings: dict[str, str] | None = None,
    dotted: set[tuple[int, int]] | None = None,
    ornaments: dict[tuple[int, int], str] | None = None,
    annotations: dict[tuple[int, int], str] | None = None,
    slurs: list[tuple[int, int, int]] | None = None,
    ties: list[tuple[int, int, int]] | None = None,
    holds: list[tuple[int, int, int]] | None = None,
) -> str:
    _ = (ornaments, annotations, slurs, ties, holds)
    settings_map = settings or {}
    style = settings_map.get("style") or piece.style or "french"
    french_c = settings_map.get("frenchc") or "normal"
    context = _TabExportContext(
        piece,
        overrides,
        durations,
        bar_width,
        settings_map,
        dotted or set(),
        style,
        french_c,
    )
    lines = _header_lines(context)
    for b_idx, bar in enumerate(piece.bars):
        lines.extend(_bar_lines(context, b_idx, bar))
    lines.append("e")
    return "\n".join(lines) + "\n"


def export_ascii(  # noqa: PLR0917 - public compatibility; replace options with a typed request
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
    _ = (ornaments, annotations, slurs, ties, holds)
    lines: list[str] = []
    default_duration = 4
    settings_map = settings or {}
    style = settings_map.get("style") or "french"
    french_c = settings_map.get("frenchc") or "normal"
    reverse_strings = style == "italian" and (settings_map.get("italianorient") or "normal") == "reverse"
    for b_idx, bar in enumerate(piece.bars):
        cells = (
            bar_cells_from_chords(
                bar,
                piece.strings,
                bar_width,
                default_duration,
                style,
                french_c=french_c,
            )
            if bar.chords
            else bar_cells(
                bar,
                piece.strings,
                bar_width,
                style,
                french_c=french_c,
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


def export_tab_to_file(  # noqa: PLR0917 - public compatibility; replace options with a typed request
    path: str,
    piece: Piece,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    bar_width: int,
    settings: dict[str, str] | None = None,
    dotted: set[tuple[int, int]] | None = None,
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
        dotted=dotted,
        ornaments=ornaments,
        annotations=annotations,
        slurs=slurs,
        ties=ties,
        holds=holds,
    )
    with Path(path).open("w", encoding="utf-8") as f:
        f.write(content)


__all__ = ["TabExportError", "export_ascii", "export_tab", "export_tab_to_file"]
