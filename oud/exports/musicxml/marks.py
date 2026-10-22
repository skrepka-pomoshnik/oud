"""Measure barlines, directions, endings and chord symbols for MusicXML."""

from __future__ import annotations

import re
from xml.etree.ElementTree import Element, SubElement

from petrucci.core.model import Bar

_CHORD_SUFFIX_KINDS = {
    "": "major",
    "m": "minor",
    "7": "dominant",
    "maj7": "major-seventh",
    "m7": "minor-seventh",
    "dim": "diminished",
    "aug": "augmented",
    "dim7": "diminished-seventh",
    "m7b5": "half-diminished",
    "sus4": "suspended-fourth",
    "sus2": "suspended-second",
    "6": "major-sixth",
    "m6": "minor-sixth",
    "9": "dominant-ninth",
    "5": "power",
}
_CHORD_SYMBOL = re.compile(r"^([A-G])(#|b|##|bb)?(.*?)(?:/([A-G])(#|b|##|bb)?)?$")
_ALTER_VALUES = {"#": "1", "b": "-1", "##": "2", "bb": "-2"}


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
    mapping = {"|": "regular", "||": "light-light", "|.": "light-heavy", ":": "dotted", " ": "none"}
    key = "|" if value is None else (value.strip() or value)
    return mapping.get(key, "regular")


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
    known = {"ppp", "pp", "p", "mp", "mf", "f", "ff", "fff", "sfz", "fz", "fp"}
    if value in known:
        dynamics = SubElement(direction_type, "dynamics")
        SubElement(dynamics, value)
        return
    SubElement(direction_type, "words").text = dynamic


def _harmony_element(name: str) -> Element:
    """A <harmony> for a chord symbol such as ``Am7`` or ``C/G``; an unknown suffix is kept as text."""
    match = _CHORD_SYMBOL.match(name.strip())
    harmony = Element("harmony")
    if match is None:
        SubElement(SubElement(harmony, "root"), "root-step").text = "C"
        SubElement(harmony, "kind", text=name).text = "other"
        return harmony
    root_step, root_alter, suffix, bass_step, bass_alter = match.groups()
    root = SubElement(harmony, "root")
    SubElement(root, "root-step").text = root_step
    if root_alter:
        SubElement(root, "root-alter").text = _ALTER_VALUES[root_alter]
    kind = SubElement(harmony, "kind", text=suffix)
    kind.text = _CHORD_SUFFIX_KINDS.get(suffix, "other")
    if bass_step:
        bass = SubElement(harmony, "bass")
        SubElement(bass, "bass-step").text = bass_step
        if bass_alter:
            SubElement(bass, "bass-alter").text = _ALTER_VALUES[bass_alter]
    return harmony
