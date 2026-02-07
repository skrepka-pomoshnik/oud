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
    author_value = _annotation_lookup(annotations, "author")
    footnote_value = _annotation_lookup(annotations, "footnote")

    if piece_value:
        piece.title = piece_value
    if subtitle_value:
        piece.subtitle = subtitle_value
    if composer_value:
        piece.composer = composer_value
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


def parse_bar(bar_data: bytes) -> Bar:  # noqa: PLR0912, C901
    bar = Bar()
    bar.time_sig = parse_time_signature(bar_data)
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
                    string = 7
                    fret = bar_data[ptr + 1] - 0x61
                elif flag & 0x20:
                    string = bar_data[ptr + 1] - 0x30 + 7
                    fret = 0
                elif flag & 0x48 == 0x48:
                    string = 8
                    fret = bar_data[ptr + 1] - 0x61

            if string is not None and fret is not None:
                note = Note(string=string, fret=fret, raw_pos=ptr)
                bar.notes.append(note)
                chord.notes.append(note)

            ptr += 5

        if chord.notes:
            bar.chords.append(chord)

    return bar


def load_ft3(path: str) -> Piece:
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

    bars = [parse_bar(chunk) for chunk in re.split(b"\x03\x80", data)]
    _apply_legacy_duration_fix(bars)
    max_string = 0
    for bar in bars:
        for note in bar.notes:
            max_string = max(max_string, note.string + 1)
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


def _needs_legacy_duration_fix(bars: list[Bar]) -> bool:
    if not bars or any(bar.time_sig for bar in bars):
        return False
    sums = [_bar_sum_quarter_beats(bar) for bar in bars if bar.chords]
    if not sums:
        return False
    return abs(median(sums) - 1.5) < 0.05


def _apply_legacy_duration_fix(bars: list[Bar]) -> None:
    # Some FT3 files encode rhythms one step faster (e.g. 7 meaning 16th).
    # Detect this pattern and shift note_type by one to restore musical lengths.
    if not _needs_legacy_duration_fix(bars):
        return
    for bar in bars:
        if bar.time_sig is None:
            bar.time_sig = "O"
        for chord in bar.chords:
            if chord.note_type > 2:
                chord.note_type -= 1


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
