from __future__ import annotations

from oud.exports._lilypond_common import (
    _append_bar_time_change,
    _append_global_prefix,
    _bar_sign_mark_tokens,
    _barline_token,
    _coalesced_imported_bars,
    _default_tuning,
    _duration_token,
    _escape_lilypond,
    _ft3_ornament_text,
    _lily_note_from_event_text,
    _midi_to_lilypond,
    _normalize_tuning_length,
    _parse_tuning,
    _piece_bar_as_imported,
    _raw_lyric_tokens,
    _repeat_mark_token,
    _with_imported_bar_structure,
)
from petrucci.model import Bar, ImportedBarContent, ImportedStaff, Piece
from petrucci.render_utils import note_type_to_denom
from petrucci.vocal_line import infer_vocal_events


def _lyric_tokens_for_row(row, event_count: int) -> list[str]:
    by_onset = {ev.onset_index: ev for ev in row}
    tokens: list[str] = []
    for onset in range(event_count):
        ev = by_onset.get(onset)
        if ev is None:
            tokens.append("_")
            continue
        if ev.extender:
            tokens.append("__")
            continue
        text = (ev.text or "").strip()
        if not text:
            tokens.append("_")
            continue
        tokens.append(f'"{_escape_lilypond(text)}"')
        if ev.syllabic in {"begin", "middle"}:
            tokens.append("--")
    return tokens


def _build_vocal_bodies(  # noqa: C901
    piece: Piece,
    settings: dict[str, str],
) -> tuple[list[str], list[list[str]]]:
    melody_body: list[str] = []
    lyric_bodies: list[list[str]] = []
    current_time_sig = _append_global_prefix(melody_body, piece, settings)
    tuning = settings.get("tuning", "") or piece.tuning or ""
    tuning_pitches = _parse_tuning(tuning) if tuning else _default_tuning(piece.strings)
    tuning_lookup = list(reversed(_normalize_tuning_length(tuning_pitches, piece.strings)))

    for bar in piece.bars:
        current_time_sig = _append_bar_time_change(melody_body, bar, current_time_sig)
        vocal_events = infer_vocal_events(bar, tuning_pitches=tuning_lookup)
        for event in vocal_events:
            duration = _duration_token(note_type_to_denom(event.note_type) or 4, event.dotted)
            if getattr(event, "is_rest", False) or event.pitch is None:
                melody_body.append(f"  r{duration}")
                continue
            melody_body.append(f"  {_midi_to_lilypond(event.pitch)}{duration}")
        if not vocal_events:
            melody_body.append("  r4")
        bar_marker = _barline_token(bar)
        melody_body.append("  |" if bar_marker == "|" else f'  \\bar "{bar_marker}"')

        rows = getattr(bar, "lyric_event_rows", None) or []
        event_count = len(vocal_events)
        if rows:
            while len(lyric_bodies) < len(rows):
                lyric_bodies.append([])
            for idx, row in enumerate(rows):
                lyric_bodies[idx].extend(_lyric_tokens_for_row(row, event_count))
        elif lyric_bodies:
            for row in lyric_bodies:
                row.extend(["_"] * event_count)
    return melody_body, lyric_bodies


def _matching_imported_lyric_staff(
    note_staff: ImportedStaff,
    lyric_staffs: list[ImportedStaff],
    index: int,
) -> ImportedStaff | None:
    if note_staff.label is not None:
        matched = next((staff for staff in lyric_staffs if staff.label == note_staff.label), None)
        if matched is not None:
            return matched
    return lyric_staffs[index] if index < len(lyric_staffs) else None


def _append_imported_melody_bar(  # noqa: C901
    melody_body: list[str],
    note_bar: ImportedBarContent,
    current_time_sig: str | None,
) -> tuple[str | None, int]:
    bar_like = Bar(
        time_sig=note_bar.time_sig,
        barline=note_bar.barline,
        repeat=note_bar.repeat,
        ending_numbers=note_bar.ending_numbers,
        system_break=note_bar.system_break,
        dynamic=note_bar.dynamic,
        fermata=note_bar.fermata,
    )
    current_time_sig = _append_bar_time_change(melody_body, bar_like, current_time_sig)
    repeat_mark = _repeat_mark_token(bar_like)
    if repeat_mark:
        melody_body.append(f"  {repeat_mark}")
    event_count = 0
    for event in note_bar.melody_events:
        is_rest = getattr(event, "is_rest", False)
        lily = "r" if is_rest else _lily_note_from_event_text(event.text)
        note_type = event.note_type or 4
        duration = _duration_token(note_type_to_denom(note_type) or 4, event.dotted)
        suffix = ""
        if event.beam == "start":
            suffix += "["
        elif event.beam == "end":
            suffix += "]"
        if event.fermata:
            suffix += r"\fermata"
        if event.ornament:
            ornament = _escape_lilypond(_ft3_ornament_text(event.ornament) or event.ornament)
            suffix += f'^\\markup {{ \\tiny "{ornament}" }}'
        if event_count == 0 and note_bar.dynamic:
            suffix += f"\\{note_bar.dynamic}"
        melody_body.append(f"  {(lily or 'r')}{duration}{suffix}")
        event_count += 1
    if event_count == 0:
        melody_body.append("  r4")
        melody_body.extend(f"  {mark}" for mark in _bar_sign_mark_tokens(bar_like))
    bar_marker = _barline_token(bar_like)
    melody_body.append("  |" if bar_marker == "|" else f'  \\bar "{bar_marker}"')
    if note_bar.system_break:
        melody_body.append(r"  \break")
    return current_time_sig, event_count


def _pad_lyric_bodies(lyric_bodies: list[list[str]], event_count: int) -> None:
    for row in lyric_bodies:
        row.extend(["_"] * max(1, event_count))


def _extend_event_lyric_rows(
    lyric_bodies: list[list[str]],
    rows: list[list],
    *,
    event_count: int,
    prior_event_count: int,
) -> None:
    while len(lyric_bodies) < len(rows):
        lyric_bodies.append(["_"] * prior_event_count)
    for row_idx, row in enumerate(rows):
        lyric_bodies[row_idx].extend(_lyric_tokens_for_row(row, max(1, event_count)))
    if len(lyric_bodies) > len(rows):
        _pad_lyric_bodies(lyric_bodies[len(rows) :], event_count)


def _extend_raw_lyric_lines(
    lyric_bodies: list[list[str]],
    raw_lines: list[str],
    *,
    event_count: int,
    prior_event_count: int,
) -> None:
    while len(lyric_bodies) < len(raw_lines):
        lyric_bodies.append(["_"] * prior_event_count)
    for row_idx, line in enumerate(raw_lines):
        lyric_bodies[row_idx].extend(_raw_lyric_tokens(line, max(1, event_count)))
    if len(lyric_bodies) > len(raw_lines):
        _pad_lyric_bodies(lyric_bodies[len(raw_lines) :], event_count)


def _extend_imported_lyric_bodies(
    lyric_bodies: list[list[str]],
    lyric_bar: ImportedBarContent | None,
    *,
    event_count: int,
    prior_event_count: int,
) -> None:
    if lyric_bar is None:
        if lyric_bodies:
            _pad_lyric_bodies(lyric_bodies, event_count)
        return
    rows = lyric_bar.lyric_event_rows or []
    if rows:
        _extend_event_lyric_rows(
            lyric_bodies,
            rows,
            event_count=event_count,
            prior_event_count=prior_event_count,
        )
        return
    raw_lines = [line for line in lyric_bar.lyrics if line.strip()]
    if raw_lines:
        _extend_raw_lyric_lines(
            lyric_bodies,
            raw_lines,
            event_count=event_count,
            prior_event_count=prior_event_count,
        )
        return
    if lyric_bodies:
        _pad_lyric_bodies(lyric_bodies, event_count)


def _build_imported_vocal_bodies(
    piece: Piece,
    settings: dict[str, str],
    note_staff: ImportedStaff | None,
    lyric_staff: ImportedStaff | None,
    barline_staff: ImportedStaff | None,
) -> tuple[list[str], list[list[str]]]:
    melody_body: list[str] = []
    lyric_bodies: list[list[str]] = []
    current_time_sig = _append_global_prefix(melody_body, piece, settings)

    note_bars = _coalesced_imported_bars(note_staff, kind="note")
    lyric_bars = _coalesced_imported_bars(lyric_staff, kind="lyrics")
    barline_bars = _coalesced_imported_bars(barline_staff, kind="barline")
    source_bar_indices = sorted(
        {
            *range(len(piece.bars)),
            *note_bars,
            *lyric_bars,
            *barline_bars,
        },
    )
    prior_event_count = 0
    for source_bar_index in source_bar_indices:
        note_bar = note_bars.get(source_bar_index) or ImportedBarContent(
            source_bar_index=source_bar_index,
        )
        note_bar = _with_imported_bar_structure(
            note_bar,
            barline_bars.get(source_bar_index),
            _piece_bar_as_imported(piece, source_bar_index),
        )
        current_time_sig, event_count = _append_imported_melody_bar(
            melody_body,
            note_bar,
            current_time_sig,
        )
        _extend_imported_lyric_bodies(
            lyric_bodies,
            lyric_bars.get(source_bar_index),
            event_count=event_count,
            prior_event_count=prior_event_count,
        )
        prior_event_count += max(1, event_count)
    return melody_body, lyric_bodies


def _vocal_blocks(
    melody_body: list[str],
    lyric_bodies: list[list[str]],
    *,
    show_lyrics: bool,
    identifier: str = "melody",
    label: str | None = None,
) -> list[str]:
    staff_name = f"{identifier}Staff"
    voice_name = f"{identifier}Voice"
    vocal_block = [f'\\new Staff = "{staff_name}"']
    if label:
        escaped = _escape_lilypond(label)
        vocal_block.extend(
            [
                r"\with {",
                f'  instrumentName = "{escaped}"',
                f'  shortInstrumentName = "{escaped}"',
                r"}",
            ],
        )
    vocal_block.extend([r"<<", f'  \\new Voice = "{voice_name}" {{'])
    vocal_block.extend(melody_body)
    vocal_block.extend([r"  }", r">>"])
    lyric_blocks: list[str] = []
    if show_lyrics:
        for row in lyric_bodies:
            lyric_blocks.append(f'\\new Lyrics \\lyricsto "{voice_name}" {{')
            lyric_blocks.append("  " + " ".join(row))
            lyric_blocks.append(r"}")
    return [*vocal_block, *lyric_blocks]
