from __future__ import annotations

import copy
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

from oud.core.model import Bar, Chord, Note, Piece

FLAG_TO_NOTE_TYPE = {
    "W": 2,
    "w": 3,
    "B": 2,
    "L": 2,
    "0": 4,
    "1": 5,
    "2": 6,
    "3": 7,
    "4": 8,
    "5": 9,
    "6": 10,
}


@dataclass(slots=True)
class TabData:
    piece: Piece
    overrides: dict[tuple[int, int, int], str]
    durations: dict[tuple[int, int, int], int]
    dotted: set[tuple[int, int]]
    bar_width: int
    bar_line_spans: list[tuple[int, int]] = field(default_factory=list)
    source_lines: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TabParseDelta:
    data: TabData | None
    old_bar_range: tuple[int, int]
    new_bar_range: tuple[int, int]
    full_reparse: bool
    reason: str | None = None


@dataclass(slots=True)
class _BarSegmentParseResult:
    bars: list[Bar]
    spans: list[tuple[int, int]]


def _is_fret_char(ch: str) -> bool:
    return ch in "abcdefghiklmnopqrst" or ch.isdigit() or ch in {"x", "r", "E"}


def _fret_from_char(ch: str, prefer_alt_c: bool) -> int | None:
    letters = "abcdefghiklmnopqrst"
    if prefer_alt_c and ch == "r":
        return 2
    if ch in letters:
        return letters.index(ch)
    if ch.isdigit():
        return int(ch)
    return {"x": 10, "r": 2, "E": 4}.get(ch)


def _parse_time_signature(sig: str) -> str | None:
    if sig == "Sc":
        return "C"
    if sig == "Sc|":
        return "C|"
    if sig.startswith("S") and len(sig) >= 2:
        return sig[1:]
    return None


def _note_type_for_flag(flag: str, last: int | None) -> int | None:
    if flag == "x":
        return last
    return FLAG_TO_NOTE_TYPE.get(flag)


def _looks_like_hash_header(line: str) -> bool:
    text = line[1:].strip()
    if not text:
        return True
    if ":" in text:
        return True
    return text.startswith((" ", "\t"))


def _normalize_chord_line(line: str) -> str:
    if not line:
        return line
    if line[0] not in {"Y", "y"}:
        return line
    if len(line) == 1:
        return ""
    second = line[1]
    if second in ".bB":
        return ""
    if second in {"#", "x", "w", "W", "B", "L"} or second.isdigit():
        return line[1:]
    return f"0{line[1:]}"


def _parse_chord_line(  # noqa: C901
    line: str, strings: int, last_note_type: int | None,
) -> tuple[Chord | None, int | None]:
    text = _normalize_chord_line(line)
    if not text:
        return None, last_note_type
    idx = 0
    grid = None
    if text.startswith("#"):
        grid = "start"
        idx += 1
        if idx >= len(text):
            return None, last_note_type
    flag = text[idx]
    if flag.isspace():
        return None, last_note_type
    dotted = False
    rest = text[idx + 1:]
    if rest.startswith("!"):
        rest = rest[1:]
    if rest.startswith("."):
        dotted = True
        rest = rest[1:]
    if rest.startswith("#"):
        grid = "start"
        rest = rest[1:]
    note_type = _note_type_for_flag(flag, last_note_type)
    if note_type is None:
        return None, last_note_type

    text = rest.rstrip("\n")
    if len(text) < strings:
        text = text.ljust(strings)
    prefer_alt_c = not any(ch in text for ch in "qst")

    chord = Chord(note_type=note_type, dotted=dotted, grid=grid)
    for idx, ch in enumerate(text[:strings]):
        if _is_fret_char(ch):
            fret = _fret_from_char(ch, prefer_alt_c)
            if fret is None:
                continue
            note = Note(string=idx + 1, fret=fret, raw_pos=0)
            chord.notes.append(note)
    return chord, note_type


def _apply_title_block(piece: Piece, text: str) -> None:
    if "/" in text and not piece.title and not piece.composer:
        title, composer = text.split("/", 1)
        title = title.strip()
        composer = composer.strip()
        if title:
            piece.title = title
        if composer:
            piece.composer = composer
        return
    if not piece.title:
        piece.title = text
    elif not piece.author:
        piece.author = text


def _finalize_current_bar(
    piece: Piece,
    current_bar: Bar,
    *,
    span_start: int | None,
    span_end: int | None,
    bar_line_spans: list[tuple[int, int]],
) -> None:
    if current_bar.chords or current_bar.notes:
        piece.bars.append(current_bar)
        if span_start is not None and span_end is not None:
            bar_line_spans.append((span_start, span_end))


def _bar_range_for_line_span(
    spans: list[tuple[int, int]],
    start_line: int,
    end_line: int,
) -> tuple[int, int]:
    if not spans:
        return (0, 0)
    lo = min(start_line, end_line)
    hi = max(start_line, end_line)
    first: int | None = None
    last: int | None = None
    for idx, (span_start, span_end) in enumerate(spans):
        if span_end < lo or span_start > hi:
            continue
        if first is None:
            first = idx
        last = idx
    if first is None or last is None:
        return (0, 0)
    return (first, last + 1)


def _bar_range_or_empty(
    data: TabData | None,
    *,
    changed_line_start: int,
    changed_line_end: int,
) -> tuple[int, int]:
    if data is None:
        return (0, 0)
    return _bar_range_for_line_span(
        data.bar_line_spans,
        changed_line_start,
        changed_line_end,
    )


def _first_bar_start(spans: list[tuple[int, int]]) -> int | None:
    return spans[0][0] if spans else None


def _tab_delta_reason(
    previous: TabData,
    *,
    changed_line_start: int,
    changed_line_end: int,
) -> str | None:
    first_bar_line = _first_bar_start(previous.bar_line_spans)
    if first_bar_line is None:
        return "no_bars"
    if min(changed_line_start, changed_line_end) < first_bar_line:
        return "header_or_metadata_change"
    return None


def _line_slice_has_structural_change(lines: list[str], start: int, end: int) -> bool:
    lo = min(start, end)
    hi = max(start, end)
    for idx in range(lo, hi + 1):
        if 0 <= idx < len(lines) and _is_structural_tab_line(lines[idx]):
            return True
    return False


def _full_reparse_delta(
    new_text: str,
    *,
    strings: int,
    old_bar_range: tuple[int, int],
    new_changed_start: int,
    new_changed_end: int,
    full_reason: str,
) -> TabParseDelta:
    new_data = parse_tab_text_data(new_text, strings=strings)
    return TabParseDelta(
        data=new_data,
        old_bar_range=old_bar_range,
        new_bar_range=_bar_range_or_empty(
            new_data,
            changed_line_start=new_changed_start,
            changed_line_end=new_changed_end,
        ),
        full_reparse=True,
        reason=full_reason,
    )


def _is_structural_tab_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    return line.startswith(("{", "#", "$", "-", "%", "b", "S")) or stripped == "e"


def _last_note_type_from_bar(bar: Bar) -> int | None:
    if not bar.chords:
        return None
    return bar.chords[-1].note_type


def _parse_bar_segment_lines(  # noqa: C901
    lines: list[str],
    *,
    start_line_no: int,
    strings: int,
    default_time: str | None,
    last_note_type: int | None,
) -> _BarSegmentParseResult | None:
    bars: list[Bar] = []
    spans: list[tuple[int, int]] = []
    current_bar = Bar(time_sig=default_time)
    current_span_start: int | None = None
    current_span_end: int | None = None
    local_last_note_type = last_note_type

    def _finalize() -> None:
        if current_bar.chords or current_bar.notes:
            bars.append(current_bar)
            if current_span_start is not None and current_span_end is not None:
                spans.append((current_span_start, current_span_end))

    for offset, raw in enumerate(lines):
        line_no = start_line_no + offset
        line = raw.rstrip("\n").rstrip("\r")
        if not line:
            continue
        if line.startswith(("{", "#", "$")):
            # Segment reparse intentionally avoids metadata/header semantics.
            return None
        if line.startswith(("-", "%")):
            continue
        if line.startswith("b"):
            _finalize()
            current_bar = Bar(time_sig=default_time)
            current_span_start = None
            current_span_end = None
            continue
        if line.startswith("S"):
            current_bar.time_sig = _parse_time_signature(line.strip())
            if current_span_start is None:
                current_span_start = line_no
            current_span_end = line_no
            continue
        if line.strip() == "e":
            _finalize()
            current_bar = Bar(time_sig=default_time)
            current_span_start = None
            current_span_end = None
            local_last_note_type = None
            continue
        chord, local_last_note_type = _parse_chord_line(line, strings, local_last_note_type)
        if chord and chord.notes:
            current_bar.chords.append(chord)
            current_bar.notes.extend(chord.notes)
            if current_span_start is None:
                current_span_start = line_no
            current_span_end = line_no
    _finalize()
    return _BarSegmentParseResult(bars=bars, spans=spans)


def parse_tab_text_data(text: str, strings: int = 6) -> TabData | None:
    return parse_tab_lines_data(text.splitlines(), strings=strings)


def parse_tab_lines_data(lines: list[str], strings: int = 6) -> TabData | None:  # noqa: PLR0912, C901
    # Format cues inspired by luteconv tab parsing.
    piece = Piece(title=None, author=None, composer=None, bars=[], strings=strings)
    current_bar = Bar()
    last_note_type: int | None = None
    saw_letters = False
    saw_digits = False
    default_time: str | None = None
    bar_line_spans: list[tuple[int, int]] = []
    current_bar_span_start: int | None = None
    current_bar_span_end: int | None = None
    for line_no, raw in enumerate(lines):
        line = raw.rstrip("\n").rstrip("\r")
        if not line:
            continue
        if line.startswith("{") and line.endswith("}"):
            title_text = line.strip("{}").strip()
            _apply_title_block(piece, title_text)
            continue
        if line.startswith("#") and _looks_like_hash_header(line):
            header = line[1:].strip()
            if header.lower().startswith("tuning:"):
                piece.tuning = header.split(":", 1)[1].strip()
            elif header.lower().startswith(("time:", "timesig:", "meter:")):
                value = header.split(":", 1)[1].strip()
                parsed = _parse_time_signature(value)
                default_time = parsed
                if current_bar.time_sig is None and parsed:
                    current_bar.time_sig = parsed
            elif header.lower().startswith("subtitle:"):
                piece.subtitle = header.split(":", 1)[1].strip()
            elif header.lower().startswith("footnote:"):
                piece.footnote = header.split(":", 1)[1].strip()
            continue
        if line.startswith("$"):
            header = line[1:].strip()
            if header.lower().startswith(("time=", "timesig=", "meter=")):
                value = header.split("=", 1)[1].strip()
                parsed = _parse_time_signature(value)
                default_time = parsed
                if current_bar.time_sig is None and parsed:
                    current_bar.time_sig = parsed
            continue
        if line.startswith("-tuning "):
            piece.tuning = line.split(" ", 1)[1].strip()
            continue
        if line.startswith("-"):
            continue
        if line.startswith("%"):
            continue
        if line.startswith("b"):
            _finalize_current_bar(
                piece,
                current_bar,
                span_start=current_bar_span_start,
                span_end=current_bar_span_end,
                bar_line_spans=bar_line_spans,
            )
            current_bar = Bar(time_sig=default_time)
            current_bar_span_start = None
            current_bar_span_end = None
            continue
        if line.startswith("S"):
            current_bar.time_sig = _parse_time_signature(line.strip())
            if current_bar_span_start is None:
                current_bar_span_start = line_no
            current_bar_span_end = line_no
            continue
        if line.strip() == "e":
            _finalize_current_bar(
                piece,
                current_bar,
                span_start=current_bar_span_start,
                span_end=current_bar_span_end,
                bar_line_spans=bar_line_spans,
            )
            current_bar = Bar(time_sig=default_time)
            current_bar_span_start = None
            current_bar_span_end = None
            last_note_type = None
            continue
        chord, last_note_type = _parse_chord_line(line, strings, last_note_type)
        if chord and chord.notes:
            current_bar.chords.append(chord)
            current_bar.notes.extend(chord.notes)
            if current_bar_span_start is None:
                current_bar_span_start = line_no
            current_bar_span_end = line_no
            for ch in line[1:]:
                if "a" <= ch <= "p":
                    saw_letters = True
                elif ch.isdigit() or ch == "x":
                    saw_digits = True
    _finalize_current_bar(
        piece,
        current_bar,
        span_start=current_bar_span_start,
        span_end=current_bar_span_end,
        bar_line_spans=bar_line_spans,
    )
    if saw_letters:
        piece.style = "french"
    elif saw_digits:
        piece.style = "italian"
    if not piece.bars and not piece.title and not piece.author and not piece.composer:
        return None
    return TabData(
        piece=piece,
        overrides={},
        durations={},
        dotted=set(),
        bar_width=0,
        bar_line_spans=bar_line_spans,
        source_lines=list(lines),
    )


def load_tab_data(path: str, strings: int = 6) -> TabData | None:
    with Path(path).open(encoding="utf-8", errors="ignore") as f:
        return parse_tab_lines_data(list(f), strings=strings)


def load_tab(path: str, strings: int = 6) -> Piece:
    data = load_tab_data(path, strings=strings)
    if data is None:
        return Piece(title=None, author=None, composer=None, bars=[], strings=strings)
    return data.piece


def reparse_tab_text_delta(
    previous: TabData,
    new_text: str,
    *,
    changed_line_start: int,
    changed_line_end: int,
    old_changed_line_start: int | None = None,
    old_changed_line_end: int | None = None,
    strings: int | None = None,
) -> TabParseDelta:
    """Return a stable bar-range delta for editor-driven TAB text reparses.

    Current implementation still performs a full parse for correctness,
    but exposes affected bar ranges and fallback reasons so callers can be
    written against a stable incremental-parse interface.
    """

    strings = strings or previous.piece.strings
    new_lines = new_text.splitlines()
    old_lines = previous.source_lines or []
    old_changed_start = (
        changed_line_start if old_changed_line_start is None else old_changed_line_start
    )
    old_changed_end = changed_line_end if old_changed_line_end is None else old_changed_line_end
    old_range = _bar_range_for_line_span(
        previous.bar_line_spans,
        old_changed_start,
        old_changed_end,
    )
    reason = _tab_delta_reason(
        previous,
        changed_line_start=old_changed_start,
        changed_line_end=old_changed_end,
    )
    if reason is not None:
        return _full_reparse_delta(
            new_text,
            strings=strings,
            old_bar_range=old_range,
            new_changed_start=changed_line_start,
            new_changed_end=changed_line_end,
            full_reason=reason,
        )

    if len(new_lines) != len(old_lines):
        return _full_reparse_delta(
            new_text,
            strings=strings,
            old_bar_range=old_range,
            new_changed_start=changed_line_start,
            new_changed_end=changed_line_end,
            full_reason="line_count_changed",
        )

    if _line_slice_has_structural_change(old_lines, old_changed_start, old_changed_end) or (
        _line_slice_has_structural_change(new_lines, changed_line_start, changed_line_end)
    ):
        return _full_reparse_delta(
            new_text,
            strings=strings,
            old_bar_range=old_range,
            new_changed_start=changed_line_start,
            new_changed_end=changed_line_end,
            full_reason="structural_change",
        )

    if old_range == (0, 0):
        return _full_reparse_delta(
            new_text,
            strings=strings,
            old_bar_range=old_range,
            new_changed_start=changed_line_start,
            new_changed_end=changed_line_end,
            full_reason="no_bar_overlap",
        )

    ctx_start = max(0, old_range[0] - 1)
    ctx_end = old_range[1]
    seg_start_line = previous.bar_line_spans[ctx_start][0]
    seg_end_line = previous.bar_line_spans[ctx_end - 1][1]
    seg_lines = new_lines[seg_start_line : seg_end_line + 1]
    seed_default_time = previous.piece.bars[ctx_start - 1].time_sig if ctx_start > 0 else None
    seed_last_note_type = (
        _last_note_type_from_bar(previous.piece.bars[ctx_start - 1]) if ctx_start > 0 else None
    )
    seg = _parse_bar_segment_lines(
        seg_lines,
        start_line_no=seg_start_line,
        strings=strings,
        default_time=seed_default_time,
        last_note_type=seed_last_note_type,
    )
    expected_seg_bars = ctx_end - ctx_start
    if seg is None or len(seg.bars) != expected_seg_bars:
        new_data = parse_tab_text_data(new_text, strings=strings)
        new_range = (
            _bar_range_for_line_span(new_data.bar_line_spans, changed_line_start, changed_line_end)
            if new_data is not None
            else (0, 0)
        )
        return TabParseDelta(
            data=new_data,
            old_bar_range=old_range,
            new_bar_range=new_range,
            full_reparse=True,
            reason="segment_parse_fallback",
        )

    new_piece = copy.deepcopy(previous.piece)
    new_piece.bars[ctx_start:ctx_end] = seg.bars
    new_spans = list(previous.bar_line_spans)
    new_spans[ctx_start:ctx_end] = seg.spans
    new_data = TabData(
        piece=new_piece,
        overrides=dict(previous.overrides),
        durations=dict(previous.durations),
        dotted=set(previous.dotted),
        bar_width=previous.bar_width,
        bar_line_spans=new_spans,
        source_lines=new_lines,
    )
    new_range = _bar_range_for_line_span(
        new_spans,
        changed_line_start,
        changed_line_end,
    )
    return TabParseDelta(
        data=new_data,
        old_bar_range=old_range,
        new_bar_range=new_range,
        full_reparse=False,
        reason=None,
    )


def reparse_tab_text_auto_delta(
    previous: TabData,
    new_text: str,
    *,
    strings: int | None = None,
) -> TabParseDelta:
    old_lines = previous.source_lines or []
    new_lines = new_text.splitlines()
    if old_lines == new_lines:
        return TabParseDelta(
            data=TabData(
                piece=copy.deepcopy(previous.piece),
                overrides=dict(previous.overrides),
                durations=dict(previous.durations),
                dotted=set(previous.dotted),
                bar_width=previous.bar_width,
                bar_line_spans=list(previous.bar_line_spans),
                source_lines=list(previous.source_lines),
            ),
            old_bar_range=(0, 0),
            new_bar_range=(0, 0),
            full_reparse=False,
            reason="no_change",
        )
    matcher = SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    opcodes = [op for op in matcher.get_opcodes() if op[0] != "equal"]
    if not opcodes:
        return reparse_tab_text_delta(
            previous,
            new_text,
            changed_line_start=0,
            changed_line_end=0,
            strings=strings,
        )
    old_start = min(op[1] for op in opcodes)
    old_end_excl = max(op[2] for op in opcodes)
    new_start = min(op[3] for op in opcodes)
    new_end_excl = max(op[4] for op in opcodes)
    return reparse_tab_text_delta(
        previous,
        new_text,
        changed_line_start=new_start,
        changed_line_end=max(new_start, new_end_excl - 1),
        old_changed_line_start=old_start,
        old_changed_line_end=max(old_start, old_end_excl - 1),
        strings=strings,
    )
