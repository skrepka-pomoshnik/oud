from __future__ import annotations

import copy
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

from oud.importers.tab_syntax import (
    ITALIAN_SETTING,
    MILAN_OPTION,
    OUD_HEADER,
    WRITTEN_HEADER,
    TabDialect,
    TabSyntax,
    detect_syntax,
    position_notes,
    read_positions,
    read_time_signature,
    read_tuning,
    split_flag,
)
from petrucci.core.model import Bar, Chord, Piece, SourceText

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

TAB_EMPTY_WARNING = "TAB import found no recoverable bars; opened a blank score instead."
TAB_INCOMPLETE_WARNING = "TAB appears incomplete (missing final 'e'); recovered {bars} bar(s)."
TAB_TRIPLET_WARNING = (
    "TAB triplets are read without tuplet timing ({count} group(s)); bar lengths may not match the meter."
)
_THICK_BARLINES = frozenset({"B", "B!", "BX", "BL"})


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


@dataclass(slots=True, frozen=True)
class _ChordLineParts:
    flag: str
    fret_text: str
    dotted: bool
    grid: str | None
    triplet: bool = False
    rest: bool = False


@dataclass(slots=True)
class _BarAccumulator:
    syntax: TabSyntax
    default_time: str | None = None
    last_note_type: int | None = None
    bars: list[Bar] = field(default_factory=list)
    spans: list[tuple[int, int]] = field(default_factory=list)
    current_bar: Bar = field(init=False)
    span_start: int | None = None
    span_end: int | None = None
    triplets: int = 0

    def __post_init__(self) -> None:
        self.current_bar = Bar(time_sig=self.default_time)

    @property
    def keeps_source(self) -> bool:
        # Oud's earlier dialect is regenerated on save; only the program's syntax is kept verbatim.
        return self.syntax.dialect is TabDialect.ORIGINAL

    def carry(self, line: str) -> None:
        """Keep a line the model does not represent, before the next event of the current bar."""

        self._source().lines.append((len(self.current_bar.chords), line))

    def _source(self) -> SourceText:
        if self.current_bar.source is None:
            self.current_bar.source = SourceText()
        return self.current_bar.source

    def set_default_time(self, value: str | None) -> None:
        self.default_time = value
        if self.current_bar.time_sig is None and value:
            self.current_bar.time_sig = value

    def set_time_signature(self, line: str, line_no: int) -> None:
        self.current_bar.time_sig = read_time_signature(line, self.syntax)
        if self.keeps_source:
            self._source().meter = line
        self._include_line(line_no)

    def add_chord(self, line: str, line_no: int) -> bool:
        parts = _chord_line_parts(line, self.syntax)
        chord, self.last_note_type = _parse_chord_line(parts, self.syntax, self.last_note_type)
        # A flag over an empty column is a rest; keep it so later onsets keep their time.
        if chord is None:
            return False
        self.triplets += bool(parts and parts.triplet)
        # Italian Milan order is not what Oud writes, so such lines are regenerated.
        if self.keeps_source and not self.syntax.milan:
            chord.source_text = line
        self.current_bar.chords.append(chord)
        self.current_bar.notes.extend(chord.notes)
        self._include_line(line_no)
        return True

    def break_bar(self, *, reset_note_type: bool = False, barline: str | None = None) -> None:
        if barline is not None and barline.strip() != "b" and self.keeps_source and self.span_start is not None:
            self._source().barline = barline
        self._finalize_current_bar()
        self.current_bar = Bar(time_sig=self.default_time)
        self.span_start = None
        self.span_end = None
        if reset_note_type:
            self.last_note_type = None

    def finish(self) -> None:
        self._finalize_current_bar()

    def mark_system_break(self) -> None:
        if self.span_start is not None:
            self.current_bar.system_break = True
        elif self.bars:
            self.bars[-1].system_break = True

    def _include_line(self, line_no: int) -> None:
        if self.span_start is None:
            self.span_start = line_no
        self.span_end = line_no

    def _finalize_current_bar(self) -> None:
        # A bar is a measure when it has chords or an explicit line such as `Sc`
        # (Oud writes one per bar, so empty measures round-trip). Bare `b` lines
        # alone are barline layout and create no bar.
        if self.span_start is None:
            self._hand_back_carried_lines()
            return
        self.bars.append(self.current_bar)
        if self.span_start is not None and self.span_end is not None:
            self.spans.append((self.span_start, self.span_end))

    def _hand_back_carried_lines(self) -> None:
        # Lines between a closing barline and the next bar's content belong
        # after the previous bar's barline when no bar follows.
        source = self.current_bar.source
        if source is None or not source.lines or not self.bars:
            return
        previous = self.bars[-1]
        if previous.source is None:
            previous.source = SourceText()
        after_barline = len(previous.chords) + 1
        previous.source.lines.extend((after_barline, line) for _index, line in source.lines)


def _parse_time_signature(sig: str) -> str | None:
    minimum_time_signature_length = 2
    if sig == "Sc":
        return "C"
    if sig == "Sc|":
        return "C|"
    if sig.startswith("S") and len(sig) >= minimum_time_signature_length:
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


def is_barline(line: str) -> bool:
    """`b` lines, a thick `B` on its own, and repeat dots around a barline (`.bb.`)."""

    stripped = line.rstrip()
    if stripped.startswith("b") or stripped in _THICK_BARLINES:
        return True
    return stripped.startswith(".") and any(char in "bB" for char in stripped)


def _chord_line_parts(line: str, syntax: TabSyntax) -> _ChordLineParts | None:
    text = _normalize_chord_line(line).rstrip("\n")
    if not text:
        return None
    lead = text[0]
    if lead == "R":
        return _ChordLineParts(text[1:2] or "1", "", text[2:3] == ".", None, rest=True)
    if lead in "#t" and len(text) > 1:
        return _ChordLineParts(text[1], text[2:], False, "start" if lead == "#" else None, triplet=lead == "t")
    if lead == "B":
        return _ChordLineParts("B", text[1:].removeprefix("-"), False, None)
    modifier = split_flag(text[1:], syntax)
    if syntax.dialect is TabDialect.OUD_LEGACY and not modifier.text[:1].strip():
        return None
    return _ChordLineParts(lead, modifier.text, modifier.dotted, "start" if modifier.grid else None)


def _parse_chord_line(
    parts: _ChordLineParts | None,
    syntax: TabSyntax,
    last_note_type: int | None,
) -> tuple[Chord | None, int | None]:
    if parts is None:
        return None, last_note_type
    note_type = _note_type_for_flag(parts.flag, last_note_type)
    if note_type is None:
        return None, last_note_type
    chord = Chord(note_type=note_type, dotted=parts.dotted, grid=parts.grid)
    positions = read_positions(parts.fret_text, syntax)
    if not parts.rest and not positions.rest:
        chord.notes.extend(position_notes(positions, syntax))
    return chord, note_type


def decode_chord_line(line: str, syntax: TabSyntax, last_note_type: int | None) -> Chord | None:
    """The chord one line gives, as the reader would read it after a chord of ``last_note_type``."""

    chord, _note_type = _parse_chord_line(_chord_line_parts(line, syntax), syntax, last_note_type)
    return chord


def _apply_title_block(piece: Piece, text: str) -> bool:
    """Fill title, composer or author from a `{…}` block; ``False`` when all were already set."""

    if "/" in text and not piece.title and not piece.composer:
        title, composer = text.split("/", 1)
        piece.title = title.strip() or None
        piece.composer = composer.strip() or None
        return True
    if not piece.title:
        piece.title = text
        return True
    if not piece.author:
        piece.author = text
        return True
    return False


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
    return any(0 <= idx < len(lines) and _is_structural_tab_line(lines[idx]) for idx in range(lo, hi + 1))


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


def _segment_line_kind(line: str) -> str:
    stripped = line.strip()
    return next(
        (
            kind
            for kind, matches in (
                ("blank", not line),
                ("invalid", line.startswith(("{", "#", "$"))),
                ("ignore", line.startswith(("-", "%"))),
                ("bar", is_barline(line)),
                ("time", line.startswith("S")),
                ("end", stripped == "e"),
            )
            if matches
        ),
        "chord",
    )


def _segment_ignore(_accumulator: _BarAccumulator, _line: str, _line_no: int) -> bool:
    return True


def _segment_invalid(_accumulator: _BarAccumulator, _line: str, _line_no: int) -> bool:
    return False


def _segment_bar(accumulator: _BarAccumulator, _line: str, _line_no: int) -> bool:
    accumulator.break_bar()
    return True


def _segment_time(accumulator: _BarAccumulator, line: str, line_no: int) -> bool:
    accumulator.set_time_signature(line, line_no)
    return True


def _segment_end(accumulator: _BarAccumulator, _line: str, _line_no: int) -> bool:
    accumulator.break_bar(reset_note_type=True)
    return True


def _segment_chord(accumulator: _BarAccumulator, line: str, line_no: int) -> bool:
    if not accumulator.add_chord(line, line_no) and accumulator.keeps_source:
        accumulator.carry(line)
    return True


_SEGMENT_HANDLERS = {
    "blank": _segment_ignore,
    "invalid": _segment_invalid,
    "ignore": _segment_ignore,
    "bar": _segment_bar,
    "time": _segment_time,
    "end": _segment_end,
    "chord": _segment_chord,
}


def _parse_bar_segment_lines(
    lines: list[str],
    *,
    start_line_no: int,
    syntax: TabSyntax,
    default_time: str | None,
    last_note_type: int | None,
) -> _BarSegmentParseResult | None:
    accumulator = _BarAccumulator(syntax, default_time=default_time, last_note_type=last_note_type)
    for offset, raw in enumerate(lines):
        line_no = start_line_no + offset
        line = raw.rstrip("\n").rstrip("\r")
        handler = _SEGMENT_HANDLERS[_segment_line_kind(line)]
        if not handler(accumulator, line, line_no):
            return None
    accumulator.finish()
    return _BarSegmentParseResult(bars=accumulator.bars, spans=accumulator.spans)


class _TabLinesParser:
    def __init__(self, strings: int, syntax: TabSyntax) -> None:
        self.syntax = syntax
        self.accumulator = _BarAccumulator(syntax)
        self.piece = Piece(title=None, author=None, composer=None, bars=self.accumulator.bars, strings=strings)
        self.saw_letters = False
        self.saw_digits = False
        self.saw_end_marker = False
        self.in_body = False

    def consume(self, line_no: int, raw: str) -> None:
        line = raw.rstrip("\n").rstrip("\r")
        if self.in_body and self.accumulator.keeps_source and _is_carried_body_line(line):
            self.accumulator.carry(line)
            return
        self._consume_line(line_no, line)
        if not self.in_body and self.accumulator.keeps_source and line.strip() != WRITTEN_HEADER:
            self.piece.source_header.append(line)

    def _consume_line(self, line_no: int, line: str) -> None:
        handlers = (
            self._consume_blank,
            self._consume_title,
            self._consume_hash_header,
            self._consume_dollar_header,
            self._consume_tuning,
            self._consume_comment_metadata,
            self._consume_ignored,
            self._consume_bar,
            self._consume_time_signature,
            self._consume_end,
        )
        for handler in handlers:
            if handler(line_no, line):
                return
        if not self._consume_chord(line_no, line) and self.in_body and self.accumulator.keeps_source:
            self.accumulator.carry(line)

    def finish(self, source_lines: list[str]) -> TabData | None:
        self.accumulator.finish()
        courses = [note.string for bar in self.piece.bars for chord in bar.chords for note in chord.notes]
        self.piece.strings = max([self.piece.strings, *courses])
        if self.accumulator.triplets:
            self.piece.import_warnings.append(TAB_TRIPLET_WARNING.format(count=self.accumulator.triplets))
        self.piece.style = self._style() or self.piece.style
        has_identity = any((self.piece.title, self.piece.author, self.piece.composer))
        if not self.piece.bars and not has_identity:
            return None
        if not self.piece.bars:
            self.piece.import_warnings.append(TAB_EMPTY_WARNING)
        elif not self.saw_end_marker:
            self.piece.import_warnings.append(TAB_INCOMPLETE_WARNING.format(bars=len(self.piece.bars)))
        return TabData(
            piece=self.piece,
            overrides={},
            durations={},
            dotted=set(),
            bar_width=0,
            bar_line_spans=self.accumulator.spans,
            source_lines=list(source_lines),
        )

    def _style(self) -> str | None:
        if self.syntax.italian or (self.saw_digits and not self.saw_letters):
            return "italian"
        return "french" if self.saw_letters else None

    def _consume_blank(self, _line_no: int, line: str) -> bool:
        if line.strip():
            return False
        # In the program a blank line ends a system; Oud's earlier files used one after every bar.
        if self.syntax.dialect is TabDialect.ORIGINAL:
            self.accumulator.mark_system_break()
        return True

    def _consume_title(self, _line_no: int, line: str) -> bool:
        if not line.startswith("{") or not line.endswith("}"):
            return False
        _apply_title_block(self.piece, line.strip("{}").strip())
        return True

    def _consume_hash_header(self, _line_no: int, line: str) -> bool:
        if not line.startswith("#") or not _looks_like_hash_header(line):
            return False
        self._apply_hash_header(line[1:].strip())
        return True

    def _apply_hash_header(self, header: str) -> None:
        lower = header.lower()
        if lower.startswith("tuning:"):
            self.piece.tuning = header.split(":", 1)[1].strip()
        elif lower.startswith("tempo:"):
            value = header.split(":", 1)[1].strip()
            if value.isdigit() and int(value) > 0:
                self.piece.tempo = int(value)
            else:
                self.piece.import_warnings.append(f"Invalid TAB tempo: {value or 'empty'}")
        elif lower.startswith(("time:", "timesig:", "meter:")):
            self.accumulator.set_default_time(_parse_time_signature(header.split(":", 1)[1].strip()))
        elif lower.startswith("subtitle:"):
            self.piece.subtitle = header.split(":", 1)[1].strip()
        elif lower.startswith("footnote:"):
            self.piece.footnote = header.split(":", 1)[1].strip()

    def _consume_dollar_header(self, _line_no: int, line: str) -> bool:
        if not line.startswith("$"):
            return False
        header = line[1:].strip()
        if header.lower().startswith(("time=", "timesig=", "meter=")):
            self.accumulator.set_default_time(_parse_time_signature(header.split("=", 1)[1].strip()))
        return True

    def _consume_tuning(self, _line_no: int, line: str) -> bool:
        if not line.startswith("-tuning "):
            return False
        tuning = line.split(" ", 1)[1].strip()
        self.piece.tuning = tuning if self.syntax.dialect is TabDialect.OUD_LEGACY else read_tuning(tuning)
        return True

    def _consume_comment_metadata(self, _line_no: int, line: str) -> bool:
        # Oud keeps what the format has no line for (tempo, a tuning below the
        # program's range) in comments, which the program ignores.
        key, colon, value = line.removeprefix("%").partition(":")
        if not line.startswith("%") or not colon or key.strip() not in ("tempo", "tuning"):
            return False
        self._apply_hash_header(f"{key.strip()}:{value}")
        return True

    @staticmethod
    def _consume_ignored(_line_no: int, line: str) -> bool:
        return line.startswith(("-", "%"))

    def _consume_bar(self, _line_no: int, line: str) -> bool:
        if not is_barline(line):
            return False
        self.in_body = True
        self.accumulator.break_bar(barline=line)
        return True

    def _consume_time_signature(self, line_no: int, line: str) -> bool:
        if not line.startswith("S"):
            return False
        self.in_body = True
        self.accumulator.set_time_signature(line, line_no)
        return True

    def _consume_end(self, _line_no: int, line: str) -> bool:
        if line.strip() != "e":
            return False
        self.saw_end_marker = True
        self.accumulator.break_bar(reset_note_type=True)
        return True

    def _consume_chord(self, line_no: int, line: str) -> bool:
        if not self.accumulator.add_chord(line, line_no):
            return False
        self.in_body = True
        payload = line[1:]
        self.saw_letters |= any("a" <= ch <= "p" for ch in payload)
        self.saw_digits |= any(ch.isdigit() or ch == "x" for ch in payload)
        return True


def _is_carried_body_line(line: str) -> bool:
    """Text, option, comment and setting lines inside the music; the model has no place for them."""

    text = line.strip()
    if text.startswith("-tuning "):
        return False
    return text.startswith(("{", "$", "-", "%"))


_OUD_COMMENT_KEYS = ("tempo", "tuning")
_DOLLAR_METER_KEYS = ("time", "timesig", "meter")


def _header_line_modelled(piece: Piece, line: str) -> bool:
    text = line.strip()
    if not text or text in (OUD_HEADER, WRITTEN_HEADER, ITALIAN_SETTING) or text.startswith("-tuning "):
        return True
    if text.startswith("{") and text.endswith("}"):
        return _apply_title_block(piece, text.strip("{}").strip())
    if text.startswith("#") and _looks_like_hash_header(text):
        return True
    key = text[1:].split(":", 1)[0].split("=", 1)[0].strip().lower()
    return (text.startswith("%") and ":" in text and key in _OUD_COMMENT_KEYS) or (
        text.startswith("$") and key in _DOLLAR_METER_KEYS
    )


def header_facts(lines: list[str]) -> tuple[object, ...]:
    """Title, composer, author, tuning and tempo that a header's lines give."""

    parser = _TabLinesParser(6, detect_syntax(lines))
    for line_no, line in enumerate(lines):
        parser.consume(line_no, line)
    piece = parser.piece
    return (piece.title, piece.composer, piece.author, piece.tuning, piece.tempo)


def unmodelled_header_lines(lines: list[str]) -> list[str]:
    """Header lines the model does not represent, with `-milan` removed (Oud writes the other order)."""

    scratch = Piece()
    kept: list[str] = []
    for line in lines:
        if _header_line_modelled(scratch, line):
            continue
        cleaned = " ".join(token for token in line.split() if token != MILAN_OPTION) if line.startswith("-") else line
        if cleaned.strip() not in ("", "-"):
            kept.append(cleaned)
    return kept


def parse_tab_text_data(text: str, strings: int = 6) -> TabData | None:
    return parse_tab_lines_data(text.splitlines(), strings=strings)


def parse_tab_lines_data(lines: list[str], strings: int = 6) -> TabData | None:
    # Format cues inspired by luteconv tab parsing.
    parser = _TabLinesParser(strings, detect_syntax(lines))
    for line_no, raw in enumerate(lines):
        parser.consume(line_no, raw)
    return parser.finish(lines)


def load_tab_data(path: str, strings: int = 6) -> TabData | None:
    with Path(path).open(encoding="utf-8", errors="ignore") as f:
        return parse_tab_lines_data(list(f), strings=strings)


def load_tab(path: str, strings: int = 6) -> Piece:
    data = load_tab_data(path, strings=strings)
    if data is None:
        piece = Piece(title=Path(path).stem, bars=[], strings=strings)
        piece.import_warnings.append(TAB_EMPTY_WARNING)
        return piece
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
    old_changed_start = changed_line_start if old_changed_line_start is None else old_changed_line_start
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
    seed_last_note_type = _last_note_type_from_bar(previous.piece.bars[ctx_start - 1]) if ctx_start > 0 else None
    seg = _parse_bar_segment_lines(
        seg_lines,
        start_line_no=seg_start_line,
        syntax=detect_syntax(new_lines),
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
