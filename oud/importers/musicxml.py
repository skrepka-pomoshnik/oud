from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from petrucci.core.model import Bar, Chord, Note, Piece

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


def _parse_measure(measure: ET.Element) -> Bar:
    bar = Bar()
    bar.time_sig = _measure_time(measure)
    bar.repeat = _measure_repeat(measure)
    events: list[Chord] = []
    pending: Chord | None = None
    for note_node in _children(measure, "note"):
        is_chord_tone = _child(note_node, "chord") is not None
        note_type, dotted = _note_type(note_node)
        tech = _technical(note_node)
        is_rest = _child(note_node, "rest") is not None
        if is_chord_tone and pending is not None:
            if tech is not None:
                pending.notes.append(Note(tech[0], tech[1], 0))
            continue
        if pending is not None:
            events.append(pending)
            pending = None
        chord = Chord(note_type=note_type, dotted=dotted, grid=None, notes=[])
        if not is_rest and tech is not None:
            chord.notes.append(Note(tech[0], tech[1], 0))
        pending = chord
    if pending is not None:
        events.append(pending)
    bar.chords = events
    return bar


def _parse_piece(root: ET.Element) -> Piece:  # noqa: C901
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
    part = _child(root, "part")
    bars: list[Bar] = []
    strings = 6
    if part is not None:
        for measure in _children(part, "measure"):
            bars.append(_parse_measure(measure))
            if strings == 6:
                attrs = _child(measure, "attributes")
                if attrs is not None:
                    staff = _child(attrs, "staff-details")
                    if staff is not None:
                        lines = _text(_child(staff, "staff-lines"))
                        if lines.isdigit():
                            strings = max(1, int(lines))
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
