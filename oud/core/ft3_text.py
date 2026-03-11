from __future__ import annotations

import re
from dataclasses import dataclass

from oud.core.model import ImportedTextRow, LyricEvent, MelodyEvent


@dataclass(frozen=True)
class FT3TextRecord:
    melody_grid: str | None
    lyrics: list[str]
    melody_events: list[MelodyEvent]
    lyric_event_rows: list[list[LyricEvent]]
    editorial_text: list[str]
    structured_rows: list[ImportedTextRow]
    parse_mode: str = "ascii"


def _empty_text_record() -> FT3TextRecord:
    return FT3TextRecord(
        melody_grid=None,
        lyrics=[],
        melody_events=[],
        lyric_event_rows=[],
        editorial_text=[],
        structured_rows=[],
        parse_mode="ascii",
    )


@dataclass(frozen=True)
class _LineFeatures:
    text: str
    stripped: str
    length: int
    alpha: int
    digits: int
    placeholders: int
    symbols: int
    weird: int
    has_text: bool
    has_wide_gap: bool


MELODY_SYMBOL_CHARS = set("#'\";:<>?@-+=./()[]{}!|")
LYRIC_WEIRD_CHARS = set("@?><=|[]{}?!\"")
MELODY_SCORE_RULES: tuple[tuple[str, int], ...] = (
    ("digits", 3),
    ("symbols", 2),
    ("placeholders", 2),
)
LYRIC_SCORE_RULES: tuple[tuple[str, int], ...] = (
    ("alpha", 3),
    ("length", 1),
)


def is_ft3_text_record(chunk: bytes) -> bool:
    tail = chunk[32:] if len(chunk) > 32 else chunk
    if not tail:
        return False
    newline_count = tail.count(b"\r") + tail.count(b"\n")
    if newline_count < 2:
        return False
    letter_count = sum(
        1 for b in tail if (0x41 <= b <= 0x5A) or (0x61 <= b <= 0x7A)
    )
    return letter_count >= 6


def _asciiish_lines(data: bytes) -> list[str]:
    chars: list[str] = []
    for b in data:
        if b in (9, 10, 13) or 32 <= b <= 126:
            chars.append(chr(b))
        else:
            chars.append(" ")
    text = "".join(chars).replace("\t", " ")
    lines = [line.rstrip() for line in text.splitlines()]
    return [line for line in lines if line.strip()]


def looks_like_melody_grid(line: str) -> bool:
    features = _line_features(line)
    if not features.has_text or len(features.stripped) < 3:
        return False
    digit_or_symbol = features.digits + features.symbols + features.placeholders + features.alpha
    enough_symbols = digit_or_symbol >= max(3, features.length // 3)
    low_alpha = features.alpha <= max(4, features.length // 5)
    has_melody_tokens = features.digits > 0 or (features.symbols + features.placeholders) >= 2
    return has_melody_tokens and enough_symbols and (digit_or_symbol >= 3 or low_alpha)


def _looks_like_lyric_text(line: str) -> bool:
    features = _line_features(line)
    if not features.has_text:
        return False
    if features.digits > 0:
        return False
    if features.alpha < 1:
        return False
    return features.weird <= max(1, len(features.stripped) // 5)


def _line_features(line: str) -> _LineFeatures:
    stripped = line.strip()
    alpha = sum(ch.isalpha() for ch in stripped)
    digits = sum(ch.isdigit() for ch in stripped)
    placeholders = sum(ch in '@?"!' for ch in stripped)
    symbols = sum(ch in MELODY_SYMBOL_CHARS for ch in stripped)
    weird = sum(ch in LYRIC_WEIRD_CHARS for ch in stripped)
    return _LineFeatures(
        text=line,
        stripped=stripped,
        length=len(stripped),
        alpha=alpha,
        digits=digits,
        placeholders=placeholders,
        symbols=symbols,
        weird=weird,
        has_text=bool(stripped),
        has_wide_gap=bool(re.search(r" {4,}", line)),
    )


def _split_wide_gap(line: str) -> tuple[str, str] | None:
    gaps = list(re.finditer(r" {4,}", line))
    if not gaps:
        return None
    best: tuple[int, str, str] | None = None
    for gap in gaps:
        left = line[: gap.start()].rstrip()
        right = line[gap.end() :].rstrip()
        if not left and not right:
            continue
        left_features = _line_features(left)
        right_features = _line_features(right)
        score = 0
        if _is_melody_candidate(left):
            score += 10 + _score_kind(left_features, MELODY_SCORE_RULES)
        if _is_lyric_candidate(right):
            score += 10 + _score_kind(right_features, LYRIC_SCORE_RULES)
        # Prefer splits that leave both sides non-empty and preserve some right text.
        if left and right:
            score += 2
        if best is None or score > best[0]:
            best = (score, left, right)
    if best is None:
        return None
    _, left, right = best
    return left, right


def _pick_melody_line(candidates: list[str]) -> str | None:
    if not candidates:
        return None

    def _score(line: str) -> tuple[int, int, int]:
        features = _line_features(line)
        melody_score = _score_kind(features, MELODY_SCORE_RULES)
        lyric_penalty = _score_kind(features, LYRIC_SCORE_RULES)
        return (melody_score, -lyric_penalty, len(features.stripped))

    best = max(candidates, key=_score)
    cleaned = "".join(" " if ch in '@?"!' else ch for ch in best).rstrip()
    return cleaned if cleaned.strip() else None


def _score_kind(features: _LineFeatures, rules: tuple[tuple[str, int], ...]) -> int:
    total = 0
    for key, weight in rules:
        total += getattr(features, key) * weight
    return total


def _is_melody_candidate(line: str) -> bool:
    return looks_like_melody_grid(line)


def _is_lyric_candidate(line: str) -> bool:
    return _looks_like_lyric_text(line)


def _classify_raw_line(raw: str) -> tuple[str | None, str | None]:
    melody: str | None = None
    lyric: str | None = None
    split = _split_wide_gap(raw)
    if split is None:
        if _is_melody_candidate(raw):
            melody = raw.rstrip()
        elif _is_lyric_candidate(raw):
            lyric = raw.strip()
        return melody, lyric

    left, right = split
    if _is_melody_candidate(left):
        melody = left.rstrip()
        if _is_lyric_candidate(right):
            lyric = right.strip()
    elif _is_lyric_candidate(raw):
        lyric = raw.strip()
    elif _is_melody_candidate(raw):
        melody = raw.rstrip()
    elif _is_lyric_candidate(right):
        lyric = right.strip()
    return melody, lyric


def _clean_text_token(token: str) -> str:
    token = "".join(" " if ch in '@?"!' else ch for ch in token)
    return token.strip()


def _clean_lyric_token(token: str) -> str:
    cleaned = _clean_text_token(token)
    if not cleaned:
        return ""
    if set(cleaned) <= {"_"}:
        return cleaned
    cleaned = re.sub(r"^[><:%#;,\d]+", "", cleaned)
    cleaned = re.sub(r"[^\w'_\-]+$", "", cleaned)
    return cleaned.strip()


def _keep_lyric_token(token: str) -> bool:
    if not token:
        return False
    if token in {"'", '"', "`", "(", ")", "[", "]", "{", "}", "|", "\\", "/", "=", "+", "*"}:
        return False
    alpha_count = sum(ch.isalpha() for ch in token)
    if alpha_count == 0:
        return False
    lowered = token.lower()
    return not (len(token) == 1 and lowered not in {"i", "a", "o"})


def _line_tokens_with_positions(line: str) -> list[tuple[int, str]]:
    return [(m.start(), m.group(0)) for m in re.finditer(r"\S+", line)]


def _split_record_rows(data: bytes) -> list[bytes]:
    rows: list[bytes] = []
    current = bytearray()
    idx = 0
    while idx < len(data):
        b = data[idx]
        if b == 13:  # CR ends a logical row in FT3 text records.
            row = bytes(current).rstrip(b"\x00")
            if row.strip(b"\x00 "):
                rows.append(row)
            current.clear()
            if idx + 1 < len(data) and data[idx + 1] == 10:
                idx += 1
        else:
            current.append(b)
        idx += 1
    tail = bytes(current).rstrip(b"\x00")
    if tail.strip(b"\x00 "):
        rows.append(tail)
    return rows


def _tokenize_control_row(row: bytes) -> list[tuple[int, str]]:
    tokens: list[tuple[int, str]] = []
    buf: list[str] = []
    col = 0
    start_col = 0

    def flush() -> None:
        nonlocal buf
        if not buf:
            return
        token = "".join(buf)
        cleaned = _clean_text_token(token)
        if cleaned:
            tokens.append((start_col, cleaned))
        buf = []

    for b in row:
        if 32 <= b <= 126:
            if not buf:
                start_col = col
            buf.append(chr(b))
            col += 1
            continue
        flush()
        if 1 <= b <= 31:
            # FT3 lyric records use control bytes as horizontal anchors.
            col = int(b)
    flush()
    return tokens


def _likely_non_lyric_token(token: str) -> bool:
    if not token:
        return True
    lower = token.lower()
    if all(ch.isdigit() or ch == "." for ch in lower):
        return True
    if re.fullmatch(r"[a-gh](?:[#b]|[',])*", lower) and not (
        len(lower) == 1 and lower in {"i", "a", "o"}
    ):
        return True
    if lower in {"times", "new", "roman", "timesnewroman"}:
        return True
    return bool(any(ch in "@?><=|[]{}!\";:" for ch in token))


def _lyric_tokens_from_control_row(row: bytes) -> list[str]:
    positioned = _tokenize_control_row(row)
    if not positioned:
        return []
    tokens = [_clean_lyric_token(tok) for _pos, tok in positioned]
    tokens = [tok for tok in tokens if tok]
    if not tokens:
        return []
    last_non_lyric = -1
    for idx, tok in enumerate(tokens):
        if _likely_non_lyric_token(tok) or not _keep_lyric_token(tok):
            if set(tok) <= {"_"}:
                continue
            last_non_lyric = idx
    start = last_non_lyric + 1
    out = [tok for tok in tokens[start:] if _keep_lyric_token(tok) or set(tok) <= {"_"}]
    if out:
        if " ".join(tok.lower() for tok in out) in {"times new roman", "new roman"}:
            return []
        return out
    fallback = [
        tok
        for tok in tokens
        if (_keep_lyric_token(tok) or set(tok) <= {"_"}) and not _likely_non_lyric_token(tok)
    ]
    if " ".join(tok.lower() for tok in fallback) in {"times new roman", "new roman"}:
        return []
    return fallback


def _raw_control_tokens_from_row(row: bytes) -> list[str]:
    positioned = _tokenize_control_row(row)
    return [tok for _pos, tok in positioned if tok]


def _structured_row_text(row: bytes) -> str:
    chars: list[str] = []
    for b in row:
        if 32 <= b <= 126:
            chars.append(chr(b))
        elif b in (9, 10, 13) or 1 <= b <= 31:
            chars.append(" ")
    return re.sub(r"\s+", " ", "".join(chars)).strip()


def _is_font_noise_text(text: str) -> bool:
    compact = re.sub(r"\s+", "", text).lower()
    return compact in {"timesnewroman", "newroman"}


def _classify_structured_row(row: bytes, row_index: int) -> ImportedTextRow | None:
    text = _structured_row_text(row)
    raw_tokens = _raw_control_tokens_from_row(row)
    lyric_tokens = _lyric_tokens_from_control_row(row)
    if not text and not raw_tokens and not lyric_tokens:
        return None
    if row_index == 0 and _structured_vocal_events(row):
        return ImportedTextRow(row_index=row_index, kind="vocal", text=text, tokens=raw_tokens)
    if raw_tokens and _looks_like_editorial_tokens(raw_tokens):
        return ImportedTextRow(
            row_index=row_index,
            kind="editorial",
            text=" ".join(raw_tokens).strip(),
            tokens=raw_tokens,
        )
    if _is_font_noise_text(text):
        return ImportedTextRow(row_index=row_index, kind="font", text=text, tokens=raw_tokens)
    if lyric_tokens:
        return ImportedTextRow(row_index=row_index, kind="lyrics", text=text, tokens=lyric_tokens)
    return ImportedTextRow(row_index=row_index, kind="unknown", text=text, tokens=raw_tokens)


def _events_from_lyric_tokens(tokens: list[str], *, verse: int) -> list[LyricEvent]:
    events: list[LyricEvent] = []
    onset_idx = 0
    chain_open = False
    for tok in tokens:
        raw = _clean_lyric_token(tok)
        if not raw:
            continue
        if set(raw) <= {"_"}:
            events.append(
                LyricEvent(
                    text="",
                    onset_index=onset_idx,
                    verse=verse,
                    syllabic="single",
                    src_pos=onset_idx,
                    extender=True,
                ),
            )
            onset_idx += 1
            continue
        trailing_hyphen = raw.endswith("-")
        text = raw.rstrip("-").strip()
        if not text and trailing_hyphen:
            text = "-"
        if not text:
            continue
        if text != "-" and not _keep_lyric_token(text):
            continue
        if trailing_hyphen and chain_open:
            syllabic = "middle"
        elif trailing_hyphen:
            syllabic = "begin"
        elif chain_open:
            syllabic = "end"
        else:
            syllabic = "single"
        events.append(
            LyricEvent(
                text=text,
                onset_index=onset_idx,
                verse=verse,
                syllabic=syllabic,
                src_pos=onset_idx,
                extender=False,
            ),
        )
        chain_open = trailing_hyphen
        onset_idx += 1
    return events


def _structured_lyric_rows(tokens_by_row: list[list[str]]) -> list[list[str]]:
    primary: list[str] = []
    secondary: list[str] = []
    for row_idx, row_tokens in enumerate(tokens_by_row):
        if not row_tokens:
            continue
        if len(row_tokens) >= 2:
            secondary.append(row_tokens[0])
            primary.append(row_tokens[-1])
            continue
        token = row_tokens[0]
        prev_len = len(tokens_by_row[row_idx - 1]) if row_idx > 0 else 0
        if row_idx == 0 or prev_len <= 1:
            primary.append(token)
        else:
            secondary.append(token)
    rows: list[list[str]] = []
    if primary:
        rows.append(primary)
    if secondary:
        rows.append(secondary)
    return rows


def _looks_like_editorial_tokens(tokens: list[str]) -> bool:
    if len(tokens) < 3:
        return False
    joined = " ".join(tokens)
    alpha = sum(ch.isalpha() for ch in joined)
    long_tokens = sum(len(tok) >= 4 for tok in tokens)
    pitch_like = sum(
        bool(re.fullmatch(r"[a-gh](?:[#b]|[',])*", tok.lower()))
        for tok in tokens
    )
    has_prose_punct = any(ch in joined for ch in ":;(),./")
    return (
        alpha >= 10
        and long_tokens >= 2
        and pitch_like == 0
        and (has_prose_punct or len(tokens) >= 4)
    )


def _structured_vocal_row_prefix(row: bytes) -> bytes:
    match = next(iter(re.finditer(rb"[A-Za-z][A-Za-z?'\-]*$", row)), None)
    if match is None:
        return row
    return row[: match.start()]


def _vocal_pitch_token(row_value: int, flags: int) -> str:
    if row_value <= 0:
        row_value = 1
    scale = ["d", "e", "f", "g", "a", "b", "c"]
    idx = row_value - 1
    name = scale[idx % len(scale)]
    octave = (idx + 1) // len(scale)
    accidental = ""
    if flags & 0x1000:
        accidental = "b"
    elif flags & 0x0002:
        accidental = "#"
    if octave > 0:
        suffix = "'" * octave
        return f"{name}{accidental}{suffix}"
    return f"{name}{accidental}"


def _vocal_note_type_from_code(code: int) -> int | None:
    mapping = {
        0x33: 4,
        0x34: 5,
        0x35: 6,
    }
    return mapping.get(code)


def _structured_vocal_events(row: bytes) -> list[MelodyEvent]:
    prefix = _structured_vocal_row_prefix(row)
    if len(prefix) < 7:
        return []
    row_value = prefix[0]
    first_flags = int.from_bytes(prefix[1:5], "little")
    events: list[MelodyEvent] = [
        MelodyEvent(
            text=_vocal_pitch_token(row_value, first_flags),
            onset_index=0,
            src_pos=-1,
            note_type=None,
            dotted=bool(first_flags & 0x10),
            accidental_flags=first_flags,
        ),
    ]
    idx = 5
    while idx + 7 <= len(prefix):
        rec = prefix[idx : idx + 7]
        if rec[0] != 0x01 or rec[1] not in (0x33, 0x34, 0x35):
            break
        flags = int.from_bytes(rec[3:5], "little")
        events.append(
            MelodyEvent(
                text=_vocal_pitch_token(rec[2], flags),
                onset_index=len(events),
                src_pos=-1,
                note_type=_vocal_note_type_from_code(rec[1]),
                dotted=bool(flags & 0x10),
                accidental_flags=flags,
            ),
        )
        idx += 7
    if not events:
        return []
    count = int.from_bytes(prefix[idx : idx + 2], "little") if idx + 2 <= len(prefix) else 0
    if count and count != len(events) + 1:
        return []
    return events


def _parse_structured_text_record(tail: bytes) -> FT3TextRecord | None:
    rows = _split_record_rows(tail)
    if not rows:
        return None
    has_controls = any(any(0 < b < 32 and b not in (9, 10, 13) for b in row) for row in rows)
    if not has_controls:
        return None
    structured_rows = [
        classified
        for row_index, row in enumerate(rows)
        if (classified := _classify_structured_row(row, row_index)) is not None
    ]
    raw_tokens_by_row = [tokens for row in rows if (tokens := _raw_control_tokens_from_row(row))]
    tokens_by_row = [tokens for row in rows if (tokens := _lyric_tokens_from_control_row(row))]
    if not tokens_by_row:
        return None
    editorial_text: list[str] = []
    if len(raw_tokens_by_row) == 1 and _looks_like_editorial_tokens(raw_tokens_by_row[0]):
        editorial_text = [" ".join(raw_tokens_by_row[0]).strip()]
        return FT3TextRecord(
            melody_grid=None,
            lyrics=[],
            melody_events=[],
            lyric_event_rows=[],
            editorial_text=editorial_text,
            structured_rows=structured_rows,
            parse_mode="structured",
        )
    verse_rows = _structured_lyric_rows(tokens_by_row)
    melody_events = _structured_vocal_events(rows[0]) if rows else []
    lyric_lines = [" ".join(tokens).strip() for tokens in verse_rows if tokens]
    lyric_event_rows = []
    for verse, tokens in enumerate(verse_rows):
        events = _events_from_lyric_tokens(tokens, verse=verse)
        if events:
            lyric_event_rows.append(events)
    if not lyric_lines and not lyric_event_rows:
        return None
    return FT3TextRecord(
        melody_grid=None,
        lyrics=lyric_lines,
        melody_events=melody_events,
        lyric_event_rows=lyric_event_rows,
        editorial_text=[],
        structured_rows=structured_rows,
        parse_mode="structured",
    )


def _melody_events_from_line(line: str | None) -> list[MelodyEvent]:
    if not line:
        return []
    events: list[MelodyEvent] = []
    onset_idx = 0
    for pos, tok in _line_tokens_with_positions(line):
        cleaned = _clean_text_token(tok)
        if not cleaned:
            continue
        events.append(MelodyEvent(text=cleaned, onset_index=onset_idx, src_pos=pos))
        onset_idx += 1
    return events


def _lyric_events_from_line(line: str) -> list[LyricEvent]:
    events: list[LyricEvent] = []
    onset_idx = 0
    chain_open = False
    for pos, tok in _line_tokens_with_positions(line):
        raw = _clean_lyric_token(tok)
        if not raw:
            continue
        if set(raw) <= {"_", "-"} and "_" in raw:
            events.append(
                LyricEvent(
                    text="",
                    onset_index=onset_idx,
                    verse=0,
                    syllabic="single",
                    src_pos=pos,
                    extender=True,
                ),
            )
            onset_idx += 1
            continue
        trailing_hyphen = raw.endswith("-")
        text = raw.rstrip("-").strip()
        if not text and trailing_hyphen:
            text = "-"
        if not text:
            continue
        if text != "-" and not _keep_lyric_token(text):
            continue
        if trailing_hyphen and chain_open:
            syllabic = "middle"
        elif trailing_hyphen:
            syllabic = "begin"
        elif chain_open:
            syllabic = "end"
        else:
            syllabic = "single"
        events.append(
            LyricEvent(
                text=text,
                onset_index=onset_idx,
                verse=0,
                syllabic=syllabic,
                src_pos=pos,
                extender=False,
            ),
        )
        chain_open = trailing_hyphen
        onset_idx += 1
    return events


def parse_ft3_text_record(chunk: bytes) -> FT3TextRecord:
    tail = chunk[32:] if len(chunk) > 32 else chunk
    structured = _parse_structured_text_record(tail)
    if structured is not None:
        return structured
    lines = _asciiish_lines(tail)
    if not lines:
        return _empty_text_record()

    melody_candidates: list[str] = []
    lyrics: list[str] = []
    for raw in lines:
        melody, lyric = _classify_raw_line(raw)
        if melody:
            melody_candidates.append(melody)
        if lyric:
            lyrics.append(lyric)

    dedup_lyrics: list[str] = []
    lyric_event_rows: list[list[LyricEvent]] = []
    seen: set[str] = set()
    for line in lyrics:
        key = line.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        dedup_lyrics.append(line)
        lyric_events = _lyric_events_from_line(line)
        if lyric_events:
            lyric_event_rows.append(lyric_events)
    melody_line = _pick_melody_line(melody_candidates)
    melody_events = _melody_events_from_line(melody_line)
    return FT3TextRecord(
        melody_line,
        dedup_lyrics,
        melody_events=melody_events,
        lyric_event_rows=lyric_event_rows,
        editorial_text=[],
        structured_rows=[],
        parse_mode="ascii",
    )
