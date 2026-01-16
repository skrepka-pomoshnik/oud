from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple

from model import Piece
from render_utils import note_type_to_denom


def _escape_lilypond(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _parse_tuning(tuning: str) -> List[int]:
    pitches: List[int] = []
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


def _default_tuning(strings: int) -> List[int]:
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
    overrides: Dict[Tuple[int, int, int], str],
    durations: Dict[Tuple[int, int, int], int],
    bar_index: int,
    strings: int,
    style: str,
    default_duration: int,
) -> List[tuple[int, List[tuple[int, int]], int]]:
    cols = sorted({col for (b, _s, col) in overrides.keys() if b == bar_index})
    events: List[tuple[int, List[int], int]] = []
    for col in cols:
        notes: List[tuple[int, int]] = []
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
                if "a" <= ch <= "p":
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


def export_lilypond(
    path: str,
    piece: Piece,
    overrides: Dict[Tuple[int, int, int], str],
    durations: Dict[Tuple[int, int, int], int],
    bar_width: int,
    settings: Dict[str, str | None] | None = None,
    ornaments: Dict[Tuple[int, int], str] | None = None,
    annotations: Dict[Tuple[int, int], str] | None = None,
    slurs: List[Tuple[int, int, int]] | None = None,
    ties: List[Tuple[int, int, int]] | None = None,
    holds: List[Tuple[int, int, int]] | None = None,
) -> str:
    settings = settings or {}
    title = piece.title or "Untitled"
    composer = piece.composer or piece.author or ""
    tuning = settings.get("tuning", "") or ""
    tuning_pitches = _parse_tuning(tuning) if tuning else _default_tuning(piece.strings)
    if len(tuning_pitches) < piece.strings:
        tuning_pitches.extend(_default_tuning(piece.strings)[len(tuning_pitches) :])
    tuning_names = [_midi_to_lilypond(p) for p in tuning_pitches]
    tuning_text = " ".join(tuning_names)

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

    body: List[str] = []
    if time_sig:
        body.append(f"  \\time {time_sig}")
    if key_sig:
        body.append(f"  \\key {key_sig} \\major")

    default_duration = 4
    style = settings.get("style", "french")
    for b_idx, bar in enumerate(piece.bars):
        if bar.chords:
            for chord in bar.chords:
                denom = note_type_to_denom(chord.note_type) or default_duration
                dur = _duration_token(denom, chord.dotted)
                pitches: List[str] = []
                for note in chord.notes:
                    s_idx = note.string - 1
                    if 0 <= s_idx < len(tuning_pitches):
                        pitch = tuning_pitches[s_idx] + note.fret
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
                pitches: List[str] = []
                for s_idx, fret in notes:
                    if 0 <= s_idx < len(tuning_pitches):
                        pitches.append(_midi_to_lilypond(tuning_pitches[s_idx] + fret))
                if not pitches:
                    body.append(f"  r{dur}")
                elif len(pitches) == 1:
                    body.append(f"  {pitches[0]}{dur}")
                else:
                    body.append(f"  <{' '.join(pitches)}>{dur}")
        body.append("  |")

    content = "\n".join(
        header
        + [
            "",
            r"\paper { indent = 0\mm }",
            "",
            r"\new TabStaff \with {",
            f"  stringTunings = \\stringTuning <{tuning_text}>",
            r"} {",
            r"  \tabFullNotation",
        ]
        + body
        + [
            r"}",
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
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        err = (exc.stderr or "").strip()
        detail = err.splitlines()[-1] if err else "unknown error"
        return f"LilyPond failed: {detail}"
    if output_base:
        return f"Printed {output_base}.pdf"
    pdf_path = str(Path(ly_path).with_suffix(".pdf"))
    return f"Printed {pdf_path}"
