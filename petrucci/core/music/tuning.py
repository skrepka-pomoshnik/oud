from __future__ import annotations


def tuning_count(tuning: str) -> int:
    count = 0
    idx = 0
    while idx < len(tuning):
        ch = tuning[idx]
        if ch.isalpha():
            count += 1
            idx += 1
            if idx < len(tuning) and tuning[idx] in "+-#b":
                idx += 1
            while idx < len(tuning) and tuning[idx].isdigit():
                idx += 1
        else:
            idx += 1
    return count


def parse_tuning_pitches(tuning: str) -> list[int]:
    pitches: list[int] = []
    idx = 0
    text = (tuning or "").strip()
    while idx < len(text):
        if text[idx].isalpha():
            midi, idx = _parse_tuning_pitch(text, idx)
            if midi is not None:
                pitches.append(midi)
        else:
            idx += 1
    pitches.reverse()  # return high -> low (string1..N)
    return pitches


def _parse_tuning_pitch(text: str, index: int) -> tuple[int | None, int]:
    note = text[index].upper()
    index += 1
    accidental = ""
    if index < len(text) and text[index] in "+-#b":
        accidental = text[index]
        index += 1
    octave_start = index
    while index < len(text) and text[index].isdigit():
        index += 1
    octave_text = text[octave_start:index]
    octave = int(octave_text) if octave_text else 3
    semitones = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}.get(note, 0)
    semitones += {"+": 1, "#": 1, "-": -1, "b": -1}.get(accidental, 0)
    midi = (octave + 1) * 12 + semitones
    midi_min = 0
    midi_max = 127
    return (midi if midi_min <= midi <= midi_max else None), index


def tuning_preset(value: str) -> str | None:
    presets = {
        "renaissance6": "g2c3f3a3d4g4",
        "renaissance": "g2c3f3a3d4g4",
        "renaissance7": "f2g2c3f3a3d4g4",
        "renaissance8": "e2f2g2c3f3a3d4g4",
        "renaissance9": "d2e2f2g2c3f3a3d4g4",
        "renaissance10": "c2d2e2f2g2c3f3a3d4g4",
        "renaissance11": "b1c2d2e2f2g2c3f3a3d4g4",
        "renaissance12": "a1b1c2d2e2f2g2c3f3a3d4g4",
        "renaissance13": "g1a1b1c2d2e2f2g2c3f3a3d4g4",
        "guitarlute": "e2a2d3g3b3e4",
        "guitar": "e4a3d3f+3b2e2",
        "dminor": "a4b-4c4d4e4f4g4a3d3f3a2d2f2",
        "sharp": "c4d4e4f+4g4a3d3g3b2d2f+2",
        "flat": "c4d4e-4f4g4a3d3g3a+2d2f2",
    }
    aliases = {
        # Common shorthand family aliases.
        "ren6": "renaissance6",
        "ren7": "renaissance7",
        "ren8": "renaissance8",
        "ren9": "renaissance9",
        "ren10": "renaissance10",
        "ren11": "renaissance11",
        "ren12": "renaissance12",
        "ren13": "renaissance13",
        # Baroque lute family defaults (11c / 13c d-minor and variants).
        "baroque": "dminor",
        "baroque11": "dminor",
        "baroque13": "dminor",
        "baroque-dminor": "dminor",
        "baroque-sharp": "sharp",
        "baroque-flat": "flat",
    }
    key = aliases.get(value, value)
    return presets.get(key)


def parse_bass_strings(value: str) -> list[str]:
    if not value:
        return []
    tokens: list[str] = []
    for part in value.replace(",", " ").split():
        token = part.strip()
        if not token:
            continue
        if not any(ch.isalpha() for ch in token):
            continue
        tokens.append(token)
    return tokens


def default_bass_strings(missing: int) -> list[str]:
    # Conservative fallback for files with extra courses but no explicit tuning metadata.
    # Starts from d2 (common 7-course extension in many lute sources) and descends.
    series = ["d2", "c2", "b1", "a1", "g1", "f1", "e1", "d1", "c1", "b0", "a0"]
    if missing <= 0:
        return []
    return series[:missing]


def default_tuning_pitches(strings: int) -> list[int]:
    """Return high-to-low courses, preserving FT3's low-to-high diapason rows."""

    if strings <= 0:
        return []
    primary = parse_tuning_pitches(tuning_preset("renaissance6") or "")
    if strings <= len(primary):
        return primary[:strings]
    bass = parse_tuning_pitches("".join(default_bass_strings(strings - len(primary))))
    return primary + bass
