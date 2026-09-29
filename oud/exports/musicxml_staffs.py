"""Notation staffs of an imported score as MusicXML parts, beside the tablature part.

Writes pitch, rhythm (dots and tuplets), rests, ties and lyrics. FT3-only rows
(comments, layout, barline and control rows) and per-note ornaments are not
MusicXML content and stay in the FT3 source.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from itertools import pairwise
from xml.etree.ElementTree import Element, SubElement

from petrucci.core.model import Bar, ImportedBarContent, ImportedStaff, LyricEvent, MelodyEvent, Piece
from petrucci.core.music.time import parse_time_signature_value

NOTE_KIND = "note"
LYRICS_KIND = "lyrics"
MIDDLE_OCTAVE = 4  # a bare letter in Petrucci's pitch text is octave 4 (c = middle C)
_PITCH = re.compile(r"([A-Ga-g])([#b]?)([,']*)")
_ALTERS = {"#": 1, "b": -1}
_TYPES = {1: "whole", 2: "half", 4: "quarter", 8: "eighth", 16: "16th", 32: "32nd", 64: "64th", 128: "128th"}
_WHOLE_NOTE_TYPE = 2  # Chord/MelodyEvent note_type 2 is a whole note, each step halves it
_DEFAULT_NOTE_TYPE = 4
_DOT = Fraction(3, 2)

TimeWriter = Callable[[Element, Bar], None]


@dataclass(frozen=True)
class NotationPart:
    notes: ImportedStaff
    lyrics: ImportedStaff | None


def notation_parts(piece: Piece) -> list[NotationPart]:
    imported = piece.imported_score
    if imported is None:
        return []
    lyric_staffs = [staff for staff in imported.staffs if staff.kind == LYRICS_KIND]
    parts: list[NotationPart] = []
    for staff in imported.staffs:
        if staff.kind != NOTE_KIND or not any(bar.melody_events for bar in staff.bars):
            continue
        # Same pairing as the renderer: a lyric staff with the same label, or the only one.
        lyrics = next((item for item in lyric_staffs if item.label == staff.label), None)
        if lyrics is None and len(lyric_staffs) == 1:
            lyrics = lyric_staffs[0]
        parts.append(NotationPart(staff, lyrics))
    return parts


def append_notation_parts(
    root: Element,
    part_list: Element,
    piece: Piece,
    *,
    divisions: int,
    append_time: TimeWriter,
) -> int:
    """Append one part per notation staff; returns how many were written."""

    parts = notation_parts(piece)
    for number, notation in enumerate(parts, start=2):
        part_id = f"P{number}"
        score_part = SubElement(part_list, "score-part", id=part_id)
        SubElement(score_part, "part-name").text = notation.notes.label or f"Staff {number - 1}"
        part = SubElement(root, "part", id=part_id)
        _append_measures(part, piece, notation, divisions=divisions, append_time=append_time)
    return len(parts)


def _append_measures(
    part: Element,
    piece: Piece,
    notation: NotationPart,
    *,
    divisions: int,
    append_time: TimeWriter,
) -> None:
    notes = {content.source_bar_index: content for content in notation.notes.bars}
    lyrics = {content.source_bar_index: content for content in notation.lyrics.bars} if notation.lyrics else {}
    events = [(index, event) for index in range(len(piece.bars)) for event in _events(notes.get(index))]
    tie_starts = {id(event) for (_i, event), (_j, following) in pairwise(events) if following.tie_from_previous}
    for index, bar in enumerate(piece.bars):
        measure = SubElement(part, "measure", number=str(index + 1))
        if index == 0 or bar.time_sig:
            attributes = SubElement(measure, "attributes")
            if index == 0:
                SubElement(attributes, "divisions").text = str(divisions)
            append_time(attributes, bar)
            if index == 0:
                clef = SubElement(attributes, "clef")
                SubElement(clef, "sign").text = "G"
                SubElement(clef, "line").text = "2"
        bar_events = _events(notes.get(index))
        if not bar_events:
            _append_measure_rest(measure, bar, divisions)
            continue
        syllables = _syllables(lyrics.get(index))
        for event in bar_events:
            _append_note(measure, event, divisions, syllables.get(event.onset_index, []), id(event) in tie_starts)


def _events(content: ImportedBarContent | None) -> list[MelodyEvent]:
    return list(content.melody_events) if content is not None else []


def _syllables(content: ImportedBarContent | None) -> dict[int, list[tuple[int, LyricEvent]]]:
    syllables: dict[int, list[tuple[int, LyricEvent]]] = {}
    if content is None:
        return syllables
    for row_index, row in enumerate(content.lyric_event_rows):
        for event in row:
            syllables.setdefault(event.onset_index, []).append((row_index, event))
    return syllables


def _append_measure_rest(measure: Element, bar: Bar, divisions: int) -> None:
    beats = parse_time_signature_value(bar.time_sig or "")
    length = Fraction(beats[0], beats[1]) if beats else Fraction(1)
    note = SubElement(measure, "note")
    SubElement(note, "rest", measure="yes")
    SubElement(note, "duration").text = str(int(length * 4 * divisions))
    SubElement(note, "voice").text = "1"


def event_duration(event: MelodyEvent, divisions: int) -> int:
    value = Fraction(4 * divisions, _denominator(event))
    if event.dotted:
        value *= _DOT
    if event.tuplet_actual and event.tuplet_normal:
        value = value * event.tuplet_normal / event.tuplet_actual
    return max(1, round(value))


def _denominator(event: MelodyEvent) -> int:
    return 2 ** ((event.note_type or _DEFAULT_NOTE_TYPE) - _WHOLE_NOTE_TYPE)


def _append_note(
    measure: Element,
    event: MelodyEvent,
    divisions: int,
    syllables: list[tuple[int, LyricEvent]],
    tie_start: bool,
) -> None:
    note = SubElement(measure, "note")
    pitch = None if event.is_rest else _PITCH.fullmatch(event.text.strip())
    if pitch is None:
        SubElement(note, "rest")
    else:
        _append_pitch(note, pitch)
    SubElement(note, "duration").text = str(event_duration(event, divisions))
    ties = [kind for kind, present in (("stop", event.tie_from_previous), ("start", tie_start)) if present]
    for kind in ties:
        SubElement(note, "tie", type=kind)
    SubElement(note, "voice").text = "1"
    _append_rhythm(note, event)
    _append_notations(note, event, ties)
    for row_index, syllable in syllables:
        _append_lyric(note, row_index, syllable)


def _append_notations(note: Element, event: MelodyEvent, ties: list[str]) -> None:
    slurs = [kind for kind, present in (("start", event.slur_start), ("stop", event.slur_end)) if present]
    if not (ties or slurs or event.fermata):
        return
    notations = SubElement(note, "notations")
    for kind in ties:
        SubElement(notations, "tied", type=kind)
    for kind in slurs:
        SubElement(notations, "slur", type=kind, number="1")
    if event.fermata:
        SubElement(notations, "fermata")


def _append_rhythm(note: Element, event: MelodyEvent) -> None:
    note_type = _TYPES.get(_denominator(event))
    if note_type:
        SubElement(note, "type").text = note_type
    if event.dotted:
        SubElement(note, "dot")
    if event.tuplet_actual and event.tuplet_normal:
        modification = SubElement(note, "time-modification")
        SubElement(modification, "actual-notes").text = str(event.tuplet_actual)
        SubElement(modification, "normal-notes").text = str(event.tuplet_normal)


def _append_pitch(note: Element, match: re.Match[str]) -> None:
    letter, accidental, marks = match.groups()
    pitch = SubElement(note, "pitch")
    SubElement(pitch, "step").text = letter.upper()
    if accidental:
        SubElement(pitch, "alter").text = str(_ALTERS[accidental])
    SubElement(pitch, "octave").text = str(MIDDLE_OCTAVE + marks.count("'") - marks.count(","))


def _append_lyric(note: Element, row_index: int, syllable: LyricEvent) -> None:
    lyric = SubElement(note, "lyric", number=str(row_index + 1))
    if syllable.text:
        SubElement(lyric, "syllabic").text = syllable.syllabic
        SubElement(lyric, "text").text = syllable.text
    if syllable.extender:
        SubElement(lyric, "extend")
