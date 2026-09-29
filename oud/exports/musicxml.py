from __future__ import annotations

import zipfile
from collections.abc import Sequence
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

from oud.exports.musicxml_staffs import append_notation_parts
from petrucci.core.model import Bar, Piece
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


def _append_note_technical(
    xml_note: Element,
    *,
    string: int,
    fret: int,
    note_model: object | None,
    fermata: bool,
) -> None:
    notations = SubElement(xml_note, "notations")
    if fermata:
        SubElement(notations, "fermata").text = "normal"
    technical = SubElement(notations, "technical")
    SubElement(technical, "string").text = str(string)
    SubElement(technical, "fret").text = str(max(0, fret))
    if note_model is None:
        return
    left_f = getattr(note_model, "left_fingering", None)
    if left_f:
        SubElement(technical, "fingering").text = str(left_f)
    right_f = getattr(note_model, "right_fingering", None)
    if right_f and right_f not in {"dot1", "dot2", "dot3"}:
        pluck = "p" if right_f == "thumb" else str(right_f)
        SubElement(technical, "pluck").text = pluck
    if getattr(note_model, "arpeggio", None) in {"single", "top"}:
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
    SubElement(xml_note, "type").text = duration_type
    if dotted:
        SubElement(xml_note, "dot")
    _append_note_technical(
        xml_note,
        string=string,
        fret=fret,
        note_model=note_model,
        fermata=fermata,
    )


def _add_barline(measure: Element, *, location: str, style: str, repeat: str | None = None) -> None:
    barline = SubElement(measure, "barline")
    barline.set("location", location)
    SubElement(barline, "bar-style").text = style
    if repeat is not None:
        repeat_node = SubElement(barline, "repeat")
        repeat_node.set("direction", repeat)


def _barline_style(value: str | None) -> str:
    mapping = {
        "|": "regular",
        "||": "light-light",
        ":": "dotted",
        " ": "none",
    }
    return mapping.get((value or "|").strip(), "regular")


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
    note_models: Sequence[object] | None = None,
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
        )


def _append_musicxml_chord_notes(
    measure: Element,
    bar: Bar,
    *,
    pitch_for_string: list[int],
    fermata_pending: bool,
) -> None:
    remaining_fermata = fermata_pending
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
) -> None:
    if bar.chords:
        _append_musicxml_chord_notes(
            measure,
            bar,
            pitch_for_string=pitch_for_string,
            fermata_pending=bool(bar.fermata),
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


def _append_musicxml_measure_prefix(
    part: Element,
    piece: Piece,
    bar: Bar,
    bar_number: int,
    *,
    settings: dict[str, str],
    pitch_for_string: list[int],
    carry_repeat_forward: bool,
) -> tuple[Element, str]:
    measure = SubElement(part, "measure", number=str(bar_number))
    if carry_repeat_forward:
        _add_barline(measure, location="left", style="heavy-light", repeat="forward")
    repeat = (bar.repeat or "").strip()
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


def _finish_musicxml_measure(measure: Element, bar: Bar, repeat: str) -> bool:
    carry_repeat_forward = repeat in (".:", ":|:")
    right_repeat = "backward" if repeat in (":.", ":|:") else None
    bar_style = "light-heavy" if right_repeat else _barline_style(bar.barline)
    if repeat or bar.barline:
        _add_barline(measure, location="right", style=bar_style, repeat=right_repeat)
    return carry_repeat_forward


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
    carry_repeat_forward: bool,
) -> bool:
    measure, repeat = _append_musicxml_measure_prefix(
        part,
        piece,
        bar,
        bar_index + 1,
        settings=settings,
        pitch_for_string=pitch_for_string,
        carry_repeat_forward=carry_repeat_forward,
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
    )
    return _finish_musicxml_measure(measure, bar, repeat)


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

    carry_repeat_forward = False
    for bar_index, bar in enumerate(piece.bars):
        carry_repeat_forward = _append_musicxml_measure(
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
            carry_repeat_forward=carry_repeat_forward,
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
