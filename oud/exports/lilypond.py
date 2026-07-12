from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

from oud.core.tab_assign_policy import AssignmentPolicy, assign_chord_pitches
from oud.petrucci.duet_score import (
    duet_staff_labels,
    is_duet_score_piece,
    split_duet_piece_staff,
    split_duet_span_list,
    split_duet_triplet_map,
)
from oud.petrucci.model import Bar, ImportedBarContent, ImportedStaff, Piece
from oud.petrucci.render_utils import chord_positions, note_type_to_denom
from oud.petrucci.vocal_line import infer_vocal_events


def _escape_lilypond(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _parse_tuning(tuning: str) -> list[int]:
    pitches: list[int] = []
    idx = 0
    text = tuning.strip()
    while idx < len(text):
        ch = text[idx]
        if ch.isalpha():
            note = ch.upper()
            idx += 1
            accidental = ""
            if idx < len(text) and text[idx] in "+-#b":
                accidental = text[idx]
                idx += 1
            start = idx
            while idx < len(text) and text[idx].isdigit():
                idx += 1
            octave = text[start:idx]
            octave_num = int(octave) if octave else 3
            semis = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}.get(
                note,
                0,
            )
            if accidental in ("+", "#"):
                semis += 1
            elif accidental in ("-", "b"):
                semis -= 1
            midi = (octave_num + 1) * 12 + semis
            if 0 <= midi <= 127:
                pitches.append(midi)
        else:
            idx += 1
    return pitches


def _split_tuning(pitches: list[int], strings: int) -> tuple[list[int], list[int]]:
    if len(pitches) <= strings:
        return pitches, []
    bass_count = len(pitches) - strings
    return pitches[bass_count:], pitches[:bass_count]


def _normalize_time_sig(value: str) -> str:
    text = value.strip()
    if text in ("C", "c"):
        return "4/4"
    if text in ("O", "o"):
        return "3/4"
    if text in ("C|", "c|"):
        return "2/2"
    return text


def _normalized_time_sig_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    return _normalize_time_sig(text)


def _time_sig_style_command(settings: dict[str, str]) -> str | None:
    mode = (settings.get("timesigstyle") or "symbol").strip().lower()
    if mode in {"numeric", "fraction"}:
        return r"\numericTimeSignature"
    if mode == "symbol":
        return r"\defaultTimeSignature"
    return None


def _ly_notehead_style_override(settings: dict[str, str]) -> str | None:
    mode = (settings.get("lynoteheads") or "classic").strip().lower()
    if mode == "petrucci":
        return r"  \override NoteHead.style = #'petrucci"
    return None


def _normalize_key_pitch(value: str) -> str | None:
    text = value.strip()
    if not text:
        return None
    note = text[0].lower()
    if note not in "abcdefg":
        return None
    acc = text[1:]
    if acc not in ("", "#", "b"):
        return None
    acc = acc.replace("#", "is").replace("b", "es")
    return note + acc


def _parse_key_signature(value: str) -> tuple[str, str] | None:
    text = value.strip()
    if not text:
        return None
    compact = re.sub(r"\s+", "", text)

    # FT3 metadata often uses compact major/minor forms like "GM", "Dm".
    match = re.fullmatch(r"([A-Ga-g])([#b]?)(M|m)?", compact)
    if match:
        note = _normalize_key_pitch(f"{match.group(1)}{match.group(2)}")
        if note is None:
            return None
        suffix = match.group(3) or ""
        mode = "minor" if suffix == "m" else "major"
        return note, mode

    # Also accept spaced forms like "D minor" / "Bb major".
    match = re.fullmatch(r"([A-Ga-g])([#b]?)\s*(maj(?:or)?|min(?:or)?)", text, re.I)
    if match:
        note = _normalize_key_pitch(f"{match.group(1)}{match.group(2)}")
        if note is None:
            return None
        kind = match.group(3).lower()
        mode = "minor" if kind.startswith("min") else "major"
        return note, mode

    return None


def _parse_fret_labels(value: str) -> list[str]:
    if not value:
        return []
    items = [item.strip() for item in value.replace(",", " ").split()]
    return [item for item in items if item]


def _default_tuning(strings: int) -> list[int]:
    # Low -> high order (matches settings tuning order and TabStaff stringTunings).
    defaults = [
        "c2",
        "d2",
        "e2",
        "f2",
        "g2",
        "c3",
        "f3",
        "a3",
        "d4",
        "g4",
    ]
    pitches = _parse_tuning("".join(defaults))
    return pitches[-max(0, strings) :] if strings > 0 else []


def _midi_to_lilypond(midi: int) -> str:
    names = ["c", "cis", "d", "dis", "e", "f", "fis", "g", "gis", "a", "ais", "b"]
    pc = midi % 12
    octave = (midi // 12) - 1
    marks = octave - 3
    if marks > 0:
        suffix = "'" * marks
    elif marks < 0:
        suffix = "," * (-marks)
    else:
        suffix = ""
    return f"{names[pc]}{suffix}"


def _duration_token(denom: int, dotted: bool) -> str:
    if denom <= 0:
        denom = 4
    token = str(denom)
    if dotted:
        token += "."
    return token


def _assignment_policy_from_settings(settings: dict[str, str]) -> AssignmentPolicy:
    minimum_fret = int(settings.get("minimumfret", "0") or "0")
    max_stretch_raw = int(settings.get("maxstretch", "0") or "0")
    max_stretch = max_stretch_raw if max_stretch_raw > 0 else None
    restrain_open = settings.get("restrainopenstrings", "off") == "on"
    return AssignmentPolicy(
        minimum_fret=minimum_fret,
        max_stretch=max_stretch,
        restrain_open_strings=restrain_open,
    )


def _normalize_tuning_length(pitches: list[int], strings: int) -> list[int]:
    if len(pitches) >= strings:
        return pitches[:]
    defaults = _default_tuning(strings)
    missing = strings - len(pitches)
    return defaults[:missing] + pitches


def _note_pitch_from_lookup(note, tuning_lookup: list[int]) -> int | None:
    s_idx = note.string - 1
    if 0 <= s_idx < len(tuning_lookup):
        return tuning_lookup[s_idx] + note.fret
    return None


def _lily_pitches_for_chord_notes(
    notes: list,
    *,
    source_tuning_lookup: list[int],
    target_tuning_pitches: list[int],
    settings: dict[str, str],
) -> list[str]:
    pitch_notes: list[tuple[object, int]] = []
    for note in notes:
        pitch = _note_pitch_from_lookup(note, source_tuning_lookup)
        if pitch is not None:
            pitch_notes.append((note, pitch))
    if not pitch_notes:
        return []
    pitches = [pitch for _note, pitch in pitch_notes]
    # LilyPond performs final TabStaff assignment, but we validate/routinely check
    # assignability through the same core policy used by editor transforms so
    # pitch->string fallback behavior stays deterministic across formats.
    policy = _assignment_policy_from_settings(settings)
    result = assign_chord_pitches(pitches, target_tuning_pitches, policy=policy)
    if not result.ok:
        # Export should degrade gracefully; keep pitches if policy is too strict.
        result = assign_chord_pitches(pitches, target_tuning_pitches)
    # Final fallback keeps source-derived pitches even if assignment policy rejects them.
    keep = [True] * len(pitches)
    out: list[str] = []
    for (note, pitch), keep_note in zip(pitch_notes, keep, strict=False):
        if not keep_note:
            continue
        base = _midi_to_lilypond(pitch)
        native = _note_native_lh_fingering_suffix(note, settings) + _note_native_rh_fingering_suffix(note, settings)
        out.append(base + native)
    return out


def _lily_pitches_for_override_event(
    notes: list[tuple[int, int]],
    *,
    target_tuning_lookup: list[int],
    target_tuning_pitches: list[int],
    settings: dict[str, str],
) -> list[str]:
    pitches: list[int] = []
    for s_idx, fret in notes:
        if 0 <= s_idx < len(target_tuning_lookup):
            pitches.append(target_tuning_lookup[s_idx] + fret)
    if not pitches:
        return []
    policy = _assignment_policy_from_settings(settings)
    result = assign_chord_pitches(pitches, target_tuning_pitches, policy=policy)
    if not result.ok:
        result = assign_chord_pitches(pitches, target_tuning_pitches)
    _ = result
    return [_midi_to_lilypond(pitch) for pitch in pitches]


def _span_maps(
    spans: list[tuple[int, int, int]] | None,
    bar_index: int,
) -> tuple[set[int], set[int]]:
    starts: set[int] = set()
    ends: set[int] = set()
    if not spans:
        return starts, ends
    for b, start, end in spans:
        if b != bar_index:
            continue
        starts.add(start)
        ends.add(end)
    return starts, ends


def _french_override_fret(ch: str, french_c: str) -> int | None:
    if french_c == "alt" and ch == "r":
        return 2
    letters = "abcdefghiklmnopqrst"
    if ch in letters:
        return letters.index(ch)
    return None


def _collect_override_chords(  # noqa: C901
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    bar_index: int,
    strings: int,
    style: str,
    default_duration: int,
    french_c: str,
) -> list[tuple[int, list[tuple[int, int]], int]]:
    cols = sorted({col for (b, _s, col) in overrides if b == bar_index})
    events: list[tuple[int, list[tuple[int, int]], int]] = []
    for col in cols:
        notes: list[tuple[int, int]] = []
        for s_idx in range(strings):
            key = (bar_index, s_idx, col)
            if key not in overrides:
                continue
            ch = overrides[key]
            if style == "italian":
                if ch.isdigit():
                    notes.append((s_idx, int(ch)))
                elif ch == "x":
                    notes.append((s_idx, 10))
            else:
                fret = _french_override_fret(ch, french_c)
                if fret is not None:
                    notes.append((s_idx, fret))
        if not notes:
            continue
        denom = default_duration
        for s_idx in range(strings):
            key = (bar_index, s_idx, col)
            if key in durations:
                denom = durations[key]
                break
        events.append((col, notes, denom))
    return events


def _barline_token(bar: Bar) -> str:
    repeat = bar.repeat or ""
    if repeat == ".:":
        return ".|:"
    if repeat == ":.":
        return ":|."
    if repeat == ".":
        return ".|."
    if repeat == ":|:":
        return ":|:"
    line = bar.barline or "|"
    mapping = {"|": "|", "||": "||", ":": ":", " ": ""}
    return mapping.get(line, "|")


def _repeat_mark_token(bar: Bar) -> str | None:
    repeat = (bar.repeat or "").strip()
    mapping = {
        "DC": "D.C.",
        "DS": "D.S.",
        "Fine": "Fine",
        "Coda": "Coda",
        "To Coda": "To Coda",
        "DC al Fine": "D.C. al Fine",
        "DC al Coda": "D.C. al Coda",
        "DS al Fine": "D.S. al Fine",
        "DS al Coda": "D.S. al Coda",
    }
    if repeat in mapping:
        return f'\\mark \\markup {{ "{mapping[repeat]}" }}'
    return None


def _ft3_fingering_text(value: str | None) -> str | None:
    if not value:
        return None
    if value == "thumb":
        return "t"
    if value == "dot1":
        return "."
    if value == "dot2":
        return ".."
    if value == "dot3":
        return "..."
    return value[:1]


def _ft3_ornament_text(value: str | None) -> str | None:
    if not value:
        return None
    mapping = {"dot-left": "."}
    return mapping.get(value, value[:1])


def _first_note_attr(notes, attr: str) -> str | None:
    for note in notes:
        value = getattr(note, attr, None)
        if value:
            return value
    return None


def _dedup_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _ft3_show_fingerings(settings: dict[str, str]) -> bool:
    return (
        settings.get("showfingerings", settings.get("showft3extras", "on")) == "on"
        and settings.get("ft3fingering", "both") != "off"
    )


def _ft3_show_ornaments(settings: dict[str, str]) -> bool:
    return (
        settings.get("showornaments", settings.get("showft3extras", "on")) == "on"
        and settings.get("ft3ornaments", "both") != "off"
    )


def _ft3_full_mode(settings: dict[str, str]) -> bool:
    return settings.get("tabnotation", "minimal") == "full"


def _note_left_fingering_text_for_export(note) -> str | None:
    value = getattr(note, "left_fingering", None)
    if not value:
        return None
    # Same sanity rule as TUI: LH 1-4 on open strings is usually not useful,
    # and often reflects editorial/barre semantics we do not engrave yet.
    if getattr(note, "fret", None) == 0 and value in {"1", "2", "3", "4"}:
        return None
    return _ft3_fingering_text(value)


def _note_barre_text_for_export(note) -> str | None:
    if getattr(note, "barre", False):
        return "barre"
    return None


def _note_native_lh_fingering_suffix(note, settings: dict[str, str]) -> str:
    if not (_ft3_full_mode(settings) and _ft3_show_fingerings(settings)):
        return ""
    mode = settings.get("ft3fingering", "both")
    if mode not in {"left", "both"}:
        return ""
    value = _note_left_fingering_text_for_export(note)
    if value and value.isdigit():
        return f"-{value}"
    return ""


def _note_native_rh_fingering_suffix(note, settings: dict[str, str]) -> str:
    if not (_ft3_full_mode(settings) and _ft3_show_fingerings(settings)):
        return ""
    mode = settings.get("ft3fingering", "both")
    if mode not in {"right", "both"}:
        return ""
    value = _ft3_fingering_text(getattr(note, "right_fingering", None))
    if value and value.isdigit():
        return f"\\rightHandFinger #{value}"
    if value == "t":
        return r'\rightHandFinger \markup { "t" }'
    return ""


def _chord_ft3_markup_suffix(chord, settings: dict[str, str]) -> str:  # noqa: C901, PLR0912
    if not _ft3_full_mode(settings):
        return ""
    show_fingerings = _ft3_show_fingerings(settings)
    show_ornaments = _ft3_show_ornaments(settings)
    if not (show_fingerings or show_ornaments):
        return ""

    finger_mode = settings.get("ft3fingering", "both")
    orn_mode = settings.get("ft3ornaments", "both")
    above: list[str] = []
    below: list[str] = []

    if show_fingerings and finger_mode != "off":
        if finger_mode in {"left", "both"}:
            for note in chord.notes:
                left_f = _note_left_fingering_text_for_export(note)
                # Numeric LH fingerings are exported natively on note/chord pitches.
                if left_f and not left_f.isdigit():
                    above.append(left_f)
                barre_text = _note_barre_text_for_export(note)
                if barre_text:
                    above.append(barre_text)
        if finger_mode in {"right", "both"}:
            for note in chord.notes:
                right_f = _ft3_fingering_text(getattr(note, "right_fingering", None))
                # Numeric RH fingerings and thumb are exported natively.
                if right_f and not (right_f.isdigit() or right_f == "t"):
                    below.append(right_f)
    if show_ornaments and orn_mode != "off":
        if orn_mode in {"left", "both"}:
            for note in chord.notes:
                left_o = _ft3_ornament_text(getattr(note, "left_ornament", None))
                if left_o:
                    above.append(left_o)
        if orn_mode in {"right", "both"}:
            for note in chord.notes:
                right_o = _ft3_ornament_text(getattr(note, "right_ornament", None))
                if right_o:
                    below.append(right_o)

    above = _dedup_keep_order(above)
    below = _dedup_keep_order(below)

    parts: list[str] = []
    if show_ornaments and any(getattr(note, "arpeggio", None) for note in chord.notes):
        parts.append(r"\arpeggio")
    if above:
        text = _escape_lilypond(" ".join(above))
        parts.append(f'^\\markup {{ \\tiny "{text}" }}')
    if below:
        text = _escape_lilypond(" ".join(below))
        parts.append(f'_\\markup {{ \\tiny "{text}" }}')
    return (" " + " ".join(parts)) if parts else ""


def _bar_sign_mark_tokens(bar: Bar) -> list[str]:
    marks: list[str] = []
    if bar.dynamic:
        marks.append(f'\\mark \\markup {{ "{_escape_lilypond(bar.dynamic)}" }}')
    if bar.fermata:
        marks.append(r'\mark \markup { \musicglyph "scripts.ufermata" }')
    return marks


def _piece_has_lyrics(piece: Piece) -> bool:
    return any(any(line.strip() for line in bar.lyrics) or bar.lyric_event_rows for bar in piece.bars)


def _piece_has_melody(piece: Piece) -> bool:
    for bar in piece.bars:
        if any((event.text or "").strip() for event in bar.melody_events):
            return True
        if bar.melody_grid and bar.melody_grid.strip():
            return True
    return False


def _piece_has_tab_content(piece: Piece) -> bool:
    return any(bar.chords or bar.notes for bar in piece.bars)


def _imported_staff_by_kind(piece: Piece, kind: str) -> ImportedStaff | None:
    staffs = _imported_staffs_by_kind(piece, kind)
    return staffs[0] if staffs else None


def _imported_staffs_by_kind(piece: Piece, kind: str) -> list[ImportedStaff]:
    imported = piece.imported_score
    if imported is None:
        return []
    return [staff for staff in imported.staffs if staff.kind == kind and staff.bars]


def _imported_bar_content_score(bar: ImportedBarContent, kind: str) -> int:
    if kind == "note":
        return len(bar.melody_events) * 10 + int(bool((bar.melody_grid or "").strip()))
    if kind == "lyrics":
        event_count = sum(len(row) for row in bar.lyric_event_rows)
        return event_count * 10 + sum(bool(line.strip()) for line in bar.lyrics)
    return sum(
        (
            bool(bar.time_sig),
            bool(bar.barline),
            bool(bar.repeat),
            bool(bar.ending_numbers),
            bool(bar.system_break),
        ),
    )


def _coalesced_imported_bars(
    staff: ImportedStaff | None,
    *,
    kind: str,
) -> dict[int, ImportedBarContent]:
    if staff is None:
        return {}
    grouped: dict[int, list[ImportedBarContent]] = {}
    for bar in staff.bars:
        grouped.setdefault(bar.source_bar_index, []).append(bar)
    out: dict[int, ImportedBarContent] = {}
    for source_bar_index, candidates in grouped.items():
        primary = max(candidates, key=lambda bar: _imported_bar_content_score(bar, kind))
        out[source_bar_index] = replace(
            primary,
            time_sig=next((bar.time_sig for bar in candidates if bar.time_sig), None),
            barline=next((bar.barline for bar in candidates if bar.barline), None),
            repeat=next((bar.repeat for bar in candidates if bar.repeat), None),
            ending_numbers=next(
                (bar.ending_numbers for bar in candidates if bar.ending_numbers),
                (),
            ),
            system_break=any(bar.system_break for bar in candidates),
        )
    return out


def _with_imported_bar_structure(
    content: ImportedBarContent,
    *fallbacks: ImportedBarContent | None,
) -> ImportedBarContent:
    available = [bar for bar in fallbacks if bar is not None]
    return replace(
        content,
        time_sig=content.time_sig or next((bar.time_sig for bar in available if bar.time_sig), None),
        barline=content.barline or next((bar.barline for bar in available if bar.barline), None),
        repeat=content.repeat or next((bar.repeat for bar in available if bar.repeat), None),
        ending_numbers=content.ending_numbers
        or next((bar.ending_numbers for bar in available if bar.ending_numbers), ()),
        system_break=content.system_break or any(bar.system_break for bar in available),
    )


def _piece_bar_as_imported(piece: Piece, source_bar_index: int) -> ImportedBarContent | None:
    if not (0 <= source_bar_index < len(piece.bars)):
        return None
    bar = piece.bars[source_bar_index]
    return ImportedBarContent(
        source_bar_index=source_bar_index,
        time_sig=bar.time_sig,
        barline=bar.barline,
        repeat=bar.repeat,
        ending_numbers=bar.ending_numbers,
        system_break=bar.system_break,
    )


def _piece_has_imported_lyrics(piece: Piece) -> bool:
    return any(
        bar.lyric_event_rows or any(line.strip() for line in bar.lyrics)
        for staff in _imported_staffs_by_kind(piece, "lyrics")
        for bar in staff.bars
    )


def _initial_time_sig(piece: Piece, settings: dict[str, str]) -> str | None:
    time_sig = settings.get("time", "") or ""
    if not time_sig:
        for bar in piece.bars:
            if bar.time_sig:
                time_sig = bar.time_sig
                break
    if not time_sig and piece.imported_score is not None:
        for staff in piece.imported_score.staffs:
            for bar in staff.bars:
                if bar.time_sig:
                    time_sig = bar.time_sig
                    break
            if time_sig:
                break
    return _normalized_time_sig_or_none(time_sig)


def _initial_key_sig(piece: Piece, settings: dict[str, str]) -> tuple[str, str] | None:
    key_sig = settings.get("key", "") or ""
    if not key_sig:
        key_sig = piece.key or ""
    if not key_sig:
        return None
    return _parse_key_signature(key_sig)


def _append_global_prefix(body: list[str], piece: Piece, settings: dict[str, str]) -> str | None:
    current_time_sig = _initial_time_sig(piece, settings)
    time_sig_style_cmd = _time_sig_style_command(settings)
    if time_sig_style_cmd:
        body.append(f"  {time_sig_style_cmd}")
    if current_time_sig:
        body.append(f"  \\time {current_time_sig}")
    parsed_key = _initial_key_sig(piece, settings)
    if parsed_key is not None:
        key_pitch, key_mode = parsed_key
        body.append(f"  \\key {key_pitch} \\{key_mode}")
    return current_time_sig


def _lily_note_from_event_text(text: str) -> str | None:
    cleaned = (text or "").strip()
    if not cleaned:
        return None
    if cleaned.lower() in {"r", "rest"}:
        return "r"
    match = re.fullmatch(r"([A-Ga-g])([#b]?)([,']*)", cleaned)
    if match is None:
        return None
    note, accidental, octave_marks = match.groups()
    base = note.lower()
    if accidental == "#":
        base += "is"
    elif accidental == "b":
        base += "es"
    return f"{base}{octave_marks}"


def _raw_lyric_tokens(line: str, event_count: int) -> list[str]:
    text = (line or "").strip()
    if not text:
        return ["_"] * event_count
    words = [word for word in text.split() if word]
    if not words:
        return ["_"] * event_count
    tokens = [f'"{_escape_lilypond(word)}"' for word in words[:event_count]]
    if len(tokens) < event_count:
        tokens.extend(["_"] * (event_count - len(tokens)))
    return tokens


def _append_bar_time_change(body: list[str], bar: Bar, current_time_sig: str | None) -> str | None:
    bar_time_sig = _normalized_time_sig_or_none(bar.time_sig)
    if bar_time_sig and bar_time_sig != current_time_sig:
        body.append(f"  \\time {bar_time_sig}")
        return bar_time_sig
    return current_time_sig


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
                    target_tuning_pitches=tuning_pitches,
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
                    target_tuning_pitches=tuning_pitches,
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
                if not pitches:
                    body.append(f"  r{dur}")
                elif len(pitches) == 1:
                    body.append(f"  {pitches[0]}{dur}{suffix}")
                else:
                    body.append(f"  <{' '.join(pitches)}>{dur}{suffix}")
        bar_marker = _barline_token(bar)
        body.append("  |" if bar_marker == "|" else f'  \\bar "{bar_marker}"')
        if bar.system_break:
            body.append(r"  \break")
    return body


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


def _build_vocal_bodies(
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


def _append_imported_melody_bar(
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


def _tab_staff_with_block(
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


def _build_main_blocks(
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


def export_lilypond(
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
) -> str:
    _ = (bar_width, ornaments, annotations, slurs, ties, holds)
    settings = settings or {}
    title = piece.title or "Untitled"
    composer = piece.composer or piece.author or ""
    header = [r'\version "2.24.0"', r"\header {"]
    header.append(f'  title = "{_escape_lilypond(title)}"')
    if composer:
        header.append(f'  composer = "{_escape_lilypond(composer)}"')
    header.append("}")

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
    content = "\n".join(
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
        # Some LilyPond builds ignore directory components in -o when passed odd paths;
        # check the process cwd fallback basename before reporting failure.
        cwd_fallback = Path.cwd() / f"{out_base.name}.pdf"
        if cwd_fallback.exists():
            pdf_path = cwd_fallback.resolve()
    if not pdf_path.exists():
        return f"LilyPond finished but PDF not found: {pdf_path}"
    return f"Printed {pdf_path}"
