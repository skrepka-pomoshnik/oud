from __future__ import annotations

from oud.importers.ft3.extras import decode_ft3_extras
from oud.importers.ft3.metadata import (
    _embedded_plain_text,
    _embedded_rtf_blocks,
)
from oud.importers.ft3.musical.duration import (
    note_type_to_denominator,
    parse_time_signature,
)
from oud.importers.ft3.text.codec import (
    is_ft3_text_record,
)
from petrucci.core.model import (
    Bar,
    Chord,
    Note,
)


def at_next_note(s: int, f: int) -> bool:
    on_fret = 0x30 <= f <= 0x3E
    # French tab frets are letter-coded across a wider alphabet range, not just a..f.
    on_diapason = 0x61 <= f <= 0x7A
    on_string = 0x02 <= s <= 0x08
    return on_string and (on_fret or on_diapason)


def _decode_ft3_note_position(
    string_byte: int,
    fret_byte: int,
    note_flag: int,
) -> tuple[int, int] | None:
    if string_byte < 8:
        fret = fret_byte - 0x61 if 0x61 <= fret_byte <= 0x7A else fret_byte - 0x30
        return string_byte - 1, fret

    if string_byte != 0x08:
        return None

    if note_flag == 0x00 and 0x61 <= fret_byte <= 0x7A:
        return 7, fret_byte - 0x61
    if (note_flag & 0x20) and 0x30 <= fret_byte <= 0x39:
        return fret_byte - 0x30 + 7, 0
    if (note_flag & 0x48) == 0x48 and 0x61 <= fret_byte <= 0x7A:
        return 8, fret_byte - 0x61
    return None


_DYNAMIC_TEXT = {"ppp", "pp", "p", "mp", "mf", "f", "ff", "fff"}


def _is_standard_staff_record(data: bytes) -> bool:
    # Byte 30 is the number of simultaneous standard-note records. Older
    # files commonly use one, while polyphonic and mensural records use up to
    # eight before the row marker in byte 31.
    return len(data) >= 32 and 1 <= data[30] <= 8 and 0x30 <= data[31] <= 0x35


def _is_embedded_score_text_record(data: bytes) -> bool:
    if len(data) < 32 or (data[30:32] != b"\x90\x01" and data[:2] != b"\x90\x01"):
        return False
    alpha = sum((0x41 <= value <= 0x5A) or (0x61 <= value <= 0x7A) for value in data[32:])
    has_font_object = data[32:38] == b"\x01\x00\x00\x00\x01\x00"
    return is_ft3_text_record(data) or alpha >= 24 or (has_font_object and alpha >= 6)


def _leading_tab_text_object(data: bytes) -> tuple[str, int] | None:
    if len(data) < 44 or data[30:32] != b"\x00\x00" or data[32:36] != b"\x01\x00\x00\x00":
        return None
    text_size = data[41]
    end = 44 + text_size
    if end > len(data):
        return None
    text = data[42 : 42 + text_size].decode("latin1", errors="replace").strip()
    return text, end


def _prepare_tab_body(data: bytes, bar: Bar) -> tuple[int, int] | None:
    if _is_standard_staff_record(data):
        return None
    # A leading 0x0190 header is a score text object. The same marker at
    # bytes 30..31 can introduce a text-bearing tablature bar, whose chord
    # stream follows the font/text payload and must still be scanned.
    if data[:2] == b"\x90\x01" and _is_embedded_score_text_record(data):
        return None
    object_count = int.from_bytes(data[28:30], "little") + 1 if len(data) >= 30 else 0
    if object_count > 128:
        return None
    ptr = 32
    text_object = _leading_tab_text_object(data)
    if text_object is None:
        return ptr, object_count
    text, ptr = text_object
    lowered = text.lower().rstrip(".")
    if lowered in _DYNAMIC_TEXT:
        bar.dynamic = lowered
    elif text and any(char.isalnum() for char in text):
        bar.editorial_text.append(text)
    return ptr, max(0, object_count - 1)


def _grid_kind(flags: int) -> str | None:
    if flags & 0x02:
        return "start"
    if flags & 0x04:
        return "mid"
    if flags & 0x08:
        return "end"
    return None


def _append_ft3_note(bar: Bar, chord: Chord, data: bytes, ptr: int) -> None:
    extras = (data[ptr + 3] << 8) | data[ptr + 2]
    decoded = decode_ft3_extras(extras)
    decoded_position = _decode_ft3_note_position(data[ptr], data[ptr + 1], data[ptr + 4])
    if decoded_position is None:
        return
    string, fret = decoded_position
    if decoded.bass_course is not None:
        string, fret = decoded.bass_course, 0
    note = Note(
        string=string,
        fret=fret,
        raw_pos=ptr,
        barre=decoded.barre,
        right_fingering=decoded.right_fingering,
        left_fingering=decoded.left_fingering,
        right_ornament=decoded.right_ornament,
        left_ornament=decoded.left_ornament,
        arpeggio=decoded.arpeggio,
        ft3_extras=extras if extras else None,
        ft3_extra_residual=decoded.residual,
        editorial_brackets=decoded.editorial_brackets,
        ft3_layout_flags=decoded.layout_flags,
    )
    bar.notes.append(note)
    chord.notes.append(note)


def _parse_tab_chords(bar_data: bytes, bar: Bar, ptr: int, object_count: int) -> None:

    while ptr + 9 <= len(bar_data):
        if len(bar.chords) >= object_count:
            break
        if not at_next_note(bar_data[ptr + 4], bar_data[ptr + 5]):
            ptr += 1
            continue

        note_type = bar_data[ptr] + 2
        if note_type_to_denominator(note_type) is None:
            # Ignore false-positive chord headers found while scanning body bytes.
            # Valid FT3 rhythmic note types map to known denominators.
            ptr += 1
            continue
        flags = bar_data[ptr + 1]
        chord = Chord(note_type=note_type, dotted=bool(flags & 0x10), grid=_grid_kind(flags))
        item_count = int.from_bytes(bar_data[ptr - 2 : ptr], "little") if ptr >= 2 else 0
        # Minimal hand-built fixtures predate the decoded item-count field.
        note_count = max(0, item_count - 1) if item_count else 128
        ptr += 4

        while note_count and ptr + 5 <= len(bar_data) and at_next_note(bar_data[ptr], bar_data[ptr + 1]):
            _append_ft3_note(bar, chord, bar_data, ptr)
            ptr += 5
            note_count -= 1

        if chord.notes:
            bar.chords.append(chord)


def parse_bar(bar_data: bytes) -> Bar:
    bar = Bar()
    bar.time_sig = parse_time_signature(bar_data)
    _parse_bar_markers(bar_data, bar)
    body_plan = _prepare_tab_body(bar_data, bar)
    if body_plan is not None:
        _parse_tab_chords(bar_data, bar, *body_plan)
        for text in _embedded_plain_text(bar_data):
            if text not in bar.editorial_text:
                bar.editorial_text.append(text)
    return bar


def _apply_embedded_sections(chunks: list[bytes], bars: list[Bar]) -> None:
    for index, chunk in enumerate(chunks[:-1]):
        titles = _embedded_rtf_blocks(chunk)
        if not titles:
            continue
        bars[index].system_break = True
        target = bars[index + 1]
        target.page_break_before = True
        target.section_title = titles[0]
        target.section_subtitle = titles[1] if len(titles) > 1 else None


def _parse_bar_markers(bar_data: bytes, bar: Bar) -> None:
    if len(bar_data) < 2:
        return
    b0 = bar_data[0]
    b1 = bar_data[1]

    # Corpus-based FT3 header hints (conservative):
    # - byte1 bit 0x10 marks left repeat dots
    # - byte0 upper-nibble bit 0x10 marks right repeat dots
    # - byte0 bit 0x80 and/or byte1 bit 0x01 mark an explicit closing/double barline
    # - byte1 bit 0x02 appears on a few bars alongside explicit closers and likely
    #   indicates right repeat dots; decode it as such only for structural repeat marks.
    left_repeat = bool(b1 & 0x10)
    right_repeat = bool((b0 & 0x10) or (b1 & 0x02))

    if left_repeat and right_repeat:
        bar.repeat = ":|:"
    elif left_repeat:
        bar.repeat = ".:"
    elif right_repeat:
        bar.repeat = ":."

    bar.ending_numbers = tuple(number for bit, number in ((0x20, 1), (0x40, 2)) if b0 & bit)

    if (b0 & 0x80) or (b1 & 0x01):
        bar.barline = "||"
