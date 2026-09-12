from __future__ import annotations

import zipfile
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from xml.etree import ElementTree as ET

from petrucci.core.model import Bar, Chord, Note, Piece


@dataclass(frozen=True)
class _TimedTabNote:
    onset: int
    duration: int
    string: int
    fret: int


_RHYTHMS = tuple(
    (Fraction(4, denominator) * (Fraction(3, 2) if dotted else 1), note_type, dotted)
    for note_type, denominator in enumerate((1, 2, 4, 8, 16, 32, 64, 128, 256), start=2)
    for dotted in (False, True)
)

_TYPE_TO_DENOM = {
    "whole": 1,
    "half": 2,
    "quarter": 4,
    "eighth": 8,
    "16th": 16,
    "32nd": 32,
    "64th": 64,
    "128th": 128,
    "256th": 256,
}

_DENOM_TO_NOTE_TYPE = {
    1: 2,
    2: 3,
    4: 4,
    8: 5,
    16: 6,
    32: 7,
    64: 8,
    128: 9,
    256: 10,
}


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _child(node: ET.Element, name: str) -> ET.Element | None:
    for ch in list(node):
        if _local(ch.tag) == name:
            return ch
    return None


def _children(node: ET.Element, name: str) -> list[ET.Element]:
    return [ch for ch in list(node) if _local(ch.tag) == name]


def _text(node: ET.Element | None) -> str:
    return (node.text or "").strip() if node is not None else ""


def _note_type(note_node: ET.Element) -> tuple[int, bool]:
    type_text = _text(_child(note_node, "type")).lower()
    denom = _TYPE_TO_DENOM.get(type_text, 4)
    note_type = _DENOM_TO_NOTE_TYPE.get(denom, 4)
    dotted = _child(note_node, "dot") is not None
    return note_type, dotted


def _technical(note_node: ET.Element) -> tuple[int, int] | None:
    notations = _child(note_node, "notations")
    if notations is None:
        return None
    technical = _child(notations, "technical")
    if technical is None:
        return None
    string_text = _text(_child(technical, "string"))
    fret_text = _text(_child(technical, "fret"))
    if not string_text.isdigit() or not fret_text.isdigit():
        return None
    return int(string_text), int(fret_text)


def _measure_time(measure: ET.Element) -> str | None:
    attributes = _child(measure, "attributes")
    if attributes is None:
        return None
    time = _child(attributes, "time")
    if time is None:
        return None
    beats = _text(_child(time, "beats"))
    beat_type = _text(_child(time, "beat-type"))
    if beats.isdigit() and beat_type.isdigit():
        return f"{beats}/{beat_type}"
    return None


def _measure_repeat(measure: ET.Element) -> str | None:
    for barline in _children(measure, "barline"):
        repeat = _child(barline, "repeat")
        if repeat is None:
            continue
        direction = (repeat.get("direction") or "").strip().lower()
        if direction == "forward":
            return ".:"
        if direction == "backward":
            return ":."
    return None


def _duration_units(node: ET.Element) -> int:
    duration = _text(_child(node, "duration"))
    try:
        return max(0, int(duration))
    except ValueError:
        return 0


def _measure_divisions(measure: ET.Element, inherited: int) -> int:
    attributes = _child(measure, "attributes")
    divisions = _text(_child(attributes, "divisions")) if attributes is not None else ""
    try:
        return max(1, int(divisions))
    except ValueError:
        return inherited


def _staff_lines(measure: ET.Element, inherited: int) -> int:
    attributes = _child(measure, "attributes")
    staff = _child(attributes, "staff-details") if attributes is not None else None
    lines = _text(_child(staff, "staff-lines")) if staff is not None else ""
    try:
        return max(1, int(lines))
    except ValueError:
        return inherited


def _rhythm_for_duration(duration: int, divisions: int) -> tuple[int, bool]:
    value = Fraction(max(1, duration), max(1, divisions))
    _, note_type, dotted = min(
        _RHYTHMS,
        key=lambda candidate: (abs(candidate[0] - value), candidate[2], candidate[1]),
    )
    return note_type, dotted


def _timed_notes(measure: ET.Element) -> tuple[list[_TimedTabNote], int]:
    cursor = 0
    previous_onset = 0
    measure_end = 0
    notes: list[_TimedTabNote] = []
    for node in measure:
        tag = _local(node.tag)
        if tag == "backup":
            cursor = max(0, cursor - _duration_units(node))
            continue
        if tag == "forward":
            cursor += _duration_units(node)
            measure_end = max(measure_end, cursor)
            continue
        if tag != "note":
            continue
        duration = _duration_units(node)
        is_chord = _child(node, "chord") is not None
        onset = previous_onset if is_chord else cursor
        if not is_chord:
            previous_onset = onset
            cursor += duration
        measure_end = max(measure_end, onset + duration, cursor)
        technical = _technical(node)
        if technical is None or _child(node, "rest") is not None:
            continue
        notes.append(_TimedTabNote(onset, duration, technical[0], technical[1]))
    return notes, measure_end


def _group_timed_notes(notes: list[_TimedTabNote], measure_end: int, divisions: int) -> list[Chord]:
    grouped: dict[int, dict[tuple[int, int], _TimedTabNote]] = {}
    for note in notes:
        grouped.setdefault(note.onset, {})[(note.string, note.fret)] = note
    onsets = sorted(grouped)
    events: list[Chord] = []
    for index, onset in enumerate(onsets):
        timed = list(grouped[onset].values())
        event_end = onsets[index + 1] if index + 1 < len(onsets) else measure_end
        duration = event_end - onset
        if duration <= 0:
            duration = max((note.duration for note in timed), default=divisions)
        note_type, dotted = _rhythm_for_duration(duration, divisions)
        events.append(
            Chord(
                note_type=note_type,
                dotted=dotted,
                grid=None,
                notes=[Note(note.string, note.fret, 0) for note in timed],
            )
        )
    return events


def _rest_chord(measure: ET.Element) -> Chord | None:
    for note_node in _children(measure, "note"):
        if _child(note_node, "rest") is None:
            continue
        note_type, dotted = _note_type(note_node)
        return Chord(note_type=note_type, dotted=dotted, grid=None, notes=[])
    return None


def _parse_measure(measure: ET.Element, divisions: int) -> tuple[Bar, int]:
    bar = Bar()
    bar.time_sig = _measure_time(measure)
    bar.repeat = _measure_repeat(measure)
    notes, measure_end = _timed_notes(measure)
    bar.chords = _group_timed_notes(notes, measure_end, divisions)
    if not bar.chords:
        rest = _rest_chord(measure)
        if rest is not None:
            bar.chords.append(rest)
    return bar, max((note.string for note in notes), default=0)


def _technical_count(part: ET.Element) -> int:
    return sum(
        _technical(note) is not None for measure in _children(part, "measure") for note in _children(measure, "note")
    )


def _piece_metadata(root: ET.Element) -> tuple[str, str | None]:
    work = _child(root, "work")
    work_title = _child(work, "work-title") if work is not None else None
    title = _text(work_title) or "Untitled"
    composer = None
    identification = _child(root, "identification")
    if identification is not None:
        for creator in _children(identification, "creator"):
            ctype = (creator.get("type") or "").strip().lower()
            if ctype == "composer":
                composer = _text(creator) or None
                break
    return title, composer


def _parse_musicxml_part(part: ET.Element) -> tuple[list[Bar], int]:
    bars: list[Bar] = []
    strings = 6
    divisions = 1
    for measure in _children(part, "measure"):
        divisions = _measure_divisions(measure, divisions)
        bar, max_string = _parse_measure(measure, divisions)
        bars.append(bar)
        strings = max(_staff_lines(measure, strings), max_string)
    return bars, strings


def _parse_piece(root: ET.Element) -> Piece:
    title, composer = _piece_metadata(root)
    part = max(_children(root, "part"), key=_technical_count, default=None)
    bars, strings = _parse_musicxml_part(part) if part is not None else ([], 6)
    return Piece(title=title, composer=composer, bars=bars, strings=strings)


def load_musicxml(path: str) -> Piece:
    root = ET.fromstring(Path(path).read_text(encoding="utf-8"))  # noqa: S314
    return _parse_piece(root)


def load_mxl(path: str) -> Piece:
    with zipfile.ZipFile(path) as zf:
        name = None
        if "META-INF/container.xml" in zf.namelist():
            container = ET.fromstring(zf.read("META-INF/container.xml"))  # noqa: S314
            for rootfile in container.iter():
                if _local(rootfile.tag) == "rootfile":
                    full_path = (rootfile.get("full-path") or "").strip()
                    if full_path:
                        name = full_path
                        break
        if name is None:
            xml_files = [n for n in zf.namelist() if n.lower().endswith(".xml")]
            if not xml_files:
                return Piece(title="Untitled", bars=[])
            name = xml_files[0]
        root = ET.fromstring(zf.read(name))  # noqa: S314
    return _parse_piece(root)
