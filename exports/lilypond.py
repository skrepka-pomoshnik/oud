from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from core.model import Piece
from core.render_utils import note_type_to_denom


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
                note, 0
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


def _normalize_key(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    note = text[0].lower()
    acc = text[1:]
    acc = acc.replace("#", "is").replace("b", "es")
    return note + acc


def _parse_fret_labels(value: str) -> list[str]:
    if not value:
        return []
    items = [item.strip() for item in value.replace(",", " ").split()]
    return [item for item in items if item]


def _default_tuning(strings: int) -> list[int]:
    defaults = [
        "g4",
        "d4",
        "a3",
        "f3",
        "c3",
        "g2",
        "f2",
        "e2",
        "d2",
        "c2",
    ]
    return _parse_tuning("".join(defaults))[:strings]


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


def _collect_override_chords(
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    bar_index: int,
    strings: int,
    style: str,
    default_duration: int,
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
            elif "a" <= ch <= "p":
                notes.append((s_idx, ord(ch) - ord("a")))
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


def export_lilypond(  # noqa: PLR0912
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
    settings = settings or {}
    title = piece.title or "Untitled"
    composer = piece.composer or piece.author or ""
    tuning = settings.get("tuning", "") or ""
    tuning_pitches = _parse_tuning(tuning) if tuning else _default_tuning(piece.strings)
    if len(tuning_pitches) < piece.strings:
        tuning_pitches.extend(_default_tuning(piece.strings)[len(tuning_pitches) :])
    main_pitches, bass_pitches = _split_tuning(tuning_pitches, piece.strings)
    tuning_names = [_midi_to_lilypond(p) for p in main_pitches]
    tuning_text = " ".join(tuning_names)
    tuning_lookup = list(reversed(main_pitches))
    bass_text = ""
    extra_bass = settings.get("basstuning", "") or settings.get("bassstrings", "") or ""
    if extra_bass:
        bass_pitches = _parse_tuning(extra_bass)
    if bass_pitches:
        bass_text = " ".join(_midi_to_lilypond(p) for p in bass_pitches)

    time_sig = settings.get("time", "") or ""
    if not time_sig:
        for bar in piece.bars:
            if bar.time_sig:
                time_sig = bar.time_sig
                break
    key_sig = settings.get("key", "") or ""
    header = [r'\version "2.24.0"', r"\header {"]
    header.append(f'  title = "{_escape_lilypond(title)}"')
    if composer:
        header.append(f'  composer = "{_escape_lilypond(composer)}"')
    header.append("}")

    body: list[str] = []
    if time_sig:
        body.append(f"  \\time {_normalize_time_sig(time_sig)}")
    if key_sig:
        body.append(f"  \\key {_normalize_key(key_sig)} \\major")

    default_duration = 4
    style = settings.get("style") or "french"
    for b_idx, bar in enumerate(piece.bars):
        if bar.chords:
            for chord in bar.chords:
                denom = note_type_to_denom(chord.note_type) or default_duration
                dur = _duration_token(denom, chord.dotted)
                pitches: list[str] = []
                for note in chord.notes:
                    s_idx = note.string - 1
                    if 0 <= s_idx < len(tuning_lookup):
                        pitch = tuning_lookup[s_idx] + note.fret
                        pitches.append(_midi_to_lilypond(pitch))
                if not pitches:
                    body.append(f"  r{dur}")
                elif len(pitches) == 1:
                    body.append(f"  {pitches[0]}{dur}")
                else:
                    chord_text = " ".join(pitches)
                    body.append(f"  <{chord_text}>{dur}")
        else:
            events = _collect_override_chords(
                overrides, durations, b_idx, piece.strings, style, default_duration
            )
            if not events:
                body.append("  r4")
            for _col, notes, denom in events:
                dur = _duration_token(denom, False)
                pitches: list[str] = []
                for s_idx, fret in notes:
                    if 0 <= s_idx < len(tuning_lookup):
                        pitches.append(_midi_to_lilypond(tuning_lookup[s_idx] + fret))
                if not pitches:
                    body.append(f"  r{dur}")
                elif len(pitches) == 1:
                    body.append(f"  {pitches[0]}{dur}")
                else:
                    body.append(f"  <{' '.join(pitches)}>{dur}")
        body.append("  |")

    layout: list[str] = [r"\layout {", r"  \context {", r"    \Score"]
    if style == "french":
        layout.append("    tablatureFormat = #fret-letter-tablature-format")
    layout += [r"  }", r"  \context {", r"    \TabStaff"]
    if style == "french":
        labels = _parse_fret_labels(settings.get("fretlabels", "") or "")
        if not labels:
            labels = ["a", "b", "r", "d", "e", "f", "g", "h", "i", "k", "l"]
        labels_text = " ".join(f"\"{label}\"" for label in labels)
        layout.append(f"    fretLabels = #'({labels_text})")
    layout.append(f"    stringTunings = \\stringTuning <{tuning_text}>")
    if bass_text:
        layout.append(f"    additionalBassStrings = \\stringTuning <{bass_text}>")
    layout += [r"  }", r"}"]

    content = "\n".join(
        [
            *header,
            "",
            r"\paper { indent = 0\mm }",
            "",
            r"\new TabStaff {",
            r"  \tabFullNotation",
            *body,
            r"}",
            "",
            *layout,
            "",
        ]
    )
    Path(path).write_text(content, encoding="utf-8")
    return f"Wrote {path}"


def print_lilypond_pdf(ly_path: str, output_base: str | None = None) -> str:
    lilypond = shutil.which("lilypond")
    if lilypond is None:
        return "LilyPond not found on PATH"
    cmd = [lilypond]
    if output_base:
        cmd += ["-o", output_base]
    cmd.append(ly_path)
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)  # noqa: S603
    except subprocess.CalledProcessError as exc:
        err = (exc.stderr or "").strip()
        detail = err.splitlines()[-1] if err else "unknown error"
        return f"LilyPond failed: {detail}"
    if output_base:
        return f"Printed {output_base}.pdf"
    pdf_path = str(Path(ly_path).with_suffix(".pdf"))
    return f"Printed {pdf_path}"
