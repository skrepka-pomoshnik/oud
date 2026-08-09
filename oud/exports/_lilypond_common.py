from __future__ import annotations

import re
from dataclasses import replace

from petrucci.model import Bar, ImportedBarContent, ImportedStaff, Piece
from petrucci.tab_input import editor_event_columns, editor_fret_at


def _escape_lilypond(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _single_line(text: str | None) -> str:
    return " ".join((text or "").split())


def _metadata_comments(piece: Piece) -> list[str]:
    fields = (
        ("source format", piece.imported_score.source_format if piece.imported_score is not None else None),
        ("source", piece.source),
        ("editor", piece.editor),
        ("publisher", piece.publisher),
        ("volume", piece.volume),
        ("page", piece.page),
        ("type", piece.piece_type),
        ("difficulty", piece.difficulty),
        ("ensemble", piece.ensemble),
        ("part", piece.part),
        ("instrumentation", piece.instrumentation),
        ("comment", piece.comment),
    )
    comments = [f"% oud {label}: {_single_line(value)}" for label, value in fields if _single_line(value)]
    comments.extend(
        f"% oud metadata {key}: {_single_line(value)}"
        for key, value in sorted(piece.section_annotations.items())
        if _single_line(value)
    )
    if piece.imported_score is not None:
        comments.extend(
            f"% oud staff {index}: {staff.kind} | {_single_line(staff.label) or '(unlabeled)'} | {len(staff.bars)} bars"
            for index, staff in enumerate(piece.imported_score.staffs, start=1)
        )
        comments.extend(
            f"% oud bar {bar.source_bar_index + 1} comment: {_single_line(text)}"
            for staff in piece.imported_score.staffs
            for bar in staff.bars
            for text in bar.editorial_text
            if _single_line(text)
        )
    return comments


def _lilypond_header(piece: Piece, version: str = "2.26") -> list[str]:  # noqa: C901
    title = piece.title or "Untitled"
    composer = piece.composer or piece.author or ""
    source_version = "2.24.0" if version == "2.24" else "2.26.0"
    header = [f'\\version "{source_version}"', *_metadata_comments(piece), r"\header {"]
    header.append(f'  title = "{_escape_lilypond(title)}"')
    if piece.subtitle:
        header.append(f'  subtitle = "{_escape_lilypond(_single_line(piece.subtitle))}"')
    if composer:
        header.append(f'  composer = "{_escape_lilypond(composer)}"')
    if piece.author and piece.author != composer:
        header.append(f'  poet = "{_escape_lilypond(_single_line(piece.author))}"')
    if piece.arranger:
        header.append(f'  arranger = "{_escape_lilypond(_single_line(piece.arranger))}"')
    if piece.piece_type or piece.part:
        description = " | ".join(value for value in (piece.piece_type, piece.part) if value)
        header.append(f'  piece = "{_escape_lilypond(_single_line(description))}"')
    if piece.volume:
        header.append(f'  opus = "{_escape_lilypond(_single_line(piece.volume))}"')
    source = ", page ".join(value for value in (piece.source, piece.page) if value)
    if source:
        header.append(f'  source = "{_escape_lilypond(_single_line(source))}"')
    if piece.publisher:
        header.append(f'  copyright = "{_escape_lilypond(_single_line(piece.publisher))}"')
    if piece.footnote:
        header.append(f'  tagline = "{_escape_lilypond(_single_line(piece.footnote))}"')
    header.append("}")
    return header


def _parse_tuning(tuning: str) -> list[int]:  # noqa: C901
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
    settings: dict[str, str],
) -> list[str]:
    pitch_notes: list[tuple[object, int]] = []
    for note in notes:
        pitch = _note_pitch_from_lookup(note, source_tuning_lookup)
        if pitch is not None:
            pitch_notes.append((note, pitch))
    if not pitch_notes:
        return []
    out: list[str] = []
    for note, pitch in pitch_notes:
        base = _midi_to_lilypond(pitch)
        native = _note_native_lh_fingering_suffix(note, settings) + _note_native_rh_fingering_suffix(note, settings)
        out.append(base + native)
    return out


def _lily_pitches_for_override_event(
    notes: list[tuple[int, int]],
    *,
    target_tuning_lookup: list[int],
) -> list[str]:
    pitches: list[int] = []
    for s_idx, fret in notes:
        if 0 <= s_idx < len(target_tuning_lookup):
            pitches.append(target_tuning_lookup[s_idx] + fret)
    if not pitches:
        return []
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


def _collect_override_chords(  # noqa: C901, PLR0917 - legacy grid projection pending typed export context
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    bar_index: int,
    strings: int,
    style: str,
    default_duration: int,
    french_c: str,
) -> list[tuple[int, list[tuple[int, int]], int]]:
    cols = editor_event_columns(overrides, bar_index=bar_index)
    events: list[tuple[int, list[tuple[int, int]], int]] = []
    for col in cols:
        notes: list[tuple[int, int]] = []
        for s_idx in range(strings):
            key = (bar_index, s_idx, col)
            if key not in overrides:
                continue
            fret = editor_fret_at(
                overrides,
                durations,
                bar_index=bar_index,
                string_index=s_idx,
                column=col,
                style=style,
                french_c_shape=french_c,
            )
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
    mapping = {
        "dot-left": ".",
        "caret": "^",
        "parenthesis": "(",
        "smile": "u",
        "under-hook": "u",
        "under-v": "v",
    }
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
    if getattr(note, "editorial_brackets", False):
        return "[ ]"
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


def _initial_time_sig(piece: Piece, settings: dict[str, str]) -> str | None:  # noqa: C901
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


def _append_barline(body: list[str], bar: Bar) -> None:
    """Print a source barline and register the following bar at measure zero."""
    body.append(f'  \\bar "{_barline_token(bar)}"')
    body.append(r"  \set Timing.measurePosition = #ZERO-MOMENT")
    body.append(r"  \allowBreak")
