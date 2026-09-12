from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from oud.exports.lilypond.common import (
    _append_bar_time_change,
    _append_barline,
    _append_global_prefix,
    _bar_sign_mark_tokens,
    _chord_ft3_markup_suffix,
    _collect_override_chords,
    _default_tuning,
    _duration_token,
    _escape_lilypond,
    _lily_pitches_for_chord_notes,
    _lily_pitches_for_override_event,
    _ly_notehead_style_override,
    _midi_to_lilypond,
    _normalize_tuning_length,
    _parse_tuning,
    _repeat_mark_token,
    _span_maps,
    _split_tuning,
)
from oud.exports.lilypond.registration import LilyPondRegistration
from oud.exports.lilypond.timing import duration_scale, timed_items_duration
from petrucci.core.model import Bar, Piece
from petrucci.rendering.primitives.utils import chord_positions, note_type_to_denom


@dataclass(frozen=True)
class _TabBodyContext:
    default_duration: int
    style: str
    french_c: str
    tuning_lookup: list[int]
    source_tuning_lookup: list[int]


def _tab_body_context(piece: Piece, settings: dict[str, str]) -> _TabBodyContext:
    default_duration = 4
    style = settings.get("style") or "french"
    french_c = settings.get("frenchc") or "normal"
    tuning = settings.get("tuning", "") or ""
    tuning_pitches = _parse_tuning(tuning) if tuning else _default_tuning(piece.strings)
    tuning_pitches = _normalize_tuning_length(tuning_pitches, piece.strings)
    source_tuning_text = piece.tuning or tuning
    source_tuning_pitches = _parse_tuning(source_tuning_text) if source_tuning_text else []
    source_tuning_pitches = _normalize_tuning_length(
        source_tuning_pitches or tuning_pitches,
        piece.strings,
    )
    return _TabBodyContext(
        default_duration=default_duration,
        style=style,
        french_c=french_c,
        tuning_lookup=list(reversed(tuning_pitches)),
        source_tuning_lookup=list(reversed(source_tuning_pitches)),
    )


def _append_tab_bar_header(body: list[str], bar: Bar, current_time_sig: str | None) -> str | None:
    if bar.page_break_before:
        body.append(r"  \pageBreak")
    if bar.section_title or bar.section_subtitle:
        title = f'\\bold "{_escape_lilypond(bar.section_title)}"' if bar.section_title else ""
        subtitle = f'"{_escape_lilypond(bar.section_subtitle)}"' if bar.section_subtitle else ""
        body.append(f"  \\mark \\markup {{ \\center-column {{ {title} {subtitle} }} }}")
    current_time_sig = _append_bar_time_change(body, bar, current_time_sig)
    repeat_mark = _repeat_mark_token(bar)
    if repeat_mark:
        body.append(f"  {repeat_mark}")
    body.extend(f"  {mark}" for mark in _bar_sign_mark_tokens(bar))
    return current_time_sig


def _tab_event_suffix(
    col: int,
    *,
    tie_starts: set[int],
    hold_starts: set[int],
    slur_starts: set[int],
    slur_ends: set[int],
) -> str:
    suffix = ""
    if col in tie_starts:
        suffix += "~"
    if col in hold_starts:
        suffix += r"\laissezVibrer"
    if col in slur_starts:
        suffix += "("
    if col in slur_ends:
        suffix += ")"
    return suffix


def _append_tab_chord_events(
    body: list[str],
    *,
    bar: Bar,
    bar_width: int,
    context: _TabBodyContext,
    settings: dict[str, str],
    tie_starts: set[int],
    hold_starts: set[int],
    slur_starts: set[int],
    slur_ends: set[int],
) -> None:
    positions = chord_positions(bar, bar_width, context.default_duration)
    for chord, (col, _denom, _dot) in zip(bar.chords, positions, strict=False):
        denom = note_type_to_denom(chord.note_type) or context.default_duration
        dur = _duration_token(denom, chord.dotted)
        pitches = _lily_pitches_for_chord_notes(
            chord.notes,
            source_tuning_lookup=context.source_tuning_lookup,
            settings=settings,
        )
        suffix = _tab_event_suffix(
            col,
            tie_starts=tie_starts,
            hold_starts=hold_starts,
            slur_starts=slur_starts,
            slur_ends=slur_ends,
        )
        extra_suffix = _chord_ft3_markup_suffix(chord, settings)
        if not pitches:
            body.append(f"  r{dur}")
        elif len(pitches) == 1:
            body.append(f"  {pitches[0]}{dur}{suffix}{extra_suffix}")
        else:
            body.append(f"  <{' '.join(pitches)}>{dur}{suffix}{extra_suffix}")


def _append_tab_override_events(
    body: list[str],
    *,
    events: list[tuple[int, list[tuple[int, int]], int]],
    context: _TabBodyContext,
    tie_starts: set[int],
    hold_starts: set[int],
    slur_starts: set[int],
    slur_ends: set[int],
) -> None:
    for col, notes, denom in events:
        dur = _duration_token(denom, False)
        pitches = _lily_pitches_for_override_event(
            notes,
            target_tuning_lookup=context.tuning_lookup,
        )
        suffix = _tab_event_suffix(
            col,
            tie_starts=tie_starts,
            hold_starts=hold_starts,
            slur_starts=slur_starts,
            slur_ends=slur_ends,
        )
        if not pitches:
            body.append(f"  r{dur}")
        elif len(pitches) == 1:
            body.append(f"  {pitches[0]}{dur}{suffix}")
        else:
            body.append(f"  <{' '.join(pitches)}>{dur}{suffix}")


def _tab_actual_duration(
    bar: Bar,
    events: list[tuple[int, list[tuple[int, int]], int]],
) -> Fraction:
    if bar.chords:
        return timed_items_duration(bar.chords, fallback=Fraction(1, 4))
    return sum(
        (Fraction(1, denominator) for _col, _notes, denominator in events),
        Fraction(1, 4) if not events else Fraction(),
    )


def _append_tab_contents(
    body: list[str],
    *,
    bar: Bar,
    bar_index: int,
    piece: Piece,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    bar_width: int,
    settings: dict[str, str],
    context: _TabBodyContext,
    tie_starts: set[int],
    hold_starts: set[int],
    slur_starts: set[int],
    slur_ends: set[int],
    registration: LilyPondRegistration,
) -> None:
    events: list[tuple[int, list[tuple[int, int]], int]] = []
    if not bar.chords:
        events = _collect_override_chords(
            overrides,
            durations,
            bar_index,
            piece.strings,
            style=context.style,
            default_duration=context.default_duration,
            french_c=context.french_c,
        )
    actual_duration = _tab_actual_duration(bar, events)
    scale = duration_scale(registration.duration_for(bar_index), actual_duration)
    if scale != 1:
        body.append(f"  \\scaleDurations {scale.numerator}/{scale.denominator} {{")
    if bar.chords:
        _append_tab_chord_events(
            body,
            bar=bar,
            bar_width=bar_width,
            context=context,
            settings=settings,
            tie_starts=tie_starts,
            hold_starts=hold_starts,
            slur_starts=slur_starts,
            slur_ends=slur_ends,
        )
    else:
        if not events:
            body.append("  r4")
        _append_tab_override_events(
            body,
            events=events,
            context=context,
            tie_starts=tie_starts,
            hold_starts=hold_starts,
            slur_starts=slur_starts,
            slur_ends=slur_ends,
        )
    if scale != 1:
        body.append("  }")


def _append_tab_bar(
    body: list[str],
    *,
    piece: Piece,
    bar: Bar,
    bar_index: int,
    current_time_sig: str | None,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    bar_width: int,
    settings: dict[str, str],
    slurs: list[tuple[int, int, int]] | None,
    ties: list[tuple[int, int, int]] | None,
    holds: list[tuple[int, int, int]] | None,
    context: _TabBodyContext,
    registration: LilyPondRegistration,
) -> str | None:
    current_time_sig = _append_tab_bar_header(body, bar, current_time_sig)
    slur_starts, slur_ends = _span_maps(slurs, bar_index)
    tie_starts, _tie_ends = _span_maps(ties, bar_index)
    hold_starts, _hold_ends = _span_maps(holds, bar_index)
    _append_tab_contents(
        body,
        bar=bar,
        bar_index=bar_index,
        piece=piece,
        overrides=overrides,
        durations=durations,
        bar_width=bar_width,
        settings=settings,
        context=context,
        tie_starts=tie_starts,
        hold_starts=hold_starts,
        slur_starts=slur_starts,
        slur_ends=slur_ends,
        registration=registration,
    )
    _append_barline(body, bar)
    if command := registration.command_after(bar_index):
        body.append(f"  {command}")
    return current_time_sig


def _build_tab_body(
    *,
    piece: Piece,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    bar_width: int,
    settings: dict[str, str],
    slurs: list[tuple[int, int, int]] | None,
    ties: list[tuple[int, int, int]] | None,
    holds: list[tuple[int, int, int]] | None,
    registration: LilyPondRegistration,
) -> list[str]:
    body: list[str] = []
    current_time_sig = _append_global_prefix(body, piece, settings)
    context = _tab_body_context(piece, settings)
    for bar_index, bar in enumerate(piece.bars):
        current_time_sig = _append_tab_bar(
            body,
            piece=piece,
            bar=bar,
            bar_index=bar_index,
            current_time_sig=current_time_sig,
            overrides=overrides,
            durations=durations,
            bar_width=bar_width,
            settings=settings,
            slurs=slurs,
            ties=ties,
            holds=holds,
            context=context,
            registration=registration,
        )
    return body


def _tab_tuning_prefix(settings: dict[str, str], piece: Piece) -> list[str]:
    tuning = settings.get("tuning", "") or ""
    tuning_pitches = _parse_tuning(tuning) if tuning else _default_tuning(piece.strings)
    tuning_pitches = _normalize_tuning_length(tuning_pitches, piece.strings)
    lute_style = (settings.get("style") or "french") in {"french", "italian"}
    main_course_count = min(piece.strings, 6) if lute_style else piece.strings
    main_pitches, bass_pitches = _split_tuning(tuning_pitches, main_course_count)
    tuning_text = " ".join(_midi_to_lilypond(p) for p in main_pitches)
    lines = [f"  \\set TabStaff.stringTunings = \\stringTuning <{tuning_text}>"]
    extra_bass = settings.get("basstuning", "") or settings.get("bassstrings", "") or ""
    if extra_bass:
        bass_pitches = _parse_tuning(extra_bass)
    if bass_pitches:
        bass_text = " ".join(_midi_to_lilypond(p) for p in bass_pitches)
        lines.append(f"  \\set TabStaff.additionalBassStrings = \\stringTuning <{bass_text}>")
    return lines


def _tab_option_prefix(settings: dict[str, str]) -> list[str]:
    lines: list[str] = []
    if settings.get("lytabrhythm", settings.get("tabnotation", "minimal")) == "full":
        lines.extend([r"  \tabFullNotation", r"  \stemUp"])
        if settings.get("lyprofile", "petrucci") != "classic":
            lines.append(r"  \autoBeamOff")
    if settings.get("tabnotation", "minimal") == "full":
        lines.extend(
            [
                r"  \set fingeringOrientations = #'(left)",
                r"  \set strokeFingerOrientations = #'(right)",
            ],
        )
    notehead_override = _ly_notehead_style_override(settings)
    if notehead_override:
        lines.append(notehead_override)
    return lines


def _tab_label_block(label: str | None) -> list[str]:
    if not label:
        return []
    escaped = _escape_lilypond(label)
    return [
        r"\with {",
        f'  instrumentName = "{escaped}"',
        f'  shortInstrumentName = "{escaped}"',
        r"}",
    ]


def _tab_staff_with_block(
    label: str | None,
    body: list[str],
    settings: dict[str, str],
    piece: Piece,
) -> list[str]:
    tab_body_prefix = _tab_tuning_prefix(settings, piece) + _tab_option_prefix(settings)
    out = [r"\new TabStaff"]
    out.extend(_tab_label_block(label))
    out.append("{")
    out.extend(tab_body_prefix)
    out.extend(body)
    out.append(r"}")
    return out
