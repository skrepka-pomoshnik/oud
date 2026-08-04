from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from oud.exports._lilypond_common import (
    _imported_staff_by_kind,
    _imported_staffs_by_kind,
    _lilypond_header,
    _parse_fret_labels,
    _piece_has_imported_lyrics,
    _piece_has_lyrics,
    _piece_has_melody,
    _piece_has_tab_content,
)
from oud.exports._lilypond_tab import (
    _build_tab_body,
    _tab_staff_with_block,
)
from oud.exports._lilypond_vocal import (
    _build_imported_vocal_bodies,
    _build_vocal_bodies,
    _matching_imported_lyric_staff,
    _vocal_blocks,
)
from petrucci.duet_score import (
    duet_staff_labels,
    is_duet_score_piece,
    split_duet_piece_staff,
    split_duet_span_list,
    split_duet_triplet_map,
)
from petrucci.model import Piece


def _build_main_blocks(  # noqa: C901
    *,
    piece: Piece,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    bar_width: int,
    settings: dict[str, str],
    slurs: list[tuple[int, int, int]] | None,
    ties: list[tuple[int, int, int]] | None,
    holds: list[tuple[int, int, int]] | None,
) -> list[str]:
    if is_duet_score_piece(piece):
        mode = settings.get("duetscoreview", "auto")
        staff_indices = [0, 1] if mode in {"auto", "both"} else [0 if mode == "1" else 1]
        labels = duet_staff_labels(piece)
        blocks = [r"\new StaffGroup <<"]
        for staff_index in staff_indices:
            sub_piece = split_duet_piece_staff(piece, staff_index)
            sub_overrides = split_duet_triplet_map(overrides, staff_index=staff_index, piece=piece)
            sub_durations = split_duet_triplet_map(durations, staff_index=staff_index, piece=piece)
            sub_slurs = split_duet_span_list(slurs or [], staff_index=staff_index, piece=piece)
            sub_ties = split_duet_span_list(ties or [], staff_index=staff_index, piece=piece)
            sub_holds = split_duet_span_list(holds or [], staff_index=staff_index, piece=piece)
            sub_body = _build_tab_body(
                piece=sub_piece,
                overrides=sub_overrides,
                durations=sub_durations,
                bar_width=bar_width,
                settings=settings,
                slurs=sub_slurs,
                ties=sub_ties,
                holds=sub_holds,
            )
            blocks.extend(_tab_staff_with_block(labels[staff_index], sub_body, settings, sub_piece))
        blocks.append(r">>")
        return blocks

    imported_note_staffs = _imported_staffs_by_kind(piece, "note")
    imported_lyric_staffs = _imported_staffs_by_kind(piece, "lyrics")
    imported_barline_staff = _imported_staff_by_kind(piece, "barline")
    tab_body = _build_tab_body(
        piece=piece,
        overrides=overrides,
        durations=durations,
        bar_width=bar_width,
        settings=settings,
        slurs=slurs,
        ties=ties,
        holds=holds,
    )
    has_imported_notation = bool(imported_note_staffs) or imported_barline_staff is not None
    has_imported_lyrics = bool(imported_lyric_staffs) and _piece_has_imported_lyrics(piece)
    show_melody = settings.get("showmelody", "on") == "on" and (has_imported_notation or _piece_has_melody(piece))
    show_lyrics = settings.get("showlyrics", "on") == "on" and (has_imported_lyrics or _piece_has_lyrics(piece))
    has_tab = _piece_has_tab_content(piece) or bool(overrides)
    if not has_tab and not show_melody and not show_lyrics:
        return [r"\new Staff {", "  r4", r"}"]
    if not show_melody and not show_lyrics:
        return _tab_staff_with_block(None, tab_body, settings, piece)

    if imported_note_staffs:
        vocal_stack: list[str] = []
        for index, note_staff in enumerate(imported_note_staffs):
            lyric_staff = _matching_imported_lyric_staff(note_staff, imported_lyric_staffs, index)
            melody_body, lyric_bodies = _build_imported_vocal_bodies(
                piece,
                settings,
                note_staff,
                lyric_staff,
                imported_barline_staff,
            )
            vocal_stack.extend(
                _vocal_blocks(
                    melody_body,
                    lyric_bodies,
                    show_lyrics=show_lyrics,
                    identifier="melody" if index == 0 else f"melody{index + 1}",
                    label=note_staff.label,
                ),
            )
    elif has_imported_notation or has_imported_lyrics:
        melody_body, lyric_bodies = _build_imported_vocal_bodies(
            piece,
            settings,
            None,
            imported_lyric_staffs[0] if imported_lyric_staffs else None,
            imported_barline_staff,
        )
        vocal_stack = _vocal_blocks(melody_body, lyric_bodies, show_lyrics=show_lyrics)
    else:
        melody_body, lyric_bodies = _build_vocal_bodies(piece, settings)
        vocal_stack = _vocal_blocks(melody_body, lyric_bodies, show_lyrics=show_lyrics)

    if not has_tab:
        blocks = [r"\new StaffGroup <<"]
        blocks.extend(vocal_stack)
        blocks.append(r">>")
        return blocks

    tab_block = _tab_staff_with_block(None, tab_body, settings, piece)
    blocks = [r"\new StaffGroup <<"]
    vocal_pos = settings.get("vocalpos", "bottom")
    if vocal_pos == "bottom":
        blocks.extend(tab_block)
        blocks.extend(vocal_stack)
    else:
        blocks.extend(vocal_stack)
        blocks.extend(tab_block)
    blocks.append(r">>")
    return blocks


def lilypond_text(
    piece: Piece,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    bar_width: int,
    *,
    settings: dict[str, str] | None = None,
    ornaments: dict[tuple[int, int], str] | None = None,
    annotations: dict[tuple[int, int], str] | None = None,
    slurs: list[tuple[int, int, int]] | None = None,
    ties: list[tuple[int, int, int]] | None = None,
    holds: list[tuple[int, int, int]] | None = None,
) -> str:
    _ = (bar_width, ornaments, annotations, slurs, ties, holds)
    settings = settings or {}
    header = _lilypond_header(piece)

    layout: list[str] = [r"\layout {", r"  \context {", r"    \Score"]
    style = settings.get("style") or "french"
    if style == "french":
        layout.append("    tablatureFormat = #fret-letter-tablature-format")
    layout += [r"  }", r"  \context {", r"    \TabStaff"]
    # Hide the default "TAB" clef label/glyph in exported tab staves.
    layout.append(r"    \override Clef.stencil = ##f")
    layout.append(r"    \override ClefModifier.stencil = ##f")
    if style == "french":
        labels = _parse_fret_labels(settings.get("fretlabels", "") or "")
        if not labels:
            labels = ["a", "b", "r", "d", "e", "f", "g", "h", "i", "k", "l"]
        labels_text = " ".join(f'"{label}"' for label in labels)
        layout.append(f"    fretLabels = #'({labels_text})")
    layout += [r"  }", r"}"]
    blocks = _build_main_blocks(
        piece=piece,
        overrides=overrides,
        durations=durations,
        bar_width=bar_width,
        settings=settings,
        slurs=slurs,
        ties=ties,
        holds=holds,
    )
    return "\n".join(
        [
            *header,
            "",
            r"\paper { indent = 0\mm }",
            "",
            *blocks,
            "",
            *layout,
            "",
        ],
    )


def export_lilypond(
    path: str,
    piece: Piece,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    bar_width: int,
    *,
    settings: dict[str, str] | None = None,
    ornaments: dict[tuple[int, int], str] | None = None,
    annotations: dict[tuple[int, int], str] | None = None,
    slurs: list[tuple[int, int, int]] | None = None,
    ties: list[tuple[int, int, int]] | None = None,
    holds: list[tuple[int, int, int]] | None = None,
) -> str:
    content = lilypond_text(
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
    Path(path).write_text(content, encoding="utf-8")
    return f"Wrote {path}"


def print_lilypond_pdf(ly_path: str, output_base: str | None = None) -> str:
    lilypond = shutil.which("lilypond")
    if lilypond is None:
        return "LilyPond not found on PATH"
    ly_file = Path(ly_path)
    out_base = Path(output_base) if output_base else ly_file.with_suffix("")
    workdir = (out_base.parent if output_base else ly_file.parent) or Path()
    workdir = workdir.resolve()
    cmd = [lilypond, "-o", out_base.name, str(ly_file.resolve())]
    try:
        subprocess.run(  # noqa: S603
            cmd,
            check=True,
            capture_output=True,
            text=False,
            cwd=workdir,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr or b""
        err = stderr.decode("utf-8", errors="replace").strip() if isinstance(stderr, bytes) else str(stderr).strip()
        detail = err.splitlines()[-1] if err else "unknown error"
        return f"LilyPond failed: {detail}"
    pdf_path = (workdir / f"{out_base.name}.pdf").resolve()
    if not pdf_path.exists():
        return f"LilyPond finished but PDF not found: {pdf_path}"
    return f"Printed {pdf_path}"
