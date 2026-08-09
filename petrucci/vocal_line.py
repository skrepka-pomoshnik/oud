from __future__ import annotations

from dataclasses import dataclass

from petrucci.model import Bar, Chord, LyricEvent, MelodyEvent

_DIATONIC_BASE = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11, "h": 11}


@dataclass(frozen=True)
class VocalEvent:
    onset_index: int
    chord_index: int
    pitch: int | None
    note_type: int
    dotted: bool
    text: str = ""
    is_rest: bool = False
    beam: str | None = None
    fermata: bool = False
    ornament: str | None = None
    courtesy_accidental: bool = False
    editorial_brackets: bool = False
    tie_from_previous: bool = False
    voice: int = 0


def token_pitch_value(token: str) -> int | None:
    raw = token.strip().lower()
    if not raw:
        return None
    letter_index = next((index for index, char in enumerate(raw) if char in _DIATONIC_BASE), None)
    if letter_index is None:
        return None
    letter = raw[letter_index]
    pitch = 60 + _DIATONIC_BASE[letter]
    accidentals = raw[letter_index + 1 :]
    pitch += accidentals.count("#")
    pitch -= accidentals.count("b")
    pitch += 12 * raw.count("'")
    pitch -= 12 * raw.count(",")
    return pitch


def chord_top_pitch(chord: Chord, tuning_pitches: list[int] | None) -> int | None:
    if not chord.notes or not tuning_pitches:
        return None
    pitches: list[int] = []
    for note in chord.notes:
        idx = note.string - 1
        if 0 <= idx < len(tuning_pitches):
            pitches.append(tuning_pitches[idx] + note.fret)
    return max(pitches) if pitches else None


def infer_vocal_events(
    bar: Bar,
    *,
    tuning_pitches: list[int] | None,
) -> list[VocalEvent]:
    explicit = _explicit_vocal_events(bar, tuning_pitches)
    return explicit or _inferred_chord_vocal_events(bar, tuning_pitches)


def _explicit_vocal_events(bar: Bar, tuning_pitches: list[int] | None) -> list[VocalEvent]:
    out: list[VocalEvent] = []
    for onset_index, chord_index, text in _anchor_melody_events(bar):
        event = _explicit_vocal_event(
            onset_index=onset_index,
            chord_index=chord_index,
            source=text,
            chords=bar.chords,
            tuning_pitches=tuning_pitches,
        )
        if event is not None:
            out.append(event)
    return out


def _inferred_chord_vocal_events(bar: Bar, tuning_pitches: list[int] | None) -> list[VocalEvent]:
    out: list[VocalEvent] = []
    for onset_index, chord in enumerate(bar.chords):
        pitch = chord_top_pitch(chord, tuning_pitches)
        if pitch is None:
            continue
        out.append(
            VocalEvent(
                onset_index=onset_index,
                chord_index=onset_index,
                pitch=pitch,
                note_type=chord.note_type,
                dotted=bool(chord.dotted),
            ),
        )
    return out


def _explicit_vocal_event(
    *,
    onset_index: int,
    chord_index: int,
    source: MelodyEvent | str,
    chords: list[Chord],
    tuning_pitches: list[int] | None,
) -> VocalEvent | None:
    chord = chords[chord_index] if 0 <= chord_index < len(chords) else None
    token = source.text if isinstance(source, MelodyEvent) else source
    is_rest = isinstance(source, MelodyEvent) and source.is_rest
    if not is_rest and token.strip().lower() in {"r", "rest"}:
        is_rest = True
    if is_rest:
        note_type = source.note_type if isinstance(source, MelodyEvent) else None
        dotted = source.dotted if isinstance(source, MelodyEvent) else False
        if note_type is None and chord is not None:
            note_type = chord.note_type
            dotted = bool(chord.dotted)
        return VocalEvent(
            onset_index=onset_index,
            chord_index=chord_index,
            pitch=None,
            note_type=note_type or 4,
            dotted=dotted,
            text=token,
            is_rest=True,
            beam=source.beam if isinstance(source, MelodyEvent) else None,
            fermata=source.fermata if isinstance(source, MelodyEvent) else False,
            ornament=source.ornament if isinstance(source, MelodyEvent) else None,
            courtesy_accidental=source.courtesy_accidental if isinstance(source, MelodyEvent) else False,
            editorial_brackets=source.editorial_brackets if isinstance(source, MelodyEvent) else False,
            tie_from_previous=source.tie_from_previous if isinstance(source, MelodyEvent) else False,
            voice=source.voice if isinstance(source, MelodyEvent) else 0,
        )
    pitch = token_pitch_value(token)
    if pitch is None and chord is not None:
        pitch = chord_top_pitch(chord, tuning_pitches)
    if pitch is None:
        return None
    note_type = source.note_type if isinstance(source, MelodyEvent) else None
    dotted = source.dotted if isinstance(source, MelodyEvent) else False
    if note_type is None and chord is not None:
        note_type = chord.note_type
        dotted = bool(chord.dotted)
    return VocalEvent(
        onset_index=onset_index,
        chord_index=chord_index,
        pitch=pitch,
        note_type=note_type or 4,
        dotted=dotted,
        text=token,
        is_rest=False,
        beam=source.beam if isinstance(source, MelodyEvent) else None,
        fermata=source.fermata if isinstance(source, MelodyEvent) else False,
        ornament=source.ornament if isinstance(source, MelodyEvent) else None,
        courtesy_accidental=source.courtesy_accidental if isinstance(source, MelodyEvent) else False,
        editorial_brackets=source.editorial_brackets if isinstance(source, MelodyEvent) else False,
        tie_from_previous=source.tie_from_previous if isinstance(source, MelodyEvent) else False,
        voice=source.voice if isinstance(source, MelodyEvent) else 0,
    )


def lyric_anchor_onsets(bar: Bar) -> list[int]:
    seen: set[int] = set()
    out: list[int] = []
    for row in getattr(bar, "lyric_event_rows", None) or []:
        for ev in row:
            if not _lyric_anchor_text(ev):
                continue
            if ev.onset_index in seen:
                continue
            seen.add(ev.onset_index)
            out.append(ev.onset_index)
    out.sort()
    return out


def _anchor_melody_events(bar: Bar) -> list[tuple[int, int, MelodyEvent | str]]:
    explicit = [ev for ev in getattr(bar, "melody_events", None) or [] if (ev.text or "").strip() or ev.is_rest]
    if explicit:
        return [(ev.onset_index, ev.onset_index, ev) for ev in explicit]
    # Structured FT3 lyrics are often available without an explicit melody lane.
    # Anchoring melody to lyric onsets drops chord attacks and produces sparse,
    # musically misleading note rows; use full chord fallback instead.
    return []


def _lyric_anchor_text(ev: LyricEvent) -> str:
    text = (ev.text or "").strip()
    if not text:
        return ""
    return text
