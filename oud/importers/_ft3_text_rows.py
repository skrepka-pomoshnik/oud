from __future__ import annotations

import re
from dataclasses import dataclass, replace

from oud.importers._ft3_note_records import (
    _structured_vocal_events,
)
from oud.importers._ft3_text_types import FT3TextRecord, empty_text_record
from petrucci.model import ImportedTextRow, LyricEvent


def _empty_text_record() -> FT3TextRecord:
    return empty_text_record()


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
LYRIC_WEIRD_CHARS = set('@?><=|[]{}?!"')
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
    letter_count = sum(1 for b in tail if (0x41 <= b <= 0x5A) or (0x61 <= b <= 0x7A))
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
    return _features_look_like_melody(features)


def _features_look_like_melody(features: _LineFeatures) -> bool:
    if not features.has_text or len(features.stripped) < 3:
        return False
    digit_or_symbol = features.digits + features.symbols + features.placeholders + features.alpha
    enough_symbols = digit_or_symbol >= max(3, features.length // 3)
    low_alpha = features.alpha <= max(4, features.length // 5)
    has_melody_tokens = features.digits > 0 or (features.symbols + features.placeholders) >= 2
    return has_melody_tokens and enough_symbols and (digit_or_symbol >= 3 or low_alpha)


def _looks_like_lyric_text(line: str) -> bool:
    features = _line_features(line)
    return _features_look_like_lyrics(features)


def _features_look_like_lyrics(features: _LineFeatures) -> bool:
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


def _split_wide_gap(line: str) -> tuple[str, str] | None:  # noqa: C901
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
        if _features_look_like_melody(left_features):
            score += 10 + _score_kind(left_features, MELODY_SCORE_RULES)
        if _features_look_like_lyrics(right_features):
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


def _classify_raw_line(raw: str) -> tuple[str | None, str | None]:  # noqa: C901
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


def _trim_leading_single_letter_lyric_noise(tokens: list[str]) -> list[str]:
    trimmed = list(tokens)
    while len(trimmed) > 1 and len(trimmed[0]) == 1 and trimmed[0].islower() and trimmed[0] not in {"i", "o"}:
        trimmed = trimmed[1:]
    return trimmed


def _trim_leading_single_letter_positioned_noise(
    tokens: list[tuple[int, str]],
) -> list[tuple[int, str]]:
    trimmed = list(tokens)
    while len(trimmed) > 1 and len(trimmed[0][1]) == 1 and trimmed[0][1].islower():
        trimmed = trimmed[1:]
    return trimmed


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


def _tokenize_control_row(row: bytes) -> list[tuple[int, str]]:  # noqa: C901
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
    if token.isupper() and 1 < len(token) <= 3:
        return True
    if all(ch.isdigit() or ch == "." for ch in lower):
        return True
    if re.fullmatch(r"[a-gh](?:[#b]|[',])*", lower) and not (len(lower) == 1 and lower in {"i", "a", "o"}):
        return True
    if lower in {"times", "new", "roman", "timesnewroman"}:
        return True
    return bool(any(ch in '@?><=|[]{}!";:' for ch in token))


def _lyric_tokens_from_control_row(row: bytes) -> list[str]:  # noqa: C901
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
    out = _trim_leading_single_letter_lyric_noise(out)
    if out:
        if " ".join(tok.lower() for tok in out) in {"times new roman", "new roman"}:
            return []
        return out
    fallback = [
        tok for tok in tokens if (_keep_lyric_token(tok) or set(tok) <= {"_"}) and not _likely_non_lyric_token(tok)
    ]
    fallback = _trim_leading_single_letter_lyric_noise(fallback)
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
    return compact in {"timesnewroman", "newroman", "}"} or compact.startswith(r"{\rtf") or r"\fonttbl" in compact


def _normalized_legacy_lyric_text(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[:;<>=\"?@]+", "", text)).strip()


def _fallback_lyric_tokens_from_text(text: str) -> list[str]:
    normalized = _normalized_legacy_lyric_text(text)
    if not normalized:
        return []
    if re.fullmatch(r"[-_]+", normalized):
        return ["_"]
    if not any(ch.isalpha() for ch in normalized):
        return []
    tokens = [tok for tok in normalized.split() if tok]
    if not tokens:
        return []
    return [
        tok
        for tok in tokens
        if (any(ch.isalpha() for ch in tok) or set(tok) <= {"_"})
        and (set(tok) <= {"_"} or (_keep_lyric_token(tok) and not _likely_non_lyric_token(tok)))
    ]


def _looks_like_control_text(text: str, raw_tokens: list[str]) -> bool:
    compact = re.sub(r"\s+", "", text)
    if not compact:
        return False
    if set(compact) <= {"?", "@", "-", "_"}:
        return True
    alpha = sum(ch.isalpha() for ch in compact)
    digits = sum(ch.isdigit() for ch in compact)
    punct = sum(not ch.isalnum() for ch in compact)
    if digits and alpha == 0:
        return True
    return bool(raw_tokens and alpha <= 1 and digits >= 1 and punct >= 1)


def _vocal_text_tokens(raw_tokens: list[str]) -> list[str]:
    return [tok for tok in raw_tokens if not _likely_non_lyric_token(tok)]


def _classify_structured_row(row: bytes, row_index: int) -> ImportedTextRow | None:  # noqa: C901
    text = _structured_row_text(row)
    raw_tokens = _raw_control_tokens_from_row(row)
    lyric_tokens = _lyric_tokens_from_control_row(row)
    fallback_lyric_tokens = _fallback_lyric_tokens_from_text(text)
    if not text and not raw_tokens and not lyric_tokens:
        return None
    kind = "unknown"
    row_text = text
    row_tokens = raw_tokens
    if row_index == 0 and _structured_vocal_events(row):
        kind = "vocal"
        row_tokens = _vocal_text_tokens(raw_tokens)
    elif raw_tokens and _looks_like_editorial_tokens(raw_tokens):
        kind = "editorial"
        row_text = " ".join(raw_tokens).strip()
    elif _is_font_noise_text(text):
        kind = "font"
    elif lyric_tokens:
        kind = "lyrics"
        row_tokens = lyric_tokens
    elif fallback_lyric_tokens:
        kind = "lyrics"
        row_text = _normalized_legacy_lyric_text(text)
        row_tokens = fallback_lyric_tokens
    elif _looks_like_control_text(text, raw_tokens):
        kind = "control"
    return ImportedTextRow(row_index=row_index, kind=kind, text=row_text, tokens=row_tokens)


def _events_from_lyric_tokens(tokens: list[str], *, verse: int) -> list[LyricEvent]:  # noqa: C901
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


def _cluster_lyric_lanes(
    positioned_rows: list[list[tuple[int, str]]],
    *,
    tolerance: int = 3,
) -> list[list[str]]:
    lane_positions: list[int] = []
    for row in positioned_rows:
        for pos, _tok in row:
            if any(abs(pos - existing) <= tolerance for existing in lane_positions):
                continue
            lane_positions.append(pos)
    if len(lane_positions) <= 1:
        return []
    lane_positions.sort(reverse=True)
    lane_rows: list[list[str]] = [[] for _ in lane_positions]
    for row in positioned_rows:
        for pos, tok in row:
            lane_idx = min(
                range(len(lane_positions)),
                key=lambda idx: abs(pos - lane_positions[idx]),
            )
            lane_rows[lane_idx].append(tok)
    return [row for row in lane_rows if row]


def _structured_lyric_rows_from_positioned_rows(
    positioned_rows: list[list[tuple[int, str]]],
    *,
    prefer_cluster: bool = False,
) -> list[list[str]]:
    if not positioned_rows:
        return []
    token_counts = [len(row) for row in positioned_rows]
    mostly_singletons = sum(count == 1 for count in token_counts) >= max(3, len(token_counts) - 1)
    lane_rows = _cluster_lyric_lanes(
        positioned_rows,
        tolerance=6 if prefer_cluster else 3,
    )
    if prefer_cluster and len(lane_rows) >= 2:
        return lane_rows
    if len(positioned_rows) >= 4 and mostly_singletons and (not prefer_cluster or len(lane_rows) < 3):
        return [[tok for _pos, tok in row] for row in positioned_rows if row]
    if lane_rows:
        return lane_rows
    return _structured_lyric_rows([[tok for _pos, tok in row] for row in positioned_rows])


def _filtered_structured_lyric_tokens(tokens: list[str]) -> list[str]:
    out: list[str] = []
    for tok in tokens:
        if not tok:
            continue
        if set(tok) <= {"_"}:
            out.append(tok)
            continue
        if _keep_lyric_token(tok) and not _likely_non_lyric_token(tok):
            out.append(tok)
    return out


def _filtered_positioned_lyric_tokens(row: bytes) -> list[tuple[int, str]]:
    tokens: list[tuple[int, str]] = []
    for pos, tok in _tokenize_control_row(row):
        cleaned = _clean_lyric_token(tok)
        if cleaned:
            tokens.append((pos, cleaned))
    if not tokens:
        return []
    last_non_lyric = -1
    for idx, (_pos, tok) in enumerate(tokens):
        if (_likely_non_lyric_token(tok) or not _keep_lyric_token(tok)) and set(tok) != {"_"}:
            last_non_lyric = idx
    filtered = [
        (pos, tok)
        for pos, tok in tokens[last_non_lyric + 1 :]
        if set(tok) <= {"_"} or (_keep_lyric_token(tok) and not _likely_non_lyric_token(tok))
    ]
    if filtered:
        return filtered
    return [
        (pos, tok)
        for pos, tok in tokens
        if set(tok) <= {"_"} or (_keep_lyric_token(tok) and not _likely_non_lyric_token(tok))
    ]


def _structured_positioned_lyric_rows(
    tail: bytes,
) -> list[list[tuple[int, str]]]:
    rows = _split_record_rows(tail)
    classified_rows = [
        (row, classified)
        for row_index, row in enumerate(rows)
        if (classified := _classify_structured_row(row, row_index)) is not None
    ]
    positioned_tokens_by_row: list[list[tuple[int, str]]] = []
    for row, classified in classified_rows:
        if classified.kind not in {"vocal", "lyrics"}:
            continue
        filtered = _filtered_positioned_lyric_tokens(row)
        filtered = _trim_leading_single_letter_positioned_noise(filtered)
        if filtered:
            positioned_tokens_by_row.append(filtered)
    return positioned_tokens_by_row


def _record_with_verse_rows(record: FT3TextRecord, verse_rows: list[list[str]]) -> FT3TextRecord:
    normalized_rows = [_collapse_consecutive_duplicate_tokens(tokens) for tokens in verse_rows]
    lyric_lines = [" ".join(tokens).strip() for tokens in normalized_rows if tokens]
    lyric_event_rows: list[list[LyricEvent]] = []
    for verse, tokens in enumerate(normalized_rows):
        events = _events_from_lyric_tokens(tokens, verse=verse)
        if events:
            lyric_event_rows.append(events)
    if not lyric_lines and not lyric_event_rows:
        return record
    return replace(record, lyrics=lyric_lines, lyric_event_rows=lyric_event_rows)


def _coalesce_raw_multi_verse_rows(  # noqa: C901
    verse_rows: list[list[str]],
    *,
    melody_event_count: int,
) -> list[list[str]]:
    if len(verse_rows) <= 2 or melody_event_count <= 1:
        return verse_rows
    lead_rows = 0
    for row in verse_rows:
        if len(row) != 1 or lead_rows >= melody_event_count:
            break
        lead_rows += 1
    if lead_rows < 2:
        return verse_rows
    primary: list[str] = []
    for row in verse_rows[:lead_rows]:
        primary.extend(row)
    secondary: list[str] = []
    for row in verse_rows[lead_rows:]:
        secondary.extend(row)
    out = [primary]
    if secondary:
        out.append(secondary)
    return out


def _reconstruct_three_verse_raw_rows(
    positioned_rows: list[list[tuple[int, str]]],
    *,
    melody_event_count: int,
) -> list[list[str]] | None:
    if melody_event_count < 1 or len(positioned_rows) < 3 or not positioned_rows[0]:
        return None
    lyric_tokens = [tok for row in positioned_rows[1:] for _pos, tok in row]
    invalid_shape = len(lyric_tokens) < 2 or any(len(row) > 2 for row in positioned_rows[1:])
    if invalid_shape:
        return None
    primary = [tok for _pos, tok in positioned_rows[0]]
    if not primary:
        return None
    verse_two: list[str] = []
    verse_three: list[str] = []
    cycle = [verse_two, verse_three, primary]
    cycle_index = 0
    for row in positioned_rows[1:]:
        for _pos, tok in row:
            cycle[cycle_index].append(tok)
            cycle_index = (cycle_index + 1) % len(cycle)
    rows = [primary, verse_two, verse_three]
    return rows if sum(1 for row in rows if row) >= 3 else None


def _collapse_consecutive_duplicate_tokens(tokens: list[str]) -> list[str]:
    out: list[str] = []
    for token in tokens:
        if out and out[-1].lower() == token.lower():
            continue
        out.append(token)
    return out


def _looks_like_editorial_tokens(tokens: list[str]) -> bool:
    if len(tokens) < 3:
        return False
    joined = " ".join(tokens)
    alpha = sum(ch.isalpha() for ch in joined)
    long_tokens = sum(len(tok) >= 4 for tok in tokens)
    pitch_like = sum(bool(re.fullmatch(r"[a-gh](?:[#b]|[',])*", tok.lower())) for tok in tokens)
    has_prose_punct = any(ch in joined for ch in ":;(),./")
    return alpha >= 10 and long_tokens >= 2 and pitch_like == 0 and (has_prose_punct or len(tokens) >= 4)
