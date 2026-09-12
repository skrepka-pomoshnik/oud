"""Piece-model adapter for the canonical Petrucci notation score."""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction
from typing import NoReturn

from petrucci.core.model import Bar, ImportedBarContent, ImportedStaff, LyricEvent, MelodyEvent, Piece
from petrucci.core.music.key_signature import key_signature_count
from petrucci.core.score import (
    AccidentalDisplay,
    BarlineKind,
    BeamKind,
    Clef,
    EventKind,
    KeySignature,
    LyricLine,
    LyricSyllable,
    NotationEvent,
    NotationMeasure,
    NotationScore,
    NotationSpan,
    NotationStaff,
    OrnamentKind,
    PitchStep,
    ProportionRatio,
    SpanKind,
    StemDirection,
    Syllabic,
    TimeSignature,
    TupletRatio,
    WrittenPitch,
)
from petrucci.rendering.primitives.utils import note_type_to_denom


class PieceAdapterError(ValueError):
    """Raised when Piece source data is not normalized enough for score layout."""


@dataclass(frozen=True, slots=True)
class _BarData:
    source_index: int
    melody_events: tuple[MelodyEvent, ...]
    lyric_rows: tuple[tuple[LyricEvent, ...], ...]
    raw_lyrics: tuple[str, ...]
    time_sig: str | None
    barline: str | None
    repeat: str | None
    ending_numbers: tuple[int, ...]
    system_break: bool
    page_break_before: bool
    dynamic: str | None
    fermata: bool
    clef: str | None
    key_signature: str | None
    proportion: tuple[int, int] | None


@dataclass(frozen=True, slots=True)
class _BarEvents:
    events: tuple[NotationEvent, ...]
    event_ids_by_onset: dict[int, str]
    tie_targets: frozenset[str]
    slur_starts: frozenset[str]
    slur_ends: frozenset[str]
    glissando_targets: frozenset[str]


@dataclass(frozen=True, slots=True)
class _StaffSource:
    source_index: int
    label: str | None
    clef: Clef
    bars: tuple[_BarData, ...]


def notation_score_from_piece(
    piece: Piece,
    *,
    score_id: str = "piece-score",
    staff_indices: tuple[int, ...] | None = None,
    include_lyrics: bool = True,
) -> NotationScore:
    """Normalize Piece note staffs, strictly including lyrics unless explicitly omitted."""

    sources = _staff_sources(piece, staff_indices=staff_indices, include_lyrics=include_lyrics)
    if not sources:
        _fail("piece does not contain a normalized standard-notation staff")
    staffs = tuple(_notation_staff(source, piece=piece) for source in sources)
    return NotationScore(
        id=score_id,
        title=piece.title,
        subtitle=piece.subtitle,
        composer=piece.composer or piece.author,
        staffs=staffs,
    )


def written_pitch_from_token(
    token: str,
    accidental_flags: int | None = None,
    *,
    courtesy: bool = False,
) -> WrittenPitch:
    """Decode an Piece/FT3 vocal pitch token without retaining source flags."""

    match = re.search(r"(?i)([a-h])([#b]*)(-?\d+|[',]*)", token.strip())
    if match is None:
        _fail(f"cannot decode written pitch token {token!r}")
    letter, accidental_text, octave_text = match.groups()
    step = PitchStep.B if letter.lower() == "h" else PitchStep(letter.upper())
    alter = accidental_text.count("#") - accidental_text.count("b")
    flags = accidental_flags or 0
    if flags & 0x2000:
        alter = 0
    elif flags & 0x1000:
        alter = -1
    elif flags & 0x0002:
        alter = 1
    octave = _token_octave(octave_text)
    explicit = bool(accidental_text or flags & (0x2000 | 0x1000 | 0x0002))
    accidental = AccidentalDisplay.COURTESY if explicit and courtesy else AccidentalDisplay.EXPLICIT
    if not explicit:
        accidental = AccidentalDisplay.AUTO
    return WrittenPitch(step=step, octave=octave, alter=alter, accidental=accidental)


def _staff_sources(
    piece: Piece,
    *,
    staff_indices: tuple[int, ...] | None,
    include_lyrics: bool,
) -> tuple[_StaffSource, ...]:
    imported = piece.imported_score
    if imported is None:
        return _piece_bar_source(piece, include_lyrics=include_lyrics)
    selected = set(staff_indices) if staff_indices is not None else None
    note_staffs = [
        (index, staff)
        for index, staff in enumerate(imported.staffs)
        if staff.kind == "note" and (selected is None or index in selected)
    ]
    if not note_staffs:
        return _piece_bar_source(piece, include_lyrics=include_lyrics)
    source_indexes = sorted({bar.source_bar_index for _index, staff in note_staffs for bar in staff.bars})
    sources: list[_StaffSource] = []
    for source_index, staff in note_staffs:
        lyric_staff = _matching_lyric_staff(imported.staffs, staff) if include_lyrics else None
        bars = _imported_bar_data(staff, lyric_staff=lyric_staff, source_indexes=source_indexes)
        sources.append(
            _StaffSource(
                source_index=source_index,
                label=staff.label,
                clef=_clef_for_label(staff.label),
                bars=bars,
            ),
        )
    return tuple(sources)


def _piece_bar_source(piece: Piece, *, include_lyrics: bool) -> tuple[_StaffSource, ...]:
    if not any(bar.melody_events for bar in piece.bars):
        return ()
    bars = tuple(_piece_bar_data(index, bar, include_lyrics=include_lyrics) for index, bar in enumerate(piece.bars))
    return (_StaffSource(source_index=0, label=piece.part, clef=_clef_for_label(piece.part), bars=bars),)


def _matching_lyric_staff(staffs: list[ImportedStaff], note_staff: ImportedStaff) -> ImportedStaff | None:
    lyric_staffs = [staff for staff in staffs if staff.kind == "lyrics"]
    labeled = next((staff for staff in lyric_staffs if staff.label == note_staff.label), None)
    if labeled is not None:
        return labeled
    return lyric_staffs[0] if len(lyric_staffs) == 1 else None


def _imported_bar_data(
    note_staff: ImportedStaff,
    *,
    lyric_staff: ImportedStaff | None,
    source_indexes: list[int],
) -> tuple[_BarData, ...]:
    notes = {bar.source_bar_index: bar for bar in note_staff.bars}
    lyrics = {bar.source_bar_index: bar for bar in lyric_staff.bars} if lyric_staff is not None else {}
    return tuple(
        _merged_imported_bar(source_index, notes.get(source_index), lyrics.get(source_index))
        for source_index in source_indexes
    )


def _merged_imported_bar(
    source_index: int,
    note: ImportedBarContent | None,
    lyric: ImportedBarContent | None,
) -> _BarData:
    structure = note or lyric
    return _BarData(
        source_index=source_index,
        melody_events=tuple(note.melody_events if note is not None else ()),
        lyric_rows=tuple(tuple(row) for row in (lyric.lyric_event_rows if lyric is not None else ())),
        raw_lyrics=tuple(lyric.lyrics if lyric is not None else ()),
        time_sig=structure.time_sig if structure is not None else None,
        barline=structure.barline if structure is not None else None,
        repeat=structure.repeat if structure is not None else None,
        ending_numbers=structure.ending_numbers if structure is not None else (),
        system_break=bool(structure and structure.system_break),
        page_break_before=False,
        dynamic=structure.dynamic if structure is not None else None,
        fermata=bool(structure and structure.fermata),
        clef=structure.clef if structure is not None else None,
        key_signature=structure.key_signature if structure is not None else None,
        proportion=structure.proportion if structure is not None else None,
    )


def _piece_bar_data(source_index: int, bar: Bar, *, include_lyrics: bool) -> _BarData:
    return _BarData(
        source_index=source_index,
        melody_events=tuple(bar.melody_events),
        lyric_rows=tuple(tuple(row) for row in bar.lyric_event_rows) if include_lyrics else (),
        raw_lyrics=tuple(bar.lyrics) if include_lyrics else (),
        time_sig=bar.time_sig,
        barline=bar.barline,
        repeat=bar.repeat,
        ending_numbers=bar.ending_numbers,
        system_break=bar.system_break,
        page_break_before=bar.page_break_before,
        dynamic=bar.dynamic,
        fermata=bar.fermata,
        clef=bar.clef,
        key_signature=bar.key_signature,
        proportion=bar.proportion,
    )


def _notation_staff(source: _StaffSource, *, piece: Piece) -> NotationStaff:
    measures: list[NotationMeasure] = []
    lyrics: list[LyricSyllable] = []
    lyric_lines: list[LyricLine] = []
    tie_targets: set[str] = set()
    slur_starts: set[str] = set()
    slur_ends: set[str] = set()
    glissando_targets: set[str] = set()
    initial_key = _key_signature(piece.key)
    current_time = TimeSignature()
    for sequence, bar in enumerate(source.bars):
        prefix = f"piece:staff:{source.source_index}:bar:{bar.source_index}"
        measure_id = f"{prefix}:measure"
        normalized = _bar_events(bar, prefix=prefix)
        tie_targets.update(normalized.tie_targets)
        slur_starts.update(normalized.slur_starts)
        slur_ends.update(normalized.slur_ends)
        glissando_targets.update(normalized.glissando_targets)
        bar_lyrics, bar_lyric_lines = _bar_lyrics(
            bar,
            prefix=prefix,
            measure_id=measure_id,
            event_ids_by_onset=normalized.event_ids_by_onset,
        )
        lyrics.extend(bar_lyrics)
        lyric_lines.extend(bar_lyric_lines)
        time_signature = _time_signature(bar.time_sig)
        if sequence == 0 and time_signature is None:
            time_signature = TimeSignature()
        if time_signature is not None:
            current_time = time_signature
        key_signature = _key_signature(bar.key_signature)
        if sequence == 0 and key_signature is None:
            key_signature = initial_key
        measures.append(
            NotationMeasure(
                id=measure_id,
                number=bar.source_index + 1,
                events=normalized.events,
                time_signature=time_signature,
                key_signature=key_signature,
                clef=_explicit_clef(bar.clef),
                barline=_barline_kind(bar.barline, bar.repeat),
                ending_numbers=bar.ending_numbers,
                forced_break_after=bar.system_break or _next_bar_starts_page(source.bars, sequence),
                irregular=any(event.onset + event.duration > current_time.duration for event in normalized.events),
                proportion=ProportionRatio(*bar.proportion) if bar.proportion is not None else None,
            ),
        )
    measure_tuple = tuple(measures)
    return NotationStaff(
        id=f"piece:staff:{source.source_index}",
        label=source.label,
        clef=source.clef,
        measures=measure_tuple,
        lyrics=tuple(lyrics),
        spans=(
            *_tie_spans(measure_tuple, tie_targets),
            *_slur_spans(measure_tuple, slur_starts, slur_ends),
            *_glissando_spans(measure_tuple, glissando_targets),
        ),
        lyric_lines=tuple(lyric_lines),
    )


def _record_source_marks(
    sources: tuple[MelodyEvent, ...],
    event_id: str,
    *,
    tie_targets: set[str],
    slur_starts: set[str],
    slur_ends: set[str],
    glissando_targets: set[str],
) -> None:
    targets = (
        ("tie_from_previous", tie_targets),
        ("slur_start", slur_starts),
        ("slur_end", slur_ends),
        ("glissando_from_previous", glissando_targets),
    )
    for attribute, target in targets:
        if any(getattr(source, attribute) for source in sources):
            target.add(event_id)


def _bar_events(
    bar: _BarData,
    *,
    prefix: str,
) -> _BarEvents:
    by_voice: dict[int, dict[int, list[MelodyEvent]]] = {}
    for event in bar.melody_events:
        by_voice.setdefault(event.voice, {}).setdefault(event.onset_index, []).append(event)
    out: list[NotationEvent] = []
    event_ids_by_onset: dict[int, str] = {}
    tie_targets: set[str] = set()
    slur_starts: set[str] = set()
    slur_ends: set[str] = set()
    glissando_targets: set[str] = set()
    polyphonic = len(by_voice) > 1
    for voice, voice_events in sorted(by_voice.items()):
        onset = Fraction(0)
        for onset_index, source_events in sorted(voice_events.items()):
            sources = tuple(sorted(source_events, key=lambda event: (event.text, event.src_pos)))
            event_id = _source_event_id(sources, fallback=f"{prefix}:event:{onset_index}:{voice}")
            duration = _group_duration(sources, event_id=event_id)
            event = _notation_event(
                sources,
                event_id=event_id,
                onset=onset,
                duration=duration,
                bar=bar,
                polyphonic=polyphonic,
            )
            out.append(event)
            _record_source_marks(
                sources,
                event_id,
                tie_targets=tie_targets,
                slur_starts=slur_starts,
                slur_ends=slur_ends,
                glissando_targets=glissando_targets,
            )
            event_ids_by_onset.setdefault(onset_index, event_id)
            if not event.grace:
                onset += duration
    return _BarEvents(
        events=tuple(sorted(out, key=lambda event: (event.onset, event.voice, event.id))),
        event_ids_by_onset=event_ids_by_onset,
        tie_targets=frozenset(tie_targets),
        slur_starts=frozenset(slur_starts),
        slur_ends=frozenset(slur_ends),
        glissando_targets=frozenset(glissando_targets),
    )


def _source_event_id(sources: tuple[MelodyEvent, ...], *, fallback: str) -> str:
    source_ids = {source.source_id for source in sources if source.source_id is not None}
    if len(source_ids) > 1:
        _fail(f"event group {fallback!r} has conflicting source identities")
    return source_ids.pop() if source_ids else fallback


def _notation_event(
    sources: tuple[MelodyEvent, ...],
    *,
    event_id: str,
    onset: Fraction,
    duration: Fraction,
    bar: _BarData,
    polyphonic: bool,
) -> NotationEvent:
    source = sources[0]
    if source.voice < 0:
        _fail(f"event {event_id!r} has negative voice {source.voice}")
    rest_values = {item.is_rest or item.text.strip().lower() in {"r", "rest"} for item in sources}
    if len(rest_values) != 1:
        _fail(f"event group {event_id!r} mixes notes and rests")
    is_rest = rest_values.pop()
    pitches = () if is_rest else _group_pitches(sources, event_id=event_id)
    return NotationEvent(
        id=event_id,
        onset=onset,
        duration=duration,
        kind=EventKind.REST if is_rest else EventKind.NOTE,
        pitches=pitches,
        voice=source.voice,
        stem=_voice_stem(source.voice) if polyphonic else StemDirection.AUTO,
        beam=_group_beam(sources, event_id=event_id),
        tuplet=_group_tuplet(sources, event_id=event_id),
        fermata=any(item.fermata for item in sources) or bar.fermata,
        dynamic=bar.dynamic,
        ornament=_group_ornament(sources, event_id=event_id),
        editorial_brackets=any(item.editorial_brackets for item in sources),
        grace=_group_grace(sources, event_id=event_id),
        harmonic=_group_harmonic(sources, event_id=event_id),
        fingering=_group_fingering(sources, event_id=event_id),
    )


def _group_duration(sources: tuple[MelodyEvent, ...], *, event_id: str) -> Fraction:
    durations = {_event_duration(source) for source in sources}
    if len(durations) != 1:
        _fail(f"event group {event_id!r} has inconsistent durations")
    return durations.pop()


def _group_pitches(sources: tuple[MelodyEvent, ...], *, event_id: str) -> tuple[WrittenPitch, ...]:
    pitches = tuple(
        written_pitch_from_token(
            source.text,
            source.accidental_flags,
            courtesy=source.courtesy_accidental,
        )
        for source in sources
    )
    if len(set(pitches)) != len(pitches):
        _fail(f"event group {event_id!r} contains a duplicate written pitch")
    return tuple(sorted(pitches, key=lambda pitch: (pitch.midi, pitch.step.value, pitch.alter)))


def _tie_spans(
    measures: tuple[NotationMeasure, ...],
    targets: set[str],
) -> tuple[NotationSpan, ...]:
    previous_by_voice: dict[int, NotationEvent] = {}
    spans: list[NotationSpan] = []
    for measure in measures:
        for event in sorted(measure.events, key=lambda item: (item.onset, item.voice, item.id)):
            if event.id in targets:
                previous = previous_by_voice.get(event.voice)
                if previous is None or not any(
                    _same_written_pitch(left, right) for left in previous.pitches for right in event.pitches
                ):
                    _fail(f"tie target {event.id!r} has no preceding event with a shared pitch")
                spans.append(
                    NotationSpan(
                        id=f"{event.id}:tie",
                        kind=SpanKind.TIE,
                        start_event_id=previous.id,
                        end_event_id=event.id,
                    ),
                )
            if event.kind is EventKind.NOTE:
                previous_by_voice[event.voice] = event
    return tuple(spans)


def _slur_spans(
    measures: tuple[NotationMeasure, ...],
    starts: set[str],
    ends: set[str],
) -> tuple[NotationSpan, ...]:
    open_by_voice: dict[int, list[NotationEvent]] = {}
    spans: list[NotationSpan] = []
    for measure in measures:
        for event in sorted(measure.events, key=lambda item: (item.onset, item.voice, item.id)):
            if event.id in ends:
                opened = open_by_voice.get(event.voice, [])
                if not opened:
                    _fail(f"slur end {event.id!r} has no preceding start in voice {event.voice}")
                start = opened.pop()
                spans.append(NotationSpan(f"{start.id}:slur", SpanKind.SLUR, start.id, event.id))
            if event.id in starts:
                open_by_voice.setdefault(event.voice, []).append(event)
    unclosed = sorted(event.id for values in open_by_voice.values() for event in values)
    if unclosed:
        _fail(f"slur starts have no following end: {', '.join(unclosed)}")
    return tuple(spans)


def _glissando_spans(
    measures: tuple[NotationMeasure, ...],
    targets: set[str],
) -> tuple[NotationSpan, ...]:
    previous_by_voice: dict[int, NotationEvent] = {}
    spans: list[NotationSpan] = []
    for measure in measures:
        for event in sorted(measure.events, key=lambda item: (item.onset, item.voice, item.id)):
            if event.id in targets:
                previous = previous_by_voice.get(event.voice)
                if previous is None:
                    _fail(f"glissando target {event.id!r} has no preceding note in voice {event.voice}")
                spans.append(NotationSpan(f"{event.id}:glissando", SpanKind.GLISSANDO, previous.id, event.id))
            if event.kind is EventKind.NOTE:
                previous_by_voice[event.voice] = event
    return tuple(spans)


def _same_written_pitch(left: WrittenPitch, right: WrittenPitch) -> bool:
    return (left.step, left.octave, left.alter) == (right.step, right.octave, right.alter)


def _group_beam(sources: tuple[MelodyEvent, ...], *, event_id: str) -> BeamKind:
    values = {_beam_kind(source.beam) for source in sources} - {BeamKind.NONE}
    if len(values) > 1:
        _fail(f"event group {event_id!r} has conflicting beam values")
    return values.pop() if values else BeamKind.NONE


def _group_tuplet(sources: tuple[MelodyEvent, ...], *, event_id: str) -> TupletRatio | None:
    values: set[tuple[int, int]] = set()
    for source in sources:
        if (source.tuplet_actual is None) != (source.tuplet_normal is None):
            _fail(f"event group {event_id!r} has an incomplete tuplet ratio")
        if source.tuplet_actual is not None and source.tuplet_normal is not None:
            values.add((source.tuplet_actual, source.tuplet_normal))
    if len(values) > 1:
        _fail(f"event group {event_id!r} has conflicting tuplet ratios")
    return TupletRatio(*values.pop()) if values else None


def _group_grace(sources: tuple[MelodyEvent, ...], *, event_id: str) -> bool:
    values = {source.grace for source in sources}
    if len(values) > 1:
        _fail(f"event group {event_id!r} mixes grace and measured notes")
    return values.pop()


def _group_harmonic(sources: tuple[MelodyEvent, ...], *, event_id: str) -> bool:
    values = {source.harmonic for source in sources}
    if len(values) > 1:
        _fail(f"event group {event_id!r} mixes harmonic and ordinary noteheads")
    return values.pop()


def _group_fingering(sources: tuple[MelodyEvent, ...], *, event_id: str) -> str | None:
    values = {source.fingering for source in sources if source.fingering is not None}
    if len(values) > 1:
        _fail(f"event group {event_id!r} has conflicting notation fingerings")
    return values.pop() if values else None


def _group_ornament(sources: tuple[MelodyEvent, ...], *, event_id: str) -> OrnamentKind | None:
    values = {_ornament_kind(source.ornament) for source in sources} - {None}
    if len(values) > 1:
        _fail(f"event group {event_id!r} has conflicting ornaments")
    return values.pop() if values else None


def _voice_stem(voice: int) -> StemDirection:
    return StemDirection.UP if voice == 0 else StemDirection.DOWN


def _raw_lyric_lines(bar: _BarData, *, prefix: str, measure_id: str) -> tuple[LyricLine, ...] | None:
    if not bar.raw_lyrics or bar.lyric_rows:
        return None
    return tuple(
        LyricLine(f"{prefix}:lyric-line:{verse}", measure_id, text, verse)
        for verse, text in enumerate(bar.raw_lyrics)
        if text.strip()
    )


def _unmapped_lyric_line(
    bar: _BarData,
    row: tuple[LyricEvent, ...],
    row_index: int,
    *,
    prefix: str,
    measure_id: str,
    event_ids_by_onset: dict[int, str],
) -> tuple[bool, LyricLine | None]:
    meaningful = tuple(source for source in row if source.text or source.extender)
    if all(source.onset_index in event_ids_by_onset for source in meaningful):
        return False, None
    text = (
        bar.raw_lyrics[row_index]
        if row_index < len(bar.raw_lyrics)
        else " ".join(source.text for source in meaningful if source.text)
    )
    if not text.strip():
        return True, None
    verse = meaningful[0].verse if meaningful else row_index
    return True, LyricLine(f"{prefix}:lyric-line:{row_index}", measure_id, text, verse)


def _lyric_event_id(source: LyricEvent, event_ids_by_onset: dict[int, str], *, bar_index: int) -> str | None:
    if not source.text and not source.extender:
        return None
    if source.verse < 0:
        _fail(f"lyric in bar {bar_index + 1} has negative verse {source.verse}")
    event_id = event_ids_by_onset.get(source.onset_index)
    if event_id is None:
        _fail(f"lyric onset {source.onset_index} in bar {bar_index + 1} has no notation event")
    return event_id


def _bar_lyrics(
    bar: _BarData,
    *,
    prefix: str,
    measure_id: str,
    event_ids_by_onset: dict[int, str],
) -> tuple[tuple[LyricSyllable, ...], tuple[LyricLine, ...]]:
    raw_lines = _raw_lyric_lines(bar, prefix=prefix, measure_id=measure_id)
    if raw_lines is not None:
        return (), raw_lines
    out: list[LyricSyllable] = []
    lines: list[LyricLine] = []
    for row_index, row in enumerate(bar.lyric_rows):
        unmapped, line = _unmapped_lyric_line(
            bar,
            row,
            row_index,
            prefix=prefix,
            measure_id=measure_id,
            event_ids_by_onset=event_ids_by_onset,
        )
        if unmapped:
            if line is not None:
                lines.append(line)
            continue
        for lyric_index, source in enumerate(row):
            event_id = _lyric_event_id(source, event_ids_by_onset, bar_index=bar.source_index)
            if event_id is None:
                continue
            out.append(
                LyricSyllable(
                    id=f"{prefix}:lyric:{row_index}:{lyric_index}",
                    event_id=event_id,
                    text=source.text,
                    verse=source.verse,
                    syllabic=_syllabic(source.syllabic),
                    extender=source.extender,
                ),
            )
    return tuple(out), tuple(lines)


def _event_duration(event: MelodyEvent) -> Fraction:
    denominator = note_type_to_denom(event.note_type or 4)
    maximum_supported_denominator = 64
    if denominator is None or denominator > maximum_supported_denominator:
        _fail(f"unsupported notation note type {event.note_type!r}")
    duration = Fraction(1, denominator)
    if event.dotted:
        duration *= Fraction(3, 2)
    if event.tuplet_actual is not None and event.tuplet_normal is not None:
        duration *= Fraction(event.tuplet_normal, event.tuplet_actual)
    return duration


def _time_signature(value: str | None) -> TimeSignature | None:
    if not value:
        return None
    normalized = value.strip()
    historical = {
        "C": TimeSignature(4, 4),
        "c": TimeSignature(4, 4),
        "O": TimeSignature(3, 4),
        "o": TimeSignature(3, 4),
        "C|": TimeSignature(2, 2),
        "c|": TimeSignature(2, 2),
    }
    if normalized in historical:
        return historical[normalized]
    match = re.fullmatch(r"(\d+)\s*/\s*(\d+)", normalized)
    if match is None:
        _fail(f"unsupported time signature {value!r}")
    return TimeSignature(int(match.group(1)), int(match.group(2)))


def _key_signature(value: str | None) -> KeySignature | None:
    if not value:
        return None
    normalized = value.strip().replace("♭", "b").replace("♯", "#")
    fifths = key_signature_count(normalized)
    if fifths is None:
        _fail(f"unsupported key signature {value!r}")
    return KeySignature(fifths)


def _next_bar_starts_page(bars: tuple[_BarData, ...], sequence: int) -> bool:
    return sequence + 1 < len(bars) and bars[sequence + 1].page_break_before


def _barline_kind(barline: str | None, repeat: str | None) -> BarlineKind:
    repeat_value = (repeat or "").lower()
    if "both" in repeat_value:
        return BarlineKind.REPEAT_BOTH
    if "start" in repeat_value and "end" not in repeat_value:
        return BarlineKind.REPEAT_START
    if "end" in repeat_value:
        return BarlineKind.REPEAT_END
    barline_value = (barline or "").lower()
    if "final" in barline_value:
        return BarlineKind.FINAL
    if "double" in barline_value:
        return BarlineKind.DOUBLE
    return BarlineKind.REGULAR


def _beam_kind(value: str | None) -> BeamKind:
    mapping = {
        None: BeamKind.NONE,
        "": BeamKind.NONE,
        "start": BeamKind.START,
        "continue": BeamKind.CONTINUE,
        "end": BeamKind.END,
        "partial-forward": BeamKind.PARTIAL_FORWARD,
        "partial-backward": BeamKind.PARTIAL_BACKWARD,
    }
    if value not in mapping:
        _fail(f"unsupported beam value {value!r}")
    return mapping[value]


def _ornament_kind(value: str | None) -> OrnamentKind | None:
    mapping = {
        None: None,
        "": None,
        "+": OrnamentKind.PLUS,
        "trill": OrnamentKind.TRILL,
        "turn": OrnamentKind.TURN,
        "mordent": OrnamentKind.MORDENT,
        "inverted-mordent": OrnamentKind.INVERTED_MORDENT,
    }
    if value not in mapping:
        _fail(f"unsupported ornament value {value!r}")
    return mapping[value]


def _syllabic(value: str) -> Syllabic:
    try:
        return Syllabic(value)
    except ValueError:
        _fail(f"unsupported syllabic value {value!r}")


def _token_octave(value: str) -> int:
    if not value:
        return 4
    if value.lstrip("-").isdigit():
        return int(value)
    return 4 + value.count("'") - value.count(",")


def _clef_for_label(label: str | None) -> Clef:
    normalized = (label or "").lower()
    return Clef.BASS if any(token in normalized for token in ("bass", "basso", "viol")) else Clef.TREBLE


def _explicit_clef(value: str | None) -> Clef | None:
    if value is None or not value.strip():
        return None
    normalized = value.strip().lower()
    mapping = {"treble": Clef.TREBLE, "g": Clef.TREBLE, "bass": Clef.BASS, "f": Clef.BASS}
    if normalized not in mapping:
        _fail(f"unsupported clef {value!r}")
    return mapping[normalized]


def _fail(message: str) -> NoReturn:
    raise PieceAdapterError(message)


__all__ = ["PieceAdapterError", "notation_score_from_piece", "written_pitch_from_token"]
