from __future__ import annotations

import gzip
import re
from pathlib import Path
from statistics import median

from oud.core.model import Bar, Chord, Note, Piece


def _strip_rtf(text: str) -> str:
    if "\\rtf" not in text:
        return text.strip()
    cleaned = re.sub(r"{\\fonttbl.*?}", " ", text, flags=re.S)
    cleaned = re.sub(r"{\\colortbl.*?}", " ", cleaned, flags=re.S)
    cleaned = re.sub(r"\\'[0-9a-fA-F]{2}", "", cleaned)
    cleaned = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", cleaned)
    cleaned = re.sub(r"\\[{}]", "", cleaned)
    cleaned = cleaned.replace("{", " ").replace("}", " ")
    cleaned = re.sub(r"[\x00-\x1f]+", " ", cleaned)
    cleaned = cleaned.replace("~", " ")
    cleaned = re.sub(r"\\+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def read_ft3(path: str) -> bytes:
    with Path(path).open("rb") as f:
        magic = f.read(2)
        f.seek(0)

        if magic == b"\x1F\x8B":
            with gzip.open(path, "rb") as gz:
                return gz.read()

        return f.read()


def extract_text(data: bytes, marker: bytes) -> tuple[str | None, int | None]:
    pos = data.find(marker)
    if pos == -1:
        return None, None
    pos += len(marker)
    if marker == b"CPiece":
        start = data.find(b"{\\rtf", pos)
        if start != -1:
            end = data.find(b"}\r\n~", start)
            if end != -1:
                raw = data[start : end + 1]
                text = raw.decode("utf-8", errors="ignore")
                return text, end + 1
        if pos + 4 <= len(data):
            length = int.from_bytes(data[pos : pos + 4], "little")
            if 0 < length <= len(data) - (pos + 4):
                raw = data[pos + 4 : pos + 4 + length]
                start = raw.find(b"{")
                if start != -1:
                    raw = raw[start:]
                text = raw.decode("utf-8", errors="ignore")
                return text, pos + 4 + length
    length = data[pos]
    text = data[pos + 1 : pos + 1 + length].decode("utf-8", errors="ignore")
    return text, pos + 1 + length


def _find_matching_brace(data: bytes, start: int, stop: int) -> int | None:
    depth = 0
    idx = start
    while idx < stop:
        byte = data[idx]
        if byte == ord("{"):
            depth += 1
        elif byte == ord("}"):
            depth -= 1
            if depth == 0:
                return idx
        idx += 1
    return None


def _extract_cpiece_blocks(data: bytes) -> tuple[list[str], str]:
    cpiece = data.find(b"CPiece")
    if cpiece == -1:
        return [], ""
    cbar = data.find(b"CBar", cpiece + 6)
    stop = cbar if cbar != -1 else min(len(data), cpiece + 8192)
    blocks: list[str] = []
    index = cpiece + 6
    while True:
        start = data.find(b"{\\rtf", index, stop)
        if start == -1:
            break
        end = _find_matching_brace(data, start, stop)
        if end is None:
            break
        block = data[start : end + 1].decode("utf-8", errors="ignore")
        blocks.append(_strip_rtf(block))
        index = end + 1
    metadata_blob = ""
    if index < stop:
        raw = data[index:stop]
        metadata_blob = raw.decode("latin1", errors="ignore")
    return blocks, metadata_blob


def _parse_section_annotations(text: str) -> dict[str, str]:
    annotations: dict[str, str] = {}
    for raw_line in text.replace("\x00", "\n").splitlines():
        line = re.sub(r"[\x00-\x1f]+", " ", raw_line).strip()
        if not line:
            continue
        line = re.sub(r"^[^A-Za-z]+", "", line)
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = re.sub(r"\s+", " ", key.strip().lower())
        value = value.strip()
        if not key or not value:
            continue
        annotations[key] = value
    return annotations


def _annotation_lookup(annotations: dict[str, str], name: str) -> str | None:
    name_l = name.strip().lower()
    if name_l in annotations:
        return annotations[name_l]
    short = name_l[:3]
    for key, value in annotations.items():
        if key[:3] == short:
            return value
        if key.endswith(name_l):
            return value
        if key.endswith(short):
            return value
    return None


def _parse_footnote_parts(footnote: str | None) -> tuple[str | None, str | None, str | None]:
    if not footnote:
        return None, None, None
    parts = [part.strip() for part in re.split(r"\s{2,}", footnote.strip(), maxsplit=2)]
    source = parts[0] if len(parts) >= 1 and parts[0] else None
    editor = parts[1] if len(parts) >= 2 and parts[1] else None
    comment = parts[2] if len(parts) >= 3 and parts[2] else None
    return source, editor, comment


def _apply_annotations(piece: Piece, annotations: dict[str, str]) -> None:
    key_value = _annotation_lookup(annotations, "key")
    type_value = _annotation_lookup(annotations, "type")
    difficulty_value = _annotation_lookup(annotations, "difficulty")
    ensemble_value = _annotation_lookup(annotations, "ensemble")
    instrumentation_value = _annotation_lookup(annotations, "instrumentation")
    part_value = _annotation_lookup(annotations, "part")
    source_value = _annotation_lookup(annotations, "source")
    editor_value = _annotation_lookup(annotations, "editor")
    comment_value = _annotation_lookup(annotations, "comment")
    publisher_value = _annotation_lookup(annotations, "publisher/library")
    volume_value = _annotation_lookup(annotations, "volume")
    page_value = _annotation_lookup(annotations, "page")
    piece_value = _annotation_lookup(annotations, "piece")
    subtitle_value = _annotation_lookup(annotations, "subtitle")
    composer_value = _annotation_lookup(annotations, "composer")
    arranger_value = _annotation_lookup(annotations, "arranger")
    author_value = _annotation_lookup(annotations, "author")
    footnote_value = _annotation_lookup(annotations, "footnote")

    if piece_value:
        piece.title = piece_value
    if subtitle_value:
        piece.subtitle = subtitle_value
    if composer_value:
        piece.composer = composer_value
    if arranger_value:
        piece.arranger = arranger_value
    if author_value:
        piece.author = author_value
    if footnote_value:
        piece.footnote = footnote_value

    piece.key = key_value
    piece.piece_type = type_value
    piece.difficulty = difficulty_value
    piece.ensemble = ensemble_value
    piece.instrumentation = instrumentation_value
    piece.part = part_value
    piece.source = source_value
    piece.editor = editor_value
    piece.comment = comment_value
    piece.publisher = publisher_value
    piece.volume = volume_value
    piece.page = page_value
    piece.section_annotations = annotations


def at_next_note(s: int, f: int) -> bool:
    on_fret = 0x30 <= f <= 0x3E
    on_diapason = 0x61 <= f <= 0x66
    on_string = 0x02 <= s <= 0x08
    return on_string and (on_fret or on_diapason)


def _ft3_right_fingering(extras: int) -> str | None:
    # Bit masks are adapted from the luteconv FT3 parser (thanks to that reverse-engineering work).
    if extras & 0x0002:
        return "thumb"
    if extras & 0x0004:
        return "1"
    if extras & 0x0008:
        return "2"
    return None


def _ft3_left_fingering(extras: int) -> str | None:
    if extras & 0x0020:
        return "1"
    if extras & 0x0040:
        return "2"
    if extras & 0x0080:
        return "3"
    if extras & 0x0100:
        return "4"
    return None


def _ft3_left_ornament(extras: int) -> str | None:
    ornament = extras & 0xFE00
    if ornament == 0x0400:
        return "#"
    if ornament == 0x0800:
        return "+"
    if ornament == 0x4A00:
        return "dot-left"
    if ornament == 0x0C00:
        return "x"
    if extras == 0x3400:
        return "brackets"
    return None


def _ft3_right_ornament(extras: int) -> str | None:
    ornament = extras & 0xFE00
    if ornament == 0x0600:
        return "#"
    return None


def parse_bar(bar_data: bytes) -> Bar:  # noqa: PLR0912, C901
    bar = Bar()
    bar.time_sig = parse_time_signature(bar_data)
    _parse_bar_markers(bar_data, bar)
    ptr = 32

    while ptr + 9 <= len(bar_data):
        if not at_next_note(bar_data[ptr + 4], bar_data[ptr + 5]):
            ptr += 1
            continue

        note_type = bar_data[ptr] + 2
        dotted = bool(bar_data[ptr + 1] & 0x10)
        grid = None
        if bar_data[ptr + 1] & 0x02:
            grid = "start"
        elif bar_data[ptr + 1] & 0x04:
            grid = "mid"
        elif bar_data[ptr + 1] & 0x08:
            grid = "end"
        chord = Chord(note_type=note_type, dotted=dotted, grid=grid)
        ptr += 4

        while ptr + 5 <= len(bar_data) and at_next_note(bar_data[ptr], bar_data[ptr + 1]):
            string = None
            fret = None

            if bar_data[ptr] < 8:
                string = bar_data[ptr] - 1
                fret_byte = bar_data[ptr + 1]
                fret = fret_byte - 0x61 if 0x61 <= fret_byte <= 0x7A else fret_byte - 0x30
            elif bar_data[ptr] == 8:
                flag = bar_data[ptr + 4]
                if flag == 0x00:
                    fret_byte = bar_data[ptr + 1]
                    if 0x61 <= fret_byte <= 0x7A:
                        string = 7
                        fret = fret_byte - 0x61
                elif flag & 0x20:
                    course_byte = bar_data[ptr + 1]
                    if 0x30 <= course_byte <= 0x39:
                        string = course_byte - 0x30 + 7
                        fret = 0
                elif flag & 0x48 == 0x48:
                    fret_byte = bar_data[ptr + 1]
                    if 0x61 <= fret_byte <= 0x7A:
                        string = 8
                        fret = fret_byte - 0x61

            if string is not None and fret is not None:
                extras = (bar_data[ptr + 3] << 8) | bar_data[ptr + 2]
                note = Note(
                    string=string,
                    fret=fret,
                    raw_pos=ptr,
                    right_fingering=_ft3_right_fingering(extras),
                    left_fingering=_ft3_left_fingering(extras),
                    right_ornament=_ft3_right_ornament(extras),
                    left_ornament=_ft3_left_ornament(extras),
                    ft3_extras=extras if extras else None,
                )
                bar.notes.append(note)
                chord.notes.append(note)

            ptr += 5

        if chord.notes:
            bar.chords.append(chord)

    return bar


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

    if (b0 & 0x80) or (b1 & 0x01):
        bar.barline = "||"


def _is_ft3_text_record(chunk: bytes) -> bool:
    tail = chunk[32:] if len(chunk) > 32 else chunk
    if not tail:
        return False
    newline_count = tail.count(b"\r") + tail.count(b"\n")
    if newline_count < 2:
        return False
    letter_count = sum(
        1
        for b in tail
        if (0x41 <= b <= 0x5A) or (0x61 <= b <= 0x7A)
    )
    return letter_count >= 6


def load_ft3(path: str) -> Piece:  # noqa: C901
    data = read_ft3(path)

    blocks, metadata_blob = _extract_cpiece_blocks(data)
    title = blocks[0] if len(blocks) >= 1 else None
    subtitle = blocks[1] if len(blocks) >= 2 else None
    composer = blocks[2] if len(blocks) >= 3 else None
    footnote = blocks[3] if len(blocks) >= 4 else None
    if not title:
        title, _pos = extract_text(data, b"CPiece")
        if title:
            title = _strip_rtf(title)
    if not title:
        title = Path(path).stem.replace("_", " ")
    author = None

    raw_chunks = re.split(b"\x03\x80", data)
    filtered_text_records = 0
    bar_chunks = raw_chunks
    body_start = data.find(b"CBar")
    if body_start >= 0:
        body_chunks = re.split(b"\x03\x80", data[body_start + 4 :])
        text_record_count = sum(1 for chunk in body_chunks if _is_ft3_text_record(chunk))
        # Some FT3 files interleave lyric/melody text records in the body stream.
        # Only switch to body-based parsing/filtering when this pattern is clearly present,
        # otherwise keep legacy whole-file splitting to preserve current import parity.
        if text_record_count >= 2:
            filtered_text_records = text_record_count
            bar_chunks = [chunk for chunk in body_chunks if not _is_ft3_text_record(chunk)]
    bars = [parse_bar(chunk) for chunk in bar_chunks]
    _apply_legacy_duration_fix(bars)
    _fill_missing_time_signatures(bars)
    max_string = 0
    for bar in bars:
        for note in bar.notes:
            max_string = max(max_string, note.string)
    strings = max(6, max_string) if max_string else 6
    piece = Piece(
        title=title,
        subtitle=subtitle,
        author=author,
        composer=composer,
        footnote=footnote,
        bars=bars,
        strings=strings,
    )
    if filtered_text_records:
        piece.import_warnings.append(
            "FT3 lyric/melody text records are present and currently ignored.",
        )
    annotations = _parse_section_annotations(metadata_blob)
    _apply_annotations(piece, annotations)
    source, editor, comment = _parse_footnote_parts(piece.footnote)
    piece.footnote_source = source
    piece.footnote_editor = editor
    piece.footnote_comment = comment
    if piece.source is None:
        piece.source = source
    if piece.editor is None:
        piece.editor = editor
    if piece.comment is None:
        piece.comment = comment
    return piece


def _bar_sum_quarter_beats(bar: Bar) -> float:
    total = 0.0
    for chord in bar.chords:
        denom = note_type_to_denominator(chord.note_type)
        if denom is None:
            continue
        value = 4.0 / denom
        if chord.dotted:
            value *= 1.5
        total += value
    return total


def _bar_sums_with_chords(bars: list[Bar]) -> list[float]:
    return [_bar_sum_quarter_beats(bar) for bar in bars if bar.chords]


def _needs_legacy_duration_fix(bars: list[Bar]) -> bool:
    if not bars or any(bar.time_sig for bar in bars):
        return False
    sums = _bar_sums_with_chords(bars)
    if not sums:
        return False
    return abs(median(sums) - 1.5) < 0.05


def _needs_common_time_halfbar_fix(bars: list[Bar]) -> bool:
    if not bars:
        return False
    if any((bar.time_sig not in (None, "C")) for bar in bars):
        return False
    sums = _bar_sums_with_chords(bars)
    if not sums:
        return False
    med = median(sums)
    near_half = sum(1 for value in sums if abs(value - 2.0) <= 0.2)
    # Avoid scaling already-correct 4/4 material.
    near_full = sum(1 for value in sums if abs(value - 4.0) <= 0.2)
    return abs(med - 2.0) <= 0.15 and near_half >= int(len(sums) * 0.7) and near_full == 0


def _shift_note_types_one_step_longer(bars: list[Bar], time_sig: str) -> None:
    for bar in bars:
        if bar.time_sig is None:
            bar.time_sig = time_sig
        for chord in bar.chords:
            if chord.note_type > 2:
                chord.note_type -= 1


def _apply_legacy_duration_fix(bars: list[Bar]) -> None:
    # Some FT3 files encode rhythms one step faster (e.g. 7 meaning 16th).
    # Detect this pattern and shift note_type by one to restore musical lengths.
    if _needs_legacy_duration_fix(bars):
        _shift_note_types_one_step_longer(bars, time_sig="O")
        return
    # Another legacy encoding pattern stores 4/4 bars at half-length (2.0).
    if _needs_common_time_halfbar_fix(bars):
        _shift_note_types_one_step_longer(bars, time_sig="C")


def _sum_matches_meter(sum_quarter_beats: float, meter: str) -> bool:
    target = {
        "O": 1.5,
        "3/4": 1.5,
        "6/8": 1.5,
        "C|": 2.0,
        "C": 4.0,
        "4/4": 4.0,
        "2/2": 2.0,
    }.get(meter)
    if target is None:
        return False
    return abs(sum_quarter_beats - target) <= 0.15


def _infer_meter_from_sum(sum_quarter_beats: float) -> str | None:
    if abs(sum_quarter_beats - 1.5) <= 0.15:
        return "O"
    if abs(sum_quarter_beats - 2.0) <= 0.15:
        return "C|"
    if abs(sum_quarter_beats - 4.0) <= 0.2:
        return "C"
    return None


def _fill_missing_time_signatures(bars: list[Bar]) -> None:  # noqa: C901
    if not bars:
        return
    explicit = [idx for idx, bar in enumerate(bars) if bar.time_sig]
    if not explicit:
        for bar in bars:
            if bar.time_sig is None and bar.chords:
                guessed = _infer_meter_from_sum(_bar_sum_quarter_beats(bar))
                if guessed:
                    bar.time_sig = guessed
        return

    def _fill_range(
        start: int,
        end: int,
        *,
        prev_meter: str | None,
        next_meter: str | None,
    ) -> None:
        for idx in range(start, end):
            bar = bars[idx]
            if bar.time_sig is not None or not bar.chords:
                continue
            total = _bar_sum_quarter_beats(bar)
            if prev_meter and _sum_matches_meter(total, prev_meter):
                bar.time_sig = prev_meter
                continue
            if next_meter and _sum_matches_meter(total, next_meter):
                bar.time_sig = next_meter
                continue
            guessed = _infer_meter_from_sum(total)
            if guessed:
                bar.time_sig = guessed

    first = explicit[0]
    _fill_range(0, first, prev_meter=None, next_meter=bars[first].time_sig)
    for pos, idx in enumerate(explicit[:-1]):
        nxt = explicit[pos + 1]
        _fill_range(idx + 1, nxt, prev_meter=bars[idx].time_sig, next_meter=bars[nxt].time_sig)
    last = explicit[-1]
    _fill_range(last + 1, len(bars), prev_meter=bars[last].time_sig, next_meter=None)


def parse_time_signature(bar_data: bytes) -> str | None:
    if len(bar_data) < 10:
        return None
    time_signature = bar_data[0] & 0x7F
    if time_signature == 0x01:
        return "C"
    if time_signature == 0x02:
        return "C|"
    if time_signature == 0x03:
        return "O"
    if time_signature == 0x06:
        beats = bar_data[9]
        beat_type = bar_data[8]
        if beats and beat_type:
            return f"{beats}/{beat_type}"
    return None


def note_type_to_denominator(note_type: int) -> int | None:
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
    return mapping.get(note_type)


def build_durations(piece: Piece) -> dict[tuple[int, int, int], int]:
    durations: dict[tuple[int, int, int], int] = {}
    for b_idx, bar in enumerate(piece.bars):
        col = 0
        for chord in bar.chords:
            denom = note_type_to_denominator(chord.note_type)
            if denom is None:
                continue
            durations[(b_idx, 0, col)] = denom
            col += 1
    return durations
