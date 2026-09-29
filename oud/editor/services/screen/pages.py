"""Full-screen editor pages: help, info, notes, plugin browser, and ASCII preview."""

from __future__ import annotations

from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, version

from petrucci.core.model import Piece
from petrucci.rendering.primitives.helpers import clean_text, safe_addstr
from petrucci.terminal.canvas.screen import Screen

try:
    _PACKAGE_VERSION = version("oud")
except PackageNotFoundError:  # pragma: no cover - source tree without installation
    _PACKAGE_VERSION = "dev"

PLUGIN_HINT = "plugin  j/k move  h back  l/enter open  d download  q close"


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
        line("ScoreView:", settings.get("scoreview", "auto")),
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
        line("LyricMode:", settings.get("lyricmode", "all")),
        line("LyricVerse:", settings.get("lyricverse", "1")),
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


def _piece_note_lines(piece: Piece) -> list[str]:
    return [text for note in piece.notes if (text := (note or "").strip())]


def _footnote_lines(piece: Piece) -> list[str]:
    return ["", f"Footnote: {piece.footnote}"] if piece.footnote else []


def _source_note_lines(piece: Piece) -> list[str]:
    fields = (("Source", piece.source), ("Editor", piece.editor), ("Comment", piece.comment))
    return [f"{label}: {value}" for label, value in fields if value]


def _editorial_note_lines(piece: Piece) -> list[str]:
    editorial = _editorial_entries(piece)
    if not editorial:
        return []
    return ["", "Bar Comments", *[f"[{bar_no}] {text}" for bar_no, text in editorial]]


def notes_lines(piece: Piece) -> list[str]:
    lines = [
        "NOTES",
        "",
        *_piece_note_lines(piece),
        *_footnote_lines(piece),
        *_source_note_lines(piece),
        *_editorial_note_lines(piece),
    ]
    if lines == ["NOTES", ""]:
        lines.append("No notes")
    lines.extend(["", "q/esc to close"])
    return lines


def paint_page(screen: Screen, lines: Sequence[str], *, offset: int, status: str, status_attr: int) -> None:
    """Paint scrollable page lines above a status row; the offset is clamped to the content."""

    height, _width = screen.getmaxyx()
    max_lines = max(0, height - 1)
    offset = min(max(0, offset), max(0, len(lines) - max_lines))
    for row, line in enumerate(lines[offset : offset + max_lines]):
        safe_addstr(screen, row, 0, clean_text(line))
    safe_addstr(screen, height - 1, 0, clean_text(status), status_attr)


def paint_plugin_browser(
    screen: Screen,
    *,
    title: str,
    items: Sequence[str],
    index: int,
    offset: int,
    message: str,
    status_attr: int,
) -> None:
    height, width = screen.getmaxyx()
    safe_addstr(screen, 0, 0, clean_text(title))
    visible = items[offset : offset + max(0, height - 2)]
    for row, label in enumerate(visible, start=1):
        selected = offset + row - 1 == index
        text = clean_text(f"{'>' if selected else ' '} {label}")
        safe_addstr(screen, row, 0, text[: max(0, width - 1)], status_attr if selected else 0)
    status = f"{PLUGIN_HINT}  {message}" if message else PLUGIN_HINT
    safe_addstr(screen, height - 1, 0, clean_text(status), status_attr)


def paint_ascii_preview(
    screen: Screen,
    lines: Sequence[str],
    *,
    status: str | None,
    status_attr: int,
) -> None:
    """Paint exported ASCII lines; ``status`` is ``None`` when the status row is hidden."""

    height, _width = screen.getmaxyx()
    for row, line in enumerate(lines[: max(0, height - int(status is not None))]):
        safe_addstr(screen, row, 0, clean_text(line))
    if status is not None:
        safe_addstr(screen, height - 1, 0, clean_text(status), status_attr)
