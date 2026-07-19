from __future__ import annotations

import gzip
import re
from pathlib import Path

from petrucci.model import (
    Piece,
)


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


def _embedded_rtf_blocks(data: bytes) -> list[str]:
    blocks: list[str] = []
    index = 0
    while True:
        start = data.find(b"{\\rtf", index)
        if start < 0:
            return blocks
        end = _find_matching_brace(data, start, len(data))
        if end is None:
            return blocks
        text = _strip_rtf(data[start : end + 1].decode("latin1", errors="ignore"))
        if text:
            blocks.append(text)
        index = end + 1


def _embedded_plain_text(data: bytes) -> list[str]:  # noqa: C901
    texts: list[str] = []
    scan_data = bytearray(data)
    rtf_index = 0
    while True:
        start = data.find(b"{\\rtf", rtf_index)
        if start < 0:
            break
        end = _find_matching_brace(data, start, len(data))
        if end is None:
            break
        scan_data[start : end + 1] = bytes(end + 1 - start)
        rtf_index = end + 1
    index = 32
    while index < len(scan_data):
        size = scan_data[index]
        end = index + 1 + size
        if 8 <= size <= 160 and end <= len(scan_data):
            raw = scan_data[index + 1 : end]
            if all(32 <= value <= 126 for value in raw):
                text = raw.decode("latin1").strip()
                alpha = sum(char.isalpha() for char in text)
                if alpha >= 4 and "\\rtf" not in text and text not in texts:
                    texts.append(text)
                index = end
                continue
        index += 1
    return texts


def read_ft3(path: str) -> bytes:
    with Path(path).open("rb") as f:
        magic = f.read(2)
        f.seek(0)

        if magic == b"\x1f\x8b":
            with gzip.open(path, "rb") as gz:
                return gz.read()

        return f.read()


def extract_text(data: bytes, marker: bytes) -> tuple[str | None, int | None]:  # noqa: C901
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


def _extract_ft3_preamble_notes(data: bytes) -> list[str]:
    cpiece = data.find(b"CPiece")
    if cpiece <= 0:
        return []
    preamble = data[:cpiece]
    printable = "".join(chr(byte) if 32 <= byte <= 126 else " " for byte in preamble)
    printable = re.sub(r"\s+", " ", printable)
    pattern = re.compile(
        r"([A-Z][A-Za-z][A-Za-z0-9 ,.'()/-]{8,}?"
        r"Encoded and edited by [A-Z][A-Za-z .'-]{1,80}\.)",
    )
    matches = [match.group(1).strip() for match in pattern.finditer(printable)]
    deduped: list[str] = []
    seen: set[str] = set()
    for text in matches:
        cleaned = re.sub(r"^[^A-Za-z]+", "", text).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        deduped.append(cleaned)
    return deduped


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


def _canonicalize_metadata_fields(annotations: dict[str, str]) -> dict[str, str]:
    normalized = dict(annotations)
    con_value = _annotation_lookup(annotations, "con")
    source_value = _annotation_lookup(annotations, "source")
    if con_value:
        if source_value:
            if con_value not in source_value:
                normalized["source"] = f"{source_value} {con_value}".strip()
        else:
            normalized["source"] = con_value
    return normalized


def _apply_annotations(piece: Piece, annotations: dict[str, str]) -> None:
    normalized = _canonicalize_metadata_fields(annotations)
    key_value = _annotation_lookup(annotations, "key")
    type_value = _annotation_lookup(annotations, "type")
    style_value = _annotation_lookup(annotations, "style")
    tuning_value = _annotation_lookup(annotations, "tuning")
    difficulty_value = _annotation_lookup(annotations, "difficulty")
    ensemble_value = _annotation_lookup(annotations, "ensemble")
    instrumentation_value = _annotation_lookup(annotations, "instrumentation")
    part_value = _annotation_lookup(annotations, "part")
    source_value = _annotation_lookup(normalized, "source")
    editor_value = _annotation_lookup(annotations, "editor")
    comment_value = _annotation_lookup(annotations, "comment")
    publisher_value = _annotation_lookup(annotations, "publisher/library") or _annotation_lookup(annotations, "library")
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
    piece.style = style_value
    piece.tuning = tuning_value
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
    piece.raw_metadata = annotations


def _apply_preamble_notes(piece: Piece, notes: list[str]) -> None:
    if not notes:
        return
    piece.notes = list(notes)
    primary = notes[0]
    match = re.match(
        r"(?P<source>.+?),\s*f\.\s*(?P<page>[A-Za-z0-9]+)\.\s*"
        r"Encoded and edited by (?P<editor>.+?)\.$",
        primary,
    )
    if match is None:
        return
    if piece.source is None:
        piece.source = match.group("source").strip()
    if piece.page is None:
        piece.page = match.group("page").strip()
    if piece.editor is None:
        piece.editor = match.group("editor").strip()
