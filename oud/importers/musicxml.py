from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from xml.etree import ElementTree as ET

from oud.importers.musicxml_staffs import read_notation_score
from petrucci.core.model import Bar, Chord, Note, Piece


@dataclass(frozen=True)
class _TimedTabNote:
    onset: int
    duration: int
    string: int
    fret: int
    written: tuple[int, bool] | None = None  # (note type, dotted) of a tuplet note, from its <type>


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

_TIME_SYMBOLS = {"common": "C", "cut": "C|"}
_FIRST_VOICE = ("", "1")
# Identification fields Oud writes for facts MusicXML has no element for.
_STYLE_FIELD = "oud-style"
_AUTHOR_FIELD = "oud-author"
_TUNING_FIELD = "oud-tuning"
_ALTER_SIGNS = {1: "+", -1: "-"}
OUD_SOFTWARE = "Oud"

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
    symbol = (time.get("symbol") or "").strip().lower()
    if symbol in _TIME_SYMBOLS:
        return _TIME_SYMBOLS[symbol]
    if symbol == "single-number" and beats.isdigit():
        return beats
    if beats.isdigit() and beat_type.isdigit():
        return f"{beats}/{beat_type}"
    return None


def _measure_repeat(measure: ET.Element) -> str | None:
    """`.:` for a forward repeat, `:.` for a backward one, `:|:` for both, as on one FT3 bar."""

    directions = {
        (repeat.get("direction") or "").strip().lower()
        for barline in _children(measure, "barline")
        if (repeat := _child(barline, "repeat")) is not None
    }
    start, end = "forward" in directions, "backward" in directions
    if start and end:
        return ":|:"
    return ".:" if start else ":." if end else None


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


@dataclass
class _Timeline:
    """Walks one measure's notes, backups and forwards in document order."""

    cursor: int = 0
    previous_onset: int = 0
    measure_end: int = 0
    notes: list[_TimedTabNote] = field(default_factory=list)
    rests: set[int] = field(default_factory=set)

    def read(self, node: ET.Element) -> None:
        tag = _local(node.tag)
        if tag == "backup":
            self.cursor = max(0, self.cursor - _duration_units(node))
        elif tag == "forward":
            self.cursor += _duration_units(node)
            self.measure_end = max(self.measure_end, self.cursor)
        elif tag == "note":
            self._note(node)

    def _note(self, node: ET.Element) -> None:
        if _child(node, "grace") is not None:
            return  # a grace note has no length of its own and must not join the chord at its onset
        duration = _duration_units(node)
        is_chord = _child(node, "chord") is not None
        onset = self.previous_onset if is_chord else self.cursor
        if not is_chord:
            self.previous_onset = onset
            self.cursor += duration
        self.measure_end = max(self.measure_end, onset + duration, self.cursor)
        if _child(node, "rest") is not None:
            # A rest in the main voice is an event of its own; other voices' rests only fill space.
            if _text(_child(node, "voice")) in _FIRST_VOICE:
                self.rests.add(onset)
            return
        technical = _technical(node)
        if technical is not None:
            written = _written_value(node) if _child(node, "time-modification") is not None else None
            self.notes.append(_TimedTabNote(onset, duration, technical[0], technical[1], written))


def _timed_notes(measure: ET.Element) -> tuple[list[_TimedTabNote], set[int], int]:
    timeline = _Timeline()
    for node in measure:
        timeline.read(node)
    return timeline.notes, timeline.rests, timeline.measure_end


def _written_value(node: ET.Element) -> tuple[int, bool] | None:
    """The value a note is written with (an eighth in a triplet), or ``None`` without a usable <type>."""

    if _text(_child(node, "type")).lower() not in _TYPE_TO_DENOM:
        return None
    return _note_type(node)


def _group_timed_notes(notes: list[_TimedTabNote], rests: set[int], measure_end: int, divisions: int) -> list[Chord]:
    grouped: dict[int, dict[tuple[int, int], _TimedTabNote]] = {onset: {} for onset in rests}
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
        written = next((note.written for note in timed if note.written is not None), None)
        note_type, dotted = written or _rhythm_for_duration(duration, divisions)
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


_BARLINE_STYLES = {"light-light": "||", "dotted": ":", "none": " ", "light-heavy": "|."}
_DYNAMICS = frozenset({"ppp", "pp", "p", "mp", "mf", "f", "ff", "fff", "sfz", "fz", "fp"})
# Words Oud writes for repeat jumps; they are not dynamics.
_REPEAT_WORDS = frozenset(
    {"D.C.", "D.S.", "Fine", "Coda", "To Coda", "D.C. al Fine", "D.C. al Coda", "D.S. al Fine", "D.S. al Coda"}
)


def _measure_barline(measure: ET.Element) -> str | None:
    """The closing barline style; a plain barline, and any barline with repeat dots, is ``None``."""

    for barline in _children(measure, "barline"):
        if (barline.get("location") or "right") != "right" or _child(barline, "repeat") is not None:
            continue
        return _BARLINE_STYLES.get(_text(_child(barline, "bar-style")))
    return None


def _measure_dynamic(measure: ET.Element) -> str | None:
    for direction in _children(measure, "direction"):
        direction_type = _child(direction, "direction-type")
        if direction_type is None:
            continue
        dynamics = _child(direction_type, "dynamics")
        if dynamics is not None:
            return next((_local(child.tag) for child in dynamics if _local(child.tag) in _DYNAMICS), None)
        words = _text(_child(direction_type, "words"))
        if words and words not in _REPEAT_WORDS:
            return words
    return None


def _measure_fermata(measure: ET.Element) -> bool:
    """Oud keeps one fermata per bar and writes it on the bar's first note."""

    first = next(iter(_children(measure, "note")), None)
    notations = _child(first, "notations") if first is not None else None
    return notations is not None and _child(notations, "fermata") is not None


def _parse_measure(measure: ET.Element, divisions: int) -> tuple[Bar, int]:
    bar = Bar()
    bar.time_sig = _measure_time(measure)
    bar.repeat = _measure_repeat(measure)
    bar.barline = _measure_barline(measure)
    bar.dynamic = _measure_dynamic(measure)
    bar.fermata = _measure_fermata(measure)
    notes, rests, measure_end = _timed_notes(measure)
    bar.chords = _group_timed_notes(notes, rests, measure_end, divisions)
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


def _measure_endings(measure: ET.Element) -> tuple[tuple[int, ...] | None, bool]:
    """Ending numbers of a volta that starts in this measure, and whether one stops here."""

    starts: tuple[int, ...] | None = None
    stops = False
    for barline in _children(measure, "barline"):
        for ending in _children(barline, "ending"):
            if ending.get("type") == "start":
                starts = tuple(int(number) for number in re.findall(r"\d+", ending.get("number") or ""))
            else:
                stops = True
    return starts, stops


def _parse_musicxml_part(part: ET.Element) -> tuple[list[Bar], int]:
    bars: list[Bar] = []
    strings = 6
    divisions = 1
    active: tuple[int, ...] = ()
    for measure in _children(part, "measure"):
        divisions = _measure_divisions(measure, divisions)
        bar, max_string = _parse_measure(measure, divisions)
        starts, stops = _measure_endings(measure)
        active = starts if starts is not None else active
        bar.ending_numbers = active
        active = () if stops else active
        bars.append(bar)
        strings = max(_staff_lines(measure, strings), max_string)
    return bars, strings


def written_by_oud(root: ET.Element) -> bool:
    identification = _child(root, "identification")
    encoding = _child(identification, "encoding") if identification is not None else None
    if encoding is None:
        return False
    return any(_text(software) == OUD_SOFTWARE for software in _children(encoding, "software"))


def _identification_fields(root: ET.Element) -> dict[str, str]:
    identification = _child(root, "identification")
    miscellaneous = _child(identification, "miscellaneous") if identification is not None else None
    if miscellaneous is None:
        return {}
    return {field.get("name", ""): _text(field) for field in _children(miscellaneous, "miscellaneous-field")}


def _first_staff_details(part: ET.Element) -> ET.Element | None:
    for measure in _children(part, "measure"):
        attributes = _child(measure, "attributes")
        details = _child(attributes, "staff-details") if attributes is not None else None
        if details is not None:
            return details
    return None


def _staff_tuning(details: ET.Element | None) -> str | None:
    """Scientific pitch, bass course first: staff line 1 is the lowest course."""

    if details is None:
        return None
    pitches: list[tuple[int, str]] = []
    for tuning in _children(details, "staff-tuning"):
        step = _text(_child(tuning, "tuning-step")).lower()
        octave = _text(_child(tuning, "tuning-octave"))
        line = (tuning.get("line") or "").strip()
        if not step or not octave.isdigit() or not line.isdigit():
            continue
        alter = _text(_child(tuning, "tuning-alter"))
        sign = _ALTER_SIGNS.get(int(alter), "") if alter.lstrip("-").isdigit() else ""
        pitches.append((int(line), f"{step}{sign}{octave}"))
    return "".join(pitch for _line, pitch in sorted(pitches)) or None


def _tempo(part: ET.Element) -> int | None:
    for sound in part.iter():
        if _local(sound.tag) != "sound":
            continue
        tempo = (sound.get("tempo") or "").strip()
        try:
            value = round(float(tempo))
        except ValueError:
            continue
        if value > 0:
            return value
    return None


def _tab_style(details: ET.Element | None, fields: dict[str, str]) -> str | None:
    if fields.get(_STYLE_FIELD):
        return fields[_STYLE_FIELD]
    if details is not None and (details.get("show-frets") or "").strip() == "letters":
        return "french"
    return None


INFORMATIONAL_WARNING_PREFIX = "MusicXML: "


def is_informational_warning(warning: str) -> bool:
    """Import warnings that report dropped content but leave a piece that can be used and converted."""

    return warning.startswith(INFORMATIONAL_WARNING_PREFIX)


def _sounding_notes(part: ET.Element) -> list[ET.Element]:
    return [
        note
        for note in part.iter()
        if _local(note.tag) == "note" and _child(note, "rest") is None and _child(note, "grace") is None
    ]


def _unread_note_count(root: ET.Element, tab_part: ET.Element) -> int:
    """Pitched notes that no string/fret describes: those of other parts and of untabbed staves."""

    count = 0
    for part in _children(root, "part"):
        notes = _sounding_notes(part)
        count += len(notes) if part is not tab_part else sum(_technical(note) is None for note in notes)
    return count


def _grace_note_count(part: ET.Element) -> int:
    return sum(
        1
        for note in part.iter()
        if _local(note.tag) == "note" and _child(note, "grace") is not None and _technical(note) is not None
    )


def _grace_notes_warning(count: int) -> str:
    noun, verb = ("grace note", "was") if count == 1 else ("grace notes", "were")
    return f"{INFORMATIONAL_WARNING_PREFIX}{count} {noun} {verb} not read"


def _tuplet_group_count(part: ET.Element) -> int:
    """Tuplet groups among the tablature notes: marked ones, else modified notes over the group size."""

    modified = [
        note
        for note in part.iter()
        if _local(note.tag) == "note" and _child(note, "time-modification") is not None and _technical(note)
    ]
    marked = sum(
        1
        for note in modified
        for tuplet in note.iter()
        if _local(tuplet.tag) == "tuplet" and tuplet.get("type") == "start"
    )
    if marked or not modified:
        return marked
    modification = _child(modified[0], "time-modification")
    actual = _text(_child(modification, "actual-notes")) if modification is not None else ""
    return max(1, len(modified) // int(actual)) if actual.isdigit() and int(actual) else 1


def _tuplet_warning(count: int) -> str:
    noun, verb = ("tuplet group", "was") if count == 1 else ("tuplet groups", "were")
    return f"{INFORMATIONAL_WARNING_PREFIX}{count} {noun} {verb} read without tuplet timing"


def _dropped_notes_warning(count: int) -> str:
    noun, verb = ("note", "was") if count == 1 else ("notes", "were")
    return f"{INFORMATIONAL_WARNING_PREFIX}{count} {noun} without tablature {verb} not read"


def _dropped_content_warnings(root: ET.Element, tab_part: ET.Element) -> list[str]:
    warnings = []
    if unread := _unread_note_count(root, tab_part):
        warnings.append(_dropped_notes_warning(unread))
    if graces := _grace_note_count(tab_part):
        warnings.append(_grace_notes_warning(graces))
    if tuplets := _tuplet_group_count(tab_part):
        warnings.append(_tuplet_warning(tuplets))
    return warnings


def _parse_piece(root: ET.Element) -> Piece:
    title, composer = _piece_metadata(root)
    part = max(_children(root, "part"), key=_technical_count, default=None)
    bars, strings = _parse_musicxml_part(part) if part is not None else ([], 6)
    piece = Piece(title=title, composer=composer, bars=bars, strings=strings)
    if part is None:
        return piece
    fields = _identification_fields(root)
    details = _first_staff_details(part)
    piece.author = fields.get(_AUTHOR_FIELD) or None
    # Oud always writes a staff tuning (MusicXML needs one); its own field says whether the piece had one.
    own_tuning = fields.get(_TUNING_FIELD) or None
    piece.tuning = own_tuning if written_by_oud(root) else own_tuning or _staff_tuning(details)
    piece.tempo = _tempo(part)
    piece.style = _tab_style(details, fields)
    if written_by_oud(root):
        # Oud writes an imported score's notation staffs as further parts.
        piece.imported_score = read_notation_score(root, part)
    else:
        piece.import_warnings.extend(_dropped_content_warnings(root, part))
    return piece


def musicxml_file_written_by_oud(path: str) -> bool:
    """Whether an uncompressed MusicXML file carries Oud's software mark; unreadable files do not."""

    if not path.lower().endswith((".musicxml", ".xml")):
        return False
    try:
        root = ET.fromstring(Path(path).read_text(encoding="utf-8"))  # noqa: S314
    except (OSError, ET.ParseError, UnicodeDecodeError):
        return False
    return written_by_oud(root)


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
