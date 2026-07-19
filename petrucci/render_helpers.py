from __future__ import annotations

import unicodedata
from importlib.metadata import PackageNotFoundError, version

from petrucci.help_text import help_lines
from petrucci.model import Piece
from petrucci.screen import CursesError, Screen

try:
    _PACKAGE_VERSION = version("oud")
except PackageNotFoundError:  # pragma: no cover - source tree without installation
    _PACKAGE_VERSION = "dev"


def _split_display_clusters(text: str) -> list[str]:
    clusters: list[str] = []
    for ch in text:
        if unicodedata.combining(ch):
            if clusters:
                clusters[-1] += ch
            continue
        clusters.append(ch)
    return clusters


def _clip_display_width(text: str, max_cols: int) -> str:
    if max_cols <= 0 or not text:
        return ""
    clusters = _split_display_clusters(text)
    if len(clusters) <= max_cols:
        return text
    return "".join(clusters[:max_cols])


def _drop_display_cols_left(text: str, skip_cols: int) -> str:
    if skip_cols <= 0 or not text:
        return text
    clusters = _split_display_clusters(text)
    if skip_cols >= len(clusters):
        return ""
    return "".join(clusters[skip_cols:])


def safe_addstr(stdscr: Screen, y: int, x: int, text: str, attr: int = 0) -> None:
    height, width = stdscr.getmaxyx()
    if height <= 0 or width <= 0:
        return
    if y < 0 or y >= height or x >= width:
        return
    if x < 0:
        text = _drop_display_cols_left(text, -x)
        x = 0
    if x >= width:
        return
    clipped = _clip_display_width(text, max(0, width - x))
    try:
        stdscr.addstr(y, x, clipped, attr)
    except CursesError:
        return
    except ValueError:
        return


def clean_text(text: str) -> str:
    return "".join(ch if 32 <= ord(ch) <= 126 else " " for ch in text)


def pad_row(row: list[str], width: int, pad: int, *, pad_char: str = " ") -> list[str]:
    if width <= 0:
        return []
    pad = max(0, min(pad, max(0, (width - 1) // 2)))
    if pad == 0:
        if len(row) < width:
            return row + [" "] * (width - len(row))
        return row[:width]
    content_width = max(1, width - pad * 2)
    if len(row) < content_width:
        row = row + [" "] * (content_width - len(row))
    row = row[:content_width]
    return ([pad_char] * pad) + row + ([pad_char] * pad)


def info_lines(piece: Piece, settings: dict[str, str]) -> list[str]:
    def line(label: str, value: str | None) -> str:
        return f"{label:<14}{value or ''}"

    fields = [
        line("File:", settings.get("filepath")),
        line("Write target:", settings.get("writepath")),
        line("Document:", settings.get("documentmode")),
        line("Terminal:", settings.get("terminal")),
        line("Version:", _PACKAGE_VERSION),
        line("Title:", piece.title),
        line("Subtitle:", piece.subtitle),
        line("Author:", piece.author),
        line("Composer:", piece.composer),
        line("Arranger:", piece.arranger),
        line("Source key:", piece.key),
        line("Type:", piece.piece_type),
        line("Difficulty:", piece.difficulty),
        line("Ensemble:", piece.ensemble),
        line("Part:", piece.part),
        line("Instrumentation:", piece.instrumentation),
        line("Source:", piece.source),
        line("Editor:", piece.editor),
        line("Publisher:", piece.publisher),
        line("Volume:", piece.volume),
        line("Source page:", piece.page),
        line("Footnote:", piece.footnote),
        line("FootSrc:", piece.footnote_source),
        line("FootEd:", piece.footnote_editor),
        line("FootCmt:", piece.footnote_comment),
        line("Comment:", piece.comment),
        line("LyricBars:", str(sum(1 for bar in piece.bars if bar.lyrics))),
        line("MelodyBars:", str(sum(1 for bar in piece.bars if bar.melody_grid))),
        line("Bars:", str(len(piece.bars))),
        line("Strings:", str(piece.strings)),
        line("Style:", settings.get("style")),
        line("Tuning:", settings.get("tuning")),
        line("Time:", settings.get("time")),
        line("Key:", settings.get("key")),
        line("Layout:", settings.get("layout")),
        line("Contrast:", settings.get("contrast")),
        line("Flagstyle:", settings.get("flagstyle")),
        line("DotPlacement:", settings.get("dotplacement", "afterflag")),
        line("Grid:", settings.get("grid")),
        line("ShowDur:", settings.get("showdur")),
        line(
            "ShowSpans:",
            "on" if settings.get("showspans", "off") == "on" or settings.get("showextras", "off") == "on" else "off",
        ),
        line("ShowFingerings:", settings.get("showfingerings", settings.get("showft3extras"))),
        line("ShowOrnaments:", settings.get("showornaments", settings.get("showft3extras"))),
        line("ShowMelody:", settings.get("showmelody")),
        line("ShowLyrics:", settings.get("showlyrics")),
        line("PlayVerses:", settings.get("playverses", "once")),
        line("ShowTactus:", settings.get("showtactus")),
        line("Measures:", settings.get("measures")),
        line("MeasuresStep:", settings.get("measuresstep")),
        line("MidiPatch:", settings.get("midipatch")),
        line("MidiVocalPatch:", settings.get("midivocalpatch", "53")),
        line("MidiGate:", settings.get("midigate")),
        line("Tempo:", settings.get("tempo")),
        line("Soundfont:", settings.get("soundfont")),
        line("TuneLabels:", settings.get("tuninglabels")),
        line("ItalianOrient:", settings.get("italianorient")),
        line("French c:", settings.get("frenchc")),
        line("FlagRedundant:", settings.get("flagredundant")),
    ]
    imported: list[str] = []
    if piece.imported_score is not None:
        imported = ["", f"Imported score: {piece.imported_score.source_format}"]
        imported.extend(
            f"Staff {index}: {staff.kind} | {staff.label or '(unlabeled)'} | {len(staff.bars)} bars"
            for index, staff in enumerate(piece.imported_score.staffs, start=1)
        )
    source_metadata: list[str] = []
    if piece.section_annotations:
        source_metadata = ["", "Source metadata"]
        source_metadata.extend(f"{key}: {value}" for key, value in sorted(piece.section_annotations.items()))
    warnings: list[str] = []
    if piece.import_warnings:
        warnings = [
            "",
            "Import warnings",
            *[f"{index}. {warning}" for index, warning in enumerate(piece.import_warnings, start=1)],
        ]
    return ["INFO", "", *fields, *imported, *source_metadata, *warnings, "", "q/esc to close"]


def _editorial_entries(piece: Piece) -> list[tuple[int, str]]:
    entries = {
        (idx + 1, text.strip()) for idx, bar in enumerate(piece.bars) for text in bar.editorial_text if text.strip()
    }
    if piece.imported_score is not None:
        entries.update(
            (bar.source_bar_index + 1, text.strip())
            for staff in piece.imported_score.staffs
            for bar in staff.bars
            for text in bar.editorial_text
            if text.strip()
        )
    return sorted(entries)


def notes_lines(piece: Piece) -> list[str]:  # noqa: C901
    lines = ["NOTES", ""]
    for note in piece.notes:
        text = (note or "").strip()
        if text:
            lines.append(text)
    if piece.footnote:
        lines.extend(["", f"Footnote: {piece.footnote}"])
    if piece.source:
        lines.append(f"Source: {piece.source}")
    if piece.editor:
        lines.append(f"Editor: {piece.editor}")
    if piece.comment:
        lines.append(f"Comment: {piece.comment}")
    editorial = _editorial_entries(piece)
    if editorial:
        lines.append("")
        lines.append("Bar Comments")
        for bar_no, text in editorial:
            lines.append(f"[{bar_no}] {text}")
    if lines == ["NOTES", ""]:
        lines.append("No notes")
    lines.extend(["", "q/esc to close"])
    return lines


def render_help(
    stdscr: Screen,
    status: str,
    status_attr: int,
    help_offset: int,
) -> None:
    height, _width = stdscr.getmaxyx()
    lines = help_lines()
    max_lines = max(0, height - 1)
    max_offset = max(0, len(lines) - max_lines)
    offset = min(max(0, help_offset), max_offset)
    for idx, line in enumerate(lines[offset : offset + max_lines]):
        safe_addstr(stdscr, idx, 0, clean_text(line))
    safe_addstr(stdscr, height - 1, 0, clean_text(status), status_attr)


def render_plugin(
    stdscr: Screen,
    status: str,
    status_attr: int,
    title: str,
    items: list[str],
    index: int,
    offset: int,
    message: str,
) -> None:
    height, width = stdscr.getmaxyx()
    safe_addstr(stdscr, 0, 0, clean_text(title))
    max_lines = max(0, height - 2)
    visible = items[offset : offset + max_lines]
    for row, label in enumerate(visible, start=1):
        absolute = offset + row - 1
        prefix = ">" if absolute == index else " "
        text = clean_text(f"{prefix} {label}")
        attr = status_attr if absolute == index else 0
        safe_addstr(stdscr, row, 0, text[: max(0, width - 1)], attr)
    status_text = status
    if message:
        status_text = f"{status}  {message}"
    safe_addstr(stdscr, height - 1, 0, clean_text(status_text), status_attr)


def render_info(
    stdscr: Screen,
    status: str,
    status_attr: int,
    info_offset: int,
    piece: Piece,
    settings: dict[str, str],
) -> None:
    height, _width = stdscr.getmaxyx()
    lines = info_lines(piece, settings)
    max_lines = max(0, height - 1)
    max_offset = max(0, len(lines) - max_lines)
    offset = min(max(0, info_offset), max_offset)
    for idx, line in enumerate(lines[offset : offset + max_lines]):
        safe_addstr(stdscr, idx, 0, clean_text(line))
    safe_addstr(stdscr, height - 1, 0, clean_text(status), status_attr)


def render_notes(
    stdscr: Screen,
    status: str,
    status_attr: int,
    notes_offset: int,
    piece: Piece,
) -> None:
    height, _width = stdscr.getmaxyx()
    lines = notes_lines(piece)
    max_lines = max(0, height - 1)
    max_offset = max(0, len(lines) - max_lines)
    offset = min(max(0, notes_offset), max_offset)
    for idx, line in enumerate(lines[offset : offset + max_lines]):
        safe_addstr(stdscr, idx, 0, clean_text(line))
    safe_addstr(stdscr, height - 1, 0, clean_text(status), status_attr)


def flag_symbols(style: str, flaglean: str = "right") -> tuple[str, str]:
    lean = "left" if (flaglean or "right").strip().lower() == "left" else "right"
    slash_flag = "/" if lean == "left" else "\\"
    symbols = {
        "italian": ("I", slash_flag),
        "thin": ("|", slash_flag),
        "board": ("|", "="),
        "englishgrid": ("|", "-"),
        "continental": ("Γ", "F"),
        "capirola": ("I", "-"),
    }
    return symbols.get(style, ("|", slash_flag))


def bass_strings_used(piece: Piece, overrides: dict[tuple[int, int, int], str]) -> set[int]:  # noqa: C901
    used: set[int] = set()
    for _bar, string, _col in overrides:
        if string >= 6:
            used.add(string)
    for bar in piece.bars:
        for note in bar.notes:
            idx = note.string - 1
            if idx >= 6:
                used.add(idx)
        for chord in bar.chords:
            for note in chord.notes:
                idx = note.string - 1
                if idx >= 6:
                    used.add(idx)
    return used


def apply_overrides(
    cells: list[list[str]],
    overrides: dict[tuple[int, int, int], str],
    bar_index: int,
    strings: int,
    bar_width: int,
) -> None:
    for s_idx in range(strings):
        for col in range(bar_width):
            key = (bar_index, s_idx, col)
            if key not in overrides:
                continue
            value = overrides[key]
            if value == "r":
                cells[s_idx][col] = "_"
                next_col = col + 1
                if (
                    next_col < bar_width
                    and cells[s_idx][next_col] in ("-", " ")
                    and (bar_index, s_idx, next_col) not in overrides
                ):
                    cells[s_idx][next_col] = "."
            else:
                cells[s_idx][col] = value
