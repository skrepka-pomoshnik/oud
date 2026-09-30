from __future__ import annotations

import zipfile
from collections.abc import Sequence
from fractions import Fraction
from itertools import pairwise
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

from oud.exports.musicxml_staffs import append_measure_rest, append_notation_parts
from petrucci.core.model import Bar, Chord, Note, Piece
from petrucci.core.music.time import parse_time_signature_value
from petrucci.core.music.tuning import default_tuning_pitches
from petrucci.core.music.tuning import parse_tuning_pitches as _parse_tuning
from petrucci.input.tablature.input import editor_event_columns, editor_fret_at

MUSICXML_DOCTYPE = (
    '<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 3.1 Partwise//EN" '
    '"http://www.musicxml.org/dtds/partwise.dtd">'
)

DIVISIONS = 480
SOFTWARE = "Oud"
# Oud-only facts MusicXML has no element for, kept as identification fields.
STYLE_FIELD = "oud-style"
AUTHOR_FIELD = "oud-author"
TUNING_FIELD = "oud-tuning"
_CUT_TIME = (2, 2)
_SINGLE_NUMBER_BEAT_TYPE = 4


def _default_tuning(strings: int) -> list[int]:
    return default_tuning_pitches(strings)


def _note_type_to_denom(note_type: int) -> int:
    mapping = {
        2: 1,
        3: 2,
        4: 4,
        5: 8,
        6: 16,
        7: 32,
        8: 64,
        9: 128,
        10: 256,
    }
    return mapping.get(note_type, 4)


def _duration_units(denom: int, dotted: bool) -> int:
    units = max(1, (DIVISIONS * 4) // max(1, denom))
    return (units * 3) // 2 if dotted else units


def _duration_type(denom: int) -> str:
    mapping = {
        1: "whole",
        2: "half",
        4: "quarter",
        8: "eighth",
        16: "16th",
        32: "32nd",
        64: "64th",
        128: "128th",
        256: "256th",
    }
    return mapping.get(denom, "quarter")


def _midi_to_pitch(midi: int) -> tuple[str, int, int]:
    pitch_map = {
        0: ("C", 0),
        1: ("C", 1),
        2: ("D", 0),
        3: ("D", 1),
        4: ("E", 0),
        5: ("F", 0),
        6: ("F", 1),
        7: ("G", 0),
        8: ("G", 1),
        9: ("A", 0),
        10: ("A", 1),
        11: ("B", 0),
    }
    step, alter = pitch_map[midi % 12]
    octave = (midi // 12) - 1
    return step, alter, octave


def _time_for_bar(bar: Bar, settings: dict[str, str]) -> tuple[int, int]:
    if bar.time_sig:
        parsed = parse_time_signature_value(bar.time_sig)
        if parsed is not None:
            return parsed
    parsed = parse_time_signature_value(settings.get("time", ""))
    if parsed is not None:
        return parsed
    return 4, 4


def _raw_time_sig_for_bar(bar: Bar, settings: dict[str, str]) -> str:
    return (bar.time_sig or settings.get("time", "") or "").strip()


def _time_symbol_attr(raw_time: str) -> str | None:
    text = raw_time.strip().upper()
    if text == "C":
        return "common"
    if text in {"C|", "C/"}:
        return "cut"
    if text.isdigit():
        return "single-number"
    return None


def _append_time(attributes: Element, bar: Bar, settings: dict[str, str]) -> None:
    raw = _raw_time_sig_for_bar(bar, settings)
    symbol = _time_symbol_attr(raw)
    beats, beat_type = _time_for_bar(bar, settings)
    if symbol == "cut":
        beats, beat_type = _CUT_TIME
    elif symbol == "single-number":
        beats, beat_type = int(raw.strip()), _SINGLE_NUMBER_BEAT_TYPE
    time = SubElement(attributes, "time")
    if symbol:
        time.set("symbol", symbol)
    SubElement(time, "beats").text = str(beats)
    SubElement(time, "beat-type").text = str(beat_type)


def _append_tempo(measure: Element, tempo: int) -> None:
    direction = SubElement(measure, "direction", placement="above")
    metronome = SubElement(SubElement(direction, "direction-type"), "metronome")
    SubElement(metronome, "beat-unit").text = "quarter"
    SubElement(metronome, "per-minute").text = str(tempo)
    SubElement(direction, "sound", tempo=str(tempo))


def _append_identification(root: Element, piece: Piece, style: str, tuning: str) -> None:
    identification = SubElement(root, "identification")
    if piece.composer:
        creator = SubElement(identification, "creator", type="composer")
        creator.text = piece.composer
    encoding = SubElement(identification, "encoding")
    SubElement(encoding, "software").text = SOFTWARE
    fields = ((STYLE_FIELD, style), (AUTHOR_FIELD, piece.author), (TUNING_FIELD, tuning))
    if not any(value for _name, value in fields):
        return
    miscellaneous = SubElement(identification, "miscellaneous")
    for name, value in fields:
        if value:
            SubElement(miscellaneous, "miscellaneous-field", name=name).text = value


def _key_name(value: str) -> str:
    text = value.strip()
    if not text:
        return "C"
    if ":" in text:
        text = text.split(":", 1)[-1]
    if len(text) > 1 and text[1] in ("#", "b"):
        return text[0].upper() + text[1]
    return text[0].upper()


def _key_fifths(value: str) -> int:
    mapping = {
        "C": 0,
        "G": 1,
        "D": 2,
        "A": 3,
        "E": 4,
        "B": 5,
        "F#": 6,
        "C#": 7,
        "F": -1,
        "Bb": -2,
        "Eb": -3,
        "Ab": -4,
        "Db": -5,
        "Gb": -6,
        "Cb": -7,
    }
    return mapping.get(_key_name(value), 0)


def _events_from_overrides(
    bar_index: int,
    strings: int,
    *,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    style: str,
    dotted: set[tuple[int, int]] | None,
) -> list[tuple[int, bool, list[tuple[int, int]]]]:
    cols = editor_event_columns(overrides, bar_index=bar_index)
    events: list[tuple[int, bool, list[tuple[int, int]]]] = []
    for col in cols:
        notes: list[tuple[int, int]] = []
        for s_idx in range(strings):
            key = (bar_index, s_idx, col)
            fret = editor_fret_at(
                overrides,
                durations,
                bar_index=bar_index,
                string_index=s_idx,
                column=col,
                style=style,
            )
            if fret is None:
                continue
            notes.append((s_idx + 1, fret))
        if not notes:
            continue
        denom = 4
        for s_idx in range(strings):
            key = (bar_index, s_idx, col)
            if key in durations:
                denom = durations[key]
                break
        is_dotted = dotted is not None and (bar_index, col) in dotted
        events.append((denom, is_dotted, notes))
    return events


def _events_for_bar(
    bar: Bar,
    bar_index: int,
    strings: int,
    *,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    style: str,
    dotted: set[tuple[int, int]] | None,
) -> list[tuple[int, bool, list[tuple[int, int]]]]:
    if bar.chords:
        events: list[tuple[int, bool, list[tuple[int, int]]]] = []
        for chord in bar.chords:
            notes = [(note.string, note.fret) for note in chord.notes]
            events.append((_note_type_to_denom(chord.note_type), bool(chord.dotted), notes))
        return events
    return _events_from_overrides(
        bar_index,
        strings,
        overrides=overrides,
        durations=durations,
        style=style,
        dotted=dotted,
    )


def _append_rest_note(
    xml_note: Element,
    *,
    duration_units: int,
    duration_type: str,
    dotted: bool,
    fermata: bool,
) -> None:
    SubElement(xml_note, "rest")
    SubElement(xml_note, "duration").text = str(duration_units)
    SubElement(xml_note, "type").text = duration_type
    if dotted:
        SubElement(xml_note, "dot")
    if fermata:
        notations = SubElement(xml_note, "notations")
        SubElement(notations, "fermata").text = "normal"


_TIE_ENDS: dict[str | None, tuple[str, ...]] = {"start": ("start",), "stop": ("stop",), "continue": ("stop", "start")}
_TECHNICAL_TECHNIQUES = ("hammer-on", "pull-off")
_ARPEGGIATED = frozenset({"single", "top"})
_PLAIN_FINGERINGS = frozenset({"dot1", "dot2", "dot3"})


def technique_stops(chords: Sequence[Chord]) -> dict[int, str]:
    """Where each technique ends: the next chord's note on the same string, keyed by ``id(note)``."""

    stops: dict[int, str] = {}
    for chord, following in pairwise(chords):
        for note in chord.notes:
            if note.technique is None:
                continue
            target = next((other for other in following.notes if other.string == note.string), None)
            if target is not None:
                stops[id(target)] = note.technique
    return stops


def _append_notations_marks(notations: Element, note_model: object | None, technique_stop: str | None) -> None:
    for end in _TIE_ENDS.get(getattr(note_model, "tie", None), ()):
        SubElement(notations, "tied").set("type", end)
    if getattr(note_model, "technique", None) == "slide":
        SubElement(notations, "slide").set("type", "start")
    if technique_stop == "slide":
        SubElement(notations, "slide").set("type", "stop")


def _append_technical_marks(technical: Element, note_model: object, technique_stop: str | None) -> None:
    for name, kind in ((getattr(note_model, "technique", None), "start"), (technique_stop, "stop")):
        if name in _TECHNICAL_TECHNIQUES:
            SubElement(technical, name).set("type", kind)
    if getattr(note_model, "harmonic", False):
        SubElement(technical, "harmonic")
    bend = getattr(note_model, "bend", None)
    if bend is not None:
        SubElement(SubElement(technical, "bend"), "bend-alter").text = f"{bend:g}"
    left_f = getattr(note_model, "left_fingering", None)
    if left_f:
        SubElement(technical, "fingering").text = str(left_f)
    right_f = getattr(note_model, "right_fingering", None)
    if right_f and right_f not in _PLAIN_FINGERINGS:
        SubElement(technical, "pluck").text = "p" if right_f == "thumb" else str(right_f)


def _append_note_technical(
    xml_note: Element,
    *,
    string: int,
    fret: int,
    note_model: object | None,
    fermata: bool,
    technique_stop: str | None = None,
) -> None:
    notations = SubElement(xml_note, "notations")
    _append_notations_marks(notations, note_model, technique_stop)
    if fermata:
        SubElement(notations, "fermata").text = "normal"
    technical = SubElement(notations, "technical")
    SubElement(technical, "string").text = str(string)
    SubElement(technical, "fret").text = str(max(0, fret))
    if note_model is None:
        return
    _append_technical_marks(technical, note_model, technique_stop)
    if getattr(note_model, "arpeggio", None) in _ARPEGGIATED:
        SubElement(notations, "arpeggiate")


def _add_note(
    measure: Element,
    note: tuple[int, int],
    *,
    duration_units: int,
    duration_type: str,
    dotted: bool,
    pitch_for_string: list[int],
    chord: bool,
    note_model: object | None = None,
    fermata: bool = False,
    technique_stop: str | None = None,
) -> None:
    string, fret = note
    xml_note = SubElement(measure, "note")
    if chord:
        SubElement(xml_note, "chord")
    if not (1 <= string <= len(pitch_for_string)):
        _append_rest_note(
            xml_note,
            duration_units=duration_units,
            duration_type=duration_type,
            dotted=dotted,
            fermata=fermata,
        )
        return
    pitch_value = pitch_for_string[string - 1] + max(0, fret)
    step, alter, octave = _midi_to_pitch(pitch_value)
    pitch = SubElement(xml_note, "pitch")
    SubElement(pitch, "step").text = step
    if alter:
        SubElement(pitch, "alter").text = str(alter)
    SubElement(pitch, "octave").text = str(octave)
    SubElement(xml_note, "duration").text = str(duration_units)
    for end in _TIE_ENDS.get(getattr(note_model, "tie", None), ()):
        SubElement(xml_note, "tie").set("type", end)
    SubElement(xml_note, "type").text = duration_type
    if dotted:
        SubElement(xml_note, "dot")
    _append_note_technical(
        xml_note,
        string=string,
        fret=fret,
        note_model=note_model,
        fermata=fermata,
        technique_stop=technique_stop,
    )


def _ending_text(numbers: tuple[int, ...]) -> str:
    return ", ".join(str(number) for number in numbers)


def _ending_start(bars: list[Bar], index: int) -> str | None:
    """Ending numbers when bar ``index`` opens a volta (a run of bars with the same ending numbers)."""

    numbers = bars[index].ending_numbers
    if not numbers or (index > 0 and bars[index - 1].ending_numbers == numbers):
        return None
    return _ending_text(numbers)


def _ending_stop(bars: list[Bar], index: int) -> str | None:
    numbers = bars[index].ending_numbers
    if not numbers or (index + 1 < len(bars) and bars[index + 1].ending_numbers == numbers):
        return None
    return _ending_text(numbers)


def _add_barline(
    measure: Element,
    *,
    location: str,
    style: str | None,
    repeat: str | None = None,
    ending: tuple[str, str] | None = None,
) -> None:
    barline = SubElement(measure, "barline")
    barline.set("location", location)
    if style is not None:
        SubElement(barline, "bar-style").text = style
    if ending is not None:
        ending_node = SubElement(barline, "ending")
        ending_node.set("number", ending[0])
        ending_node.set("type", ending[1])
    if repeat is not None:
        repeat_node = SubElement(barline, "repeat")
        repeat_node.set("direction", repeat)


def _barline_style(value: str | None) -> str:
    mapping = {
        "|": "regular",
        "||": "light-light",
        "|.": "light-heavy",
        ":": "dotted",
        " ": "none",
    }
    key = "|" if value is None else (value.strip() or value)  # a blank barline (" ") is `none`
    return mapping.get(key, "regular")


def _append_first_measure_attributes(
    measure: Element,
    piece: Piece,
    settings: dict[str, str],
    bar: Bar,
    pitch_for_string: list[int],
) -> None:
    attributes = SubElement(measure, "attributes")
    SubElement(attributes, "divisions").text = str(DIVISIONS)
    key = SubElement(attributes, "key")
    SubElement(key, "fifths").text = str(_key_fifths(settings.get("key") or piece.key or "C"))
    _append_time(attributes, bar, settings)
    clef = SubElement(attributes, "clef")
    SubElement(clef, "sign").text = "TAB"
    SubElement(clef, "line").text = "5"
    staff_details = SubElement(attributes, "staff-details")
    SubElement(staff_details, "staff-lines").text = str(max(1, piece.strings))
    style = settings.get("style") or piece.style or "french"
    if style == "french":
        staff_details.set("show-frets", "letters")
    for idx, pitch_value in enumerate(pitch_for_string, start=1):
        staff_tuning = SubElement(staff_details, "staff-tuning")
        staff_tuning.set("line", str(max(1, piece.strings - (idx - 1))))
        step, alter, octave = _midi_to_pitch(pitch_value)
        SubElement(staff_tuning, "tuning-step").text = step
        if alter:
            SubElement(staff_tuning, "tuning-alter").text = str(alter)
        SubElement(staff_tuning, "tuning-octave").text = str(octave)


def _append_time_change(measure: Element, bar: Bar, settings: dict[str, str]) -> None:
    if not bar.time_sig:
        return
    _append_time(SubElement(measure, "attributes"), bar, settings)


def _repeat_words(repeat: str) -> str | None:
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
    return mapping.get(repeat.strip())


def _add_direction_words(measure: Element, words: str) -> None:
    direction = SubElement(measure, "direction")
    direction_type = SubElement(direction, "direction-type")
    SubElement(direction_type, "words").text = words


def _add_direction_symbol(measure: Element, symbol: str) -> None:
    direction = SubElement(measure, "direction")
    direction_type = SubElement(direction, "direction-type")
    SubElement(direction_type, symbol)


def _add_repeat_directions(measure: Element, repeat: str) -> None:
    text = repeat.strip()
    if not text:
        return
    upper = text.upper()
    if upper.startswith("DS"):
        _add_direction_symbol(measure, "segno")
    if "CODA" in upper:
        _add_direction_symbol(measure, "coda")


def _add_direction_dynamic(measure: Element, dynamic: str) -> None:
    value = (dynamic or "").strip().lower()
    if not value:
        return
    direction = SubElement(measure, "direction")
    direction_type = SubElement(direction, "direction-type")
    known = {
        "ppp",
        "pp",
        "p",
        "mp",
        "mf",
        "f",
        "ff",
        "fff",
        "sfz",
        "fz",
        "fp",
    }
    if value in known:
        dynamics = SubElement(direction_type, "dynamics")
        SubElement(dynamics, value)
        return
    SubElement(direction_type, "words").text = dynamic


def export_musicxml(
    path: str,
    piece: Piece,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    bar_width: int,
    *,
    settings: dict[str, str] | None = None,
    dotted: set[tuple[int, int]] | None = None,
) -> str:
    content = musicxml_text(
        piece,
        overrides,
        durations,
        bar_width,
        settings=settings,
        dotted=dotted,
    )
    Path(path).write_text(content, encoding="utf-8")
    return f"Wrote {path}"


def export_mxl(
    path: str,
    piece: Piece,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    bar_width: int,
    *,
    settings: dict[str, str] | None = None,
    dotted: set[tuple[int, int]] | None = None,
) -> str:
    output = Path(path)
    inner_name = output.with_suffix(".xml").name
    xml_text = musicxml_text(
        piece,
        overrides,
        durations,
        bar_width,
        settings=settings,
        dotted=dotted,
    )
    container_xml = "".join(
        (
            '<?xml version="1.0" encoding="UTF-8"?>\n',
            ('<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'),
            "  <rootfiles>\n",
            (f'    <rootfile full-path="{inner_name}" media-type="application/vnd.recordare.musicxml+xml"/>\n'),
            "  </rootfiles>\n",
            "</container>\n",
        ),
    )
    with zipfile.ZipFile(output, "w") as zf:
        zf.writestr(
            "mimetype",
            "application/vnd.recordare.musicxml",
            compress_type=zipfile.ZIP_STORED,
        )
        zf.writestr("META-INF/container.xml", container_xml)
        zf.writestr(inner_name, xml_text)
    return f"Wrote {path}"


def _musicxml_pitch_context(piece: Piece, settings: dict[str, str]) -> tuple[list[int], str]:
    tuning_text = piece.tuning or settings.get("tuning", "")
    pitch_for_string = _parse_tuning(tuning_text) if tuning_text else _default_tuning(piece.strings)
    defaults = _default_tuning(piece.strings)
    if len(pitch_for_string) < piece.strings:
        pitch_for_string.extend(defaults[len(pitch_for_string) : piece.strings])
    pitch_for_string = pitch_for_string[: piece.strings]
    style = settings.get("style") or piece.style or "french"
    return pitch_for_string, style


def _append_musicxml_note_group(
    measure: Element,
    notes: list[tuple[int, int]],
    *,
    duration_units: int,
    duration_type: str,
    dotted: bool,
    pitch_for_string: list[int],
    fermata: bool,
    note_models: Sequence[Note] | None = None,
    stops: dict[int, str] | None = None,
) -> None:
    if not notes:
        _add_note(
            measure,
            (0, 0),
            duration_units=duration_units,
            duration_type=duration_type,
            dotted=dotted,
            pitch_for_string=pitch_for_string,
            chord=False,
            fermata=fermata,
        )
        return
    for index, note in enumerate(notes):
        _add_note(
            measure,
            note,
            duration_units=duration_units,
            duration_type=duration_type,
            dotted=dotted,
            pitch_for_string=pitch_for_string,
            chord=index > 0,
            note_model=note_models[index] if note_models else None,
            fermata=fermata and index == 0,
            technique_stop=(stops or {}).get(id(note_models[index])) if note_models else None,
        )


def _append_musicxml_chord_notes(
    measure: Element,
    bar: Bar,
    *,
    pitch_for_string: list[int],
    fermata_pending: bool,
    next_bar: Bar | None = None,
) -> None:
    remaining_fermata = fermata_pending
    stops = technique_stops([*bar.chords, *(next_bar.chords[:1] if next_bar is not None else [])])
    for chord in bar.chords:
        denom = _note_type_to_denom(chord.note_type)
        _append_musicxml_note_group(
            measure,
            [(note.string, note.fret) for note in chord.notes],
            duration_units=_duration_units(denom, bool(chord.dotted)),
            duration_type=_duration_type(denom),
            dotted=bool(chord.dotted),
            pitch_for_string=pitch_for_string,
            fermata=remaining_fermata,
            note_models=chord.notes,
            stops=stops,
        )
        remaining_fermata = False


def _append_musicxml_override_notes(
    measure: Element,
    bar: Bar,
    bar_index: int,
    piece: Piece,
    *,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    style: str,
    dotted: set[tuple[int, int]] | None,
    pitch_for_string: list[int],
    fermata_pending: bool,
) -> None:
    remaining_fermata = fermata_pending
    for denom, is_dotted, notes in _events_for_bar(
        bar,
        bar_index,
        piece.strings,
        overrides=overrides,
        durations=durations,
        style=style,
        dotted=dotted,
    ):
        _append_musicxml_note_group(
            measure,
            notes,
            duration_units=_duration_units(denom, is_dotted),
            duration_type=_duration_type(denom),
            dotted=is_dotted,
            pitch_for_string=pitch_for_string,
            fermata=remaining_fermata,
        )
        remaining_fermata = False


def _effective_meter(piece: Piece, bar_index: int, settings: dict[str, str]) -> Fraction:
    """The meter in force in a bar: its own, else the latest earlier one, else the setting."""

    for bar in reversed(piece.bars[: bar_index + 1]):
        if bar.time_sig:
            beats, unit = _time_for_bar(bar, settings)
            return Fraction(beats, unit)
    beats, unit = _time_for_bar(piece.bars[bar_index], settings)
    return Fraction(beats, unit)


def _append_musicxml_measure_notes(
    measure: Element,
    bar: Bar,
    bar_index: int,
    piece: Piece,
    *,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    style: str,
    dotted: set[tuple[int, int]] | None,
    pitch_for_string: list[int],
    settings: dict[str, str],
) -> None:
    if bar.chords:
        _append_musicxml_chord_notes(
            measure,
            bar,
            pitch_for_string=pitch_for_string,
            fermata_pending=bool(bar.fermata),
            next_bar=piece.bars[bar_index + 1] if bar_index + 1 < len(piece.bars) else None,
        )
        return
    _append_musicxml_override_notes(
        measure,
        bar,
        bar_index,
        piece,
        overrides=overrides,
        durations=durations,
        style=style,
        dotted=dotted,
        pitch_for_string=pitch_for_string,
        fermata_pending=bool(bar.fermata),
    )
    if measure.find("note") is None:
        # An empty bar needs a measure rest, or other programs show nothing.
        append_measure_rest(measure, _effective_meter(piece, bar_index, settings), DIVISIONS)


def _append_musicxml_measure_prefix(
    part: Element,
    piece: Piece,
    bar: Bar,
    bar_number: int,
    *,
    settings: dict[str, str],
    pitch_for_string: list[int],
) -> tuple[Element, str]:
    measure = SubElement(part, "measure", number=str(bar_number))
    repeat = (bar.repeat or "").strip()
    # `.:` and `:|:` put the repeat dots at the left barline of this bar (as FT3 and the renderer do).
    forward = repeat in (".:", ":|:")
    ending_start = _ending_start(piece.bars, bar_number - 1)
    if forward or ending_start:
        _add_barline(
            measure,
            location="left",
            style="heavy-light" if forward else None,
            repeat="forward" if forward else None,
            ending=(ending_start, "start") if ending_start else None,
        )
    if repeat:
        _add_repeat_directions(measure, repeat)
    repeat_words = _repeat_words(repeat)
    if repeat_words:
        _add_direction_words(measure, repeat_words)
    if bar.dynamic:
        _add_direction_dynamic(measure, bar.dynamic)
    if bar_number == 1:
        _append_first_measure_attributes(
            measure,
            piece,
            settings,
            bar,
            pitch_for_string,
        )
        tempo = piece.tempo or settings.get("tempo", "")
        if str(tempo).isdigit() and int(tempo) > 0:
            _append_tempo(measure, int(tempo))
    else:
        _append_time_change(measure, bar, settings)
    return measure, repeat


def _finish_musicxml_measure(measure: Element, bar: Bar, repeat: str, ending_stop: str | None) -> None:
    right_repeat = "backward" if repeat in (":.", ":|:") else None
    bar_style = "light-heavy" if right_repeat else _barline_style(bar.barline)
    if repeat or bar.barline:
        _add_barline(
            measure,
            location="right",
            style=bar_style,
            repeat=right_repeat,
            ending=(ending_stop, "stop") if ending_stop else None,
        )
    elif ending_stop:
        _add_barline(measure, location="right", style=None, ending=(ending_stop, "stop"))


def _append_musicxml_measure(
    part: Element,
    piece: Piece,
    bar: Bar,
    bar_index: int,
    *,
    settings: dict[str, str],
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    style: str,
    dotted: set[tuple[int, int]] | None,
    pitch_for_string: list[int],
) -> None:
    measure, repeat = _append_musicxml_measure_prefix(
        part,
        piece,
        bar,
        bar_index + 1,
        settings=settings,
        pitch_for_string=pitch_for_string,
    )
    _append_musicxml_measure_notes(
        measure,
        bar,
        bar_index,
        piece,
        overrides=overrides,
        durations=durations,
        style=style,
        dotted=dotted,
        pitch_for_string=pitch_for_string,
        settings=settings,
    )
    _finish_musicxml_measure(measure, bar, repeat, _ending_stop(piece.bars, bar_index))


def _musicxml_text(
    piece: Piece,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    bar_width: int,
    settings: dict[str, str] | None = None,
    *,
    dotted: set[tuple[int, int]] | None = None,
) -> str:
    _ = bar_width
    settings_map = settings or {}
    pitch_for_string, style = _musicxml_pitch_context(piece, settings_map)
    title = piece.title or "Untitled"

    root = Element("score-partwise", version="3.1")
    work = SubElement(root, "work")
    SubElement(work, "work-title").text = title
    _append_identification(root, piece, style, piece.tuning or settings_map.get("tuning", ""))
    part_list = SubElement(root, "part-list")
    score_part = SubElement(part_list, "score-part", id="P1")
    SubElement(score_part, "part-name").text = "Lute"
    part = SubElement(root, "part", id="P1")

    for bar_index, bar in enumerate(piece.bars):
        _append_musicxml_measure(
            part,
            piece,
            bar,
            bar_index,
            settings=settings_map,
            overrides=overrides,
            durations=durations,
            style=style,
            dotted=dotted,
            pitch_for_string=pitch_for_string,
        )

    append_notation_parts(
        root,
        part_list,
        piece,
        divisions=DIVISIONS,
        append_time=lambda attributes, bar: _append_time(attributes, bar, settings_map),
    )
    xml_bytes = tostring(root, encoding="utf-8")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + MUSICXML_DOCTYPE + "\n" + xml_bytes.decode("utf-8") + "\n"


def musicxml_text(
    piece: Piece,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    bar_width: int,
    settings: dict[str, str] | None = None,
    *,
    dotted: set[tuple[int, int]] | None = None,
) -> str:
    """Render one score as uncompressed MusicXML text."""

    return _musicxml_text(
        piece,
        overrides,
        durations,
        bar_width,
        settings,
        dotted=dotted,
    )


__all__ = ["export_musicxml", "export_mxl", "musicxml_text"]
