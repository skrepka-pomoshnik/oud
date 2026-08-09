from __future__ import annotations

from oud.exports._lilypond_common import (
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
from petrucci.model import Piece
from petrucci.render_utils import chord_positions, note_type_to_denom


def _build_tab_body(  # noqa: C901, PLR0912
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
    body: list[str] = []
    current_time_sig = _append_global_prefix(body, piece, settings)
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
    source_tuning_lookup = list(reversed(source_tuning_pitches))
    tuning_lookup = list(reversed(tuning_pitches))

    for b_idx, bar in enumerate(piece.bars):
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
        slur_starts, slur_ends = _span_maps(slurs, b_idx)
        tie_starts, _tie_ends = _span_maps(ties, b_idx)
        hold_starts, _hold_ends = _span_maps(holds, b_idx)
        if bar.chords:
            positions = chord_positions(bar, bar_width, default_duration)
            for chord, (col, _denom, _dot) in zip(bar.chords, positions, strict=False):
                denom = note_type_to_denom(chord.note_type) or default_duration
                dur = _duration_token(denom, chord.dotted)
                pitches = _lily_pitches_for_chord_notes(
                    chord.notes,
                    source_tuning_lookup=source_tuning_lookup,
                    settings=settings,
                )
                suffix = ""
                if col in tie_starts:
                    suffix += "~"
                if col in hold_starts:
                    suffix += r"\laissezVibrer"
                if col in slur_starts:
                    suffix += "("
                if col in slur_ends:
                    suffix += ")"
                extra_suffix = _chord_ft3_markup_suffix(chord, settings)
                if not pitches:
                    body.append(f"  r{dur}")
                elif len(pitches) == 1:
                    body.append(f"  {pitches[0]}{dur}{suffix}{extra_suffix}")
                else:
                    body.append(f"  <{' '.join(pitches)}>{dur}{suffix}{extra_suffix}")
        else:
            events = _collect_override_chords(
                overrides,
                durations,
                b_idx,
                piece.strings,
                style,
                default_duration,
                french_c,
            )
            if not events:
                body.append("  r4")
            for col, notes, denom in events:
                dur = _duration_token(denom, False)
                pitches = _lily_pitches_for_override_event(
                    notes,
                    target_tuning_lookup=tuning_lookup,
                )
                suffix = ""
                if col in tie_starts:
                    suffix += "~"
                if col in hold_starts:
                    suffix += r"\laissezVibrer"
                if col in slur_starts:
                    suffix += "("
                if col in slur_ends:
                    suffix += ")"
                if not pitches:
                    body.append(f"  r{dur}")
                elif len(pitches) == 1:
                    body.append(f"  {pitches[0]}{dur}{suffix}")
                else:
                    body.append(f"  <{' '.join(pitches)}>{dur}{suffix}")
        _append_barline(body, bar)
        if bar.system_break:
            body.append(r"  \break")
    return body


def _tab_staff_with_block(  # noqa: C901
    label: str | None,
    body: list[str],
    settings: dict[str, str],
    piece: Piece,
) -> list[str]:
    tuning = settings.get("tuning", "") or ""
    tuning_pitches = _parse_tuning(tuning) if tuning else _default_tuning(piece.strings)
    tuning_pitches = _normalize_tuning_length(tuning_pitches, piece.strings)
    main_pitches, bass_pitches = _split_tuning(tuning_pitches, piece.strings)
    tuning_text = " ".join(_midi_to_lilypond(p) for p in main_pitches)
    bass_text = ""
    extra_bass = settings.get("basstuning", "") or settings.get("bassstrings", "") or ""
    if extra_bass:
        bass_pitches = _parse_tuning(extra_bass)
    if bass_pitches:
        bass_text = " ".join(_midi_to_lilypond(p) for p in bass_pitches)

    tab_body_prefix: list[str] = []
    tab_body_prefix.append(f"  \\set TabStaff.stringTunings = \\stringTuning <{tuning_text}>")
    if bass_text:
        tab_body_prefix.append(
            f"  \\set TabStaff.additionalBassStrings = \\stringTuning <{bass_text}>",
        )
    if settings.get("tabnotation", "minimal") == "full":
        tab_body_prefix.append(r"  \tabFullNotation")
        tab_body_prefix.append(r"  \set fingeringOrientations = #'(left)")
        tab_body_prefix.append(r"  \set strokeFingerOrientations = #'(right)")
    notehead_override = _ly_notehead_style_override(settings)
    if notehead_override:
        tab_body_prefix.append(notehead_override)

    out = [r"\new TabStaff"]
    with_lines: list[str] = []
    if label:
        escaped = _escape_lilypond(label)
        with_lines.append(f'  instrumentName = "{escaped}"')
        with_lines.append(f'  shortInstrumentName = "{escaped}"')
    if with_lines:
        out.append(r"\with {")
        out.extend(with_lines)
        out.append(r"}")
    out.append("{")
    out.extend(tab_body_prefix)
    out.extend(body)
    out.append(r"}")
    return out
