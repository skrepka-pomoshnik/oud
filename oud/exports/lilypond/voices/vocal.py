from __future__ import annotations

from fractions import Fraction

from oud.exports.lilypond.common import (
    _append_bar_time_change,
    _append_barline,
    _append_global_prefix,
    _bar_sign_mark_tokens,
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
from oud.exports.lilypond.registration import LilyPondRegistration
from oud.exports.lilypond.timing import duration_scale, timed_items_duration
from petrucci.adapters.vocal import infer_vocal_events
from petrucci.core.model import Bar, ImportedBarContent, ImportedStaff, MelodyEvent, Piece
from petrucci.rendering.primitives.utils import note_type_to_denom


def _lyric_tokens_for_row(row, sung_onsets: tuple[int, ...]) -> list[str]:
    by_onset = {ev.onset_index: ev for ev in row}
    tokens: list[str] = []
    for onset in sung_onsets:
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
    registration: LilyPondRegistration,
) -> tuple[list[str], list[list[str]]]:
    melody_body: list[str] = []
    lyric_bodies: list[list[str]] = []
    current_time_sig = _append_global_prefix(melody_body, piece, settings)
    tuning = settings.get("tuning", "") or piece.tuning or ""
    tuning_pitches = _parse_tuning(tuning) if tuning else _default_tuning(piece.strings)
    tuning_lookup = list(reversed(_normalize_tuning_length(tuning_pitches, piece.strings)))

    for bar_index, bar in enumerate(piece.bars):
        _append_editorial_marks(melody_body, registration, bar_index)
        current_time_sig = _append_bar_time_change(melody_body, bar, current_time_sig)
        vocal_events = infer_vocal_events(bar, tuning_pitches=tuning_lookup)
        scale = duration_scale(
            registration.duration_for(bar_index),
            timed_items_duration(vocal_events, fallback=Fraction(1, 4)),
        )
        if scale != 1:
            melody_body.append(f"  \\scaleDurations {scale.numerator}/{scale.denominator} {{")
        for event in vocal_events:
            duration = _duration_token(note_type_to_denom(event.note_type) or 4, event.dotted)
            if getattr(event, "is_rest", False) or event.pitch is None:
                melody_body.append(f"  r{duration}")
                continue
            melody_body.append(f"  {_midi_to_lilypond(event.pitch)}{duration}")
        if not vocal_events:
            melody_body.append("  r4")
        if scale != 1:
            melody_body.append("  }")
        _append_barline(melody_body, bar)
        if command := registration.command_after(bar_index):
            melody_body.append(f"  {command}")

        rows = getattr(bar, "lyric_event_rows", None) or []
        sung_onsets = tuple(event.onset_index for event in vocal_events if not event.is_rest)
        if rows:
            while len(lyric_bodies) < len(rows):
                lyric_bodies.append([])
            for idx, row in enumerate(rows):
                lyric_bodies[idx].extend(_lyric_tokens_for_row(row, sung_onsets))
        elif lyric_bodies:
            for row in lyric_bodies:
                row.extend(["_"] * len(sung_onsets))
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


def _imported_event_suffix(
    event: MelodyEvent,
    *,
    beam_suffix: str,
    glissando_to_next: bool,
    dynamic: str | None,
) -> str:
    suffix = beam_suffix
    if event.fermata:
        suffix += r"\fermata"
    if event.ornament:
        ornament = _escape_lilypond(_ft3_ornament_text(event.ornament) or event.ornament)
        suffix += f'^\\markup {{ \\tiny "{ornament}" }}'
    if event.harmonic:
        suffix += r"\flageolet"
    if event.fingering:
        fingering = _escape_lilypond(event.fingering)
        suffix += f"-{fingering}" if fingering.isdigit() else f'^\\markup {{ "{fingering}" }}'
    if glissando_to_next:
        suffix += r"\glissando"
    if dynamic:
        suffix += f"\\{dynamic}"
    return suffix


def _beam_suffix(event: MelodyEvent, beam_open: bool, *, final_event: bool) -> tuple[str, bool]:
    suffix = ""
    if event.beam == "start" and not beam_open:
        suffix = "["
        beam_open = True
    elif event.beam == "end" and beam_open:
        suffix = "]"
        beam_open = False
    if final_event and beam_open:
        suffix += "]"
        beam_open = False
    return suffix, beam_open


def _open_imported_duration_scales(
    melody_body: list[str],
    note_bar: ImportedBarContent,
    target_duration: Fraction,
) -> tuple[bool, bool]:
    proportion_open = note_bar.proportion is not None
    if note_bar.proportion is not None:
        numerator, denominator = note_bar.proportion
        melody_body.append(f"  \\scaleDurations {denominator}/{numerator} {{")
    measure_scale = duration_scale(
        target_duration,
        timed_items_duration(note_bar.melody_events, fallback=Fraction(1, 4)),
    )
    measure_scale_open = measure_scale != 1
    if measure_scale_open:
        melody_body.append(f"  \\scaleDurations {measure_scale.numerator}/{measure_scale.denominator} {{")
    return proportion_open, measure_scale_open


def _append_imported_events(melody_body: list[str], note_bar: ImportedBarContent) -> tuple[int, tuple[int, ...]]:
    sung_onsets: list[int] = []
    beam_open = False
    for event_index, event in enumerate(note_bar.melody_events):
        if not event.is_rest:
            sung_onsets.append(event.onset_index)
        lily = "r" if event.is_rest else _lily_note_from_event_text(event.text)
        duration = _duration_token(note_type_to_denom(event.note_type or 4) or 4, event.dotted)
        glissando_to_next = (
            event_index + 1 < len(note_bar.melody_events)
            and note_bar.melody_events[event_index + 1].glissando_from_previous
        )
        beam_suffix, beam_open = _beam_suffix(
            event,
            beam_open,
            final_event=event_index == len(note_bar.melody_events) - 1,
        )
        suffix = _imported_event_suffix(
            event,
            beam_suffix=beam_suffix,
            glissando_to_next=glissando_to_next,
            dynamic=note_bar.dynamic if event_index == 0 else None,
        )
        melody_body.append(f"  {(lily or 'r')}{duration}{suffix}")
    return len(note_bar.melody_events), tuple(sung_onsets)


def _close_imported_duration_scales(melody_body: list[str], scales: tuple[bool, bool]) -> None:
    melody_body.extend("  }" for scale_open in reversed(scales) if scale_open)


def _append_imported_melody_bar(
    melody_body: list[str],
    note_bar: ImportedBarContent,
    current_time_sig: str | None,
    target_duration: Fraction,
) -> tuple[str | None, tuple[int, ...]]:
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
    scales = _open_imported_duration_scales(melody_body, note_bar, target_duration)
    event_count, sung_onsets = _append_imported_events(melody_body, note_bar)
    if event_count == 0:
        melody_body.append("  r4")
        melody_body.extend(f"  {mark}" for mark in _bar_sign_mark_tokens(bar_like))
    _close_imported_duration_scales(melody_body, scales)
    _append_barline(melody_body, bar_like)
    return current_time_sig, sung_onsets


def _append_editorial_marks(
    body: list[str],
    registration: LilyPondRegistration,
    source_bar_index: int,
) -> None:
    if source_bar_index in registration.boxed_bar_number_before:
        body.append(f'  \\mark \\markup {{ \\box "{source_bar_index + 1}" }}')
    body.extend(
        f'  \\mark \\markup {{ \\italic "{_escape_lilypond(text)}" }}'
        for text in registration.editorial_before[source_bar_index]
    )


def _pad_lyric_bodies(lyric_bodies: list[list[str]], event_count: int) -> None:
    for row in lyric_bodies:
        row.extend(["_"] * max(1, event_count))


def _extend_event_lyric_rows(
    lyric_bodies: list[list[str]],
    rows: list[list],
    *,
    sung_onsets: tuple[int, ...],
    prior_event_count: int,
) -> None:
    while len(lyric_bodies) < len(rows):
        lyric_bodies.append(["_"] * prior_event_count)
    for row_idx, row in enumerate(rows):
        lyric_bodies[row_idx].extend(_lyric_tokens_for_row(row, sung_onsets))
    if len(lyric_bodies) > len(rows):
        _pad_lyric_bodies(lyric_bodies[len(rows) :], len(sung_onsets))


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
    sung_onsets: tuple[int, ...],
    prior_event_count: int,
) -> None:
    if lyric_bar is None:
        if lyric_bodies:
            _pad_lyric_bodies(lyric_bodies, len(sung_onsets))
        return
    rows = lyric_bar.lyric_event_rows or []
    if rows:
        _extend_event_lyric_rows(
            lyric_bodies,
            rows,
            sung_onsets=sung_onsets,
            prior_event_count=prior_event_count,
        )
        return
    raw_lines = [line for line in lyric_bar.lyrics if line.strip()]
    if raw_lines:
        _extend_raw_lyric_lines(
            lyric_bodies,
            raw_lines,
            event_count=len(sung_onsets),
            prior_event_count=prior_event_count,
        )
        return
    if lyric_bodies:
        _pad_lyric_bodies(lyric_bodies, len(sung_onsets))


def _build_imported_vocal_bodies(
    piece: Piece,
    settings: dict[str, str],
    note_staff: ImportedStaff | None,
    lyric_staff: ImportedStaff | None,
    barline_staff: ImportedStaff | None,
    *,
    registration: LilyPondRegistration,
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
        _append_editorial_marks(melody_body, registration, source_bar_index)
        note_bar = note_bars.get(source_bar_index) or ImportedBarContent(
            source_bar_index=source_bar_index,
        )
        note_bar = _with_imported_bar_structure(
            note_bar,
            barline_bars.get(source_bar_index),
            _piece_bar_as_imported(piece, source_bar_index),
        )
        current_time_sig, sung_onsets = _append_imported_melody_bar(
            melody_body,
            note_bar,
            current_time_sig,
            registration.duration_for(source_bar_index),
        )
        if command := registration.command_after(source_bar_index):
            melody_body.append(f"  {command}")
        _extend_imported_lyric_bodies(
            lyric_bodies,
            lyric_bars.get(source_bar_index),
            sung_onsets=sung_onsets,
            prior_event_count=prior_event_count,
        )
        prior_event_count += len(sung_onsets)
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
                '  shortInstrumentName = ""',
                r"}",
            ],
        )
    vocal_block.extend([r"<<", f'  \\new Voice = "{voice_name}" {{'])
    label_text = (label or "").casefold()
    clef = next((name for name in ("bass", "tenor", "alto") if name in label_text), None)
    if clef is not None:
        vocal_block.append(f'    \\clef "{clef}"')
    vocal_block.extend(melody_body)
    vocal_block.extend([r"  }", r">>"])
    lyric_blocks: list[str] = []
    if show_lyrics:
        for row in lyric_bodies:
            tokens = [
                item
                for index, item in enumerate(row)
                if item != "--" or (index + 1 < len(row) and row[index + 1] not in {"_", "__", "--"})
            ]
            lyric_blocks.append(f'\\new Lyrics \\lyricsto "{voice_name}" {{')
            lyric_blocks.append("  " + " ".join(tokens))
            lyric_blocks.append(r"}")
    return [*vocal_block, *lyric_blocks]
