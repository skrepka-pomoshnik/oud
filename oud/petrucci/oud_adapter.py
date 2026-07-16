"""Oud model adapter for the canonical Petrucci notation score."""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction
from typing import NoReturn

from oud.petrucci.key_signature import key_signature_count
from oud.petrucci.model import Bar, ImportedBarContent, ImportedStaff, LyricEvent, MelodyEvent, Piece
from oud.petrucci.render_utils import note_type_to_denom
from oud.petrucci.score import (
    AccidentalDisplay,
    BarlineKind,
    BeamKind,
    Clef,
    EventKind,
    KeySignature,
    LyricSyllable,
    NotationEvent,
    NotationMeasure,
    NotationScore,
    NotationStaff,
    OrnamentKind,
    PitchStep,
    StemDirection,
    Syllabic,
    TimeSignature,
    WrittenPitch,
)


class OudScoreAdapterError(ValueError):
    """Raised when Oud source data is not normalized enough for score layout."""


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


@dataclass(frozen=True, slots=True)
class _StaffSource:
    source_index: int
    label: str | None
    clef: Clef
    bars: tuple[_BarData, ...]


def notation_score_from_piece(
    piece: Piece,
    *,
    score_id: str = "oud-score",
    staff_indices: tuple[int, ...] | None = None,
    include_lyrics: bool = True,
) -> NotationScore:
    """Normalize Oud note staffs, strictly including lyrics unless explicitly omitted."""

    if not isinstance(include_lyrics, bool):
        _fail("include_lyrics must be a bool")
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


def written_pitch_from_token(token: str, accidental_flags: int | None = None) -> WrittenPitch:
    """Decode an Oud/FT3 vocal pitch token without retaining source flags."""

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
    accidental = AccidentalDisplay.EXPLICIT if explicit else AccidentalDisplay.AUTO
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
    )


def _notation_staff(source: _StaffSource, *, piece: Piece) -> NotationStaff:
    measures: list[NotationMeasure] = []
    lyrics: list[LyricSyllable] = []
    key = _key_signature(piece.key)
    for sequence, bar in enumerate(source.bars):
        prefix = f"oud:staff:{source.source_index}:bar:{bar.source_index}"
        events, event_ids_by_onset = _bar_events(bar, prefix=prefix)
        lyrics.extend(_bar_lyrics(bar, prefix=prefix, event_ids_by_onset=event_ids_by_onset))
        time_signature = _time_signature(bar.time_sig)
        if sequence == 0 and time_signature is None:
            time_signature = TimeSignature()
        measures.append(
            NotationMeasure(
                id=f"{prefix}:measure",
                number=bar.source_index + 1,
                events=events,
                time_signature=time_signature,
                key_signature=key if sequence == 0 else None,
                barline=_barline_kind(bar.barline, bar.repeat),
                ending_numbers=bar.ending_numbers,
                forced_break_after=bar.system_break or _next_bar_starts_page(source.bars, sequence),
            ),
        )
    return NotationStaff(
        id=f"oud:staff:{source.source_index}",
        label=source.label,
        clef=source.clef,
        measures=tuple(measures),
        lyrics=tuple(lyrics),
    )


def _bar_events(
    bar: _BarData,
    *,
    prefix: str,
) -> tuple[tuple[NotationEvent, ...], dict[int, str]]:
    by_voice: dict[int, dict[int, list[MelodyEvent]]] = {}
    for event in bar.melody_events:
        by_voice.setdefault(event.voice, {}).setdefault(event.onset_index, []).append(event)
    out: list[NotationEvent] = []
    event_ids_by_onset: dict[int, str] = {}
    polyphonic = len(by_voice) > 1
    for voice, voice_events in sorted(by_voice.items()):
        onset = Fraction(0)
        for onset_index, source_events in sorted(voice_events.items()):
            sources = tuple(sorted(source_events, key=lambda event: (event.text, event.src_pos)))
            event_id = f"{prefix}:event:{onset_index}:{voice}"
            duration = _group_duration(sources, event_id=event_id)
            out.append(
                _notation_event(
                    sources,
                    event_id=event_id,
                    onset=onset,
                    duration=duration,
                    bar=bar,
                    polyphonic=polyphonic,
                ),
            )
            event_ids_by_onset.setdefault(onset_index, event_id)
            onset += duration
    return tuple(sorted(out, key=lambda event: (event.onset, event.voice, event.id))), event_ids_by_onset


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
        fermata=any(item.fermata for item in sources) or bar.fermata,
        dynamic=bar.dynamic,
        ornament=_group_ornament(sources, event_id=event_id),
    )


def _group_duration(sources: tuple[MelodyEvent, ...], *, event_id: str) -> Fraction:
    durations = {_event_duration(source) for source in sources}
    if len(durations) != 1:
        _fail(f"event group {event_id!r} has inconsistent durations")
    return durations.pop()


def _group_pitches(sources: tuple[MelodyEvent, ...], *, event_id: str) -> tuple[WrittenPitch, ...]:
    pitches = tuple(written_pitch_from_token(source.text, source.accidental_flags) for source in sources)
    if len(set(pitches)) != len(pitches):
        _fail(f"event group {event_id!r} contains a duplicate written pitch")
    return tuple(sorted(pitches, key=lambda pitch: (pitch.midi, pitch.step.value, pitch.alter)))


def _group_beam(sources: tuple[MelodyEvent, ...], *, event_id: str) -> BeamKind:
    values = {_beam_kind(source.beam) for source in sources} - {BeamKind.NONE}
    if len(values) > 1:
        _fail(f"event group {event_id!r} has conflicting beam values")
    return values.pop() if values else BeamKind.NONE


def _group_ornament(sources: tuple[MelodyEvent, ...], *, event_id: str) -> OrnamentKind | None:
    values = {_ornament_kind(source.ornament) for source in sources} - {None}
    if len(values) > 1:
        _fail(f"event group {event_id!r} has conflicting ornaments")
    return values.pop() if values else None


def _voice_stem(voice: int) -> StemDirection:
    return StemDirection.UP if voice == 0 else StemDirection.DOWN


def _bar_lyrics(
    bar: _BarData,
    *,
    prefix: str,
    event_ids_by_onset: dict[int, str],
) -> tuple[LyricSyllable, ...]:
    if bar.raw_lyrics and not bar.lyric_rows:
        _fail(f"bar {bar.source_index + 1} has raw lyrics without normalized lyric events")
    out: list[LyricSyllable] = []
    for row_index, row in enumerate(bar.lyric_rows):
        for lyric_index, source in enumerate(row):
            if source.verse < 0:
                _fail(f"lyric in bar {bar.source_index + 1} has negative verse {source.verse}")
            event_id = event_ids_by_onset.get(source.onset_index)
            if event_id is None:
                _fail(
                    f"lyric onset {source.onset_index} in bar {bar.source_index + 1} has no notation event",
                )
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
    return tuple(out)


def _event_duration(event: MelodyEvent) -> Fraction:
    denominator = note_type_to_denom(event.note_type or 4)
    if denominator is None or denominator > 64:
        _fail(f"unsupported notation note type {event.note_type!r}")
    duration = Fraction(1, denominator)
    return duration * Fraction(3, 2) if event.dotted else duration


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
    mapping = {None: None, "": None, "+": OrnamentKind.PLUS}
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


def _fail(message: str) -> NoReturn:
    raise OudScoreAdapterError(message)


__all__ = ["OudScoreAdapterError", "notation_score_from_piece", "written_pitch_from_token"]
