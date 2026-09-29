"""Notation parts of MusicXML that Oud wrote, read back as an imported score's staffs.

Mirrors `oud.exports.musicxml_staffs`: pitch, rhythm (dots and tuplets), rests,
ties and lyrics of the first voice. Foreign MusicXML keeps only its tablature
part, as before.
"""

from __future__ import annotations

from xml.etree import ElementTree as ET

from petrucci.core.model import ImportedBarContent, ImportedScore, ImportedStaff, LyricEvent, MelodyEvent

NOTE_KIND = "note"
LYRICS_KIND = "lyrics"
SOURCE_FORMAT = "musicxml"
MIDDLE_OCTAVE = 4
_TYPE_TO_NOTE_TYPE = {
    "whole": 2,
    "half": 3,
    "quarter": 4,
    "eighth": 5,
    "16th": 6,
    "32nd": 7,
    "64th": 8,
    "128th": 9,
}
_ACCIDENTALS = {1: "#", -1: "b"}
_FIRST_VOICE = ("", "1")


def _local(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _child(node: ET.Element, name: str) -> ET.Element | None:
    return next((child for child in node if _local(child.tag) == name), None)


def _children(node: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in node if _local(child.tag) == name]


def _text(node: ET.Element | None) -> str:
    return (node.text or "").strip() if node is not None else ""


def read_notation_score(root: ET.Element, tab_part: ET.Element | None) -> ImportedScore | None:
    names = {
        score_part.get("id", ""): _text(_child(score_part, "part-name"))
        for part_list in _children(root, "part-list")
        for score_part in _children(part_list, "score-part")
    }
    staffs: list[ImportedStaff] = []
    for part in _children(root, "part"):
        if part is tab_part:
            continue
        label = names.get(part.get("id", "")) or None
        notes, lyrics = _read_part(part, label)
        staffs.append(notes)
        if any(content.lyric_event_rows for content in lyrics.bars):
            staffs.append(lyrics)
    return ImportedScore(SOURCE_FORMAT, staffs) if staffs else None


def _read_part(part: ET.Element, label: str | None) -> tuple[ImportedStaff, ImportedStaff]:
    notes = ImportedStaff(kind=NOTE_KIND, label=label)
    lyrics = ImportedStaff(kind=LYRICS_KIND, label=label)
    for index, measure in enumerate(_children(part, "measure")):
        events: list[MelodyEvent] = []
        rows: list[list[LyricEvent]] = []
        for node in _children(measure, "note"):
            if not _is_main_event(node):
                continue
            onset = len(events)
            events.append(_melody_event(node, onset))
            _collect_lyrics(node, onset, rows)
        if events:
            notes.bars.append(ImportedBarContent(index, melody_events=events))
        if rows:
            lyrics.bars.append(ImportedBarContent(index, lyric_event_rows=rows))
    return notes, lyrics


def _is_main_event(node: ET.Element) -> bool:
    rest = _child(node, "rest")
    if rest is not None and rest.get("measure") == "yes":
        return False
    return _child(node, "chord") is None and _text(_child(node, "voice")) in _FIRST_VOICE


def _melody_event(node: ET.Element, onset: int) -> MelodyEvent:
    modification = _child(node, "time-modification")
    actual = _text(_child(modification, "actual-notes")) if modification is not None else ""
    normal = _text(_child(modification, "normal-notes")) if modification is not None else ""
    is_rest = _child(node, "rest") is not None
    notations = _child(node, "notations")
    slurs = {slur.get("type") for slur in _children(notations, "slur")} if notations is not None else set()
    return MelodyEvent(
        text="r" if is_rest else _pitch_text(_child(node, "pitch")),
        onset_index=onset,
        note_type=_TYPE_TO_NOTE_TYPE.get(_text(_child(node, "type"))),
        dotted=_child(node, "dot") is not None,
        is_rest=is_rest,
        tie_from_previous=any(tie.get("type") == "stop" for tie in _children(node, "tie")),
        tuplet_actual=int(actual) if actual.isdigit() else None,
        tuplet_normal=int(normal) if normal.isdigit() else None,
        fermata=notations is not None and _child(notations, "fermata") is not None,
        slur_start="start" in slurs,
        slur_end="stop" in slurs,
    )


def _pitch_text(pitch: ET.Element | None) -> str:
    """Petrucci's pitch text: `c` is middle C, `'` raises and `,` lowers an octave."""

    if pitch is None:
        return "r"
    step = _text(_child(pitch, "step")).lower() or "c"
    alter = _text(_child(pitch, "alter"))
    accidental = _ACCIDENTALS.get(int(alter), "") if alter.lstrip("-").isdigit() else ""
    octave_text = _text(_child(pitch, "octave"))
    octave = int(octave_text) if octave_text.isdigit() else MIDDLE_OCTAVE
    marks = "'" * (octave - MIDDLE_OCTAVE) if octave >= MIDDLE_OCTAVE else "," * (MIDDLE_OCTAVE - octave)
    return f"{step}{accidental}{marks}"


def _collect_lyrics(node: ET.Element, onset: int, rows: list[list[LyricEvent]]) -> None:
    for lyric in _children(node, "lyric"):
        number = lyric.get("number", "1")
        row = int(number) - 1 if number.isdigit() and int(number) > 0 else 0
        while len(rows) <= row:
            rows.append([])
        rows[row].append(
            LyricEvent(
                text=_text(_child(lyric, "text")),
                onset_index=onset,
                verse=row,
                syllabic=_text(_child(lyric, "syllabic")) or "single",
                extender=_child(lyric, "extend") is not None,
            )
        )
